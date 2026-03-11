#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for the Volcano execution engine.

Measures operator throughput in rows/sec for scan, filter, project,
sort, aggregate, distinct, and window operators.
"""

from __future__ import annotations

import pytest

from uqa.engine import Engine
from benchmarks.data.generators import BenchmarkDataGenerator
from benchmarks.data.schemas import BENCH_TABLE_DDL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_with_data(n: int) -> Engine:
    """Create an engine with *n* rows in the bench table."""
    e = Engine()
    e.sql(BENCH_TABLE_DDL)
    gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
    rows = gen.table_rows(num_rows=n)
    for row in rows:
        active_str = "TRUE" if row["active"] else "FALSE"
        e.sql(
            f"INSERT INTO bench VALUES ("
            f"{row['id']}, '{row['name']}', {row['value']}, "
            f"'{row['category']}', {row['quantity']}, {active_str})"
        )
    return e


# ---------------------------------------------------------------------------
# Sequential Scan
# ---------------------------------------------------------------------------

class TestSeqScan:
    @pytest.mark.parametrize("n", [100, 500, 1000])
    def test_full_scan(self, benchmark, n: int) -> None:
        e = _engine_with_data(n)
        result = benchmark(e.sql, "SELECT * FROM bench")
        assert len(result) == n


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

class TestFilter:
    def test_high_selectivity(self, benchmark) -> None:
        """~90% of rows pass the filter."""
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT * FROM bench WHERE value > 500")

    def test_low_selectivity(self, benchmark) -> None:
        """~1% of rows pass the filter."""
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT * FROM bench WHERE value > 9900")

    def test_compound_filter(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(
            e.sql,
            "SELECT * FROM bench WHERE value > 100 AND quantity < 500 AND category = 'cat_0'",
        )


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class TestProject:
    def test_simple_project(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT id, name, value FROM bench")

    def test_expr_project(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(
            e.sql,
            "SELECT id, value * quantity AS total, "
            "CASE WHEN value > 500 THEN 'high' ELSE 'low' END AS tier FROM bench",
        )


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

class TestSort:
    def test_single_column(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT * FROM bench ORDER BY value")

    def test_multi_column(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT * FROM bench ORDER BY category, value DESC")

    def test_sort_with_limit(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT * FROM bench ORDER BY value DESC LIMIT 10")


# ---------------------------------------------------------------------------
# Hash Aggregate
# ---------------------------------------------------------------------------

class TestHashAggregate:
    def test_count_group_by(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT category, COUNT(*) FROM bench GROUP BY category")

    def test_sum_avg_group_by(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(
            e.sql,
            "SELECT category, SUM(value), AVG(quantity) FROM bench GROUP BY category",
        )

    def test_high_cardinality_group(self, benchmark) -> None:
        """Group by a column with many distinct values."""
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT name, COUNT(*) FROM bench GROUP BY name")


# ---------------------------------------------------------------------------
# Distinct
# ---------------------------------------------------------------------------

class TestDistinct:
    def test_low_cardinality(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT DISTINCT category FROM bench")

    def test_high_cardinality(self, benchmark) -> None:
        e = _engine_with_data(1000)
        benchmark(e.sql, "SELECT DISTINCT name FROM bench")


# ---------------------------------------------------------------------------
# Window Functions
# ---------------------------------------------------------------------------

class TestWindow:
    def test_row_number(self, benchmark) -> None:
        e = _engine_with_data(500)
        benchmark(
            e.sql,
            "SELECT id, ROW_NUMBER() OVER (ORDER BY value DESC) AS rn FROM bench",
        )

    def test_rank_partitioned(self, benchmark) -> None:
        e = _engine_with_data(500)
        benchmark(
            e.sql,
            "SELECT id, category, "
            "RANK() OVER (PARTITION BY category ORDER BY value DESC) AS rnk "
            "FROM bench",
        )

    def test_sum_window(self, benchmark) -> None:
        e = _engine_with_data(500)
        benchmark(
            e.sql,
            "SELECT id, SUM(value) OVER (ORDER BY id) AS running_sum FROM bench",
        )


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------

class TestLimit:
    @pytest.mark.parametrize("limit", [10, 100])
    def test_limit(self, benchmark, limit: int) -> None:
        e = _engine_with_data(1000)
        result = benchmark(e.sql, f"SELECT * FROM bench LIMIT {limit}")
        assert len(result) == limit


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_scan_filter_project_sort_limit(self, benchmark) -> None:
        e = _engine_with_data(1000)
        sql = (
            "SELECT id, name, value * quantity AS total "
            "FROM bench "
            "WHERE value > 100 AND quantity > 0 "
            "ORDER BY total DESC "
            "LIMIT 50"
        )
        benchmark(e.sql, sql)

    def test_scan_group_sort(self, benchmark) -> None:
        e = _engine_with_data(1000)
        sql = (
            "SELECT category, COUNT(*) AS cnt, SUM(value) AS total "
            "FROM bench "
            "GROUP BY category "
            "ORDER BY total DESC"
        )
        benchmark(e.sql, sql)
