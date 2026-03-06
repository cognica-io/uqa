#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, FieldName, IndexStats, Payload, PostingEntry


class InvertedIndex:
    """Term-to-posting-list mapping with per-term statistics."""

    def __init__(self) -> None:
        self._index: dict[tuple[str, str], list[PostingEntry]] = {}
        self._doc_lengths: dict[DocId, dict[FieldName, int]] = {}
        self._doc_count: int = 0
        self._total_length: dict[FieldName, int] = defaultdict(int)

    def add_document(self, doc_id: DocId, fields: dict[FieldName, str]) -> None:
        """Index a document by tokenizing each field."""
        self._doc_count += 1
        self._doc_lengths[doc_id] = {}

        for field_name, text in fields.items():
            tokens = text.lower().split()
            self._doc_lengths[doc_id][field_name] = len(tokens)
            self._total_length[field_name] += len(tokens)

            # Build position index for each token
            term_positions: dict[str, list[int]] = defaultdict(list)
            for pos, token in enumerate(tokens):
                term_positions[token].append(pos)

            for term, positions in term_positions.items():
                key = (field_name, term)
                if key not in self._index:
                    self._index[key] = []
                entry = PostingEntry(
                    doc_id,
                    Payload(positions=tuple(positions), score=0.0),
                )
                self._index[key].append(entry)

    def get_posting_list(self, field: str, term: str) -> PostingList:
        entries = self._index.get((field, term))
        if entries is None:
            return PostingList()
        return PostingList(list(entries))

    def get_posting_list_any_field(self, term: str) -> PostingList:
        """Get posting list matching term across any field."""
        all_entries: list[PostingEntry] = []
        seen_docs: set[DocId] = set()
        for (field, t), entries in self._index.items():
            if t == term:
                for e in entries:
                    if e.doc_id not in seen_docs:
                        seen_docs.add(e.doc_id)
                        all_entries.append(e)
        return PostingList(all_entries)

    def doc_freq(self, field: str, term: str) -> int:
        entries = self._index.get((field, term))
        if entries is None:
            return 0
        return len(entries)

    def get_doc_length(self, doc_id: DocId, field: FieldName) -> int:
        doc_lengths = self._doc_lengths.get(doc_id)
        if doc_lengths is None:
            return 0
        return doc_lengths.get(field, 0)

    def get_total_doc_length(self, doc_id: DocId) -> int:
        """Get total document length across all fields."""
        lengths = self._doc_lengths.get(doc_id, {})
        return sum(lengths.values())

    def get_term_freq(self, doc_id: DocId, field: str, term: str) -> int:
        """Get term frequency for a specific doc in a specific field."""
        entries = self._index.get((field, term), [])
        for e in entries:
            if e.doc_id == doc_id:
                return len(e.payload.positions) if e.payload.positions else 0
        return 0

    def get_total_term_freq(self, doc_id: DocId, term: str) -> int:
        """Get total term frequency for a doc across all fields."""
        total = 0
        for (f, t), entries in self._index.items():
            if t == term:
                for e in entries:
                    if e.doc_id == doc_id:
                        total += len(e.payload.positions) if e.payload.positions else 0
        return total

    def doc_freq_any_field(self, term: str) -> int:
        """Get document frequency across all fields."""
        doc_ids: set[DocId] = set()
        for (f, t), entries in self._index.items():
            if t == term:
                for e in entries:
                    doc_ids.add(e.doc_id)
        return len(doc_ids)

    @property
    def stats(self) -> IndexStats:
        total_length = sum(self._total_length.values())
        avg_doc_length = total_length / self._doc_count if self._doc_count > 0 else 0.0
        doc_freqs: dict[tuple[str, str], int] = {}
        for key, entries in self._index.items():
            doc_freqs[key] = len(entries)
        return IndexStats(
            total_docs=self._doc_count,
            avg_doc_length=avg_doc_length,
            _doc_freqs=doc_freqs,
        )
