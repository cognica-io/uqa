#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Multi-paradigm query examples combining all four paradigms.

UQA unifies relational, full-text, vector, and graph queries through
posting lists as the universal abstraction. This example shows how
all four paradigms compose naturally via the fluent API.

Demonstrates:
  - Product catalog search: text + vector + filters
  - Citation network: graph + text + scoring fusion
  - E-commerce analytics: hierarchical + filter + aggregate pipelines
  - Multi-signal ranking: log-odds fusion across paradigms
  - Query plan introspection for multi-paradigm queries
"""

import numpy as np

from uqa.core.types import (
    Edge,
    Equals,
    GreaterThanOrEqual,
    LessThanOrEqual,
    Vertex,
)
from uqa.engine import Engine

# ======================================================================
# Data setup: product catalog with text, vectors, graph, and nested data
# ======================================================================

engine = Engine()
rng = np.random.RandomState(42)

# -- Products table (text + vector) --
engine.sql("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        category TEXT,
        price REAL,
        rating REAL,
        stock INTEGER,
        embedding VECTOR(8)
    )
""")

catalog = [
    (
        1,
        "wireless noise cancelling headphones",
        "premium over ear headphones with active noise cancellation and bluetooth connectivity",
        "audio",
        299.99,
        4.7,
        50,
    ),
    (
        2,
        "bluetooth portable speaker",
        "waterproof portable speaker with deep bass and 12 hour battery life",
        "audio",
        89.99,
        4.3,
        120,
    ),
    (
        3,
        "mechanical gaming keyboard",
        "rgb backlit mechanical keyboard with cherry mx switches and programmable keys",
        "peripherals",
        149.99,
        4.5,
        80,
    ),
    (
        4,
        "ergonomic wireless mouse",
        "silent click wireless mouse with adjustable dpi and ergonomic vertical design",
        "peripherals",
        49.99,
        4.2,
        200,
    ),
    (
        5,
        "ultrawide curved monitor",
        "34 inch ultrawide curved monitor with 144hz refresh rate and hdr support",
        "displays",
        599.99,
        4.8,
        30,
    ),
    (
        6,
        "portable external ssd",
        "1tb usb c external solid state drive with 1050mb per second read speed",
        "storage",
        119.99,
        4.6,
        150,
    ),
    (
        7,
        "webcam 4k autofocus",
        "4k webcam with autofocus noise cancelling microphone and privacy shutter",
        "peripherals",
        79.99,
        4.1,
        90,
    ),
    (
        8,
        "usb c docking station",
        "dual monitor docking station with power delivery ethernet and usb ports",
        "accessories",
        189.99,
        4.4,
        60,
    ),
    (
        9,
        "wireless earbuds anc",
        "true wireless earbuds with active noise cancellation and spatial audio",
        "audio",
        199.99,
        4.6,
        100,
    ),
    (
        10,
        "gaming monitor 27 inch",
        "27 inch gaming monitor with 165hz refresh rate 1ms response time and freesync",
        "displays",
        449.99,
        4.5,
        45,
    ),
]

# Embed products with category-aligned vectors
category_centers = {
    "audio": np.array([1, 0, 0, 0, 0.5, 0, 0, 0], dtype=np.float32),
    "peripherals": np.array([0, 1, 0, 0, 0, 0.5, 0, 0], dtype=np.float32),
    "displays": np.array([0, 0, 1, 0, 0, 0, 0.5, 0], dtype=np.float32),
    "storage": np.array([0, 0, 0, 1, 0, 0, 0, 0.5], dtype=np.float32),
    "accessories": np.array([0.3, 0.3, 0.3, 0.3, 0, 0, 0, 0], dtype=np.float32),
}

for pid, name, desc, cat, price, rating, stock in catalog:
    center = category_centers[cat]
    vec = center + rng.randn(8).astype(np.float32) * 0.1
    vec = vec / np.linalg.norm(vec)
    engine.add_document(
        pid,
        {
            "name": name,
            "description": desc,
            "category": cat,
            "price": price,
            "rating": rating,
            "stock": stock,
        },
        table="products",
        embedding=vec,
    )

