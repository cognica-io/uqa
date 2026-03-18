#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Knowledge Discovery Engine: all four paradigms in unified queries.

UQA's core thesis is that posting lists serve as the universal abstraction
across relational SQL, full-text search, vector similarity, and graph
queries. This example demonstrates progressive unification -- from
single-paradigm queries to a single SQL statement that fuses all four.

Demonstrates:
  - SQL: relational filtering, aggregation, GROUP BY
  - FTS: text_match (BM25) and bayesian_match (calibrated P(relevant))
  - Vector: knn_match (cosine similarity nearest neighbors)
  - Graph: pagerank, traverse, rpq (citation network analysis)
  - Cypher: complex graph pattern matching via FROM cypher()
  - Fusion: fuse_log_odds combining 3 scoring signals + relational filter
  - EXPLAIN: query plans showing unified posting list operations
"""

import numpy as np

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# ======================================================================
# Data setup: 15 landmark ML papers with text, vectors, and citations
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        year INTEGER NOT NULL,
        venue TEXT,
        field TEXT,
        citations INTEGER DEFAULT 0,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

# (title, abstract, year, venue, field, citations)
paper_data = [
    (
        "attention is all you need",
        "self attention mechanisms replacing recurrence and convolutions",
        2017,
        "NeurIPS",
        "nlp",
        95000,
    ),
    (
        "bert pre-training deep bidirectional transformers",
        "masked language modeling and next sentence prediction",
        2019,
        "NAACL",
        "nlp",
        80000,
    ),
    (
        "deep residual learning for image recognition",
        "residual connections enabling very deep convolutional networks",
        2016,
        "CVPR",
        "cv",
        180000,
    ),
    (
        "generative adversarial networks",
        "adversarial training with generator and discriminator",
        2014,
        "NeurIPS",
        "generative",
        60000,
    ),
    (
        "graph attention networks",
        "attention mechanisms for graph neural networks",
        2018,
        "ICLR",
        "graph",
        15000,
    ),
    (
        "language models are few-shot learners",
        "scaling language models for in-context learning",
        2020,
        "NeurIPS",
        "nlp",
        35000,
    ),
    (
        "vision transformer image recognition at scale",
        "pure transformer applied to sequences of image patches",
        2021,
        "ICLR",
        "cv",
        30000,
    ),
    (
        "contrastive language image pre-training",
        "visual representations from natural language supervision",
        2021,
        "ICML",
        "multimodal",
        20000,
    ),
    (
        "denoising diffusion probabilistic models",
        "progressive denoising for high quality image generation",
        2020,
        "NeurIPS",
        "generative",
        18000,
    ),
    (
        "diffusion models beat gans on image synthesis",
        "classifier guidance and improved sampling quality",
        2021,
        "NeurIPS",
        "generative",
        12000,
    ),
    (
        "training language models to follow instructions",
        "reinforcement learning from human feedback alignment",
        2022,
        "NeurIPS",
        "alignment",
        8000,
    ),
    (
        "dense passage retrieval for question answering",
        "dual-encoder dense vector representations for retrieval",
        2020,
        "EMNLP",
        "ir",
        5000,
    ),
    (
        "flash attention fast memory-efficient attention",
        "io-aware exact attention algorithm with tiling and fusion",
        2022,
        "NeurIPS",
        "architecture",
        4000,
    ),
    (
        "neural machine translation by learning to align",
        "soft attention mechanism for source target alignment",
        2015,
        "ICLR",
        "nlp",
        35000,
    ),
    (
        "llama open and efficient foundation language models",
        "open foundation models trained on public data at scale",
        2023,
        "arXiv",
        "nlp",
        10000,
    ),
]

# Field-aligned embedding centers for meaningful vector search
field_centers = {
    "nlp": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0]),
    "cv": np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "graph": np.array([0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "generative": np.array([0.0, 0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]),
    "ir": np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0]),
    "multimodal": np.array([0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "architecture": np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "alignment": np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]),
}

for title, abstract, year, venue, field, cit in paper_data:
    center = field_centers[field].astype(np.float32)
    vec = center + rng.randn(8).astype(np.float32) * 0.1
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, abstract, year, venue, field, citations, embedding) "
        f"VALUES ('{title}', '{abstract}', {year}, '{venue}', '{field}', {cit}, {arr})"
    )

# -- Per-table citation graph (for pagerank, traverse_match, rpq) --
for i in range(1, 16):
    engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'paper', 'papers')")

# Citation edges: citing_paper -> cited_paper
# This direction gives correct PageRank (most-cited papers get highest score)
citation_list = [
    (1, 1, 14),  # Transformer -> Bahdanau attention
    (2, 2, 1),  # BERT -> Transformer
    (3, 5, 1),  # GAT -> Transformer
    (4, 6, 1),  # GPT-3 -> Transformer
    (5, 6, 2),  # GPT-3 -> BERT
    (6, 7, 1),  # ViT -> Transformer
    (7, 7, 3),  # ViT -> ResNet
    (8, 8, 1),  # CLIP -> Transformer
    (9, 8, 7),  # CLIP -> ViT
    (10, 9, 4),  # DDPM -> GAN
    (11, 10, 9),  # Diff>GAN -> DDPM
    (12, 10, 4),  # Diff>GAN -> GAN
    (13, 11, 6),  # InstructGPT -> GPT-3
    (14, 11, 2),  # InstructGPT -> BERT
    (15, 12, 2),  # DPR -> BERT
    (16, 13, 1),  # FlashAttn -> Transformer
    (17, 15, 1),  # LLaMA -> Transformer
    (18, 15, 6),  # LLaMA -> GPT-3
    (19, 15, 13),  # LLaMA -> FlashAttn
]
for eid, src, dst in citation_list:
    engine.sql(
        f"SELECT * FROM graph_add_edge("
        f"{eid}, {src}, {dst}, 'cites', 'papers', 'weight=1.0')"
    )

# -- Named graph "citations" for Cypher queries --
engine.create_graph("citations")
gs = engine.graph_store
for i, (title, _, year, _, field, _) in enumerate(paper_data, 1):
    gs.add_vertex(
        Vertex(i, "Paper", {"vid": i, "title": title, "year": year, "field": field}),
        graph="citations",
    )
for eid, src, dst in citation_list:
    gs.add_edge(Edge(eid, src, dst, "cites"), graph="citations")

# Query vector pointing toward NLP region of embedding space
nlp_query = field_centers["nlp"].astype(np.float32)
nlp_query = nlp_query + rng.randn(8).astype(np.float32) * 0.05
nlp_query = (nlp_query / np.linalg.norm(nlp_query)).astype(np.float32)


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<30}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<30.4f}")
            else:
                vals.append(str(v)[:30].ljust(30))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Knowledge Discovery Engine -- Four Paradigms, One Query")
print("=" * 70)


# ==================================================================
# 1. SQL: Relational Queries
# ==================================================================
print("\n" + "=" * 50)
print("Paradigm 1: SQL (Relational)")
print("=" * 50)

show(
    "1a. Papers per field with average citations",
    engine.sql("""
    SELECT field, COUNT(*) AS papers, ROUND(AVG(citations), 0) AS avg_cit
    FROM papers
    GROUP BY field
    ORDER BY avg_cit DESC
