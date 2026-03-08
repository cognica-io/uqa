#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""UQA extended SQL function examples.

Demonstrates SQL functions beyond standard SQL:
  - text_match(field, query): BM25 full-text search
  - bayesian_match(field, query): calibrated probability scoring
  - knn_match(k): KNN vector similarity search
  - path_agg(path, func): per-row nested array aggregation
  - path_value(path): nested field access
  - path_filter(path, value): hierarchical path filtering
  - FROM text_search(query, field, table): text search table function
"""

import numpy as np

from uqa.engine import Engine

# ======================================================================
# Data setup
# ======================================================================

engine = Engine(vector_dimensions=8, max_elements=50)

# -- SQL table: articles --
engine.sql("""
    CREATE TABLE articles (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        category TEXT,
        year INTEGER
    )
""")
engine.sql("""INSERT INTO articles (title, body, category, year) VALUES
    ('transformer architecture for nlp',
     'the transformer model uses self attention for sequence processing',
     'nlp', 2017),
    ('bert pre-training deep transformers',
     'bert applies masked language modeling for bidirectional representations',
     'nlp', 2019),
    ('graph neural networks survey',
     'graph neural networks aggregate neighbor features for node classification',
     'graph', 2020),
    ('vision transformer for images',
     'vision transformer processes image patches with transformer encoder',
     'cv', 2021),
    ('diffusion models for generation',
     'diffusion models generate images through iterative denoising steps',
     'cv', 2021),
    ('reinforcement learning from feedback',
     'rlhf trains language models using human preference reward signals',
     'alignment', 2022)
""")

# -- Vector embeddings for knn_match --
rng = np.random.RandomState(42)
for i in range(1, 7):
    vec = rng.randn(8).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    engine.vector_index.add(i, vec)

# -- Documents with nested data for path functions --
engine.add_document(101, {
    "order_id": "ORD-001", "customer": "Alice",
    "items": [
        {"name": "Widget A", "price": 29.99, "qty": 2},
        {"name": "Widget B", "price": 49.99, "qty": 1},
    ],
    "shipping": {"city": "Seoul", "method": "express", "cost": 15.0},
})
engine.add_document(102, {
    "order_id": "ORD-002", "customer": "Bob",
    "items": [
        {"name": "Gadget X", "price": 99.99, "qty": 1},
    ],
    "shipping": {"city": "Busan", "method": "standard", "cost": 5.0},
})
engine.add_document(103, {
    "order_id": "ORD-003", "customer": "Charlie",
    "items": [
        {"name": "Widget A", "price": 29.99, "qty": 3},
        {"name": "Gadget X", "price": 99.99, "qty": 2},
        {"name": "Part Z", "price": 9.99, "qty": 10},
    ],
    "shipping": {"city": "Seoul", "method": "express", "cost": 20.0},
})


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<15}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<15.4f}")
            else:
                vals.append(str(v)[:15].ljust(15))
        print("  " + " | ".join(vals))


print("=" * 70)
print("UQA Extended SQL Function Examples")
print("=" * 70)


# ==================================================================
# text_match: BM25 full-text search
# ==================================================================
show("1. text_match: 'transformer'", engine.sql(
    "SELECT title, text_match(title, 'transformer') AS score "
    "FROM articles WHERE text_match(title, 'transformer') ORDER BY score DESC"
))

show("2. text_match: multi-term 'graph neural'", engine.sql(
    "SELECT title, text_match(body, 'graph neural') AS score "
    "FROM articles WHERE text_match(body, 'graph neural')"
))


# ==================================================================
# text_match + relational filter
# ==================================================================
show("3. text_match + year filter", engine.sql(
    "SELECT title, year FROM articles "
    "WHERE text_match(title, 'transformer') AND year >= 2019 "
    "ORDER BY year"
))


# ==================================================================
# bayesian_match: calibrated probability
# ==================================================================
show("4. bayesian_match: P(relevant|'attention')", engine.sql(
    "SELECT title, bayesian_match(body, 'attention') AS prob "
    "FROM articles WHERE bayesian_match(body, 'attention') ORDER BY prob DESC"
))


# ==================================================================
# knn_match: vector similarity search
# ==================================================================
query_vec = rng.randn(8).astype(np.float32)
query_vec = query_vec / np.linalg.norm(query_vec)
engine.set_query_vector(query_vec)

show("5. knn_match(3): top-3 nearest", engine.sql(
    "SELECT title, _score FROM articles WHERE knn_match(3) ORDER BY _score DESC"
))


# ==================================================================
# knn_match + relational filter
# ==================================================================
show("6. knn_match + category filter", engine.sql(
    "SELECT title, category, _score FROM articles "
    "WHERE knn_match(5) AND category = 'nlp' ORDER BY _score DESC"
))


# ==================================================================
# FROM text_search: text search as table function
# ==================================================================
show("7. FROM text_search()", engine.sql(
    "SELECT title, _score FROM text_search('transformer model', 'title', 'articles') "
    "ORDER BY _score DESC"
))


# ==================================================================
# path_agg: per-row nested array aggregation
# ==================================================================
show("8. path_agg: SUM(items.price)", engine.sql(
    "SELECT path_agg('items.price', 'sum') AS total FROM _default"
))

show("9. path_agg: COUNT(items.name)", engine.sql(
    "SELECT path_agg('items.name', 'count') AS item_count FROM _default"
))

show("10. path_agg: AVG(items.price)", engine.sql(
    "SELECT path_agg('items.price', 'avg') AS avg_price FROM _default"
))

show("11. path_agg: MIN + MAX", engine.sql(
    "SELECT path_agg('items.price', 'min') AS lo, "
    "path_agg('items.price', 'max') AS hi FROM _default"
))


# ==================================================================
# path_value: access nested field
# ==================================================================
show("12. path_value: shipping.city", engine.sql(
    "SELECT path_value('shipping.city') AS city, "
    "path_value('shipping.cost') AS cost FROM _default"
))


# ==================================================================
# path_filter: hierarchical WHERE clause
# ==================================================================
show("13. path_filter: shipping.city = 'Seoul'", engine.sql(
    "SELECT * FROM _default WHERE path_filter('shipping.city', 'Seoul')"
))

show("14. path_filter: shipping.cost > 10", engine.sql(
    "SELECT * FROM _default WHERE path_filter('shipping.cost', '>', 10)"
))

show("15. path_filter: items.name = 'Widget A' (any-match)", engine.sql(
    "SELECT * FROM _default WHERE path_filter('items.name', 'Widget A')"
))


# ==================================================================
# Combined: path_filter + path_agg
# ==================================================================
show("16. Seoul orders total", engine.sql(
    "SELECT path_agg('items.price', 'sum') AS total "
    "FROM _default WHERE path_filter('shipping.city', 'Seoul')"
))


print("\n" + "=" * 70)
print("All extended SQL function examples completed successfully.")
print("=" * 70)
