#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.hybrid import _coverage_based_default

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


_PROB_FLOOR = 1e-15
_PROB_CEIL = 1.0 - 1e-15


def _safe_logit(p: float) -> float:
    """Convert probability to logit with clamping."""
    p = max(_PROB_FLOOR, min(_PROB_CEIL, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _apply_gating(logit: float, gating: str) -> float:
    """Apply gating function to a logit value."""
    if gating == "relu":
        return max(0.0, logit)
    if gating == "swish":
        return logit * _sigmoid(logit)
    return logit


def _sigmoid_vec(x: np.ndarray) -> np.ndarray:
    """Element-wise numerically stable sigmoid on a numpy array."""
    return np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-x)),
        np.exp(x) / (1.0 + np.exp(x)),
    )


def _apply_gating_vec(vec: np.ndarray, gating: str) -> np.ndarray:
    """Apply gating function element-wise to a numpy array."""
    if gating == "relu":
        return np.maximum(0.0, vec)
    if gating == "swish":
        return vec * _sigmoid_vec(vec)
    return vec


# -- Layer dataclasses --


@dataclass(frozen=True, slots=True)
class SignalLayer:
    """Groups signals for same-layer log-odds conjunction."""

    signals: list[Operator]


@dataclass(frozen=True, slots=True)
class PropagateLayer:
    """Propagates previous layer scores through graph edges."""

    edge_label: str
    aggregation: str  # "mean" | "sum" | "max"
    direction: str  # "both" | "out" | "in"


@dataclass(frozen=True, slots=True)
class ConvLayer:
    """Weighted multi-hop aggregation over graph neighborhoods (CNN).

    Performs BFS-style neighborhood aggregation where each hop distance
    has its own weight.  The weighted average of neighbor probabilities
    at each hop ring is computed, then converted to logit and added as
    a residual connection.

    hop_weights[0] = self weight (identity / skip connection)
    hop_weights[1] = 1-hop neighbors (3x3 equivalent on grid)
    hop_weights[2] = 2-hop neighbors (5x5 receptive field)
    ...

    Weights are internally normalized to sum to 1 so the convolved
    value remains a valid probability in (0, 1).
    """

    edge_label: str
    hop_weights: tuple[float, ...]  # (w_self, w_1hop, w_2hop, ...)
    direction: str  # "both" | "out" | "in"
    # Multi-channel kernel: (out_ch, in_ch, kH, kW) flattened + shape
    kernel: tuple[float, ...] | None = None
    kernel_shape: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class PoolLayer:
    """Spatial downsampling via greedy graph partitioning.

    Groups pool_size neighboring nodes via BFS, aggregates their
    channel vectors element-wise (max or avg), and keeps the
    smallest doc_id as representative.  Reduces active node count.
    """

    edge_label: str
    pool_size: int  # >= 2
    method: str  # "max" | "avg"
    direction: str  # "both" | "out" | "in"


@dataclass(frozen=True, slots=True)
class DenseLayer:
    """Fully connected layer: out = W @ input + bias, then gating."""

    weights: tuple[float, ...]  # flattened (out_ch, in_ch)
    bias: tuple[float, ...]  # (out_ch,)
    output_channels: int
    input_channels: int


@dataclass(frozen=True, slots=True)
class FlattenLayer:
    """Concatenates all spatial nodes into a single vector."""


@dataclass(frozen=True, slots=True)
class SoftmaxLayer:
    """Numerically stable softmax classification head."""


@dataclass(frozen=True, slots=True)
class BatchNormLayer:
    """Per-channel batch normalization across all nodes."""

    epsilon: float = 1e-5


@dataclass(frozen=True, slots=True)
class DropoutLayer:
    """Inference-mode dropout: scales values by (1 - p)."""

    p: float


