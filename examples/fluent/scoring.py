#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Scoring features via the fluent QueryBuilder API.

Demonstrates:
  - .score_bayesian_bm25() -- Bayesian BM25 calibrated probabilities
  - .sparse_threshold() -- ReLU thresholding
  - .score_multi_field_bayesian() -- multi-field Bayesian BM25
  - .learn_params() -- parameter learning via QueryBuilder
  - .score_bayesian_with_prior() -- Bayesian BM25 with external prior
"""

from __future__ import annotations

from uqa.engine import Engine
from uqa.scoring.external_prior import authority_prior

# ======================================================================
# Data setup: academic papers
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        authority TEXT DEFAULT 'medium'
    )
""")

papers = [
    (
        1,
        {
            "title": "attention is all you need",
            "abstract": "transformer model self attention mechanisms",
            "authority": "high",
        },
    ),
    (
        2,
        {
            "title": "bert pre-training deep bidirectional",
            "abstract": "masked language modeling pre-training transformers",
            "authority": "high",
        },
    ),
    (
        3,
        {
            "title": "graph attention networks",
            "abstract": "attention mechanisms graph structured data",
            "authority": "medium",
        },
    ),
    (
        4,
        {
            "title": "vision transformer image recognition",
            "abstract": "image patches standard transformer encoder",
            "authority": "medium",
        },
    ),
    (
        5,
        {
            "title": "scaling language models methods",
            "abstract": "scaling laws language model performance compute",
            "authority": "low",
        },
    ),
    (
        6,
        {
            "title": "diffusion models beat gans",
            "abstract": "denoising diffusion probabilistic models image quality",
            "authority": "medium",
        },
    ),
    (
        7,
        {
            "title": "reinforcement learning human feedback",
            "abstract": "rlhf language models instructions reward modeling",
            "authority": "high",
        },
    ),
    (
        8,
        {
            "title": "efficient attention long sequences",
            "abstract": "linear attention sparse attention patterns quadratic",
            "authority": "low",
        },
    ),
]

for doc_id, doc in papers:
    engine.add_document(doc_id, doc, table="papers")

print("=" * 70)
print("Scoring Features (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. Bayesian BM25: calibrated probabilities
# ------------------------------------------------------------------
print("\n--- 1. Bayesian BM25: 'attention' ---")
results = (
    engine.query(table="papers")
    .term("attention")
    .score_bayesian_bm25("attention")
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] P(rel)={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 2. Sparse threshold: filter below 0.55
# ------------------------------------------------------------------
print("\n--- 2. Sparse threshold: 'attention' with threshold=0.52 ---")
results = (
    engine.query(table="papers")
    .term("attention")
    .score_bayesian_bm25("attention")
    .sparse_threshold(0.52)
    .execute()
)
print(f"  {len(results)} documents above threshold")
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 3. Multi-field Bayesian BM25
# ------------------------------------------------------------------
print("\n--- 3. Multi-field Bayesian: 'transformer' across title + abstract ---")
results = (
    engine.query(table="papers")
    .score_multi_field_bayesian("transformer", ["title", "abstract"])
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] P(rel)={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 4. Multi-field with weights: title weighted higher
# ------------------------------------------------------------------
print("\n--- 4. Multi-field with weights: title=2.0, abstract=0.5 ---")
results = (
    engine.query(table="papers")
    .score_multi_field_bayesian("attention", ["title", "abstract"], [2.0, 0.5])
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] P(rel)={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 5. learn_params: parameter learning via QueryBuilder
# ------------------------------------------------------------------
print("\n--- 5. Parameter learning for 'attention' query ---")

# Labels: 1 = relevant, 0 = not relevant
# Papers 1, 3, 8 strongly mention attention
labels = [1, 0, 1, 0, 0, 0, 0, 1]

learned = engine.query(table="papers").learn_params("attention", labels, field="title")
print("  Learned parameters:")
for param, value in sorted(learned.items()):
    print(f"    {param}: {value:.6f}")


# ------------------------------------------------------------------
# 6. Bayesian BM25 with external prior (authority)
# ------------------------------------------------------------------
print("\n--- 6. Bayesian BM25 with authority prior ---")

prior_fn = authority_prior("authority")

results = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_with_prior("attention", field="title", prior_fn=prior_fn)
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(
        f"  [{entry.doc_id}] P(rel)={entry.payload.score:.4f}  "
        f"{doc['title']} [{doc['authority']}]"
    )


# ------------------------------------------------------------------
# 7. Comparison: standard vs authority-boosted scoring
# ------------------------------------------------------------------
print("\n--- 7. Comparison: standard Bayesian vs authority-boosted ---")

standard = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
    .execute()
)
boosted = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_with_prior("attention", field="title", prior_fn=prior_fn)
    .execute()
)

std_map = {e.doc_id: e.payload.score for e in standard}
boost_map = {e.doc_id: e.payload.score for e in boosted}

print(f"  {'Title':<35} {'Standard':>10} {'Boosted':>10} {'Authority':>10}")
print(f"  {'-' * 67}")
for doc_id in sorted(std_map.keys()):
    doc = engine.get_document(doc_id, table="papers")
    std_score = std_map.get(doc_id, 0.0)
    bst_score = boost_map.get(doc_id, 0.0)
    print(
        f"  {doc['title'][:35]:<35} "
        f"{std_score:>10.4f} {bst_score:>10.4f} {doc['authority']:>10}"
    )


# ------------------------------------------------------------------
# 8. EXPLAIN: scoring pipeline plan
# ------------------------------------------------------------------
print("\n--- 8. EXPLAIN: Bayesian BM25 scoring plan ---")
plan = (
    engine.query(table="papers")
    .term("attention")
    .score_bayesian_bm25("attention")
    .explain()
)
print(f"  {plan}")


print("\n" + "=" * 70)
print("All scoring examples completed successfully.")
print("=" * 70)
