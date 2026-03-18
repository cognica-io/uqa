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

JACCARD_JOIN_SELECTIVITY = 0.05
VECTOR_JOIN_SELECTIVITY = 0.1
GRAPH_AVG_DEGREE_DEFAULT = 10.0


@dataclass
class GraphStats:
    """Graph-level statistics for cardinality estimation (Theorem 6.3.2, Paper 2).

    Collects vertex count, edge count, label distribution, and edge
    density to replace heuristic graph cardinality estimates with
    independence-based formulas.  When ``graph_name`` is set, statistics
    are scoped to that named graph.
    """

    num_vertices: int = 0
    num_edges: int = 0
    label_counts: dict[str, int] = field(default_factory=dict)
    avg_out_degree: float = 0.0
    degree_distribution: dict[int, int] = field(default_factory=dict)
    min_timestamp: float | None = None
    max_timestamp: float | None = None
    graph_name: str = ""
    vertex_label_counts: dict[str, int] = field(default_factory=dict)
    label_degree_map: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_graph_store(cls, graph_store: object, *, graph: str = "") -> GraphStats:
        """Compute statistics from a GraphStore instance.

        When ``graph`` is provided and the store supports named graphs,
        statistics are scoped to that graph partition.
        """
        from uqa.graph.store import GraphStore as GS

        if isinstance(graph_store, GS) and graph:
            return cls._from_named_graph(graph_store, graph)

        # Fallback: global stats
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

    @classmethod
    def _from_named_graph(cls, gs: object, graph: str) -> GraphStats:
        """Compute per-graph statistics using graph-scoped API."""
        store = gs  # type: ignore[assignment]
        vertices = store.vertices_in_graph(graph)
        edges = store.edges_in_graph(graph)
        num_v = len(vertices)
        num_e = len(edges)

        label_counts: dict[str, int] = {}
        for edge in edges:
            label_counts[edge.label] = label_counts.get(edge.label, 0) + 1

        avg_out = num_e / num_v if num_v > 0 else 0.0

        vlc = store.vertex_label_counts(graph)
        ldm: dict[str, float] = {}
        for label in label_counts:
            ldm[label] = store.label_degree(label, graph)
        dd = store.degree_distribution(graph)

        return cls(
            num_vertices=num_v,
            num_edges=num_e,
            label_counts=label_counts,
            avg_out_degree=avg_out,
            degree_distribution=dd,
            graph_name=graph,
            vertex_label_counts=vlc,
            label_degree_map=ldm,
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
        graph_store: object | None = None,
    ) -> None:
        self._column_stats = column_stats or {}
        self._graph_stats = graph_stats
        self._graph_store = graph_store

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
                return n * self._vector_selectivity(op.threshold)
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
                damping = self._intersection_damping(ops)
                result = child_cards[0]
                for card in child_cards[1:]:
                    sel = card / n if n > 0 else 1.0
                    result *= sel**damping

                # Apply entropy-based lower bound (Paper 1, Section 7)
                # when column stats are available
                if self._column_stats:
                    entropies: list[float] = []
                    for op_item in ops:
                        if isinstance(op_item, FilterOperator) and op_item.field:
                            cs = self._column_stats.get(op_item.field)
                            if cs is not None:
                                entropies.append(_column_entropy(cs))
                    if entropies:
                        lb = _entropy_cardinality_lower_bound(n, entropies)
                        result = max(result, lb)

                return max(1.0, result)
            case UnionOperator(operands=ops):
                child_cards = [self.estimate(o, stats) for o in ops]
                return min(n, sum(child_cards))
            case ComplementOperator(operand=inner):
                inner_card = self.estimate(inner, stats)
                return max(0.0, n - inner_card)
            case _:
                return self._estimate_cross_paradigm(op, stats, n)

    def _intersection_damping(self, ops: list[Operator]) -> float:
        """Choose damping exponent based on predicate correlation.

        The exponent controls how aggressively the second predicate
        reduces the estimate: sel**exponent.  Lower exponent means
        less reduction (more correlation), higher exponent means more
        reduction (more independence).

        Uses mutual information when column stats are available to detect
        correlation.  Falls back to field-name heuristic otherwise.
        """
        from uqa.operators.primitive import FilterOperator

        fields: list[str] = []
        for op in ops:
            if isinstance(op, FilterOperator) and op.field is not None:
                fields.append(op.field)

        if len(fields) < 2:
            return 0.5

        if len(set(fields)) == 1:
            return 0.1

        # Use mutual information estimate when stats are available
        if self._column_stats and len(fields) >= 2:
            cs_a = self._column_stats.get(fields[0])
            cs_b = self._column_stats.get(fields[1])
            if cs_a is not None and cs_b is not None:
                mi = _mutual_information_estimate(cs_a, cs_b, 0.1)
                # Higher MI = more correlated = lower damping
                if mi > 1.0:
                    return 0.2
                if mi > 0.5:
                    return 0.3

        return 0.5

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

        # Weighted RPQ: RPQ estimate with selectivity factor for predicate
        from uqa.graph.operators import WeightedPathQueryOperator

        if isinstance(op, WeightedPathQueryOperator):
            rpq_est = self._estimate_rpq(op, n)
            return rpq_est * 0.5  # Selectivity factor for predicate

        if isinstance(op, MessagePassingOperator):
            return n

        if isinstance(op, GraphEmbeddingOperator):
            return n

        # Centrality operators: one score per vertex
        from uqa.graph.centrality import (
            BetweennessCentralityOperator,
            HITSOperator,
            PageRankOperator,
        )

        if isinstance(
            op, (PageRankOperator, HITSOperator, BetweennessCentralityOperator)
        ):
            if self._graph_stats is not None:
                return float(self._graph_stats.num_vertices)
            return n

        # Cross-paradigm join operators
        from uqa.joins.cross_paradigm import (
            CrossParadigmJoinOperator,
            GraphJoinOperator,
            HybridJoinOperator,
            TextSimilarityJoinOperator,
            VectorSimilarityJoinOperator,
        )

        if isinstance(op, TextSimilarityJoinOperator):
            left = self._estimate_join_side(op.left, stats, n)
            right = self._estimate_join_side(op.right, stats, n)
            return left * right * JACCARD_JOIN_SELECTIVITY

        if isinstance(op, VectorSimilarityJoinOperator):
            left = self._estimate_join_side(op.left, stats, n)
            right = self._estimate_join_side(op.right, stats, n)
            return left * right * VECTOR_JOIN_SELECTIVITY

        if isinstance(op, GraphJoinOperator):
            left = self._estimate_join_side(op.left, stats, n)
            avg_degree = (
                self._graph_stats.avg_out_degree
                if self._graph_stats
                else GRAPH_AVG_DEGREE_DEFAULT
            )
            label_sel = (
                self._graph_stats.label_selectivity(op.label)
                if self._graph_stats
                else 1.0
            )
            return left * avg_degree * label_sel

        if isinstance(op, HybridJoinOperator):
            left = self._estimate_join_side(op.left, stats, n)
            right = self._estimate_join_side(op.right, stats, n)
            return left * right / n if n > 0 else 0.0

        if isinstance(op, CrossParadigmJoinOperator):
            left = self._estimate_join_side(op.left, stats, n)
            avg_degree = (
                self._graph_stats.avg_out_degree
                if self._graph_stats
                else GRAPH_AVG_DEGREE_DEFAULT
            )
            label_sel = 1.0  # CrossParadigmJoinOperator doesn't have label attribute
            return left * avg_degree * label_sel

        # Progressive fusion: cardinality = last stage k
        from uqa.operators.progressive_fusion import ProgressiveFusionOperator

        if isinstance(op, ProgressiveFusionOperator):
            _, last_k = op.stages[-1]
            return float(last_k)

        # Deep fusion: union of signal cardinalities, expanded by propagate
        from uqa.operators.deep_fusion import (
            ConvLayer,
            DeepFusionOperator,
            FlattenLayer,
            PoolLayer,
            PropagateLayer,
            SignalLayer,
        )

        if isinstance(op, DeepFusionOperator):
            card = 0.0
            for layer in op.layers:
                if isinstance(layer, SignalLayer):
                    layer_cards = [self.estimate(s, stats) for s in layer.signals]
                    card = max(card, min(n, sum(layer_cards)))
                elif isinstance(layer, PropagateLayer):
                    avg_degree = (
                        self._graph_stats.avg_out_degree
                        if self._graph_stats
                        else GRAPH_AVG_DEGREE_DEFAULT
                    )
                    label_sel = (
                        self._graph_stats.label_selectivity(layer.edge_label)
                        if self._graph_stats
                        else 1.0
                    )
                    card = min(n, card * avg_degree * label_sel)
                elif isinstance(layer, ConvLayer):
                    # ConvLayer does not discover new docs (only
                    # convolves scores of existing docs), so cardinality
                    # stays the same.
                    pass
                elif isinstance(layer, PoolLayer):
                    card = max(1.0, card / layer.pool_size)
                elif isinstance(layer, FlattenLayer):
                    card = 1.0
                # DenseLayer, SoftmaxLayer, BatchNormLayer, DropoutLayer:
                # pass-through (no change in node count)
            return max(1.0, card)

        return n

    def _estimate_traverse(self, op: object, n: float) -> float:
        """Traverse cardinality using graph statistics (Theorem 6.3.2, Paper 2).

        With statistics and label_degree_map: use label-specific degree.
        With statistics without map: branching = avg_out_degree * label_selectivity.
        Without statistics: fallback to heuristic min(n*0.1, 10).
        """
        hops = getattr(op, "max_hops", 1)
        label = getattr(op, "label", None)

        if self._graph_stats is not None:
            gs = self._graph_stats
            # Use label-specific degree from label_degree_map when available
            if label and hasattr(gs, "label_degree_map") and gs.label_degree_map:
                branching = gs.label_degree_map.get(
                    label, gs.avg_out_degree * gs.label_selectivity(label)
                )
            else:
                sel = gs.label_selectivity(label)
                branching = gs.avg_out_degree * sel
        else:
            branching = min(n * 0.1, 10.0)

        result = min(n, branching**hops)

        temporal_filter = getattr(op, "temporal_filter", None)
        if temporal_filter is not None and self._graph_stats is not None:
            result *= self._temporal_selectivity(temporal_filter, self._graph_stats)

        return result

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

            # Use sampling for large graphs (Section 6.3, Paper 2)
            if nv > 10000 and self._graph_store is not None:
                sampled = self._sample_graph_cardinality(pattern)
                if sampled >= 0.0:
                    return max(1.0, sampled)

            density = gs.edge_density()

            label_sel = 1.0
            for ep in pattern.edge_patterns:
                label_sel *= gs.label_selectivity(ep.label)

            # Vertex label selectivity: use vertex_label_counts when available
            vertex_sel = 1.0
            if hasattr(gs, "vertex_label_counts") and gs.vertex_label_counts:
                for vp in pattern.vertex_patterns:
                    # Extract label from constraints if available
                    vp_label = getattr(vp, "label", None)
                    if vp_label and vp_label in gs.vertex_label_counts:
                        vlc = gs.vertex_label_counts[vp_label]
                        vertex_sel *= vlc / nv if nv > 0 else 1.0

            # |V|^k * density^e * label_selectivity * vertex_selectivity
            estimate = (nv**k) * (density**e) * label_sel * vertex_sel
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
            estimate = max(1.0, min(nv, estimate))

            # Apply temporal selectivity if temporal filter available
            temporal_filter = getattr(op, "temporal_filter", None)
            if temporal_filter is not None:
                estimate *= self._temporal_selectivity(temporal_filter, gs)

            return estimate

        estimate = min(n, n**1.5)

        # Apply temporal selectivity if temporal filter available
        temporal_filter = getattr(op, "temporal_filter", None)
        if temporal_filter is not None and self._graph_stats is not None:
            estimate *= self._temporal_selectivity(temporal_filter, self._graph_stats)

        return estimate

    def _estimate_rpq(self, op: object, n: float) -> float:
        """RPQ cardinality using graph statistics (Theorem 6.3.2, Paper 2).

        With statistics: |V|^2 * |R| * density where |R| is NFA state count
        (estimated from expression structure).
        Without statistics: fallback to n^1.5.
        """
        if self._graph_stats is not None:
            gs = self._graph_stats
            nv = float(gs.num_vertices) if gs.num_vertices > 0 else n
            density = gs.edge_density()
            # Estimate |R| (NFA size) from expression structure
            path_expr = getattr(op, "path_expr", None)
            if path_expr is not None:
                from uqa.planner.cost_model import _expr_label_count

                r_size = _expr_label_count(path_expr)
            else:
                r_size = 1
            # O(|V|^2 * |R|) scaled by density
            estimate = (nv**2) * r_size * density
            return max(1.0, min(nv, estimate))

        return min(n, n**1.5)

    @staticmethod
    def _vector_selectivity(threshold: float) -> float:
        """Estimate vector selectivity based on threshold (Paper 1, Section 5.3)."""
        if threshold >= 0.9:
            return 0.01
        if threshold >= 0.7:
            return 0.05
        if threshold >= 0.5:
            return 0.1
        return 0.2

    def _estimate_join_side(self, side: object, stats: IndexStats, n: float) -> float:
        """Estimate cardinality of a join operand, handling untyped objects."""
        from uqa.operators.base import Operator

        if isinstance(side, Operator):
            return self.estimate(side, stats)
        if hasattr(side, "execute"):
            return n
        return n

    def _sample_graph_cardinality(
        self,
        pattern: object,
        sample_size: int = 100,
    ) -> float:
        """Approximate cardinality via random walk sampling (Section 6.3, Paper 2).

        Returns estimated number of pattern matches, or -1.0 if sampling
        is unavailable (no graph_store or empty graph).
        """
        import random

        graph_store = self._graph_store
        if graph_store is None:
            return -1.0

        vertices = getattr(graph_store, "_vertices", {})
        if not vertices:
            return 0.0

        vertex_patterns = getattr(pattern, "vertex_patterns", [])
        edge_patterns = getattr(pattern, "edge_patterns", [])
        k = len(vertex_patterns)
        if k == 0:
            return 0.0

        vertex_ids = list(vertices.keys())
        n = len(vertex_ids)
        successes = 0

        for _ in range(sample_size):
            # Pick random start vertex
            start_vid = random.choice(vertex_ids)
            vertex = vertices.get(start_vid)
            if vertex is None:
                continue

            # Check first variable constraints
            vp0 = vertex_patterns[0]
            if not all(c(vertex) for c in vp0.constraints):
                continue

            # Try to extend assignment via random neighbor walks
            assignment = {vp0.variable: start_vid}
            valid = True

            for vi in range(1, k):
                vp = vertex_patterns[vi]
                # Find edges connecting to already-assigned variables
                neighbor_found = False
                for ep in edge_patterns:
                    src_id = assignment.get(ep.source_var)
                    if src_id is not None and ep.target_var == vp.variable:
                        adj_out = getattr(graph_store, "_adj_out", {})
                        edges_dict = getattr(graph_store, "_edges", {})
                        candidates = []
                        for eid in adj_out.get(src_id, []):
                            edge = edges_dict.get(eid)
                            if edge is None:
                                continue
                            if ep.label is not None and edge.label != ep.label:
                                continue
                            tgt = vertices.get(edge.target_id)
                            if tgt is not None and all(c(tgt) for c in vp.constraints):
                                candidates.append(edge.target_id)
                        if candidates:
                            assignment[vp.variable] = random.choice(candidates)
                            neighbor_found = True
                            break
                if not neighbor_found:
                    valid = False
                    break

            if valid and len(assignment) == k:
                successes += 1

        success_rate = successes / sample_size
        return success_rate * float(n) ** k

    def _temporal_selectivity(self, temporal_filter: object, gs: GraphStats) -> float:
        """Estimate temporal selectivity (Paper 2, Section 8)."""
        if gs.min_timestamp is None or gs.max_timestamp is None:
            return 1.0

        total_range = gs.max_timestamp - gs.min_timestamp
        if total_range <= 0:
            return 1.0

        timestamp = getattr(temporal_filter, "timestamp", None)
        time_range = getattr(temporal_filter, "time_range", None)

        if timestamp is not None:
            return min(1.0, 1.0 / total_range)

        if time_range is not None:
            query_span = time_range[1] - time_range[0]
            return min(1.0, query_span / total_range)

        return 1.0

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

        The final selectivity is clamped by an entropy-based lower bound
        (Paper 1, Section 7): selectivity >= 1 / 2^H(column).
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
        selectivity: float

        if isinstance(predicate, Equals):
            selectivity = self._equality_selectivity(cs, predicate.target, ndv)
        elif isinstance(predicate, NotEquals):
            selectivity = 1.0 - self._equality_selectivity(cs, predicate.target, ndv)
        elif isinstance(predicate, InSet):
            selectivity = min(
                1.0,
                sum(self._equality_selectivity(cs, v, ndv) for v in predicate.values),
            )
        elif isinstance(predicate, Between):
            selectivity = self._range_selectivity(cs, predicate.low, predicate.high)
        elif isinstance(predicate, (GreaterThan, GreaterThanOrEqual)):
            selectivity = self._gt_selectivity(cs, predicate.target)
        elif isinstance(predicate, (LessThan, LessThanOrEqual)):
            selectivity = self._lt_selectivity(cs, predicate.target)
        else:
            selectivity = 0.5

        # Entropy-based lower bound: selectivity >= 1 / 2^H(column)
        if cs.distinct_count > 1:
            h = _column_entropy(cs)
            if h > 0:
                min_sel = 1.0 / (2.0**h)
                selectivity = max(min_sel, selectivity)

        return selectivity

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


