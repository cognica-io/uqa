#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, FieldName, IndexStats, Payload, PostingEntry


@dataclass(frozen=True, slots=True)
class IndexedTerms:
    """Metadata returned from indexing a document.

    Used by the persistence layer to store posting entries and per-field
    token lengths without duplicating tokenization logic.
    """

    field_lengths: dict[str, int]
    postings: dict[tuple[str, str], tuple[int, ...]]  # (field, term) -> positions


class InvertedIndex:
    """Term-to-posting-list mapping with per-term statistics."""

    def __init__(self) -> None:
        self._index: dict[tuple[str, str], list[PostingEntry]] = {}
        self._doc_lengths: dict[DocId, dict[FieldName, int]] = {}
        self._doc_count: int = 0
        self._total_length: dict[FieldName, int] = defaultdict(int)

    def add_document(
        self, doc_id: DocId, fields: dict[FieldName, str]
    ) -> IndexedTerms:
        """Index a document by tokenizing each field.

        Returns an IndexedTerms with per-field lengths and posting data
        so the caller can persist them without re-tokenizing.
        """
        self._doc_count += 1
        self._doc_lengths[doc_id] = {}

        result_field_lengths: dict[str, int] = {}
        result_postings: dict[tuple[str, str], tuple[int, ...]] = {}

        for field_name, text in fields.items():
            tokens = text.lower().split()
            length = len(tokens)
            self._doc_lengths[doc_id][field_name] = length
            self._total_length[field_name] += length
            result_field_lengths[field_name] = length

            # Build position index for each token
            term_positions: dict[str, list[int]] = defaultdict(list)
            for pos, token in enumerate(tokens):
                term_positions[token].append(pos)

            for term, positions in term_positions.items():
                key = (field_name, term)
                if key not in self._index:
                    self._index[key] = []
                pos_tuple = tuple(positions)
                entry = PostingEntry(
                    doc_id,
                    Payload(positions=pos_tuple, score=0.0),
                )
                self._index[key].append(entry)
                result_postings[key] = pos_tuple

        return IndexedTerms(result_field_lengths, result_postings)

    # -- Restore methods (used by catalog persistence) -----------------

    def add_posting(
        self, field: str, term: str, entry: PostingEntry
    ) -> None:
        """Add a single posting entry directly (for catalog restore)."""
        key = (field, term)
        if key not in self._index:
            self._index[key] = []
        self._index[key].append(entry)

    def set_doc_length(
        self, doc_id: DocId, lengths: dict[FieldName, int]
    ) -> None:
        """Set per-field token lengths for a document (for catalog restore)."""
        self._doc_lengths[doc_id] = lengths

    def set_doc_count(self, count: int) -> None:
        """Set the indexed document count (for catalog restore)."""
        self._doc_count = count

    def add_total_length(self, field: FieldName, length: int) -> None:
        """Accumulate total token length for a field (for catalog restore)."""
        self._total_length[field] += length

    # -- Remove method (for delete support) ----------------------------

    def remove_document(self, doc_id: DocId) -> None:
        """Remove all entries for a document from the index."""
        keys_to_delete: list[tuple[str, str]] = []
        for key, entries in self._index.items():
            self._index[key] = [e for e in entries if e.doc_id != doc_id]
            if not self._index[key]:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self._index[key]

        if doc_id in self._doc_lengths:
            for fld, length in self._doc_lengths[doc_id].items():
                self._total_length[fld] -= length
            del self._doc_lengths[doc_id]
            self._doc_count -= 1

    def clear(self) -> None:
        """Remove all indexed data."""
        self._index.clear()
        self._doc_lengths.clear()
        self._doc_count = 0
        self._total_length.clear()

    # -- Query methods -------------------------------------------------

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
