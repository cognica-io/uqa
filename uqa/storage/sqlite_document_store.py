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

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

from uqa.core.hierarchical import HierarchicalDocument
from uqa.storage.abc.document_store import DocumentStore

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from uqa.core.types import DocId, FieldName, PathExpr
    from uqa.storage.managed_connection import SQLiteConnection


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
    "time": "TEXT",
    "timetz": "TEXT",
    "time without time zone": "TEXT",
    "time with time zone": "TEXT",
    "timestamp": "TEXT",
    "timestamptz": "TEXT",
    "timestamp without time zone": "TEXT",
    "timestamp with time zone": "TEXT",
    "json": "TEXT",
    "jsonb": "TEXT",
    "uuid": "TEXT",
    "bytea": "BLOB",
}


class SQLiteDocumentStore(DocumentStore):
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
        Sequence of ``(column_name, sql_type_name)`` or
        ``(column_name, sql_type_name, vector_dimensions)`` entries that
        define the schema.
    """

    def __init__(
        self,
        conn: SQLiteConnection,
        table_name: str,
        columns: Sequence[tuple[str, str] | tuple[str, str, int | None]],
    ) -> None:
        self._conn = conn
        self._table_name = table_name
        self._columns: list[str] = [col[0] for col in columns]
        self._col_set: frozenset[str] = frozenset(self._columns)
        self._has_atomic_fetch = hasattr(conn, "execute_fetchall")
        self._json_cols: frozenset[str] = frozenset(
            name
            for name, type_name, *_rest in columns
            if type_name.lower() in ("json", "jsonb", "vector", "point")
            or type_name.lower().endswith("[]")
        )
        self._vector_cols: frozenset[str] = frozenset(
            name
            for name, type_name, *_rest in columns
            if type_name.lower() in ("vector", "tensor")
        )
        self._create_tables()

    def add_column(self, name: str, type_name: str) -> None:
        if name in self._col_set:
            return
        self._columns.append(name)
        self._refresh_column_sets()
        self._add_typed_column(name, type_name)

    def drop_column(self, name: str) -> None:
        if name not in self._col_set:
            return
        self._columns = [col for col in self._columns if col != name]
        self._refresh_column_sets()

    def rename_column(self, old: str, new: str) -> None:
        self._columns = [new if col == old else col for col in self._columns]
        json_cols = {new if col == old else col for col in self._json_cols}
        vector_cols = {new if col == old else col for col in self._vector_cols}
        self._refresh_column_sets(json_cols=json_cols, vector_cols=vector_cols)

    def _add_typed_column(self, name: str, type_name: str) -> None:
        lower = type_name.lower()
        json_cols = set(self._json_cols)
        vector_cols = set(self._vector_cols)
        if lower in ("json", "jsonb", "vector", "point") or lower.endswith("[]"):
            json_cols.add(name)
        if lower in ("vector", "tensor"):
            vector_cols.add(name)
        self._refresh_column_sets(json_cols=json_cols, vector_cols=vector_cols)

    def _refresh_column_sets(
        self,
        *,
        json_cols: set[str] | None = None,
        vector_cols: set[str] | None = None,
    ) -> None:
        self._col_set = frozenset(self._columns)
        if json_cols is not None:
            self._json_cols = frozenset(json_cols)
        else:
            self._json_cols = frozenset(
                col for col in self._json_cols if col in self._col_set
            )
        if vector_cols is not None:
            self._vector_cols = frozenset(vector_cols)
        else:
            self._vector_cols = frozenset(
                col for col in self._vector_cols if col in self._col_set
            )

    # -- Thread-safe query helpers -------------------------------------

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        if self._has_atomic_fetch:
            return self._conn.execute_fetchall(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchall()

    def _fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        if self._has_atomic_fetch:
            return self._conn.execute_fetchone(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchone()

    def _create_tables(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _documents ("
            "table_name TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "body TEXT NOT NULL, "
            "PRIMARY KEY (table_name, doc_id))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _document_blobs ("
            "table_name TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "field_name TEXT NOT NULL, "
            "bytes BLOB NOT NULL, "
            "PRIMARY KEY (table_name, doc_id, field_name))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _vectors ("
            "table_name TEXT NOT NULL, "
            "field TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "vector_ordinal INTEGER NOT NULL DEFAULT 0, "
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (table_name, field, doc_id, vector_ordinal))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _ivf_assignments ("
            "table_name TEXT NOT NULL, "
            "field TEXT NOT NULL, "
            "doc_id INTEGER NOT NULL, "
            "vector_ordinal INTEGER NOT NULL DEFAULT 0, "
            "centroid_id INTEGER NOT NULL, "
            "PRIMARY KEY (table_name, field, doc_id, vector_ordinal))"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API (mirrors DocumentStore)
    # ------------------------------------------------------------------

    def put(self, doc_id: DocId, document: dict) -> None:
        """Insert or replace a document (row) keyed by *doc_id*."""
        stored: dict[str, Any] = {}
        blobs: list[tuple[str, bytes]] = []
        for col in self._columns:
            if col not in document or document[col] is None:
                continue
            encoded = _encode_value(document[col])
            if isinstance(encoded, _BlobValue):
                stored[col] = {
                    "$uqa_type": "document_blob",
                    "field": col,
                }
                blobs.append((col, encoded.data))
            else:
                stored[col] = encoded
        self._conn.execute(
            "DELETE FROM _document_blobs WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO _documents (table_name, doc_id, body) "
            "VALUES (?, ?, ?)",
            (self._table_name, doc_id, json.dumps(stored, ensure_ascii=False)),
        )
        for field, data in blobs:
            self._conn.execute(
                "INSERT OR REPLACE INTO _document_blobs "
                "(table_name, doc_id, field_name, bytes) VALUES (?, ?, ?, ?)",
                (self._table_name, doc_id, field, data),
            )
        self._persist_vectors(doc_id, document)
        self._conn.commit()

    def get(self, doc_id: DocId) -> dict | None:
        """Return the document as a dict, or ``None`` if absent."""
        row = self._fetchone(
            "SELECT body FROM _documents WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        if row is None:
            return None
        return self._decode_body(doc_id, row[0])

    def delete(self, doc_id: DocId) -> None:
        """Delete a document.  No error if *doc_id* does not exist."""
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _document_blobs WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments WHERE table_name = ? AND doc_id = ?",
            (self._table_name, doc_id),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Remove all rows from the backing SQLite table."""
        self._conn.execute(
            "DELETE FROM _documents WHERE table_name = ?", (self._table_name,)
        )
        self._conn.execute(
            "DELETE FROM _document_blobs WHERE table_name = ?", (self._table_name,)
        )
        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ?", (self._table_name,)
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments WHERE table_name = ?", (self._table_name,)
        )
        self._conn.commit()

    def get_field(self, doc_id: DocId, field: FieldName) -> Any:
        """Return a single field value, or ``None`` if absent."""
        if field not in self._col_set:
            return None
        doc = self.get(doc_id)
        return None if doc is None else doc.get(field)

    def get_fields_bulk(
        self, doc_ids: list[DocId], field: FieldName
    ) -> dict[DocId, Any]:
        """Return field values for multiple doc_ids in a single call."""
        if field not in self._col_set:
            return dict.fromkeys(doc_ids)
        result: dict[DocId, Any] = dict.fromkeys(doc_ids)
        for doc_id in doc_ids:
            result[doc_id] = self.get_field(doc_id, field)
        return result

    def has_value(self, field: FieldName, value: Any) -> bool:
        """Return True if any row has ``field == value``."""
        if field not in self._col_set:
            return False
        return any(doc.get(field) == value for _doc_id, doc in self.iter_all())

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
        rows = self._fetchall(
            "SELECT doc_id FROM _documents WHERE table_name = ?", (self._table_name,)
        )
        return {row[0] for row in rows}

    def __len__(self) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) FROM _documents WHERE table_name = ?",
            (self._table_name,),
        )
        return row[0] if row else 0

    def max_doc_id(self) -> int:
        """Return the largest ``_rowid`` currently stored, or 0."""
        row = self._fetchone(
            "SELECT MAX(doc_id) FROM _documents WHERE table_name = ?",
            (self._table_name,),
        )
        return row[0] if row is not None and row[0] is not None else 0

    def iter_all(self) -> Iterator[tuple[int, dict]]:
        """Yield all (doc_id, document) pairs in rowid order."""
        rows = self._fetchall(
            "SELECT doc_id, body FROM _documents WHERE table_name = ? ORDER BY doc_id",
            (self._table_name,),
        )
        for row in rows:
            doc_id = row[0]
            yield doc_id, self._decode_body(doc_id, row[1])

    def _decode_body(self, doc_id: int, body: str) -> dict[str, Any]:
        raw = json.loads(body)
        result: dict[str, Any] = {}
        for key, value in raw.items():
            decoded = _decode_value(value)
            if _is_blob_marker(decoded):
                blob = self._fetchone(
                    "SELECT bytes FROM _document_blobs "
                    "WHERE table_name = ? AND doc_id = ? AND field_name = ?",
                    (self._table_name, doc_id, key),
                )
                if blob is not None:
                    decoded = blob[0]
            result[key] = decoded
        return result

    def _persist_vectors(self, doc_id: int, document: dict[str, Any]) -> None:
        for field in self._vector_cols:
            self._conn.execute(
                "DELETE FROM _vectors "
                "WHERE table_name = ? AND field = ? AND doc_id = ?",
                (self._table_name, field, doc_id),
            )
            value = document.get(field)
            if value is None:
                continue
            vectors = _coerce_vectors(value)
            for ordinal, vector in enumerate(vectors):
                self._conn.execute(
                    "INSERT OR REPLACE INTO _vectors "
                    "(table_name, field, doc_id, vector_ordinal, vector) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self._table_name, field, doc_id, ordinal, vector),
                )