# -- "also_bought" graph edges --
gs = engine.get_graph_store("products")
for pid, name, desc, cat, price, rating, stock in catalog:
    gs.add_vertex(
        Vertex(
            pid,
            "",
            {
                "name": name,
                "category": cat,
                "price": price,
                "rating": rating,
            },
        ),
        graph="products",
    )

bought_together = [
    (1, 9, "also_bought"),
    (9, 1, "also_bought"),  # headphones <-> earbuds
    (3, 4, "also_bought"),
    (4, 3, "also_bought"),  # keyboard <-> mouse
    (5, 8, "also_bought"),
    (8, 5, "also_bought"),  # monitor <-> dock
    (5, 10, "also_bought"),
    (10, 5, "also_bought"),  # monitors together
    (3, 10, "also_bought"),
    (10, 3, "also_bought"),  # keyboard <-> gaming monitor
    (7, 8, "also_bought"),
    (8, 7, "also_bought"),  # webcam <-> dock
    (1, 7, "also_bought"),  # headphones -> webcam (video calls)
    (6, 8, "also_bought"),  # ssd -> dock
]
for i, (src, dst, label) in enumerate(bought_together, start=1):
    gs.add_edge(Edge(i, src, dst, label), graph="products")

# -- Orders table (hierarchical nested data) --
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
    (
        1,
        {
            "order_id": "ORD-001",
            "customer": "Alice",
            "status": "shipped",
            "items": [
                {"product_id": 1, "name": "headphones", "price": 299.99, "qty": 1},
                {"product_id": 9, "name": "earbuds", "price": 199.99, "qty": 1},
            ],
            "shipping": {"city": "Seoul", "method": "express", "cost": 15.0},
        },
    ),
    (
        2,
        {
            "order_id": "ORD-002",
            "customer": "Bob",
            "status": "delivered",
            "items": [
                {"product_id": 3, "name": "keyboard", "price": 149.99, "qty": 1},
                {"product_id": 4, "name": "mouse", "price": 49.99, "qty": 2},
                {"product_id": 10, "name": "gaming monitor", "price": 449.99, "qty": 1},
            ],
            "shipping": {"city": "Busan", "method": "standard", "cost": 10.0},
        },
    ),
    (
        3,
        {
            "order_id": "ORD-003",
            "customer": "Charlie",
            "status": "shipped",
            "items": [
                {
                    "product_id": 5,
                    "name": "ultrawide monitor",
                    "price": 599.99,
                    "qty": 1,
                },
                {"product_id": 8, "name": "dock", "price": 189.99, "qty": 1},
                {"product_id": 7, "name": "webcam", "price": 79.99, "qty": 1},
            ],
            "shipping": {"city": "Seoul", "method": "express", "cost": 20.0},
        },
    ),
    (
        4,
        {
            "order_id": "ORD-004",
            "customer": "Diana",
            "status": "processing",
            "items": [
                {"product_id": 6, "name": "ssd", "price": 119.99, "qty": 2},
            ],
            "shipping": {"city": "Incheon", "method": "standard", "cost": 5.0},
        },
    ),
]
for doc_id, doc in orders:
    engine.add_document(doc_id, doc, table="orders")


print("=" * 70)
print("Multi-Paradigm Query Examples (Fluent API)")
print("=" * 70)


# ==================================================================
# Scenario 1: Product Discovery
# Text search + vector similarity + relational filters
# ==================================================================
print("\n" + "=" * 50)
print("Scenario 1: Product Discovery")
print("=" * 50)

# 1a. Text search: find products mentioning "noise cancelling"
print("\n--- 1a. Text search: 'noise cancelling' ---")
results = engine.query(table="products").term("noise").term("cancelling").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] {doc['name']} (${doc['price']:.2f})")

# 1b. Vector search: find products similar to "audio" category
print("\n--- 1b. Vector: 3 nearest to audio profile ---")
audio_query = category_centers["audio"] + rng.randn(8).astype(np.float32) * 0.05
audio_query = (audio_query / np.linalg.norm(audio_query)).astype(np.float32)

results = engine.query(table="products").knn(audio_query, k=3).execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(
        f"  [{entry.doc_id}] sim={entry.payload.score:.4f}  "
        f"{doc['name']} [{doc['category']}]"
    )

