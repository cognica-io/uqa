#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from typing import Any

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, FieldName, IndexStats, Payload, PostingEntry
from uqa.storage.abc.inverted_index import IndexedTerms, InvertedIndex

__all__ = ["IndexedTerms", "InvertedIndex", "MemoryInvertedIndex"]


class MemoryInvertedIndex(InvertedIndex):
    """Term-to-posting-list mapping with per-term statistics.

    The internal ``_index`` maps each (field, term) key to a dict of
    ``{DocId: PostingEntry}``.  This gives O(1) term-frequency lookup
    per document instead of a linear scan over the posting list.

    A reverse map ``_doc_terms`` tracks which (field, term) keys each
    document appears in, making ``remove_document`` proportional to the
    number of distinct terms in that document rather than the total
    index size.
    """

    def __init__(
        self,
        analyzer: Any | None = None,
        field_analyzers: dict[str, Any] | None = None,
    ) -> None:
        from uqa.analysis.analyzer import DEFAULT_ANALYZER

        self._analyzer = analyzer or DEFAULT_ANALYZER
        self._index_field_analyzers: dict[str, Any] = (
            dict(field_analyzers) if field_analyzers else {}
        )
        self._search_field_analyzers: dict[str, Any] = {}
        self._index: dict[tuple[str, str], dict[DocId, PostingEntry]] = {}
        self._doc_terms: dict[DocId, set[tuple[str, str]]] = {}
        self._doc_lengths: dict[DocId, dict[FieldName, int]] = {}
        self._doc_count: int = 0
        self._total_length: dict[FieldName, int] = defaultdict(int)
        self._cached_stats: IndexStats | None = None
        self._term_to_keys: dict[str, list[tuple[str, str]]] = defaultdict(list)

    @property
    def analyzer(self) -> Any:
        return self._analyzer

    @property
    def field_analyzers(self) -> dict[str, Any]:
        return self._index_field_analyzers

    def set_field_analyzer(
        self, field: str, analyzer: Any, phase: str = "both"
    ) -> None:
        """Set a per-field analyzer override.

        ``phase`` controls which phase the analyzer applies to:
        ``"index"`` for indexing only, ``"search"`` for search only,
        or ``"both"`` (default) for both phases.
        """
        if phase not in ("index", "search", "both"):
            raise ValueError(
                f"phase must be 'index', 'search', or 'both', got '{phase}'"
            )
        if phase in ("index", "both"):
            self._index_field_analyzers[field] = analyzer
        if phase in ("search", "both"):
            self._search_field_analyzers[field] = analyzer

    def get_field_analyzer(self, field: str) -> Any:
        """Get the index-time analyzer for a specific field."""
        return self._index_field_analyzers.get(field, self._analyzer)

    def get_search_analyzer(self, field: str) -> Any:
        """Get the search-time analyzer for a specific field.

        Falls back to the index-time analyzer, then the default analyzer.
        """
        return self._search_field_analyzers.get(
            field, self._index_field_analyzers.get(field, self._analyzer)
        )

    def add_document(self, doc_id: DocId, fields: dict[FieldName, str]) -> IndexedTerms:
        """Index a document by tokenizing each field.

        Returns an IndexedTerms with per-field lengths and posting data
        so the caller can persist them without re-tokenizing.
        """
        self._cached_stats = None
        self._doc_count += 1
        self._doc_lengths[doc_id] = {}

        result_field_lengths: dict[str, int] = {}
        result_postings: dict[tuple[str, str], tuple[int, ...]] = {}

        doc_term_set = self._doc_terms.get(doc_id)
        if doc_term_set is None:
            doc_term_set = set()
            self._doc_terms[doc_id] = doc_term_set

        for field_name, text in fields.items():
            field_analyzer = self._index_field_analyzers.get(field_name, self._analyzer)
            tokens = field_analyzer.analyze(text)
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
                is_new_key = key not in self._index
                if is_new_key:
                    self._index[key] = {}
                    self._term_to_keys[term].append(key)
                pos_tuple = tuple(positions)
                entry = PostingEntry(
                    doc_id,
                    Payload(positions=pos_tuple, score=0.0),
                )
                self._index[key][doc_id] = entry
                doc_term_set.add(key)
                result_postings[key] = pos_tuple

        return IndexedTerms(result_field_lengths, result_postings)

    # -- Restore methods (used by catalog persistence) -----------------

    def add_posting(self, field: str, term: str, entry: PostingEntry) -> None:
        """Add a single posting entry directly (for catalog restore)."""
        self._cached_stats = None
        key = (field, term)
        if key not in self._index:
            self._index[key] = {}
            self._term_to_keys[term].append(key)
        self._index[key][entry.doc_id] = entry

        doc_term_set = self._doc_terms.get(entry.doc_id)
        if doc_term_set is None:
            doc_term_set = set()
            self._doc_terms[entry.doc_id] = doc_term_set
        doc_term_set.add(key)

    def set_doc_length(self, doc_id: DocId, lengths: dict[FieldName, int]) -> None:
        """Set per-field token lengths for a document (for catalog restore)."""
        self._doc_lengths[doc_id] = lengths

    def set_doc_count(self, count: int) -> None:
        """Set the indexed document count (for catalog restore)."""
        self._cached_stats = None
        self._doc_count = count

    def add_total_length(self, field: FieldName, length: int) -> None:
        """Accumulate total token length for a field (for catalog restore)."""
        self._cached_stats = None
        self._total_length[field] += length

    # -- Remove method (for delete support) ----------------------------

    def remove_document(self, doc_id: DocId) -> None:
        """Remove all entries for a document from the index.

        Uses the ``_doc_terms`` reverse map to touch only relevant
        posting dicts, avoiding a full scan of the entire index.
        """
        self._cached_stats = None
        keys = self._doc_terms.pop(doc_id, set())
        for key in keys:
            inner = self._index.get(key)
            if inner is not None:
                inner.pop(doc_id, None)
                if not inner:
                    del self._index[key]
                    _field, term = key
                    term_keys = self._term_to_keys.get(term)
                    if term_keys is not None:
                        try:
                            term_keys.remove(key)
                        except ValueError:
                            pass
                        if not term_keys:
                            del self._term_to_keys[term]

        if doc_id in self._doc_lengths:
            for fld, length in self._doc_lengths[doc_id].items():
                self._total_length[fld] -= length
            del self._doc_lengths[doc_id]
            self._doc_count -= 1

    def clear(self) -> None:
        """Remove all indexed data."""
        self._cached_stats = None
        self._index.clear()
        self._doc_terms.clear()
        self._doc_lengths.clear()
        self._doc_count = 0
        self._total_length.clear()
        self._term_to_keys.clear()

    # -- Query methods -------------------------------------------------

    def get_posting_list(self, field: str, term: str) -> PostingList:
        inner = self._index.get((field, term))
        if inner is None:
            return PostingList()
        entries = sorted(inner.values(), key=lambda e: e.doc_id)
        return PostingList.from_sorted(entries)

    def get_posting_list_any_field(self, term: str) -> PostingList:
        """Get posting list matching term across any field."""
        keys = self._term_to_keys.get(term)
        if not keys:
            return PostingList()
        seen_docs: set[DocId] = set()
        all_entries: list[PostingEntry] = []
        for key in keys:
            inner = self._index.get(key)
            if inner is not None:
                for doc_id, e in inner.items():
                    if doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        all_entries.append(e)
        all_entries.sort(key=lambda e: e.doc_id)
        return PostingList.from_sorted(all_entries)

    def doc_freq(self, field: str, term: str) -> int:
        inner = self._index.get((field, term))
        if inner is None:
            return 0
        return len(inner)

    def get_doc_length(self, doc_id: DocId, field: FieldName) -> int:
        doc_lengths = self._doc_lengths.get(doc_id)
        if doc_lengths is None:
            return 0
        return doc_lengths.get(field, 0)

    def get_doc_lengths_bulk(
        self, doc_ids: list[DocId], field: FieldName
    ) -> dict[DocId, int]:
        """Return doc lengths for multiple doc_ids in a single call."""
        result: dict[DocId, int] = {}
        for doc_id in doc_ids:
            lengths = self._doc_lengths.get(doc_id)
            result[doc_id] = lengths.get(field, 0) if lengths else 0
        return result

    def get_total_doc_length(self, doc_id: DocId) -> int:
        """Get total document length across all fields."""
        lengths = self._doc_lengths.get(doc_id, {})
        return sum(lengths.values())

    def get_term_freq(self, doc_id: DocId, field: str, term: str) -> int:
        """Get term frequency for a specific doc in a specific field."""
        inner = self._index.get((field, term))
        if inner is None:
            return 0
        e = inner.get(doc_id)
        if e is None:
            return 0
        return len(e.payload.positions) if e.payload.positions else 0

    def get_term_freqs_bulk(
        self, doc_ids: list[DocId], field: str, term: str
    ) -> dict[DocId, int]:
        """Return term frequencies for multiple doc_ids in a single call."""
        inner = self._index.get((field, term))
        if inner is None:
            return dict.fromkeys(doc_ids, 0)
        result: dict[DocId, int] = {}
        for doc_id in doc_ids:
            e = inner.get(doc_id)
            if e is None:
                result[doc_id] = 0
            else:
                result[doc_id] = len(e.payload.positions) if e.payload.positions else 0
        return result

    def get_total_term_freq(self, doc_id: DocId, term: str) -> int:
        """Get total term frequency for a doc across all fields."""
        keys = self._term_to_keys.get(term)
        if not keys:
            return 0
        total = 0
        for key in keys:
            inner = self._index.get(key)
            if inner is not None:
                e = inner.get(doc_id)
                if e is not None:
                    total += len(e.payload.positions) if e.payload.positions else 0
        return total

    def doc_freq_any_field(self, term: str) -> int:
        """Get document frequency across all fields."""
        keys = self._term_to_keys.get(term)
        if not keys:
            return 0
        doc_ids: set[DocId] = set()
        for key in keys:
            inner = self._index.get(key)
            if inner is not None:
                doc_ids.update(inner.keys())
        return len(doc_ids)

    @property
    def stats(self) -> IndexStats:
        if self._cached_stats is not None:
            return self._cached_stats
        total_length = sum(self._total_length.values())
        avg_doc_length = total_length / self._doc_count if self._doc_count > 0 else 0.0
        doc_freqs: dict[tuple[str, str], int] = {}
        for key, inner in self._index.items():
            doc_freqs[key] = len(inner)
        result = IndexStats(
            total_docs=self._doc_count,
            avg_doc_length=avg_doc_length,
            _doc_freqs=doc_freqs,
        )
        self._cached_stats = result
        return result
