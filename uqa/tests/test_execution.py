#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Phase 4: Volcano Execution Engine.

Covers:
- Batch and ColumnVector data structures
- SeqScanOp (sequential table scan)
- PostingListScanOp (PostingList-to-batch bridge)
- FilterOp (predicate evaluation)
- ProjectOp (column selection)
- SortOp (blocking sort)
- LimitOp (streaming limit)
- HashAggOp (blocking GROUP BY + aggregation)
- DistinctOp (blocking deduplication)
- Operator composition (multi-operator pipelines)
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Equals,
    GreaterThan,
    LessThan,
    Between,
    InSet,
    Payload,
    PostingEntry,
)
from uqa.execution.batch import (
    Batch,
    ColumnVector,
    DataType,
    DEFAULT_BATCH_SIZE,
    _infer_dtype,
)
from uqa.execution.physical import PhysicalOperator
from uqa.execution.relational import (
    DistinctOp,
    FilterOp,
    HashAggOp,
    LimitOp,
    ProjectOp,
    SortOp,
)
from uqa.execution.scan import PostingListScanOp, SeqScanOp
from uqa.storage.document_store import DocumentStore
from uqa.sql.table import ColumnDef, Table


# ======================================================================
# Helpers
# ======================================================================


def _make_table(rows: list[dict], name: str = "t") -> Table:
    """Create an in-memory table and insert rows."""
    columns = [
        ColumnDef(
            name="id",
            type_name="serial",
            python_type=int,
            primary_key=True,
            auto_increment=True,
        ),
        ColumnDef(name="name", type_name="text", python_type=str),
        ColumnDef(name="age", type_name="integer", python_type=int),
        ColumnDef(name="score", type_name="real", python_type=float),
    ]
    table = Table(name, columns)
    for row in rows:
        table.insert(row)
    return table


def _collect_rows(op: PhysicalOperator) -> list[dict]:
    """Run an operator pipeline and collect all rows."""
    op.open()
    rows: list[dict] = []
    while True:
        batch = op.next()
        if batch is None:
            break
        rows.extend(batch.to_rows())
    op.close()
    return rows


# ======================================================================
# ColumnVector
# ======================================================================


class TestColumnVector:
    def test_integer_vector(self):
        cv = ColumnVector.from_values([1, 2, None, 4], DataType.INTEGER)
        assert len(cv) == 4
        assert cv[0] == 1
        assert cv[1] == 2
        assert cv[2] is None
        assert cv[3] == 4
        assert isinstance(cv.data, np.ndarray)
        assert cv.data.dtype == np.int64

    def test_float_vector(self):
        cv = ColumnVector.from_values([1.5, None, 3.5], DataType.FLOAT)
        assert cv[0] == 1.5
        assert cv[1] is None
        assert cv[2] == 3.5
        assert cv.data.dtype == np.float64

    def test_text_vector(self):
        cv = ColumnVector.from_values(["a", None, "c"], DataType.TEXT)
        assert cv[0] == "a"
        assert cv[1] is None
        assert cv[2] == "c"
        assert isinstance(cv.data, list)

    def test_boolean_vector(self):
        cv = ColumnVector.from_values([True, False, None], DataType.BOOLEAN)
        assert cv[0] is True
        assert cv[1] is False
        assert cv[2] is None

    def test_select(self):
        cv = ColumnVector.from_values([10, 20, 30, 40], DataType.INTEGER)
        selected = cv.select(np.array([1, 3], dtype=np.intp))
        assert len(selected) == 2
        assert selected[0] == 20
        assert selected[1] == 40

    def test_select_text(self):
        cv = ColumnVector.from_values(["a", "b", "c"], DataType.TEXT)
        selected = cv.select(np.array([0, 2], dtype=np.intp))
        assert selected[0] == "a"
        assert selected[1] == "c"


# ======================================================================
# Batch
# ======================================================================


