#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Advanced fusion features via the fluent QueryBuilder API.

Demonstrates:
  - .fuse_attention() -- attention-weighted fusion
  - .fuse_learned() -- learned-weight fusion
  - .multi_stage() -- multi-stage retrieval pipeline
  - Comparison of different fusion strategies
"""

from __future__ import annotations

from uqa.engine import Engine

# ======================================================================
# Data setup: academic papers
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        year INTEGER,
        field TEXT
    )
""")

papers = [
    (
        1,
        {
            "title": "attention is all you need",
            "abstract": "transformer model self attention mechanisms",
            "year": 2017,
            "field": "nlp",
        },
    ),
    (
        2,
        {
            "title": "bert pre-training deep bidirectional",
            "abstract": "masked language modeling pre-training transformers",
            "year": 2019,
            "field": "nlp",
        },
    ),
    (
        3,
        {
            "title": "graph attention networks",
            "abstract": "attention mechanisms graph structured data",
            "year": 2018,
            "field": "graph",
        },
    ),
    (
        4,
        {
            "title": "vision transformer image recognition",
            "abstract": "image patches standard transformer encoder",
            "year": 2021,
            "field": "cv",
        },
    ),
    (
        5,
        {
            "title": "scaling language models methods",
            "abstract": "scaling laws language model performance compute",
            "year": 2020,
            "field": "nlp",
        },
    ),
    (
        6,
        {
            "title": "diffusion models beat gans",
            "abstract": "denoising diffusion probabilistic models image quality",
            "year": 2021,
            "field": "cv",
        },
    ),
    (
        7,
        {
            "title": "reinforcement learning human feedback",
            "abstract": "rlhf language models instructions reward modeling",
            "year": 2022,
            "field": "alignment",
        },
    ),
    (
        8,
        {
            "title": "efficient attention long sequences",
            "abstract": "linear attention sparse attention patterns quadratic",
            "year": 2020,
            "field": "nlp",
        },
    ),
]

for doc_id, doc in papers:
    engine.add_document(doc_id, doc, table="papers")

print("=" * 70)
print("Advanced Fusion (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. fuse_attention: attention-weighted fusion of two text signals
# ------------------------------------------------------------------
print("\n--- 1. fuse_attention: title:'attention' + abstract:'model' ---")
sig_title = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
sig_abstract = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)
results = (
    engine.query(table="papers")
    .fuse_attention(sig_title, sig_abstract, alpha=0.6)
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] fused={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 2. fuse_attention: three signals
# ------------------------------------------------------------------
print("\n--- 2. fuse_attention: three text signals ---")
sig1 = (
    engine.query(table="papers")
    .term("transformer", "title")
    .score_bayesian_bm25("transformer", "title")
)
sig2 = (
    engine.query(table="papers")
    .term("attention", "abstract")
    .score_bayesian_bm25("attention", "abstract")
)
sig3 = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)
results = (
    engine.query(table="papers").fuse_attention(sig1, sig2, sig3, alpha=0.5).execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True)[:5]:
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] fused={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 3. fuse_learned: learned-weight fusion
# ------------------------------------------------------------------
print("\n--- 3. fuse_learned: title:'transformer' + abstract:'attention' ---")
sig_title = (
    engine.query(table="papers")
    .term("transformer", "title")
    .score_bayesian_bm25("transformer", "title")
)
sig_abstract = (
    engine.query(table="papers")
    .term("attention", "abstract")
    .score_bayesian_bm25("attention", "abstract")
)
results = (
    engine.query(table="papers")
    .fuse_learned(sig_title, sig_abstract, alpha=0.5)
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] fused={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 4. multi_stage: two-stage pipeline (broad recall -> precise)
# ------------------------------------------------------------------
print("\n--- 4. multi_stage: 2-stage (top 5 -> top 3) ---")
stage1 = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
stage2 = (
    engine.query(table="papers")
    .term("attention", "abstract")
    .score_bayesian_bm25("attention mechanisms", "abstract")
)
results = engine.query(table="papers").multi_stage([(stage1, 5), (stage2, 3)]).execute()
print(f"  {len(results)} documents survived the pipeline")
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 5. multi_stage: three-stage cascade
# ------------------------------------------------------------------
print("\n--- 5. multi_stage: 3-stage cascade (6 -> 4 -> 2) ---")
s1 = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
s2 = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)
s3 = (
    engine.query(table="papers")
    .term("transformer", "title")
    .score_bayesian_bm25("transformer attention", "title")
)
results = (
    engine.query(table="papers").multi_stage([(s1, 6), (s2, 4), (s3, 2)]).execute()
)
print(f"  {len(results)} documents after 3-stage cascade")
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 6. multi_stage with threshold cutoff
# ------------------------------------------------------------------
print("\n--- 6. multi_stage: threshold-based cutoff ---")
s1 = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
s2 = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)
results = engine.query(table="papers").multi_stage([(s1, 0.5), (s2, 0.5)]).execute()
print(f"  {len(results)} documents above 0.5 threshold at each stage")
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="papers")
    print(f"  [{entry.doc_id}] score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 7. Comparison: different fusion strategies
# ------------------------------------------------------------------
print("\n--- 7. Comparison: attention vs learned vs log-odds ---")
sig_a = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
sig_b = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)

strategies = {
    "fuse_attention": engine.query(table="papers").fuse_attention(sig_a, sig_b),
    "fuse_learned": engine.query(table="papers").fuse_learned(sig_a, sig_b),
    "fuse_log_odds": engine.query(table="papers").fuse_log_odds(sig_a, sig_b),
}

for name, fused_query in strategies.items():
    results = fused_query.execute()
    top = sorted(results, key=lambda e: e.payload.score, reverse=True)[:3]
    print(f"\n  {name}:")
    for entry in top:
        doc = engine.get_document(entry.doc_id, table="papers")
        print(f"    score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 8. EXPLAIN: attention fusion plan
# ------------------------------------------------------------------
print("\n--- 8. EXPLAIN: attention fusion plan ---")
sig_a = (
    engine.query(table="papers")
    .term("attention", "title")
    .score_bayesian_bm25("attention", "title")
)
sig_b = (
    engine.query(table="papers")
    .term("model", "abstract")
    .score_bayesian_bm25("model", "abstract")
)
plan = engine.query(table="papers").fuse_attention(sig_a, sig_b).explain()
print(f"  {plan}")


print("\n" + "=" * 70)
print("All advanced fusion examples completed successfully.")
print("=" * 70)
