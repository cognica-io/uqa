#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.planner.cardinality import CardinalityEstimator

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator
    from uqa.storage.index_manager import IndexManager


class QueryOptimizer:
    """Query optimizer with equivalence-preserving rewrite rules (Theorem 6.1.2, Paper 1).

    Rewrite rules:
    - Filter pushdown into intersections
    - Vector threshold merge (same query vector)
    - Intersect operand reordering by cardinality (cheapest first)
    - Index scan substitution (replace full scans with index scans)
    """

    def __init__(
        self,
        stats: IndexStats,
        column_stats: dict | None = None,
        index_manager: IndexManager | None = None,
        table_name: str | None = None,
    ):
        self.stats = stats
        self.estimator = CardinalityEstimator(column_stats)
        self._index_manager = index_manager
        self._table_name = table_name

    def optimize(self, op: Operator) -> Operator:
        op = self._push_filters_down(op)
        op = self._merge_vector_thresholds(op)
        op = self._reorder_intersect(op)
        op = self._apply_index_scan(op)
        return op

    def _push_filters_down(self, op: Operator) -> Operator:
        """Push FilterOperator through IntersectOperator when possible."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator

        if not isinstance(op, FilterOperator):
            return self._recurse_children(op)

        source = op.source
        if isinstance(source, IntersectOperator):
            new_operands = []
            pushed = False
            for child in source.operands:
                if not pushed and self._filter_applies_to(op, child):
                    new_operands.append(FilterOperator(op.field, op.predicate, child))
                    pushed = True
                else:
                    new_operands.append(child)
            if pushed:
                return self._recurse_children(IntersectOperator(new_operands))

        return FilterOperator(
            op.field,
            op.predicate,
            self._recurse_children(source),
        )

    def _merge_vector_thresholds(self, op: Operator) -> Operator:
        """Merge V_theta1(q) AND V_theta2(q) into V_max(theta1,theta2)(q)."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import VectorSimilarityOperator
        import numpy as np

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
                if (
                    merged.field == vector_ops[j].field
                    and np.array_equal(merged.query_vector, vector_ops[j].query_vector)
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
        children.sort(key=lambda c: self.estimator.estimate(c, self.stats))
        return IntersectOperator(children)

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
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.base import ComposedOperator

        if isinstance(op, IntersectOperator):
            return IntersectOperator(
                [self._apply_index_scan(o) for o in op.operands]
            )
        if isinstance(op, UnionOperator):
            return UnionOperator(
                [self._apply_index_scan(o) for o in op.operands]
            )
        if isinstance(op, ComplementOperator):
            return ComplementOperator(self._apply_index_scan(op.operand))
        if isinstance(op, ComposedOperator):
            return ComposedOperator(
                [self._apply_index_scan(o) for o in op.operators]
            )
        return op

    def _recurse_children(self, op: Operator) -> Operator:
        """Recursively optimize children of composite operators."""
        from uqa.operators.boolean import IntersectOperator, UnionOperator, ComplementOperator
        from uqa.operators.primitive import FilterOperator
        from uqa.operators.base import ComposedOperator

        match op:
            case IntersectOperator(operands=ops):
                return IntersectOperator([self.optimize(o) for o in ops])
            case UnionOperator(operands=ops):
                return UnionOperator([self.optimize(o) for o in ops])
            case ComplementOperator(operand=inner):
                return ComplementOperator(self.optimize(inner))
            case FilterOperator(field=f, predicate=p, source=s):
                return FilterOperator(f, p, self.optimize(s))
            case ComposedOperator(operators=ops):
                return ComposedOperator([self.optimize(o) for o in ops])
            case _:
                return op

    @staticmethod
    def _filter_applies_to(filter_op: object, target: Operator) -> bool:
        """Check if a filter is relevant to a specific operand."""
        from uqa.operators.primitive import TermOperator, FilterOperator

        field = getattr(filter_op, "field", None)
        if field is None:
            return False

        if isinstance(target, TermOperator):
            return target.field == field or target.field is None
        if isinstance(target, FilterOperator):
            return target.field == field
        return False
