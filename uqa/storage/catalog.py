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
from typing import TYPE_CHECKING, Any

import numpy as np

from uqa.storage.managed_connection import ManagedConnection

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.storage.managed_connection import SQLiteConnection


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
    label           TEXT    NOT NULL DEFAULT '',
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
    table_name      TEXT    NOT NULL,
    column_name     TEXT    NOT NULL,
    distinct_count  INTEGER NOT NULL DEFAULT 0,
    null_count      INTEGER NOT NULL DEFAULT 0,
    min_value       TEXT,
    max_value       TEXT,
    row_count       INTEGER NOT NULL DEFAULT 0,
    histogram       TEXT    NOT NULL DEFAULT '[]',
    mcv_values      TEXT    NOT NULL DEFAULT '[]',
    mcv_frequencies TEXT    NOT NULL DEFAULT '[]',
    PRIMARY KEY (table_name, column_name)
);
CREATE TABLE IF NOT EXISTS _scoring_params (
    name        TEXT PRIMARY KEY,
    params_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _catalog_indexes (
    name       TEXT PRIMARY KEY,
    index_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    columns    TEXT NOT NULL,
    parameters TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _named_graphs (
    name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS _analyzers (
    name        TEXT PRIMARY KEY,
    config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _foreign_servers (
    name     TEXT PRIMARY KEY,
    fdw_type TEXT NOT NULL,
    options  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _foreign_tables (
    name         TEXT PRIMARY KEY,
    server_name  TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    options      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _table_field_analyzers (
    table_name    TEXT NOT NULL,
    field         TEXT NOT NULL,
    phase         TEXT NOT NULL,
    analyzer_name TEXT NOT NULL,
    PRIMARY KEY (table_name, field, phase)
);
CREATE TABLE IF NOT EXISTS _path_indexes (
    graph_name       TEXT PRIMARY KEY,
    label_sequences  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS _graph_vertices_label ON _graph_vertices (label);
CREATE INDEX IF NOT EXISTS _graph_edges_out ON _graph_edges (source_id, label);
CREATE INDEX IF NOT EXISTS _graph_edges_in ON _graph_edges (target_id, label);
CREATE INDEX IF NOT EXISTS _graph_edges_label ON _graph_edges (label);
"""

    def __init__(self, db_path: str) -> None:
        raw = sqlite3.connect(db_path, check_same_thread=False)
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA foreign_keys=ON")
        raw.execute("PRAGMA synchronous=NORMAL")
        raw.execute("PRAGMA cache_size=-8000")
        raw.execute("PRAGMA temp_store=MEMORY")
        raw.execute("PRAGMA mmap_size=268435456")
        raw.executescript(self._SCHEMA_SQL)
        self._migrate_column_stats(raw)
        self._migrate_table_field_analyzers(raw)
        raw.commit()
        self._conn = ManagedConnection(raw)
        self._in_transaction = False

    @staticmethod
    def _migrate_column_stats(conn: SQLiteConnection) -> None:
        """Add histogram/MCV columns to _column_stats if missing."""
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(_column_stats)").fetchall()
        }
        for col, default in [
            ("histogram", "'[]'"),
            ("mcv_values", "'[]'"),
            ("mcv_frequencies", "'[]'"),
        ]:
            if col not in cols:
                conn.execute(
                    f"ALTER TABLE _column_stats "
                    f"ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}"
                )

    @staticmethod
    def _migrate_table_field_analyzers(conn: SQLiteConnection) -> None:
        """Create _table_field_analyzers table if missing (for existing DBs)."""
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "_table_field_analyzers" not in tables:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _table_field_analyzers ("
                "    table_name    TEXT NOT NULL,"
                "    field         TEXT NOT NULL,"
                "    phase         TEXT NOT NULL,"
                "    analyzer_name TEXT NOT NULL,"
                "    PRIMARY KEY (table_name, field, phase)"
                ")"
            )

    @property
    def conn(self) -> ManagedConnection:
        """The managed connection (shared with per-table stores)."""
        return self._conn

    # -- Transaction management ----------------------------------------

    def begin(self) -> None:
        """Begin an internal batch transaction.

        While active, individual writes do not auto-commit.
        Call ``commit()`` or ``rollback()`` to end the batch.

        Note: this is for internal batching (e.g. ``add_document``).
        User-level transactions use :class:`Transaction` via
        ``Engine.begin()``.
        """
        self._in_transaction = True

    def commit(self) -> None:
        """Commit the current internal batch."""
        self._conn.commit()
        self._in_transaction = False

    def rollback(self) -> None:
        """Rollback the current internal batch."""
        self._conn.rollback()
        self._in_transaction = False

    def _auto_commit(self) -> None:
        """Commit unless inside an internal batch."""
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

    def save_table_schema(self, name: str, columns: list[dict[str, Any]]) -> None:
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
        """Remove a table schema and all associated data.

        Drops both per-table SQLite tables (new format) and rows in
        shared catalog tables (old format) for backward compatibility.
        """
        self._conn.execute("DELETE FROM _catalog_tables WHERE name = ?", (name,))

        # -- Drop per-table SQLite tables (new format) ---
        self._conn.execute(f'DROP TABLE IF EXISTS "_data_{name}"')
        self._conn.execute(f'DROP TABLE IF EXISTS "_field_stats_{name}"')
        self._conn.execute(f'DROP TABLE IF EXISTS "_doc_lengths_{name}"')

        # -- Drop per-table graph tables ---
        self._conn.execute(f'DROP TABLE IF EXISTS "_graph_vertices_{name}"')
        self._conn.execute(f'DROP TABLE IF EXISTS "_graph_edges_{name}"')

        # Drop all per-field inverted, skip, block-max, and IVF tables
        for prefix in (
            f"_inverted_{name}_",
            f"_skip_{name}_",
            f"_blockmax_{name}_",
            f"_ivf_centroids_{name}_",
            f"_ivf_lists_{name}_",
        ):
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
                (prefix + "%",),
            ).fetchall()
            for (tbl_name,) in rows:
                self._conn.execute(f'DROP TABLE IF EXISTS "{tbl_name}"')

        # -- Drop index catalog entries for this table ---
        self._conn.execute("DELETE FROM _catalog_indexes WHERE table_name = ?", (name,))

        # -- Clean shared catalog tables (old format / backward compat) ---
        self._conn.execute("DELETE FROM _documents WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _postings WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _doc_lengths WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _column_stats WHERE table_name = ?", (name,))
        self._conn.execute(
            "DELETE FROM _table_field_analyzers WHERE table_name = ?", (name,)
        )
        self._auto_commit()

    def load_table_schemas(self) -> list[tuple[str, list[dict[str, Any]]]]:
        """Return ``[(table_name, [column_dict, ...]), ...]``."""
        rows = self._conn.execute(
            "SELECT name, columns_json FROM _catalog_tables"
        ).fetchall()
        return [(name, json.loads(columns_json)) for name, columns_json in rows]

    # -- Documents -----------------------------------------------------

    def save_document(self, table_name: str, doc_id: int, data: dict[str, Any]) -> None:
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

    def load_documents(self, table_name: str) -> list[tuple[int, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT doc_id, data_json FROM _documents WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [(doc_id, json.loads(data_json)) for doc_id, data_json in rows]

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
            "SELECT field, term, doc_id, positions FROM _postings WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (field, term, doc_id, tuple(json.loads(positions)))
            for field, term, doc_id, positions in rows
        ]

    def load_doc_lengths(self, table_name: str) -> list[tuple[int, dict[str, int]]]:
        """Load per-document per-field token lengths.

        Returns ``[(doc_id, {field: length, ...}), ...]``.
        """
        rows = self._conn.execute(
            "SELECT doc_id, lengths FROM _doc_lengths WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [(doc_id, json.loads(lengths)) for doc_id, lengths in rows]

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
        return [(vertex_id, json.loads(props)) for vertex_id, props in rows]

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
        self._conn.execute("DELETE FROM _vectors WHERE doc_id = ?", (doc_id,))
        self._auto_commit()

    def load_vectors(self) -> list[tuple[int, NDArray]]:
        rows = self._conn.execute(
            "SELECT doc_id, dimensions, embedding FROM _vectors"
        ).fetchall()
        result: list[tuple[int, NDArray]] = []
        for doc_id, _dims, blob in rows:
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
        histogram: list[Any] | None = None,
        mcv_values: list[Any] | None = None,
        mcv_frequencies: list[float] | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _column_stats "
            "(table_name, column_name, distinct_count, null_count, "
            "min_value, max_value, row_count, "
            "histogram, mcv_values, mcv_frequencies) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                table_name,
                column_name,
                distinct_count,
                null_count,
                json.dumps(min_value),
                json.dumps(max_value),
                row_count,
                json.dumps(histogram or []),
                json.dumps(mcv_values or []),
                json.dumps(mcv_frequencies or []),
            ),
        )
        self._auto_commit()

    def load_column_stats(
        self, table_name: str
    ) -> list[tuple[str, int, int, Any, Any, int, list, list, list]]:
        """Return stats tuples including histogram and MCV data."""
        rows = self._conn.execute(
            "SELECT column_name, distinct_count, null_count, "
            "min_value, max_value, row_count, "
            "histogram, mcv_values, mcv_frequencies "
            "FROM _column_stats WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        result = []
        for row in rows:
            col, dc, nc, mn, mx, rc = row[:6]
            hist = json.loads(row[6]) if len(row) > 6 else []
            mcv_v = json.loads(row[7]) if len(row) > 7 else []
            mcv_f = json.loads(row[8]) if len(row) > 8 else []
            result.append(
                (col, dc, nc, json.loads(mn), json.loads(mx), rc, hist, mcv_v, mcv_f)
            )
        return result

    def delete_column_stats(self, table_name: str) -> None:
        self._conn.execute(
            "DELETE FROM _column_stats WHERE table_name = ?", (table_name,)
        )
        self._auto_commit()

    # -- Scoring / calibration parameters (Papers 3-4) -----------------

    def save_scoring_params(self, name: str, params: dict[str, Any]) -> None:
        """Persist Bayesian calibration parameters for a named signal."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _scoring_params (name, params_json) VALUES (?, ?)",
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
        self._conn.execute("DELETE FROM _scoring_params WHERE name = ?", (name,))
        self._auto_commit()

    # -- Indexes -------------------------------------------------------

    def save_index(self, index_def: Any) -> None:
        """Persist an index definition to the catalog."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _catalog_indexes "
            "(name, index_type, table_name, columns, parameters) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                index_def.name,
                index_def.index_type.value,
                index_def.table_name,
                json.dumps(list(index_def.columns)),
                json.dumps(index_def.parameters),
            ),
        )
        self._auto_commit()

    def drop_index(self, name: str) -> None:
        """Remove an index definition from the catalog."""
        self._conn.execute("DELETE FROM _catalog_indexes WHERE name = ?", (name,))
        self._auto_commit()

    def load_indexes(self) -> list[tuple[str, str, str, list[str], dict]]:
        """Load all index definitions.

        Returns ``[(name, index_type, table_name, columns, parameters), ...]``.
        """
        rows = self._conn.execute(
            "SELECT name, index_type, table_name, columns, parameters "
            "FROM _catalog_indexes"
        ).fetchall()
        return [
            (name, idx_type, tbl, json.loads(cols), json.loads(params))
            for name, idx_type, tbl, cols, params in rows
        ]

    def load_indexes_for_table(
        self, table_name: str
    ) -> list[tuple[str, str, str, list[str], dict]]:
        """Load index definitions for a specific table."""
        rows = self._conn.execute(
            "SELECT name, index_type, table_name, columns, parameters "
            "FROM _catalog_indexes WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [
            (name, idx_type, tbl, json.loads(cols), json.loads(params))
            for name, idx_type, tbl, cols, params in rows
        ]

    # -- Named graphs --------------------------------------------------

    def save_named_graph(self, name: str) -> None:
        """Register a named graph in the catalog."""
        self._conn.execute(
            "INSERT OR IGNORE INTO _named_graphs (name) VALUES (?)",
            (name,),
        )
        self._auto_commit()

    def drop_named_graph(self, name: str) -> None:
        """Remove a named graph from the catalog."""
        self._conn.execute("DELETE FROM _named_graphs WHERE name = ?", (name,))
        self._auto_commit()

    def load_named_graphs(self) -> list[str]:
        """Return the names of all registered named graphs."""
        rows = self._conn.execute("SELECT name FROM _named_graphs").fetchall()
        return [r[0] for r in rows]

    # -- Path indexes --------------------------------------------------

    def save_path_index(
        self, graph_name: str, label_sequences: list[list[str]]
    ) -> None:
        """Persist path index label sequences for a named graph."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _path_indexes "
            "(graph_name, label_sequences) VALUES (?, ?)",
            (graph_name, json.dumps(label_sequences)),
        )
        self._auto_commit()

    def load_path_indexes(self) -> list[tuple[str, list[list[str]]]]:
        """Load all persisted path index configurations."""
        try:
            rows = self._conn.execute(
                "SELECT graph_name, label_sequences FROM _path_indexes"
            ).fetchall()
        except Exception:
            return []
        return [(name, json.loads(seqs)) for name, seqs in rows]

    def drop_path_index(self, graph_name: str) -> None:
        """Remove path index configuration for a graph."""
        self._conn.execute(
            "DELETE FROM _path_indexes WHERE graph_name = ?",
            (graph_name,),
        )
        self._auto_commit()

    # -- Analyzers -----------------------------------------------------

    def save_analyzer(self, name: str, config: dict[str, Any]) -> None:
        """Persist a named analyzer configuration."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _analyzers (name, config_json) VALUES (?, ?)",
            (name, json.dumps(config)),
        )
        self._auto_commit()

    def drop_analyzer(self, name: str) -> None:
        """Remove a named analyzer from the catalog."""
        self._conn.execute("DELETE FROM _analyzers WHERE name = ?", (name,))
        self._auto_commit()

    def load_analyzers(self) -> list[tuple[str, dict[str, Any]]]:
        """Return ``[(name, config_dict), ...]`` for all persisted analyzers."""
        rows = self._conn.execute("SELECT name, config_json FROM _analyzers").fetchall()
        return [(name, json.loads(cfg)) for name, cfg in rows]

    # -- Table field analyzers -----------------------------------------

    def save_table_field_analyzer(
        self, table_name: str, field: str, phase: str, analyzer_name: str
    ) -> None:
        """Persist a field-to-analyzer mapping for a specific phase."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _table_field_analyzers "
            "(table_name, field, phase, analyzer_name) VALUES (?, ?, ?, ?)",
            (table_name, field, phase, analyzer_name),
        )
        self._auto_commit()

    def load_table_field_analyzers(
        self,
    ) -> list[tuple[str, str, str, str]]:
        """Return ``[(table_name, field, phase, analyzer_name), ...]``."""
        rows = self._conn.execute(
            "SELECT table_name, field, phase, analyzer_name FROM _table_field_analyzers"
        ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    def drop_table_field_analyzers(self, table_name: str) -> None:
        """Remove all field-analyzer mappings for a table."""
        self._conn.execute(
            "DELETE FROM _table_field_analyzers WHERE table_name = ?",
            (table_name,),
        )
        self._auto_commit()

    # -- Foreign servers -----------------------------------------------

    def save_foreign_server(
        self, name: str, fdw_type: str, options: dict[str, str]
    ) -> None:
        """Persist a foreign server definition."""
        self._conn.execute(
            "INSERT INTO _foreign_servers (name, fdw_type, options) VALUES (?, ?, ?)",
            (name, fdw_type, json.dumps(options)),
        )
        self._auto_commit()

    def drop_foreign_server(self, name: str) -> None:
        """Remove a foreign server from the catalog."""
        self._conn.execute("DELETE FROM _foreign_servers WHERE name = ?", (name,))
        self._auto_commit()

    def load_foreign_servers(
        self,
    ) -> list[tuple[str, str, dict[str, str]]]:
        """Return ``[(name, fdw_type, options_dict), ...]``."""
        rows = self._conn.execute(
            "SELECT name, fdw_type, options FROM _foreign_servers"
        ).fetchall()
        return [(name, fdw_type, json.loads(opts)) for name, fdw_type, opts in rows]

    # -- Foreign tables ------------------------------------------------

    def save_foreign_table(
        self,
        name: str,
        server_name: str,
        columns_json: list[dict[str, Any]],
        options: dict[str, str],
    ) -> None:
        """Persist a foreign table definition."""
        self._conn.execute(
            "INSERT INTO _foreign_tables "
            "(name, server_name, columns_json, options) VALUES (?, ?, ?, ?)",
            (name, server_name, json.dumps(columns_json), json.dumps(options)),
        )
        self._auto_commit()

    def drop_foreign_table(self, name: str) -> None:
        """Remove a foreign table from the catalog."""
        self._conn.execute("DELETE FROM _foreign_tables WHERE name = ?", (name,))
        self._auto_commit()

    def load_foreign_tables(
        self,
    ) -> list[tuple[str, str, list[dict[str, Any]], dict[str, str]]]:
        """Return ``[(name, server_name, columns_json, options), ...]``."""
        rows = self._conn.execute(
            "SELECT name, server_name, columns_json, options FROM _foreign_tables"
        ).fetchall()
        return [
            (name, server_name, json.loads(cols), json.loads(opts))
            for name, server_name, cols, opts in rows
        ]

    # -- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._conn.close()
