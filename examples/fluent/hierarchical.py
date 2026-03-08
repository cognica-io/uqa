#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Hierarchical (nested) data examples using the fluent QueryBuilder API.

Demonstrates:
  - path_aggregate: per-document aggregation over nested arrays
  - filter with dot-path: automatic dispatch to PathFilterOperator
  - path_project: extract specific nested fields
  - Combined filter + aggregate pipelines
  - Dashboard-style multi-aggregation queries
"""

from uqa.core.types import (
    Equals,
    GreaterThan,
    GreaterThanOrEqual,
    LessThanOrEqual,
    NotEquals,
)
from uqa.engine import Engine

# ======================================================================
# Data setup: e-commerce orders with nested items and shipping
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        order_id TEXT,
        customer TEXT,
        status TEXT,
        items TEXT,
        shipping TEXT
    )
""")

orders = [
    (1, {
        "order_id": "ORD-001", "customer": "Alice", "status": "shipped",
        "items": [
            {"name": "Laptop Stand", "price": 49.99, "quantity": 1},
            {"name": "USB-C Hub", "price": 39.99, "quantity": 2},
        ],
        "shipping": {"city": "Seoul", "method": "express", "cost": 15.00},
    }),
    (2, {
        "order_id": "ORD-002", "customer": "Bob", "status": "delivered",
        "items": [
            {"name": "Mechanical Keyboard", "price": 149.99, "quantity": 1},
        ],
        "shipping": {"city": "Busan", "method": "standard", "cost": 5.00},
    }),
    (3, {
        "order_id": "ORD-003", "customer": "Charlie", "status": "shipped",
        "items": [
            {"name": "Monitor Arm", "price": 89.99, "quantity": 1},
            {"name": "Webcam", "price": 79.99, "quantity": 1},
            {"name": "Headset", "price": 129.99, "quantity": 1},
        ],
        "shipping": {"city": "Seoul", "method": "express", "cost": 20.00},
    }),
    (4, {
        "order_id": "ORD-004", "customer": "Diana", "status": "processing",
        "items": [
            {"name": "Laptop Stand", "price": 49.99, "quantity": 3},
            {"name": "Mouse Pad", "price": 19.99, "quantity": 2},
        ],
        "shipping": {"city": "Incheon", "method": "standard", "cost": 8.00},
    }),
    (5, {
        "order_id": "ORD-005", "customer": "Eve", "status": "delivered",
        "items": [
            {"name": "USB-C Hub", "price": 39.99, "quantity": 1},
            {"name": "HDMI Cable", "price": 12.99, "quantity": 3},
            {"name": "Webcam", "price": 79.99, "quantity": 1},
            {"name": "Mouse Pad", "price": 19.99, "quantity": 1},
        ],
        "shipping": {"city": "Seoul", "method": "standard", "cost": 10.00},
    }),
    (6, {
        "order_id": "ORD-006", "customer": "Frank", "status": "cancelled",
        "items": [
            {"name": "Gaming Monitor", "price": 449.99, "quantity": 1},
        ],
        "shipping": {"city": "Daegu", "method": "express", "cost": 25.00},
    }),
]

for doc_id, doc in orders:
    engine.add_document(doc_id, doc, table="orders")

