#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Advanced scoring and retrieval SQL examples.

Demonstrates:
  - sparse_threshold(signal, threshold) -- ReLU thresholding
  - multi_field_match(field1, field2, ..., query) -- multi-field BM25
  - multi_field_match with per-field weights
  - fuse_attention(sig1, sig2, ...) -- attention-weighted fusion
  - fuse_learned(sig1, sig2, ...) -- learned-weight fusion
  - staged_retrieval(sig1, k1, sig2, k2, ...) -- multi-stage pipeline
  - EXPLAIN plans for multi_field_match and staged_retrieval
"""

from __future__ import annotations

from uqa.engine import Engine

# ======================================================================
# Data setup: academic papers with title, abstract, year, authority
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        year INTEGER,
        authority TEXT DEFAULT 'medium'
    )
""")

papers = [
    ("attention is all you need", "transformer model self attention mechanisms", 2017, "high"),
    ("bert pre-training deep bidirectional", "masked language modeling pre-training transformers", 2019, "high"),
    ("graph attention networks", "attention mechanisms graph structured data", 2018, "medium"),
    ("vision transformer image recognition", "image patches standard transformer encoder", 2021, "medium"),
    ("scaling language models methods", "scaling laws language model performance compute", 2020, "low"),
    ("diffusion models beat gans", "denoising diffusion probabilistic models image quality", 2021, "medium"),
    ("reinforcement learning human feedback", "rlhf language models instructions reward modeling", 2022, "high"),
    ("efficient attention long sequences", "linear attention sparse attention patterns quadratic", 2020, "low"),
]
for title, abstract, year, auth in papers:
    engine.sql(
        f"INSERT INTO papers (title, abstract, year, authority) "
        f"VALUES ('{title}', '{abstract}', {year}, '{auth}')"
    )


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
print("Advanced Scoring and Retrieval (SQL)")
print("=" * 70)


# ==================================================================
# 1. sparse_threshold: filter low-confidence results
# ==================================================================
show(
    "1. sparse_threshold: bayesian_match filtered at 0.5",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE sparse_threshold(
        bayesian_match(title, 'attention'),
        0.5
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 2. multi_field_match: search across title + abstract
# ==================================================================
show(
    "2. multi_field_match: title + abstract for 'transformer'",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE multi_field_match(title, abstract, 'transformer')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 3. multi_field_match with weights: title weighted higher
# ==================================================================
show(
    "3. multi_field_match with weights (title=2.0, abstract=0.5)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE multi_field_match(title, abstract, 'attention', 2.0, 0.5)
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 4. fuse_attention: attention-weighted fusion of two text signals
# ==================================================================
show(
    "4. fuse_attention: title:'attention' + abstract:'model'",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_attention(
        bayesian_match(title, 'attention'),
        bayesian_match(abstract, 'model')
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 5. fuse_learned: learned-weight fusion
# ==================================================================
show(
    "5. fuse_learned: title:'transformer' + abstract:'attention'",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_learned(
        bayesian_match(title, 'transformer'),
        bayesian_match(abstract, 'attention')
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 6. staged_retrieval: two-stage pipeline (broad -> precise)
# ==================================================================
show(
    "6. staged_retrieval: broad recall (top 5) -> precise re-ranking (top 3)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE staged_retrieval(
        bayesian_match(title, 'attention transformer'),
        5,
        bayesian_match(abstract, 'attention mechanisms'),
        3
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 7. staged_retrieval: three-stage cascade
# ==================================================================
show(
    "7. staged_retrieval: 3-stage cascade (6 -> 4 -> 2)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE staged_retrieval(
        bayesian_match(title, 'attention'),
        6,
        bayesian_match(abstract, 'model'),
        4,
        bayesian_match(abstract, 'transformer attention'),
        2
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 8. Comparison: multi_field_match vs separate bayesian_match
# ==================================================================
print("\n--- 8. Comparison: multi_field_match vs separate bayesian_match ---")

multi_result = engine.sql("""
    SELECT title, _score FROM papers
    WHERE multi_field_match(title, abstract, 'attention')
    ORDER BY _score DESC LIMIT 3
""")
print("\n  multi_field_match(title, abstract, 'attention'):")
for row in multi_result.rows:
    print(f"    score={row['_score']:.4f}  {row['title']}")

single_result = engine.sql("""
    SELECT title, _score FROM papers
    WHERE bayesian_match(title, 'attention')
    ORDER BY _score DESC LIMIT 3
""")
print("\n  bayesian_match(title, 'attention') [title only]:")
for row in single_result.rows:
    print(f"    score={row['_score']:.4f}  {row['title']}")


# ==================================================================
# 9. EXPLAIN for multi_field_match
# ==================================================================
result = engine.sql("""
    EXPLAIN SELECT * FROM papers
    WHERE multi_field_match(title, abstract, 'attention')
""")
print("\n--- 9. EXPLAIN multi_field_match plan ---")
for row in result.rows:
    print(f"  {row['plan']}")


# ==================================================================
# 10. EXPLAIN for staged_retrieval
# ==================================================================
result = engine.sql("""
    EXPLAIN SELECT * FROM papers
    WHERE staged_retrieval(
        bayesian_match(title, 'attention'),
        5,
        bayesian_match(abstract, 'model'),
        3
    )
""")
print("\n--- 10. EXPLAIN staged_retrieval plan ---")
for row in result.rows:
    print(f"  {row['plan']}")


print("\n" + "=" * 70)
print("All advanced scoring SQL examples completed successfully.")
print("=" * 70)
