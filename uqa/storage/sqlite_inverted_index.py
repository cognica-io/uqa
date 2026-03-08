#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed inverted index -- drop-in replacement for InvertedIndex.

Each (table_name, field_name) pair maps to its own SQLite table for postings.
Per-document field lengths and per-field aggregate statistics are stored in
additional shared tables scoped by table_name.

Performance structures (Phase 2, Section 3.2.2):
    Skip pointers -- every Nth doc_id per term for fast forward-seeking
        during posting list intersection.  Table: _skip_{table}_{field}.
    Block-max scores -- per-block maximum BM25 scores for BMW pruning.
        Table: _blockmax_{table}_{field}.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.storage.inverted_index import IndexedTerms

if TYPE_CHECKING:
    from uqa.core.types import DocId, FieldName, IndexStats


class SQLiteInvertedIndex:
    """Term-to-posting-list mapping backed by SQLite.

    Public API is identical to ``InvertedIndex`` so that this class can
    serve as a transparent, persistent drop-in replacement.
    """

    BLOCK_SIZE = 128

    def __init__(self, conn: sqlite3.Connection, table_name: str) -> None:
        self._conn = conn
        self._table_name = table_name
        self._known_fields: set[str] = set()

        # Create shared stats / doc-lengths tables eagerly.
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "_field_stats_{table_name}" ('
            "    field        TEXT PRIMARY KEY,"
            "    doc_count    INTEGER NOT NULL DEFAULT 0,"
            "    total_length INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "_doc_lengths_{table_name}" ('
            "    doc_id  INTEGER NOT NULL,"
            "    field   TEXT    NOT NULL,"
            "    length  INTEGER NOT NULL,"
            "    PRIMARY KEY (doc_id, field)"
            ")"
        )
        self._conn.commit()

        # Discover fields that already have inverted tables from a
        # previous session so we do not attempt to re-create them.
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE ?",
            (f"_inverted_{table_name}_%",),
        ).fetchall()
        prefix = f"_inverted_{table_name}_"
        for (name,) in rows:
            field = name[len(prefix):]
            self._known_fields.add(field)

    # -- Lazy table creation -------------------------------------------

    def _ensure_field_table(self, field: str) -> None:
        """Create the per-field inverted, skip, and block-max tables."""
        if field in self._known_fields:
            return
        tbl = self._inverted_table_name(field)
        skip_tbl = self._skip_table_name(field)
        bm_tbl = self._blockmax_table_name(field)
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{tbl}" ('
            "    term    TEXT    NOT NULL,"
            "    doc_id  INTEGER NOT NULL,"
            "    tf      INTEGER NOT NULL,"
            "    positions TEXT  NOT NULL,"
            "    PRIMARY KEY (term, doc_id)"
            ")"
        )
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

    # -- Tokenization --------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase and split on whitespace (matches InvertedIndex)."""
        return text.lower().split()

    # -- Indexing -------------------------------------------------------

    def add_document(
        self, doc_id: DocId, fields: dict[FieldName, str]
    ) -> IndexedTerms:
        """Index a document by tokenizing each field.

        Returns an ``IndexedTerms`` with per-field lengths and posting
        data so the caller can persist them without re-tokenizing.
        """
        result_field_lengths: dict[str, int] = {}
        result_postings: dict[tuple[str, str], tuple[int, ...]] = {}

        for field_name, text in fields.items():
            self._ensure_field_table(field_name)
            tbl = self._inverted_table_name(field_name)

            tokens = self._tokenize(text)
            length = len(tokens)
            result_field_lengths[field_name] = length

            # Build position index for each token.
            term_positions: dict[str, list[int]] = defaultdict(list)
            for pos, token in enumerate(tokens):
                term_positions[token].append(pos)

            for term, positions in term_positions.items():
                pos_tuple = tuple(positions)
                tf = len(positions)
                self._conn.execute(
                    f'INSERT OR REPLACE INTO "{tbl}" '
                    "(term, doc_id, tf, positions) VALUES (?, ?, ?, ?)",
                    (term, doc_id, tf, json.dumps(list(pos_tuple))),
                )
                result_postings[(field_name, term)] = pos_tuple

            # Doc length
            self._conn.execute(
                f'INSERT OR REPLACE INTO "_doc_lengths_{self._table_name}" '
                "(doc_id, field, length) VALUES (?, ?, ?)",
                (doc_id, field_name, length),
            )

            # Field stats -- upsert doc_count and total_length.
            self._conn.execute(
                f'INSERT INTO "_field_stats_{self._table_name}" '
                "(field, doc_count, total_length) VALUES (?, 1, ?) "
                "ON CONFLICT(field) DO UPDATE SET "
                "doc_count = doc_count + 1, "
                "total_length = total_length + ?",
                (field_name, length, length),
            )

        self._conn.commit()

        # Rebuild skip pointers for all affected (field, term) pairs.
        for (field_name, term) in result_postings:
            self._rebuild_skip_pointers(field_name, term)

        return IndexedTerms(result_field_lengths, result_postings)

    # -- Restore methods (backward compatibility during migration) ------

    def add_posting(
        self, field: str, term: str, entry: PostingEntry
    ) -> None:
        """Add a single posting entry directly (for catalog restore)."""
        self._ensure_field_table(field)
        tbl = self._inverted_table_name(field)
        positions = list(entry.payload.positions) if entry.payload.positions else []
        tf = len(positions)
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{tbl}" '
            "(term, doc_id, tf, positions) VALUES (?, ?, ?, ?)",
            (term, entry.doc_id, tf, json.dumps(positions)),
        )
        self._conn.commit()

    def set_doc_length(
        self, doc_id: DocId, lengths: dict[FieldName, int]
    ) -> None:
        """Set per-field token lengths for a document (for catalog restore)."""
        for field, length in lengths.items():
            self._conn.execute(
                f'INSERT OR REPLACE INTO "_doc_lengths_{self._table_name}" '
                "(doc_id, field, length) VALUES (?, ?, ?)",
                (doc_id, field, length),
            )
        self._conn.commit()

    def set_doc_count(self, count: int) -> None:
        """Set the indexed document count (for catalog restore).

        Applies the given count to every known field in the stats table.
        If no rows exist yet, this is a no-op (the caller is expected to
        call ``add_total_length`` first to create the rows).
        """
        self._conn.execute(
            f'UPDATE "_field_stats_{self._table_name}" '
            "SET doc_count = ?",
            (count,),
        )
        self._conn.commit()

    def add_total_length(self, field: FieldName, length: int) -> None:
        """Accumulate total token length for a field (for catalog restore)."""
        self._conn.execute(
            f'INSERT INTO "_field_stats_{self._table_name}" '
            "(field, doc_count, total_length) VALUES (?, 0, ?) "
            "ON CONFLICT(field) DO UPDATE SET "
            "total_length = total_length + ?",
            (field, length, length),
        )
        self._conn.commit()

    # -- Remove --------------------------------------------------------

    def remove_document(self, doc_id: DocId) -> None:
        """Remove all entries for a document from the index."""
        # Collect per-field lengths so we can decrement field stats.
        rows = self._conn.execute(
            f'SELECT field, length FROM "_doc_lengths_{self._table_name}" '
            "WHERE doc_id = ?",
            (doc_id,),
        ).fetchall()

        # Collect affected (field, term) pairs for skip pointer rebuild.
        affected_terms: list[tuple[str, str]] = []
        for field in self._known_fields:
            tbl = self._inverted_table_name(field)
            term_rows = self._conn.execute(
                f'SELECT term FROM "{tbl}" WHERE doc_id = ?',
                (doc_id,),
            ).fetchall()
            for (term,) in term_rows:
                affected_terms.append((field, term))

            self._conn.execute(
                f'DELETE FROM "{tbl}" WHERE doc_id = ?',
                (doc_id,),
            )

        if rows:
            for field, length in rows:
                self._conn.execute(
                    f'UPDATE "_field_stats_{self._table_name}" '
                    "SET doc_count = MAX(doc_count - 1, 0), "
                    "total_length = MAX(total_length - ?, 0) "
                    "WHERE field = ?",
                    (length, field),
                )
            self._conn.execute(
                f'DELETE FROM "_doc_lengths_{self._table_name}" '
                "WHERE doc_id = ?",
                (doc_id,),
            )

        self._conn.commit()

        # Rebuild skip pointers for affected terms.
        for field, term in affected_terms:
            self._rebuild_skip_pointers(field, term)

    # -- Query methods -------------------------------------------------

    def get_posting_list(self, field: str, term: str) -> PostingList:
        if field not in self._known_fields:
            return PostingList()
        tbl = self._inverted_table_name(field)
        rows = self._conn.execute(
            f'SELECT doc_id, tf, positions FROM "{tbl}" '
            "WHERE term = ? ORDER BY doc_id",
            (term,),
        ).fetchall()
        entries = [
            PostingEntry(
                doc_id=row[0],
                payload=Payload(
                    positions=tuple(json.loads(row[2])),
                    score=0.0,
                ),
            )
            for row in rows
        ]
        return PostingList(entries)

    def get_posting_list_any_field(self, term: str) -> PostingList:
        """Get posting list matching *term* across any field."""
        seen_docs: set[int] = set()
        all_entries: list[PostingEntry] = []

        for field in sorted(self._known_fields):
            tbl = self._inverted_table_name(field)
            rows = self._conn.execute(
                f'SELECT doc_id, tf, positions FROM "{tbl}" '
                "WHERE term = ? ORDER BY doc_id",
                (term,),
            ).fetchall()
            for row in rows:
                doc_id = row[0]
                if doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    all_entries.append(
                        PostingEntry(
                            doc_id=doc_id,
                            payload=Payload(
                                positions=tuple(json.loads(row[2])),
                                score=0.0,
                            ),
                        )
                    )

        return PostingList(all_entries)

    def doc_freq(self, field: str, term: str) -> int:
        if field not in self._known_fields:
            return 0
        tbl = self._inverted_table_name(field)
        row = self._conn.execute(
            f'SELECT COUNT(*) FROM "{tbl}" WHERE term = ?',
            (term,),
        ).fetchone()
        return row[0] if row else 0

    def get_doc_length(self, doc_id: DocId, field: FieldName) -> int:
        row = self._conn.execute(
            f'SELECT length FROM "_doc_lengths_{self._table_name}" '
            "WHERE doc_id = ? AND field = ?",
            (doc_id, field),
        ).fetchone()
        return row[0] if row else 0

    def get_total_doc_length(self, doc_id: DocId) -> int:
        """Get total document length across all fields."""
        row = self._conn.execute(
            f'SELECT SUM(length) FROM "_doc_lengths_{self._table_name}" '
            "WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        return row[0] if row and row[0] is not None else 0

    def get_term_freq(self, doc_id: DocId, field: str, term: str) -> int:
        """Get term frequency for a specific doc in a specific field."""
        if field not in self._known_fields:
            return 0
        tbl = self._inverted_table_name(field)
        row = self._conn.execute(
            f'SELECT tf FROM "{tbl}" WHERE term = ? AND doc_id = ?',
            (term, doc_id),
        ).fetchone()
        return row[0] if row else 0

    def get_total_term_freq(self, doc_id: DocId, term: str) -> int:
        """Get total term frequency for a doc across all fields."""
        total = 0
        for field in self._known_fields:
            tbl = self._inverted_table_name(field)
            row = self._conn.execute(
                f'SELECT tf FROM "{tbl}" WHERE term = ? AND doc_id = ?',
                (term, doc_id),
            ).fetchone()
            if row:
                total += row[0]
        return total

    def doc_freq_any_field(self, term: str) -> int:
        """Get document frequency across all fields."""
        doc_ids: set[int] = set()
        for field in self._known_fields:
            tbl = self._inverted_table_name(field)
            rows = self._conn.execute(
                f'SELECT doc_id FROM "{tbl}" WHERE term = ?',
                (term,),
            ).fetchall()
            for (did,) in rows:
                doc_ids.add(did)
        return len(doc_ids)

    @property
    def stats(self) -> IndexStats:
        from uqa.core.types import IndexStats

        rows = self._conn.execute(
            f'SELECT field, doc_count, total_length '
            f'FROM "_field_stats_{self._table_name}"'
        ).fetchall()

        if not rows:
            return IndexStats(total_docs=0, avg_doc_length=0.0, _doc_freqs={})

        # doc_count: maximum across fields (a single add_document increments
        # each field individually, so the max is the actual document count).
        total_docs = max(r[1] for r in rows)
        total_length = sum(r[2] for r in rows)
        avg_doc_length = total_length / total_docs if total_docs > 0 else 0.0

        # Build doc_freqs by scanning every inverted table.
        doc_freqs: dict[tuple[str, str], int] = {}
        for field in self._known_fields:
            tbl = self._inverted_table_name(field)
            term_rows = self._conn.execute(
                f'SELECT term, COUNT(*) FROM "{tbl}" GROUP BY term'
            ).fetchall()
            for term, cnt in term_rows:
                doc_freqs[(field, term)] = cnt

        return IndexStats(
            total_docs=total_docs,
            avg_doc_length=avg_doc_length,
            _doc_freqs=doc_freqs,
        )

    # -- Skip pointers -------------------------------------------------

    def _rebuild_skip_pointers(self, field: str, term: str) -> None:
        """Rebuild skip entries for a (field, term) pair.

        Stores every ``BLOCK_SIZE``-th doc_id so intersection algorithms
        can forward-seek in O(log N) via the skip table.
        """
        skip_tbl = self._skip_table_name(field)
        inv_tbl = self._inverted_table_name(field)

        # Clear old skips for this term.
        self._conn.execute(
            f'DELETE FROM "{skip_tbl}" WHERE term = ?', (term,)
        )

        # Fetch sorted doc_ids for this term.
        rows = self._conn.execute(
            f'SELECT doc_id FROM "{inv_tbl}" '
            "WHERE term = ? ORDER BY doc_id",
            (term,),
        ).fetchall()

        # Insert skip entries every BLOCK_SIZE docs.
        for offset, (doc_id,) in enumerate(rows):
            if offset % self.BLOCK_SIZE == 0:
                self._conn.execute(
                    f'INSERT INTO "{skip_tbl}" '
                    "(term, skip_doc_id, skip_offset) VALUES (?, ?, ?)",
                    (term, doc_id, offset),
                )

        self._conn.commit()

    def skip_to(
        self, field: str, term: str, target_doc_id: int
    ) -> tuple[int, int]:
        """Find the nearest skip entry at or before *target_doc_id*.

        Returns ``(skip_doc_id, skip_offset)`` -- the doc_id and its
        0-based offset in the posting list.  If no skip entry exists,
        returns ``(0, 0)`` (start from the beginning).
        """
        if field not in self._known_fields:
            return (0, 0)
        skip_tbl = self._skip_table_name(field)
        row = self._conn.execute(
            f'SELECT skip_doc_id, skip_offset FROM "{skip_tbl}" '
            "WHERE term = ? AND skip_doc_id <= ? "
            "ORDER BY skip_doc_id DESC LIMIT 1",
            (term, target_doc_id),
        ).fetchone()
        if row is None:
            return (0, 0)
        return (row[0], row[1])

    # -- Block-max scores ----------------------------------------------

    def build_block_max_scores(
        self, field: str, term: str, scorer: object
    ) -> None:
        """Compute and persist per-block maximum scores for a term.

        ``scorer`` must have a ``score(tf, dl, df)`` method (e.g. BM25Scorer).
        Block-max scores enable BMW (Block-Max WAND) pruning during top-k
        retrieval.
        """
        if field not in self._known_fields:
            return

        inv_tbl = self._inverted_table_name(field)
        bm_tbl = self._blockmax_table_name(field)

        # Fetch all entries for this term, sorted by doc_id.
        rows = self._conn.execute(
            f'SELECT doc_id, tf FROM "{inv_tbl}" '
            "WHERE term = ? ORDER BY doc_id",
            (term,),
        ).fetchall()

        doc_freq = len(rows)

        # Clear old block-max entries for this term.
        self._conn.execute(
            f'DELETE FROM "{bm_tbl}" WHERE term = ?', (term,)
        )

        # Compute per-block maximums.
        for block_start in range(0, len(rows), self.BLOCK_SIZE):
            block_end = min(block_start + self.BLOCK_SIZE, len(rows))
            max_score = 0.0
            for i in range(block_start, block_end):
                tf = rows[i][1]
                score = scorer.score(tf, tf, doc_freq)  # type: ignore[union-attr]
                max_score = max(max_score, score)
            block_idx = block_start // self.BLOCK_SIZE
            self._conn.execute(
                f'INSERT INTO "{bm_tbl}" '
                "(term, block_idx, max_score) VALUES (?, ?, ?)",
                (term, block_idx, max_score),
            )

        self._conn.commit()

    def build_all_block_max_scores(self, field: str, scorer: object) -> None:
        """Compute and persist block-max scores for all terms in a field."""
        if field not in self._known_fields:
            return
        inv_tbl = self._inverted_table_name(field)
        terms = self._conn.execute(
            f'SELECT DISTINCT term FROM "{inv_tbl}"'
        ).fetchall()
        for (term,) in terms:
            self.build_block_max_scores(field, term, scorer)

    def get_block_max_score(
        self, field: str, term: str, block_idx: int
    ) -> float:
        """Return the persisted max score for a given block."""
        if field not in self._known_fields:
            return 0.0
        bm_tbl = self._blockmax_table_name(field)
        row = self._conn.execute(
            f'SELECT max_score FROM "{bm_tbl}" '
            "WHERE term = ? AND block_idx = ?",
            (term, block_idx),
        ).fetchone()
        return row[0] if row else 0.0

    def get_all_block_max_scores(
        self, field: str, term: str
    ) -> list[float]:
        """Return all block-max scores for a (field, term) pair."""
        if field not in self._known_fields:
            return []
        bm_tbl = self._blockmax_table_name(field)
        rows = self._conn.execute(
            f'SELECT max_score FROM "{bm_tbl}" '
            "WHERE term = ? ORDER BY block_idx",
            (term,),
        ).fetchall()
        return [r[0] for r in rows]

    def load_block_max_into(self, block_max_index: object) -> None:
        """Load all persisted block-max scores into a BlockMaxIndex."""
        for field in self._known_fields:
            bm_tbl = self._blockmax_table_name(field)
            rows = self._conn.execute(
                f'SELECT term, block_idx, max_score FROM "{bm_tbl}" '
                "ORDER BY term, block_idx"
            ).fetchall()

            # Group by term.
            current_term: str | None = None
            scores: list[float] = []
            for term, block_idx, max_score in rows:
                if term != current_term:
                    if current_term is not None:
                        block_max_index._block_maxes[(self._table_name, field, current_term)] = scores  # type: ignore[union-attr]
                    current_term = term
                    scores = []
                scores.append(max_score)
            if current_term is not None:
                block_max_index._block_maxes[(self._table_name, field, current_term)] = scores  # type: ignore[union-attr]
