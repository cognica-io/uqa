#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for the SQL compiler pipeline.

Measures pglast parsing time and UQA compilation time separately
to identify bottlenecks in the query processing pipeline.
"""

from __future__ import annotations

import pglast
import pytest

from uqa.engine import Engine
from benchmarks.data.generators import BenchmarkDataGenerator
from benchmarks.data.schemas import (
    BENCH_TABLE_DDL,
    CUSTOMERS_DDL,
    ORDERS_DDL,
    PRODUCTS_DDL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_with_tables() -> Engine:
    """Create an engine with schema definitions (no data needed for compile)."""
    e = Engine()
    e.sql(BENCH_TABLE_DDL)
    e.sql(CUSTOMERS_DDL)
    e.sql(PRODUCTS_DDL)
    e.sql(ORDERS_DDL)
    return e


# ---------------------------------------------------------------------------
# pglast parsing
# ---------------------------------------------------------------------------

class TestParse:
    def test_simple_select(self, benchmark) -> None:
        sql = "SELECT id, name FROM bench WHERE value > 100"
        benchmark(pglast.parse_sql, sql)

    def test_complex_join(self, benchmark) -> None:
        sql = (
            "SELECT o.id, c.name, p.name, o.amount "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "JOIN products p ON o.product_id = p.id "
            "WHERE o.amount > 100 AND c.region = 'region_1'"
        )
        benchmark(pglast.parse_sql, sql)

    def test_subquery(self, benchmark) -> None:
        sql = (
            "SELECT id, name FROM bench "
            "WHERE value > (SELECT AVG(value) FROM bench WHERE category = 'cat_1')"
        )
        benchmark(pglast.parse_sql, sql)

    def test_cte(self, benchmark) -> None:
        sql = (
            "WITH top_items AS ("
            "  SELECT id, value FROM bench WHERE value > 500 ORDER BY value DESC LIMIT 100"
            "), categories AS ("
            "  SELECT category, COUNT(*) AS cnt FROM bench GROUP BY category"
            ") "
            "SELECT t.id, t.value, c.cnt "
            "FROM top_items t JOIN bench b ON t.id = b.id "
            "JOIN categories c ON b.category = c.category"
        )
        benchmark(pglast.parse_sql, sql)

    def test_window_function(self, benchmark) -> None:
        sql = (
            "SELECT id, value, category, "
            "ROW_NUMBER() OVER (PARTITION BY category ORDER BY value DESC) AS rn, "
            "SUM(value) OVER (PARTITION BY category) AS cat_total "
            "FROM bench"
        )
        benchmark(pglast.parse_sql, sql)


# ---------------------------------------------------------------------------
# Full SQL compilation (parse + compile to operator tree)
# ---------------------------------------------------------------------------

class TestCompileSelect:
    def test_simple_select(self, benchmark) -> None:
        e = _engine_with_tables()
        benchmark(e.sql, "SELECT id, name FROM bench WHERE value > 100")

    def test_select_multiple_predicates(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT id, name, value FROM bench "
            "WHERE value > 100 AND category = 'cat_1' AND quantity < 500"
        )
        benchmark(e.sql, sql)

    def test_select_with_expressions(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT id, name, value * quantity AS total, "
            "CASE WHEN value > 500 THEN 'high' ELSE 'low' END AS tier "
            "FROM bench WHERE value > 0"
        )
        benchmark(e.sql, sql)


class TestCompileJoin:
    def test_2way_join(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT o.id, c.name FROM orders o "
            "JOIN customers c ON o.customer_id = c.id"
        )
        benchmark(e.sql, sql)

    def test_3way_join(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT o.id, c.name, p.name FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "JOIN products p ON o.product_id = p.id"
        )
        benchmark(e.sql, sql)


class TestCompileAggregate:
    def test_group_by(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = "SELECT category, COUNT(*), SUM(value) FROM bench GROUP BY category"
        benchmark(e.sql, sql)

    def test_group_by_having(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT category, COUNT(*) AS cnt, AVG(value) AS avg_val "
            "FROM bench GROUP BY category HAVING COUNT(*) > 5"
        )
        benchmark(e.sql, sql)


class TestCompileSubquery:
    def test_scalar_subquery(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT id, name FROM bench "
            "WHERE value > (SELECT AVG(value) FROM bench)"
        )
        benchmark(e.sql, sql)

    def test_exists_subquery(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT c.id, c.name FROM customers c "
            "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)"
        )
        benchmark(e.sql, sql)


class TestCompileCTE:
    def test_single_cte(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "WITH high_value AS ("
            "  SELECT id, value FROM bench WHERE value > 500"
            ") SELECT COUNT(*) FROM high_value"
        )
        benchmark(e.sql, sql)

    def test_multiple_ctes(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "WITH high AS ("
            "  SELECT id, value FROM bench WHERE value > 500"
            "), low AS ("
            "  SELECT id, value FROM bench WHERE value <= 500"
            ") "
            "SELECT 'high' AS tier, COUNT(*) FROM high "
            "UNION ALL "
            "SELECT 'low', COUNT(*) FROM low"
        )
        benchmark(e.sql, sql)


class TestCompileWindow:
    def test_row_number(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT id, value, "
            "ROW_NUMBER() OVER (ORDER BY value DESC) AS rn "
            "FROM bench"
        )
        benchmark(e.sql, sql)

    def test_partition_window(self, benchmark) -> None:
        e = _engine_with_tables()
        sql = (
            "SELECT id, category, value, "
            "RANK() OVER (PARTITION BY category ORDER BY value DESC) AS rnk "
            "FROM bench"
        )
        benchmark(e.sql, sql)


class TestCompileDML:
    def test_insert(self, benchmark) -> None:
        e = _engine_with_tables()

        def do_insert() -> None:
            e.sql(
                "INSERT INTO bench (id, name, value, category, quantity, active) "
                "VALUES (99999, 'test', 42.0, 'cat_0', 10, TRUE)"
            )
            # Clean up for next iteration
            e.sql("DELETE FROM bench WHERE id = 99999")

        benchmark(do_insert)

    def test_update(self, benchmark) -> None:
        e = _engine_with_tables()
        e.sql(
            "INSERT INTO bench (id, name, value, category, quantity, active) "
            "VALUES (99999, 'test', 42.0, 'cat_0', 10, TRUE)"
        )
        benchmark(
            e.sql,
            "UPDATE bench SET value = 99.0 WHERE id = 99999",
        )

    def test_delete(self, benchmark) -> None:
        e = _engine_with_tables()

        def do_delete() -> None:
            e.sql(
                "INSERT INTO bench (id, name, value, category, quantity, active) "
                "VALUES (99998, 'del', 1.0, 'cat_0', 1, TRUE)"
            )
            e.sql("DELETE FROM bench WHERE id = 99998")

        benchmark(do_delete)
