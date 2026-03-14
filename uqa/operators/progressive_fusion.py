#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.operators.base import ExecutionContext, Operator

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


class ProgressiveFusionOperator(Operator):
    """Progressive multi-signal fusion with WAND pruning (Paper 4, Section 7).

    Cascading multi-stage fusion: each stage introduces new signals and
    narrows the candidate set via top-k cutoff using FusionWANDScorer.

    Each stage is a tuple of (new_signals, k):
    - new_signals: list of Operator producing new signal posting lists
    - k: top-k cutoff after fusing all accumulated signals
    """

    def __init__(
        self,
        stages: list[tuple[list[Operator], int]],
        alpha: float = 0.5,
        gating: str | None = None,
    ) -> None:
        if not stages:
            raise ValueError("ProgressiveFusionOperator requires at least one stage")
        self.stages = stages
        self.alpha = alpha
        self.gating = gating

    def execute(self, context: ExecutionContext) -> PostingList:
        from uqa.scoring.fusion_wand import FusionWANDScorer

        accumulated_posting_lists: list[PostingList] = []
        candidate_ids: set[int] | None = None

        for new_signals, k in self.stages:
            # Execute new signal operators
            new_pls: list[PostingList] = []
            for sig in new_signals:
                pl = sig.execute(context)
                # Filter to candidate set if we have one from previous stage
                if candidate_ids is not None:
                    filtered_entries = [e for e in pl if e.doc_id in candidate_ids]
                    pl = PostingList(filtered_entries)
                new_pls.append(pl)

            accumulated_posting_lists.extend(new_pls)

            # Compute upper bounds for all accumulated signals
            upper_bounds: list[float] = []
            for apl in accumulated_posting_lists:
                if apl:
                    ub = max(entry.payload.score for entry in apl)
                else:
                    ub = 0.5
                upper_bounds.append(ub)

            # Use WAND scorer to get top-k
            scorer = FusionWANDScorer(
                accumulated_posting_lists,
                upper_bounds,
                alpha=self.alpha,
                k=k,
                gating=self.gating,
            )
            result = scorer.score_top_k()

            # Update candidate set for next stage
            candidate_ids = {entry.doc_id for entry in result}

        # Return the final result from the last stage
        return result

    def cost_estimate(self, stats: IndexStats) -> float:
        """Cascading cost model: each stage cost proportional to candidate ratio."""
        total_cost = 0.0
        n = float(stats.total_docs)
        candidate_size = n

        for new_signals, k in self.stages:
            stage_cost = sum(sig.cost_estimate(stats) for sig in new_signals)
            # Scale by candidate ratio
            ratio = candidate_size / n if n > 0 else 1.0
            total_cost += stage_cost * ratio
            candidate_size = float(k)

        return total_cost
