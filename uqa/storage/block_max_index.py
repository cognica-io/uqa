from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList

if TYPE_CHECKING:
    from uqa.scoring.bm25 import BM25Scorer


class BlockMaxIndex:
    """Per-block maximum score index for BMW optimization.

    Storage: O(|PostingList| / B * |Terms|) -- Theorem 6.2.2, Paper 3.
    """

    def __init__(self, block_size: int = 128) -> None:
        self.block_size = block_size
        self._block_maxes: dict[tuple[str, str], list[float]] = {}

    def build(
        self,
        posting_list: PostingList,
        scorer: BM25Scorer,
        field: str,
        term: str,
    ) -> None:
        """Compute per-block max scores for a posting list."""
        entries = posting_list.entries
        if not entries:
            self._block_maxes[(field, term)] = []
            return

        doc_freq = len(entries)
        block_maxes: list[float] = []

        for block_start in range(0, len(entries), self.block_size):
            block_end = min(block_start + self.block_size, len(entries))
            block_entries = entries[block_start:block_end]
            max_score = 0.0
            for entry in block_entries:
                tf = len(entry.payload.positions) if entry.payload.positions else 1
                score = scorer.score(tf, tf, doc_freq)
                max_score = max(max_score, score)
            block_maxes.append(max_score)

        self._block_maxes[(field, term)] = block_maxes

    def get_block_max(self, field: str, term: str, block_idx: int) -> float:
        """Return max score for a given block."""
        maxes = self._block_maxes.get((field, term))
        if maxes is None or block_idx >= len(maxes):
            return 0.0
        return maxes[block_idx]

    def num_blocks(self, field: str, term: str) -> int:
        maxes = self._block_maxes.get((field, term))
        if maxes is None:
            return 0
        return len(maxes)
