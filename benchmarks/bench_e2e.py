#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""End-to-end SQL benchmarks.

Measures full query latency including parsing, planning, and execution.
Uses pre-populated tables from conftest fixtures.
"""

from __future__ import annotations

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

def _engine_with_data(n: int = 1000) -> Engine:
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


def _engine_with_joins(n_orders: int = 500) -> Engine:
    e = Engine()
    e.sql(CUSTOMERS_DDL)
    e.sql(PRODUCTS_DDL)
    e.sql(ORDERS_DDL)
    gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
    customers, products, orders = gen.join_tables(
        num_orders=n_orders, num_customers=100
    )
    for c in customers:
        e.sql(f"INSERT INTO customers VALUES ({c['id']}, '{c['name']}', '{c['region']}')")
    for p in products:
        e.sql(f"INSERT INTO products VALUES ({p['id']}, '{p['name']}', {p['price']}, '{p['category']}')")
    for o in orders:
        e.sql(
            f"INSERT INTO orders VALUES ({o['id']}, {o['customer_id']}, "
            f"{o['product_id']}, {o['amount']}, '{o['status']}')"
        )
    return e


# ---------------------------------------------------------------------------
# OLTP-style queries
# ---------------------------------------------------------------------------

class TestOLTP:
    def test_point_lookup(self, benchmark) -> None:
        e = _engine_with_data()
        result = benchmark(e.sql, "SELECT * FROM bench WHERE id = 500")
        assert len(result) == 1

    def test_range_scan(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(e.sql, "SELECT * FROM bench WHERE value BETWEEN 100 AND 200")

    def test_insert_single(self, benchmark) -> None:
        e = _engine_with_data(100)
        counter = [200000]

        def do_insert() -> None:
            counter[0] += 1
            e.sql(
                f"INSERT INTO bench VALUES ("
                f"{counter[0]}, 'new_{counter[0]}', 42.0, 'cat_0', 1, TRUE)"
            )

        benchmark(do_insert)

    def test_update_where(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(e.sql, "UPDATE bench SET value = value + 1 WHERE id = 500")

    def test_delete_where(self, benchmark) -> None:
        e = _engine_with_data()
        counter = [100000]

        def do_delete() -> None:
            counter[0] += 1
            e.sql(
                f"INSERT INTO bench VALUES ("
                f"{counter[0]}, 'del', 1.0, 'cat_0', 1, TRUE)"
            )
            e.sql(f"DELETE FROM bench WHERE id = {counter[0]}")

        benchmark(do_delete)


# ---------------------------------------------------------------------------
# OLAP-style queries
# ---------------------------------------------------------------------------

class TestOLAP:
    def test_aggregate_group(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "SELECT category, COUNT(*), SUM(value), AVG(quantity) "
            "FROM bench GROUP BY category",
        )

    def test_aggregate_having(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "SELECT category, COUNT(*) AS cnt "
            "FROM bench GROUP BY category HAVING COUNT(*) > 50",
        )

    def test_order_by_limit(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "SELECT id, value FROM bench ORDER BY value DESC LIMIT 20",
        )

    def test_distinct(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(e.sql, "SELECT DISTINCT category FROM bench")


# ---------------------------------------------------------------------------
# JOIN queries
# ---------------------------------------------------------------------------

class TestJoin:
    def test_2way_join(self, benchmark) -> None:
        e = _engine_with_joins()
        benchmark(
            e.sql,
            "SELECT o.id, c.name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id",
        )

    def test_3way_join(self, benchmark) -> None:
        e = _engine_with_joins()
        benchmark(
            e.sql,
            "SELECT o.id, c.name, p.name "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "JOIN products p ON o.product_id = p.id",
        )

    def test_join_with_filter(self, benchmark) -> None:
        e = _engine_with_joins()
        benchmark(
            e.sql,
            "SELECT o.id, c.name, o.amount "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.amount > 500 AND c.region = 'region_1'",
        )

    def test_join_with_aggregate(self, benchmark) -> None:
        e = _engine_with_joins()
        benchmark(
            e.sql,
            "SELECT c.name, COUNT(*) AS order_count, SUM(o.amount) AS total "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "GROUP BY c.name ORDER BY total DESC LIMIT 10",
        )


# ---------------------------------------------------------------------------
# Subqueries
# ---------------------------------------------------------------------------

class TestSubquery:
    def test_scalar_subquery(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "SELECT id, value FROM bench "
            "WHERE value > (SELECT AVG(value) FROM bench)",
        )

    def test_exists_subquery(self, benchmark) -> None:
        e = _engine_with_joins()
        benchmark(
            e.sql,
            "SELECT c.id, c.name FROM customers c "
            "WHERE EXISTS ("
            "  SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > 500"
            ")",
        )


# ---------------------------------------------------------------------------
# CTE
# ---------------------------------------------------------------------------

class TestCTE:
    def test_single_cte(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "WITH high_value AS ("
            "  SELECT id, name, value, category, quantity FROM bench WHERE value > 500"
            ") SELECT category, COUNT(*) FROM high_value GROUP BY category",
        )

    def test_multi_cte(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(
            e.sql,
            "WITH high AS ("
            "  SELECT id, value FROM bench WHERE value > 500"
            "), low AS ("
            "  SELECT id, value FROM bench WHERE value <= 500"
            ") "
            "SELECT 'high' AS tier, COUNT(*) AS cnt FROM high "
            "UNION ALL "
            "SELECT 'low', COUNT(*) FROM low",
        )


# ---------------------------------------------------------------------------
# Window Functions
# ---------------------------------------------------------------------------

class TestWindowE2E:
    def test_row_number(self, benchmark) -> None:
        e = _engine_with_data(500)
        benchmark(
            e.sql,
            "SELECT id, value, "
            "ROW_NUMBER() OVER (ORDER BY value DESC) AS rn "
            "FROM bench",
        )

    def test_rank_partitioned(self, benchmark) -> None:
        e = _engine_with_data(500)
        benchmark(
            e.sql,
            "SELECT id, category, value, "
            "RANK() OVER (PARTITION BY category ORDER BY value DESC) AS rnk "
            "FROM bench",
        )


# ---------------------------------------------------------------------------
# ANALYZE
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_analyze(self, benchmark) -> None:
        e = _engine_with_data()
        benchmark(e.sql, "ANALYZE bench")