class TestBatch:
    def test_from_rows_basic(self):
        rows = [
            {"x": 1, "y": "a"},
            {"x": 2, "y": "b"},
        ]
        batch = Batch.from_rows(rows)
        assert batch.size == 2
        assert len(batch) == 2
        assert batch.column_names == ["x", "y"]

    def test_from_rows_with_schema(self):
        rows = [{"x": 1, "y": 1.5}]
        schema = {"x": DataType.INTEGER, "y": DataType.FLOAT}
        batch = Batch.from_rows(rows, schema)
        assert batch.column("x").dtype == DataType.INTEGER
        assert batch.column("y").dtype == DataType.FLOAT

    def test_to_rows_roundtrip(self):
        original = [
            {"x": 1, "y": "hello"},
            {"x": 2, "y": "world"},
        ]
        batch = Batch.from_rows(original)
        result = batch.to_rows()
        assert result == original

    def test_selection_vector(self):
        rows = [{"x": i} for i in range(5)]
        batch = Batch.from_rows(rows)
        batch = Batch(
            columns=batch.columns,
            selection=np.array([1, 3], dtype=np.intp),
            size=batch.size,
        )
        assert len(batch) == 2
        result = batch.to_rows()
        assert result == [{"x": 1}, {"x": 3}]

    def test_compact(self):
        rows = [{"x": i} for i in range(5)]
        batch = Batch.from_rows(rows)
        batch = Batch(
            columns=batch.columns,
            selection=np.array([0, 2, 4], dtype=np.intp),
            size=batch.size,
        )
        compacted = batch.compact()
        assert compacted.size == 3
        assert compacted.selection is None
        assert compacted.to_rows() == [{"x": 0}, {"x": 2}, {"x": 4}]

    def test_compact_noop(self):
        rows = [{"x": 1}]
        batch = Batch.from_rows(rows)
        assert batch.compact() is batch

    def test_empty_batch(self):
        batch = Batch.from_rows([])
        assert batch.size == 0
        assert len(batch) == 0
        assert batch.to_rows() == []

    def test_null_handling(self):
        rows = [{"x": 1, "y": None}, {"x": None, "y": "hi"}]
        batch = Batch.from_rows(rows)
        result = batch.to_rows()
        assert result[0]["y"] is None
        assert result[1]["x"] is None


# ======================================================================
# DataType inference
# ======================================================================


class TestDataTypeInference:
    def test_infer_int(self):
        assert _infer_dtype(42) == DataType.INTEGER

    def test_infer_float(self):
        assert _infer_dtype(3.14) == DataType.FLOAT

    def test_infer_text(self):
        assert _infer_dtype("hello") == DataType.TEXT

    def test_infer_bool(self):
        assert _infer_dtype(True) == DataType.BOOLEAN

    def test_infer_bytes(self):
        assert _infer_dtype(b"data") == DataType.BYTES


# ======================================================================
# SeqScanOp
# ======================================================================


class TestSeqScanOp:
    def test_scan_empty_table(self):
        table = _make_table([])
        rows = _collect_rows(SeqScanOp(table))
        assert rows == []

    def test_scan_all_rows(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 35, "score": 9.0},
        ])
        rows = _collect_rows(SeqScanOp(table))
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"
        assert rows[2]["name"] == "Carol"

    def test_includes_doc_id(self):
        table = _make_table([{"name": "Alice", "age": 30, "score": 9.5}])
        rows = _collect_rows(SeqScanOp(table))
        assert "_doc_id" in rows[0]
        assert rows[0]["_doc_id"] == rows[0]["id"]

    def test_batch_size_respected(self):
        table = _make_table([
            {"name": f"user{i}", "age": 20 + i, "score": float(i)}
            for i in range(5)
        ])
        op = SeqScanOp(table, batch_size=2)
        op.open()

        batch1 = op.next()
        assert batch1 is not None
        assert batch1.size == 2

        batch2 = op.next()
        assert batch2 is not None
        assert batch2.size == 2

        batch3 = op.next()
        assert batch3 is not None
        assert batch3.size == 1

        assert op.next() is None
        op.close()

    def test_reopen(self):
        table = _make_table([{"name": "Alice", "age": 30, "score": 9.5}])
        op = SeqScanOp(table)

        rows1 = _collect_rows(op)
        rows2 = _collect_rows(op)
        assert rows1 == rows2


# ======================================================================
# PostingListScanOp
# ======================================================================


