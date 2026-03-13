#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for disk spilling in blocking operators.

Verifies that SortOp, HashAggOp, and DistinctOp produce correct results
when the input exceeds the spill threshold and data is written to
temporary Arrow IPC files on disk.
"""

from __future__ import annotations

import os
import tempfile

from uqa.execution.batch import DEFAULT_BATCH_SIZE, Batch
from uqa.execution.physical import PhysicalOperator
from uqa.execution.relational import (
    DistinctOp,
    HashAggOp,
    SortOp,
)

# -- Helpers ---------------------------------------------------------------


class RowSourceOp(PhysicalOperator):
    """Emit pre-built rows as batches for testing."""

    def __init__(self, rows: list[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._rows = rows
        self._batch_size = batch_size
        self._offset = 0

    def open(self) -> None:
        self._offset = 0

    def next(self) -> Batch | None:
        if self._offset >= len(self._rows):
            return None
        end = min(self._offset + self._batch_size, len(self._rows))
        batch_rows = self._rows[self._offset : end]
        self._offset = end
        return Batch.from_rows(batch_rows)

    def close(self) -> None:
        self._offset = 0


def _drain(op: PhysicalOperator) -> list[dict]:
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
# Spill infrastructure
# ======================================================================


class TestSpillManager:
    def test_lifecycle(self):
        from uqa.execution.spill import SpillManager, SpillWriter

        mgr = SpillManager()
        p1 = mgr.new_path()
        p2 = mgr.new_path()
        assert p1 != p2
        assert os.path.isdir(mgr._temp_dir)

        # Write something so the files exist.
        for p in [p1, p2]:
            w = SpillWriter(p)
            w.write_rows([{"a": 1}])
            w.close()
            assert os.path.isfile(p)

        mgr.cleanup()
        assert not os.path.isfile(p1)
        assert not os.path.isfile(p2)

    def test_write_and_read(self):
        from uqa.execution.spill import SpillWriter, read_rows_from_ipc

        path = os.path.join(tempfile.mkdtemp(), "test.arrow")
        writer = SpillWriter(path)
        writer.write_rows([{"x": 1, "y": "a"}, {"x": 2, "y": "b"}])
        writer.write_rows([{"x": 3, "y": "c"}])
        writer.close()
        assert writer.row_count == 3

        rows = list(read_rows_from_ipc(path))
        assert len(rows) == 3
        assert rows[0]["x"] == 1
        assert rows[2]["y"] == "c"
        os.unlink(path)


class TestMergeSortedRuns:
    def test_single_run(self):
        from uqa.execution.spill import merge_sorted_runs

        run = iter([{"v": 1}, {"v": 3}, {"v": 5}])
        merged = list(merge_sorted_runs([run], [("v", False)]))
        assert [r["v"] for r in merged] == [1, 3, 5]

    def test_two_runs_asc(self):
        from uqa.execution.spill import merge_sorted_runs

        r1 = iter([{"v": 1}, {"v": 4}, {"v": 7}])
        r2 = iter([{"v": 2}, {"v": 3}, {"v": 8}])
        merged = list(merge_sorted_runs([r1, r2], [("v", False)]))
        assert [r["v"] for r in merged] == [1, 2, 3, 4, 7, 8]

    def test_two_runs_desc(self):
        from uqa.execution.spill import merge_sorted_runs

        r1 = iter([{"v": 7}, {"v": 4}, {"v": 1}])
        r2 = iter([{"v": 8}, {"v": 3}, {"v": 2}])
        merged = list(merge_sorted_runs([r1, r2], [("v", True)]))
        assert [r["v"] for r in merged] == [8, 7, 4, 3, 2, 1]

    def test_nulls_asc(self):
        from uqa.execution.spill import merge_sorted_runs

        r1 = iter([{"v": 1}, {"v": None}])
        r2 = iter([{"v": 2}])
        merged = list(merge_sorted_runs([r1, r2], [("v", False)]))
        vals = [r["v"] for r in merged]
        assert vals == [1, 2, None]

    def test_nulls_desc(self):
        from uqa.execution.spill import merge_sorted_runs

        r1 = iter([{"v": None}, {"v": 1}])
        r2 = iter([{"v": 2}])
        merged = list(merge_sorted_runs([r1, r2], [("v", True)]))
        vals = [r["v"] for r in merged]
        assert vals == [None, 2, 1]

    def test_empty_runs(self):
        from uqa.execution.spill import merge_sorted_runs

        merged = list(merge_sorted_runs([], [("v", False)]))
        assert merged == []


# ======================================================================
# SortOp with spilling
# ======================================================================


class TestSortOpSpill:
    def test_no_spill_small_input(self):
        rows = [{"v": 3}, {"v": 1}, {"v": 2}]
        op = SortOp(RowSourceOp(rows), [("v", False)], spill_threshold=100)
        result = _drain(op)
        assert [r["v"] for r in result] == [1, 2, 3]

    def test_spill_single_run(self):
        """Threshold exceeded once -> one spilled run + in-memory remainder."""
        rows = [{"v": i} for i in range(20, 0, -1)]
        op = SortOp(RowSourceOp(rows), [("v", False)], spill_threshold=10)
        result = _drain(op)
        assert [r["v"] for r in result] == list(range(1, 21))

    def test_spill_multiple_runs(self):
        """Threshold forces multiple spilled runs."""
        rows = [{"v": i} for i in range(100, 0, -1)]
        op = SortOp(RowSourceOp(rows), [("v", False)], spill_threshold=20)
        result = _drain(op)
        assert [r["v"] for r in result] == list(range(1, 101))

    def test_spill_descending(self):
        rows = [{"v": i} for i in range(1, 51)]
        op = SortOp(RowSourceOp(rows), [("v", True)], spill_threshold=15)
        result = _drain(op)
        assert [r["v"] for r in result] == list(range(50, 0, -1))

    def test_spill_multi_key(self):
        rows = [
            {"a": 2, "b": 1},
            {"a": 1, "b": 2},
            {"a": 1, "b": 1},
            {"a": 2, "b": 2},
        ]
        op = SortOp(
            RowSourceOp(rows),
            [("a", False), ("b", False)],
            spill_threshold=2,
        )
        result = _drain(op)
        assert [(r["a"], r["b"]) for r in result] == [
            (1, 1),
            (1, 2),
            (2, 1),
            (2, 2),
        ]

    def test_spill_with_nulls(self):
        rows = [{"v": 3}, {"v": None}, {"v": 1}]
        op = SortOp(RowSourceOp(rows), [("v", False)], spill_threshold=2)
        result = _drain(op)
        assert [r["v"] for r in result] == [1, 3, None]

    def test_spill_cleanup(self):
        rows = [{"v": i} for i in range(20, 0, -1)]
        op = SortOp(RowSourceOp(rows), [("v", False)], spill_threshold=5)
        op.open()
        assert op._spill_mgr is not None
        temp_dir = op._spill_mgr._temp_dir
        assert os.path.isdir(temp_dir)
        while op.next() is not None:
            pass
        op.close()
        assert not os.path.isdir(temp_dir)

    def test_spill_empty_input(self):
        op = SortOp(RowSourceOp([]), [("v", False)], spill_threshold=5)
        result = _drain(op)
        assert result == []


# ======================================================================
# HashAggOp with spilling
# ======================================================================


class TestHashAggOpSpill:
    def test_no_spill_small_input(self):
        rows = [
            {"g": "a", "v": 1},
            {"g": "b", "v": 2},
            {"g": "a", "v": 3},
        ]
        op = HashAggOp(
            RowSourceOp(rows),
            ["g"],
            [("total", "sum", "v")],
            spill_threshold=100,
        )
        result = _drain(op)
        by_g = {r["g"]: r["total"] for r in result}
        assert by_g == {"a": 4, "b": 2}

    def test_spill_groupby(self):
        rows = [{"g": i % 5, "v": i} for i in range(100)]
        op = HashAggOp(
            RowSourceOp(rows),
            ["g"],
            [("cnt", "count", None), ("total", "sum", "v")],
            spill_threshold=30,
        )
        result = _drain(op)
        assert len(result) == 5
        by_g = {r["g"]: r for r in result}
        for g in range(5):
            assert by_g[g]["cnt"] == 20
            assert by_g[g]["total"] == sum(i for i in range(100) if i % 5 == g)

    def test_spill_aggregate_only(self):
        rows = [{"v": i} for i in range(50)]
        op = HashAggOp(
            RowSourceOp(rows),
            [],
            [("cnt", "count", None)],
            spill_threshold=20,
        )
        result = _drain(op)
        assert len(result) == 1
        assert result[0]["cnt"] == 50

    def test_spill_empty_input(self):
        op = HashAggOp(
            RowSourceOp([]),
            [],
            [("cnt", "count", None)],
            spill_threshold=10,
        )
        result = _drain(op)
        assert len(result) == 1
        assert result[0]["cnt"] == 0

    def test_spill_cleanup(self):
        rows = [{"g": i % 3, "v": i} for i in range(60)]
        op = HashAggOp(
            RowSourceOp(rows),
            ["g"],
            [("cnt", "count", None)],
            spill_threshold=20,
        )
        op.open()
        assert op._spill_mgr is not None
        temp_dir = op._spill_mgr._temp_dir
        assert os.path.isdir(temp_dir)
        while op.next() is not None:
            pass
        op.close()
        assert not os.path.isdir(temp_dir)


# ======================================================================
# DistinctOp with spilling
# ======================================================================


class TestDistinctOpSpill:
    def test_no_spill_small_input(self):
        rows = [{"v": 1}, {"v": 2}, {"v": 1}, {"v": 3}]
        op = DistinctOp(
            RowSourceOp(rows),
            ["v"],
            spill_threshold=100,
        )
        result = _drain(op)
        assert sorted(r["v"] for r in result) == [1, 2, 3]

    def test_spill_dedup(self):
        rows = [{"v": i % 10} for i in range(200)]
        op = DistinctOp(
            RowSourceOp(rows),
            ["v"],
            spill_threshold=50,
        )
        result = _drain(op)
        assert sorted(r["v"] for r in result) == list(range(10))

    def test_spill_multi_column(self):
        rows = [{"a": i % 3, "b": i % 5} for i in range(100)]
        op = DistinctOp(
            RowSourceOp(rows),
            ["a", "b"],
            spill_threshold=30,
        )
        result = _drain(op)
        keys = sorted((r["a"], r["b"]) for r in result)
        expected = sorted((i % 3, i % 5) for i in range(15))
        assert keys == expected

    def test_spill_empty_input(self):
        op = DistinctOp(
            RowSourceOp([]),
            ["v"],
            spill_threshold=5,
        )
        result = _drain(op)
        assert result == []

    def test_spill_cleanup(self):
        rows = [{"v": i % 5} for i in range(100)]
        op = DistinctOp(
            RowSourceOp(rows),
            ["v"],
            spill_threshold=20,
        )
        op.open()
        assert op._spill_mgr is not None
        temp_dir = op._spill_mgr._temp_dir
        assert os.path.isdir(temp_dir)
        while op.next() is not None:
            pass
        op.close()
        assert not os.path.isdir(temp_dir)


# ======================================================================
# SQL integration with spill_threshold
# ======================================================================


class TestSQLSpillIntegration:
    def test_sort_via_sql(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db, spill_threshold=10) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, v INTEGER)")
            for i in range(30, 0, -1):
                engine.sql(f"INSERT INTO t (v) VALUES ({i})")
            rows = engine.sql("SELECT v FROM t ORDER BY v ASC")
            assert [r["v"] for r in rows] == list(range(1, 31))

    def test_groupby_via_sql(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db, spill_threshold=10) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, g INTEGER, v INTEGER)")
            for i in range(50):
                engine.sql(f"INSERT INTO t (g, v) VALUES ({i % 5}, {i})")
            rows = engine.sql("SELECT g, COUNT(*) AS cnt FROM t GROUP BY g ORDER BY g")
            assert len(rows) == 5
            assert all(r["cnt"] == 10 for r in rows)

    def test_distinct_via_sql(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db, spill_threshold=10) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, v INTEGER)")
            for i in range(40):
                engine.sql(f"INSERT INTO t (v) VALUES ({i % 8})")
            rows = engine.sql("SELECT DISTINCT v FROM t ORDER BY v")
            assert [r["v"] for r in rows] == list(range(8))