"""),
)

show(
    "1b. Top 5 most cited papers",
    engine.sql("""
    SELECT title, year, venue, citations
    FROM papers
    ORDER BY citations DESC
    LIMIT 5
"""),
)


# ==================================================================
# 2. FTS: Full-Text Search
# ==================================================================
print("\n" + "=" * 50)
print("Paradigm 2: Full-Text Search")
print("=" * 50)

show(
    "2a. text_match: 'attention transformer' (raw BM25 scores)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE text_match(title, 'attention transformer')
    ORDER BY _score DESC
"""),
)

show(
    "2b. bayesian_match: 'attention' (calibrated probabilities)",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE bayesian_match(title, 'attention')
    ORDER BY _score DESC
"""),
)

show(
    "2c. multi_field_match: 'attention' across title + abstract",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE multi_field_match(title, abstract, 'attention')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 3. Vector: Semantic Similarity
# ==================================================================
print("\n" + "=" * 50)
print("Paradigm 3: Vector Search")
print("=" * 50)

show(
    "3. knn_match: 5 nearest neighbors to NLP query vector",
    engine.sql(
        """
    SELECT title, field, _score FROM papers
    WHERE knn_match(embedding, $1, 5)
    ORDER BY _score DESC
""",
        params=[nlp_query],
    ),
)


# ==================================================================
# 4. Graph: Citation Network Analysis
# ==================================================================
print("\n" + "=" * 50)
print("Paradigm 4: Graph Queries")
print("=" * 50)

show(
    "4a. PageRank: most influential papers",
    engine.sql("""
    SELECT title, _score FROM pagerank()
    ORDER BY _score DESC LIMIT 5
"""),
)

show(
    "4b. rpq: LLaMA's transitive citation chain (cites*)",
    engine.sql("SELECT _doc_id, title FROM rpq('cites*', 15)"),
)

show(
    "4c. Bounded RPQ: exactly 2 hops from LLaMA",
    engine.sql("SELECT _doc_id, title FROM rpq('cites{2,2}', 15)"),
)


# ==================================================================
# 5. Two-Signal Fusion
# ==================================================================
print("\n" + "=" * 50)
print("Cross-Paradigm: Two-Signal Fusion")
print("=" * 50)

show(
    "5a. fuse_log_odds: text + vector",
    engine.sql(
        """
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        knn_match(embedding, $1, 10)
    )
    ORDER BY _score DESC LIMIT 5
