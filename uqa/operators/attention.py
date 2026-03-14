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
from uqa.operators.hybrid import _coverage_based_default

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.core.types import IndexStats
    from uqa.fusion.attention import AttentionFusion


class AttentionFusionOperator(Operator):
    """Attention-weighted multi-signal fusion operator (Section 8, Paper 4).

    Same pattern as LogOddsFusionOperator but uses attention-weighted
    fusion based on query features.
    """

    def __init__(
        self,
        signals: list[Operator],
        attention: AttentionFusion,
        query_features: NDArray,
    ) -> None:
        self.signals = signals
        self.attention = attention
        self.query_features = query_features

    def execute(self, context: ExecutionContext) -> PostingList:
        posting_lists = [sig.execute(context) for sig in self.signals]

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        sorted_ids = sorted(all_doc_ids)
        num_docs = len(sorted_ids)

        if num_docs == 0:
            return PostingList()

        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        entries: list[PostingEntry] = []
        for doc_id in sorted_ids:
            probs = [smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)]
            fused = self.attention.fuse(probs, self.query_features)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(sig.cost_estimate(stats) for sig in self.signals)
