#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Analytical training pipeline for deep learning models (Paper 4).

PoE local learning with supervised conv weight estimation.
Uses PyTorch Conv2d/MaxPool2d for grid graphs when available,
numpy fallback otherwise.

Training:
    ConvLayer   -- supervised grid search over conv weights
    PoolLayer   -- stateless
    DenseLayer  -- ridge regression (closed-form)
    SoftmaxLayer -- stateless

Inference:
    PoE combination of per-stage expert heads (Theorem 8.3)
    + shrinkage correction (Theorem 4.4.1)
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

from uqa.operators._backend import (
    grid_forward,
    hop_weights_to_kernel,
    ridge_solve,
)

if TYPE_CHECKING:
    from uqa.engine import Engine


# -- Layer specification (training mode) ----------------------------------


@dataclass(frozen=True, slots=True)
class ConvSpec:
    """Convolution layer spec.

    n_channels > 1: random multi-channel conv (extreme learning machine).
    Random 3x3 kernels create diverse feature maps; ridge regression
    finds the optimal linear combination. This is the Bayesian approach:
    random weights = prior, ridge regression = posterior.
    """

    kernel_hops: int = 1
    n_channels: int = 1


@dataclass(frozen=True, slots=True)
class PoolSpec:
    """Pooling layer spec: method and pool_size."""

    method: str = "max"
    pool_size: int = 2


@dataclass(frozen=True, slots=True)
class FlattenSpec:
    """Flatten spatial nodes into a single vector."""


@dataclass(frozen=True, slots=True)
class DenseSpec:
    """Dense layer spec: output_channels is the target dimensionality."""

    output_channels: int = 10


@dataclass(frozen=True, slots=True)
class SoftmaxSpec:
    """Softmax classification head."""


LayerSpec = ConvSpec | PoolSpec | FlattenSpec | DenseSpec | SoftmaxSpec


# -- Trained model --------------------------------------------------------


@dataclass
class TrainedModel:
    """Persisted representation of a trained model."""

    model_name: str
    table_name: str | None
    label_field: str
    embedding_field: str
    edge_label: str
    gating: str
    lam: float
    layer_specs: list[dict[str, Any]]
    conv_weights: list[list[float]]
    dense_weights: list[float]
    dense_bias: list[float]
    dense_input_channels: int
    dense_output_channels: int
    num_classes: int
    class_labels: list[Any]
    grid_size: int = 0
    embedding_dim: int = 0
    training_accuracy: float = 0.0
    training_samples: int = 0
    # PoE expert heads (per conv+pool stage)
    expert_weights: list[list[float]] = field(default_factory=list)
    expert_biases: list[list[float]] = field(default_factory=list)
    expert_input_channels: list[int] = field(default_factory=list)
    shrinkage_alpha: float = 0.5
    # Multi-channel kernel storage
    conv_kernel_data: list[list[float]] = field(default_factory=list)
    conv_kernel_shapes: list[list[int]] = field(default_factory=list)
    in_channels: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> TrainedModel:
        return cls(**json.loads(s))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrainedModel:
        return cls(**d)

    def to_deep_fusion_layers(self) -> list[Any]:
        """Convert to inference-mode deep_fusion layers (final head only)."""
        from uqa.operators.deep_fusion import (
            ConvLayer,
            DenseLayer,
            FlattenLayer,
            PoolLayer,
            SoftmaxLayer,
        )

        layers: list[Any] = []
        conv_idx = 0

        for spec_dict in self.layer_specs:
            t = spec_dict["type"]
            if t == "conv":
                layers.append(
                    ConvLayer(
                        edge_label=self.edge_label,
                        hop_weights=tuple(self.conv_weights[conv_idx]),
                        direction="both",
                    )
                )
                conv_idx += 1
            elif t == "pool":
                layers.append(
                    PoolLayer(
                        edge_label=self.edge_label,
                        pool_size=spec_dict.get("pool_size", 2),
                        method=spec_dict.get("method", "max"),
                        direction="both",
                    )
                )
            elif t == "flatten":
                layers.append(FlattenLayer())
            elif t == "dense":
                layers.append(
                    DenseLayer(
                        weights=tuple(self.dense_weights),
                        bias=tuple(self.dense_bias),
                        output_channels=self.dense_output_channels,
                        input_channels=self.dense_input_channels,
                    )
                )
            elif t == "softmax":
                layers.append(SoftmaxLayer())

        return layers


