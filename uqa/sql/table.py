#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQL table: a named, schema-validated collection backed by UQA storage.

Each table maintains per-column statistics (distinct values, min/max,
null count) that drive the query optimizer's cardinality estimator.
Statistics are refreshed via ``ANALYZE table_name``.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from uqa.storage.document_store import DocumentStore
from uqa.storage.inverted_index import InvertedIndex


_SQL_TYPE_MAP: dict[str, type] = {
    "integer": int, "int": int, "int2": int, "int4": int, "int8": int,
    "bigint": int, "smallint": int,
    "serial": int, "bigserial": int,
    "text": str, "varchar": str, "character varying": str,
    "char": str, "character": str, "name": str,
    "real": float, "float": float, "float4": float, "float8": float,
    "double precision": float, "numeric": float, "decimal": float,
    "boolean": bool, "bool": bool,
}

_AUTO_INCREMENT_TYPES = frozenset({"serial", "bigserial"})


@dataclass(slots=True)
class ColumnStats:
    """Per-column statistics for cardinality estimation (Definition 6.2.3, Paper 1)."""

    distinct_count: int = 0
    null_count: int = 0
    min_value: Any = None
    max_value: Any = None
    row_count: int = 0

    @property
    def selectivity(self) -> float:
        """Estimated selectivity for equality predicates: 1/ndv."""
        if self.distinct_count <= 0:
            return 1.0
        return 1.0 / self.distinct_count


@dataclass(slots=True)
class ColumnDef:
    """Column definition within a table schema."""

    name: str
    type_name: str
    python_type: type
    primary_key: bool = False
    not_null: bool = False
    auto_increment: bool = False
    default: Any = None


class Table:
    """A named table with schema, backed by UQA storage.

    Each table owns its own DocumentStore and InvertedIndex so that
    ``FROM table_name`` resolves to isolated storage.
    """

    def __init__(self, name: str, columns: list[ColumnDef]) -> None:
        self.name = name
        self.columns: OrderedDict[str, ColumnDef] = OrderedDict(
            (col.name, col) for col in columns
        )
        self.primary_key: str | None = next(
            (col.name for col in columns if col.primary_key), None
        )
        self.document_store = DocumentStore()
        self.inverted_index = InvertedIndex()
        self._next_id = 1
        self._stats: dict[str, ColumnStats] = {}

    def insert(self, row: dict[str, Any]) -> int:
        """Insert a row and return the assigned primary key (doc_id)."""

        # -- primary key / doc_id resolution --------------------------
        if self.primary_key is not None:
            pk_col = self.columns[self.primary_key]
            if pk_col.auto_increment:
                if self.primary_key not in row or row[self.primary_key] is None:
                    row[self.primary_key] = self._next_id
                doc_id: int = row[self.primary_key]
                self._next_id = max(self._next_id, doc_id + 1)
            else:
                if self.primary_key not in row or row[self.primary_key] is None:
                    raise ValueError(
                        f"Missing primary key '{self.primary_key}' "
                        f"for table '{self.name}'"
                    )
                doc_id = int(row[self.primary_key])
                self._next_id = max(self._next_id, doc_id + 1)
        else:
            doc_id = self._next_id
            self._next_id += 1

        # -- NOT NULL validation --------------------------------------
        for col_name, col_def in self.columns.items():
            if col_def.not_null and not col_def.auto_increment:
                value = row.get(col_name)
                if value is None:
                    if col_def.default is not None:
                        row[col_name] = col_def.default
                    else:
                        raise ValueError(
                            f"NOT NULL constraint violated: "
                            f"column '{col_name}' in table '{self.name}'"
                        )

        # -- unknown column check -------------------------------------
        for col_name in row:
            if col_name not in self.columns:
                raise ValueError(
                    f"Unknown column '{col_name}' for table '{self.name}'"
                )

        # -- type coercion + defaults ---------------------------------
        coerced: dict[str, Any] = {}
        for col_name, col_def in self.columns.items():
            if col_name in row and row[col_name] is not None:
                coerced[col_name] = col_def.python_type(row[col_name])
            elif col_def.default is not None:
                coerced[col_name] = col_def.default
            # else: column absent -> not stored (sparse document)

        # -- persist ---------------------------------------------------
        self.document_store.put(doc_id, coerced)

        text_fields = {k: v for k, v in coerced.items() if isinstance(v, str)}
        if text_fields:
            self.inverted_index.add_document(doc_id, text_fields)

        return doc_id

    @property
    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    @property
    def row_count(self) -> int:
        return len(self.document_store.doc_ids)

    def analyze(self) -> dict[str, ColumnStats]:
        """Collect per-column statistics by scanning all rows.

        Updates ``self._stats`` and returns it.  Called by ``ANALYZE table``.
        """
        doc_ids = sorted(self.document_store.doc_ids)
        n = len(doc_ids)

        stats: dict[str, ColumnStats] = {}
        for col_name in self.columns:
            values: list[Any] = []
            null_count = 0
            for doc_id in doc_ids:
                val = self.document_store.get_field(doc_id, col_name)
                if val is None:
                    null_count += 1
                else:
                    values.append(val)

            distinct = len(set(values))
            comparable = [v for v in values if isinstance(v, (int, float, str))]
            min_val = min(comparable) if comparable else None
            max_val = max(comparable) if comparable else None

            stats[col_name] = ColumnStats(
                distinct_count=distinct,
                null_count=null_count,
                min_value=min_val,
                max_value=max_val,
                row_count=n,
            )

        self._stats = stats
        return stats

    def get_column_stats(self, col_name: str) -> ColumnStats | None:
        """Return cached statistics for a column, or None if not analyzed."""
        return self._stats.get(col_name)


def resolve_type(type_names: tuple) -> tuple[str, type]:
    """Map a pglast TypeName.names tuple to (canonical_name, python_type)."""
    # TypeName.names is e.g. ('pg_catalog', 'int4') or ('text',)
    raw = type_names[-1].sval.lower()
    python_type = _SQL_TYPE_MAP.get(raw)
    if python_type is None:
        raise ValueError(f"Unsupported column type: {raw}")
    return raw, python_type