# 1c. Text + vector + filter: "wireless" products similar to audio, under $250
print("\n--- 1c. Hybrid: 'wireless' + audio vector + price <= $250 ---")
text_q = engine.query(table="products").term("wireless")
vec_q = engine.query(table="products").knn(audio_query, k=5)
results = text_q.and_(vec_q).filter("price", LessThanOrEqual(250.0)).execute()
for entry in results:
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] {doc['name']} (${doc['price']:.2f})")

# 1d. BM25 scored text + filter
print("\n--- 1d. BM25 scored: 'monitor gaming' + rating >= 4.5 ---")
q = (
    engine.query(table="products")
    .term("monitor")
    .or_(engine.query(table="products").term("gaming"))
)
results = (
    q.score_bm25("monitor gaming").filter("rating", GreaterThanOrEqual(4.5)).execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(
        f"  [{entry.doc_id}] score={entry.payload.score:.4f}  "
        f"{doc['name']} (rating: {doc['rating']})"
    )


# ==================================================================
# Scenario 2: Recommendation Engine
# Graph traversal + vector similarity + scoring fusion
# ==================================================================
print("\n" + "=" * 50)
print("Scenario 2: Recommendation Engine")
print("=" * 50)

# 2a. Graph: "also bought" from headphones (product 1)
print("\n--- 2a. Graph: products also bought with headphones ---")
results = (
    engine.query(table="products").traverse(1, "also_bought", max_hops=1).execute()
)
for entry in results:
    if entry.doc_id != 1:
        v = gs.get_vertex(entry.doc_id)
        if v:
            print(
                f"  [{entry.doc_id}] {v.properties['name']} "
                f"(${v.properties['price']:.2f})"
            )

# 2b. Graph 2-hop: extended recommendations
print("\n--- 2b. Graph 2-hop: extended recommendations from keyboard ---")
results = (
    engine.query(table="products").traverse(3, "also_bought", max_hops=2).execute()
)
for entry in sorted(results, key=lambda e: e.doc_id):
    if entry.doc_id != 3:
        v = gs.get_vertex(entry.doc_id)
        if v:
            print(
                f"  [{entry.doc_id}] {v.properties['name']} [{v.properties['category']}]"
            )

# 2c. Graph aggregate: average price of related products
print("\n--- 2c. Graph aggregate: avg price of products bought with monitor ---")
team = engine.query(table="products").traverse(5, "also_bought", max_hops=1)
for fn in ("avg", "min", "max", "count"):
    result = team.vertex_aggregate("price", fn)
    if fn == "count":
        print(f"  {fn:>5}: {result.value}")
    else:
        print(f"  {fn:>5}: ${result.value:,.2f}")

# 2d. Fusion: text relevance + graph proximity + vector similarity
print("\n--- 2d. Multi-signal fusion: text + graph + vector ---")
display_query = category_centers["displays"] + rng.randn(8).astype(np.float32) * 0.05
display_query = (display_query / np.linalg.norm(display_query)).astype(np.float32)

text_signal = (
    engine.query(table="products").term("monitor").score_bayesian_bm25("monitor")
)
vec_signal = engine.query(table="products").knn(display_query, k=5)

fused = engine.query(table="products").fuse_log_odds(text_signal, vec_signal, alpha=0.6)
results = fused.execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True)[:5]:
    doc = engine.get_document(entry.doc_id, table="products")
    print(
        f"  [{entry.doc_id}] fused={entry.payload.score:.4f}  "
        f"{doc['name']} [{doc['category']}]"
    )


# ==================================================================
# Scenario 3: Order Analytics
# Hierarchical data + filters + aggregation pipelines
# ==================================================================
print("\n" + "=" * 50)
print("Scenario 3: Order Analytics")
print("=" * 50)

# 3a. Per-order totals via path aggregation
print("\n--- 3a. Path aggregate: order totals ---")
results = engine.query(table="orders").path_aggregate("items.price", "sum").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine.get_document(entry.doc_id, table="orders")
    total = entry.payload.fields.get("_path_aggregate", 0)
    print(f"  {doc['order_id']} ({doc['customer']}): ${total:.2f}")

