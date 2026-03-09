#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed document store.

Drop-in replacement for the in-memory ``DocumentStore`` that persists
rows in a typed SQLite table.  Each column is mapped to its closest
SQLite affinity so that type round-tripping is preserved.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from uqa.core.hierarchical import HierarchicalDocument

if TYPE_CHECKING:
    from uqa.core.types import DocId, FieldName, PathExpr


# Mapping from SQL type keywords to SQLite column affinity.
_AFFINITY_MAP: dict[str, str] = {
    "int": "INTEGER",
    "integer": "INTEGER",
    "int2": "INTEGER",
    "int4": "INTEGER",
    "int8": "INTEGER",
    "bigint": "INTEGER",
    "smallint": "INTEGER",
    "serial": "INTEGER",
    "bigserial": "INTEGER",
    "text": "TEXT",
    "varchar": "TEXT",
    "character varying": "TEXT",
    "char": "TEXT",
    "character": "TEXT",
    "name": "TEXT",
    "real": "REAL",
    "float": "REAL",
    "float4": "REAL",
    "float8": "REAL",
    "double": "REAL",
    "double precision": "REAL",
    "numeric": "REAL",
    "decimal": "REAL",
    "bool": "INTEGER",
    "boolean": "INTEGER",
    "bytes": "BLOB",
    "blob": "BLOB",
    "date": "TEXT",
    "timestamp": "TEXT",
    "timestamptz": "TEXT",
    "timestamp without time zone": "TEXT",
    "timestamp with time zone": "TEXT",
    "json": "TEXT",
    "jsonb": "TEXT",
}


class SQLiteDocumentStore:
    """SQLite-backed document store with the same public API as DocumentStore.

    Parameters
    ----------
    conn:
        An open ``sqlite3.Connection``.  The caller is responsible for
        connection lifetime and commits/WAL mode.
    table_name:
        Logical table name.  The backing SQLite table is named
        ``_data_{table_name}``.
    columns:
        Sequence of ``(column_name, sql_type_name)`` pairs that define
        the schema.  Type names are resolved via ``_AFFINITY_MAP``.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        columns: list[tuple[str, str]],
    ) -> None:
        self._conn = conn
        self._table = f"_data_{table_name}"
        self._columns: list[str] = [name for name, _ in columns]
        self._col_set: frozenset[str] = frozenset(self._columns)
        self._json_cols: frozenset[str] = frozenset(
            name for name, type_name in columns
            if type_name.lower() in ("json", "jsonb")
        )

        # Build and execute CREATE TABLE IF NOT EXISTS
        col_defs: list[str] = ["_rowid INTEGER PRIMARY KEY"]
        for name, type_name in columns:
            affinity = _AFFINITY_MAP.get(type_name.lower(), "TEXT")
            col_defs.append(f"{name} {affinity}")

        ddl = (
            f"CREATE TABLE IF NOT EXISTS {self._table} "
            f"({', '.join(col_defs)})"
        )
        self._conn.execute(ddl)
        self._conn.commit()

        # Pre-build reusable SQL fragments
        all_cols = ", ".join(self._columns)
        placeholders = ", ".join(["?"] * (1 + len(self._columns)))
        col_list = ", ".join(["_rowid"] + self._columns)

        self._sql_put = (
            f"INSERT OR REPLACE INTO {self._table} ({col_list}) "
            f"VALUES ({placeholders})"
        )
        self._sql_get = (
            f"SELECT {all_cols} FROM {self._table} WHERE _rowid = ?"
        )
        self._sql_delete = f"DELETE FROM {self._table} WHERE _rowid = ?"
        self._sql_ids = f"SELECT _rowid FROM {self._table}"
        self._sql_count = f"SELECT COUNT(*) FROM {self._table}"
        self._sql_max = f"SELECT MAX(_rowid) FROM {self._table}"

    # ------------------------------------------------------------------
    # Public API (mirrors DocumentStore)
    # ------------------------------------------------------------------

    def put(self, doc_id: DocId, document: dict) -> None:
        """Insert or replace a document (row) keyed by *doc_id*."""
        import json as json_mod

        values = [doc_id]
        for c in self._columns:
            v = document.get(c)
            if v is not None and c in self._json_cols and isinstance(
                v, (dict, list)
            ):
                v = json_mod.dumps(v, ensure_ascii=False)
            values.append(v)
        self._conn.execute(self._sql_put, values)
        self._conn.commit()

    def get(self, doc_id: DocId) -> dict | None:
        """Return the document as a dict, or ``None`` if absent."""
        import json as json_mod

        cursor = self._conn.execute(self._sql_get, (doc_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        result: dict = {}
        for i, col in enumerate(self._columns):
            v = row[i]
            if v is None:
                continue
            if col in self._json_cols and isinstance(v, str):
                v = json_mod.loads(v)
            result[col] = v
        return result

    def delete(self, doc_id: DocId) -> None:
        """Delete a document.  No error if *doc_id* does not exist."""
        self._conn.execute(self._sql_delete, (doc_id,))
        self._conn.commit()

    def clear(self) -> None:
        """Remove all rows from the backing SQLite table."""
        self._conn.execute(f"DELETE FROM {self._table}")
        self._conn.commit()

    def get_field(self, doc_id: DocId, field: FieldName) -> Any:
        """Return a single field value, or ``None`` if absent."""
        if field not in self._col_set:
            return None
        sql = f"SELECT {field} FROM {self._table} WHERE _rowid = ?"
        cursor = self._conn.execute(sql, (doc_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        v = row[0]
        if v is not None and field in self._json_cols and isinstance(v, str):
            import json as json_mod
            v = json_mod.loads(v)
        return v

    def eval_path(self, doc_id: DocId, path: PathExpr) -> Any:
        """Evaluate a hierarchical path expression against a document.

        SQLite stores flat rows, so single-element paths resolve directly
        to a column.  For multi-element (nested) paths the full document
        is fetched and traversed via ``HierarchicalDocument``.
        """
        if len(path) == 1 and isinstance(path[0], str):
            return self.get_field(doc_id, path[0])

        doc = self.get(doc_id)
        if doc is None:
            return None
        hdoc = HierarchicalDocument(doc_id, doc)
        return hdoc.eval_path(path)

    @property
    def doc_ids(self) -> set[DocId]:
        """Return the set of all stored document IDs."""
        cursor = self._conn.execute(self._sql_ids)
        return {row[0] for row in cursor.fetchall()}

    def __len__(self) -> int:
        cursor = self._conn.execute(self._sql_count)
        return cursor.fetchone()[0]

    def max_doc_id(self) -> int:
        """Return the largest ``_rowid`` currently stored, or 0."""
        cursor = self._conn.execute(self._sql_max)
        result = cursor.fetchone()[0]
        return result if result is not None else 0