# -- Information-Theoretic Bounds (Paper 1, Section 7) --


def _column_entropy(cs: Any) -> float:
    """Estimate column entropy from histogram or distinct count.

    H(X) = -sum(p_i * log2(p_i)) for each distinct value.
    With equi-depth histogram, each bucket has equal probability.
    """
    import math

    if cs is None:
        return 0.0

    ndv = getattr(cs, "distinct_count", 0)
    if ndv <= 1:
        return 0.0

    # If MCV frequencies are available, use them
    mcv_freqs = getattr(cs, "mcv_frequencies", [])
    if mcv_freqs:
        entropy = 0.0
        remaining = 1.0 - sum(mcv_freqs)
        for freq in mcv_freqs:
            if freq > 0:
                entropy -= freq * math.log2(freq)
        # Remaining probability spread uniformly over non-MCV values
        remaining_ndv = max(1, ndv - len(mcv_freqs))
        if remaining > 0 and remaining_ndv > 0:
            p = remaining / remaining_ndv
            entropy -= remaining * math.log2(p)
        return max(0.0, entropy)

    # If histogram buckets are available, use bucket frequencies
    histogram = getattr(cs, "histogram", None)
    if histogram is not None and len(histogram) > 1:
        num_buckets = len(histogram) - 1  # boundaries define buckets
        total_rows = getattr(cs, "row_count", 0)
        if total_rows > 0 and num_buckets > 0:
            # Equi-depth: each bucket has approximately total_rows/num_buckets rows
            p = 1.0 / num_buckets
            entropy = -num_buckets * p * math.log2(p)  # = log2(num_buckets)
            return max(0.0, entropy)

    # Uniform assumption: H = log2(ndv)
    return math.log2(ndv)


