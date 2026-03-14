#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Shared fixtures for benchmark tests."""

from __future__ import annotations

import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from benchmarks.data.schemas import (
    BENCH_TABLE_DDL,
    CUSTOMERS_DDL,
    ORDERS_DDL,
    PRODUCTS_DDL,
)
from uqa.engine import Engine


@pytest.fixture(params=[1], ids=["SF1"])
def scale_factor(request: pytest.FixtureRequest) -> int:
    """Scale factor for benchmark data generation."""
    return request.param


@pytest.fixture()
def gen(scale_factor: int) -> BenchmarkDataGenerator:
    """Data generator seeded for reproducibility."""
    return BenchmarkDataGenerator(scale_factor=scale_factor, seed=42)


@pytest.fixture()
def engine() -> Engine:
    """In-memory UQA engine."""
    return Engine()


@pytest.fixture()
def engine_with_bench_table(gen: BenchmarkDataGenerator) -> Engine:
    """Engine with a populated 'bench' table."""
    e = Engine()
    e.sql(BENCH_TABLE_DDL)
    rows = gen.table_rows()
    for row in rows:
        cols = ", ".join(
            str(v)
            if not isinstance(v, str | bool)
            else f"'{v}'"
            if isinstance(v, str)
            else ("TRUE" if v else "FALSE")
            for v in row.values()
        )
        e.sql(f"INSERT INTO bench VALUES ({cols})")
    return e


@pytest.fixture()
def engine_with_join_tables(gen: BenchmarkDataGenerator) -> Engine:
    """Engine with customers, products, and orders tables."""
    e = Engine()
    e.sql(CUSTOMERS_DDL)
    e.sql(PRODUCTS_DDL)
    e.sql(ORDERS_DDL)

    customers, products, orders = gen.join_tables()
    for c in customers:
        e.sql(
            f"INSERT INTO customers VALUES ({c['id']}, '{c['name']}', '{c['region']}')"
        )
    for p in products:
        e.sql(
            f"INSERT INTO products VALUES ({p['id']}, '{p['name']}', {p['price']}, '{p['category']}')"
        )
    for o in orders:
        e.sql(
            f"INSERT INTO orders VALUES ({o['id']}, {o['customer_id']}, "
            f"{o['product_id']}, {o['amount']}, '{o['status']}')"
        )
    return e
