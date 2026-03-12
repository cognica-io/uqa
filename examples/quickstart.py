#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""UQA quickstart: hybrid search in under 30 lines.

Shows the core UQA workflow: create a table with text and vector columns,
insert documents via SQL, then run text search, vector search, and
fused hybrid search -- all through standard SQL.
"""

import numpy as np

from uqa.engine import Engine

engine = Engine()

# -- Schema: a table with text and vector columns -----------------------
engine.sql("""
    CREATE TABLE docs (
        id INTEGER PRIMARY KEY,
        title TEXT,
        body TEXT,
        embedding VECTOR(4)
    )
""")

# -- Insert documents with embeddings via SQL ---------------------------
engine.sql("""
    INSERT INTO docs (id, title, body, embedding) VALUES
    (1, 'Introduction to UQA',
     'UQA unifies relational text vector and graph queries through posting lists',
     ARRAY[0.9, 0.1, 0.0, 0.0]),
    (2, 'Vector Search Basics',
     'vector similarity search finds nearest neighbors in embedding space',
     ARRAY[0.1, 0.9, 0.1, 0.0]),
    (3, 'Graph Databases',
     'graph queries traverse vertices and edges to discover relationships',
     ARRAY[0.0, 0.1, 0.9, 0.0]),
    (4, 'Hybrid Retrieval',
     'combining text search with vector similarity improves retrieval quality',
     ARRAY[0.5, 0.5, 0.0, 0.1])
""")

# -- 1. Text search (BM25) ---------------------------------------------
print("--- Text search: 'vector search' ---")
result = engine.sql(
    "SELECT id, title, _score AS s FROM docs "
    "WHERE text_match(body, 'vector search') "
    "ORDER BY s DESC"
)
for row in result.rows:
    print(f"  [{row['id']}] {row['title']}  (score: {row['s']:.4f})")

# -- 2. Vector search (KNN) --------------------------------------------
print("\n--- Vector search: nearest to [0.5, 0.5, 0.0, 0.0] ---")
query_vec = np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32)
result = engine.sql(
    "SELECT id, title, _score AS s FROM docs "
    "WHERE knn_match(embedding, $1, 3) "
    "ORDER BY s DESC",
    params=[query_vec],
)
for row in result.rows:
    print(f"  [{row['id']}] {row['title']}  (sim: {row['s']:.4f})")

# -- 3. Hybrid: fuse text + vector signals -----------------------------
print("\n--- Hybrid: fuse_log_odds(text, vector) ---")
result = engine.sql(
    "SELECT id, title, _score AS s FROM docs "
    "WHERE fuse_log_odds("
    "  text_match(body, 'vector search'), "
    "  knn_match(embedding, $1, 3)"
    ") ORDER BY s DESC",
    params=[query_vec],
)
for row in result.rows:
    print(f"  [{row['id']}] {row['title']}  (fused: {row['s']:.4f})")

# -- 4. Inspect the query plan -----------------------------------------
print("\n--- EXPLAIN ---")
result = engine.sql(
    "EXPLAIN SELECT id, title FROM docs "
    "WHERE fuse_log_odds("
    "  text_match(body, 'vector search'), "
    "  knn_match(embedding, $1, 3)"
    ")",
    params=[query_vec],
)
for row in result.rows:
    print(f"  {row['plan']}")
