#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deep Fusion as ResNet: hierarchical signal layers with residual connections.

Each SignalLayer adds its fused logits to the running accumulator:

    l^(k) = g( l^(k-1) + sum_j logit(P_j^(k)) )

This is mathematically identical to ResNet skip connections:

    x^(k) = g( x^(k-1) + F(x^(k-1)) )

Demonstrates:
  1. Single layer (baseline)
  2. Two-layer hierarchical fusion (text -> vector)
  3. Three-layer deep hierarchy (text -> vector -> graph centrality)
  4. Gating comparison (none vs relu vs swish)
  5. EXPLAIN plan
"""

from __future__ import annotations

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        year INTEGER NOT NULL,
        field TEXT,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

paper_data = [
    (
        "attention is all you need",
        "self attention mechanisms replacing recurrence and convolutions",
        2017,
        "nlp",
    ),
    (
        "bert pre-training deep bidirectional transformers",
        "masked language modeling pre-training fine-tuning",
        2019,
        "nlp",
    ),
    (
        "deep residual learning for image recognition",
        "residual connections deep convolutional networks",
        2016,
        "cv",
    ),
    (
        "generative adversarial networks",
        "adversarial training generator discriminator minimax",
        2014,
        "generative",
    ),
    (
        "graph attention networks",
        "attention mechanisms for graph neural networks",
        2018,
        "graph",
    ),
    (
        "language models are few-shot learners",
        "scaling language models in-context learning prompting",
        2020,
        "nlp",
    ),
    (
        "vision transformer image recognition at scale",
        "pure transformer applied to sequences of image patches",
        2021,
        "cv",
    ),
    (
        "denoising diffusion probabilistic models",
        "progressive denoising noise schedule image generation",
        2020,
        "generative",
    ),
    (
        "flash attention fast memory-efficient attention",
        "io-aware exact attention algorithm tiling kernel fusion",
        2022,
        "architecture",
    ),
    (
        "neural machine translation by learning to align",
        "soft attention mechanism for alignment in translation",
        2015,
        "nlp",
    ),
]

field_centers = {
    "nlp": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0]),
    "cv": np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "graph": np.array([0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "generative": np.array([0.0, 0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]),
    "architecture": np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
}

for title, abstract, year, field in paper_data:
    center = field_centers[field].astype(np.float32)
    vec = center + rng.randn(8).astype(np.float32) * 0.1
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, abstract, year, field, embedding) "
        f"VALUES ('{title}', '{abstract}', {year}, '{field}', {arr})"
    )

# Citation graph (needed for pagerank signal)
engine.add_graph_edge(Edge(1, 2, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(2, 5, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(3, 6, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(4, 6, 2, "cites"), table="papers")
engine.add_graph_edge(Edge(5, 7, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(6, 9, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(7, 5, 2, "cites"), table="papers")
engine.add_graph_edge(Edge(8, 7, 3, "cites"), table="papers")
engine.add_graph_edge(Edge(9, 10, 1, "cites"), table="papers")

nlp_query = field_centers["nlp"].astype(np.float32)
nlp_query = nlp_query + rng.randn(8).astype(np.float32) * 0.05
nlp_query = (nlp_query / np.linalg.norm(nlp_query)).astype(np.float32)
arr = "ARRAY[" + ",".join(str(float(v)) for v in nlp_query) + "]"


def print_results(result, label=""):
    if label:
        print(f"\n  {label}")
    for row in result.rows:
        title = row.get("title", "")
        score = row["_score"]
        print(f"    [{score:.4f}] {title}")


print("=" * 70)
print("Deep Fusion as ResNet: Hierarchical Signal Layers")
print("=" * 70)


# ======================================================================
# 1. Single layer (baseline) -- equivalent to fuse_log_odds
# ======================================================================
print("\n" + "=" * 60)
print("1. Single Layer (baseline)")
print("=" * 60)
print("\n  One layer with two signals = standard log-odds fusion\n")

result = engine.sql(f"""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 10))
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result, "Single layer (text + vector):")


# ======================================================================
# 2. Two-layer hierarchy -- text, then vector refinement
# ======================================================================
print("\n" + "=" * 60)
print("2. Two-Layer Hierarchy: text -> vector")
print("=" * 60)
print(
    "\n  Layer 0: text relevance (prior)\n"
    "  Layer 1: vector similarity (refines via residual addition)\n"
    "\n  l^(1) = l^(0) + logit(P_vector)\n"
)

result = engine.sql(f"""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        layer(knn_match(embedding, {arr}, 10))
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result, "Two layers (text -> vector):")


# ======================================================================
# 3. Three-layer deep hierarchy -- text -> vector -> graph centrality
# ======================================================================
print("\n" + "=" * 60)
print("3. Three-Layer Hierarchy: text -> vector -> PageRank")
print("=" * 60)
print(
    "\n  Layer 0: text relevance\n"
    "  Layer 1: vector similarity\n"
    "  Layer 2: graph centrality (important papers get boosted)\n"
)

result = engine.sql(f"""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        layer(knn_match(embedding, {arr}, 10)),
        layer(pagerank('papers'))
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result, "Three layers (text -> vector -> PageRank):")


# ======================================================================
# 4. Gating comparison
# ======================================================================
print("\n" + "=" * 60)
print("4. Gating Function Comparison")
print("=" * 60)
print(
    "\n  none:  g(l) = l              -- identity\n"
    "  relu:  g(l) = max(0, l)      -- MAP under sparse prior\n"
    "  swish: g(l) = l * sigmoid(l) -- Bayesian posterior mean\n"
)

for gating in ("none", "relu", "swish"):
    result = engine.sql(f"""
        SELECT title, _score FROM papers
        WHERE deep_fusion(
            layer(bayesian_match(title, 'attention'),
                  bayesian_match(abstract, 'transformer')),
            layer(knn_match(embedding, {arr}, 10)),
            gating => '{gating}'
        ) ORDER BY _score DESC LIMIT 3
    """)
    print_results(result, f"gating='{gating}':")


# ======================================================================
# 5. EXPLAIN
# ======================================================================
print("\n" + "=" * 60)
print("5. EXPLAIN Output")
print("=" * 60)
print()

explain = engine.sql(f"""
    EXPLAIN SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 10)),
        layer(bayesian_match(abstract, 'transformer')),
        layer(pagerank('papers')),
        gating => 'relu'
    ) ORDER BY _score DESC
""")
for row in explain.rows:
    print(f"  {row['plan']}")

print("\n" + "=" * 70)
print("ResNet demonstration completed successfully.")
print("=" * 70)
