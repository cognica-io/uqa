#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator
    from uqa.sql.table import ColumnStats


class CardinalityEstimator:
    """Cardinality estimation for query optimization (Definition 6.2.3, Paper 1).

    Uses independence assumption for intersections and standard join
    cardinality formulas.  When per-column statistics are available
    (via ``column_stats``), filter selectivity uses 1/ndv instead of
    the default 0.5.
    """

    def __init__(
        self, column_stats: dict[str, ColumnStats] | None = None
    ) -> None:
        self._column_stats = column_stats or {}

    def estimate(self, op: Operator, stats: IndexStats) -> float:
        from uqa.operators.boolean import (
            IntersectOperator,
            UnionOperator,
            ComplementOperator,
        )
        from uqa.operators.primitive import (
            FilterOperator,
            KNNOperator,
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
            case IntersectOperator(operands=ops):
                child_cards = [self.estimate(o, stats) for o in ops]
                result = child_cards[0] if child_cards else 0.0
                for card in child_cards[1:]:
                    result = (result * card) / n
                return max(1.0, result)
            case UnionOperator(operands=ops):
                child_cards = [self.estimate(o, stats) for o in ops]
                return min(n, sum(child_cards))
            case ComplementOperator(operand=inner):
                inner_card = self.estimate(inner, stats)
                return max(0.0, n - inner_card)
            case _:
                return n

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

    def _filter_selectivity(
        self, field: str, predicate: Any, n: float
    ) -> float:
        """Estimate filter selectivity using column statistics when available.

        Uses standard heuristics from database query optimizers:
          - Equality:  1 / ndv (number of distinct values)
          - Range (<, >, <=, >=): estimate from min/max range
          - IN(set):   |set| / ndv
          - BETWEEN:   fraction of [min, max] range
          - Default:   0.5 when no stats available
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
            return 1.0 / ndv

        if isinstance(predicate, NotEquals):
            return 1.0 - 1.0 / ndv

        if isinstance(predicate, InSet):
            return min(1.0, len(predicate.values) / ndv)

        if isinstance(predicate, Between):
            return self._range_fraction(
                cs, predicate.low, predicate.high
            )

        if isinstance(predicate, (GreaterThan, GreaterThanOrEqual)):
            target = predicate.target
            if cs.min_value is not None and cs.max_value is not None:
                try:
                    span = float(cs.max_value) - float(cs.min_value)
                    if span > 0:
                        return max(0.0, (float(cs.max_value) - float(target)) / span)
                except (TypeError, ValueError):
                    pass
            return 1.0 / 3.0

        if isinstance(predicate, (LessThan, LessThanOrEqual)):
            target = predicate.target
            if cs.min_value is not None and cs.max_value is not None:
                try:
                    span = float(cs.max_value) - float(cs.min_value)
                    if span > 0:
                        return max(0.0, (float(target) - float(cs.min_value)) / span)
                except (TypeError, ValueError):
                    pass
            return 1.0 / 3.0

        return 0.5

    @staticmethod
    def _range_fraction(
        cs: ColumnStats, low: Any, high: Any
    ) -> float:
        """Estimate the fraction of rows in [low, high] from column stats."""
        if cs.min_value is None or cs.max_value is None:
            return 0.25
        try:
            span = float(cs.max_value) - float(cs.min_value)
            if span <= 0:
                return 0.5
            return max(0.0, min(1.0, (float(high) - float(low)) / span))
        except (TypeError, ValueError):
            return 0.25