@dataclass(frozen=True, slots=True)
class AttentionLayer:
    """Self-attention: context-dependent PoE (Theorem 8.3, Paper 4).

    Attention weights are the expert reliability coefficients in
    a Product of Experts.  Each spatial position attends to all others,
    enabling global context injection between conv+pool stages.

    Modes:
        "content"    -- Q=K=V=X, pure content-based attention
        "random_qk"  -- random Q,K projections, V=X
        "learned_v"  -- random Q,K, learned V projection
    """

    n_heads: int = 1
    mode: str = "content"
    q_weights: tuple[float, ...] | None = None
    q_shape: tuple[int, ...] | None = None
    k_weights: tuple[float, ...] | None = None
    k_shape: tuple[int, ...] | None = None
    v_weights: tuple[float, ...] | None = None
    v_shape: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class EmbedLayer:
    """Initialize channel_map from a raw embedding vector.

    Unpacks a vector into per-node single-channel values:
    element i -> node (i+1) with channel value = embedding[i].

    This is the classification counterpart to SignalLayer:
    - SignalLayer: retrieval (scores from knn_match, text_match, etc.)
    - EmbedLayer: classification (raw values from a learned model input)
    """

    embedding: tuple[float, ...]
    grid_h: int = 0
    grid_w: int = 0
    in_channels: int = 1


# Type alias for all layer types
_Layer = (
    SignalLayer
    | PropagateLayer
    | ConvLayer
    | PoolLayer
    | DenseLayer
    | FlattenLayer
    | SoftmaxLayer
    | BatchNormLayer
    | DropoutLayer
    | EmbedLayer
    | AttentionLayer
)

_SPATIAL_LAYERS = (PropagateLayer, ConvLayer, PoolLayer)