class TestPostingListScanOp:
    def test_basic(self):
        store = DocumentStore()
        store.put(1, {"name": "Alice", "age": 30})
        store.put(2, {"name": "Bob", "age": 25})

        pl = PostingList([
            PostingEntry(1, Payload(score=0.9)),
            PostingEntry(2, Payload(score=0.8)),
        ])

        rows = _collect_rows(PostingListScanOp(pl, store))
        assert len(rows) == 2
        assert rows[0]["_doc_id"] == 1
        assert rows[0]["_score"] == 0.9
        assert rows[0]["name"] == "Alice"
        assert rows[1]["_doc_id"] == 2
        assert rows[1]["_score"] == 0.8

    def test_preserves_payload_fields(self):
        store = DocumentStore()
        store.put(1, {"name": "Alice"})

        pl = PostingList([
            PostingEntry(
                1,
                Payload(score=0.5, fields={"_extra": "data"}),
            ),
        ])

        rows = _collect_rows(PostingListScanOp(pl, store))
        assert rows[0]["_extra"] == "data"

    def test_empty_posting_list(self):
        store = DocumentStore()
        pl = PostingList([])
        rows = _collect_rows(PostingListScanOp(pl, store))
        assert rows == []

    def test_batch_size(self):
        store = DocumentStore()
        entries = []
        for i in range(5):
            store.put(i, {"x": i})
            entries.append(PostingEntry(i, Payload(score=float(i))))
        pl = PostingList(entries)

        op = PostingListScanOp(pl, store, batch_size=2)
        op.open()

        batch1 = op.next()
        assert batch1.size == 2
        batch2 = op.next()
        assert batch2.size == 2
        batch3 = op.next()
        assert batch3.size == 1
        assert op.next() is None
        op.close()


# ======================================================================
# FilterOp
# ======================================================================


class TestFilterOp:
    def test_equals_filter(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 9.0},
        ])
        op = FilterOp(SeqScanOp(table), "age", Equals(30))
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert all(r["age"] == 30 for r in rows)

    def test_greater_than_filter(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 35, "score": 9.0},
        ])
        op = FilterOp(SeqScanOp(table), "age", GreaterThan(28))
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert {r["name"] for r in rows} == {"Alice", "Carol"}

    def test_between_filter(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 35, "score": 9.0},
        ])
        op = FilterOp(SeqScanOp(table), "age", Between(26, 34))
        rows = _collect_rows(op)
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_in_set_filter(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 35, "score": 9.0},
        ])
        op = FilterOp(
            SeqScanOp(table), "name", InSet(frozenset({"Alice", "Carol"}))
        )
        rows = _collect_rows(op)
        assert len(rows) == 2

    def test_filter_no_match(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = FilterOp(SeqScanOp(table), "age", Equals(99))
        rows = _collect_rows(op)
        assert rows == []

    def test_filter_missing_column(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = FilterOp(SeqScanOp(table), "nonexistent", Equals(1))
        rows = _collect_rows(op)
        assert rows == []


# ======================================================================
# ProjectOp
# ======================================================================


class TestProjectOp:
    def test_basic_projection(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = ProjectOp(SeqScanOp(table), ["name", "age"])
        rows = _collect_rows(op)
        assert list(rows[0].keys()) == ["name", "age"]
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == 30

    def test_projection_with_alias(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = ProjectOp(
            SeqScanOp(table), ["name"], aliases={"name": "user_name"}
        )
        rows = _collect_rows(op)
        assert "user_name" in rows[0]
        assert rows[0]["user_name"] == "Alice"

    def test_single_column(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
        ])
        op = ProjectOp(SeqScanOp(table), ["name"])
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert list(rows[0].keys()) == ["name"]


# ======================================================================
# SortOp
# ======================================================================


class TestSortOp:
    def test_sort_ascending(self):
        table = _make_table([
            {"name": "Carol", "age": 35, "score": 9.0},
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
        ])
        op = SortOp(SeqScanOp(table), [("age", False)])
        rows = _collect_rows(op)
        assert [r["age"] for r in rows] == [25, 30, 35]

    def test_sort_descending(self):
        table = _make_table([
            {"name": "Carol", "age": 35, "score": 9.0},
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
        ])
        op = SortOp(SeqScanOp(table), [("age", True)])
        rows = _collect_rows(op)
        assert [r["age"] for r in rows] == [35, 30, 25]

    def test_sort_multiple_keys(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 30, "score": 8.0},
            {"name": "Carol", "age": 25, "score": 9.0},
        ])
        op = SortOp(
            SeqScanOp(table), [("age", False), ("score", True)]
        )
        rows = _collect_rows(op)
        assert rows[0]["name"] == "Carol"
        assert rows[1]["name"] == "Alice"
        assert rows[2]["name"] == "Bob"

    def test_sort_with_nulls(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "score": 8.0},
            {"name": "Carol", "age": 25, "score": 9.0},
        ])
        op = SortOp(SeqScanOp(table), [("age", False)])
        rows = _collect_rows(op)
        # Nulls sort last
        assert rows[0]["name"] == "Carol"
        assert rows[1]["name"] == "Alice"
        assert rows[2]["age"] is None

    def test_sort_batch_output(self):
        table = _make_table([
            {"name": f"user{i}", "age": 100 - i, "score": float(i)}
            for i in range(5)
        ])
        op = SortOp(SeqScanOp(table), [("age", False)], batch_size=2)
        op.open()

        batch1 = op.next()
        assert batch1.size == 2
        batch2 = op.next()
        assert batch2.size == 2
        batch3 = op.next()
        assert batch3.size == 1
        assert op.next() is None
        op.close()


