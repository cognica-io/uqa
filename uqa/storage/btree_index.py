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

import json
import math
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from uqa.storage.index_types import IndexDef
    from uqa.storage.managed_connection import SQLiteConnection


class BTreeIndex(Index):
    """B-tree index backed by a SQLite CREATE INDEX."""

    def __init__(self, index_def: IndexDef, conn: SQLiteConnection) -> None:
        super().__init__(index_def, conn)
        self._table_name = index_def.table_name

    def build(self) -> None:
        cols = ", ".join(
            f"json_extract(body, {self._json_path_sql(c)})"
            for c in self._index_def.columns
        )
        table_literal = self._sql_string(self._table_name)
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{self._index_def.name}" '
            f"ON _documents ({cols}) WHERE table_name = {table_literal}"
        )
        self._conn.commit()

    def drop(self) -> None:
        self._conn.execute(f'DROP INDEX IF EXISTS "{self._index_def.name}"')
        self._conn.commit()

    def scan(self, predicate: Predicate) -> PostingList:
        where_clause, params = self._predicate_to_sql(predicate)
        sql = (
            "SELECT doc_id FROM _documents "
            f"WHERE table_name = ? AND {where_clause} ORDER BY doc_id"
        )
        rows = self._conn.execute(sql, [self._table_name, *params]).fetchall()
        entries = [PostingEntry(row[0], Payload(score=0.0)) for row in rows]
        return PostingList.from_sorted(entries)

    def estimate_cardinality(self, predicate: Predicate) -> int:
        where_clause, params = self._predicate_to_sql(predicate)
        sql = (
            "SELECT COUNT(*) FROM _documents "
            f"WHERE table_name = ? AND {where_clause}"
        )
        row = self._conn.execute(sql, [self._table_name, *params]).fetchone()
        return row[0] if row else 0

    def scan_cost(self, predicate: Predicate) -> float:
        total = self._total_rows()
        if total == 0:
            return 0.0
        estimated = self.estimate_cardinality(predicate)
        return math.log2(total) + estimated

    def _total_rows(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM _documents WHERE table_name = ?",
            (self._table_name,),
        ).fetchone()
        return row[0] if row else 0

    def _predicate_to_sql(self, predicate: Predicate) -> tuple[str, list]:
        col = f"json_extract(body, {self._json_path_sql(self._index_def.columns[0])})"

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
            f"BTreeIndex cannot handle predicate type: {type(predicate).__name__}"
        )

    @staticmethod
    def _json_path_sql(column_name: str) -> str:
        return BTreeIndex._sql_string("$." + json.dumps(column_name))

    @staticmethod
    def _sql_string(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
