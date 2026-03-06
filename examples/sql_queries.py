#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Example: SQL Interface for UQA
=================================

Demonstrates how to query the UQA engine using standard SQL syntax
powered by pglast (PostgreSQL parser).

UQA extends SQL with custom functions for cross-paradigm queries:
  - text_match(field, 'query')      full-text search with BM25 scoring
  - bayesian_match(field, 'query')  calibrated P(relevant) via Bayesian BM25
  - knn_match(k)                    k-nearest neighbor vector search
  - FROM traverse(start, label, k)  graph BFS traversal
  - FROM rpq('expr', start)         regular path query
  - FROM text_search('q', 'f', 't') table-scoped full-text search
"""

from __future__ import annotations

import numpy as np

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine


def build_database() -> Engine:
    """Build an academic paper database using SQL DDL/DML and graph API."""
    engine = Engine(vector_dimensions=32, max_elements=1000)

    # -- DDL: Create the papers table --------------------------------
    engine.sql("""
        CREATE TABLE papers (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT,
            year INTEGER NOT NULL,
            venue TEXT,
            field TEXT,
            citations INTEGER DEFAULT 0
        )
    """)

    # -- DML: Insert papers ------------------------------------------
    engine.sql("""INSERT INTO papers (title, abstract, year, venue, field, citations) VALUES
        ('attention is all you need', 'transformer architecture based on attention mechanisms', 2017, 'NeurIPS', 'nlp', 90000),
        ('bert pre-training of deep bidirectional transformers', 'language representation model using bidirectional transformers', 2019, 'NAACL', 'nlp', 75000),
        ('graph attention networks', 'neural network using attention on graph structured data', 2018, 'ICLR', 'graph', 15000),
        ('vision transformer for image recognition', 'transformer applied to image patches for classification with attention', 2021, 'ICLR', 'cv', 25000),
        ('generative pre-trained transformer for language', 'unsupervised pre-training and supervised fine-tuning of transformer', 2018, 'NeurIPS', 'nlp', 12000),
        ('scaling language models methods and insights', 'empirical scaling laws for language model performance', 2020, 'arXiv', 'nlp', 8000),
        ('deformable attention for vision transformers', 'sparse attention sampling in feature maps for vision transformer', 2022, 'CVPR', 'cv', 3000),
        ('flash attention fast and memory efficient', 'io-aware exact attention with tiling for gpu memory efficiency', 2022, 'NeurIPS', 'systems', 5000),
        ('retrieval augmented generation for knowledge nlp', 'combining retrieval and generation with attention over documents', 2020, 'NeurIPS', 'nlp', 6000),
        ('self-supervised visual feature learning', 'contrastive learning for visual representations without attention', 2020, 'CVPR', 'cv', 10000)
    """)

    # -- Graph: citation edges (programmatic API) --------------------
    papers = engine.sql("SELECT id, title, field FROM papers ORDER BY id")
    for row in papers:
        engine.add_graph_vertex(
            Vertex(row["id"], {"title": row["title"], "field": row["field"]})
        )

    citations = [
        (1, 1, 2, "cited_by"), (2, 1, 3, "cited_by"), (3, 1, 4, "cited_by"),
        (4, 1, 5, "cited_by"), (5, 1, 7, "cited_by"), (6, 1, 8, "cited_by"),
        (7, 2, 4, "cited_by"), (8, 2, 6, "cited_by"), (9, 2, 8, "cited_by"),
        (10, 2, 9, "cited_by"), (11, 3, 7, "cited_by"), (12, 5, 6, "cited_by"),
        (13, 5, 9, "cited_by"),
    ]
    for eid, src, tgt, label in citations:
        engine.add_graph_edge(Edge(eid, src, tgt, label))

    # -- Vector embeddings (programmatic API) ------------------------
    rng = np.random.RandomState(2024)
    base_attention = rng.randn(32).astype(np.float32)
    base_attention /= np.linalg.norm(base_attention)

    for row in papers:
        doc = engine._tables["papers"].document_store.get(row["id"])
        if doc and ("attention" in doc.get("title", "") or "attention" in doc.get("abstract", "")):
            noise = rng.randn(32).astype(np.float32) * 0.3
            emb = base_attention + noise
        else:
            emb = rng.randn(32).astype(np.float32)
        emb = (emb / np.linalg.norm(emb)).astype(np.float32)
        engine.vector_index.add(row["id"], emb)

    return engine


def main() -> None:
    engine = build_database()

    print("=" * 70)
    print("UQA SQL Interface -- Query Examples")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Basic relational queries
    # ------------------------------------------------------------------
    print("\n--- 1. SELECT with WHERE, ORDER BY, LIMIT ---")
    print(engine.sql(
        "SELECT title, year, venue FROM papers "
        "WHERE year >= 2020 ORDER BY year DESC LIMIT 5"
    ))

    # ------------------------------------------------------------------
    # 2. IN clause
    # ------------------------------------------------------------------
    print("\n--- 2. IN clause ---")
    print(engine.sql(
        "SELECT title, field FROM papers WHERE field IN ('nlp', 'cv')"
    ))

    # ------------------------------------------------------------------
    # 3. BETWEEN
    # ------------------------------------------------------------------
    print("\n--- 3. BETWEEN ---")
    print(engine.sql(
        "SELECT title, year FROM papers WHERE year BETWEEN 2019 AND 2021"
    ))

    # ------------------------------------------------------------------
    # 4. Boolean logic: OR + NOT
    # ------------------------------------------------------------------
    print("\n--- 4. Boolean: (field = 'nlp' OR field = 'cv') AND NOT year < 2020 ---")
    print(engine.sql(
        "SELECT title, field, year FROM papers "
        "WHERE (field = 'nlp' OR field = 'cv') AND NOT year < 2020"
    ))

    # ------------------------------------------------------------------
    # 5. Full-text search with BM25 scoring
    # ------------------------------------------------------------------
    print("\n--- 5. text_match() with BM25 scoring ---")
    print(engine.sql(
        "SELECT title, _score FROM papers "
        "WHERE text_match(title, 'attention') ORDER BY _score DESC"
    ))

    # ------------------------------------------------------------------
    # 6. Multi-term text search
    # ------------------------------------------------------------------
    print("\n--- 6. Multi-term text_match('attention transformer') ---")
    print(engine.sql(
        "SELECT title, _score FROM papers "
        "WHERE text_match(title, 'attention transformer') ORDER BY _score DESC"
    ))

    # ------------------------------------------------------------------
    # 7. Bayesian BM25 -- calibrated probability
    # ------------------------------------------------------------------
    print("\n--- 7. bayesian_match() -- P(relevant) in [0,1] ---")
    print(engine.sql(
        "SELECT title, _score AS p_relevant FROM papers "
        "WHERE bayesian_match(title, 'attention') ORDER BY p_relevant DESC"
    ))

    # ------------------------------------------------------------------
    # 8. Text search + relational filter
    # ------------------------------------------------------------------
    print("\n--- 8. text_match() AND year >= 2020 ---")
    print(engine.sql(
        "SELECT title, year, _score FROM papers "
        "WHERE text_match(title, 'attention') AND year >= 2020 "
        "ORDER BY _score DESC"
    ))

    # ------------------------------------------------------------------
    # 9. GROUP BY with aggregates
    # ------------------------------------------------------------------
    print("\n--- 9. GROUP BY field with COUNT, AVG ---")
    print(engine.sql(
        "SELECT field, COUNT(*) AS papers_count, AVG(citations) AS avg_cites "
        "FROM papers GROUP BY field ORDER BY papers_count DESC"
    ))

    # ------------------------------------------------------------------
    # 10. GROUP BY with HAVING
    # ------------------------------------------------------------------
    print("\n--- 10. GROUP BY venue HAVING COUNT(*) >= 2 ---")
    print(engine.sql(
        "SELECT venue, COUNT(*) AS cnt, AVG(year) AS avg_year "
        "FROM papers GROUP BY venue HAVING COUNT(*) >= 2 ORDER BY cnt DESC"
    ))

    # ------------------------------------------------------------------
    # 11. Aggregate without GROUP BY
    # ------------------------------------------------------------------
    print("\n--- 11. Aggregate-only query ---")
    print(engine.sql(
        "SELECT COUNT(*) AS total, AVG(citations) AS avg_cites, "
        "MIN(year) AS earliest, MAX(year) AS latest FROM papers"
    ))

    # ------------------------------------------------------------------
    # 12. Graph traversal via FROM clause
    # ------------------------------------------------------------------
    print("\n--- 12. FROM traverse() -- 1-hop citations from paper #1 ---")
    print(engine.sql(
        "SELECT _doc_id, title FROM traverse(1, 'cited_by', 1)"
    ))

    # ------------------------------------------------------------------
    # 13. 2-hop graph traversal
    # ------------------------------------------------------------------
    print("\n--- 13. FROM traverse() -- 2-hop ---")
    print(engine.sql(
        "SELECT _doc_id, title FROM traverse(1, 'cited_by', 2)"
    ))

    # ------------------------------------------------------------------
    # 14. Regular path query
    # ------------------------------------------------------------------
    print("\n--- 14. FROM rpq() -- 2-hop transitive citations ---")
    print(engine.sql(
        "SELECT _doc_id, title FROM rpq('cited_by/cited_by', 1)"
    ))

    # ------------------------------------------------------------------
    # 15. KNN vector search
    # ------------------------------------------------------------------
    print("\n--- 15. knn_match() -- 5 nearest neighbors ---")
    rng = np.random.RandomState(2024)
    query_vec = rng.randn(32).astype(np.float32)
    query_vec /= np.linalg.norm(query_vec)

    from uqa.sql.compiler import SQLCompiler
    compiler = SQLCompiler(engine)
    compiler.set_query_vector(query_vec)
    print(compiler.execute(
        "SELECT title, _score AS similarity FROM papers "
        "WHERE knn_match(5) ORDER BY similarity DESC"
    ))

    # ------------------------------------------------------------------
    # 16. text_search as FROM-clause table function
    # ------------------------------------------------------------------
    print("\n--- 16. FROM text_search() ---")
    print(engine.sql(
        "SELECT title, _score FROM text_search('attention', 'title', 'papers') "
        "ORDER BY _score DESC"
    ))

    print("\n" + "=" * 70)
    print("All SQL examples completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
