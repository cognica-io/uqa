#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


class SparseThresholdOperator(Operator):
    """ReLU thresholding operator (Section 6.5, Paper 4).

    Applies max(0, score - threshold) to each document score, excluding
    documents whose adjusted score is zero.  This implements the MAP
    estimation interpretation of ReLU activation: documents below the
    threshold have zero posterior probability under the sparse prior.
    """

    def __init__(self, source: Operator, threshold: float) -> None:
        self.source = source
        self.threshold = threshold

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        entries: list[PostingEntry] = []
        for entry in source_pl:
            adjusted = entry.payload.score - self.threshold
            if adjusted > 0.0:
                entries.append(
                    PostingEntry(
                        entry.doc_id,
                        Payload(
                            score=adjusted,
                            fields=entry.payload.fields,
                            positions=entry.payload.positions,
                        ),
                    )
                )
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.source.cost_estimate(stats)