print("=" * 70)
print("Hierarchical Data Examples (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. Path aggregate: total price per order
# ------------------------------------------------------------------
print("\n--- 1. path_aggregate: SUM of items.price per order ---")
results = engine.query(table="orders").path_aggregate("items.price", "sum").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    total = entry.payload.fields.get("_path_aggregate", 0)
    print(f"  {doc['order_id']} ({doc['customer']}): ${total:.2f}")


# ------------------------------------------------------------------
# 2. Path aggregate: item count per order
# ------------------------------------------------------------------
print("\n--- 2. path_aggregate: COUNT of items.name per order ---")
results = engine.query(table="orders").path_aggregate("items.name", "count").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    count = entry.payload.fields.get("_path_aggregate", 0)
    print(f"  {doc['order_id']}: {count} item(s)")


# ------------------------------------------------------------------
# 3. Path aggregate: min/max price per order
# ------------------------------------------------------------------
print("\n--- 3. path_aggregate: MIN/MAX price per order ---")
min_results = engine.query(table="orders").path_aggregate("items.price", "min").execute()
max_results = engine.query(table="orders").path_aggregate("items.price", "max").execute()
min_map = {e.doc_id: e.payload.fields.get("_path_aggregate") for e in min_results}
max_map = {e.doc_id: e.payload.fields.get("_path_aggregate") for e in max_results}
for doc_id in sorted(min_map.keys()):
    doc = engine._tables["orders"].document_store.get(doc_id)
    print(f"  {doc['order_id']}: ${min_map[doc_id]:.2f} - ${max_map[doc_id]:.2f}")


# ------------------------------------------------------------------
# 4. Path aggregate: average price per order
# ------------------------------------------------------------------
print("\n--- 4. path_aggregate: AVG price per order ---")
results = engine.query(table="orders").path_aggregate("items.price", "avg").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    avg = entry.payload.fields.get("_path_aggregate", 0)
    print(f"  {doc['order_id']}: ${avg:.2f}")


# ------------------------------------------------------------------
# 5. Filter on flat field: status = 'shipped'
# ------------------------------------------------------------------
print("\n--- 5. Filter: status = 'shipped' ---")
results = engine.query(table="orders").filter("status", Equals("shipped")).execute()
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    print(f"  {doc['order_id']} ({doc['customer']})")


# ------------------------------------------------------------------
# 6. Filter on nested path: shipping.city = 'Seoul'
# ------------------------------------------------------------------
print("\n--- 6. Nested filter: shipping.city = 'Seoul' ---")
results = engine.query(table="orders").filter("shipping.city", Equals("Seoul")).execute()
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    print(f"  {doc['order_id']} ({doc['customer']})")


# ------------------------------------------------------------------
# 7. Filter on nested path: shipping.method = 'express'
# ------------------------------------------------------------------
print("\n--- 7. Nested filter: shipping.method = 'express' ---")
results = engine.query(table="orders").filter("shipping.method", Equals("express")).execute()
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    ship = doc["shipping"]
    print(f"  {doc['order_id']} -> {ship['city']} (${ship['cost']:.2f})")


# ------------------------------------------------------------------
# 8. Filter on nested path with comparison: shipping.cost > 10
# ------------------------------------------------------------------
print("\n--- 8. Nested filter: shipping.cost > 10 ---")
results = engine.query(table="orders").filter("shipping.cost", GreaterThan(10)).execute()
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    print(f"  {doc['order_id']}: shipping ${doc['shipping']['cost']:.2f}")


# ------------------------------------------------------------------
# 9. Chained filters: status != 'cancelled' AND shipping.city = 'Seoul'
# ------------------------------------------------------------------
print("\n--- 9. Chained: status != 'cancelled' AND shipping.city = 'Seoul' ---")
results = (
    engine.query(table="orders")
    .filter("status", NotEquals("cancelled"))
    .filter("shipping.city", Equals("Seoul"))
    .execute()
)
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    print(f"  {doc['order_id']} ({doc['customer']}) [{doc['status']}]")


# ------------------------------------------------------------------
# 10. Filter + aggregate pipeline: total for Seoul express orders
# ------------------------------------------------------------------
print("\n--- 10. Pipeline: Seoul express orders -> SUM(items.price) ---")
results = (
    engine.query(table="orders")
    .filter("shipping.city", Equals("Seoul"))
    .filter("shipping.method", Equals("express"))
    .path_aggregate("items.price", "sum")
    .execute()
)
grand_total = 0.0
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    total = entry.payload.fields.get("_path_aggregate", 0)
    grand_total += total
    print(f"  {doc['order_id']} ({doc['customer']}): ${total:.2f}")
print(f"  Grand total: ${grand_total:.2f}")


# ------------------------------------------------------------------
# 11. Filter on array element: items containing 'Webcam'
# ------------------------------------------------------------------
print("\n--- 11. Array filter: items.name = 'Webcam' ---")
results = engine.query(table="orders").filter("items.name", Equals("Webcam")).execute()
for entry in results:
    doc = engine._tables["orders"].document_store.get(entry.doc_id)
    print(f"  {doc['order_id']} ({doc['customer']})")


# ------------------------------------------------------------------
# 12. Path project: extract specific nested fields
# ------------------------------------------------------------------
print("\n--- 12. path_project: order_id + shipping ---")
source = engine.query(table="orders").filter("status", Equals("shipped"))
results = source.path_project(["order_id"], ["shipping", "city"], ["shipping", "cost"]).execute()
for entry in results:
    fields = entry.payload.fields
    print(f"  {fields.get('order_id')} -> "
          f"{fields.get('shipping.city')} (${fields.get('shipping.cost', 0):.2f})")


# ------------------------------------------------------------------
# 13. Dashboard: multi-aggregation per order
# ------------------------------------------------------------------
print("\n--- 13. Dashboard: per-order summary ---")
sum_results = engine.query(table="orders").path_aggregate("items.price", "sum").execute()
count_results = engine.query(table="orders").path_aggregate("items.name", "count").execute()
sum_map = {e.doc_id: e.payload.fields.get("_path_aggregate", 0) for e in sum_results}
count_map = {e.doc_id: e.payload.fields.get("_path_aggregate", 0) for e in count_results}

for doc_id in sorted(sum_map.keys()):
    doc = engine._tables["orders"].document_store.get(doc_id)
    total = sum_map[doc_id]
    count = count_map.get(doc_id, 0)
    ship = doc["shipping"]["cost"]
    print(f"  {doc['order_id']} | {doc['customer']:<8} | "
          f"{count} items | ${total:>7.2f} + ${ship:.2f} shipping")


# ------------------------------------------------------------------
# 14. Revenue by shipping method
# ------------------------------------------------------------------
print("\n--- 14. Revenue by shipping method ---")
for method in ("express", "standard"):
    results = (
        engine.query(table="orders")
        .filter("shipping.method", Equals(method))
        .filter("status", NotEquals("cancelled"))
        .path_aggregate("items.price", "sum")
        .execute()
    )
    total = sum(e.payload.fields.get("_path_aggregate", 0) for e in results)
    print(f"  {method:>10}: {len(results)} orders, ${total:.2f} revenue")


# ------------------------------------------------------------------
# 15. Faceted search: order count by status
# ------------------------------------------------------------------
print("\n--- 15. Facets: order distribution by status ---")
facets = engine.query(table="orders").facet("status")
for status, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
    print(f"  {status:>12}: {count} order(s)")


print("\n" + "=" * 70)
print("All hierarchical data examples completed successfully.")
print("=" * 70)
