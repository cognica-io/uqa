#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed inverted index -- drop-in replacement for InvertedIndex.

Postings, document lengths, and aggregate field statistics use the UQA canonical
shared-table format: ``_postings``, ``_doc_lengths``, and ``_field_stats``.

Performance structures (Phase 2, Section 3.2.2):
    Skip pointers -- every Nth doc_id per term for fast forward-seeking
        during posting list intersection.  Table: _skip_{table}_{field}.
    Block-max scores -- per-block maximum BM25 scores for BMW pruning.
        Table: _blockmax_{table}_{field}.
"""

from __future__ import annotations

import json
import struct
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.storage.abc.inverted_index import IndexedTerms, InvertedIndex

if TYPE_CHECKING:
    from uqa.core.types import DocId, FieldName, IndexStats
    from uqa.storage.managed_connection import SQLiteConnection


class SQLiteInvertedIndex(InvertedIndex):
    """Term-to-posting-list mapping backed by SQLite.

    Public API is identical to ``InvertedIndex`` so that this class can
    serve as a transparent, persistent drop-in replacement.
    """

    BLOCK_SIZE = 128

    def __init__(
        self,
        conn: SQLiteConnection,
        table_name: str,
        analyzer: Any | None = None,
        field_analyzers: dict[str, Any] | None = None,
    ) -> None:
        from uqa.analysis.analyzer import DEFAULT_ANALYZER

        self._conn = conn
        self._table_name = table_name
        self._analyzer = analyzer or DEFAULT_ANALYZER
        self._index_field_analyzers: dict[str, Any] = (
            dict(field_analyzers) if field_analyzers else {}
        )
        self._search_field_analyzers: dict[str, Any] = {}
        self._known_fields: set[str] = set()
        self._has_atomic_fetch = hasattr(conn, "execute_fetchall")
        self._cached_stats: IndexStats | None = None
        self._dirty_terms: set[tuple[str, str]] = set()

        # Create canonical shared FTS tables eagerly.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _postings ("
            "    table_name TEXT NOT NULL,"
            "    field      TEXT NOT NULL,"
            "    term       TEXT NOT NULL,"
            "    doc_id     INTEGER NOT NULL,"
            "    positions  BLOB NOT NULL,"
            "    PRIMARY KEY (table_name, field, term, doc_id)"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS _postings_term_idx "
            "ON _postings (table_name, field, term)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS _postings_doc_idx "
            "ON _postings (table_name, doc_id)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _doc_lengths ("
            "    table_name TEXT NOT NULL,"
            "    doc_id     INTEGER NOT NULL,"
            "    field      TEXT NOT NULL,"
            "    length     INTEGER NOT NULL,"
            "    PRIMARY KEY (table_name, doc_id, field)"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _field_stats ("
            "    table_name   TEXT NOT NULL,"
            "    field        TEXT NOT NULL,"
            "    total_length INTEGER NOT NULL DEFAULT 0,"
            "    PRIMARY KEY (table_name, field)"
            ")"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "_field_stats_{table_name}" ('
            "    field        TEXT PRIMARY KEY,"
            "    doc_count    INTEGER NOT NULL DEFAULT 0,"
            "    total_length INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        self._conn.commit()

        # Discover fields already present in canonical or legacy storage.
        for (field,) in self._fetchall(
            "SELECT DISTINCT field FROM _doc_lengths WHERE table_name = ?",
            (table_name,),
        ):
            self._known_fields.add(field)
        rows = self._fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
            (f"_inverted_{table_name}_%",),
        )
        prefix = f"_inverted_{table_name}_"
        for (name,) in rows:
            field = name[len(prefix) :]
            self._known_fields.add(field)

    # -- Thread-safe query helpers -------------------------------------

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute a query and return all rows.

        Uses ``ManagedConnection.execute_fetchall`` when available to
        guarantee atomicity under concurrent access.  Falls back to the
        standard cursor pattern for plain ``sqlite3.Connection``.
        """
        if self._has_atomic_fetch:
            return self._conn.execute_fetchall(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchall()

    def _fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        """Execute a query and return one row atomically."""
        if self._has_atomic_fetch:
            return self._conn.execute_fetchone(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchone()

    # -- Lazy table creation -------------------------------------------

    def _ensure_field_table(self, field: str) -> None:
        """Create the per-field skip and block-max auxiliary tables."""
        skip_tbl = self._skip_table_name(field)
        bm_tbl = self._blockmax_table_name(field)
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{skip_tbl}" ('
            "    term        TEXT    NOT NULL,"
            "    skip_doc_id INTEGER NOT NULL,"
            "    skip_offset INTEGER NOT NULL,"
            "    PRIMARY KEY (term, skip_doc_id)"
            ")"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{bm_tbl}" ('
            "    term      TEXT    NOT NULL,"
            "    block_idx INTEGER NOT NULL,"
            "    max_score REAL    NOT NULL,"
            "    PRIMARY KEY (term, block_idx)"
            ")"
        )
        self._conn.commit()
        self._known_fields.add(field)

    def _inverted_table_name(self, field: str) -> str:
        return f"_inverted_{self._table_name}_{field}"

    def _skip_table_name(self, field: str) -> str:
        return f"_skip_{self._table_name}_{field}"

    def _blockmax_table_name(self, field: str) -> str:
        return f"_blockmax_{self._table_name}_{field}"

    # -- Analyzer accessors --------------------------------------------

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

    # -- Tokenization --------------------------------------------------

    def _tokenize(self, text: str, field: str | None = None) -> list[str]:
        """Tokenize text using the appropriate field analyzer."""
        analyzer = (
            self._index_field_analyzers.get(field, self._analyzer)
            if field
            else self._analyzer
        )
        return analyzer.analyze(text)

    # -- Positions encoding helpers ------------------------------------

    @staticmethod
    def _encode_positions(positions: tuple[int, ...] | list[int]) -> bytes:
        """Encode positions as canonical little-endian uint32 values."""
        return struct.pack(f"<{len(positions)}I", *positions)

    @staticmethod
    def _decode_positions(data: str | bytes) -> tuple[int, ...]:
        """Decode positions from binary blob or legacy JSON text."""
        if isinstance(data, bytes):
            little = struct.unpack(f"<{len(data) // 4}I", data)
            if little and max(little) > 10_000_000:
                return struct.unpack(f">{len(data) // 4}I", data)
            return little
        # Legacy JSON-encoded positions (TEXT).
        return tuple(json.loads(data))

    # -- Deferred skip pointer rebuild ---------------------------------

    def flush_skip_pointers(self) -> None:
        """Rebuild skip pointers for all dirty (field, term) pairs."""
        if not self._dirty_terms:
            return
        dirty = self._dirty_terms
        self._dirty_terms = set()
        for field, term in dirty:
            self._rebuild_skip_pointers(field, term)

    # -- Indexing -------------------------------------------------------

    def add_document(self, doc_id: DocId, fields: dict[FieldName, str]) -> IndexedTerms:
        """Index a document by tokenizing each field.

        Returns an ``IndexedTerms`` with per-field lengths and posting
        data so the caller can persist them without re-tokenizing.
        """
        result_field_lengths: dict[str, int] = {}
        result_postings: dict[tuple[str, str], tuple[int, ...]] = {}

        old_lengths = self._fetchall(
            "SELECT field, length FROM _doc_lengths "
            "WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        for field, length in old_lengths:
            self._conn.execute(
                "UPDATE _field_stats "
                "SET total_length = MAX(total_length - ?, 0) "
                "WHERE table_name = ? AND field = ?",
                (length, self._table_name, field),
            )
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _doc_lengths WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )

        for field_name, text in fields.items():
            self._ensure_field_table(field_name)

            tokens = self._tokenize(text, field_name)
            length = len(tokens)
            result_field_lengths[field_name] = length

            # Build position index for each token.
            term_positions: dict[str, list[int]] = defaultdict(list)
            for pos, token in enumerate(tokens):
                term_positions[token].append(pos)

            # Batch insert all term postings for this field at once.
            batch_rows: list[tuple[str, str, str, int, bytes]] = []
            for term, positions in term_positions.items():
                pos_tuple = tuple(positions)
                batch_rows.append(
                    (
                        self._table_name,
                        field_name,
                        term,
                        doc_id,
                        self._encode_positions(pos_tuple),
                    )
                )
                result_postings[(field_name, term)] = pos_tuple

            self._conn.executemany(
                "INSERT OR REPLACE INTO _postings "
                "(table_name, field, term, doc_id, positions) "
                "VALUES (?, ?, ?, ?, ?)",
                batch_rows,
            )

            # Doc length
            self._conn.execute(
                "INSERT OR REPLACE INTO _doc_lengths "
                "(table_name, doc_id, field, length) VALUES (?, ?, ?, ?)",
                (self._table_name, doc_id, field_name, length),
            )

            # Field stats -- canonical total length only.
            self._conn.execute(
                "INSERT INTO _field_stats "
                "(table_name, field, total_length) VALUES (?, ?, ?) "
                "ON CONFLICT(table_name, field) DO UPDATE SET "
                "total_length = total_length + excluded.total_length",
                (self._table_name, field_name, length),
            )
            self._conn.execute(
                f'INSERT INTO "_field_stats_{self._table_name}" '
                "(field, doc_count, total_length) VALUES (?, 1, ?) "
                "ON CONFLICT(field) DO UPDATE SET "
                "doc_count = doc_count + 1, "
                "total_length = total_length + excluded.total_length",
                (field_name, length),
            )

        self._conn.commit()
        self._cached_stats = None

        # Defer skip pointer rebuilds until the next query.
        for field_name, term in result_postings:
            self._dirty_terms.add((field_name, term))

        return IndexedTerms(result_field_lengths, result_postings)

    # -- Restore methods (backward compatibility during migration) ------

    def add_posting(self, field: str, term: str, entry: PostingEntry) -> None:
        """Add a single posting entry directly (for catalog restore)."""
        self._ensure_field_table(field)
        positions = tuple(entry.payload.positions) if entry.payload.positions else ()
        self._conn.execute(
            "INSERT OR REPLACE INTO _postings "
            "(table_name, field, term, doc_id, positions) VALUES (?, ?, ?, ?, ?)",
            (
                self._table_name,
                field,
                term,
                entry.doc_id,
                self._encode_positions(positions),
            ),
        )
        self._conn.commit()

    def set_doc_length(self, doc_id: DocId, lengths: dict[FieldName, int]) -> None:
        """Set per-field token lengths for a document (for catalog restore)."""
        for field, length in lengths.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO _doc_lengths "
                "(table_name, doc_id, field, length) VALUES (?, ?, ?, ?)",
                (self._table_name, doc_id, field, length),
            )
        self._conn.commit()

    def set_doc_count(self, count: int) -> None:
        """Set the indexed document count (for catalog restore).

        Canonical storage derives document count from ``_doc_lengths`` rows.
        This compatibility mirror is used only by old Python restore
        callers that set stats before any document-length rows exist.
        """
        self._conn.execute(
            f'UPDATE "_field_stats_{self._table_name}" SET doc_count = ?',
            (count,),
        )
        self._conn.commit()

    def add_total_length(self, field: FieldName, length: int) -> None:
        """Accumulate total token length for a field (for catalog restore)."""
        self._conn.execute(
            "INSERT INTO _field_stats (table_name, field, total_length) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(table_name, field) DO UPDATE SET "
            "total_length = total_length + excluded.total_length",
            (self._table_name, field, length),
        )
        self._conn.execute(
            f'INSERT INTO "_field_stats_{self._table_name}" '
            "(field, doc_count, total_length) VALUES (?, 0, ?) "
            "ON CONFLICT(field) DO UPDATE SET "
            "total_length = total_length + excluded.total_length",
            (field, length),
        )
        self._conn.commit()

    # -- Remove --------------------------------------------------------

    def remove_document(self, doc_id: DocId) -> None:
        """Remove all entries for a document from the index."""
        # Collect per-field lengths so we can decrement field stats.
        rows = self._fetchall(
            "SELECT field, length FROM _doc_lengths "
            "WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )

        # Collect affected (field, term) pairs for skip pointer rebuild.
        affected_terms = self._fetchall(
            "SELECT field, term FROM _postings "
            "WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )

        if rows:
            for field, length in rows:
                self._conn.execute(
                    "UPDATE _field_stats "
                    "SET total_length = MAX(total_length - ?, 0) "
                    "WHERE table_name = ? AND field = ?",
                    (length, self._table_name, field),
                )
                self._conn.execute(
                    f'UPDATE "_field_stats_{self._table_name}" '
                    "SET doc_count = MAX(doc_count - 1, 0), "
                    "total_length = MAX(total_length - ?, 0) "
                    "WHERE field = ?",
                    (length, field),
                )
            self._conn.execute(
                "DELETE FROM _doc_lengths WHERE table_name = ? AND doc_id = ?",
                (self._table_name, doc_id),
            )
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )

        self._conn.commit()
        self._cached_stats = None

        # Defer skip pointer rebuilds until next query.
        for field, term in affected_terms:
            self._dirty_terms.add((field, term))

    def clear(self) -> None:
        """Remove all indexed data from all backing tables."""
        for field in self._known_fields:
            skip_tbl = f"_skip_{self._table_name}_{field}"
            bm_tbl = f"_blockmax_{self._table_name}_{field}"
            self._conn.execute(f'DROP TABLE IF EXISTS "{skip_tbl}"')
            self._conn.execute(f'DROP TABLE IF EXISTS "{bm_tbl}"')
        self._conn.execute("DELETE FROM _postings WHERE table_name = ?", (self._table_name,))
        self._conn.execute("DELETE FROM _field_stats WHERE table_name = ?", (self._table_name,))
        self._conn.execute("DELETE FROM _doc_lengths WHERE table_name = ?", (self._table_name,))
        self._conn.execute(f'DELETE FROM "_field_stats_{self._table_name}"')
        self._conn.commit()
        self._cached_stats = None
        self._dirty_terms.clear()
        self._known_fields.clear()

    # -- Query methods -------------------------------------------------

    def _flush_term(self, field: str, term: str) -> None:
        """Flush skip pointers for a specific (field, term) if dirty."""
        key = (field, term)
        if key in self._dirty_terms:
            self._dirty_terms.discard(key)
            self._rebuild_skip_pointers(field, term)

    def get_posting_list(self, field: str, term: str) -> PostingList:
        self._flush_term(field, term)
        if field not in self._known_fields:
            return PostingList()
        rows = self._fetchall(
            "SELECT doc_id, positions FROM _postings "
            "WHERE table_name = ? AND field = ? AND term = ? ORDER BY doc_id",
            (self._table_name, field, term),
        )
        entries = [
            PostingEntry(
                doc_id=row[0],
                payload=Payload(
                    positions=self._decode_positions(row[1]),
                    score=0.0,
                ),
            )
            for row in rows
        ]
        return PostingList.from_sorted(entries)

    def get_posting_list_any_field(self, term: str) -> PostingList:
        """Get posting list matching *term* across any field."""
        self.flush_skip_pointers()
        seen_docs: set[int] = set()
        all_entries: list[PostingEntry] = []

        for field in sorted(self._known_fields):
            rows = self._fetchall(
                "SELECT doc_id, positions FROM _postings "
                "WHERE table_name = ? AND field = ? AND term = ? ORDER BY doc_id",
                (self._table_name, field, term),
            )
            for row in rows:
                doc_id = row[0]
                if doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    all_entries.append(
                        PostingEntry(
                            doc_id=doc_id,
                            payload=Payload(
                                positions=self._decode_positions(row[1]),
                                score=0.0,
                            ),
                        )
                    )

        return PostingList(all_entries)

    def doc_freq(self, field: str, term: str) -> int:
        if field not in self._known_fields:
            return 0
        row = self._fetchone(
            "SELECT COUNT(*) FROM _postings "
            "WHERE table_name = ? AND field = ? AND term = ?",
            (self._table_name, field, term),
        )
        return row[0] if row else 0

    def get_doc_length(self, doc_id: DocId, field: FieldName) -> int:
        row = self._fetchone(
            "SELECT length FROM _doc_lengths "
            "WHERE table_name = ? AND doc_id = ? AND field = ?",
            (self._table_name, doc_id, field),
        )
        return row[0] if row else 0

    def get_doc_lengths_bulk(
        self, doc_ids: list[DocId], field: FieldName
    ) -> dict[DocId, int]:
        """Return doc lengths for multiple doc_ids in a single call."""
        result: dict[DocId, int] = dict.fromkeys(doc_ids, 0)
        for chunk_start in range(0, len(doc_ids), 500):
            chunk = doc_ids[chunk_start : chunk_start + 500]
            placeholders = ",".join("?" * len(chunk))
            rows = self._fetchall(
                "SELECT doc_id, length FROM _doc_lengths "
                f"WHERE table_name = ? AND field = ? AND doc_id IN ({placeholders})",
                (self._table_name, field, *chunk),
            )
            for doc_id, length in rows:
                result[doc_id] = length
        return result

    def get_total_doc_length(self, doc_id: DocId) -> int:
        """Get total document length across all fields."""
        row = self._fetchone(
            "SELECT SUM(length) FROM _doc_lengths "
            "WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        return row[0] if row and row[0] is not None else 0

    def get_term_freq(self, doc_id: DocId, field: str, term: str) -> int:
        """Get term frequency for a specific doc in a specific field."""
        if field not in self._known_fields:
            return 0
        row = self._fetchone(
            "SELECT positions FROM _postings "
            "WHERE table_name = ? AND field = ? AND term = ? AND doc_id = ?",
            (self._table_name, field, term, doc_id),
        )
        return len(self._decode_positions(row[0])) if row else 0

    def get_term_freqs_bulk(
        self, doc_ids: list[DocId], field: str, term: str
    ) -> dict[DocId, int]:
        """Return term frequencies for multiple doc_ids in a single call."""
        result: dict[DocId, int] = dict.fromkeys(doc_ids, 0)
        if field not in self._known_fields:
            return result
        for chunk_start in range(0, len(doc_ids), 500):
            chunk = doc_ids[chunk_start : chunk_start + 500]
            placeholders = ",".join("?" * len(chunk))
            rows = self._fetchall(
                "SELECT doc_id, positions FROM _postings "
                f"WHERE table_name = ? AND field = ? AND term = ? "
                f"AND doc_id IN ({placeholders})",
                (self._table_name, field, term, *chunk),
            )
            for doc_id, positions in rows:
                result[doc_id] = len(self._decode_positions(positions))
        return result

    def get_total_term_freq(self, doc_id: DocId, term: str) -> int:
        """Get total term frequency for a doc across all fields."""
        if not self._known_fields:
            return 0
        parts = []
        params: list[Any] = []
        for field in self._known_fields:
            parts.append(
                "SELECT positions FROM _postings "
                "WHERE table_name = ? AND field = ? AND term = ? AND doc_id = ?"
            )
            params.extend([self._table_name, field, term, doc_id])
        sql = " UNION ALL ".join(parts)
        rows = self._fetchall(sql, tuple(params))
        return sum(len(self._decode_positions(r[0])) for r in rows)

    def doc_freq_any_field(self, term: str) -> int:
        """Get document frequency across all fields."""
        if not self._known_fields:
            return 0
        parts = []
        params: list[Any] = []
        for field in self._known_fields:
            parts.append(
                "SELECT DISTINCT doc_id FROM _postings "
                "WHERE table_name = ? AND field = ? AND term = ?"
            )
            params.extend([self._table_name, field, term])
        sql = f"SELECT COUNT(DISTINCT doc_id) FROM ({' UNION ALL '.join(parts)})"
        row = self._fetchone(sql, tuple(params))
        return row[0] if row else 0

    @property
    def stats(self) -> IndexStats:
        self.flush_skip_pointers()

        if self._cached_stats is not None:
            return self._cached_stats

        from uqa.core.types import IndexStats

        rows = self._fetchall(
            "SELECT field, total_length FROM _field_stats WHERE table_name = ?",
            (self._table_name,),
        )

        if not rows:
            return IndexStats(total_docs=0, avg_doc_length=0.0, _doc_freqs={})

        total_docs_row = self._fetchone(
            "SELECT COUNT(DISTINCT doc_id) FROM _doc_lengths WHERE table_name = ?",
            (self._table_name,),
        )
        total_docs = total_docs_row[0] if total_docs_row else 0
        if total_docs == 0:
            compat_row = self._fetchone(
                f'SELECT MAX(doc_count) FROM "_field_stats_{self._table_name}"'
            )
            total_docs = compat_row[0] if compat_row and compat_row[0] else 0
        total_length = sum(r[1] for r in rows)
        avg_doc_length = total_length / total_docs if total_docs > 0 else 0.0

        # Build doc_freqs by scanning every inverted table.
        doc_freqs: dict[tuple[str, str], int] = {}
        term_rows = self._fetchall(
            "SELECT field, term, COUNT(*) FROM _postings "
            "WHERE table_name = ? GROUP BY field, term",
            (self._table_name,),
        )
        for field, term, cnt in term_rows:
            doc_freqs[(field, term)] = cnt

        result = IndexStats(
            total_docs=total_docs,
            avg_doc_length=avg_doc_length,
            _doc_freqs=doc_freqs,
        )
        self._cached_stats = result
        return result

    # -- Skip pointers -------------------------------------------------

    def _rebuild_skip_pointers(self, field: str, term: str) -> None:
        """Rebuild skip entries for a (field, term) pair.

        Stores every ``BLOCK_SIZE``-th doc_id so intersection algorithms
        can forward-seek in O(log N) via the skip table.
        """
        self._ensure_field_table(field)
        skip_tbl = self._skip_table_name(field)

        # Clear old skips for this term.
        self._conn.execute(f'DELETE FROM "{skip_tbl}" WHERE term = ?', (term,))

        # Fetch sorted doc_ids for this term.
        rows = self._fetchall(
            "SELECT doc_id FROM _postings "
            "WHERE table_name = ? AND field = ? AND term = ? ORDER BY doc_id",
            (self._table_name, field, term),
        )

        # Insert skip entries every BLOCK_SIZE docs.
        for offset, (doc_id,) in enumerate(rows):
            if offset % self.BLOCK_SIZE == 0:
                self._conn.execute(
                    f'INSERT INTO "{skip_tbl}" '
                    "(term, skip_doc_id, skip_offset) VALUES (?, ?, ?)",
                    (term, doc_id, offset),
                )

        self._conn.commit()

    def skip_to(self, field: str, term: str, target_doc_id: int) -> tuple[int, int]:
        """Find the nearest skip entry at or before *target_doc_id*.

        Returns ``(skip_doc_id, skip_offset)`` -- the doc_id and its
        0-based offset in the posting list.  If no skip entry exists,
        returns ``(0, 0)`` (start from the beginning).
        """
        self.flush_skip_pointers()
        if field not in self._known_fields:
            return (0, 0)
        skip_tbl = self._skip_table_name(field)
        row = self._fetchone(
            f'SELECT skip_doc_id, skip_offset FROM "{skip_tbl}" '
            "WHERE term = ? AND skip_doc_id <= ? "
            "ORDER BY skip_doc_id DESC LIMIT 1",
            (term, target_doc_id),
        )
        if row is None:
            return (0, 0)
        return (row[0], row[1])

    # -- Block-max scores ----------------------------------------------

    def build_block_max_scores(self, field: str, term: str, scorer: object) -> None:
        """Compute and persist per-block maximum scores for a term.

        ``scorer`` must have a ``score(tf, dl, df)`` method (e.g. BM25Scorer).
        Block-max scores enable BMW (Block-Max WAND) pruning during top-k
        retrieval.
        """
        if field not in self._known_fields:
            return

        self._ensure_field_table(field)
        bm_tbl = self._blockmax_table_name(field)

        # Fetch all entries for this term, sorted by doc_id.
        rows = self._fetchall(
            "SELECT doc_id, positions FROM _postings "
            "WHERE table_name = ? AND field = ? AND term = ? ORDER BY doc_id",
            (self._table_name, field, term),
        )

        doc_freq = len(rows)

        # Clear old block-max entries for this term.
        self._conn.execute(f'DELETE FROM "{bm_tbl}" WHERE term = ?', (term,))

        # Compute per-block maximums.
        for block_start in range(0, len(rows), self.BLOCK_SIZE):
            block_end = min(block_start + self.BLOCK_SIZE, len(rows))
            max_score = 0.0
            for i in range(block_start, block_end):
                doc_id = rows[i][0]
                tf = len(self._decode_positions(rows[i][1]))
                doc_length = max(tf, self.get_doc_length(doc_id, field))
                score = scorer.score(tf, doc_length, doc_freq)  # type: ignore[union-attr]
                max_score = max(max_score, score)
            block_idx = block_start // self.BLOCK_SIZE
            self._conn.execute(
                f'INSERT INTO "{bm_tbl}" (term, block_idx, max_score) VALUES (?, ?, ?)',
                (term, block_idx, max_score),
            )

        self._conn.commit()

    def build_all_block_max_scores(self, field: str, scorer: object) -> None:
        """Compute and persist block-max scores for all terms in a field."""
        if field not in self._known_fields:
            return
        terms = self._fetchall(
            "SELECT DISTINCT term FROM _postings "
            "WHERE table_name = ? AND field = ?",
            (self._table_name, field),
        )
        for (term,) in terms:
            self.build_block_max_scores(field, term, scorer)

    def get_block_max_score(self, field: str, term: str, block_idx: int) -> float:
        """Return the persisted max score for a given block."""
        if field not in self._known_fields:
            return 0.0
        bm_tbl = self._blockmax_table_name(field)
        row = self._fetchone(
            f'SELECT max_score FROM "{bm_tbl}" WHERE term = ? AND block_idx = ?',
            (term, block_idx),
        )
        return row[0] if row else 0.0

    def get_all_block_max_scores(self, field: str, term: str) -> list[float]:
        """Return all block-max scores for a (field, term) pair."""
        if field not in self._known_fields:
            return []
        bm_tbl = self._blockmax_table_name(field)
        rows = self._fetchall(
            f'SELECT max_score FROM "{bm_tbl}" WHERE term = ? ORDER BY block_idx',
            (term,),
        )
        return [r[0] for r in rows]

    def load_block_max_into(self, block_max_index: object) -> None:
        """Load all persisted block-max scores into a BlockMaxIndex."""
        for field in self._known_fields:
            bm_tbl = self._blockmax_table_name(field)
            rows = self._fetchall(
                f'SELECT term, block_idx, max_score FROM "{bm_tbl}" '
                "ORDER BY term, block_idx",
            )

            # Group by term.
            current_term: str | None = None
            scores: list[float] = []
            for term, _block_idx, max_score in rows:
                if term != current_term:
                    if current_term is not None:
                        block_max_index._block_maxes[
                            (self._table_name, field, current_term)
                        ] = scores  # type: ignore[union-attr]
                    current_term = term
                    scores = []
                scores.append(max_score)
            if current_term is not None:
                block_max_index._block_maxes[
                    (self._table_name, field, current_term)
                ] = scores  # type: ignore[union-attr]
