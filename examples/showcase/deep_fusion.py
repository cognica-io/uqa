#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deep Fusion: multi-layer Bayesian networks via SQL.

Paper 4 proves that Bayesian multi-signal fusion IS a feedforward neural
network. The deep_fusion() operator extends this to multi-layer networks:

    l^(k) = g( l^(k-1) + sum_j logit(P_j^(k)) )
    P_final = sigmoid(l^(K))

This gives us:
  - ResNet when layers are signal groups (residual = logit accumulation)
  - GNN when layers propagate scores through graph edges

Demonstrates:
  1. Hierarchical fusion (text + vector, then graph signals)
  2. Multi-hop graph reasoning (signal + 2x propagate)
  3. Mixed fusion (signal + propagate + signal)
  4. Gating comparison (none vs relu vs swish)
  5. EXPLAIN plan output
"""

from __future__ import annotations

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: research papers with text + vector signals + citations
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

# Citation graph
engine.add_graph_edge(Edge(1, 2, 1, "cites"), table="papers")  # BERT cites Transformer
engine.add_graph_edge(Edge(2, 5, 1, "cites"), table="papers")  # GAT cites Transformer
engine.add_graph_edge(Edge(3, 6, 1, "cites"), table="papers")  # GPT-3 cites Transformer
engine.add_graph_edge(Edge(4, 6, 2, "cites"), table="papers")  # GPT-3 cites BERT
engine.add_graph_edge(Edge(5, 7, 1, "cites"), table="papers")  # ViT cites Transformer
engine.add_graph_edge(Edge(6, 9, 1, "cites"), table="papers")  # Flash cites Transformer
engine.add_graph_edge(Edge(7, 5, 2, "cites"), table="papers")  # GAT cites BERT
engine.add_graph_edge(Edge(8, 7, 3, "cites"), table="papers")  # ViT cites ResNet
engine.add_graph_edge(Edge(9, 10, 1, "cites"), table="papers")  # NMT cites Transformer

nlp_query = field_centers["nlp"].astype(np.float32)
nlp_query = nlp_query + rng.randn(8).astype(np.float32) * 0.05
nlp_query = (nlp_query / np.linalg.norm(nlp_query)).astype(np.float32)


def print_results(result, label=""):
    if label:
        print(f"\n  {label}")
    for row in result.rows:
        title = row.get("title", "")
        score = row["_score"]
        print(f"    [{score:.4f}] {title}")


print("=" * 70)
print("Deep Fusion: Multi-Layer Bayesian Networks via SQL")
print("=" * 70)


# ======================================================================
# 1. Hierarchical Fusion (text + vector, then graph)
# ======================================================================
print("\n" + "=" * 60)
print("1. Hierarchical Fusion: text + vector -> graph signals")
print("=" * 60)
print(
    "\n  Layer 0: text + vector signals (within-layer conjunction)\n"
    "  Layer 1: graph centrality signal (residual addition)\n"
)

arr = "ARRAY[" + ",".join(str(float(v)) for v in nlp_query) + "]"

result = engine.sql(f"""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 10)),
        layer(pagerank('papers'))
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result, "Top-5 by hierarchical deep fusion:")


# ======================================================================
# 2. Multi-Hop Graph Reasoning (signal + 2x propagate)
# ======================================================================
print("\n" + "=" * 60)
print("2. Multi-Hop GNN: signal -> propagate -> propagate")
print("=" * 60)
print(
    "\n  Layer 0: text signal seeds initial scores\n"
    "  Layer 1: 1-hop propagation through citations\n"
    "  Layer 2: 2-hop propagation (scores reach 2-hop neighbors)\n"
)

result_1hop = engine.sql("""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        propagate('cites', 'mean')
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result_1hop, "After 1-hop propagation:")

result_2hop = engine.sql("""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        propagate('cites', 'mean'),
        propagate('cites', 'mean')
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result_2hop, "After 2-hop propagation:")


# ======================================================================
# 3. Mixed Fusion (signal + propagate + signal)
# ======================================================================
print("\n" + "=" * 60)
print("3. Mixed Fusion: signal -> propagate -> signal")
print("=" * 60)
print(
    "\n  Layer 0: text match seeds relevance\n"
    "  Layer 1: propagate through citations\n"
    "  Layer 2: vector similarity refines ranking\n"
)

result = engine.sql(f"""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        propagate('cites', 'mean'),
        layer(knn_match(embedding, {arr}, 10)),
        gating => 'relu'
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result, "Mixed fusion (signal + propagate + signal, ReLU gating):")


# ======================================================================
# 4. Gating Comparison (none vs relu vs swish)
# ======================================================================
print("\n" + "=" * 60)
print("4. Gating Function Comparison")
print("=" * 60)
print(
    "\n  none:  identity (standard log-odds)\n"
    "  relu:  max(0, logit) -- MAP under sparse prior\n"
    "  swish: logit * sigmoid(logit) -- Bayesian posterior mean\n"
)

for gating in ("none", "relu", "swish"):
    result = engine.sql(f"""
        SELECT title, _score FROM papers
        WHERE deep_fusion(
            layer(bayesian_match(title, 'attention'),
                  bayesian_match(abstract, 'transformer')),
            propagate('cites', 'mean'),
            gating => '{gating}'
        ) ORDER BY _score DESC LIMIT 3
    """)
    print_results(result, f"gating='{gating}':")


# ======================================================================
# 5. EXPLAIN Plan
# ======================================================================
print("\n" + "=" * 60)
print("5. EXPLAIN Output")
print("=" * 60)

explain = engine.sql(f"""
    EXPLAIN SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 10)),
        propagate('cites', 'mean'),
        layer(pagerank('papers')),
        gating => 'relu'
    ) ORDER BY _score DESC
""")

for row in explain.rows:
    print(f"  {row['plan']}")

print("\n" + "=" * 70)
print("All deep fusion demonstrations completed successfully.")
print("=" * 70)