""",
        params=[nlp_query],
    ),
)

show(
    "5b. fuse_log_odds: text + PageRank",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention transformer'),
        pagerank()
    )
    ORDER BY _score DESC LIMIT 5
"""),
)


# ==================================================================
# 6. Three-Signal Fusion
# ==================================================================
print("\n" + "=" * 50)
print("Cross-Paradigm: Three-Signal Fusion")
print("=" * 50)

show(
    "6. fuse_log_odds: text + vector + PageRank",
    engine.sql(
        """
    SELECT title, field, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        knn_match(embedding, $1, 10),
        pagerank()
    )
    ORDER BY _score DESC LIMIT 5
""",
        params=[nlp_query],
    ),
)


# ==================================================================
# 7. Four-Paradigm Unification
# ==================================================================
print("\n" + "=" * 50)
print("Four-Paradigm Unification")
print("=" * 50)

print("""
  This query combines ALL four paradigms in a single SQL statement:
    - FTS:    bayesian_match (Bayesian BM25 calibrated relevance)
    - Vector: knn_match (semantic similarity)
    - Graph:  pagerank (citation network influence)
    - SQL:    year >= 2019 (relational filter)

  Under the hood, each paradigm produces a posting list.
  fuse_log_odds combines the three scoring signals in log-odds space.
  The relational filter intersects the result with the year constraint.
  All operations compose through the same posting list algebra.
""")

show(
    "7. Text + Vector + Graph + SQL filter (year >= 2019)",
    engine.sql(
        """
    SELECT title, year, field, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        knn_match(embedding, $1, 10),
        pagerank()
    ) AND year >= 2019
    ORDER BY _score DESC LIMIT 5
""",
        params=[nlp_query],
    ),
)


# ==================================================================
# 8. Cypher: Complex Graph Patterns
# ==================================================================
print("\n" + "=" * 50)
print("Cypher Integration")
print("=" * 50)

show(
    "8a. Cypher: all direct citation pairs",
    engine.sql("""
    SELECT * FROM cypher('citations', $$
        MATCH (a)-[:cites]->(b)
        RETURN a.title AS citing, b.title AS cited
    $$) AS (citing agtype, cited agtype)
"""),
)

show(
    "8b. Cypher: two-hop citation chains (paper -> via -> root)",
    engine.sql("""
    SELECT * FROM cypher('citations', $$
        MATCH (a)-[:cites]->(b)-[:cites]->(c)
        RETURN a.title AS paper, b.title AS via, c.title AS root
    $$) AS (paper agtype, via agtype, root agtype)
"""),
)


# ==================================================================
# 9. EXPLAIN: Unified Query Plan
# ==================================================================
print("\n" + "=" * 50)
print("Query Plan: Posting List Unification")
print("=" * 50)

result = engine.sql(
    """
    EXPLAIN SELECT title, year FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        knn_match(embedding, $1, 10),
        pagerank()
    ) AND year >= 2019
""",
    params=[nlp_query],
)
print("\n--- 9. EXPLAIN: four-paradigm unified plan ---")
for row in result.rows:
    print(f"  {row['plan']}")
print()
print("  Each paradigm contributes a posting list to the operator tree.")
print("  fuse_log_odds combines them in calibrated probability space.")
print("  The relational filter intersects the result via Boolean algebra.")


print("\n" + "=" * 70)
print("All knowledge discovery examples completed successfully.")
print("=" * 70)
