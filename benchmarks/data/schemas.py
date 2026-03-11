#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Table schema definitions for benchmark workloads."""

from __future__ import annotations

# Schema for the generic benchmark table
BENCH_TABLE_COLUMNS = [
    ("id", "INTEGER"),
    ("name", "TEXT"),
    ("value", "REAL"),
    ("category", "TEXT"),
    ("quantity", "INTEGER"),
    ("active", "BOOLEAN"),
]

# Schema for join benchmark tables
CUSTOMERS_COLUMNS = [
    ("id", "INTEGER"),
    ("name", "TEXT"),
    ("region", "TEXT"),
]

PRODUCTS_COLUMNS = [
    ("id", "INTEGER"),
    ("name", "TEXT"),
    ("price", "REAL"),
    ("category", "TEXT"),
]

ORDERS_COLUMNS = [
    ("id", "INTEGER"),
    ("customer_id", "INTEGER"),
    ("product_id", "INTEGER"),
    ("amount", "REAL"),
    ("status", "TEXT"),
]

# Schema for text search benchmark
TEXT_TABLE_COLUMNS = [
    ("id", "INTEGER"),
    ("title", "TEXT"),
    ("body", "TEXT"),
    ("category", "TEXT"),
    ("price", "REAL"),
    ("rating", "REAL"),
]

# DDL statements for SQL engine benchmarks
BENCH_TABLE_DDL = (
    "CREATE TABLE bench ("
    "  id INTEGER PRIMARY KEY,"
    "  name TEXT,"
    "  value REAL,"
    "  category TEXT,"
    "  quantity INTEGER,"
    "  active BOOLEAN"
    ")"
)

CUSTOMERS_DDL = (
    "CREATE TABLE customers ("
    "  id INTEGER PRIMARY KEY,"
    "  name TEXT,"
    "  region TEXT"
    ")"
)

PRODUCTS_DDL = (
    "CREATE TABLE products ("
    "  id INTEGER PRIMARY KEY,"
    "  name TEXT,"
    "  price REAL,"
    "  category TEXT"
    ")"
)

ORDERS_DDL = (
    "CREATE TABLE orders ("
    "  id INTEGER PRIMARY KEY,"
    "  customer_id INTEGER,"
    "  product_id INTEGER,"
    "  amount REAL,"
    "  status TEXT"
    ")"
)
