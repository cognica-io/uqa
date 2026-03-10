#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Foreign Data Wrapper examples using the engine.sql() API.

Demonstrates:
  - DDL: CREATE SERVER, CREATE FOREIGN TABLE, DROP FOREIGN TABLE, DROP SERVER
  - Querying Parquet files via duckdb_fdw
  - Querying CSV files via duckdb_fdw
  - WHERE, ORDER BY, LIMIT on foreign tables
  - Aggregation (GROUP BY, SUM, AVG) on foreign data
  - JOIN between local tables and foreign tables
  - information_schema visibility of foreign tables
  - Catalog persistence (foreign tables survive engine restart)
"""

import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from uqa.engine import Engine

engine = Engine()


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<15}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = [str(row.get(c, ""))[:15].ljust(15) for c in result.columns]
        print("  " + " | ".join(vals))


print("=" * 70)
print("Foreign Data Wrapper (FDW) Examples")
print("=" * 70)


# ==================================================================
# Setup: write sample data files
# ==================================================================
tmp_dir = tempfile.mkdtemp()

# Parquet: product catalog
products_path = os.path.join(tmp_dir, "products.parquet")
pq.write_table(pa.table({
    "product_id": [101, 102, 103, 104, 105],
    "name": ["Widget", "Gadget", "Gizmo", "Doohickey", "Thingamajig"],
    "category": ["Tools", "Electronics", "Tools", "Electronics", "Tools"],
    "price": [29.99, 49.99, 19.99, 99.99, 14.99],
    "stock": [500, 200, 1000, 50, 800],
}), products_path)

# Parquet: order history
orders_path = os.path.join(tmp_dir, "orders.parquet")
pq.write_table(pa.table({
    "order_id": [1, 2, 3, 4, 5, 6, 7, 8],
    "product_id": [101, 103, 102, 101, 105, 104, 103, 102],
    "customer": ["Alice", "Bob", "Alice", "Carol", "Bob", "Diana", "Alice", "Carol"],
    "quantity": [2, 5, 1, 3, 10, 1, 4, 2],
    "order_date": [
        "2024-01-15", "2024-01-20", "2024-02-01", "2024-02-10",
        "2024-03-01", "2024-03-05", "2024-03-10", "2024-04-01",
    ],
}), orders_path)

# CSV: customer info
customers_path = os.path.join(tmp_dir, "customers.csv")
with open(customers_path, "w") as f:
    f.write("customer_id,name,region,tier\n")
    f.write("1,Alice,East,Gold\n")
    f.write("2,Bob,West,Silver\n")
    f.write("3,Carol,East,Bronze\n")
    f.write("4,Diana,West,Gold\n")

print(f"\n  Sample data written to {tmp_dir}/")


# ==================================================================
# 1. CREATE SERVER + FOREIGN TABLE for Parquet
# ==================================================================
engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
print("\n--- 1. CREATE SERVER local (duckdb_fdw) ---")
print("  Server created.")

engine.sql(f"""
    CREATE FOREIGN TABLE products (
        product_id INTEGER,
        name TEXT,
        category TEXT,
        price REAL,
        stock INTEGER
    ) SERVER local OPTIONS (source '{products_path}')
""")
print("\n--- 2. CREATE FOREIGN TABLE products ---")
print("  Foreign table created (backed by Parquet).")


# ==================================================================
# 2. Basic SELECT from foreign table
# ==================================================================
show("3. SELECT * FROM products", engine.sql(
    "SELECT * FROM products ORDER BY product_id"
))


# ==================================================================
# 3. WHERE + ORDER BY + LIMIT on foreign table
# ==================================================================
show("4. WHERE category = 'Tools' ORDER BY price", engine.sql(
    "SELECT name, price, stock FROM products "
    "WHERE category = 'Tools' ORDER BY price"
))

show("5. WHERE price > 20 LIMIT 3", engine.sql(
    "SELECT name, price FROM products WHERE price > 20 ORDER BY price DESC LIMIT 3"
))


# ==================================================================
# 4. Aggregation on foreign data
# ==================================================================
show("6. Aggregate: category stats", engine.sql("""
    SELECT category,
           COUNT(*) AS num_products,
           AVG(price) AS avg_price,
           SUM(stock) AS total_stock
    FROM products
    GROUP BY category
    ORDER BY category
"""))


# ==================================================================
# 5. Multiple foreign tables from same server
# ==================================================================
engine.sql(f"""
    CREATE FOREIGN TABLE orders (
        order_id INTEGER,
        product_id INTEGER,
        customer TEXT,
        quantity INTEGER,
        order_date TEXT
    ) SERVER local OPTIONS (source '{orders_path}')
""")
print("\n--- 7. CREATE FOREIGN TABLE orders ---")
print("  Second foreign table created (same server).")

show("8. SELECT from orders", engine.sql(
    "SELECT * FROM orders ORDER BY order_id LIMIT 5"
))


# ==================================================================
# 6. JOIN between two foreign tables
# ==================================================================
show("9. JOIN: orders with product details", engine.sql("""
    SELECT o.order_id, o.customer, p.name AS product, o.quantity,
           p.price * o.quantity AS total
    FROM orders o
    INNER JOIN products p ON o.product_id = p.product_id
    ORDER BY o.order_id
