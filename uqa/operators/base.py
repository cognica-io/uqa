#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from uqa.core.posting_list import PostingList

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.planner.parallel import ParallelExecutor
    from uqa.storage.block_max_index import BlockMaxIndex
    from uqa.storage.document_store import DocumentStore
    from uqa.storage.index_manager import IndexManager
    from uqa.storage.inverted_index import InvertedIndex
    from uqa.storage.spatial_index import SpatialIndex
    from uqa.storage.vector_index import VectorIndex


@dataclass
class ExecutionContext:
    """Context holding all storage backends for operator execution."""

    document_store: DocumentStore | None = None
    inverted_index: InvertedIndex | None = None
    vector_indexes: dict[str, VectorIndex] = field(default_factory=dict)
    spatial_indexes: dict[str, SpatialIndex] = field(default_factory=dict)
    graph_store: Any = None
    block_max_index: BlockMaxIndex | None = None
    index_manager: IndexManager | None = None
    parallel_executor: ParallelExecutor | None = None


class Operator(ABC):
    """Abstract base for all query operators.

    Operators form a monoid under composition (Theorem 3.2.3, Paper 1).
    """

    @abstractmethod
    def execute(self, context: ExecutionContext) -> PostingList: ...

    def compose(self, other: Operator) -> ComposedOperator:
        return ComposedOperator([self, other])

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs)


class ComposedOperator(Operator):
    """Sequential composition of operators (monoid product)."""

    def __init__(self, operators: list[Operator]) -> None:
        self.operators = operators

    def execute(self, context: ExecutionContext) -> PostingList:
        result = PostingList()
        for op in self.operators:
            result = op.execute(context)
        return result

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(op.cost_estimate(stats) for op in self.operators)