class DeepFusionOperator(Operator):
    """Multi-layer fusion operator (Paper 4, Section 7).

    Implements deep Bayesian fusion as a multi-layer network:

        l^(k) = g( l^(k-1) + sum_j logit(P_j^(k)) )
        P_final = sigmoid(l^(K))

    Each layer is either a SignalLayer (log-odds conjunction of operator
    signals, added as residual) or a PropagateLayer (graph neighbor
    aggregation that spreads scores through edges).

    This is a ResNet when layers are signal groups, and a GNN when layers
    propagate scores through graph edges.

    Internal data model uses channel_map: dict[int, np.ndarray] where
    each value has shape (num_channels,).  Single-channel (num_channels=1)
    is backward compatible with the original scalar logit model.
    Existing layers (Signal, Propagate, Conv) operate on channel 0 only.
    New layers (Dense, Flatten, Softmax, BatchNorm, Dropout) operate on
    all channels.
    """

    def __init__(
        self,
        layers: list[_Layer],
        alpha: float = 0.5,
        gating: str = "none",
        graph_name: str = "",
    ) -> None:
        if not layers:
            raise ValueError("deep_fusion requires at least one layer")
        if isinstance(layers[0], _SPATIAL_LAYERS):
            raise ValueError(
                "deep_fusion: first layer must be a SignalLayer or "
                "EmbedLayer (no scores to propagate or convolve)"
            )
        # Validate layer ordering and parameters
        flattened = False
        for layer in layers:
            if isinstance(layer, _SPATIAL_LAYERS) and flattened:
                raise ValueError(
                    "deep_fusion: spatial layers (propagate, convolve, pool) "
                    "must not appear after flatten()"
                )
            if isinstance(layer, FlattenLayer):
                flattened = True
            if isinstance(layer, PoolLayer) and layer.pool_size < 2:
                raise ValueError("deep_fusion: pool() pool_size must be >= 2")
            if isinstance(layer, DropoutLayer) and not (0 < layer.p < 1):
                raise ValueError("deep_fusion: dropout() p must be in (0, 1)")

        self.layers = layers
        self.alpha = alpha
        self.gating = gating
        self.graph_name = graph_name
        # EmbedLayer input: conv operates on raw values (graph convolution).
        # SignalLayer input: conv operates in logit space (Bayesian fusion).
        self.embed_mode = isinstance(layers[0], EmbedLayer)
        # Grid acceleration: when EmbedLayer provides grid dimensions,
        # conv/pool use PyTorch Conv2d/MaxPool2d instead of BFS.
        if self.embed_mode:
            el = layers[0]
            assert isinstance(el, EmbedLayer)
            if el.grid_h > 0 and el.grid_w > 0:
                self._grid_shape: tuple[int, int] | None = (el.grid_h, el.grid_w)
            else:
                self._grid_shape = None
        else:
            self._grid_shape = None

    def execute(self, context: ExecutionContext) -> PostingList:
        from bayesian_bm25 import log_odds_conjunction

        channel_map: dict[int, np.ndarray] = {}
        num_channels = 1
        softmax_applied = False

        # Grid acceleration: batch conv+pool sequences via backend
        if self._grid_shape is not None:
            channel_map, num_channels, softmax_applied = self._execute_grid(
                channel_map,
                num_channels,
                softmax_applied,
                log_odds_conjunction,
                context,
            )
        else:
            for layer in self.layers:
                if isinstance(layer, EmbedLayer):
                    self._execute_embed_layer(layer, channel_map)
                elif isinstance(layer, SignalLayer):
                    self._execute_signal_layer(
                        layer, context, channel_map, num_channels, log_odds_conjunction
                    )
                elif isinstance(layer, PropagateLayer):
                    self._execute_propagate_layer(
                        layer, context, channel_map, num_channels
                    )
                elif isinstance(layer, ConvLayer):
                    self._execute_conv_layer(layer, context, channel_map)
                elif isinstance(layer, PoolLayer):
                    self._execute_pool_layer(layer, context, channel_map)
                elif isinstance(layer, DenseLayer):
                    self._execute_dense_layer(layer, channel_map)
                    num_channels = layer.output_channels
                elif isinstance(layer, FlattenLayer):
                    channel_map, num_channels = self._execute_flatten_layer(channel_map)
                elif isinstance(layer, SoftmaxLayer):
                    self._execute_softmax_layer(channel_map)
                    softmax_applied = True
                elif isinstance(layer, BatchNormLayer):
                    self._execute_batchnorm_layer(layer, channel_map)
                elif isinstance(layer, DropoutLayer):
                    self._execute_dropout_layer(layer, channel_map)
                elif isinstance(layer, AttentionLayer):
                    self._execute_attention_layer(layer, channel_map)

        return self._build_result(channel_map, num_channels, softmax_applied)

    # -- Result builder --

    @staticmethod
    def _build_result(
        channel_map: dict[int, np.ndarray],
        num_channels: int,
        softmax_applied: bool,
    ) -> PostingList:
        if not channel_map:
            return PostingList()

        entries: list[PostingEntry] = []
        for doc_id in sorted(channel_map):
            vec = channel_map[doc_id]
            if softmax_applied:
                score = float(np.max(vec))
                fields: dict[str, object] = {"class_probs": vec.tolist()}
                entries.append(
                    PostingEntry(doc_id, Payload(score=score, fields=fields))
                )
            elif num_channels == 1:
                score = _sigmoid(float(vec[0]))
                entries.append(PostingEntry(doc_id, Payload(score=score)))
            else:
                score = float(_sigmoid_vec(vec).max())
                entries.append(PostingEntry(doc_id, Payload(score=score)))

        return PostingList.from_sorted(entries)

    # -- Existing layer executors (channel 0 only) --

    def _execute_signal_layer(
        self,
        layer: SignalLayer,
        context: ExecutionContext,
        channel_map: dict[int, np.ndarray],
        num_channels: int,
        log_odds_conjunction: object,
    ) -> None:
        """Execute a signal layer: run signals, fuse within layer, add residual to channel 0."""
        signals = layer.signals

        par = context.parallel_executor
        if par is not None and par.enabled:
            posting_lists = par.execute_branches(signals, context)
        else:
            posting_lists = [sig.execute(context) for sig in signals]

        # Build per-signal score maps and collect all doc_ids
        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        if not all_doc_ids:
            return

        num_docs = len(all_doc_ids)
        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        alpha = self.alpha
        gating = self.gating

        if len(signals) == 1:
            # Single signal: direct passthrough, no conjunction needed
            smap = score_maps[0]
            default = defaults[0]
            for doc_id in all_doc_ids:
                p = smap.get(doc_id, default)
                layer_logit = _safe_logit(p)
                layer_logit = _apply_gating(layer_logit, gating)
                if doc_id not in channel_map:
                    channel_map[doc_id] = np.zeros(num_channels)
                channel_map[doc_id][0] += layer_logit
        else:
            # Multiple signals: log-odds conjunction within layer
            for doc_id in all_doc_ids:
                probs = [
                    smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)
                ]
                fused_p = float(
                    log_odds_conjunction(probs, alpha=alpha, gating="none")  # type: ignore[operator]
                )
                layer_logit = _safe_logit(fused_p)
                layer_logit = _apply_gating(layer_logit, gating)
                if doc_id not in channel_map:
                    channel_map[doc_id] = np.zeros(num_channels)
                channel_map[doc_id][0] += layer_logit

    def _execute_propagate_layer(
        self,
        layer: PropagateLayer,
        context: ExecutionContext,
        channel_map: dict[int, np.ndarray],
        num_channels: int,
    ) -> None:
        """Propagate scores through graph edges (channel 0 only)."""
        gs = context.graph_store
        if gs is None:
            raise ValueError(
                "deep_fusion propagate layer requires a graph_store in ExecutionContext"
            )

        # Convert channel 0 to probabilities
        prob_map: dict[int, float] = {}
        for doc_id, vec in channel_map.items():
            prob_map[doc_id] = _sigmoid(float(vec[0]))

        new_map: dict[int, np.ndarray] = {}
        direction = layer.direction
        edge_label = layer.edge_label
        aggregation = layer.aggregation
        graph_name = self.graph_name
        gating = self.gating

        # Collect all vertices that could be affected
        all_vertex_ids = set(channel_map.keys())

        # Also discover neighbors of existing docs
        for doc_id in list(all_vertex_ids):
            if direction in ("out", "both"):
                for nb in gs.neighbors(doc_id, edge_label, "out", graph=graph_name):
                    all_vertex_ids.add(nb)
            if direction in ("in", "both"):
                for nb in gs.neighbors(doc_id, edge_label, "in", graph=graph_name):
                    all_vertex_ids.add(nb)

        for vid in all_vertex_ids:
            neighbor_probs: list[float] = []

            if direction in ("out", "both"):
                for nb in gs.neighbors(vid, edge_label, "out", graph=graph_name):
                    if nb in prob_map:
                        neighbor_probs.append(prob_map[nb])
            if direction in ("in", "both"):
                for nb in gs.neighbors(vid, edge_label, "in", graph=graph_name):
                    if nb in prob_map:
                        neighbor_probs.append(prob_map[nb])

            if not neighbor_probs:
                # No neighbors with scores: keep existing channels (residual)
                if vid in channel_map:
                    new_map[vid] = channel_map[vid].copy()
                continue

            if aggregation == "mean":
                agg_prob = sum(neighbor_probs) / len(neighbor_probs)
            elif aggregation == "sum":
                agg_prob = min(_PROB_CEIL, sum(neighbor_probs))
            elif aggregation == "max":
                agg_prob = max(neighbor_probs)
            else:
                agg_prob = sum(neighbor_probs) / len(neighbor_probs)

            propagated_logit = _safe_logit(agg_prob)
            propagated_logit = _apply_gating(propagated_logit, gating)

            # Residual connection on channel 0, preserve other channels
            existing = channel_map.get(vid)
            if existing is not None:
                new_vec = existing.copy()
                new_vec[0] = float(existing[0]) + propagated_logit
            else:
                new_vec = np.zeros(num_channels)
                new_vec[0] = propagated_logit
            new_map[vid] = new_vec

        channel_map.clear()
        channel_map.update(new_map)

    def _execute_conv_layer(
        self,
        layer: ConvLayer,
        context: ExecutionContext,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Weighted multi-hop convolution over graph neighborhoods (channel 0 only).

        Two modes:
        - Logit mode (SignalLayer input): sigmoid -> weighted avg -> logit -> residual.
          This is Bayesian log-odds fusion.
        - Raw mode (EmbedLayer input): weighted avg of raw values -> gating.
          This is standard graph convolution preserving full dynamic range.
        """
        gs = context.graph_store
        if gs is None:
            raise ValueError(
                "deep_fusion convolve layer requires a graph_store in ExecutionContext"
            )

        embed_mode = self.embed_mode

        # Build value map: raw values or sigmoid-transformed probabilities
        val_map: dict[int, float] = {}
        for doc_id, vec in channel_map.items():
            if embed_mode:
                val_map[doc_id] = float(vec[0])
            else:
                val_map[doc_id] = _sigmoid(float(vec[0]))

        # Normalize hop weights
        total_w = sum(layer.hop_weights)
        if total_w <= 0:
            return
        norm_weights = [w / total_w for w in layer.hop_weights]

        new_map: dict[int, np.ndarray] = {}
        edge_label = layer.edge_label
        direction = layer.direction
        graph_name = self.graph_name
        gating = self.gating
        kernel_hops = len(layer.hop_weights) - 1

        for vid in list(channel_map.keys()):
            weighted_val = 0.0

            # Hop 0: self
            if vid in val_map:
                weighted_val += norm_weights[0] * val_map[vid]

            # Hop 1..kernel_hops: BFS rings
            current_frontier = {vid}
            visited = {vid}
            for h in range(1, kernel_hops + 1):
                next_frontier: set[int] = set()
                for fv in current_frontier:
                    for nb in _graph_neighbors(
                        gs, fv, edge_label, direction, graph_name
                    ):
                        if nb not in visited:
                            next_frontier.add(nb)
                            visited.add(nb)

                if next_frontier:
                    hop_vals = [val_map[nb] for nb in next_frontier if nb in val_map]
                    if hop_vals:
                        hop_mean = sum(hop_vals) / len(hop_vals)
                        weighted_val += norm_weights[h] * hop_mean

                current_frontier = next_frontier

            new_vec = channel_map[vid].copy()
            if embed_mode:
                # Raw mode: replace with weighted average, then gating
                new_vec[0] = _apply_gating(weighted_val, gating)
            else:
                # Logit mode: convert to logit, add as residual
                conv_logit = _safe_logit(
                    max(_PROB_FLOOR, min(_PROB_CEIL, weighted_val))
                )
                conv_logit = _apply_gating(conv_logit, gating)
                new_vec[0] = float(channel_map[vid][0]) + conv_logit
            new_map[vid] = new_vec

        channel_map.clear()
        channel_map.update(new_map)

    # -- New layer executors --

    def _execute_pool_layer(
        self,
        layer: PoolLayer,
        context: ExecutionContext,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Spatial downsampling via greedy BFS partitioning."""
        gs = context.graph_store
        if gs is None:
            raise ValueError(
                "deep_fusion pool layer requires a graph_store in ExecutionContext"
            )

        graph_name = self.graph_name
        edge_label = layer.edge_label
        direction = layer.direction
        pool_size = layer.pool_size
        method = layer.method

        remaining = set(channel_map.keys())
        pooled: dict[int, np.ndarray] = {}

        while remaining:
            # Seed from the smallest unvisited doc_id (deterministic)
            seed = min(remaining)
            remaining.discard(seed)

            # BFS to collect pool_size - 1 more neighbors
            group = [seed]
            frontier = {seed}
            visited_bfs = {seed}

            while len(group) < pool_size and frontier:
                next_frontier: set[int] = set()
                for fv in frontier:
                    for nb in _graph_neighbors(
                        gs, fv, edge_label, direction, graph_name
                    ):
                        if nb not in visited_bfs:
                            visited_bfs.add(nb)
                            next_frontier.add(nb)
                            if nb in remaining:
                                group.append(nb)
                                remaining.discard(nb)
                                if len(group) >= pool_size:
                                    break
                    if len(group) >= pool_size:
                        break
                frontier = next_frontier

            # Aggregate channel vectors element-wise
            vecs = np.stack([channel_map[g] for g in group])
            if method == "max":
                agg = np.max(vecs, axis=0)
            else:  # "avg"
                agg = np.mean(vecs, axis=0)

            # Representative: min doc_id in group
            rep = min(group)
            pooled[rep] = agg

        channel_map.clear()
        channel_map.update(pooled)

    def _execute_dense_layer(
        self,
        layer: DenseLayer,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Fully connected: out = W @ input + bias, then gating (batch)."""
        from uqa.operators._backend import batch_dense

        w_mat = np.array(layer.weights).reshape(
            layer.output_channels, layer.input_channels
        )
        bias = np.array(layer.bias)
        gating = self.gating

        doc_ids = sorted(channel_map.keys())
        X = np.stack([channel_map[did] for did in doc_ids])
        out = batch_dense(X, w_mat, bias, gating)
        for i, did in enumerate(doc_ids):
            channel_map[did] = out[i]

    @staticmethod
    def _execute_flatten_layer(
        channel_map: dict[int, np.ndarray],
    ) -> tuple[dict[int, np.ndarray], int]:
        """Sort nodes by doc_id, concatenate all channel vectors into one."""
        if not channel_map:
            return {}, 0

        sorted_ids = sorted(channel_map.keys())
        flat_vec = np.concatenate([channel_map[did] for did in sorted_ids])
        new_num_channels = len(flat_vec)

        # Use the minimum doc_id as the representative
        rep_id = sorted_ids[0]
        return {rep_id: flat_vec}, new_num_channels

    @staticmethod
    def _execute_softmax_layer(
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Numerically stable softmax per node (batch)."""
        from uqa.operators._backend import batch_softmax

        doc_ids = sorted(channel_map.keys())
        X = np.stack([channel_map[did] for did in doc_ids])
        out = batch_softmax(X)
        for i, did in enumerate(doc_ids):
            channel_map[did] = out[i]

    @staticmethod
    def _execute_batchnorm_layer(
        layer: BatchNormLayer,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Per-channel normalize across all nodes (batch)."""
        if len(channel_map) < 2:
            return

        from uqa.operators._backend import batch_batchnorm

        doc_ids = sorted(channel_map.keys())
        stacked = np.stack([channel_map[did] for did in doc_ids])
        normalized = batch_batchnorm(stacked, layer.epsilon)
        for i, did in enumerate(doc_ids):
            channel_map[did] = normalized[i]

    @staticmethod
    def _execute_dropout_layer(
        layer: DropoutLayer,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Inference-mode dropout: scale by (1 - p)."""
        scale = 1.0 - layer.p
        for doc_id, vec in channel_map.items():
            channel_map[doc_id] = vec * scale

    def _execute_attention_layer(
        self,
        layer: AttentionLayer,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Self-attention over all spatial positions (Theorem 8.3)."""
        from uqa.operators._backend import batch_self_attention

        if not channel_map:
            return

        doc_ids = sorted(channel_map.keys())
        X = np.stack([channel_map[did] for did in doc_ids])  # (seq_len, n_ch)
        seq_len, n_ch = X.shape

        # Reshape to (1, seq_len, d_model) for batch_self_attention
        X_3d = X.reshape(1, seq_len, n_ch).astype(np.float32)

        W_q: np.ndarray | None = None
        W_k: np.ndarray | None = None
        W_v: np.ndarray | None = None
        if layer.q_weights is not None and layer.q_shape is not None:
            W_q = np.array(layer.q_weights, dtype=np.float32).reshape(layer.q_shape)
        if layer.k_weights is not None and layer.k_shape is not None:
            W_k = np.array(layer.k_weights, dtype=np.float32).reshape(layer.k_shape)
        if layer.v_weights is not None and layer.v_shape is not None:
            W_v = np.array(layer.v_weights, dtype=np.float32).reshape(layer.v_shape)

        out_3d = batch_self_attention(
            X_3d,
            layer.n_heads,
            W_q,
            W_k,
            W_v,
            self.gating,
        )
        out = out_3d[0]  # (seq_len, n_ch)

        for i, did in enumerate(doc_ids):
            channel_map[did] = out[i].astype(np.float64)

    @staticmethod
    def _execute_embed_layer(
        layer: EmbedLayer,
        channel_map: dict[int, np.ndarray],
    ) -> None:
        """Initialize channel_map from a raw embedding vector.

        Element i of the embedding becomes node (i+1) with a
        single-channel value.  This is the classification input
        counterpart to SignalLayer (retrieval input).
        """
        for i, val in enumerate(layer.embedding):
            channel_map[i + 1] = np.array([val], dtype=np.float64)

    def _execute_grid(
        self,
        channel_map: dict[int, np.ndarray],
        num_channels: int,
        softmax_applied: bool,
        log_odds_conjunction: object,
        context: ExecutionContext,
    ) -> tuple[dict[int, np.ndarray], int, bool]:
        """Grid-accelerated execution: conv+pool via backend, rest as usual."""
        from uqa.operators._backend import batch_self_attention, grid_forward

        assert self._grid_shape is not None
        grid_h, grid_w = self._grid_shape

        # Build processing segments: groups of conv+pool stages separated
        # by attention layers, followed by remaining (flatten, dense, etc.)
        segments: list[tuple[str, object]] = []
        current_conv_pool: list[tuple[np.ndarray, int, str]] = []
        remaining_layers: list[_Layer] = []
        non_embed = [la for la in self.layers if not isinstance(la, EmbedLayer)]
        i = 0
        while i < len(non_embed):
            la = non_embed[i]
            if isinstance(la, ConvLayer):
                pool_size = 2
                pool_method = "max"
                if i + 1 < len(non_embed) and isinstance(non_embed[i + 1], PoolLayer):
                    pl = non_embed[i + 1]
                    assert isinstance(pl, PoolLayer)
                    pool_size = pl.pool_size
                    pool_method = pl.method
                    i += 2
                else:
                    i += 1
                if la.kernel is not None and la.kernel_shape is not None:
                    k = np.array(la.kernel, dtype=np.float32).reshape(la.kernel_shape)
                else:
                    from uqa.operators._backend import hop_weights_to_kernel

                    k = hop_weights_to_kernel(list(la.hop_weights))
                current_conv_pool.append((k, pool_size, pool_method))
            elif isinstance(la, AttentionLayer):
                if current_conv_pool:
                    segments.append(("conv_pool", current_conv_pool))
                    current_conv_pool = []
                segments.append(("attention", la))
                i += 1
            else:
                if current_conv_pool:
                    segments.append(("conv_pool", current_conv_pool))
                    current_conv_pool = []
                remaining_layers.append(la)
                i += 1
        if current_conv_pool:
            segments.append(("conv_pool", current_conv_pool))

        # Process segments sequentially
        embed_layer = self.layers[0]
        assert isinstance(embed_layer, EmbedLayer)
        current_flat = np.array(embed_layer.embedding, dtype=np.float32).reshape(1, -1)
        cur_h, cur_w = grid_h, grid_w

        for seg_type, seg_data in segments:
            if seg_type == "conv_pool":
                stages_list: list[tuple[np.ndarray, int, str]] = seg_data  # type: ignore[assignment]
                current_flat = grid_forward(
                    current_flat,
                    cur_h,
                    cur_w,
                    stages_list,
                    self.gating,
                )
                for _, ps, _ in stages_list:
                    cur_h = cur_h // ps
                    cur_w = cur_w // ps
            elif seg_type == "attention":
                attn_layer = seg_data
                assert isinstance(attn_layer, AttentionLayer)
                n_ch = current_flat.shape[1] // (cur_h * cur_w)
                seq_len = cur_h * cur_w

                X_3d = (
                    current_flat.reshape(1, n_ch, seq_len)
                    .transpose(0, 2, 1)
                    .astype(np.float32)
                )

                W_q: np.ndarray | None = None
                W_k: np.ndarray | None = None
                W_v: np.ndarray | None = None
                if attn_layer.q_weights is not None and attn_layer.q_shape is not None:
                    W_q = np.array(attn_layer.q_weights, dtype=np.float32).reshape(
                        attn_layer.q_shape
                    )
                if attn_layer.k_weights is not None and attn_layer.k_shape is not None:
                    W_k = np.array(attn_layer.k_weights, dtype=np.float32).reshape(
                        attn_layer.k_shape
                    )
                if attn_layer.v_weights is not None and attn_layer.v_shape is not None:
                    W_v = np.array(attn_layer.v_weights, dtype=np.float32).reshape(
                        attn_layer.v_shape
                    )

                out_3d = batch_self_attention(
                    X_3d,
                    attn_layer.n_heads,
                    W_q,
                    W_k,
                    W_v,
                    self.gating,
                )
                current_flat = out_3d.transpose(0, 2, 1).reshape(1, -1)

        # Rebuild channel_map from final features
        channel_map.clear()
        for i in range(current_flat.shape[1]):
            channel_map[i + 1] = np.array([current_flat[0, i]], dtype=np.float64)
        num_channels = 1

        # Process remaining layers (flatten, dense, softmax, etc.)
        for layer in remaining_layers:
            if isinstance(layer, FlattenLayer):
                channel_map, num_channels = self._execute_flatten_layer(channel_map)
            elif isinstance(layer, DenseLayer):
                self._execute_dense_layer(layer, channel_map)
                num_channels = layer.output_channels
            elif isinstance(layer, SoftmaxLayer):
                self._execute_softmax_layer(channel_map)
                softmax_applied = True
            elif isinstance(layer, BatchNormLayer):
                self._execute_batchnorm_layer(layer, channel_map)
            elif isinstance(layer, DropoutLayer):
                self._execute_dropout_layer(layer, channel_map)

        return channel_map, num_channels, softmax_applied

    # -- Cost estimation --

    def cost_estimate(self, stats: IndexStats) -> float:
        total = 0.0
        for layer in self.layers:
            if isinstance(layer, SignalLayer):
                total += sum(sig.cost_estimate(stats) for sig in layer.signals)
            elif isinstance(layer, EmbedLayer):
                total += float(len(layer.embedding))
            elif isinstance(layer, (PropagateLayer, ConvLayer, PoolLayer)):
                total += float(stats.total_docs)
            elif isinstance(layer, DenseLayer):
                total += float(layer.input_channels * layer.output_channels)
            elif isinstance(
                layer, (FlattenLayer, SoftmaxLayer, BatchNormLayer, DropoutLayer)
            ):
                total += float(stats.total_docs)
            elif isinstance(layer, AttentionLayer):
                # O(seq_len^2 * d_model) per position
                total += float(stats.total_docs) ** 2
        return total


def _graph_neighbors(
    gs: object,
    vid: int,
    edge_label: str,
    direction: str,
    graph_name: str,
) -> list[int]:
    """Collect neighbors in the specified direction(s)."""
    result: list[int] = []
    if direction in ("out", "both"):
        result.extend(gs.neighbors(vid, edge_label, "out", graph=graph_name))  # type: ignore[union-attr]
    if direction in ("in", "both"):
        result.extend(gs.neighbors(vid, edge_label, "in", graph=graph_name))  # type: ignore[union-attr]
    return result


def estimate_conv_weights(
    engine: object,
    table_name: str,
    edge_label: str,
    kernel_hops: int,
    embedding_field: str = "embedding",
) -> list[float]:
    """Estimate ConvLayer hop weights from spatial autocorrelation (MLE).

    Computes the average cosine similarity between patch embeddings at
    each hop distance.  High similarity at hop h means spatial coherence
    is strong at that distance, so w_h should be large.

    Returns normalized weights [w_0, w_1, ..., w_{kernel_hops}] that
    sum to 1.0.

    Parameters
    ----------
    engine : Engine
        UQA engine with the table and graph loaded.
    table_name : str
        Name of the table containing patch data.
    edge_label : str
        Edge label for spatial adjacency in the graph.
    kernel_hops : int
        Maximum hop distance (1 = 3x3, 2 = 5x5 receptive field).
    embedding_field : str
        Name of the VECTOR column containing patch embeddings.
    """
    eng = engine  # type: ignore[assignment]
    table = eng._tables.get(table_name)
    if table is None:
        raise ValueError(f"Table '{table_name}' does not exist")

    gs = table.graph_store
    if gs is None:
        raise ValueError(f"Table '{table_name}' has no graph store")

    graph_name = table_name
    doc_store = table.document_store

    # Collect all doc_ids and their embeddings
    embeddings: dict[int, np.ndarray] = {}
    for doc_id in doc_store.doc_ids:
        vec = doc_store.get_field(doc_id, embedding_field)
        if vec is not None:
            if not isinstance(vec, np.ndarray):
                vec = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                embeddings[doc_id] = vec / norm

    if len(embeddings) < 2:
        # Not enough data; return uniform weights
        w = 1.0 / (kernel_hops + 1)
        return [w] * (kernel_hops + 1)

    # For each hop distance, compute average cosine similarity
    hop_similarities: list[list[float]] = [[] for _ in range(kernel_hops + 1)]

    for vid, vec_v in embeddings.items():
        # Hop 0: self-similarity (always 1.0, but we include it for
        # completeness; it represents the self-connection weight)
        hop_similarities[0].append(1.0)

        # BFS to find neighbors at each hop
        current_frontier = {vid}
        visited = {vid}
        for h in range(1, kernel_hops + 1):
            next_frontier: set[int] = set()
            for fv in current_frontier:
                for nb in _graph_neighbors(gs, fv, edge_label, "both", graph_name):
                    if nb not in visited:
                        next_frontier.add(nb)
                        visited.add(nb)

            for nb in next_frontier:
                if nb in embeddings:
                    sim = float(np.dot(vec_v, embeddings[nb]))
                    hop_similarities[h].append(sim)

            current_frontier = next_frontier

    # Compute mean similarity per hop
    raw_weights: list[float] = []
    for h in range(kernel_hops + 1):
        sims = hop_similarities[h]
        if sims:
            mean_sim = sum(sims) / len(sims)
            # Clamp to positive (negative correlation = no useful signal)
            raw_weights.append(max(0.0, mean_sim))
        else:
            raw_weights.append(0.0)

    # Normalize to sum to 1
    total = sum(raw_weights)
    if total <= 0:
        w = 1.0 / (kernel_hops + 1)
        return [w] * (kernel_hops + 1)

    return [w / total for w in raw_weights]
