#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Cross-paradigm fusion SQL examples.

Demonstrates:
  - fuse_log_odds(): log-odds conjunction of multiple signals
  - fuse_prob_and(): probabilistic AND fusion
  - fuse_prob_or(): probabilistic OR fusion
  - fuse_prob_not(): probabilistic complement
  - Multi-signal fusion with text + vector + graph
  - Fusion with relational filters
  - Alpha parameter tuning for log-odds
"""

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: academic papers with text, vectors, and citation graph
# ======================================================================

engine = Engine(vector_dimensions=8, max_elements=50)

# -- SQL table with vector column --
engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        year INTEGER NOT NULL,
        venue TEXT,
        field TEXT,
        citations INTEGER DEFAULT 0,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

titles = [
    ('attention is all you need',                    2017, 'NeurIPS', 'nlp',       90000),
    ('bert pre-training deep bidirectional',         2019, 'NAACL',   'nlp',       75000),
    ('graph attention networks',                     2018, 'ICLR',    'graph',     15000),
    ('vision transformer image recognition',         2021, 'ICLR',    'cv',        25000),
    ('scaling language models methods insights',     2020, 'arXiv',   'nlp',       8000),
    ('diffusion models beat gans',                   2021, 'NeurIPS', 'cv',        12000),
    ('reinforcement learning human feedback',        2022, 'NeurIPS', 'alignment', 5000),
    ('efficient attention long sequences',           2020, 'ICML',    'nlp',       3000),
]
for title, year, venue, fld, cit in titles:
    vec = rng.randn(8).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, year, venue, field, citations, embedding) "
        f"VALUES ('{title}', {year}, '{venue}', '{fld}', {cit}, {arr})"
    )

# -- Citation graph (per-table: edges between paper rows) --
# Paper 1 (attention) cited by 2, 3, 4
engine.add_graph_edge(Edge(1, 1, 2, "cited_by"), table="papers")
engine.add_graph_edge(Edge(2, 1, 3, "cited_by"), table="papers")
engine.add_graph_edge(Edge(3, 1, 4, "cited_by"), table="papers")
# Paper 2 (bert) cited by 5, 7
engine.add_graph_edge(Edge(4, 2, 5, "cited_by"), table="papers")
engine.add_graph_edge(Edge(5, 2, 7, "cited_by"), table="papers")
# Paper 3 (GAT) cited by 4
engine.add_graph_edge(Edge(6, 3, 4, "cited_by"), table="papers")

# -- Query vector for knn_match --
query_vec = rng.randn(8).astype(np.float32)
query_vec = query_vec / np.linalg.norm(query_vec)


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<20}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<20.4f}")
            else:
                vals.append(str(v)[:20].ljust(20))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Cross-Paradigm Fusion SQL Examples")
print("=" * 70)


# ==================================================================
# fuse_log_odds: text + graph
# ==================================================================
show("1. fuse_log_odds: text + graph", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cited_by', 1)
    )
    ORDER BY _score DESC
"""))


# ==================================================================
# fuse_log_odds: text + vector
# ==================================================================
show("2. fuse_log_odds: text + vector", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'transformer'),
        knn_match(embedding, $1, 5)
    )
    ORDER BY _score DESC
""", params=[query_vec]))


# ==================================================================
# fuse_log_odds: 3 signals (text + vector + graph)
# ==================================================================
show("3. fuse_log_odds: text + vector + graph", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention transformer'),
        knn_match(embedding, $1, 5),
        traverse_match(1, 'cited_by', 2)
    )
    ORDER BY _score DESC
""", params=[query_vec]))


# ==================================================================
# fuse_log_odds with alpha parameter
# ==================================================================
show("4. fuse_log_odds with alpha=0.8 (high confidence)", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cited_by', 1),
        0.8
    )
    ORDER BY _score DESC
"""))


# ==================================================================
# fuse_log_odds + relational filter
# ==================================================================
show("5. fusion + year >= 2019", engine.sql("""
    SELECT title, year, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention transformer'),
        knn_match(embedding, $1, 5)
    ) AND year >= 2019
    ORDER BY _score DESC
""", params=[query_vec]))


# ==================================================================
# fuse_prob_and: probabilistic AND
# ==================================================================
show("6. fuse_prob_and: text AND graph", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_prob_and(
        text_match(title, 'attention'),
        traverse_match(1, 'cited_by', 1)
    )
    ORDER BY _score DESC
"""))


# ==================================================================
# fuse_prob_or: probabilistic OR (broader recall)
# ==================================================================
show("7. fuse_prob_or: text OR graph", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_prob_or(
        text_match(title, 'diffusion'),
        traverse_match(1, 'cited_by', 2)
    )
    ORDER BY _score DESC
"""))


# ==================================================================
# fuse_prob_not: probabilistic complement
# ==================================================================
show("8. fuse_prob_not: NOT text_match('attention')", engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_prob_not(
        text_match(title, 'attention')
    )
    ORDER BY _score DESC
"""))


# ==================================================================
# Side-by-side comparison: different fusion strategies
# ==================================================================
print("\n--- 9. Comparison: log_odds vs prob_and vs prob_or ---")
for mode in ("fuse_log_odds", "fuse_prob_and", "fuse_prob_or"):
    result = engine.sql(f"""
        SELECT title, _score FROM papers
        WHERE {mode}(
            text_match(title, 'transformer'),
            traverse_match(1, 'cited_by', 1)
        )
        ORDER BY _score DESC LIMIT 3
    """)
    print(f"\n  {mode}:")
    for row in result.rows:
        print(f"    score={row['_score']:.4f}  {row['title']}")


# ==================================================================
# EXPLAIN fusion query plan
# ==================================================================
result = engine.sql("""
    EXPLAIN SELECT * FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        knn_match(embedding, $1, 3),
        traverse_match(1, 'cited_by', 1)
    )
""", params=[query_vec])
print("\n--- 10. EXPLAIN fusion plan ---")
for row in result.rows:
    print(f"  {row['plan']}")


print("\n" + "=" * 70)
print("All fusion SQL examples completed successfully.")
print("=" * 70)