# ======================================================================
# LimitOp
# ======================================================================


class TestLimitOp:
    def test_basic_limit(self):
        table = _make_table([
            {"name": f"user{i}", "age": 20 + i, "score": float(i)}
            for i in range(10)
        ])
        op = LimitOp(SeqScanOp(table), 3)
        rows = _collect_rows(op)
        assert len(rows) == 3

    def test_limit_larger_than_data(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = LimitOp(SeqScanOp(table), 100)
        rows = _collect_rows(op)
        assert len(rows) == 1

    def test_limit_zero(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
        ])
        op = LimitOp(SeqScanOp(table), 0)
        rows = _collect_rows(op)
        assert rows == []

    def test_limit_truncates_batch(self):
        table = _make_table([
            {"name": f"user{i}", "age": 20 + i, "score": float(i)}
            for i in range(10)
        ])
        op = LimitOp(SeqScanOp(table, batch_size=5), 3)
        op.open()
        batch = op.next()
        assert batch is not None
        assert batch.size == 3
        assert op.next() is None
        op.close()


# ======================================================================
# HashAggOp
# ======================================================================


class TestHashAggOp:
    def test_group_by_count(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 9.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=["age"],
            agg_specs=[("cnt", "count", None)],
        )
        rows = _collect_rows(op)
        result = {r["age"]: r["cnt"] for r in rows}
        assert result[30] == 2
        assert result[25] == 1

    def test_group_by_sum(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 9.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=["age"],
            agg_specs=[("total", "sum", "score")],
        )
        rows = _collect_rows(op)
        result = {r["age"]: r["total"] for r in rows}
        assert result[30] == pytest.approx(18.5)
        assert result[25] == pytest.approx(8.0)

    def test_group_by_avg(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 10.0},
            {"name": "Bob", "age": 30, "score": 8.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=["age"],
            agg_specs=[("avg_score", "avg", "score")],
        )
        rows = _collect_rows(op)
        assert rows[0]["avg_score"] == pytest.approx(9.0)

    def test_group_by_min_max(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 10.0},
            {"name": "Bob", "age": 30, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 9.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=["age"],
            agg_specs=[
                ("min_s", "min", "score"),
                ("max_s", "max", "score"),
            ],
        )
        rows = _collect_rows(op)
        assert rows[0]["min_s"] == pytest.approx(8.0)
        assert rows[0]["max_s"] == pytest.approx(10.0)

    def test_aggregate_only(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=[],
            agg_specs=[("cnt", "count", None)],
        )
        rows = _collect_rows(op)
        assert len(rows) == 1
        assert rows[0]["cnt"] == 2

    def test_aggregate_empty_table(self):
        table = _make_table([])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=[],
            agg_specs=[("cnt", "count", None)],
        )
        rows = _collect_rows(op)
        assert len(rows) == 1
        assert rows[0]["cnt"] == 0

    def test_count_column(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "score": 8.0},
        ])
        op = HashAggOp(
            SeqScanOp(table),
            group_columns=[],
            agg_specs=[("cnt", "count", "age")],
        )
        rows = _collect_rows(op)
        assert rows[0]["cnt"] == 1


# ======================================================================
# DistinctOp
# ======================================================================


