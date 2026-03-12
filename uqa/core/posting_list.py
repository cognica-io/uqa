#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import heapq
from collections.abc import Iterator

from uqa.core.types import DocId, GeneralizedPostingEntry, Payload, PostingEntry


class PostingList:
    """Ordered sequence of (doc_id, payload) pairs.

    Invariant: entries are sorted by doc_id in ascending order.
    Implements the Boolean algebra (L, union, intersect, complement, empty, universal).
    """

    def __init__(self, entries: list[PostingEntry] | None = None):
        if entries:
            seen: set[DocId] = set()
            deduped: list[PostingEntry] = []
            for e in sorted(entries, key=lambda e: e.doc_id):
                if e.doc_id not in seen:
                    seen.add(e.doc_id)
                    deduped.append(e)
            self._entries: list[PostingEntry] = deduped
        else:
            self._entries = []

    @classmethod
    def from_sorted(cls, entries: list[PostingEntry]) -> PostingList:
        """Create a PostingList from entries that are already sorted by doc_id.

        Bypasses the O(n log n) sort and O(n) dedup in ``__init__``.
        The caller MUST guarantee that *entries* are sorted by doc_id
        in ascending order and contain no duplicate doc_ids.
        """
        pl = cls.__new__(cls)
        pl._entries = entries
        return pl

    # -- Boolean Algebra Operations (Theorem 2.1.2, Paper 1) --

    def union(self, other: PostingList) -> PostingList:
        """A union B: two-pointer merge keeping all doc_ids."""
        result: list[PostingEntry] = []
        i, j = 0, 0
        while i < len(self._entries) and j < len(other._entries):
            a, b = self._entries[i], other._entries[j]
            if a.doc_id == b.doc_id:
                merged = self._merge_payloads(a.payload, b.payload)
                result.append(PostingEntry(a.doc_id, merged))
                i += 1
                j += 1
            elif a.doc_id < b.doc_id:
                result.append(a)
                i += 1
            else:
                result.append(b)
                j += 1
        result.extend(self._entries[i:])
        result.extend(other._entries[j:])
        pl = PostingList.__new__(PostingList)
        pl._entries = result
        return pl

    def intersect(self, other: PostingList) -> PostingList:
        """A intersect B: two-pointer merge keeping only shared doc_ids."""
        result: list[PostingEntry] = []
        i, j = 0, 0
        while i < len(self._entries) and j < len(other._entries):
            a, b = self._entries[i], other._entries[j]
            if a.doc_id == b.doc_id:
                merged = self._merge_payloads(a.payload, b.payload)
                result.append(PostingEntry(a.doc_id, merged))
                i += 1
                j += 1
            elif a.doc_id < b.doc_id:
                i += 1
            else:
                j += 1
        pl = PostingList.__new__(PostingList)
        pl._entries = result
        return pl

    def difference(self, other: PostingList) -> PostingList:
        """A - B: entries in A but not in B."""
        other_ids = other.doc_ids
        result = [e for e in self._entries if e.doc_id not in other_ids]
        pl = PostingList.__new__(PostingList)
        pl._entries = result
        return pl

    def complement(self, universal: PostingList) -> PostingList:
        """Complement of A with respect to universal set U: U - A."""
        return universal.difference(self)

    # -- Merge strategy for payloads during set operations --

    @staticmethod
    def _merge_payloads(a: Payload, b: Payload) -> Payload:
        positions = tuple(sorted(set(a.positions) | set(b.positions)))
        score = a.score + b.score
        fields = {**a.fields, **b.fields}
        return Payload(positions=positions, score=score, fields=fields)

    # -- Properties --

    @property
    def doc_ids(self) -> set[DocId]:
        return {e.doc_id for e in self._entries}

    @property
    def entries(self) -> list[PostingEntry]:
        return list(self._entries)

    def get_entry(self, doc_id: DocId) -> PostingEntry | None:
        lo, hi = 0, len(self._entries) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._entries[mid].doc_id == doc_id:
                return self._entries[mid]
            elif self._entries[mid].doc_id < doc_id:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def top_k(self, k: int) -> PostingList:
        """Return top-k entries by score (descending)."""
        if k >= len(self._entries):
            return PostingList.from_sorted(list(self._entries))
        top = heapq.nlargest(k, self._entries, key=lambda e: e.payload.score)
        return PostingList(top)

    def with_scores(self, score_fn: object) -> PostingList:
        """Return a new PostingList with scores updated by score_fn.

        score_fn is called as score_fn(entry) -> float.
        """
        result = []
        for e in self._entries:
            new_score = score_fn(e)  # type: ignore[operator]
            new_payload = Payload(
                positions=e.payload.positions,
                score=new_score,
                fields=e.payload.fields,
            )
            result.append(PostingEntry(e.doc_id, new_payload))
        pl = PostingList.__new__(PostingList)
        pl._entries = result
        return pl

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[PostingEntry]:
        return iter(self._entries)

    def __bool__(self) -> bool:
        return len(self._entries) > 0

    def __and__(self, other: PostingList) -> PostingList:
        return self.intersect(other)

    def __or__(self, other: PostingList) -> PostingList:
        return self.union(other)

    def __sub__(self, other: PostingList) -> PostingList:
        return self.difference(other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PostingList):
            return NotImplemented
        if len(self._entries) != len(other._entries):
            return False
        return all(
            a.doc_id == b.doc_id for a, b in zip(self._entries, other._entries)
        )

    def __repr__(self) -> str:
        ids = [e.doc_id for e in self._entries]
        return f"PostingList({ids})"


class GeneralizedPostingList:
    """Posting list with multi-document tuples for join results (Definition 4.1.2)."""

    def __init__(self, entries: list[GeneralizedPostingEntry] | None = None):
        self._entries = sorted(entries or [], key=lambda e: e.doc_ids)

    @property
    def entries(self) -> list[GeneralizedPostingEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[GeneralizedPostingEntry]:
        return iter(self._entries)

    def __bool__(self) -> bool:
        return len(self._entries) > 0

    def union(self, other: GeneralizedPostingList) -> GeneralizedPostingList:
        seen: set[tuple[DocId, ...]] = set()
        result: list[GeneralizedPostingEntry] = []
        for e in self._entries + other._entries:
            if e.doc_ids not in seen:
                seen.add(e.doc_ids)
                result.append(e)
        return GeneralizedPostingList(result)

    def __repr__(self) -> str:
        tuples = [e.doc_ids for e in self._entries]
        return f"GeneralizedPostingList({tuples})"
