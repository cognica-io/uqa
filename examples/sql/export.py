#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Arrow and Parquet export examples.

Demonstrates:
  - to_arrow(): convert query results to a pyarrow.Table (zero-copy)
  - to_parquet(): write query results to a Parquet file
  - Round-trip: Parquet write -> read back via pyarrow
  - Lazy iteration: iterate over results without materializing all rows
  - Type preservation: int, float, string, bool, date, NULL
"""

import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from uqa.engine import Engine

engine = Engine()

print("=" * 70)
print("Arrow / Parquet Export Examples")
print("=" * 70)


# ==================================================================
# 1. Set up test data
# ==================================================================
print("\n--- 1. Setup ---")

engine.sql("""
    CREATE TABLE products (
        id SERIAL PRIMARY KEY,
        name TEXT,
        category TEXT,
        price REAL,
        in_stock BOOLEAN,
        release_date DATE
    )
""")

engine.sql("""INSERT INTO products (name, category, price, in_stock, release_date) VALUES
    ('Widget A', 'hardware', 9.99, TRUE, '2024-01-15'),
    ('Widget B', 'hardware', 14.99, TRUE, '2024-03-20'),
    ('Gadget X', 'electronics', 49.99, FALSE, '2023-11-01'),
    ('Gadget Y', 'electronics', 79.99, TRUE, '2024-06-10'),
    ('Tool Z', 'hardware', 24.99, TRUE, '2024-02-28'),
    ('Sensor Q', 'electronics', 199.99, FALSE, '2025-01-05')
""")

print("  Inserted 6 products.")


# ==================================================================
# 2. to_arrow() -- zero-copy conversion
# ==================================================================
print("\n--- 2. to_arrow() ---")

result = engine.sql("SELECT name, category, price FROM products ORDER BY price")
table = result.to_arrow()

print(f"  Type: {type(table).__name__}")
print(f"  Rows: {table.num_rows}")
print(f"  Columns: {table.column_names}")
print("  Schema:")
for field in table.schema:
    print(f"    {field.name}: {field.type}")
print(f"  Memory: {table.nbytes} bytes")


# ==================================================================
# 3. Arrow column access and compute
# ==================================================================
print("\n--- 3. Arrow column operations ---")

prices = table.column("price")
print(f"  Prices: {prices.to_pylist()}")
print(f"  Min: {pa.compute.min(prices).as_py()}")
print(f"  Max: {pa.compute.max(prices).as_py()}")
print(f"  Mean: {pa.compute.mean(prices).as_py():.2f}")


# ==================================================================
# 4. to_parquet() -- write to file
# ==================================================================
print("\n--- 4. to_parquet() ---")

parquet_dir = tempfile.mkdtemp()
parquet_path = os.path.join(parquet_dir, "products.parquet")

result = engine.sql("""
    SELECT name, category, price, in_stock
    FROM products
    WHERE in_stock = TRUE
    ORDER BY price
""")
result.to_parquet(parquet_path)

file_size = os.path.getsize(parquet_path)
print(f"  Written to: {parquet_path}")
print(f"  File size: {file_size} bytes")


# ==================================================================
# 5. Parquet round-trip -- read back
# ==================================================================
print("\n--- 5. Parquet round-trip ---")

restored = pq.read_table(parquet_path)
print(f"  Rows: {restored.num_rows}")
print(f"  Columns: {restored.column_names}")
print(f"  Names: {restored.column('name').to_pylist()}")
print(f"  Prices: {restored.column('price').to_pylist()}")


# ==================================================================
# 6. Type preservation
# ==================================================================
print("\n--- 6. Type preservation ---")

result = engine.sql("""
    SELECT id, name, price, in_stock, release_date
    FROM products
    ORDER BY id LIMIT 3
""")
table = result.to_arrow()

print("  Arrow schema:")
for field in table.schema:
    print(f"    {field.name}: {field.type}")

print("  First row:")
for col in table.column_names:
    val = table.column(col)[0].as_py()
    print(f"    {col} = {val!r} ({type(val).__name__})")


# ==================================================================
# 7. Aggregation results to Arrow
# ==================================================================
print("\n--- 7. Aggregation -> Arrow ---")

result = engine.sql("""
    SELECT category,
           COUNT(*) AS cnt,
           AVG(price) AS avg_price,
           MIN(price) AS min_price,
           MAX(price) AS max_price
    FROM products
    GROUP BY category
    ORDER BY avg_price DESC
""")
table = result.to_arrow()

print(f"  Categories: {table.column('category').to_pylist()}")
print(f"  Counts: {table.column('cnt').to_pylist()}")
print(f"  Avg prices: {table.column('avg_price').to_pylist()}")


# ==================================================================
# 8. Empty result to Arrow/Parquet
# ==================================================================
print("\n--- 8. Empty result ---")

result = engine.sql("SELECT name, price FROM products WHERE price > 1000")
table = result.to_arrow()
print(f"  Rows: {table.num_rows}")
print(f"  Columns: {table.column_names}")

empty_path = os.path.join(parquet_dir, "empty.parquet")
result.to_parquet(empty_path)
print(f"  Empty Parquet written: {os.path.getsize(empty_path)} bytes")


# ==================================================================
# 9. Lazy iteration (generator-based)
# ==================================================================
print("\n--- 9. Lazy iteration ---")

result = engine.sql("SELECT name, price FROM products ORDER BY price DESC")
print("  First 3 rows via iterator:")
for i, row in enumerate(result):
    if i >= 3:
        break
    print(f"    {row['name']}: ${row['price']}")


# ==================================================================
# 10. Parquet with JOIN results
# ==================================================================
print("\n--- 10. JOIN result -> Parquet ---")

engine.sql("""
    CREATE TABLE categories (
        name TEXT PRIMARY KEY,
        department TEXT
    )
""")

engine.sql("""INSERT INTO categories (name, department) VALUES
    ('hardware', 'engineering'),
    ('electronics', 'engineering')
""")

result = engine.sql("""
    SELECT p.name AS product, p.price, c.department
    FROM products p
    INNER JOIN categories c ON p.category = c.name
    WHERE p.in_stock = TRUE
    ORDER BY p.price
""")

join_path = os.path.join(parquet_dir, "joined.parquet")
result.to_parquet(join_path)

restored = pq.read_table(join_path)
print(f"  Rows: {restored.num_rows}")
for i in range(restored.num_rows):
    name = restored.column("product")[i].as_py()
    price = restored.column("price")[i].as_py()
    dept = restored.column("department")[i].as_py()
    print(f"    {name}: ${price} ({dept})")


print("\n" + "=" * 70)
print("All Arrow / Parquet export examples completed successfully.")
print("=" * 70)
