#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    """

    def __init__(
        self,
        layers: list[SignalLayer | PropagateLayer | ConvLayer],
        alpha: float = 0.5,
        gating: str = "none",
        graph_name: str = "",
    ) -> None:
        if not layers:
            raise ValueError("deep_fusion requires at least one layer")
        if isinstance(layers[0], (PropagateLayer, ConvLayer)):
            raise ValueError(
                "deep_fusion: first layer must be a SignalLayer "
                "(no scores to propagate or convolve)"
            )
        self.layers = layers
        self.alpha = alpha
        self.gating = gating
        self.graph_name = graph_name

    def execute(self, context: ExecutionContext) -> PostingList:
        from bayesian_bm25 import log_odds_conjunction

        logit_map: dict[int, float] = {}

        for layer in self.layers:
            if isinstance(layer, SignalLayer):
                self._execute_signal_layer(
                    layer, context, logit_map, log_odds_conjunction
                )
            elif isinstance(layer, PropagateLayer):
                self._execute_propagate_layer(layer, context, logit_map)
            elif isinstance(layer, ConvLayer):
                self._execute_conv_layer(layer, context, logit_map)

        if not logit_map:
            return PostingList()

        entries: list[PostingEntry] = []
        for doc_id in sorted(logit_map):
            score = _sigmoid(logit_map[doc_id])
            entries.append(PostingEntry(doc_id, Payload(score=score)))

        return PostingList.from_sorted(entries)

    def _execute_signal_layer(
        self,
        layer: SignalLayer,
        context: ExecutionContext,
        logit_map: dict[int, float],
        log_odds_conjunction: object,
    ) -> None:
        """Execute a signal layer: run signals, fuse within layer, add residual."""
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
                logit_map[doc_id] = logit_map.get(doc_id, 0.0) + layer_logit
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
                logit_map[doc_id] = logit_map.get(doc_id, 0.0) + layer_logit

    def _execute_propagate_layer(
        self,
        layer: PropagateLayer,
        context: ExecutionContext,
        logit_map: dict[int, float],
    ) -> None:
        """Propagate scores through graph edges."""
        gs = context.graph_store
        if gs is None:
            raise ValueError(
                "deep_fusion propagate layer requires a graph_store in ExecutionContext"
            )

        # Convert current logits to probabilities
        prob_map: dict[int, float] = {}
        for doc_id, logit in logit_map.items():
            prob_map[doc_id] = _sigmoid(logit)

        new_logits: dict[int, float] = {}
        direction = layer.direction
        edge_label = layer.edge_label
        aggregation = layer.aggregation
        graph_name = self.graph_name
        gating = self.gating

        # Collect all vertices that could be affected
        all_vertex_ids = set(logit_map.keys())

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
                # No neighbors with scores: keep existing logit (residual)
                if vid in logit_map:
                    new_logits[vid] = logit_map[vid]
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

            # Add to existing logit (residual connection)
            existing = logit_map.get(vid, 0.0)
            new_logits[vid] = existing + propagated_logit

        logit_map.clear()
        logit_map.update(new_logits)

    def _execute_conv_layer(
        self,
        layer: ConvLayer,
        context: ExecutionContext,
        logit_map: dict[int, float],
    ) -> None:
        """Weighted multi-hop convolution over graph neighborhoods."""
        gs = context.graph_store
        if gs is None:
            raise ValueError(
                "deep_fusion convolve layer requires a graph_store in ExecutionContext"
            )

        prob_map: dict[int, float] = {}
        for doc_id, logit in logit_map.items():
            prob_map[doc_id] = _sigmoid(logit)

        # Normalize hop weights
        total_w = sum(layer.hop_weights)
        if total_w <= 0:
            return
        norm_weights = [w / total_w for w in layer.hop_weights]

        new_logits: dict[int, float] = {}
        edge_label = layer.edge_label
        direction = layer.direction
        graph_name = self.graph_name
        gating = self.gating
        kernel_hops = len(layer.hop_weights) - 1

        for vid in list(logit_map.keys()):
            weighted_prob = 0.0

            # Hop 0: self
            if vid in prob_map:
                weighted_prob += norm_weights[0] * prob_map[vid]

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
                    hop_probs = [prob_map[nb] for nb in next_frontier if nb in prob_map]
                    if hop_probs:
                        hop_mean = sum(hop_probs) / len(hop_probs)
                        weighted_prob += norm_weights[h] * hop_mean

                current_frontier = next_frontier

            conv_logit = _safe_logit(max(_PROB_FLOOR, min(_PROB_CEIL, weighted_prob)))
            conv_logit = _apply_gating(conv_logit, gating)

            # Residual connection
            new_logits[vid] = logit_map.get(vid, 0.0) + conv_logit

        logit_map.clear()
        logit_map.update(new_logits)

    def cost_estimate(self, stats: IndexStats) -> float:
        total = 0.0
        for layer in self.layers:
            if isinstance(layer, SignalLayer):
                total += sum(sig.cost_estimate(stats) for sig in layer.signals)
            elif isinstance(layer, PropagateLayer | ConvLayer):
                total += float(stats.total_docs)
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
    import numpy as np

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
