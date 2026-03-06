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
"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(self._SCHEMA_SQL)
        self._conn.commit()

    # -- Metadata ------------------------------------------------------

    def set_metadata(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

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
        self._conn.commit()

    def drop_table_schema(self, name: str) -> None:
        self._conn.execute(
            "DELETE FROM _catalog_tables WHERE name = ?", (name,)
        )
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ?", (name,)
        )
        self._conn.commit()

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
        self._conn.commit()

    def delete_document(self, table_name: str, doc_id: int) -> None:
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._conn.commit()

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

    # -- Graph vertices ------------------------------------------------

    def save_vertex(self, vertex_id: int, properties: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _graph_vertices "
            "(vertex_id, properties_json) VALUES (?, ?)",
            (vertex_id, json.dumps(properties)),
        )
        self._conn.commit()

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
        self._conn.commit()

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
        self._conn.commit()

    def load_vectors(self) -> list[tuple[int, NDArray]]:
        rows = self._conn.execute(
            "SELECT doc_id, dimensions, embedding FROM _vectors"
        ).fetchall()
        result: list[tuple[int, NDArray]] = []
        for doc_id, dims, blob in rows:
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            result.append((doc_id, vec))
        return result

    # -- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._conn.close()
