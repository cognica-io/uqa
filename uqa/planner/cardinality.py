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
            return 1.0 - self._equality_selectivity(
                cs, predicate.target, ndv
            )

        if isinstance(predicate, InSet):
            sel = sum(
                self._equality_selectivity(cs, v, ndv)
                for v in predicate.values
            )
            return min(1.0, sel)

        if isinstance(predicate, Between):
            return self._range_selectivity(
                cs, predicate.low, predicate.high
            )

        if isinstance(predicate, (GreaterThan, GreaterThanOrEqual)):
            return self._gt_selectivity(cs, predicate.target)

        if isinstance(predicate, (LessThan, LessThanOrEqual)):
            return self._lt_selectivity(cs, predicate.target)

        return 0.5

    @staticmethod
    def _equality_selectivity(
        cs: ColumnStats, target: Any, ndv: int
    ) -> float:
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
    def _histogram_fraction(
        boundaries: list[Any], low: Any, high: Any
    ) -> float:
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
                        overlapping += 1.0
                        continue
                    clamp_low = max(float(low), float(b_low))
                    clamp_high = min(float(high), float(b_high))
                    overlapping += (clamp_high - clamp_low) / b_span
            except (TypeError, ValueError):
                overlapping += 1.0

        return max(0.0, min(1.0, overlapping / n_buckets))

    def _range_selectivity(
        self, cs: ColumnStats, low: Any, high: Any
    ) -> float:
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
            return self._histogram_fraction(
                cs.histogram, target, cs.histogram[-1]
            )
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
            return self._histogram_fraction(
                cs.histogram, cs.histogram[0], target
            )
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
