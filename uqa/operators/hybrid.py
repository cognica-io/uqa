from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.primitive import TermOperator, VectorSimilarityOperator

if TYPE_CHECKING:
    from numpy.typing import NDArray


class HybridTextVectorOperator(Operator):
    """Definition 3.3.1: Hybrid_{t,q,theta} = T(t) AND V_theta(q)."""

    def __init__(
        self,
        term: str,
        query_vector: NDArray,
        threshold: float,
    ) -> None:
        self.term_op = TermOperator(term)
        self.vector_op = VectorSimilarityOperator(query_vector, threshold)

    def execute(self, context: ExecutionContext) -> PostingList:
        return self.term_op.execute(context).intersect(
            self.vector_op.execute(context)
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        return min(
            self.term_op.cost_estimate(stats),
            self.vector_op.cost_estimate(stats),
        )


class SemanticFilterOperator(Operator):
    """Definition 3.3.4: SemanticFilter_{q,theta,L} = L AND V_theta(q)."""

    def __init__(
        self,
        source: Operator,
        query_vector: NDArray,
        threshold: float,
    ) -> None:
        self.source = source
        self.vector_op = VectorSimilarityOperator(query_vector, threshold)

    def execute(self, context: ExecutionContext) -> PostingList:
        return self.source.execute(context).intersect(
            self.vector_op.execute(context)
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        return min(
            self.source.cost_estimate(stats),
            self.vector_op.cost_estimate(stats),
        )
