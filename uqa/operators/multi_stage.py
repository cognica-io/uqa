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


class MultiStageOperator(Operator):
    """Multi-stage retrieval pipeline (Section 9, Paper 4).

    Depth as recursive Bayesian inference: each stage refines the
    candidate set from the previous stage.

    Each stage is a (operator, k_or_threshold) pair:
    - If k_or_threshold is an int, keep top-k by score
    - If k_or_threshold is a float, keep entries with score >= threshold

    Stage 0 executes fully. Each subsequent stage re-scores the
    surviving documents from the previous stage.
    """

    def __init__(
        self,
        stages: list[tuple[Operator, int | float]],
    ) -> None:
        if not stages:
            raise ValueError("MultiStageOperator requires at least one stage")
        self.stages = stages

    def execute(self, context: ExecutionContext) -> PostingList:
        # Stage 0: full execution
        first_op, first_cutoff = self.stages[0]
        candidates = first_op.execute(context)
        candidates = self._apply_cutoff(candidates, first_cutoff)

        # Subsequent stages: re-score surviving documents
        for stage_op, cutoff in self.stages[1:]:
            # Execute the stage operator to get scores
            stage_result = stage_op.execute(context)

            # Build score map from stage result
            stage_scores: dict[int, float] = {}
            for entry in stage_result:
                stage_scores[entry.doc_id] = entry.payload.score

            # Re-score surviving candidates
            re_scored: list[PostingEntry] = []
            for entry in candidates:
                new_score = stage_scores.get(entry.doc_id)
                if new_score is not None:
                    re_scored.append(
                        PostingEntry(entry.doc_id, Payload(score=new_score))
                    )
                else:
                    # Document not scored by this stage; keep original score
                    re_scored.append(entry)

            candidates = PostingList(re_scored)
            candidates = self._apply_cutoff(candidates, cutoff)

        return candidates

    @staticmethod
    def _apply_cutoff(pl: PostingList, cutoff: int | float) -> PostingList:
        """Apply a top-k or threshold cutoff to a posting list."""
        if isinstance(cutoff, int):
            # Top-k: sort by score descending, take top k
            sorted_entries = sorted(
                pl.entries, key=lambda e: e.payload.score, reverse=True
            )
            kept = sorted_entries[:cutoff]
            # Restore doc_id order
            kept.sort(key=lambda e: e.doc_id)
            return PostingList.from_sorted(kept)
        else:
            # Threshold: keep entries with score >= threshold
            entries = [e for e in pl if e.payload.score >= cutoff]
            return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        """Cascading cost: each stage sees fewer documents."""
        total = 0.0
        card = float(stats.total_docs)
        for op, cutoff in self.stages:
            total += op.cost_estimate(stats) * (
                card / max(1.0, float(stats.total_docs))
            )
            if isinstance(cutoff, int):
                card = min(card, float(cutoff))
            else:
                card *= 0.5  # heuristic: threshold keeps ~50%
        return total
