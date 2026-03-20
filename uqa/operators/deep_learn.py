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
    elastic_net_solve,
    grid_forward,
    hop_weights_to_kernel,
    magnitude_prune,
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


@dataclass(frozen=True, slots=True)
class AttentionSpec:
    """Self-attention layer spec (Theorem 8.3, Paper 4).

    Context-dependent PoE: attention weights determine how strongly
    each spatial position's evidence is weighted in the product.

    mode:
        "content"    -- Q=K=V=X, pure content-based attention
        "random_qk"  -- random Q,K projections, V=X (ELM prior)
        "learned_v"  -- random Q,K, learned V projection (supervised search)
    """

    n_heads: int = 1
    mode: str = "content"


LayerSpec = ConvSpec | PoolSpec | FlattenSpec | DenseSpec | SoftmaxSpec | AttentionSpec


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
    expert_accuracies: list[float] = field(default_factory=list)
    shrinkage_alpha: float = 0.5
    # Multi-channel kernel storage
    conv_kernel_data: list[list[float]] = field(default_factory=list)
    conv_kernel_shapes: list[list[int]] = field(default_factory=list)
    in_channels: int = 1
    # Self-attention parameters (per attention layer)
    attention_params: list[dict[str, Any]] = field(default_factory=list)
    # Pruning metadata
    l1_ratio: float = 0.0
    prune_ratio: float = 0.0
    weight_sparsity: float = 0.0

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
            AttentionLayer,
            ConvLayer,
            DenseLayer,
            FlattenLayer,
            PoolLayer,
            SoftmaxLayer,
        )

        layers: list[Any] = []
        conv_idx = 0
        attn_idx = 0

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
            elif t == "attention":
                ap = (
                    self.attention_params[attn_idx]
                    if attn_idx < len(self.attention_params)
                    else {}
                )
                layers.append(
                    AttentionLayer(
                        n_heads=ap.get("n_heads", 1),
                        mode=ap.get("mode", "content"),
                        q_weights=(tuple(ap["W_q"]) if "W_q" in ap else None),
                        q_shape=(tuple(ap["W_q_shape"]) if "W_q_shape" in ap else None),
                        k_weights=(tuple(ap["W_k"]) if "W_k" in ap else None),
                        k_shape=(tuple(ap["W_k_shape"]) if "W_k_shape" in ap else None),
                        v_weights=(tuple(ap["W_v"]) if "W_v" in ap else None),
                        v_shape=(tuple(ap["W_v_shape"]) if "W_v_shape" in ap else None),
                    )
                )
                attn_idx += 1
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


_Operation = tuple[str, ...]  # ("stage", conv_d, pool_d) | ("attention", attn_d)


def _identify_operations(
    spec_dicts: list[dict[str, Any]],
) -> list[tuple[Any, ...]]:
    """Build ordered list of operations from spec dicts.

    Returns ("stage", conv_d, pool_d) for conv+pool pairs
    and ("attention", attn_d) for attention layers.
    """
    ops: list[tuple[Any, ...]] = []
    i = 0
    while i < len(spec_dicts):
        d = spec_dicts[i]
        if d["type"] == "conv":
            conv_d = d
            if i + 1 < len(spec_dicts) and spec_dicts[i + 1]["type"] == "pool":
                pool_d = spec_dicts[i + 1]
                i += 2
            else:
                pool_d = {"type": "pool", "method": "max", "pool_size": 2}
                i += 1
            ops.append(("stage", conv_d, pool_d))
        elif d["type"] == "attention":
            ops.append(("attention", d))
            i += 1
        else:
            i += 1
    return ops


# -- Self-attention training -----------------------------------------------


