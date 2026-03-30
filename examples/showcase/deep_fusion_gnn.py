#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deep Fusion as GNN: graph propagation layers for message passing.

PropagateLayer spreads scores through graph edges:

    For each vertex v:
        agg = aggregate(prob(neighbors of v))
        l_new(v) = l_old(v) + logit(agg)

This is one round of GNN message passing with a logit-space residual.
Stacking multiple propagate layers = multi-hop reasoning.

Demonstrates:
  1. 1-hop propagation (signal -> propagate)
  2. Multi-hop reasoning (signal -> propagate -> propagate)
  3. Aggregation comparison (mean vs sum vs max)
  4. Mixed: signal -> propagate -> signal (GNN + refinement)
  5. Direction control (out, in, both)
"""

from __future__ import annotations

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: papers with citation graph
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        embedding VECTOR(8)
    )
""")
engine.sql("CREATE INDEX idx_papers_gin ON papers USING gin (title)")

rng = np.random.RandomState(42)

paper_data = [
    (
        "attention is all you need",
        "self attention mechanisms replacing recurrence and convolutions",
    ),
    (
        "bert pre-training deep bidirectional transformers",
        "masked language modeling pre-training fine-tuning",
    ),
    (
        "deep residual learning for image recognition",
        "residual connections deep convolutional networks",
    ),
    (
        "generative adversarial networks",
        "adversarial training generator discriminator minimax",
    ),
    ("graph attention networks", "attention mechanisms for graph neural networks"),
    (
        "language models are few-shot learners",
        "scaling language models in-context learning prompting",
    ),
    (
        "vision transformer image recognition at scale",
        "pure transformer applied to sequences of image patches",
    ),
    (
        "denoising diffusion probabilistic models",
        "progressive denoising noise schedule image generation",
    ),
    (
        "flash attention fast memory-efficient attention",
        "io-aware exact attention algorithm tiling kernel fusion",
    ),
    (
        "neural machine translation by learning to align",
        "soft attention mechanism for alignment in translation",
    ),
]

for title, abstract in paper_data:
    vec = rng.randn(8).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, abstract, embedding) "
        f"VALUES ('{title}', '{abstract}', {arr})"
    )

# Dense citation graph
#   1 (Transformer) <- 2 (BERT), 5 (GAT), 6 (GPT-3), 7 (ViT), 9 (Flash), 10 (NMT)
#   2 (BERT) <- 5 (GAT), 6 (GPT-3)
#   3 (ResNet) <- 7 (ViT)
#   1 -> 10 (Transformer cites NMT)
engine.add_graph_edge(Edge(1, 2, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(2, 5, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(3, 6, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(4, 6, 2, "cites"), table="papers")
engine.add_graph_edge(Edge(5, 7, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(6, 9, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(7, 5, 2, "cites"), table="papers")
engine.add_graph_edge(Edge(8, 7, 3, "cites"), table="papers")
engine.add_graph_edge(Edge(9, 10, 1, "cites"), table="papers")
engine.add_graph_edge(Edge(10, 1, 10, "cites"), table="papers")

nlp_query = rng.randn(8).astype(np.float32)
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
print("Deep Fusion as GNN: Graph Propagation Layers")
print("=" * 70)


# ======================================================================
# 1. One-hop propagation
# ======================================================================
print("\n" + "=" * 60)
print("1. One-Hop Propagation")
print("=" * 60)
print(
    "\n  Layer 0: text match seeds 'attention' scores\n"
    "  Layer 1: propagate through citations (1-hop neighbors get scores)\n"
)

text_only = engine.sql("""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention'))
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(text_only, "Before propagation (text only):")

result_1hop = engine.sql("""
    SELECT title, _score FROM papers
    WHERE deep_fusion(
        layer(bayesian_match(title, 'attention')),
        propagate('cites', 'mean')
    ) ORDER BY _score DESC LIMIT 5
""")
print_results(result_1hop, "After 1-hop propagation:")


# ======================================================================
# 2. Multi-hop reasoning (2-hop)
# ======================================================================
print("\n" + "=" * 60)
print("2. Multi-Hop Reasoning: 2-hop propagation")
print("=" * 60)
print(
    "\n  Each propagate layer extends the reach by one hop.\n"
    "  2 layers = scores reach 2-hop citation neighbors.\n"
)

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
# 3. Aggregation comparison
# ======================================================================
print("\n" + "=" * 60)
print("3. Aggregation Function Comparison")
print("=" * 60)
print(
    "\n  mean: average neighbor probability (smooth spread)\n"
    "  sum:  total neighbor probability (hub amplification)\n"
    "  max:  strongest neighbor probability (best-path)\n"
)

for agg in ("mean", "sum", "max"):
    result = engine.sql(f"""
        SELECT title, _score FROM papers
        WHERE deep_fusion(
            layer(bayesian_match(title, 'attention')),
            propagate('cites', '{agg}')
        ) ORDER BY _score DESC LIMIT 3
    """)
    print_results(result, f"aggregation='{agg}':")


# ======================================================================
# 4. Mixed: signal -> propagate -> signal
# ======================================================================
print("\n" + "=" * 60)
print("4. Mixed: signal -> propagate -> signal")
print("=" * 60)
print(
    "\n  Layer 0: text relevance (seed)\n"
    "  Layer 1: citation propagation (spread)\n"
    "  Layer 2: vector similarity (refine)\n"
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
print_results(result, "signal -> propagate -> signal (ReLU gating):")


# ======================================================================
# 5. Direction control
# ======================================================================
print("\n" + "=" * 60)
print("5. Direction Control: out vs in vs both")
print("=" * 60)
print(
    "\n  out:  follow citation edges forward (who does X cite?)\n"
    "  in:   follow citation edges backward (who cites X?)\n"
    "  both: bidirectional (default)\n"
)

for direction in ("out", "in", "both"):
    result = engine.sql(f"""
        SELECT title, _score FROM papers
        WHERE deep_fusion(
            layer(bayesian_match(title, 'attention')),
            propagate('cites', 'mean', '{direction}')
        ) ORDER BY _score DESC LIMIT 3
    """)
    print_results(result, f"direction='{direction}':")

print("\n" + "=" * 70)
print("GNN demonstration completed successfully.")
print("=" * 70)