"""))


# ==================================================================
# 7. Aggregation across joined foreign tables
# ==================================================================
show("10. Revenue by customer (foreign JOIN + GROUP BY)", engine.sql("""
    SELECT o.customer,
           COUNT(*) AS num_orders,
           SUM(p.price * o.quantity) AS total_spent
    FROM orders o
    INNER JOIN products p ON o.product_id = p.product_id
    GROUP BY o.customer
    ORDER BY total_spent DESC
"""))


# ==================================================================
# 8. JOIN between local table and foreign table
# ==================================================================
engine.sql("""
    CREATE TABLE customer_notes (
        customer TEXT PRIMARY KEY,
        note TEXT NOT NULL
    )
""")
engine.sql("""INSERT INTO customer_notes (customer, note) VALUES
    ('Alice', 'VIP customer, priority shipping'),
    ('Bob', 'Prefers bulk orders'),
    ('Carol', 'New customer, watch for retention')
""")

show("11. Local + foreign JOIN", engine.sql("""
    SELECT o.customer, p.name AS product, o.quantity, n.note
    FROM orders o
    INNER JOIN products p ON o.product_id = p.product_id
    INNER JOIN customer_notes n ON o.customer = n.customer
    ORDER BY o.order_id
    LIMIT 5
"""))


# ==================================================================
# 9. CSV via duckdb_fdw (auto-detected reader)
# ==================================================================
engine.sql(f"""
    CREATE FOREIGN TABLE customers (
        customer_id INTEGER,
        name TEXT,
        region TEXT,
        tier TEXT
    ) SERVER local OPTIONS (source '{customers_path}')
""")

show("12. SELECT from CSV foreign table", engine.sql(
    "SELECT * FROM customers ORDER BY customer_id"
))


# ==================================================================
# 10. Three-way join: local + Parquet + CSV
# ==================================================================
show("13. Three-way JOIN: orders + products + customers", engine.sql("""
    SELECT c.name AS customer, c.tier, c.region,
           p.name AS product, o.quantity,
           p.price * o.quantity AS total
    FROM orders o
    INNER JOIN products p ON o.product_id = p.product_id
    INNER JOIN customers c ON o.customer = c.name
    ORDER BY total DESC
    LIMIT 5
"""))


# ==================================================================
# 11. DuckDB expression as source (read_parquet with options)
# ==================================================================
engine.sql(f"""
    CREATE FOREIGN TABLE products_v2 (
        product_id INTEGER,
        name TEXT,
        category TEXT,
        price REAL,
        stock INTEGER
    ) SERVER local OPTIONS (source 'read_parquet(''{products_path}'')')
""")

show("14. Explicit read_parquet() source", engine.sql(
    "SELECT name, price FROM products_v2 ORDER BY price DESC LIMIT 3"
))


# ==================================================================
# 12. information_schema: foreign tables visible
# ==================================================================
show("15. information_schema.tables", engine.sql("""
    SELECT table_name, table_type
    FROM information_schema.tables
    ORDER BY table_type, table_name
"""))


# ==================================================================
# 13. DML guard: INSERT/UPDATE/DELETE rejected
# ==================================================================
print("\n--- 16. DML guard: foreign tables are read-only ---")
for op, sql in [
    ("INSERT", "INSERT INTO products (product_id, name) VALUES (999, 'test')"),
    ("UPDATE", "UPDATE products SET price = 0 WHERE product_id = 101"),
    ("DELETE", "DELETE FROM products WHERE product_id = 101"),
]:
    try:
        engine.sql(sql)
    except ValueError as e:
        print(f"  {op}: {e}")


# ==================================================================
# 14. DROP FOREIGN TABLE + DROP SERVER
# ==================================================================
engine.sql("DROP FOREIGN TABLE products_v2")
engine.sql("DROP FOREIGN TABLE customers")
engine.sql("DROP FOREIGN TABLE orders")
engine.sql("DROP FOREIGN TABLE products")
engine.sql("DROP SERVER local")
print("\n--- 17. DROP ---")
print("  All foreign tables and server dropped.")


# ==================================================================
# 15. Catalog persistence
# ==================================================================
print("\n--- 18. Catalog persistence ---")
db_path = os.path.join(tmp_dir, "persistent.db")

engine1 = Engine(db_path=db_path)
engine1.sql("CREATE SERVER parquet_srv FOREIGN DATA WRAPPER duckdb_fdw")
engine1.sql(f"""
    CREATE FOREIGN TABLE ext_products (
        product_id INTEGER, name TEXT, price REAL
    ) SERVER parquet_srv OPTIONS (source '{products_path}')
""")
result1 = engine1.sql("SELECT COUNT(*) AS cnt FROM ext_products")
print(f"  Engine 1: {result1.rows[0]['cnt']} rows from foreign table")
engine1.close()

engine2 = Engine(db_path=db_path)
result2 = engine2.sql("SELECT COUNT(*) AS cnt FROM ext_products")
print(f"  Engine 2 (reopened): {result2.rows[0]['cnt']} rows (persisted!)")
result3 = engine2.sql(
    "SELECT name, price FROM ext_products ORDER BY price DESC LIMIT 3"
)
for row in result3.rows:
    print(f"    {row['name']}: ${row['price']}")
engine2.close()


# ==================================================================
# Cleanup
# ==================================================================
engine.close()
import shutil
shutil.rmtree(tmp_dir)


print("\n" + "=" * 70)
print("All FDW examples completed successfully.")
print("=" * 70)