# -- Supervised conv weight search ----------------------------------------


def _generate_kernels(
    n_channels: int,
    in_channels: int,
    seed: int = 42,
) -> NDArray[np.float32]:
    """Generate random conv kernels (Kaiming initialization).

    Returns (n_channels, in_channels, 3, 3) float32 array.
    """
    rng = np.random.RandomState(seed)
    fan_in = in_channels * 9
    std = (2.0 / fan_in) ** 0.5
    return (rng.randn(n_channels, in_channels, 3, 3) * std).astype(np.float32)


# -- Stage identification -------------------------------------------------


def _identify_stages(
    spec_dicts: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Identify (conv, pool) stage pairs from spec dicts."""
    stages: list[tuple[dict[str, Any], dict[str, Any]]] = []
    i = 0
    while i < len(spec_dicts):
        if spec_dicts[i]["type"] == "conv":
            conv_d = spec_dicts[i]
            if i + 1 < len(spec_dicts) and spec_dicts[i + 1]["type"] == "pool":
                pool_d = spec_dicts[i + 1]
                i += 2
            else:
                pool_d = {"type": "pool", "method": "max", "pool_size": 2}
                i += 1
            stages.append((conv_d, pool_d))
        else:
            i += 1
    return stages


# -- Training --------------------------------------------------------------


def train_model(
    engine: Engine,
    model_name: str,
    table_name: str | None,
    label_field: str,
    embedding_field: str,
    edge_label: str,
    layer_specs: list[LayerSpec],
    gating: str = "none",
    lam: float = 1.0,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Train via PoE local learning with supervised conv weight search.

    Two data sources:
    - rows=None: read all docs from table_name's document store
    - rows=list: use pre-filtered rows from SQL aggregate (WHERE clause)
    """
    if table_name is not None:
        table = engine._tables.get(table_name)
        if table is not None:
            # Store table_name for model persistence
            pass
    else:
        table = None

    if not layer_specs:
        raise ValueError("deep_learn requires at least one layer spec")
    spec_dicts = _specs_to_dicts(layer_specs)

    # Collect data from rows or document store
    labels_raw: list[Any] = []
    emb_list: list[np.ndarray] = []

    if rows is not None:
        # SQL aggregate mode: data from pre-filtered rows
        for row in rows:
            labels_raw.append(row.get(label_field))
            emb = row.get(embedding_field)
            if isinstance(emb, np.ndarray):
                emb_list.append(emb.astype(np.float32))
            elif emb is not None:
                emb_list.append(np.array(emb, dtype=np.float32))
    else:
        # Python API mode: read from document store
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        doc_store = table.document_store
        doc_ids = sorted(doc_store.doc_ids)
        if not doc_ids:
            raise ValueError(f"Table '{table_name}' has no documents")
        for doc_id in doc_ids:
            doc = doc_store.get(doc_id)
            if doc is None:
                continue
            labels_raw.append(doc.get(label_field))
            emb = doc.get(embedding_field)
            if isinstance(emb, np.ndarray):
                emb_list.append(emb.astype(np.float32))
            else:
                emb_list.append(np.array(emb, dtype=np.float32))

    if not emb_list:
        raise ValueError("No training data")

    embeddings = np.stack(emb_list)  # (n_samples, embedding_dim)
    embedding_dim = embeddings.shape[1]

    unique_labels = sorted(set(labels_raw))
    label_to_idx = {lab: i for i, lab in enumerate(unique_labels)}
    num_classes = len(unique_labels)

    dense_output = num_classes
    for spec in layer_specs:
        if isinstance(spec, DenseSpec):
            dense_output = spec.output_channels
            break

    # One-hot labels
    Y = np.zeros((len(labels_raw), dense_output), dtype=np.float64)
    for i, lab in enumerate(labels_raw):
        idx = label_to_idx[lab]
        if idx < dense_output:
            Y[i, idx] = 1.0

    # Grid detection: determine spatial size and input channels.
    in_channels = 0
    grid_size = 0
    for ch in [1, 3, 4]:
        if embedding_dim % ch != 0:
            continue
        side = int(np.sqrt(embedding_dim // ch))
        if side * side * ch == embedding_dim:
            in_channels = ch
            grid_size = side
            break

    if grid_size == 0:
        raise ValueError(
            f"Embedding dimension {embedding_dim} is not C*H*W "
            f"for any supported channel count."
        )

    stages = _identify_stages(spec_dicts)

    # Generate conv kernels per stage
    conv_kernels: list[NDArray[np.float32]] = []
    conv_weights: list[list[float]] = []
    in_ch = in_channels
    for stage_idx, (conv_d, _pool_d) in enumerate(stages):
        n_ch = conv_d.get("n_channels", 1)
        if n_ch > 1:
            # Multi-channel: random kernels (prior)
            kernels = _generate_kernels(n_ch, in_ch, seed=42 + stage_idx)
            conv_weights.append([])
        else:
            # Single-channel: placeholder, will be searched
            kernels = hop_weights_to_kernel([1.0, 0.0])
            conv_weights.append([1.0, 0.0])
        conv_kernels.append(kernels)
        in_ch = n_ch if n_ch > 1 else 1

    # Per-stage forward + ridge regression
    current_flat = embeddings
    cur_h, cur_w = grid_size, grid_size

    expert_weights_list: list[list[float]] = []
    expert_biases_list: list[list[float]] = []
    expert_input_channels: list[int] = []

    for stage_idx, (conv_d, pool_d) in enumerate(stages):
        pool_size = pool_d.get("pool_size", 2)
        pool_method = pool_d.get("method", "max")
        n_ch = conv_d.get("n_channels", 1)

        if n_ch <= 1:
            # Single-channel: supervised grid search
            candidates = [[1.0, a] for a in np.arange(-1.0, 1.05, 0.1)]
            best_acc = -1.0
            best_hw = [1.0, 0.0]
            for cand in candidates:
                k = hop_weights_to_kernel(cand)
                feats = grid_forward(
                    current_flat,
                    cur_h,
                    cur_w,
                    [(k, pool_size, pool_method)],
                    gating,
                )
                if feats.shape[1] == 0:
                    continue
                W_t, b_t = ridge_solve(feats.astype(np.float64), Y, lam)
                acc = float(
                    np.mean(
                        np.argmax(feats @ W_t.T + b_t, axis=1) == np.argmax(Y, axis=1)
                    )
                )
                if acc > best_acc:
                    best_acc = acc
                    best_hw = list(cand)
            conv_kernels[stage_idx] = hop_weights_to_kernel(best_hw)
            conv_weights[stage_idx] = best_hw

        # Forward through this stage
        current_flat = grid_forward(
            current_flat,
            cur_h,
            cur_w,
            [(conv_kernels[stage_idx], pool_size, pool_method)],
            gating,
        )
        cur_h = cur_h // pool_size
        cur_w = cur_w // pool_size

        # Train expert head
        X_stage = current_flat.astype(np.float64)
        W_stage, b_stage = ridge_solve(X_stage, Y, lam)
        expert_weights_list.append(W_stage.flatten().tolist())
        expert_biases_list.append(b_stage.flatten().tolist())
        expert_input_channels.append(X_stage.shape[1])

    # Final head
    X_final = current_flat.astype(np.float64)
    n_features = X_final.shape[1]
    W_final, b_final = ridge_solve(X_final, Y, lam)

    # PoE training accuracy
    shrinkage_alpha = 0.5

    # Recompute per-stage features for PoE
    stage_logits_list: list[np.ndarray] = []
    tmp = embeddings
    tmp_h, tmp_w = grid_size, grid_size
    for stage_idx, (_conv_d, pool_d) in enumerate(stages):
        ps = pool_d.get("pool_size", 2)
        pm = pool_d.get("method", "max")
        tmp = grid_forward(
            tmp, tmp_h, tmp_w, [(conv_kernels[stage_idx], ps, pm)], gating
        )
        tmp_h = tmp_h // ps
        tmp_w = tmp_w // ps
        eic = expert_input_channels[stage_idx]
        W_e = np.array(expert_weights_list[stage_idx]).reshape(dense_output, eic)
        b_e = np.array(expert_biases_list[stage_idx])
        stage_logits_list.append(tmp.astype(np.float64) @ W_e.T + b_e)

    logits_final = X_final @ W_final.T + b_final
    stage_logits_list.append(logits_final)

    # PoE: average logits + shrinkage
    n_experts = len(stage_logits_list)
    avg_logits = np.mean(stage_logits_list, axis=0)
    avg_logits += shrinkage_alpha * math.log(n_experts)

    predicted_classes = np.argmax(avg_logits, axis=1)
    true_classes = np.array([label_to_idx[lab] for lab in labels_raw])
    correct = int(np.sum(predicted_classes == true_classes))
    accuracy = correct / len(labels_raw) if labels_raw else 0.0

    # Store kernel data for reproducible inference
    conv_kernel_data = [k.flatten().tolist() for k in conv_kernels]
    conv_kernel_shapes = [list(k.shape) for k in conv_kernels]

    trained = TrainedModel(
        model_name=model_name,
        table_name=table_name,
        label_field=label_field,
        embedding_field=embedding_field,
        edge_label=edge_label,
        gating=gating,
        lam=lam,
        layer_specs=spec_dicts,
        conv_weights=conv_weights,
        conv_kernel_data=conv_kernel_data,
        conv_kernel_shapes=conv_kernel_shapes,
        dense_weights=W_final.flatten().tolist(),
        dense_bias=b_final.flatten().tolist(),
        dense_input_channels=n_features,
        dense_output_channels=dense_output,
        num_classes=num_classes,
        class_labels=[
            lab if not isinstance(lab, np.integer) else int(lab)
            for lab in unique_labels
        ],
        grid_size=grid_size,
        in_channels=in_channels,
        embedding_dim=embedding_dim,
        training_accuracy=accuracy,
        training_samples=len(labels_raw),
        expert_weights=expert_weights_list,
        expert_biases=expert_biases_list,
        expert_input_channels=expert_input_channels,
        shrinkage_alpha=shrinkage_alpha,
    )

    engine.save_model(model_name, trained.to_dict())

    return {
        "model_name": model_name,
        "training_samples": len(labels_raw),
        "num_classes": num_classes,
        "training_accuracy": accuracy,
        "feature_dim": n_features,
        "class_labels": trained.class_labels,
    }


# -- Inference -------------------------------------------------------------


def predict(
    engine: Engine,
    model_name: str,
    input_embedding: list[float],
) -> list[tuple[int, float]]:
    """Run PoE inference using a trained model.

    Uses the same grid-accelerated forward pass as training for consistency.
    """
    config = engine.load_model(model_name)
    if config is None:
        raise ValueError(f"Model '{model_name}' does not exist")

    model = TrainedModel.from_dict(config)
    stages = _identify_stages(model.layer_specs)
    has_experts = bool(model.expert_weights) and len(model.expert_weights) == len(
        stages
    )

    emb = np.array(input_embedding, dtype=np.float32)
    grid_size = model.grid_size

    # Reconstruct conv kernels from stored data
    conv_kernels: list[NDArray[np.float32]] = []
    if model.conv_kernel_data and model.conv_kernel_shapes:
        for kdata, kshape in zip(model.conv_kernel_data, model.conv_kernel_shapes):
            conv_kernels.append(np.array(kdata, dtype=np.float32).reshape(kshape))
    else:
        # Legacy: single-channel models with hop_weights only
        for cw in model.conv_weights:
            conv_kernels.append(hop_weights_to_kernel(cw))

    model_in_ch = getattr(model, "in_channels", 1)
    is_grid = (
        grid_size > 0 and grid_size * grid_size * model_in_ch == model.embedding_dim
    )
    if is_grid:
        # Grid-accelerated inference
        all_logits: list[np.ndarray] = []
        current_flat = emb.reshape(1, -1)
        cur_h, cur_w = grid_size, grid_size

        for stage_idx, (_conv_d, pool_d) in enumerate(stages):
            pool_size = pool_d.get("pool_size", 2)
            pool_method = pool_d.get("method", "max")

            current_flat = grid_forward(
                current_flat,
                cur_h,
                cur_w,
                [(conv_kernels[stage_idx], pool_size, pool_method)],
                model.gating,
            )
            cur_h = cur_h // pool_size
            cur_w = cur_w // pool_size

            # Expert head logits
            if has_experts:
                feat = current_flat[0].astype(np.float64)
                eic = model.expert_input_channels[stage_idx]
                W_e = np.array(model.expert_weights[stage_idx]).reshape(
                    model.dense_output_channels, eic
                )
                b_e = np.array(model.expert_biases[stage_idx])
                all_logits.append(W_e @ feat + b_e)

        # Final head
        feat_final = current_flat.reshape(-1).astype(np.float64)
        W_f = np.array(model.dense_weights).reshape(
            model.dense_output_channels, model.dense_input_channels
        )
        b_f = np.array(model.dense_bias)
        all_logits.append(W_f @ feat_final + b_f)

        # PoE: average logits + shrinkage
        n_experts = len(all_logits)
        avg_logits = np.mean(all_logits, axis=0)
        avg_logits += model.shrinkage_alpha * math.log(n_experts)

        # Softmax
        shifted = avg_logits - np.max(avg_logits)
        exp_vals = np.exp(shifted)
        probs = exp_vals / np.sum(exp_vals)
    else:
        # Fallback: BFS-based via DeepFusionOperator
        from uqa.operators.base import ExecutionContext
        from uqa.operators.deep_fusion import DeepFusionOperator, EmbedLayer

        tbl_name = model.table_name or ""
        table = engine._tables.get(tbl_name)
        if table is None:
            raise ValueError(f"Table '{tbl_name}' does not exist")

        embed = EmbedLayer(embedding=tuple(float(v) for v in input_embedding))
        fusion_layers = [embed, *model.to_deep_fusion_layers()]
        op = DeepFusionOperator(
            layers=fusion_layers,
            gating=model.gating,
            graph_name=tbl_name,
        )
        ctx = ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
            vector_indexes={},
            spatial_indexes={},
            graph_store=table.graph_store,
            block_max_index=None,
            index_manager=None,
            parallel_executor=None,
        )
        result_pl = op.execute(ctx)
        if not result_pl:
            return []
        entry = next(iter(result_pl))
        class_probs = entry.payload.fields.get("class_probs")
        if class_probs is not None:
            probs = np.array(class_probs)
        else:
            return [(0, entry.payload.score)]

    indices = np.argsort(-probs)
    return [(int(idx), float(probs[idx])) for idx in indices]


# -- Spec serialization ---------------------------------------------------


def _specs_to_dicts(specs: list[LayerSpec]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for spec in specs:
        if isinstance(spec, ConvSpec):
            result.append(
                {
                    "type": "conv",
                    "kernel_hops": spec.kernel_hops,
                    "n_channels": spec.n_channels,
                }
            )
        elif isinstance(spec, PoolSpec):
            result.append(
                {
                    "type": "pool",
                    "method": spec.method,
                    "pool_size": spec.pool_size,
                }
            )
        elif isinstance(spec, FlattenSpec):
            result.append({"type": "flatten"})
        elif isinstance(spec, DenseSpec):
            result.append(
                {
                    "type": "dense",
                    "output_channels": spec.output_channels,
                }
            )
        elif isinstance(spec, SoftmaxSpec):
            result.append({"type": "softmax"})
    return result


def _dicts_to_specs(dicts: list[dict[str, Any]]) -> list[LayerSpec]:
    result: list[LayerSpec] = []
    for d in dicts:
        t = d["type"]
        if t == "conv":
            result.append(ConvSpec(kernel_hops=d.get("kernel_hops", 1)))
        elif t == "pool":
            result.append(
                PoolSpec(method=d.get("method", "max"), pool_size=d.get("pool_size", 2))
            )
        elif t == "flatten":
            result.append(FlattenSpec())
        elif t == "dense":
            result.append(DenseSpec(output_channels=d.get("output_channels", 10)))
        elif t == "softmax":
            result.append(SoftmaxSpec())
    return result
