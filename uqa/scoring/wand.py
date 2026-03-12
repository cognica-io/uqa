#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry

if TYPE_CHECKING:
    from uqa.storage.block_max_index import BlockMaxIndex


def _advance_cursor(
    entries: list[PostingEntry], pos: int, target: int
) -> int:
    """Advance to first position with doc_id >= target using binary search."""
    lo, hi = pos, len(entries)
    while lo < hi:
        mid = (lo + hi) // 2
        if entries[mid].doc_id < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


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

        # Initialize cursors: entries list and current position per term
        iterators: list[list[PostingEntry]] = [
            pl.entries for pl in self.posting_lists
        ]
        positions: list[int] = [0] * num_terms

        # Min-heap of (score, doc_id) for top-k tracking
        top_k_heap: list[tuple[float, int]] = []
        threshold = 0.0

        _INF = float("inf")

        while True:
            # Build sorted order of term indices by current doc_id
            def _cur_doc(i: int) -> float:
                if positions[i] < len(iterators[i]):
                    return iterators[i][positions[i]].doc_id
                return _INF

            sorted_terms = sorted(range(num_terms), key=_cur_doc)

            # If the smallest current doc_id is infinity, all exhausted
            if _cur_doc(sorted_terms[0]) == _INF:
                break

            # Find pivot: smallest index p where cumulative upper bounds
            # of sorted_terms[0..p] >= threshold
            cumulative = 0.0
            pivot = -1
            for idx in range(len(sorted_terms)):
                ti = sorted_terms[idx]
                # Skip exhausted terms
                if _cur_doc(ti) == _INF:
                    break
                cumulative += upper_bounds[ti]
                if cumulative >= threshold:
                    pivot = idx
                    break

            if pivot == -1:
                # Cannot reach threshold with any remaining terms
                break

            pivot_term = sorted_terms[pivot]
            pivot_doc = int(_cur_doc(pivot_term))

            # Check if all terms 0..pivot point to the same doc_id
            first_doc = int(_cur_doc(sorted_terms[0]))

            if first_doc == pivot_doc:
                # All terms up to pivot converge on pivot_doc -- score it
                actual_score = 0.0
                for i in range(num_terms):
                    entry_pos = positions[i]
                    if (
                        entry_pos < len(iterators[i])
                        and iterators[i][entry_pos].doc_id == pivot_doc
                    ):
                        entry = iterators[i][entry_pos]
                        tf = (
                            len(entry.payload.positions)
                            if entry.payload.positions
                            else 1
                        )
                        df = len(self.posting_lists[i])
                        actual_score += self.scorers[i].score(tf, tf, df)  # type: ignore[union-attr]

                if len(top_k_heap) < self.k:
                    heapq.heappush(top_k_heap, (actual_score, pivot_doc))
                    if len(top_k_heap) == self.k:
                        threshold = top_k_heap[0][0]
                elif actual_score > threshold:
                    heapq.heapreplace(
                        top_k_heap, (actual_score, pivot_doc)
                    )
                    threshold = top_k_heap[0][0]

                # Advance all cursors pointing at pivot_doc
                for i in range(num_terms):
                    if (
                        positions[i] < len(iterators[i])
                        and iterators[i][positions[i]].doc_id == pivot_doc
                    ):
                        positions[i] += 1
            else:
                # Advance the first cursor to pivot_doc via binary search
                first_term = sorted_terms[0]
                positions[first_term] = _advance_cursor(
                    iterators[first_term],
                    positions[first_term],
                    pivot_doc,
                )

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
        table_name: str = "",
    ) -> None:
        self.scorers = scorers
        self.k = k
        self.block_max_index = block_max_index
        self.posting_lists = posting_lists
        self.fields = fields or [""] * len(posting_lists)
        self.terms = terms or [""] * len(posting_lists)
        self.block_size = block_size
        self.table_name = table_name

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

        _INF = float("inf")

        while True:
            # Build sorted order of term indices by current doc_id
            def _cur_doc(i: int) -> float:
                if positions[i] < len(iterators[i]):
                    return iterators[i][positions[i]].doc_id
                return _INF

            sorted_terms = sorted(range(num_terms), key=_cur_doc)

            # If the smallest current doc_id is infinity, all exhausted
            if _cur_doc(sorted_terms[0]) == _INF:
                break

            # Find pivot using block-max scores
            cumulative = 0.0
            pivot = -1
            for idx in range(len(sorted_terms)):
                ti = sorted_terms[idx]
                if _cur_doc(ti) == _INF:
                    break
                block_idx = self._get_block_idx(positions[ti])
                block_max = self.block_max_index.get_block_max(
                    self.fields[ti],
                    self.terms[ti],
                    block_idx,
                    table_name=self.table_name,
                )
                cumulative += block_max
                if cumulative >= threshold:
                    pivot = idx
                    break

            if pivot == -1:
                break

            pivot_term = sorted_terms[pivot]
            pivot_doc = int(_cur_doc(pivot_term))

            first_doc = int(_cur_doc(sorted_terms[0]))

            if first_doc == pivot_doc:
                # Score the document fully
                actual_score = 0.0
                for i in range(num_terms):
                    entry_pos = positions[i]
                    if (
                        entry_pos < len(iterators[i])
                        and iterators[i][entry_pos].doc_id == pivot_doc
                    ):
                        entry = iterators[i][entry_pos]
                        tf = (
                            len(entry.payload.positions)
                            if entry.payload.positions
                            else 1
                        )
                        df = len(self.posting_lists[i])
                        actual_score += self.scorers[i].score(tf, tf, df)  # type: ignore[union-attr]

                if len(top_k_heap) < self.k:
                    heapq.heappush(top_k_heap, (actual_score, pivot_doc))
                    if len(top_k_heap) == self.k:
                        threshold = top_k_heap[0][0]
                elif actual_score > threshold:
                    heapq.heapreplace(
                        top_k_heap, (actual_score, pivot_doc)
                    )
                    threshold = top_k_heap[0][0]

                # Advance all cursors pointing at pivot_doc
                for i in range(num_terms):
                    if (
                        positions[i] < len(iterators[i])
                        and iterators[i][positions[i]].doc_id == pivot_doc
                    ):
                        positions[i] += 1
            else:
                # Advance the first cursor to pivot_doc via binary search
                first_term = sorted_terms[0]
                positions[first_term] = _advance_cursor(
                    iterators[first_term],
                    positions[first_term],
                    pivot_doc,
                )

        entries: list[PostingEntry] = []
        for score, doc_id in top_k_heap:
            entries.append(PostingEntry(doc_id, Payload(score=score)))
        return PostingList(entries)