class TestDistinctOp:
    def test_basic_distinct(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Alice", "age": 30, "score": 7.0},
        ])
        op = DistinctOp(
            ProjectOp(SeqScanOp(table), ["name", "age"]),
            columns=["name", "age"],
        )
        rows = _collect_rows(op)
        assert len(rows) == 2

    def test_all_unique(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
        ])
        op = DistinctOp(
            ProjectOp(SeqScanOp(table), ["name"]),
            columns=["name"],
        )
        rows = _collect_rows(op)
        assert len(rows) == 2

    def test_all_same(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Alice", "age": 30, "score": 8.0},
            {"name": "Alice", "age": 30, "score": 7.0},
        ])
        op = DistinctOp(
            ProjectOp(SeqScanOp(table), ["name"]),
            columns=["name"],
        )
        rows = _collect_rows(op)
        assert len(rows) == 1


# ======================================================================
# Operator composition
# ======================================================================


class TestComposition:
    def test_scan_filter_project(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 35, "score": 9.0},
        ])
        op = ProjectOp(
            FilterOp(SeqScanOp(table), "age", GreaterThan(28)),
            ["name", "age"],
        )
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert all("score" not in r for r in rows)
        assert {r["name"] for r in rows} == {"Alice", "Carol"}

    def test_scan_filter_sort_limit(self):
        table = _make_table([
            {"name": f"user{i}", "age": 20 + i, "score": float(i)}
            for i in range(20)
        ])
        op = LimitOp(
            SortOp(
                FilterOp(SeqScanOp(table), "age", GreaterThan(30)),
                [("age", True)],
            ),
            3,
        )
        rows = _collect_rows(op)
        assert len(rows) == 3
        assert rows[0]["age"] == 39
        assert rows[1]["age"] == 38
        assert rows[2]["age"] == 37

    def test_scan_group_sort(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 10.0},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 6.0},
            {"name": "Dave", "age": 25, "score": 9.0},
        ])
        op = SortOp(
            HashAggOp(
                SeqScanOp(table),
                group_columns=["age"],
                agg_specs=[
                    ("cnt", "count", None),
                    ("avg_score", "avg", "score"),
                ],
            ),
            [("age", False)],
        )
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert rows[0]["age"] == 25
        assert rows[0]["cnt"] == 2
        assert rows[0]["avg_score"] == pytest.approx(8.5)
        assert rows[1]["age"] == 30

    def test_posting_list_filter_sort_limit(self):
        store = DocumentStore()
        for i in range(10):
            store.put(i, {"x": i, "label": "even" if i % 2 == 0 else "odd"})

        entries = [
            PostingEntry(i, Payload(score=float(i) / 10))
            for i in range(10)
        ]
        pl = PostingList(entries)

        op = LimitOp(
            SortOp(
                FilterOp(
                    PostingListScanOp(pl, store),
                    "label",
                    Equals("even"),
                ),
                [("x", True)],
            ),
            3,
        )
        rows = _collect_rows(op)
        assert len(rows) == 3
        assert [r["x"] for r in rows] == [8, 6, 4]

    def test_full_pipeline(self):
        """Full pipeline: scan -> filter -> group -> sort -> limit."""
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 10.0},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Carol", "age": 30, "score": 6.0},
            {"name": "Dave", "age": 25, "score": 9.0},
            {"name": "Eve", "age": 35, "score": 7.0},
        ])
        op = LimitOp(
            SortOp(
                HashAggOp(
                    FilterOp(SeqScanOp(table), "age", LessThan(35)),
                    group_columns=["age"],
                    agg_specs=[("total", "sum", "score")],
                ),
                [("total", True)],
            ),
            1,
        )
        rows = _collect_rows(op)
        assert len(rows) == 1
        assert rows[0]["total"] == pytest.approx(17.0)

    def test_distinct_sort_limit(self):
        table = _make_table([
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": 25, "score": 8.0},
            {"name": "Alice", "age": 30, "score": 7.0},
            {"name": "Carol", "age": 35, "score": 9.0},
            {"name": "Bob", "age": 25, "score": 6.0},
        ])
        op = LimitOp(
            SortOp(
                DistinctOp(
                    ProjectOp(SeqScanOp(table), ["name", "age"]),
                    columns=["name"],
                ),
                [("age", False)],
            ),
            2,
        )
        rows = _collect_rows(op)
        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"
        assert rows[1]["name"] == "Alice"


# ======================================================================
# DEFAULT_BATCH_SIZE constant
# ======================================================================


class TestBatchSize:
    def test_default_value(self):
        assert DEFAULT_BATCH_SIZE == 1024
