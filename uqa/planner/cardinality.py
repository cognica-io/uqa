#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator
    from uqa.sql.table import ColumnStats


@dataclass
class GraphStats:
    """Graph-level statistics for cardinality estimation (Theorem 6.3.2, Paper 2).

    Collects vertex count, edge count, label distribution, and edge
    density to replace heuristic graph cardinality estimates with
    independence-based formulas.
    """

    num_vertices: int = 0
    num_edges: int = 0
    label_counts: dict[str, int] = field(default_factory=dict)
    avg_out_degree: float = 0.0

    @classmethod
    def from_graph_store(cls, graph_store: object) -> GraphStats:
        """Compute statistics from a GraphStore instance."""
        vertices = getattr(graph_store, "_vertices", {})
        edges = getattr(graph_store, "_edges", {})
        num_v = len(vertices)
        num_e = len(edges)

        label_counts: dict[str, int] = {}
        for edge in edges.values():
            label = edge.label
            label_counts[label] = label_counts.get(label, 0) + 1

        avg_out = num_e / num_v if num_v > 0 else 0.0

        return cls(
            num_vertices=num_v,
            num_edges=num_e,
            label_counts=label_counts,
            avg_out_degree=avg_out,
        )

    def label_selectivity(self, label: str | None) -> float:
        """Fraction of edges matching a given label."""
        if label is None or self.num_edges == 0:
            return 1.0
        return self.label_counts.get(label, 0) / self.num_edges

    def edge_density(self) -> float:
        """Edge density: |E| / |V|^2."""
        if self.num_vertices <= 1:
            return 0.0
        return self.num_edges / (self.num_vertices**2)