# 3b. Filter by nested field + aggregate
print("\n--- 3b. Seoul express orders: total revenue ---")
results = (
    engine.query(table="orders")
    .filter("shipping.city", Equals("Seoul"))
    .filter("shipping.method", Equals("express"))
    .path_aggregate("items.price", "sum")
    .execute()
)
grand = 0.0
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine.get_document(entry.doc_id, table="orders")
    total = entry.payload.fields.get("_path_aggregate", 0)
    grand += total
    print(f"  {doc['order_id']}: ${total:.2f}")
print(f"  Grand total: ${grand:.2f}")

# 3c. Item count distribution
print("\n--- 3c. Item count per order ---")
results = engine.query(table="orders").path_aggregate("items.name", "count").execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    doc = engine.get_document(entry.doc_id, table="orders")
    count = entry.payload.fields.get("_path_aggregate", 0)
    print(f"  {doc['order_id']}: {count} item(s)")

# 3d. Filter on array element
print("\n--- 3d. Orders containing 'webcam' ---")
results = engine.query(table="orders").filter("items.name", Equals("webcam")).execute()
for entry in results:
    doc = engine.get_document(entry.doc_id, table="orders")
    print(f"  {doc['order_id']} ({doc['customer']})")

# 3e. Revenue by shipping method
print("\n--- 3e. Revenue by shipping method ---")
for method in ("express", "standard"):
    results = (
        engine.query(table="orders")
        .filter("shipping.method", Equals(method))
        .path_aggregate("items.price", "sum")
        .execute()
    )
    total = sum(e.payload.fields.get("_path_aggregate", 0) for e in results)
    print(f"  {method:>10}: {len(results)} orders, ${total:.2f}")

# 3f. Faceted search: order status distribution
print("\n--- 3f. Order status distribution ---")
facets = engine.query(table="orders").facet("status")
for status, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
    print(f"  {status:>12}: {count}")


# ==================================================================
# Scenario 4: Comparison of Fusion Strategies
# ==================================================================
print("\n" + "=" * 50)
print("Scenario 4: Fusion Strategy Comparison")
print("=" * 50)

text_signal = (
    engine.query(table="products").term("wireless").score_bayesian_bm25("wireless")
)
vec_signal = engine.query(table="products").vector(audio_query, threshold=0.3)

print("\n--- 4a. Side-by-side: log_odds vs prob_and vs prob_or ---")
for mode_name, fuse_fn in [
    (
        "log_odds",
        lambda: engine.query(table="products").fuse_log_odds(
            text_signal, vec_signal, alpha=0.5
        ),
    ),
    (
        "prob_and",
        lambda: engine.query(table="products").fuse_prob_and(text_signal, vec_signal),
    ),
    (
        "prob_or",
        lambda: engine.query(table="products").fuse_prob_or(text_signal, vec_signal),
    ),
]:
    results = fuse_fn().execute()
    top = sorted(results, key=lambda e: e.payload.score, reverse=True)[:3]
    print(f"\n  {mode_name}:")
    for entry in top:
        doc = engine.get_document(entry.doc_id, table="products")
        print(f"    score={entry.payload.score:.4f}  {doc['name']}")


# ==================================================================
# Scenario 5: Query Plan Introspection
# ==================================================================
print("\n" + "=" * 50)
print("Scenario 5: Query Plans")
print("=" * 50)

# 5a. Simple text search plan
print("\n--- 5a. Text search plan ---")
plan = engine.query(table="products").term("monitor").explain()
print(f"  {plan}")

# 5b. Hybrid search plan
print("\n--- 5b. Hybrid text + vector plan ---")
hybrid = (
    engine.query(table="products")
    .term("wireless")
    .and_(engine.query(table="products").knn(audio_query, k=3))
)
plan = hybrid.explain()
print(f"  {plan}")

# 5c. Fusion plan
print("\n--- 5c. Fusion plan ---")
text_s = engine.query(table="products").term("monitor").score_bayesian_bm25("monitor")
vec_s = engine.query(table="products").knn(display_query, k=3)
fused = engine.query(table="products").fuse_log_odds(text_s, vec_s)
plan = fused.explain()
print(f"  {plan}")


print("\n" + "=" * 70)
print("All multi-paradigm examples completed successfully.")
print("=" * 70)
