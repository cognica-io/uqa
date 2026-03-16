#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from uqa.planner.cardinality import CardinalityEstimator, GraphStats
from uqa.planner.cost_model import CostModel

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator
    from uqa.storage.index_manager import IndexManager


class QueryOptimizer:
    """Query optimizer with equivalence-preserving rewrite rules (Theorem 6.1.2, Paper 1).

    Rewrite rules:
    - Algebraic simplification (idempotent, absorption, empty elimination)
    - Filter pushdown into intersections
    - Vector threshold merge (same query vector)
    - Intersect operand reordering by cardinality (cheapest first)
    - Fusion signal reordering by cost (cheapest first)
    - Index scan substitution (replace full scans with index scans)
    """

    def __init__(
        self,
        stats: IndexStats,
        column_stats: dict | None = None,
        index_manager: IndexManager | None = None,
        table_name: str | None = None,
        graph_stats: GraphStats | None = None,
    ):
        self.stats = stats
        self.estimator = CardinalityEstimator(column_stats, graph_stats=graph_stats)
        self._cost_model = CostModel(graph_stats=graph_stats)
        self._graph_stats = graph_stats
        self._index_manager = index_manager
        self._table_name = table_name

    def optimize(self, op: Operator) -> Operator:
        op = self._simplify_algebra(op)
        op = self._push_filters_down(op)
        op = self._push_graph_pattern_filters(op)
        op = self._push_filter_into_traverse(op)
        op = self._push_filter_below_graph_join(op)
        op = self._fuse_join_pattern(op)
        op = self._merge_vector_thresholds(op)
        op = self._reorder_intersect(op)
        op = self._reorder_fusion_signals(op)
        op = self._apply_index_scan(op)
        return op

    def _simplify_algebra(self, op: Operator) -> Operator:
        """Apply algebraic simplification rules (Theorem 6.1.2, Paper 1).

        Rules applied bottom-up:
        1. Idempotent intersection: remove duplicate operands (by identity).
        2. Idempotent union: remove duplicate operands (by identity).
        3. Absorption: A union (A intersect B) => A;
                        A intersect (A union B) => A.
        4. Empty elimination: A intersect empty => empty;
                              A union empty => A.

        An operator is considered "empty" if it is an IntersectOperator or
        UnionOperator with an empty operands list.
        """
        from uqa.operators.boolean import IntersectOperator, UnionOperator

        # Recurse into children first (bottom-up simplification).
        op = self._recurse_simplify(op)

        if isinstance(op, IntersectOperator):
            operands = op.operands

            # Empty elimination: if any operand is empty, the whole
            # intersection is empty.
            for child in operands:
                if self._is_empty_operator(child):
                    return IntersectOperator([])

            # Idempotent: remove duplicates by identity.
            seen: list[Operator] = []
            for child in operands:
                if not any(child is s for s in seen):
                    seen.append(child)
            operands = seen

            # Absorption: if an operand A appears and also a
            # UnionOperator([A, ...]) appears, drop the union operand.
            absorbed: list[Operator] = []
            for child in operands:
                if isinstance(child, UnionOperator) and any(
                    any(other is uc for uc in child.operands)
                    for other in operands
                    if other is not child
                ):
                    continue
                absorbed.append(child)
            operands = absorbed

            if len(operands) == 1:
                return operands[0]
            return IntersectOperator(operands)

        if isinstance(op, UnionOperator):
            operands = op.operands

            # Empty elimination: drop empty children.
            operands = [
                child for child in operands if not self._is_empty_operator(child)
            ]

            # Idempotent: remove duplicates by identity.
            seen = []
            for child in operands:
                if not any(child is s for s in seen):
                    seen.append(child)
            operands = seen

            # Absorption: if an operand A appears and also an
            # IntersectOperator([A, ...]) appears, drop the intersect operand.
            absorbed = []
            for child in operands:
                if isinstance(child, IntersectOperator) and any(
                    any(other is ic for ic in child.operands)
                    for other in operands
                    if other is not child
                ):
                    continue
                absorbed.append(child)
            operands = absorbed

            if len(operands) == 1:
                return operands[0]
            if not operands:
                return UnionOperator([])
            return UnionOperator(operands)

        return op

    def _recurse_simplify(self, op: Operator) -> Operator:
        """Recurse into children for algebraic simplification."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator([self._simplify_algebra(o) for o in op.operands])
        if isinstance(op, UnionOperator):
            return UnionOperator([self._simplify_algebra(o) for o in op.operands])
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._simplify_algebra(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._simplify_algebra(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator([self._simplify_algebra(o) for o in op.operators])
        return op

    @staticmethod
    def _is_empty_operator(op: Operator) -> bool:
        """Check if an operator is structurally empty.

        An IntersectOperator or UnionOperator with no operands always
        produces an empty PostingList regardless of context.
        """
        from uqa.operators.boolean import IntersectOperator, UnionOperator

        if isinstance(op, (IntersectOperator, UnionOperator)):
            return len(op.operands) == 0
        return False

    def _push_filters_down(self, op: Operator) -> Operator:
        """Push FilterOperator through IntersectOperator when possible."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator

        if not isinstance(op, FilterOperator):
            return self._recurse_children(op)

        source = op.source
        if isinstance(source, IntersectOperator):
            new_operands = []
            any_pushed = False
            for child in source.operands:
                if self._filter_applies_to(op, child):
                    new_operands.append(FilterOperator(op.field, op.predicate, child))
                    any_pushed = True
                else:
                    new_operands.append(child)
            if any_pushed:
                recursed = [self._push_filters_down(o) for o in new_operands]
                return self._recurse_children(IntersectOperator(recursed))

        if source is None:
            return op
        return FilterOperator(
            op.field,
            op.predicate,
            self._recurse_children(source),
        )

    def _push_filter_into_traverse(self, op: Operator) -> Operator:
        """Push vertex property filters into TraverseOperator as BFS pruning.

        When a FilterOperator on a vertex property sits above a
        TraverseOperator, the filter predicate is absorbed into the
        traverse's vertex_predicate so vertices failing the predicate
        are pruned during BFS rather than post-filtered.
        """
        from uqa.graph.operators import TraverseOperator
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, FilterOperator) and op.source is not None:
            inner = op.source
            if isinstance(inner, TraverseOperator):
                field = op.field
                predicate = op.predicate

                def vertex_filter(
                    v: object, f: str = field, p: object = predicate
                ) -> bool:
                    props = getattr(v, "properties", {})
                    val = props.get(f)
                    if val is None:
                        return False
                    return p.evaluate(val)  # type: ignore[union-attr]

                # Combine with existing vertex_predicate if any
                existing = inner.vertex_predicate
                if existing is not None:
                    prev = existing

                    def combined(v: object) -> bool:
                        return prev(v) and vertex_filter(v)  # type: ignore[operator]

                    new_pred = combined
                else:
                    new_pred = vertex_filter

                return cast(
                    "Operator",
                    TraverseOperator(
                        inner.start_vertex,
                        graph=inner.graph_name,
                        label=inner.label,
                        max_hops=inner.max_hops,
                        vertex_predicate=new_pred,
                    ),
                )

        return self._recurse_traverse_filter(op)

    def _recurse_traverse_filter(self, op: Operator) -> Operator:
        """Recurse into composite operators for traverse filter pushdown."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator(
                [self._push_filter_into_traverse(o) for o in op.operands]
            )
        if isinstance(op, UnionOperator):
            return UnionOperator(
                [self._push_filter_into_traverse(o) for o in op.operands]
            )
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._push_filter_into_traverse(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._push_filter_into_traverse(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator(
                [self._push_filter_into_traverse(o) for o in op.operators]
            )
        return op

    def _push_graph_pattern_filters(self, op: Operator) -> Operator:
        """Push filter predicates into graph pattern matching constraints.

        Theorem 6.1.1, Paper 2: When a FilterOperator on a vertex property
        sits above a PatternMatchOperator, the filter predicate is pushed
        into the vertex pattern constraints so vertices are pruned during
        matching rather than post-filtered.
        """
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, FilterOperator) and op.source is not None:
            inner = op.source
            # Check if inner is wrapped in an operator that delegates to PatternMatch
            if isinstance(inner, PatternMatchOperator):
                pattern = inner.pattern
                field = op.field
                predicate = op.predicate

                # Parse field: "b.name" -> variable="b", prop="name"
                # Only push if we can identify the target vertex.
                parts = field.split(".", 1)
                if len(parts) != 2:
                    # Unqualified field: cannot determine target vertex;
                    # keep as post-filter.
                    return FilterOperator(field, predicate, inner)

                target_var, prop = parts

                new_vertex_patterns = []
                pushed = False
                for vp in pattern.vertex_patterns:
                    if not pushed and vp.variable == target_var:

                        def new_constraint(v, f=prop, p=predicate):
                            return f in v.properties and p.evaluate(v.properties[f])

                        new_vp = VertexPattern(
                            vp.variable,
                            [*vp.constraints, new_constraint],
                        )
                        new_vertex_patterns.append(new_vp)
                        pushed = True
                    else:
                        new_vertex_patterns.append(vp)

                if pushed:
                    new_pattern = GraphPattern(
                        new_vertex_patterns, pattern.edge_patterns
                    )
                    return cast(
                        "Operator",
                        PatternMatchOperator(new_pattern, graph=inner.graph_name),
                    )

                # Edge pushdown: field like "a_b.since" matches edge (a -> b)
                if not pushed:
                    # Try edge variable: "src_tgt.prop"
                    edge_var_map = {
                        f"{ep.source_var}_{ep.target_var}": ep
                        for ep in pattern.edge_patterns
                    }
                    dot_parts = field.split(".", 1)
                    if len(dot_parts) == 2:
                        edge_key, prop = dot_parts
                        ep = edge_var_map.get(edge_key)
                        if ep is not None:

                            def edge_constraint(e, f=prop, p=predicate):
                                return f in e.properties and p.evaluate(e.properties[f])

                            new_edge_patterns = []
                            for orig_ep in pattern.edge_patterns:
                                if (
                                    orig_ep.source_var == ep.source_var
                                    and orig_ep.target_var == ep.target_var
                                    and orig_ep.label == ep.label
                                ):
                                    new_ep = EdgePattern(
                                        orig_ep.source_var,
                                        orig_ep.target_var,
                                        orig_ep.label,
                                        [*orig_ep.constraints, edge_constraint],
                                    )
                                    new_edge_patterns.append(new_ep)
                                    pushed = True
                                else:
                                    new_edge_patterns.append(orig_ep)

                            if pushed:
                                new_pattern = GraphPattern(
                                    pattern.vertex_patterns, new_edge_patterns
                                )
                                return cast(
                                    "Operator",
                                    PatternMatchOperator(
                                        new_pattern, graph=inner.graph_name
                                    ),
                                )

        # Recurse into children
        return self._recurse_graph_pattern(op)

    def _recurse_graph_pattern(self, op: Operator) -> Operator:
        """Recurse into composite operators for graph pattern pushdown."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator(
                [self._push_graph_pattern_filters(o) for o in op.operands]
            )
        if isinstance(op, UnionOperator):
            return UnionOperator(
                [self._push_graph_pattern_filters(o) for o in op.operands]
            )
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._push_graph_pattern_filters(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._push_graph_pattern_filters(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator(
                [self._push_graph_pattern_filters(o) for o in op.operators]
            )
        return op

    def _push_filter_below_graph_join(self, op: Operator) -> Operator:
        """Push filters below graph join operators to reduce join input size.

        When FilterOperator(field, pred, GraphJoinOperator(left, right, ...)):
        - Push the filter to the left (graph) side of the join, reducing the
          number of rows entering the join.
        - If the source is not a GraphJoinOperator, recurse into children.
        """
        from uqa.joins.cross_paradigm import GraphJoinOperator
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, FilterOperator) and op.source is not None:
            source = op.source
            if isinstance(source, GraphJoinOperator):
                # Push filter below the join -- apply to left operand
                new_left = FilterOperator(
                    op.field, op.predicate, cast("Operator", source.left)
                )
                new_join = GraphJoinOperator(
                    new_left,
                    source.right,
                    source.label,
                    graph=source.graph_name,
                )
                return cast("Operator", new_join)
            return FilterOperator(
                op.field,
                op.predicate,
                self._push_filter_below_graph_join(op.source),
            )

        return self._recurse_graph_join(op)

    def _recurse_graph_join(self, op: Operator) -> Operator:
        """Recurse into composite operators for graph join filter pushdown."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator(
                [self._push_filter_below_graph_join(o) for o in op.operands]
            )
        if isinstance(op, UnionOperator):
            return UnionOperator(
                [self._push_filter_below_graph_join(o) for o in op.operands]
            )
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._push_filter_below_graph_join(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._push_filter_below_graph_join(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator(
                [self._push_filter_below_graph_join(o) for o in op.operators]
            )
        return op

    def _fuse_join_pattern(self, op: Operator) -> Operator:
        """Fuse intersected pattern matches into a single pattern.

        Theorem 6.1.2, Paper 2: When IntersectOperator has 2+ PatternMatchOperator
        children sharing vertex variables, merge into single PatternMatchOperator
        to eliminate intermediate materialization.
        """
        from uqa.graph.operators import PatternMatchOperator
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            # Recursively optimize children first
            children = [self._fuse_join_pattern(o) for o in op.operands]

            # Separate PatternMatchOperators from others
            pattern_ops: list[PatternMatchOperator] = []
            other_ops: list[Operator] = []
            for child in children:
                if isinstance(child, PatternMatchOperator):
                    pattern_ops.append(child)
                else:
                    other_ops.append(child)

            # Try pairwise merging of pattern ops
            if len(pattern_ops) >= 2:
                merged = [pattern_ops[0]]
                for pm in pattern_ops[1:]:
                    fused = self._merge_patterns(merged[-1], pm)
                    if fused is not None:
                        merged[-1] = fused
                    else:
                        merged.append(pm)
                pattern_ops = merged

            all_ops: list[Operator] = other_ops + [
                cast("Operator", p) for p in pattern_ops
            ]
            if len(all_ops) == 1:
                return all_ops[0]
            return IntersectOperator(all_ops)

        # Recurse into other operator types
        if isinstance(op, UnionOperator):
            return UnionOperator([self._fuse_join_pattern(o) for o in op.operands])
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._fuse_join_pattern(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._fuse_join_pattern(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator([self._fuse_join_pattern(o) for o in op.operators])
        return op

    @staticmethod
    def _merge_patterns(pm1: object, pm2: object) -> Any:
        """Merge two PatternMatchOperators if they share vertex variables.

        Returns merged PatternMatchOperator or None if no shared variables.
        """
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import GraphPattern, VertexPattern

        if not isinstance(pm1, PatternMatchOperator) or not isinstance(
            pm2, PatternMatchOperator
        ):
            return None

        p1 = pm1.pattern
        p2 = pm2.pattern

        vars1 = {vp.variable for vp in p1.vertex_patterns}
        vars2 = {vp.variable for vp in p2.vertex_patterns}

        shared = vars1 & vars2
        if not shared:
            return None

        # Merge vertex patterns: deduplicate by variable, combine constraints
        merged_vps: dict[str, VertexPattern] = {}
        for vp in p1.vertex_patterns:
            merged_vps[vp.variable] = vp
        for vp in p2.vertex_patterns:
            if vp.variable in merged_vps:
                existing = merged_vps[vp.variable]
                merged_vps[vp.variable] = VertexPattern(
                    vp.variable,
                    [*existing.constraints, *vp.constraints],
                )
            else:
                merged_vps[vp.variable] = vp

        # Concatenate edge patterns
        merged_edges = list(p1.edge_patterns) + list(p2.edge_patterns)

        merged_pattern = GraphPattern(
            list(merged_vps.values()),
            merged_edges,
        )
        return PatternMatchOperator(merged_pattern, graph=pm1.graph_name)

    def _merge_vector_thresholds(self, op: Operator) -> Operator:
        """Merge V_theta1(q) AND V_theta2(q) into V_max(theta1,theta2)(q)."""
        import numpy as np

        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import VectorSimilarityOperator

        if not isinstance(op, IntersectOperator):
            return self._recurse_children(op)

        vector_ops: list[VectorSimilarityOperator] = []
        other_ops: list[Operator] = []

        for child in op.operands:
            child = self._recurse_children(child)
            if isinstance(child, VectorSimilarityOperator):
                vector_ops.append(child)
            else:
                other_ops.append(child)

        merged_vectors: list[VectorSimilarityOperator] = []
        used = [False] * len(vector_ops)

        for i in range(len(vector_ops)):
            if used[i]:
                continue
            merged = vector_ops[i]
            for j in range(i + 1, len(vector_ops)):
                if used[j]:
                    continue
                if merged.field == vector_ops[j].field and np.allclose(
                    merged.query_vector,
                    vector_ops[j].query_vector,
                    rtol=1e-7,
                    atol=1e-9,
                ):
                    merged = VectorSimilarityOperator(
                        merged.query_vector,
                        max(merged.threshold, vector_ops[j].threshold),
                        merged.field,
                    )
                    used[j] = True
            used[i] = True
            merged_vectors.append(merged)

        all_ops = other_ops + merged_vectors
        if len(all_ops) == 1:
            return all_ops[0]
        return IntersectOperator(all_ops)

    def _reorder_intersect(self, op: Operator) -> Operator:
        """Reorder intersect operands by estimated cardinality (cheapest first)."""
        from uqa.operators.boolean import IntersectOperator

        if not isinstance(op, IntersectOperator):
            return self._recurse_children(op)

        children = [self._recurse_children(c) for c in op.operands]
        children.sort(key=lambda c: self._cost_model.estimate(c, self.stats))
        return IntersectOperator(children)

    def _reorder_fusion_signals(self, op: Operator) -> Operator:
        """Reorder fusion signal inputs by ascending cost estimate.

        For LogOddsFusionOperator and ProbBoolFusionOperator, evaluating
        cheaper signals first enables earlier threshold checks and reduces
        wasted computation on expensive signals whose contribution cannot
        change the final ranking.

        When graph_stats are available, graph operators (TraverseOperator,
        PatternMatchOperator, RegularPathQueryOperator) receive a cost
        discount factor of 0.5 because graph indexes make them cheaper
        than their raw cardinality estimate suggests.
        """
        from uqa.operators.hybrid import (
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
        )

        if isinstance(op, LogOddsFusionOperator):
            signals = [self._reorder_fusion_signals(s) for s in op.signals]
            signals.sort(key=self._graph_aware_signal_cost)
            return LogOddsFusionOperator(signals, alpha=op.alpha, gating=op.gating)

        if isinstance(op, ProbBoolFusionOperator):
            signals = [self._reorder_fusion_signals(s) for s in op.signals]
            signals.sort(key=self._graph_aware_signal_cost)
            return ProbBoolFusionOperator(signals, mode=op.mode)

        return self._recurse_fusion(op)

    def _graph_aware_signal_cost(self, signal: Operator) -> float:
        """Estimate signal cost with graph-aware discount.

        When graph_stats are available, graph operators benefit from
        indexed lookups and are assigned a lower effective cost (0.5x)
        to prefer evaluating them before text/vector operators.
        """
        from uqa.graph.operators import (
            PatternMatchOperator,
            RegularPathQueryOperator,
            TraverseOperator,
        )

        base = self.estimator.estimate(signal, self.stats)
        if self._graph_stats is not None and isinstance(
            signal, (TraverseOperator, PatternMatchOperator, RegularPathQueryOperator)
        ):
            base *= 0.5
        return base

    def _recurse_fusion(self, op: Operator) -> Operator:
        """Recurse into composite operators for fusion signal reordering."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.primitive import FilterOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator(
                [self._reorder_fusion_signals(o) for o in op.operands]
            )
        if isinstance(op, UnionOperator):
            return UnionOperator([self._reorder_fusion_signals(o) for o in op.operands])
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._reorder_fusion_signals(op.operand))
        if isinstance(op, FilterOperator) and op.source is not None:
            return FilterOperator(
                op.field,
                op.predicate,
                self._reorder_fusion_signals(op.source),
            )
        if isinstance(op, ComposedOperator):
            return ComposedOperator(
                [self._reorder_fusion_signals(o) for o in op.operators]
            )
        return op

    def _apply_index_scan(self, op: Operator) -> Operator:
        """Replace full-scan FilterOperators with IndexScanOperators when profitable."""
        from uqa.operators.primitive import FilterOperator, IndexScanOperator

        if self._index_manager is None or self._table_name is None:
            return op

        if isinstance(op, FilterOperator) and op.source is None:
            idx = self._index_manager.find_covering_index(
                self._table_name, op.field, op.predicate
            )
            if idx is not None:
                scan_cost = idx.scan_cost(op.predicate)
                full_scan_cost = float(self.stats.total_docs)
                if scan_cost < full_scan_cost:
                    return IndexScanOperator(idx, op.field, op.predicate)

        if isinstance(op, FilterOperator) and op.source is not None:
            op = FilterOperator(
                op.field,
                op.predicate,
                self._apply_index_scan(op.source),
            )
            return op

        return self._recurse_index_scan(op)

    def _recurse_index_scan(self, op: Operator) -> Operator:
        """Recurse into composite operators for index scan rewriting."""
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )

        if isinstance(op, IntersectOperator):
            return IntersectOperator([self._apply_index_scan(o) for o in op.operands])
        if isinstance(op, UnionOperator):
            return UnionOperator([self._apply_index_scan(o) for o in op.operands])
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._apply_index_scan(op.operand))
        if isinstance(op, ComposedOperator):
            return ComposedOperator([self._apply_index_scan(o) for o in op.operators])
        return op

    def _recurse_children(self, op: Operator) -> Operator:
        """Recursively optimize children of composite operators."""
        from uqa.operators.attention import AttentionFusionOperator
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.hybrid import (
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
            ProbNotOperator,
        )
        from uqa.operators.learned_fusion import LearnedFusionOperator
        from uqa.operators.primitive import FilterOperator, ScoreOperator
        from uqa.operators.sparse import SparseThresholdOperator

        match op:
            case IntersectOperator(operands=ops):
                return IntersectOperator([self.optimize(o) for o in ops])
            case UnionOperator(operands=ops):
                return UnionOperator([self.optimize(o) for o in ops])
            case ComplementOperator(operand=inner):
                return ComplementOperator(self.optimize(inner))
            case FilterOperator(field=f, predicate=p, source=s) if s is not None:
                return FilterOperator(f, p, self.optimize(s))
            case ComposedOperator(operators=ops):
                return ComposedOperator([self.optimize(o) for o in ops])
            case ScoreOperator(scorer=sc, source=src, query_terms=qt, field=f):
                return ScoreOperator(sc, self.optimize(src), qt, f)
            case LogOddsFusionOperator(signals=sigs):
                return LogOddsFusionOperator(
                    [self.optimize(s) for s in sigs],
                    alpha=op.alpha,
                    gating=op.gating,
                )
            case ProbBoolFusionOperator(signals=sigs):
                return ProbBoolFusionOperator(
                    [self.optimize(s) for s in sigs],
                    mode=op.mode,
                )
            case ProbNotOperator(signal=sig):
                return ProbNotOperator(
                    self.optimize(sig),
                    default_prob=op.default_prob,
                )
            case AttentionFusionOperator(signals=sigs):
                return AttentionFusionOperator(
                    [self.optimize(s) for s in sigs],
                    attention=op.attention,
                    query_features=op.query_features,
                )
            case LearnedFusionOperator(signals=sigs):
                return LearnedFusionOperator(
                    [self.optimize(s) for s in sigs],
                    learned=op.learned,
                )
            case SparseThresholdOperator(source=src):
                return SparseThresholdOperator(
                    self.optimize(src), threshold=op.threshold
                )
            case _:
                return op

    @staticmethod
    def _filter_applies_to(filter_op: object, target: Operator) -> bool:
        """Check if a filter is relevant to a specific operand."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator, TermOperator

        field = getattr(filter_op, "field", None)
        if field is None:
            return False

        if isinstance(target, TermOperator):
            return target.field == field or target.field is None
        if isinstance(target, FilterOperator):
            return target.field == field
        if isinstance(target, IntersectOperator):
            return any(
                QueryOptimizer._filter_applies_to(filter_op, child)
                for child in target.operands
            )
        return False
