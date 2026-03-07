#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed system catalog with write-through persistence.

Every mutation writes to both in-memory structures and SQLite.
On startup, in-memory structures are rebuilt from SQLite.

SQLite tables:
    _metadata          -- key-value engine configuration
    _catalog_tables    -- table schemas (name, columns JSON)
    _documents         -- documents per table (table_name='': global)
    _graph_vertices    -- graph vertices with properties
    _graph_edges       -- graph edges with label and properties
    _vectors           -- vector embeddings as binary blobs
    _postings          -- inverted index posting entries (Paper 1)
    _doc_lengths       -- per-document per-field token lengths (BM25)
    _column_stats      -- ANALYZE results for query optimizer
    _scoring_params    -- Bayesian calibration parameters (Papers 3-4)
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import numpy as np
from numpy.typing import NDArray


class Catalog:
    """SQLite-backed system catalog for persistent storage."""

    _SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS _metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _catalog_tables (
    name         TEXT PRIMARY KEY,
    columns_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _documents (
    table_name TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    data_json  TEXT    NOT NULL,
    PRIMARY KEY (table_name, doc_id)
);
CREATE TABLE IF NOT EXISTS _graph_vertices (
    vertex_id       INTEGER PRIMARY KEY,
    properties_json TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS _graph_edges (
    edge_id         INTEGER PRIMARY KEY,
    source_id       INTEGER NOT NULL,
    target_id       INTEGER NOT NULL,
    label           TEXT    NOT NULL,
    properties_json TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS _vectors (
    doc_id     INTEGER PRIMARY KEY,
    dimensions INTEGER NOT NULL,
    embedding  BLOB    NOT NULL
);
CREATE TABLE IF NOT EXISTS _postings (
    table_name TEXT    NOT NULL,
    field      TEXT    NOT NULL,
    term       TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    positions  TEXT    NOT NULL,
    PRIMARY KEY (table_name, field, term, doc_id)
);
CREATE TABLE IF NOT EXISTS _doc_lengths (
    table_name TEXT NOT NULL,
    doc_id     INTEGER NOT NULL,
    lengths    TEXT NOT NULL,
    PRIMARY KEY (table_name, doc_id)
);
CREATE TABLE IF NOT EXISTS _column_stats (
    table_name     TEXT    NOT NULL,
    column_name    TEXT    NOT NULL,
    distinct_count INTEGER NOT NULL DEFAULT 0,
    null_count     INTEGER NOT NULL DEFAULT 0,
    min_value      TEXT,
    max_value      TEXT,
    row_count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (table_name, column_name)
);
CREATE TABLE IF NOT EXISTS _scoring_params (
    name        TEXT PRIMARY KEY,
    params_json TEXT NOT NULL
);
"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(self._SCHEMA_SQL)
        self._conn.commit()
        self._in_transaction = False

    # -- Transaction management ----------------------------------------

    def begin(self) -> None:
        """Begin an explicit transaction.

        While active, individual writes do not auto-commit.
        Call ``commit()`` or ``rollback()`` to end the transaction.
        """
        self._in_transaction = True

    def commit(self) -> None:
        """Commit the current transaction."""
        self._conn.commit()
        self._in_transaction = False

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._conn.rollback()
        self._in_transaction = False

    def _auto_commit(self) -> None:
        """Commit unless inside an explicit transaction."""
        if not self._in_transaction:
            self._conn.commit()

    # -- Metadata ------------------------------------------------------

    def set_metadata(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._auto_commit()

    def get_metadata(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM _metadata WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    # -- Table schemas -------------------------------------------------

    def save_table_schema(
        self, name: str, columns: list[dict[str, Any]]
    ) -> None:
        """Persist a table schema.

        ``columns`` is a list of dicts with keys: name, type_name,
        primary_key, not_null, auto_increment, default.
        """
        self._conn.execute(
            "INSERT INTO _catalog_tables (name, columns_json) VALUES (?, ?)",
            (name, json.dumps(columns)),
        )
        self._auto_commit()

    def drop_table_schema(self, name: str) -> None:
        """Remove a table schema and all associated data."""
        self._conn.execute(
            "DELETE FROM _catalog_tables WHERE name = ?", (name,)
        )
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ?", (name,)
        )
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ?", (name,)
        )
        self._conn.execute(
            "DELETE FROM _doc_lengths WHERE table_name = ?", (name,)
        )
        self._conn.execute(
            "DELETE FROM _column_stats WHERE table_name = ?", (name,)
        )
        self._auto_commit()

    def load_table_schemas(self) -> list[tuple[str, list[dict[str, Any]]]]:
        """Return ``[(table_name, [column_dict, ...]), ...]``."""
        rows = self._conn.execute(
            "SELECT name, columns_json FROM _catalog_tables"
        ).fetchall()
        return [
            (name, json.loads(columns_json))
            for name, columns_json in rows
        ]

    # -- Documents -----------------------------------------------------

    def save_document(
        self, table_name: str, doc_id: int, data: dict[str, Any]
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _documents "
            "(table_name, doc_id, data_json) VALUES (?, ?, ?)",
            (table_name, doc_id, json.dumps(data)),
        )
        self._auto_commit()

    def delete_document(self, table_name: str, doc_id: int) -> None:
        """Delete a document and its associated postings and doc lengths."""
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _doc_lengths WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._auto_commit()

    def load_documents(
        self, table_name: str
    ) -> list[tuple[int, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT doc_id, data_json FROM _documents WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (doc_id, json.loads(data_json))
            for doc_id, data_json in rows
        ]

    # -- Postings (inverted index entries) -----------------------------

    def save_postings(
        self,
        table_name: str,
        doc_id: int,
        field_lengths: dict[str, int],
        postings: dict[tuple[str, str], tuple[int, ...]],
    ) -> None:
        """Persist posting entries and per-field token lengths for one doc."""
        for (field, term), positions in postings.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO _postings "
                "(table_name, field, term, doc_id, positions) "
                "VALUES (?, ?, ?, ?, ?)",
                (table_name, field, term, doc_id, json.dumps(list(positions))),
            )
        self._conn.execute(
            "INSERT OR REPLACE INTO _doc_lengths "
            "(table_name, doc_id, lengths) VALUES (?, ?, ?)",
            (table_name, doc_id, json.dumps(field_lengths)),
        )
        self._auto_commit()

    def delete_postings(self, table_name: str, doc_id: int) -> None:
        """Remove all postings and doc lengths for one document."""
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _doc_lengths WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._auto_commit()

    def load_postings(
        self, table_name: str
    ) -> list[tuple[str, str, int, tuple[int, ...]]]:
        """Load all posting entries for a table.

        Returns ``[(field, term, doc_id, positions), ...]``.
        """
        rows = self._conn.execute(
            "SELECT field, term, doc_id, positions FROM _postings "
            "WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (field, term, doc_id, tuple(json.loads(positions)))
            for field, term, doc_id, positions in rows
        ]

    def load_doc_lengths(
        self, table_name: str
    ) -> list[tuple[int, dict[str, int]]]:
        """Load per-document per-field token lengths.

        Returns ``[(doc_id, {field: length, ...}), ...]``.
        """
        rows = self._conn.execute(
            "SELECT doc_id, lengths FROM _doc_lengths WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (doc_id, json.loads(lengths))
            for doc_id, lengths in rows
        ]

    # -- Graph vertices ------------------------------------------------

    def save_vertex(self, vertex_id: int, properties: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _graph_vertices "
            "(vertex_id, properties_json) VALUES (?, ?)",
            (vertex_id, json.dumps(properties)),
        )
        self._auto_commit()

    def save_edge(
        self,
        edge_id: int,
        source_id: int,
        target_id: int,
        label: str,
        properties: dict[str, Any],
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _graph_edges "
            "(edge_id, source_id, target_id, label, properties_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (edge_id, source_id, target_id, label, json.dumps(properties)),
        )
        self._auto_commit()

    def load_vertices(self) -> list[tuple[int, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT vertex_id, properties_json FROM _graph_vertices"
        ).fetchall()
        return [
            (vertex_id, json.loads(props))
            for vertex_id, props in rows
        ]

    def load_edges(
        self,
    ) -> list[tuple[int, int, int, str, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT edge_id, source_id, target_id, label, properties_json "
            "FROM _graph_edges"
        ).fetchall()
        return [
            (eid, src, dst, label, json.loads(props))
            for eid, src, dst, label, props in rows
        ]

    # -- Vectors -------------------------------------------------------

    def save_vector(self, doc_id: int, embedding: NDArray) -> None:
        blob = embedding.astype(np.float32).tobytes()
        self._conn.execute(
            "INSERT OR REPLACE INTO _vectors "
            "(doc_id, dimensions, embedding) VALUES (?, ?, ?)",
            (doc_id, len(embedding), blob),
        )
        self._auto_commit()

    def delete_vector(self, doc_id: int) -> None:
        self._conn.execute(
            "DELETE FROM _vectors WHERE doc_id = ?", (doc_id,)
        )
        self._auto_commit()

    def load_vectors(self) -> list[tuple[int, NDArray]]:
        rows = self._conn.execute(
            "SELECT doc_id, dimensions, embedding FROM _vectors"
        ).fetchall()
        result: list[tuple[int, NDArray]] = []
        for doc_id, dims, blob in rows:
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            result.append((doc_id, vec))
        return result

    # -- Column statistics (ANALYZE results) ---------------------------

    def save_column_stats(
        self,
        table_name: str,
        column_name: str,
        distinct_count: int,
        null_count: int,
        min_value: Any,
        max_value: Any,
        row_count: int,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _column_stats "
            "(table_name, column_name, distinct_count, null_count, "
            "min_value, max_value, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                table_name,
                column_name,
                distinct_count,
                null_count,
                json.dumps(min_value),
                json.dumps(max_value),
                row_count,
            ),
        )
        self._auto_commit()

    def load_column_stats(
        self, table_name: str
    ) -> list[tuple[str, int, int, Any, Any, int]]:
        """Return ``[(column_name, distinct, nulls, min, max, rows), ...]``."""
        rows = self._conn.execute(
            "SELECT column_name, distinct_count, null_count, "
            "min_value, max_value, row_count "
            "FROM _column_stats WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (col, dc, nc, json.loads(mn), json.loads(mx), rc)
            for col, dc, nc, mn, mx, rc in rows
        ]

    def delete_column_stats(self, table_name: str) -> None:
        self._conn.execute(
            "DELETE FROM _column_stats WHERE table_name = ?", (table_name,)
        )
        self._auto_commit()

    # -- Scoring / calibration parameters (Papers 3-4) -----------------

    def save_scoring_params(
        self, name: str, params: dict[str, Any]
    ) -> None:
        """Persist Bayesian calibration parameters for a named signal."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _scoring_params "
            "(name, params_json) VALUES (?, ?)",
            (name, json.dumps(params)),
        )
        self._auto_commit()

    def load_scoring_params(self, name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT params_json FROM _scoring_params WHERE name = ?",
            (name,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_all_scoring_params(self) -> list[tuple[str, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT name, params_json FROM _scoring_params"
        ).fetchall()
        return [(name, json.loads(pjson)) for name, pjson in rows]

    def delete_scoring_params(self, name: str) -> None:
        self._conn.execute(
            "DELETE FROM _scoring_params WHERE name = ?", (name,)
        )
        self._auto_commit()

    # -- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._conn.close()