def _train_attention(
    X_flat: np.ndarray,
    grid_h: int,
    grid_w: int,
    n_channels: int,
    n_heads: int,
    mode: str,
    Y: np.ndarray,
    lam: float,
    gating: str = "none",
    seed: int = 42,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply self-attention during training.

    Returns (out_flat, params_dict).
    """
    from uqa.operators._backend import (
        batch_self_attention,
        generate_qk_projections,
        search_v_projection,
    )

    batch = X_flat.shape[0]
    seq_len = grid_h * grid_w
    d_model = n_channels

    # (batch, C*H*W) -> (batch, H*W, C) = (batch, seq_len, d_model)
    X_3d = X_flat.reshape(batch, d_model, seq_len).transpose(0, 2, 1).astype(np.float32)

    params: dict[str, Any] = {"mode": mode, "n_heads": n_heads, "d_model": d_model}
    W_q: np.ndarray | None = None
    W_k: np.ndarray | None = None

    if mode in ("random_qk", "learned_v"):
        W_q, W_k = generate_qk_projections(d_model, seed)
        params["W_q"] = W_q.flatten().tolist()
        params["W_q_shape"] = list(W_q.shape)
        params["W_k"] = W_k.flatten().tolist()
        params["W_k_shape"] = list(W_k.shape)

    if mode == "learned_v":
        # GPU-optimized: Q,K computed once, ridge on GPU, no redundant pass
        W_v, out_flat = search_v_projection(
            X_3d,
            n_heads,
            W_q,
            W_k,
            Y,
            lam,
            gating,
            seed=seed,
        )
        params["W_v"] = W_v.flatten().tolist()
        params["W_v_shape"] = list(W_v.shape)
        return out_flat, params

    out_3d = batch_self_attention(X_3d, n_heads, W_q, W_k, None, gating)

    # (batch, H*W, C) -> (batch, C*H*W)
    out_flat = out_3d.transpose(0, 2, 1).reshape(batch, -1)
    return out_flat, params


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
    l1_ratio: float = 0.0,
    prune_ratio: float = 0.0,
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

    ops = _identify_operations(spec_dicts)
    stages_only = [(op[1], op[2]) for op in ops if op[0] == "stage"]

    # Generate conv kernels per stage
    conv_kernels: list[NDArray[np.float32]] = []
    conv_weights: list[list[float]] = []
    in_ch = in_channels
    for stage_idx, (conv_d, _pool_d) in enumerate(stages_only):
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

    # Per-operation forward + ridge regression
    current_flat = embeddings
    cur_h, cur_w = grid_size, grid_size

    expert_weights_list: list[list[float]] = []
    expert_biases_list: list[list[float]] = []
    expert_input_channels: list[int] = []
    attention_params_list: list[dict[str, Any]] = []
    expert_accuracies: list[float] = []
    true_classes = np.array([label_to_idx[lab] for lab in labels_raw])

    stage_idx = 0
    attn_idx = 0
    for op in ops:
        if op[0] == "stage":
            conv_d, pool_d = op[1], op[2]
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
                            np.argmax(feats @ W_t.T + b_t, axis=1)
                            == np.argmax(Y, axis=1)
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
            stage_idx += 1

        elif op[0] == "attention":
            attn_d = op[1]
            n_heads = attn_d.get("n_heads", 1)
            mode = attn_d.get("mode", "content")
            n_ch_attn = current_flat.shape[1] // (cur_h * cur_w)

            current_flat, attn_params = _train_attention(
                current_flat,
                cur_h,
                cur_w,
                n_ch_attn,
                n_heads,
                mode,
                Y,
                lam,
                gating,
                seed=42 + attn_idx,
            )
            attention_params_list.append(attn_params)
            attn_idx += 1

        # Train expert head (for both stage and attention operations)
        X_stage = current_flat.astype(np.float64)
        if l1_ratio > 0:
            W_stage, b_stage = elastic_net_solve(X_stage, Y, lam, l1_ratio)
        else:
            W_stage, b_stage = ridge_solve(X_stage, Y, lam)
        if prune_ratio > 0:
            W_stage = magnitude_prune(W_stage, prune_ratio)
        expert_weights_list.append(W_stage.flatten().tolist())
        expert_biases_list.append(b_stage.flatten().tolist())
        expert_input_channels.append(X_stage.shape[1])
        # Per-stage accuracy for weighted PoE
        stage_pred = np.argmax(X_stage @ W_stage.T + b_stage, axis=1)
        stage_acc = float(np.mean(stage_pred == true_classes))
        expert_accuracies.append(stage_acc)

    # Final head
    X_final = current_flat.astype(np.float64)
    n_features = X_final.shape[1]
    if l1_ratio > 0:
        W_final, b_final = elastic_net_solve(X_final, Y, lam, l1_ratio)
    else:
        W_final, b_final = ridge_solve(X_final, Y, lam)
    if prune_ratio > 0:
        W_final = magnitude_prune(W_final, prune_ratio)
    final_pred = np.argmax(X_final @ W_final.T + b_final, axis=1)
    final_acc = float(np.mean(final_pred == true_classes))
    expert_accuracies.append(final_acc)

    # PoE training accuracy
    # Shrinkage from diversity prior: 1 / (2 * sqrt(n_experts))
    n_ops = len(ops)
    n_expert_stages = n_ops + 1  # operation experts + final head
    shrinkage_alpha = 1.0 / (2.0 * math.sqrt(n_expert_stages))

    # Recompute per-operation features for PoE
    op_logits_list: list[np.ndarray] = []
    tmp = embeddings
    tmp_h, tmp_w = grid_size, grid_size
    tmp_stage_idx = 0
    tmp_attn_idx = 0
    for op_idx, op in enumerate(ops):
        if op[0] == "stage":
            _conv_d, pool_d = op[1], op[2]
            ps = pool_d.get("pool_size", 2)
            pm = pool_d.get("method", "max")
            tmp = grid_forward(
                tmp,
                tmp_h,
                tmp_w,
                [(conv_kernels[tmp_stage_idx], ps, pm)],
                gating,
            )
            tmp_h = tmp_h // ps
            tmp_w = tmp_w // ps
            tmp_stage_idx += 1
        elif op[0] == "attention":
            ap = attention_params_list[tmp_attn_idx]
            n_ch_tmp = tmp.shape[1] // (tmp_h * tmp_w)
            batch_n = tmp.shape[0]
            seq_l = tmp_h * tmp_w
            tmp_3d = (
                tmp.reshape(batch_n, n_ch_tmp, seq_l)
                .transpose(0, 2, 1)
                .astype(np.float32)
            )
            from uqa.operators._backend import batch_self_attention

            W_q_t = (
                np.array(ap["W_q"], dtype=np.float32).reshape(ap["W_q_shape"])
                if "W_q" in ap
                else None
            )
            W_k_t = (
                np.array(ap["W_k"], dtype=np.float32).reshape(ap["W_k_shape"])
                if "W_k" in ap
                else None
            )
            W_v_t = (
                np.array(ap["W_v"], dtype=np.float32).reshape(ap["W_v_shape"])
                if "W_v" in ap
                else None
            )
            out_3d = batch_self_attention(
                tmp_3d,
                ap.get("n_heads", 1),
                W_q_t,
                W_k_t,
                W_v_t,
                gating,
            )
            tmp = out_3d.transpose(0, 2, 1).reshape(batch_n, -1)
            tmp_attn_idx += 1

        eic = expert_input_channels[op_idx]
        W_e = np.array(expert_weights_list[op_idx]).reshape(dense_output, eic)
        b_e = np.array(expert_biases_list[op_idx])
        op_logits_list.append(tmp.astype(np.float64) @ W_e.T + b_e)

    logits_final = X_final @ W_final.T + b_final
    op_logits_list.append(logits_final)

    # PoE: average logits + shrinkage
    n_experts = len(op_logits_list)
    avg_logits = np.mean(op_logits_list, axis=0)
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
        expert_accuracies=expert_accuracies,
        shrinkage_alpha=shrinkage_alpha,
        attention_params=attention_params_list,
        l1_ratio=l1_ratio,
        prune_ratio=prune_ratio,
        weight_sparsity=float(
            np.mean(np.array(W_final.flatten()) == 0)
            if prune_ratio > 0 or l1_ratio > 0
            else 0.0
        ),
    )

    engine.save_model(model_name, trained.to_dict())

    return {
        "model_name": model_name,
        "training_samples": len(labels_raw),
        "num_classes": num_classes,
        "training_accuracy": accuracy,
        "feature_dim": n_features,
        "class_labels": trained.class_labels,
        "l1_ratio": l1_ratio,
        "prune_ratio": prune_ratio,
        "weight_sparsity": trained.weight_sparsity,
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
    ops = _identify_operations(model.layer_specs)
    n_ops = len(ops)
    has_experts = bool(model.expert_weights) and len(model.expert_weights) == n_ops

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

        stage_idx = 0
        attn_idx = 0
        for op_idx, op in enumerate(ops):
            if op[0] == "stage":
                _conv_d, pool_d = op[1], op[2]
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
                stage_idx += 1

            elif op[0] == "attention":
                from uqa.operators._backend import batch_self_attention

                n_ch = current_flat.shape[1] // (cur_h * cur_w)
                seq_len = cur_h * cur_w
                X_3d = (
                    current_flat.reshape(1, n_ch, seq_len)
                    .transpose(0, 2, 1)
                    .astype(np.float32)
                )
                ap = (
                    model.attention_params[attn_idx]
                    if attn_idx < len(model.attention_params)
                    else {}
                )
                W_q = (
                    np.array(ap["W_q"], dtype=np.float32).reshape(ap["W_q_shape"])
                    if "W_q" in ap
                    else None
                )
                W_k = (
                    np.array(ap["W_k"], dtype=np.float32).reshape(ap["W_k_shape"])
                    if "W_k" in ap
                    else None
                )
                W_v = (
                    np.array(ap["W_v"], dtype=np.float32).reshape(ap["W_v_shape"])
                    if "W_v" in ap
                    else None
                )
                out_3d = batch_self_attention(
                    X_3d,
                    ap.get("n_heads", 1),
                    W_q,
                    W_k,
                    W_v,
                    model.gating,
                )
                current_flat = out_3d.transpose(0, 2, 1).reshape(1, -1)
                attn_idx += 1

            # Expert head logits
            if has_experts:
                feat = current_flat[0].astype(np.float64)
                eic = model.expert_input_channels[op_idx]
                W_e = np.array(model.expert_weights[op_idx]).reshape(
                    model.dense_output_channels, eic
                )
                b_e = np.array(model.expert_biases[op_idx])
                all_logits.append(W_e @ feat + b_e)

        # Final head
        feat_final = current_flat.reshape(-1).astype(np.float64)
        W_f = np.array(model.dense_weights).reshape(
            model.dense_output_channels, model.dense_input_channels
        )
        b_f = np.array(model.dense_bias)
        all_logits.append(W_f @ feat_final + b_f)

        # PoE: accuracy-weighted logit combination
        n_experts = len(all_logits)
        accs = getattr(model, "expert_accuracies", [])
        if accs and len(accs) == n_experts:
            weights = np.array(accs, dtype=np.float64)
            weights = weights / weights.sum()
            avg_logits = sum(w * l for w, l in zip(weights, all_logits))
        else:
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
        elif isinstance(spec, AttentionSpec):
            result.append(
                {
                    "type": "attention",
                    "n_heads": spec.n_heads,
                    "mode": spec.mode,
                }
            )
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
        elif t == "attention":
            result.append(
                AttentionSpec(
                    n_heads=d.get("n_heads", 1),
                    mode=d.get("mode", "content"),
                )
            )
    return result
