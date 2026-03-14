#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Fusion gating and progressive fusion SQL examples.

Demonstrates:
  - fuse_log_odds with ReLU gating
  - fuse_log_odds with Swish gating
  - Gating vs no-gating comparison
  - Alpha + gating combined parameters
  - Progressive fusion via staged_retrieval
"""

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: research papers with text, vectors, and citations
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        year INTEGER NOT NULL,
        field TEXT,
        citations INTEGER DEFAULT 0,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

papers = [
    ("attention is all you need", 2017, "nlp", 90000),
    ("bert pre-training deep bidirectional", 2019, "nlp", 75000),
    ("graph attention networks", 2018, "graph", 15000),
    ("vision transformer image recognition", 2021, "cv", 25000),
    ("scaling language models methods analysis", 2020, "nlp", 8000),
    ("diffusion models beat generative adversarial", 2021, "cv", 12000),
    ("reinforcement learning human feedback alignment", 2022, "alignment", 5000),
    ("efficient attention for long sequences", 2020, "nlp", 3000),
    ("neural machine translation sequence models", 2017, "nlp", 40000),
    ("contrastive learning visual representations", 2020, "cv", 20000),
]
for title, year, fld, cit in papers:
    vec = rng.randn(8).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, year, field, citations, embedding) "
        f"VALUES ('{title}', {year}, '{fld}', {cit}, {arr})"
    )

# Citation graph
engine.add_graph_edge(Edge(1, 2, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(2, 3, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(3, 4, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(4, 5, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(5, 5, 2, "cites"), table="papers")
engine.add_graph_edge(Edge(6, 7, 5, "cites"), table="papers")
engine.add_graph_edge(Edge(7, 9, 1, "cites"), table="papers")

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
print("Fusion Gating and Progressive Fusion Examples (SQL)")
print("=" * 70)


# ==================================================================
# 1. fuse_log_odds: baseline (no gating)
# ==================================================================
show(
    "1. fuse_log_odds: no gating (default)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cites', 1)
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 2. fuse_log_odds with ReLU gating
# ==================================================================
show(
    "2. fuse_log_odds with 'relu' gating",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cites', 1),
        'relu'
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 3. fuse_log_odds with Swish gating
# ==================================================================
show(
    "3. fuse_log_odds with 'swish' gating",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cites', 1),
        'swish'
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 4. Comparison: no gating vs relu vs swish
# ==================================================================
print("\n--- 4. Comparison: gating strategies ---")
for gating in ("none", "relu", "swish"):
    if gating == "none":
        query = """
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention transformer'),
                traverse_match(1, 'cites', 2)
            )
            ORDER BY _score DESC LIMIT 3
        """
    else:
        query = f"""
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention transformer'),
                traverse_match(1, 'cites', 2),
                '{gating}'
            )
            ORDER BY _score DESC LIMIT 3
        """
    result = engine.sql(query)
    print(f"\n  gating='{gating}':")
    for row in result.rows:
        print(f"    score={row['_score']:.4f}  {row['title']}")


# ==================================================================
# 5. Alpha + gating combined
# ==================================================================
show(
    "5. fuse_log_odds with alpha=0.8 and 'relu' gating",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        traverse_match(1, 'cites', 1),
        0.8,
        'relu'
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 6. Three-signal fusion with gating
# ==================================================================
show(
    "6. Three-signal fusion with swish gating",
    engine.sql(
        """
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention transformer'),
        knn_match(embedding, $1, 5),
        traverse_match(1, 'cites', 2),
        'swish'
    )
    ORDER BY _score DESC
""",
        params=[query_vec],
    ),
)


# ==================================================================
# 7. Progressive fusion via staged_retrieval
# ==================================================================
show(
    "7. staged_retrieval: text (top-5) then vector (top-3)",
    engine.sql(
        """
    SELECT title, _score FROM papers
    WHERE staged_retrieval(
        text_match(title, 'attention'), 5,
        knn_match(embedding, $1, 3), 3
    )
    ORDER BY _score DESC
""",
        params=[query_vec],
    ),
)


# ==================================================================
# 8. Gating + relational filter
# ==================================================================
show(
    "8. Gating with relational filter (year >= 2020)",
    engine.sql("""
    SELECT title, year, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'learning models'),
        traverse_match(1, 'cites', 2),
        'relu'
    ) AND year >= 2020
    ORDER BY _score DESC
"""),
)


print("\n" + "=" * 70)
print("All fusion gating examples completed successfully.")
print("=" * 70)
