from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator


class CardinalityEstimator:
    """Cardinality estimation for query optimization (Definition 6.2.3, Paper 1).

    Uses independence assumption for intersections and standard join
    cardinality formulas.
    """

    def estimate(self, op: Operator, stats: IndexStats) -> float:
        from uqa.operators.boolean import IntersectOperator, UnionOperator, ComplementOperator
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
            case FilterOperator():
                return n * 0.5
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
