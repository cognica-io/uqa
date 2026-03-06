#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from functools import reduce

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator


class UnionOperator(Operator):
    """Boolean union of multiple operands: A1 union A2 union ... union An."""

    def __init__(self, operands: list[Operator]) -> None:
        self.operands = operands

    def execute(self, context: ExecutionContext) -> PostingList:
        results = [op.execute(context) for op in self.operands]
        return reduce(PostingList.union, results, PostingList())

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(op.cost_estimate(stats) for op in self.operands)


class IntersectOperator(Operator):
    """Boolean intersection of multiple operands: A1 intersect A2 intersect ... intersect An."""

    def __init__(self, operands: list[Operator]) -> None:
        self.operands = operands

    def execute(self, context: ExecutionContext) -> PostingList:
        if not self.operands:
            return PostingList()
        results = [op.execute(context) for op in self.operands]
        return reduce(PostingList.intersect, results)

    def cost_estimate(self, stats: IndexStats) -> float:
        if not self.operands:
            return 0.0
        return min(op.cost_estimate(stats) for op in self.operands)


class ComplementOperator(Operator):
    """Boolean complement with respect to the universal set (all documents)."""

    def __init__(self, operand: Operator) -> None:
        self.operand = operand

    def execute(self, context: ExecutionContext) -> PostingList:
        result = self.operand.execute(context)
        # Build universal set from document_store
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()
        universal = PostingList([
            PostingEntry(doc_id, Payload(score=0.0))
            for doc_id in doc_store.doc_ids
        ])
        return result.complement(universal)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs)
