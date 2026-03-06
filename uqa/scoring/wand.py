from __future__ import annotations

import heapq
from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry

if TYPE_CHECKING:
    from uqa.storage.block_max_index import BlockMaxIndex


class WANDScorer:
    """WAND top-k scorer with safe pruning (Section 6.1, Paper 3).

    Pivot-based WAND algorithm uses upper bounds to prune posting list
    traversal. When the sum of upper bounds for terms up to the pivot
    is less than the current k-th highest score (threshold), those
    documents are guaranteed to not enter the top-k.
    """

    def __init__(
        self,
        scorers: list[object],
        k: int,
        posting_lists: list[PostingList],
        fields: list[str] | None = None,
        terms: list[str] | None = None,
    ) -> None:
        self.scorers = scorers
        self.k = k
        self.posting_lists = posting_lists
        self.fields = fields or [""] * len(posting_lists)
        self.terms = terms or [""] * len(posting_lists)

    def _compute_upper_bounds(self) -> list[float]:
        upper_bounds: list[float] = []
        for i, scorer in enumerate(self.scorers):
            df = len(self.posting_lists[i])
            ub = scorer.upper_bound(df)  # type: ignore[union-attr]
            upper_bounds.append(ub)
        return upper_bounds

    def score_top_k(self) -> PostingList:
        """Execute pivot-based WAND top-k algorithm."""
        upper_bounds = self._compute_upper_bounds()
        num_terms = len(self.posting_lists)

        if num_terms == 0:
            return PostingList()

        # Initialize iterators: list of (entries, current_position) per term
        iterators: list[list[PostingEntry]] = [
            pl.entries for pl in self.posting_lists
        ]
        positions: list[int] = [0] * num_terms

        # Min-heap of (-score, doc_id) for top-k tracking
        top_k_heap: list[tuple[float, int]] = []
        threshold = 0.0

        # Collect all unique doc_ids across all posting lists
        all_doc_ids: set[int] = set()
        for pl in self.posting_lists:
            all_doc_ids.update(e.doc_id for e in pl)

        for doc_id in sorted(all_doc_ids):
            # Compute the sum of upper bounds for terms that contain this doc_id
            potential_score = 0.0
            for i in range(num_terms):
                # Advance iterator to doc_id or past it
                while (
                    positions[i] < len(iterators[i])
                    and iterators[i][positions[i]].doc_id < doc_id
                ):
                    positions[i] += 1

                if (
                    positions[i] < len(iterators[i])
                    and iterators[i][positions[i]].doc_id == doc_id
                ):
                    potential_score += upper_bounds[i]

            # WAND pruning: skip if potential score is below threshold
            if potential_score < threshold:
                continue

            # Full scoring for this document
            actual_score = 0.0
            for i in range(num_terms):
                entry_pos = positions[i]
                if (
                    entry_pos < len(iterators[i])
                    and iterators[i][entry_pos].doc_id == doc_id
                ):
                    entry = iterators[i][entry_pos]
                    tf = len(entry.payload.positions) if entry.payload.positions else 1
                    df = len(self.posting_lists[i])
                    # Use doc_length = tf as approximation when not available
                    actual_score += self.scorers[i].score(tf, tf, df)  # type: ignore[union-attr]

            if len(top_k_heap) < self.k:
                heapq.heappush(top_k_heap, (actual_score, doc_id))
                if len(top_k_heap) == self.k:
                    threshold = top_k_heap[0][0]
            elif actual_score > threshold:
                heapq.heapreplace(top_k_heap, (actual_score, doc_id))
                threshold = top_k_heap[0][0]

        # Build result posting list
        entries: list[PostingEntry] = []
        for score, doc_id in top_k_heap:
            entries.append(PostingEntry(doc_id, Payload(score=score)))
        return PostingList(entries)


class BlockMaxWANDScorer:
    """Block-Max WAND with per-block upper bounds (Section 6.2, Paper 3).

    Uses per-block maximum scores for tighter bounds, achieving higher
    skip rates than standard WAND: Skip_BMW >= Skip_WAND.
    """

    def __init__(
        self,
        scorers: list[object],
        k: int,
        block_max_index: BlockMaxIndex,
        posting_lists: list[PostingList],
        fields: list[str] | None = None,
        terms: list[str] | None = None,
        block_size: int = 128,
    ) -> None:
        self.scorers = scorers
        self.k = k
        self.block_max_index = block_max_index
        self.posting_lists = posting_lists
        self.fields = fields or [""] * len(posting_lists)
        self.terms = terms or [""] * len(posting_lists)
        self.block_size = block_size

    def _get_block_idx(self, position: int) -> int:
        return position // self.block_size

    def score_top_k(self) -> PostingList:
        """Execute Block-Max WAND top-k algorithm."""
        num_terms = len(self.posting_lists)
        if num_terms == 0:
            return PostingList()

        iterators: list[list[PostingEntry]] = [
            pl.entries for pl in self.posting_lists
        ]
        positions: list[int] = [0] * num_terms

        top_k_heap: list[tuple[float, int]] = []
        threshold = 0.0

        all_doc_ids: set[int] = set()
        for pl in self.posting_lists:
            all_doc_ids.update(e.doc_id for e in pl)

        for doc_id in sorted(all_doc_ids):
            # Compute block-max upper bound for this document
            potential_score = 0.0
            for i in range(num_terms):
                while (
                    positions[i] < len(iterators[i])
                    and iterators[i][positions[i]].doc_id < doc_id
                ):
                    positions[i] += 1

                if (
                    positions[i] < len(iterators[i])
                    and iterators[i][positions[i]].doc_id == doc_id
                ):
                    block_idx = self._get_block_idx(positions[i])
                    block_max = self.block_max_index.get_block_max(
                        self.fields[i], self.terms[i], block_idx
                    )
                    potential_score += block_max

            # Block-Max WAND pruning: tighter bounds than standard WAND
            if potential_score < threshold:
                continue

            # Full scoring
            actual_score = 0.0
            for i in range(num_terms):
                entry_pos = positions[i]
                if (
                    entry_pos < len(iterators[i])
                    and iterators[i][entry_pos].doc_id == doc_id
                ):
                    entry = iterators[i][entry_pos]
                    tf = len(entry.payload.positions) if entry.payload.positions else 1
                    df = len(self.posting_lists[i])
                    actual_score += self.scorers[i].score(tf, tf, df)  # type: ignore[union-attr]

            if len(top_k_heap) < self.k:
                heapq.heappush(top_k_heap, (actual_score, doc_id))
                if len(top_k_heap) == self.k:
                    threshold = top_k_heap[0][0]
            elif actual_score > threshold:
                heapq.heapreplace(top_k_heap, (actual_score, doc_id))
                threshold = top_k_heap[0][0]

        entries: list[PostingEntry] = []
        for score, doc_id in top_k_heap:
            entries.append(PostingEntry(doc_id, Payload(score=score)))
        return PostingList(entries)
