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
import struct
from typing import TYPE_CHECKING, Any

import numpy as np

from uqa.storage.managed_connection import ManagedConnection

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.storage.managed_connection import SQLiteConnection


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def positions_to_blob(positions: tuple[int, ...] | list[int]) -> bytes:
    return struct.pack(f"<{len(positions)}I", *[int(p) for p in positions])


def blob_to_positions(data: bytes | str) -> tuple[int, ...]:
    if isinstance(data, str):
        return tuple(json.loads(data))
    return struct.unpack(f"<{len(data) // 4}I", data)


def decode_legacy_positions(data: bytes | str) -> tuple[int, ...]:
    if isinstance(data, str):
        return tuple(json.loads(data))
    little = struct.unpack(f"<{len(data) // 4}I", data)
    if little and max(little) > 10_000_000:
        return struct.unpack(f">{len(data) // 4}I", data)
    return little


def default_analyzer_json() -> str:
    return json.dumps(
        {
            "tokenizer": {"type": "standard"},
            "token_filters": [
                {"type": "lowercase"},
                {"type": "a_s_c_i_i_folding"},
                {"type": "stop", "language": "english"},
                {"type": "porter_stem"},
            ],
            "char_filters": [],
        },
        separators=(",", ":"),
    )


def vector_fields_from_python_columns(
    columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for col in columns:
        dimensions = col.get("vector_dimensions")
        if dimensions is None and str(col.get("type_name", "")).lower() == "vector":
            dimensions = 0
        if dimensions is not None:
            fields.append({"field": col["name"], "dimensions": int(dimensions)})
    return fields


def python_columns_to_catalog_columns(
    columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    catalog_columns: list[dict[str, Any]] = []
    for col in columns:
        out = {
            "name": col["name"],
            "ty": python_type_to_catalog_type(col),
            "type_name": str(col.get("type_name", "text")).lower(),
            "primary_key": bool(col.get("primary_key", False)),
            "not_null": bool(col.get("not_null", False)),
            "auto_increment": bool(col.get("auto_increment", False)),
            "unique": bool(col.get("unique", False)),
        }
        default = python_default_to_catalog_default(col.get("default"))
        if default is not None:
            out["default"] = default
        catalog_columns.append(out)
    return catalog_columns


def python_default_to_catalog_default(default: Any) -> dict[str, Any] | None:
    if default is None:
        return None
    if isinstance(default, str | int | float | bool):
        return {"Literal": default}
    if isinstance(default, dict) and set(default) == {"Expression"}:
        return {"Expression": str(default["Expression"])}
    raise ValueError(f"Unsupported DEFAULT value type: {type(default).__name__}")


def catalog_default_to_python_default(default: Any) -> Any:
    if isinstance(default, dict) and set(default) == {"Literal"}:
        return default["Literal"]
    if isinstance(default, dict) and set(default) == {"Expression"}:
        return {"Expression": str(default["Expression"])}
    if default is None:
        return None
    raise ValueError("Unsupported DEFAULT value in catalog")


def python_type_to_catalog_type(col: dict[str, Any]) -> str | dict[str, Any]:
    raw = str(col.get("type_name", "text")).lower()
    if raw == "vector":
        return {"Vector": int(col.get("vector_dimensions") or 0)}
    if raw == "tensor":
        return {"Tensor": int(col.get("vector_dimensions") or 0)}
    if raw.endswith("[]") or raw in {"json", "jsonb", "point"}:
        return "Json"
    if raw in {"bytea", "bytes", "blob"}:
        return "Bytea"
    if raw == "date":
        return "Date"
    if raw in {"time", "time without time zone"}:
        return "Time"
    if raw in {"timetz", "time with time zone"}:
        return "TimeTz"
    if raw in {"timestamp", "datetime", "timestamp without time zone"}:
        return "Timestamp"
    if raw in {"timestamptz", "timestamp with time zone"}:
        return "TimestampTz"
    if raw in {"numeric", "decimal"}:
        return {
            "Numeric": {
                "precision": col.get("numeric_precision"),
                "scale": col.get("numeric_scale"),
            }
        }
    if raw in {
        "integer",
        "int",
        "int2",
        "int4",
        "int8",
        "bigint",
        "smallint",
        "serial",
        "bigserial",
        "serial4",
        "serial8",
        "bool",
        "boolean",
    }:
        return "Integer"
    if raw in {"real", "float", "float4", "float8", "double", "double precision"}:
        return "Real"
    return "Text"


def catalog_columns_to_python_columns(
    columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    python_columns: list[dict[str, Any]] = []
    for col in columns:
        type_name, vector_dimensions, numeric_precision, numeric_scale = (
            catalog_type_to_python(col.get("ty", "Text"))
        )
        auto_increment = bool(col.get("auto_increment", False))
        if type_name == "integer" and auto_increment:
            type_name = "serial"
        original_type = col.get("type_name")
        if isinstance(original_type, str) and original_type:
            type_name = original_type.lower()
        default = catalog_default_to_python_default(col.get("default"))
        out = {
            "name": col["name"],
            "type_name": type_name,
            "primary_key": bool(col.get("primary_key", False)),
            "not_null": bool(col.get("not_null", False)),
            "auto_increment": auto_increment,
            "default": default,
        }
        if col.get("unique", False):
            out["unique"] = True
        if vector_dimensions is not None:
            out["vector_dimensions"] = vector_dimensions
        if numeric_precision is not None:
            out["numeric_precision"] = numeric_precision
        if numeric_scale is not None:
            out["numeric_scale"] = numeric_scale
        python_columns.append(out)
    return python_columns


def catalog_type_to_python(ty: Any) -> tuple[str, int | None, int | None, int | None]:
    if isinstance(ty, str):
        return {
            "Integer": ("integer", None, None, None),
            "Text": ("text", None, None, None),
            "Real": ("real", None, None, None),
            "Json": ("jsonb", None, None, None),
            "Bytea": ("bytea", None, None, None),
            "Date": ("date", None, None, None),
            "Time": ("time", None, None, None),
            "TimeTz": ("timetz", None, None, None),
            "Timestamp": ("timestamp without time zone", None, None, None),
            "TimestampTz": ("timestamp with time zone", None, None, None),
        }.get(ty, ("text", None, None, None))
    if isinstance(ty, dict):
        if "Vector" in ty:
            return ("vector", int(ty["Vector"]), None, None)
        if "Tensor" in ty:
            return ("tensor", int(ty["Tensor"]), None, None)
        if "Numeric" in ty:
            numeric = ty["Numeric"] or {}
            return (
                "numeric",
                None,
                numeric.get("precision"),
                numeric.get("scale"),
            )
    return ("text", None, None, None)


class Catalog:
    """SQLite-backed system catalog for persistent storage."""

    CURRENT_SCHEMA_VERSION = 10

    _SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS _metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _tables (
    name          TEXT PRIMARY KEY,
    analyzer      TEXT NOT NULL,
    fts_fields    TEXT NOT NULL,
    vector_fields TEXT NOT NULL,
    columns       TEXT
);
CREATE TABLE IF NOT EXISTS _documents (
    table_name TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    body       TEXT    NOT NULL,
    PRIMARY KEY (table_name, doc_id)
);
CREATE TABLE IF NOT EXISTS _document_blobs (
    table_name TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    field_name TEXT    NOT NULL,
    bytes      BLOB    NOT NULL,
    PRIMARY KEY (table_name, doc_id, field_name)
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
CREATE TABLE IF NOT EXISTS _graph_membership (
    entity_type TEXT    NOT NULL,
    entity_id   INTEGER NOT NULL,
    graph_name  TEXT    NOT NULL,
    PRIMARY KEY (entity_type, entity_id, graph_name)
);
CREATE TABLE IF NOT EXISTS _vectors (
    table_name     TEXT    NOT NULL,
    field          TEXT    NOT NULL,
    doc_id         INTEGER NOT NULL,
    vector_ordinal INTEGER NOT NULL DEFAULT 0,
    vector         BLOB    NOT NULL,
    PRIMARY KEY (table_name, field, doc_id, vector_ordinal)
);
CREATE TABLE IF NOT EXISTS _postings (
    table_name TEXT    NOT NULL,
    field      TEXT    NOT NULL,
    term       TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    positions  BLOB    NOT NULL,
    PRIMARY KEY (table_name, field, term, doc_id)
);
CREATE INDEX IF NOT EXISTS _postings_term_idx
    ON _postings (table_name, field, term);
CREATE INDEX IF NOT EXISTS _postings_doc_idx
    ON _postings (table_name, doc_id);
CREATE TABLE IF NOT EXISTS _doc_lengths (
    table_name TEXT NOT NULL,
    doc_id     INTEGER NOT NULL,
    field      TEXT NOT NULL,
    length     INTEGER NOT NULL,
    PRIMARY KEY (table_name, doc_id, field)
);
CREATE TABLE IF NOT EXISTS _field_stats (
    table_name   TEXT NOT NULL,
    field        TEXT NOT NULL,
    total_length INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (table_name, field)
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
    params      TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS _models (
    name TEXT PRIMARY KEY,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _ivf_indexes (
    table_name          TEXT    NOT NULL,
    field               TEXT    NOT NULL,
    dimensions          INTEGER NOT NULL,
    nlist               INTEGER NOT NULL,
    nprobe              INTEGER NOT NULL,
    train_threshold     INTEGER NOT NULL,
    state               TEXT    NOT NULL,
    trained_size        INTEGER NOT NULL,
    deletes_since_train INTEGER NOT NULL,
    vector_count        INTEGER NOT NULL,
    PRIMARY KEY (table_name, field)
);
CREATE TABLE IF NOT EXISTS _ivf_centroids (
    table_name  TEXT    NOT NULL,
    field       TEXT    NOT NULL,
    centroid_id INTEGER NOT NULL,
    vector      BLOB    NOT NULL,
    PRIMARY KEY (table_name, field, centroid_id)
);
CREATE TABLE IF NOT EXISTS _ivf_assignments (
    table_name     TEXT    NOT NULL,
    field          TEXT    NOT NULL,
    doc_id         INTEGER NOT NULL,
    vector_ordinal INTEGER NOT NULL DEFAULT 0,
    centroid_id    INTEGER NOT NULL,
    PRIMARY KEY (table_name, field, doc_id, vector_ordinal)
);
CREATE INDEX IF NOT EXISTS _ivf_assignments_centroid_idx
    ON _ivf_assignments (table_name, field, centroid_id, doc_id, vector_ordinal);
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
        self._migrate_legacy_metadata(raw)
        self._migrate_legacy_documents(raw)
        self._migrate_legacy_postings(raw)
        self._migrate_legacy_doc_lengths(raw)
        self._migrate_legacy_models(raw)
        self._migrate_legacy_scoring_params(raw)
        self._migrate_legacy_vectors(raw)
        raw.executescript(self._SCHEMA_SQL)
        self._migrate_legacy_tables(raw)
        self._migrate_column_stats(raw)
        self._migrate_table_field_analyzers(raw)
        self._migrate_models(raw)
        raw.execute(
            "INSERT OR REPLACE INTO _metadata (key, value) VALUES (?, ?)",
            ("schema_version", str(self.CURRENT_SCHEMA_VERSION)),
        )
        raw.commit()
        self._conn = ManagedConnection(raw, db_path=db_path)
        self._in_transaction = False

    @staticmethod
    def _table_names(conn: SQLiteConnection) -> set[str]:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    @staticmethod
    def _table_columns(conn: SQLiteConnection, table_name: str) -> dict[str, str]:
        if table_name not in Catalog._table_names(conn):
            return {}
        return {
            row[1]: row[2]
            for row in conn.execute(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            ).fetchall()
        }

    @staticmethod
    def _migrate_legacy_metadata(conn: SQLiteConnection) -> None:
        tables = Catalog._table_names(conn)
        if "_meta" in tables and "_metadata" not in tables:
            conn.execute("ALTER TABLE _meta RENAME TO _metadata")

    @staticmethod
    def _migrate_legacy_documents(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_documents")
        if not cols or "body" in cols:
            return
        if "data_json" not in cols:
            return
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _documents_v10 ("
            "table_name TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "body TEXT NOT NULL, "
            "PRIMARY KEY (table_name, doc_id))"
        )
        conn.execute(
            "INSERT OR REPLACE INTO _documents_v10 (table_name, doc_id, body) "
            "SELECT table_name, doc_id, data_json FROM _documents"
        )
        conn.execute("DROP TABLE _documents")
        conn.execute("ALTER TABLE _documents_v10 RENAME TO _documents")

    @staticmethod
    def _migrate_legacy_postings(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_postings")
        if not cols:
            return
        positions_type = cols.get("positions", "")
        if positions_type.upper() == "BLOB":
            return
        rows = conn.execute(
            "SELECT table_name, field, term, doc_id, positions FROM _postings"
        ).fetchall()
        conn.execute("DROP TABLE _postings")
        conn.execute(
            "CREATE TABLE _postings ("
            "table_name TEXT NOT NULL, "
            "field TEXT NOT NULL, "
            "term TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "positions BLOB NOT NULL, "
            "PRIMARY KEY (table_name, field, term, doc_id))"
        )
        for table_name, field, term, doc_id, positions in rows:
            conn.execute(
                "INSERT OR REPLACE INTO _postings "
                "(table_name, field, term, doc_id, positions) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    table_name,
                    field,
                    term,
                    doc_id,
                    positions_to_blob(decode_legacy_positions(positions)),
                ),
            )

    @staticmethod
    def _migrate_legacy_doc_lengths(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_doc_lengths")
        if not cols or "field" in cols:
            return
        if "lengths" not in cols:
            return
        rows = conn.execute(
            "SELECT table_name, doc_id, lengths FROM _doc_lengths"
        ).fetchall()
        conn.execute("DROP TABLE _doc_lengths")
        conn.execute(
            "CREATE TABLE _doc_lengths ("
            "table_name TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "field TEXT NOT NULL, "
            "length INTEGER NOT NULL, "
            "PRIMARY KEY (table_name, doc_id, field))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _field_stats ("
            "table_name TEXT NOT NULL, "
            "field TEXT NOT NULL, "
            "total_length INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (table_name, field))"
        )
        for table_name, doc_id, lengths_json in rows:
            lengths = json.loads(lengths_json)
            for field, length in lengths.items():
                conn.execute(
                    "INSERT OR REPLACE INTO _doc_lengths "
                    "(table_name, doc_id, field, length) VALUES (?, ?, ?, ?)",
                    (table_name, doc_id, field, int(length)),
                )
                conn.execute(
                    "INSERT INTO _field_stats "
                    "(table_name, field, total_length) VALUES (?, ?, ?) "
                    "ON CONFLICT(table_name, field) DO UPDATE "
                    "SET total_length = total_length + excluded.total_length",
                    (table_name, field, int(length)),
                )

    @staticmethod
    def _migrate_legacy_models(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_models")
        if not cols or {"name", "body"}.issubset(cols):
            return
        if not {"model_name", "config_json"}.issubset(cols):
            return
        rows = conn.execute("SELECT model_name, config_json FROM _models").fetchall()
        conn.execute("DROP TABLE _models")
        conn.execute("CREATE TABLE _models (name TEXT PRIMARY KEY, body TEXT NOT NULL)")
        conn.executemany(
            "INSERT OR REPLACE INTO _models (name, body) VALUES (?, ?)", rows
        )

    @staticmethod
    def _migrate_legacy_scoring_params(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_scoring_params")
        if not cols or "params" in cols:
            return
        if "params_json" not in cols:
            return
        rows = conn.execute("SELECT name, params_json FROM _scoring_params").fetchall()
        conn.execute("DROP TABLE _scoring_params")
        conn.execute(
            "CREATE TABLE _scoring_params (name TEXT PRIMARY KEY, params TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO _scoring_params (name, params) VALUES (?, ?)",
            rows,
        )

    @staticmethod
    def _migrate_legacy_vectors(conn: SQLiteConnection) -> None:
        cols = Catalog._table_columns(conn, "_vectors")
        if not cols or "table_name" in cols:
            return
        conn.execute("DROP TABLE _vectors")

    @staticmethod
    def _migrate_legacy_tables(conn: SQLiteConnection) -> None:
        tables = Catalog._table_names(conn)
        if "_catalog_tables" not in tables:
            return
        existing = {
            row[0] for row in conn.execute("SELECT name FROM _tables").fetchall()
        }
        rows = conn.execute(
            "SELECT name, columns_json FROM _catalog_tables ORDER BY name"
        ).fetchall()
        for name, columns_json in rows:
            if name in existing:
                continue
            columns = json.loads(columns_json)
            conn.execute(
                "INSERT OR REPLACE INTO _tables "
                "(name, analyzer, fts_fields, vector_fields, columns) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    name,
                    default_analyzer_json(),
                    "[]",
                    json.dumps(vector_fields_from_python_columns(columns)),
                    json.dumps(python_columns_to_catalog_columns(columns)),
                ),
            )

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

    @staticmethod
    def _migrate_models(conn: SQLiteConnection) -> None:
        """Create _models table if missing (for existing databases)."""
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "_models" not in tables:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _models ("
                "    name TEXT PRIMARY KEY,"
                "    body TEXT NOT NULL"
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
            "INSERT OR REPLACE INTO _tables "
            "(name, analyzer, fts_fields, vector_fields, columns) "
            "VALUES (?, COALESCE((SELECT analyzer FROM _tables WHERE name = ?), ?), "
            "COALESCE((SELECT fts_fields FROM _tables WHERE name = ?), '[]'), "
            "?, ?)",
            (
                name,
                name,
                default_analyzer_json(),
                name,
                json.dumps(vector_fields_from_python_columns(columns)),
                json.dumps(python_columns_to_catalog_columns(columns)),
            ),
        )
        self._auto_commit()

    def drop_table_schema(self, name: str) -> None:
        """Remove a table schema and all associated data.

        Drops both per-table SQLite tables (new format) and rows in
        shared catalog tables (old format) for backward compatibility.
        """
        self._conn.execute("DELETE FROM _tables WHERE name = ?", (name,))
        if "_catalog_tables" in self._table_names(self._conn):
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
        self._conn.execute("DELETE FROM _document_blobs WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _postings WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _doc_lengths WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _field_stats WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _vectors WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _ivf_indexes WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _ivf_centroids WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _ivf_assignments WHERE table_name = ?", (name,))
        self._conn.execute("DELETE FROM _column_stats WHERE table_name = ?", (name,))
        self._conn.execute(
            "DELETE FROM _table_field_analyzers WHERE table_name = ?", (name,)
        )
        self._auto_commit()

    def load_table_schemas(self) -> list[tuple[str, list[dict[str, Any]]]]:
        """Return ``[(table_name, [column_dict, ...]), ...]``."""
        rows = self._conn.execute(
            "SELECT name, columns FROM _tables ORDER BY name"
        ).fetchall()
        if rows:
            return [
                (name, catalog_columns_to_python_columns(json.loads(columns or "[]")))
                for name, columns in rows
            ]
        tables = {
            row[0]
            for row in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "_catalog_tables" not in tables:
            return []
        legacy_rows = self._conn.execute(
            "SELECT name, columns_json FROM _catalog_tables ORDER BY name"
        ).fetchall()
        return [(name, json.loads(columns_json)) for name, columns_json in legacy_rows]

    # -- Documents -----------------------------------------------------

    def save_document(self, table_name: str, doc_id: int, data: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _documents "
            "(table_name, doc_id, body) VALUES (?, ?, ?)",
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
            "DELETE FROM _document_blobs WHERE table_name = ? AND doc_id = ?",
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
        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        self._auto_commit()

    def load_documents(self, table_name: str) -> list[tuple[int, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT doc_id, body FROM _documents WHERE table_name = ? ORDER BY doc_id",
            (table_name,),
        ).fetchall()
        return [(doc_id, json.loads(body)) for doc_id, body in rows]

    # -- Postings (inverted index entries) -----------------------------

    def save_postings(
        self,
        table_name: str,
        doc_id: int,
        field_lengths: dict[str, int],
        postings: dict[tuple[str, str], tuple[int, ...]],
    ) -> None:
        """Persist posting entries and per-field token lengths for one doc."""
        self.delete_postings(table_name, doc_id)
        for (field, term), positions in postings.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO _postings "
                "(table_name, field, term, doc_id, positions) "
                "VALUES (?, ?, ?, ?, ?)",
                (table_name, field, term, doc_id, positions_to_blob(positions)),
            )
        for field, length in field_lengths.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO _doc_lengths "
                "(table_name, doc_id, field, length) VALUES (?, ?, ?, ?)",
                (table_name, doc_id, field, int(length)),
            )
            self._conn.execute(
                "INSERT INTO _field_stats (table_name, field, total_length) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(table_name, field) DO UPDATE "
                "SET total_length = total_length + excluded.total_length",
                (table_name, field, int(length)),
            )
        self._auto_commit()

    def delete_postings(self, table_name: str, doc_id: int) -> None:
        """Remove all postings and doc lengths for one document."""
        self._conn.execute(
            "DELETE FROM _postings WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        )
        rows = self._conn.execute(
            "SELECT field, length FROM _doc_lengths "
            "WHERE table_name = ? AND doc_id = ?",
            (table_name, doc_id),
        ).fetchall()
        for field, length in rows:
            self._conn.execute(
                "UPDATE _field_stats "
                "SET total_length = MAX(0, total_length - ?) "
                "WHERE table_name = ? AND field = ?",
                (int(length), table_name, field),
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
            (field, term, doc_id, blob_to_positions(positions))
            for field, term, doc_id, positions in rows
        ]

    def load_doc_lengths(self, table_name: str) -> list[tuple[int, dict[str, int]]]:
        """Load per-document per-field token lengths.

        Returns ``[(doc_id, {field: length, ...}), ...]``.
        """
        rows = self._conn.execute(
            "SELECT doc_id, field, length FROM _doc_lengths "
            "WHERE table_name = ? ORDER BY doc_id, field",
            (table_name,),
        ).fetchall()
        by_doc: dict[int, dict[str, int]] = {}
        for doc_id, field, length in rows:
            by_doc.setdefault(doc_id, {})[field] = int(length)
        return list(by_doc.items())

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
            "(table_name, field, doc_id, vector_ordinal, vector) "
            "VALUES (?, ?, ?, ?, ?)",
            ("", "", doc_id, 0, blob),
        )
        self._auto_commit()

    def delete_vector(self, doc_id: int) -> None:
        self._conn.execute("DELETE FROM _vectors WHERE doc_id = ?", (doc_id,))
        self._auto_commit()

    def load_vectors(self) -> list[tuple[int, NDArray]]:
        rows = self._conn.execute(
            "SELECT doc_id, vector FROM _vectors WHERE table_name = '' AND field = ''"
        ).fetchall()
        result: list[tuple[int, NDArray]] = []
        for doc_id, blob in rows:
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
            "INSERT OR REPLACE INTO _scoring_params (name, params) VALUES (?, ?)",
            (name, json.dumps(params)),
        )
        self._auto_commit()

    def load_scoring_params(self, name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT params FROM _scoring_params WHERE name = ?",
            (name,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_all_scoring_params(self) -> list[tuple[str, dict[str, Any]]]:
        rows = self._conn.execute("SELECT name, params FROM _scoring_params").fetchall()
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
        self._sync_table_index_fields(
            index_def.table_name,
            index_def.index_type.value,
            list(index_def.columns),
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

    def _sync_table_index_fields(
        self, table_name: str, index_type: str, columns: list[str]
    ) -> None:
        row = self._conn.execute(
            "SELECT fts_fields, vector_fields, columns FROM _tables WHERE name = ?",
            (table_name,),
        ).fetchone()
        if row is None:
            return
        fts_fields = json.loads(row[0] or "[]")
        vector_fields = json.loads(row[1] or "[]")
        table_columns = catalog_columns_to_python_columns(json.loads(row[2] or "[]"))
        by_name = {col["name"]: col for col in table_columns}
        if index_type == "gin":
            seen = set(fts_fields)
            for col in columns:
                if col not in seen:
                    fts_fields.append(col)
                    seen.add(col)
        elif index_type in {"ivf", "hnsw"}:
            by_field = {vf["field"]: vf for vf in vector_fields}
            for col in columns:
                col_def = by_name.get(col)
                dimensions = (col_def or {}).get("vector_dimensions")
                if dimensions is None:
                    continue
                by_field[col] = {"field": col, "dimensions": int(dimensions)}
            vector_fields = list(by_field.values())
        else:
            return
        self._conn.execute(
            "UPDATE _tables SET fts_fields = ?, vector_fields = ? WHERE name = ?",
            (json.dumps(fts_fields), json.dumps(vector_fields), table_name),
        )

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

    # -- Models (deep_learn) -------------------------------------------

    def save_model(self, model_name: str, config: dict[str, Any]) -> None:
        """Persist a trained model configuration."""
        self._conn.execute(
            "INSERT OR REPLACE INTO _models (name, body) VALUES (?, ?)",
            (model_name, json.dumps(config)),
        )
        self._auto_commit()

    def load_model(self, model_name: str) -> dict[str, Any] | None:
        """Load a trained model configuration by name."""
        row = self._conn.execute(
            "SELECT body FROM _models WHERE name = ?",
            (model_name,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def delete_model(self, model_name: str) -> None:
        """Remove a trained model from the catalog."""
        self._conn.execute("DELETE FROM _models WHERE name = ?", (model_name,))
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
        # Checkpoint WAL to ensure all committed data is flushed to
        # the main database file before closing.  Without this,
        # large transactions (e.g. IVF _train with thousands of
        # vectors) may remain only in the WAL file and appear as
        # corruption on reopen.
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        self._conn.close()