def _mutual_information_estimate(
    cs_x: Any, cs_y: Any, joint_selectivity: float
) -> float:
    """Estimate mutual information I(X;Y) = H(X) + H(Y) - H(X,Y).

    Uses column entropies and an estimated joint entropy based on
    joint selectivity (from join cardinality estimation).
    """
    import math

    h_x = _column_entropy(cs_x)
    h_y = _column_entropy(cs_y)

    # Joint entropy lower bound: max(H(X), H(Y))
    # Joint entropy upper bound: H(X) + H(Y) (independence)
    # Estimate using joint selectivity as a correlation proxy
    if joint_selectivity <= 0:
        return 0.0

    ndv_x = max(1, getattr(cs_x, "distinct_count", 1))
    ndv_y = max(1, getattr(cs_y, "distinct_count", 1))

    # Under independence, joint NDV = ndv_x * ndv_y.
    # With correlation, the effective joint NDV is smaller.
    # joint_selectivity is a fraction in [0,1] representing the join
    # selectivity.  Lower selectivity = more correlation = smaller
    # effective joint NDV.
    independent_ndv = ndv_x * ndv_y
    effective_ndv = max(1, independent_ndv * joint_selectivity)

    h_joint = math.log2(max(1, effective_ndv))
    mi = max(0.0, h_x + h_y - h_joint)
    return mi


def _entropy_cardinality_lower_bound(n: float, entropies: list[float]) -> float:
    """Information-theoretic lower bound on join/intersection cardinality.

    From the entropy power inequality, the result cardinality of an
    intersection of k predicates is bounded below by:
        |result| >= n * 2^(-sum(H_i))
    where H_i is the entropy of each predicate's selectivity distribution.
    """
    if not entropies or n <= 0:
        return 1.0
    total_entropy = sum(entropies)
    lb = n * (2.0 ** (-total_entropy))
    return max(1.0, lb)
