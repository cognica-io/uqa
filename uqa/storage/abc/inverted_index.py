#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for inverted indexes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uqa.core.posting_list import PostingList
    from uqa.core.types import DocId, FieldName, IndexStats, PostingEntry


@dataclass(frozen=True, slots=True)
class IndexedTerms:
    """Metadata returned from indexing a document.

    Used by the persistence layer to store posting entries and per-field
    token lengths without duplicating tokenization logic.
    """

    field_lengths: dict[str, int]
    postings: dict[tuple[str, str], tuple[int, ...]]  # (field, term) -> positions


class InvertedIndex(ABC):
    """Abstract interface for inverted index backends.

    An inverted index maps ``(field, term)`` pairs to posting lists and
    maintains per-document token lengths and corpus statistics for scoring.
    Concrete implementations include in-memory and SQLite-backed stores.
    """

    # -- Indexing -----------------------------------------------------------

    @abstractmethod
    def add_document(self, doc_id: DocId, fields: dict[FieldName, str]) -> IndexedTerms:
        """Index a document by tokenizing each field.

        Returns an ``IndexedTerms`` with per-field lengths and posting data
        so the caller can persist them without re-tokenizing.
        """

    @abstractmethod
    def add_posting(self, field: str, term: str, entry: PostingEntry) -> None:
        """Add a single posting entry directly (for catalog restore)."""

    @abstractmethod
    def set_doc_length(self, doc_id: DocId, lengths: dict[FieldName, int]) -> None:
        """Set per-field token lengths for a document (for catalog restore)."""

    @abstractmethod
    def set_doc_count(self, count: int) -> None:
        """Set the indexed document count (for catalog restore)."""

    @abstractmethod
    def add_total_length(self, field: FieldName, length: int) -> None:
        """Accumulate total token length for a field (for catalog restore)."""

    @abstractmethod
    def remove_document(self, doc_id: DocId) -> None:
        """Remove all entries for a document from the index."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all indexed data."""

    # -- Query methods -----------------------------------------------------

    @abstractmethod
    def get_posting_list(self, field: str, term: str) -> PostingList:
        """Return the posting list for a specific (field, term) pair."""

    @abstractmethod
    def get_posting_list_any_field(self, term: str) -> PostingList:
        """Return the posting list matching *term* across any field."""

    @abstractmethod
    def doc_freq(self, field: str, term: str) -> int:
        """Return the document frequency for a (field, term) pair."""

    @abstractmethod
    def doc_freq_any_field(self, term: str) -> int:
        """Return the document frequency across all fields."""

    @abstractmethod
    def get_doc_length(self, doc_id: DocId, field: FieldName) -> int:
        """Return the token count for *doc_id* in *field*."""

    @abstractmethod
    def get_doc_lengths_bulk(
        self, doc_ids: list[DocId], field: FieldName
    ) -> dict[DocId, int]:
        """Return doc lengths for multiple doc_ids in a single call."""

    @abstractmethod
    def get_total_doc_length(self, doc_id: DocId) -> int:
        """Return the total document length across all fields."""

    @abstractmethod
    def get_term_freq(self, doc_id: DocId, field: str, term: str) -> int:
        """Return term frequency for a specific doc in a specific field."""

    @abstractmethod
    def get_term_freqs_bulk(
        self, doc_ids: list[DocId], field: str, term: str
    ) -> dict[DocId, int]:
        """Return term frequencies for multiple doc_ids in a single call."""

    @abstractmethod
    def get_total_term_freq(self, doc_id: DocId, term: str) -> int:
        """Return total term frequency for a doc across all fields."""

    # -- Analyzer methods --------------------------------------------------

    @property
    @abstractmethod
    def analyzer(self) -> Any:
        """Return the default analyzer."""

    @property
    @abstractmethod
    def field_analyzers(self) -> dict[str, Any]:
        """Return the per-field index-time analyzer overrides."""

    @abstractmethod
    def set_field_analyzer(
        self, field: str, analyzer: Any, phase: str = "both"
    ) -> None:
        """Set a per-field analyzer override.

        ``phase`` controls which phase the analyzer applies to:
        ``"index"`` for indexing only, ``"search"`` for search only,
        or ``"both"`` (default) for both phases.
        """

    @abstractmethod
    def get_field_analyzer(self, field: str) -> Any:
        """Return the index-time analyzer for a specific field."""

    @abstractmethod
    def get_search_analyzer(self, field: str) -> Any:
        """Return the search-time analyzer for a specific field.

        Falls back to the index-time analyzer, then the default analyzer.
        """

    # -- Statistics ---------------------------------------------------------

    @property
    @abstractmethod
    def stats(self) -> IndexStats:
        """Return corpus-level statistics for scoring."""
