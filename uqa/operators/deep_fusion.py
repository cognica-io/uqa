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
        layers: list[SignalLayer | PropagateLayer],
        alpha: float = 0.5,
        gating: str = "none",
        graph_name: str = "",
    ) -> None:
        if not layers:
            raise ValueError("deep_fusion requires at least one layer")
        if isinstance(layers[0], PropagateLayer):
            raise ValueError(
                "deep_fusion: first layer must be a SignalLayer "
                "(no scores to propagate)"
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

    def cost_estimate(self, stats: IndexStats) -> float:
        total = 0.0
        for layer in self.layers:
            if isinstance(layer, SignalLayer):
                total += sum(sig.cost_estimate(stats) for sig in layer.signals)
            elif isinstance(layer, PropagateLayer):
                total += float(stats.total_docs)
        return total