class CardinalityEstimator:
    """Cardinality estimation for query optimization (Definition 6.2.3, Paper 1).

    Uses independence assumption for intersections and standard join
    cardinality formulas.  When per-column statistics are available
    (via ``column_stats``), filter selectivity uses 1/ndv instead of
    the default 0.5.

    When ``graph_stats`` are provided, graph operators use statistics-based
    estimation (Theorem 6.3.2, Paper 2) instead of fixed heuristics.
    """

    def __init__(
        self,
        column_stats: dict[str, ColumnStats] | None = None,
        graph_stats: GraphStats | None = None,
    ) -> None:
        self._column_stats = column_stats or {}
        self._graph_stats = graph_stats

    def estimate(self, op: Operator, stats: IndexStats) -> float:
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import (
            FilterOperator,
            KNNOperator,
            ScoreOperator,
            TermOperator,
            VectorSimilarityOperator,
        )

        n = float(stats.total_docs) if stats.total_docs > 0 else 1.0

        match op:
            case TermOperator(term=t, field=f):
                field_name = f or "_default"
                return float(stats.doc_freq(field_name, t))
            case VectorSimilarityOperator():
                return n * 0.1
            case KNNOperator(k=k):
                return float(k)
            case FilterOperator(field=f, predicate=pred):
                return n * self._filter_selectivity(f, pred, n)
            case ScoreOperator(source=src):
                return self.estimate(src, stats)
            case IntersectOperator(operands=ops):
                child_cards = sorted([self.estimate(o, stats) for o in ops])
                if not child_cards:
                    return 0.0
                result = child_cards[0]
                for card in child_cards[1:]:
                    sel = card / n if n > 0 else 1.0
                    result *= sel**0.5  # sqrt damping for correlated predicates
                return max(1.0, result)
            case UnionOperator(operands=ops):
                child_cards = [self.estimate(o, stats) for o in ops]
                return min(n, sum(child_cards))
            case ComplementOperator(operand=inner):
                inner_card = self.estimate(inner, stats)
                return max(0.0, n - inner_card)
            case _:
                return self._estimate_cross_paradigm(op, stats, n)

    def _estimate_cross_paradigm(
        self, op: Operator, stats: IndexStats, n: float
    ) -> float:
        """Cardinality estimation for cross-paradigm operators.

        Handles fusion, hybrid, graph, and other multi-paradigm operators
        that combine signals from different query paradigms.
        """
        from uqa.graph.graph_embedding import GraphEmbeddingOperator
        from uqa.graph.message_passing import MessagePassingOperator
        from uqa.graph.operators import (
            PatternMatchOperator,
            RegularPathQueryOperator,
            TraverseOperator,
            VertexAggregationOperator,
        )
        from uqa.graph.temporal_pattern_match import TemporalPatternMatchOperator
        from uqa.graph.temporal_traverse import TemporalTraverseOperator
        from uqa.operators.attention import AttentionFusionOperator
        from uqa.operators.hybrid import (
            FacetVectorOperator,
            HybridTextVectorOperator,
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
            ProbNotOperator,
            SemanticFilterOperator,
            VectorExclusionOperator,
        )
        from uqa.operators.learned_fusion import LearnedFusionOperator
        from uqa.operators.multi_field import MultiFieldSearchOperator
        from uqa.operators.multi_stage import MultiStageOperator
        from uqa.operators.sparse import SparseThresholdOperator

        if isinstance(op, MultiStageOperator):
            # Final cardinality is determined by the last stage cutoff
            _, last_cutoff = op.stages[-1]
            if isinstance(last_cutoff, int):
                return float(last_cutoff)
            return n * 0.5

        if isinstance(op, AttentionFusionOperator):
            child_cards = [self.estimate(s, stats) for s in op.signals]
            return min(n, sum(child_cards))

        if isinstance(op, LearnedFusionOperator):
            child_cards = [self.estimate(s, stats) for s in op.signals]
            return min(n, sum(child_cards))

        if isinstance(op, MultiFieldSearchOperator):
            return min(n, n * 0.3 * len(op.fields))

        if isinstance(op, SparseThresholdOperator):
            return self.estimate(op.source, stats) * 0.5

        # VectorExclusion: positive minus negative overlap
        if isinstance(op, VectorExclusionOperator):
            pos_card = self.estimate(op.positive, stats)
            neg_card = self.estimate(op.negative_op, stats)
            overlap = (pos_card * neg_card) / n if n > 0 else 0.0
            return max(1.0, pos_card - overlap)

        # FacetVector: bounded by vector result size
        if isinstance(op, FacetVectorOperator):
            return self.estimate(op.vector_op, stats)

        # VertexAggregation: single result row
        if isinstance(op, VertexAggregationOperator):
            return 1.0

        # Fusion: union of all signal doc sets
        if isinstance(op, LogOddsFusionOperator):
            child_cards = [self.estimate(s, stats) for s in op.signals]
            return min(n, sum(child_cards))

        # Probabilistic AND -> product selectivity; OR -> union
        if isinstance(op, ProbBoolFusionOperator):
            child_cards = [self.estimate(s, stats) for s in op.signals]
            if op.mode == "and":
                result = child_cards[0] if child_cards else 0.0
                for card in child_cards[1:]:
                    result = (result * card) / n
                return max(1.0, result)
            return min(n, sum(child_cards))

        # Probabilistic NOT -> complement
        if isinstance(op, ProbNotOperator):
            inner_card = self.estimate(op.signal, stats)
            return max(0.0, n - inner_card)

        # Hybrid text+vector -> intersection of text and vector
        if isinstance(op, HybridTextVectorOperator):
            text_card = self.estimate(op.term_op, stats)
            vec_card = self.estimate(op.vector_op, stats)
            return max(1.0, (text_card * vec_card) / n)

        # SemanticFilter -> intersection of source and vector
        if isinstance(op, SemanticFilterOperator):
            src_card = self.estimate(op.source, stats)
            vec_card = self.estimate(op.vector_op, stats)
            return max(1.0, (src_card * vec_card) / n)

        # Temporal graph traversal: reuses traverse estimation
        if isinstance(op, TemporalTraverseOperator):
            return self._estimate_traverse(op, n)

        # Temporal pattern matching: reuses pattern match estimation
        if isinstance(op, TemporalPatternMatchOperator):
            return self._estimate_temporal_pattern_match(op, n)

        # Graph traversal: statistics-based when available
        if isinstance(op, TraverseOperator):
            return self._estimate_traverse(op, n)

        # Pattern matching: statistics-based when available
        if isinstance(op, PatternMatchOperator):
            return self._estimate_pattern_match(op, n)

        # RPQ: statistics-based when available
        if isinstance(op, RegularPathQueryOperator):
            return self._estimate_rpq(op, n)

        if isinstance(op, MessagePassingOperator):
            return n

        if isinstance(op, GraphEmbeddingOperator):
            return n

        return n

    def _estimate_traverse(self, op: object, n: float) -> float:
        """Traverse cardinality using graph statistics (Theorem 6.3.2, Paper 2).

        With statistics: branching = avg_out_degree * label_selectivity.
        Without statistics: fallback to heuristic min(n*0.1, 10).
        """
        hops = getattr(op, "max_hops", 1)
        label = getattr(op, "label", None)

        if self._graph_stats is not None:
            gs = self._graph_stats
            sel = gs.label_selectivity(label)
            branching = gs.avg_out_degree * sel
        else:
            branching = min(n * 0.1, 10.0)

        return min(n, branching**hops)

    def _estimate_pattern_match(self, op: object, n: float) -> float:
        """Pattern match cardinality using graph statistics (Theorem 6.3.2, Paper 2).

        With statistics: |V|^k * density^e * prod(label_selectivity)
        where k = vertex count, e = edge count in pattern.
        Without statistics: fallback to n^1.5.
        """
        from uqa.graph.operators import PatternMatchOperator

        if not isinstance(op, PatternMatchOperator):
            return min(n, n**1.5)

        pattern = op.pattern
        k = len(pattern.vertex_patterns)
        e = len(pattern.edge_patterns)

        if self._graph_stats is not None:
            gs = self._graph_stats
            nv = float(gs.num_vertices) if gs.num_vertices > 0 else n
            density = gs.edge_density()

            label_sel = 1.0
            for ep in pattern.edge_patterns:
                label_sel *= gs.label_selectivity(ep.label)

            # |V|^k * density^e * label_selectivity
            estimate = (nv**k) * (density**e) * label_sel
            return max(1.0, min(nv, estimate))

        # Heuristic fallback: n^1.5 captures the super-linear growth of
        # pattern match results (more than linear scan but less than the
        # full n^k cross-product) when no graph statistics are available.
        return min(n, n**1.5)

    def _estimate_temporal_pattern_match(self, op: object, n: float) -> float:
        """Temporal pattern match cardinality estimation.

        Uses the same formula as _estimate_pattern_match but works with
        TemporalPatternMatchOperator which has the same pattern attribute.
        """
        from uqa.graph.temporal_pattern_match import TemporalPatternMatchOperator

        if not isinstance(op, TemporalPatternMatchOperator):
            return min(n, n**1.5)

        pattern = op.pattern
        k = len(pattern.vertex_patterns)
        e = len(pattern.edge_patterns)

        if self._graph_stats is not None:
            gs = self._graph_stats
            nv = float(gs.num_vertices) if gs.num_vertices > 0 else n
            density = gs.edge_density()

            label_sel = 1.0
            for ep in pattern.edge_patterns:
                label_sel *= gs.label_selectivity(ep.label)

            estimate = (nv**k) * (density**e) * label_sel
            return max(1.0, min(nv, estimate))

        return min(n, n**1.5)

    def _estimate_rpq(self, op: object, n: float) -> float:
        """RPQ cardinality using graph statistics (Theorem 6.3.2, Paper 2).

        With statistics: |V|^2 * density * label_selectivity.
        Without statistics: fallback to n^1.5.
        """
        if self._graph_stats is not None:
            gs = self._graph_stats
            nv = float(gs.num_vertices) if gs.num_vertices > 0 else n
            density = gs.edge_density()
            # RPQ can reach any (start, end) pair; estimate fraction
            estimate = (nv**2) * density
            return max(1.0, min(nv, estimate))

        # Heuristic fallback: n^1.5 approximates RPQ result size when no
        # graph stats are available.  RPQs can reach any (start, end) pair
        # so result size is between n (single hop) and n^2 (all pairs).
        return min(n, n**1.5)

    def estimate_join(
        self,
        left_card: float,
        right_card: float,
        domain_size: float,
    ) -> float:
        """Join cardinality: |L1| * |L2| / |dom(f)| (Definition 6.2.3)."""
        if domain_size <= 0:
            return 0.0
        return (left_card * right_card) / domain_size

    def _filter_selectivity(self, field: str, predicate: Any, n: float) -> float:
        """Estimate filter selectivity using column statistics.

        Uses a hierarchy of estimation methods:
          1. MCV lookup for equality on frequent values
          2. Histogram-based estimation for range predicates
          3. Uniform assumption with min/max as fallback
          4. Default 0.5 when no stats available
        """
        from uqa.core.types import (
            Between,
            Equals,
            GreaterThan,
            GreaterThanOrEqual,
            InSet,
            LessThan,
            LessThanOrEqual,
            NotEquals,
        )

        cs = self._column_stats.get(field)
        if cs is None or cs.distinct_count <= 0:
            return 0.5

        ndv = cs.distinct_count

        if isinstance(predicate, Equals):
            return self._equality_selectivity(cs, predicate.target, ndv)

        if isinstance(predicate, NotEquals):
            return 1.0 - self._equality_selectivity(cs, predicate.target, ndv)

        if isinstance(predicate, InSet):
            sel = sum(self._equality_selectivity(cs, v, ndv) for v in predicate.values)
            return min(1.0, sel)

        if isinstance(predicate, Between):
            return self._range_selectivity(cs, predicate.low, predicate.high)

        if isinstance(predicate, (GreaterThan, GreaterThanOrEqual)):
            return self._gt_selectivity(cs, predicate.target)

        if isinstance(predicate, (LessThan, LessThanOrEqual)):
            return self._lt_selectivity(cs, predicate.target)

        return 0.5

    @staticmethod
    def _equality_selectivity(cs: ColumnStats, target: Any, ndv: int) -> float:
        """Estimate selectivity for equality predicate.

        Checks MCV list first for exact frequency, otherwise uses
        1/NDV uniform assumption.
        """
        if cs.mcv_values:
            for i, val in enumerate(cs.mcv_values):
                if val == target:
                    return cs.mcv_frequencies[i]
        return 1.0 / ndv if ndv > 0 else 1.0

    @staticmethod
    def _histogram_fraction(boundaries: list[Any], low: Any, high: Any) -> float:
        """Estimate fraction of values in [low, high] using histogram.

        Counts the fraction of histogram buckets that overlap [low, high].
        """
        if len(boundaries) < 2:
            return 0.5

        n_buckets = len(boundaries) - 1
        overlapping = 0.0
        for i in range(n_buckets):
            b_low = boundaries[i]
            b_high = boundaries[i + 1]
            try:
                if high < b_low or low > b_high:
                    continue
                if low <= b_low and high >= b_high:
                    overlapping += 1.0
                else:
                    b_span = float(b_high) - float(b_low)
                    if b_span <= 0:
                        # Zero-width bucket: the point [low, high] fully
                        # overlaps if it touches the bucket boundary, so
                        # count it as 1.0 (100% overlap).
                        overlapping += 1.0
                        continue
                    clamp_low = max(float(low), float(b_low))
                    clamp_high = min(float(high), float(b_high))
                    overlapping += (clamp_high - clamp_low) / b_span
            except (TypeError, ValueError):
                overlapping += 1.0

        return max(0.0, min(1.0, overlapping / n_buckets))

    def _range_selectivity(self, cs: ColumnStats, low: Any, high: Any) -> float:
        """Estimate selectivity for BETWEEN predicate."""
        if cs.histogram:
            return self._histogram_fraction(cs.histogram, low, high)
        if cs.min_value is not None and cs.max_value is not None:
            try:
                span = float(cs.max_value) - float(cs.min_value)
                if span > 0:
                    return max(
                        0.0,
                        min(
                            1.0,
                            (float(high) - float(low)) / span,
                        ),
                    )
            except (TypeError, ValueError):
                pass
        return 0.25

    def _gt_selectivity(self, cs: ColumnStats, target: Any) -> float:
        """Estimate selectivity for > or >= predicate."""
        if cs.histogram:
            return self._histogram_fraction(cs.histogram, target, cs.histogram[-1])
        if cs.min_value is not None and cs.max_value is not None:
            try:
                span = float(cs.max_value) - float(cs.min_value)
                if span > 0:
                    return max(
                        0.0,
                        (float(cs.max_value) - float(target)) / span,
                    )
            except (TypeError, ValueError):
                pass
        return 1.0 / 3.0

    def _lt_selectivity(self, cs: ColumnStats, target: Any) -> float:
        """Estimate selectivity for < or <= predicate."""
        if cs.histogram:
            return self._histogram_fraction(cs.histogram, cs.histogram[0], target)
        if cs.min_value is not None and cs.max_value is not None:
            try:
                span = float(cs.max_value) - float(cs.min_value)
                if span > 0:
                    return max(
                        0.0,
                        (float(target) - float(cs.min_value)) / span,
                    )
            except (TypeError, ValueError):
                pass
        return 1.0 / 3.0
