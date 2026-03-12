#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite B-tree index wrapper.

Translates UQA Predicate objects into SQL WHERE clauses and executes
index-backed scans on the underlying ``_data_{table}`` SQLite table.
"""

from __future__ import annotations

import math
import sqlite3

from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Between,
    Equals,
    GreaterThan,
    GreaterThanOrEqual,
    InSet,
    LessThan,
    LessThanOrEqual,
    NotEquals,
    Payload,
    PostingEntry,
    Predicate,
)
from uqa.storage.index_abc import Index
from uqa.storage.index_types import IndexDef


class BTreeIndex(Index):
    """B-tree index backed by a SQLite CREATE INDEX."""

    def __init__(self, index_def: IndexDef, conn: sqlite3.Connection) -> None:
        super().__init__(index_def, conn)
        self._data_table = f"_data_{index_def.table_name}"

    def build(self) -> None:
        cols = ", ".join(
            f'"{c}"' for c in self._index_def.columns
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{self._index_def.name}" '
            f'ON "{self._data_table}" ({cols})'
        )
        self._conn.commit()

    def drop(self) -> None:
        self._conn.execute(
            f'DROP INDEX IF EXISTS "{self._index_def.name}"'
        )
        self._conn.commit()

    def scan(self, predicate: Predicate) -> PostingList:
        where_clause, params = self._predicate_to_sql(predicate)
        sql = (
            f'SELECT _rowid FROM "{self._data_table}" '
            f"WHERE {where_clause} ORDER BY _rowid"
        )
        rows = self._conn.execute(sql, params).fetchall()
        entries = [
            PostingEntry(row[0], Payload(score=0.0))
            for row in rows
        ]
        return PostingList.from_sorted(entries)

    def estimate_cardinality(self, predicate: Predicate) -> int:
        where_clause, params = self._predicate_to_sql(predicate)
        sql = (
            f'SELECT COUNT(*) FROM "{self._data_table}" '
            f"WHERE {where_clause}"
        )
        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    def scan_cost(self, predicate: Predicate) -> float:
        total = self._total_rows()
        if total == 0:
            return 0.0
        estimated = self.estimate_cardinality(predicate)
        return math.log2(total) + estimated

    def _total_rows(self) -> int:
        row = self._conn.execute(
            f'SELECT COUNT(*) FROM "{self._data_table}"'
        ).fetchone()
        return row[0] if row else 0

    def _predicate_to_sql(
        self, predicate: Predicate
    ) -> tuple[str, list]:
        col = f'"{self._index_def.columns[0]}"'

        if isinstance(predicate, Equals):
            return f"{col} = ?", [predicate.target]
        if isinstance(predicate, NotEquals):
            return f"{col} != ?", [predicate.target]
        if isinstance(predicate, GreaterThan):
            return f"{col} > ?", [predicate.target]
        if isinstance(predicate, GreaterThanOrEqual):
            return f"{col} >= ?", [predicate.target]
        if isinstance(predicate, LessThan):
            return f"{col} < ?", [predicate.target]
        if isinstance(predicate, LessThanOrEqual):
            return f"{col} <= ?", [predicate.target]
        if isinstance(predicate, Between):
            return f"{col} BETWEEN ? AND ?", [predicate.low, predicate.high]
        if isinstance(predicate, InSet):
            placeholders = ", ".join("?" for _ in predicate.values)
            return f"{col} IN ({placeholders})", list(predicate.values)

        raise ValueError(
            f"BTreeIndex cannot handle predicate type: "
            f"{type(predicate).__name__}"
        )
