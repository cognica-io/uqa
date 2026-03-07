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

import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from uqa.storage.document_store import DocumentStore
from uqa.storage.inverted_index import IndexedTerms, InvertedIndex
from uqa.storage.sqlite_document_store import SQLiteDocumentStore
from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex


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
    """Per-column statistics for cardinality estimation (Definition 6.2.3, Paper 1).

    Attributes:
        distinct_count: Number of distinct non-NULL values.
        null_count: Number of NULL values.
        min_value: Minimum value.
        max_value: Maximum value.
        row_count: Total number of rows.
        histogram: Equi-depth histogram bucket boundaries (sorted).
            For *b* buckets, this is a list of *b+1* boundary values.
            Each bucket [boundary[i], boundary[i+1]) contains roughly
            the same number of rows.
        mcv_values: Most common values, sorted by descending frequency.
        mcv_frequencies: Frequency (fraction) of each MCV value.
    """

    distinct_count: int = 0
    null_count: int = 0
    min_value: Any = None
    max_value: Any = None
    row_count: int = 0
    histogram: list[Any] = field(default_factory=list)
    mcv_values: list[Any] = field(default_factory=list)
    mcv_frequencies: list[float] = field(default_factory=list)

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

    When *conn* is provided the table uses SQLite-backed stores that
    persist reads/writes directly to the database.  When *conn* is
    ``None`` (the default) the table uses in-memory stores.
    """

    def __init__(
        self,
        name: str,
        columns: list[ColumnDef],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.name = name
        self.columns: OrderedDict[str, ColumnDef] = OrderedDict(
            (col.name, col) for col in columns
        )
        self.primary_key: str | None = next(
            (col.name for col in columns if col.primary_key), None
        )

        if conn is not None:
            col_pairs = [(col.name, col.type_name) for col in columns]
            self.document_store: DocumentStore | SQLiteDocumentStore = (
                SQLiteDocumentStore(conn, name, col_pairs)
            )
            self.inverted_index: InvertedIndex | SQLiteInvertedIndex = (
                SQLiteInvertedIndex(conn, name)
            )
        else:
            self.document_store = DocumentStore()
            self.inverted_index = InvertedIndex()

        self._next_id = 1
        self._stats: dict[str, ColumnStats] = {}

    def insert(self, row: dict[str, Any]) -> tuple[int, IndexedTerms | None]:
        """Insert a row and return (doc_id, indexed_terms).

        ``indexed_terms`` is non-None when text fields were indexed,
        allowing the caller to persist posting entries to the catalog.
        """

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

        indexed: IndexedTerms | None = None
        text_fields = {k: v for k, v in coerced.items() if isinstance(v, str)}
        if text_fields:
            indexed = self.inverted_index.add_document(doc_id, text_fields)

        return doc_id, indexed

    @property
    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    @property
    def row_count(self) -> int:
        return len(self.document_store.doc_ids)

    _HISTOGRAM_BUCKETS = 100
    _MCV_COUNT = 10

    def analyze(self) -> dict[str, ColumnStats]:
        """Collect per-column statistics by scanning all rows.

        Computes distinct count, null count, min/max, equi-depth
        histogram, and most-common-value (MCV) list for each column.
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
            comparable = [
                v for v in values if isinstance(v, (int, float, str))
            ]
            min_val = min(comparable) if comparable else None
            max_val = max(comparable) if comparable else None

            histogram = self._build_histogram(comparable)
            mcv_values, mcv_frequencies = self._build_mcv(
                values, n
            )

            stats[col_name] = ColumnStats(
                distinct_count=distinct,
                null_count=null_count,
                min_value=min_val,
                max_value=max_val,
                row_count=n,
                histogram=histogram,
                mcv_values=mcv_values,
                mcv_frequencies=mcv_frequencies,
            )

        self._stats = stats
        return stats

    @classmethod
    def _build_histogram(cls, values: list[Any]) -> list[Any]:
        """Build equi-depth histogram boundaries from sorted values.

        Returns a list of boundary values defining bucket edges.
        For *b* buckets there are *b+1* boundaries.
        """
        if not values:
            return []
        try:
            sorted_vals = sorted(values)
        except TypeError:
            return []

        n = len(sorted_vals)
        num_buckets = min(cls._HISTOGRAM_BUCKETS, n)
        if num_buckets <= 1:
            return [sorted_vals[0], sorted_vals[-1]]

        boundaries: list[Any] = [sorted_vals[0]]
        for i in range(1, num_buckets):
            idx = (i * n) // num_buckets
            val = sorted_vals[idx]
            if val != boundaries[-1]:
                boundaries.append(val)
        if boundaries[-1] != sorted_vals[-1]:
            boundaries.append(sorted_vals[-1])
        return boundaries

    @classmethod
    def _build_mcv(
        cls, values: list[Any], total: int
    ) -> tuple[list[Any], list[float]]:
        """Build most-common-value list with frequencies.

        Returns (values, frequencies) where frequencies are fractions
        of total row count.  Only values appearing more than 1/NDV
        are included (i.e., above-average frequency).
        """
        if not values or total <= 0:
            return [], []

        from collections import Counter

        counts = Counter(values)
        ndv = len(counts)
        if ndv <= 0:
            return [], []

        avg_freq = 1.0 / ndv
        above_avg = [
            (val, cnt)
            for val, cnt in counts.most_common(cls._MCV_COUNT)
            if cnt / total > avg_freq
        ]
        if not above_avg:
            return [], []

        mcv_values = [val for val, _ in above_avg]
        mcv_frequencies = [cnt / total for _, cnt in above_avg]
        return mcv_values, mcv_frequencies

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