class _BlobValue:
    def __init__(self, data: bytes) -> None:
        self.data = data


def _encode_value(value: Any) -> Any:
    if isinstance(value, bytes | bytearray | memoryview):
        return _BlobValue(bytes(value))
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None and value.utcoffset() is not None:
            micros = int(value.timestamp() * 1_000_000)
            return {"$uqa_type": "timestamp_tz", "micros": micros}
        epoch = dt.datetime(1970, 1, 1)
        delta = value.replace(tzinfo=None) - epoch
        return {
            "$uqa_type": "timestamp",
            "micros": int(delta.total_seconds() * 1_000_000),
        }
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        days = (value - dt.date(1970, 1, 1)).days
        return {"$uqa_type": "date", "days": days}
    if isinstance(value, dt.time):
        micros = (
            value.hour * 3600 + value.minute * 60 + value.second
        ) * 1_000_000 + value.microsecond
        if value.tzinfo is not None and value.utcoffset() is not None:
            offset = int(value.utcoffset().total_seconds() // 60)
            return {"$uqa_type": "time_tz", "micros": micros, "offset_minutes": offset}
        return {"$uqa_type": "time", "micros": micros}
    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode_value(v) for v in value]
    return value


def _decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_value(v) for v in value]
    if not isinstance(value, dict):
        return value
    kind = value.get("$uqa_type")
    if kind == "date":
        return dt.date(1970, 1, 1) + dt.timedelta(days=int(value["days"]))
    if kind == "time":
        return _time_from_micros(int(value["micros"]))
    if kind == "time_tz":
        offset = dt.timezone(dt.timedelta(minutes=int(value.get("offset_minutes", 0))))
        return _time_from_micros(int(value["micros"]), offset)
    if kind == "timestamp":
        return dt.datetime(1970, 1, 1) + dt.timedelta(microseconds=int(value["micros"]))
    if kind == "timestamp_tz":
        return dt.datetime.fromtimestamp(int(value["micros"]) / 1_000_000, tz=dt.UTC)
    return {k: _decode_value(v) for k, v in value.items()}


def _time_from_micros(micros: int, tzinfo: dt.tzinfo | None = None) -> dt.time:
    micros %= 86_400 * 1_000_000
    seconds, microsecond = divmod(micros, 1_000_000)
    hour, rem = divmod(seconds, 3600)
    minute, second = divmod(rem, 60)
    return dt.time(hour, minute, second, microsecond, tzinfo=tzinfo)


def _is_blob_marker(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("$uqa_type") == "document_blob"
        and isinstance(value.get("field"), str)
    )


def _coerce_vectors(value: Any) -> list[bytes]:
    import numpy as np

    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 1:
        return [arr.tobytes()]
    if arr.ndim == 2:
        return [arr[i].tobytes() for i in range(arr.shape[0])]
    return []
