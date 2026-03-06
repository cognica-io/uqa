#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Example 1: Academic Paper Search Engine
==========================================

A research paper search engine that combines:
- Full-text search (BM25 / Bayesian BM25)
- Semantic vector search (embedding similarity)
- Citation graph traversal
- Multi-signal fusion via log-odds conjunction

Scenario: A researcher is looking for papers about "attention mechanisms"
that are semantically similar to a known paper, and are well-cited
within a specific subfield.
"""

from __future__ import annotations

import numpy as np

from uqa.engine import Engine
from uqa.core.types import (
    Edge,
    Equals,
    GreaterThanOrEqual,
    InSet,
    Vertex,
)
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern


def build_paper_database() -> Engine:
    """Build an academic paper database with documents, embeddings, and citation graph."""
    engine = Engine(vector_dimensions=32, max_elements=1000)
    rng = np.random.RandomState(2024)

    papers = [
        {
            "doc_id": 1,
            "title": "attention is all you need",
            "abstract": "we propose a new simple network architecture the transformer "
                        "based entirely on attention mechanisms dispensing with recurrence "
                        "and convolutions entirely",
            "year": 2017,
            "venue": "NeurIPS",
            "field": "nlp",
            "citations": 90000,
        },
        {
            "doc_id": 2,
            "title": "bert pre-training of deep bidirectional transformers",
            "abstract": "we introduce a new language representation model called bert "
                        "which stands for bidirectional encoder representations from "
                        "transformers bert is designed to pre-train deep bidirectional "
                        "representations from unlabeled text",
            "year": 2019,
            "venue": "NAACL",
            "field": "nlp",
            "citations": 75000,
        },
        {
            "doc_id": 3,
            "title": "an image is worth 16x16 words transformers for image recognition",
            "abstract": "we show that a pure transformer applied directly to sequences "
                        "of image patches can perform very well on image classification "
                        "tasks with attention mechanisms for vision",
            "year": 2021,
            "venue": "ICLR",
            "field": "cv",
            "citations": 25000,
        },
        {
            "doc_id": 4,
            "title": "graph attention networks",
            "abstract": "we present graph attention networks a novel neural network "
                        "architecture that operates on graph structured data leveraging "
                        "masked self attention layers to address shortcomings of prior "
                        "methods based on graph convolutions",
            "year": 2018,
            "venue": "ICLR",
            "field": "graph",
            "citations": 15000,
        },
        {
            "doc_id": 5,
            "title": "generative pre-trained transformer for language understanding",
            "abstract": "we explore a semi-supervised approach using a combination of "
                        "unsupervised pre-training and supervised fine-tuning on a "
                        "transformer language model to improve language understanding",
            "year": 2018,
            "venue": "NeurIPS",
            "field": "nlp",
            "citations": 12000,
        },
        {
            "doc_id": 6,
            "title": "scaling language models methods analysis and insights",
            "abstract": "we study empirical scaling laws for language model performance "
                        "as a function of model size dataset size and the amount of "
                        "compute used for training",
            "year": 2020,
            "venue": "arXiv",
            "field": "nlp",
            "citations": 8000,
        },
        {
            "doc_id": 7,
            "title": "deformable attention for vision transformers",
            "abstract": "we propose deformable attention that learns to attend to "
                        "a sparse set of key sampling points in the feature map "
                        "for efficient vision transformer architectures",
            "year": 2022,
            "venue": "CVPR",
            "field": "cv",
            "citations": 3000,
        },
        {
            "doc_id": 8,
            "title": "flash attention fast and memory efficient exact attention",
            "abstract": "we propose flash attention an io-aware exact attention "
                        "algorithm that uses tiling to reduce memory reads and writes "
                        "between gpu high bandwidth memory and on-chip sram",
            "year": 2022,
            "venue": "NeurIPS",
            "field": "systems",
            "citations": 5000,
        },
        {
            "doc_id": 9,
            "title": "retrieval augmented generation for knowledge intensive nlp",
            "abstract": "we explore retrieval augmented generation models combining "
                        "pre-trained parametric and non-parametric memory for language "
                        "generation with attention over retrieved documents",
            "year": 2020,
            "venue": "NeurIPS",
            "field": "nlp",
            "citations": 6000,
        },
        {
            "doc_id": 10,
            "title": "self-supervised learning of visual features by contrasting",
            "abstract": "we present a contrastive learning framework for self-supervised "
                        "visual representation learning without attention mechanisms "
                        "using a momentum contrast approach",
            "year": 2020,
            "venue": "CVPR",
            "field": "cv",
            "citations": 10000,
        },
    ]

    # Generate mock embeddings -- in practice these come from a sentence encoder.
    # Papers about attention/transformers get similar embeddings.
    base_attention = rng.randn(32).astype(np.float32)
    base_attention /= np.linalg.norm(base_attention)

    for paper in papers:
        doc_id = paper.pop("doc_id")
        # Papers mentioning "attention" get embeddings closer to base_attention
        if "attention" in paper["title"] or "attention" in paper["abstract"]:
            noise = rng.randn(32).astype(np.float32) * 0.3
            embedding = base_attention + noise
        else:
            embedding = rng.randn(32).astype(np.float32)
        embedding = (embedding / np.linalg.norm(embedding)).astype(np.float32)
        engine.add_document(doc_id, paper, embedding)

    # Build citation graph
    # Vertices = papers
    for i in range(1, 11):
        vertex_data = engine.document_store.get(i)
        engine.add_graph_vertex(
            Vertex(i, {"title": vertex_data["title"], "field": vertex_data["field"]})
        )

    # Citation edges: (edge_id, source=cited_by, target=cites_paper, label)
    # Direction: cited paper -> citing paper (outgoing from the cited)
    # This way traverse(start=1) finds papers that cite paper #1.
    citations = [
        # Attention Is All You Need is cited by BERT, ViT, GAT, GPT, Deformable, Flash
        (1,  1, 2,  "cited_by"),
        (2,  1, 3,  "cited_by"),
        (3,  1, 4,  "cited_by"),
        (4,  1, 5,  "cited_by"),
        (5,  1, 7,  "cited_by"),
        (6,  1, 8,  "cited_by"),
        # BERT is cited by ViT, Scaling Laws, Flash Attention, RAG
        (7,  2, 3,  "cited_by"),
        (8,  2, 6,  "cited_by"),
        (9,  2, 8,  "cited_by"),
        (10, 2, 9,  "cited_by"),
        # ViT is cited by Deformable Attention
        (11, 3, 7,  "cited_by"),
        # GPT is cited by Scaling Laws, RAG
        (12, 5, 6,  "cited_by"),
        (13, 5, 9,  "cited_by"),
    ]

    for edge_id, source_id, target_id, label in citations:
        engine.add_graph_edge(Edge(edge_id, source_id, target_id, label))

    return engine


def main() -> None:
    engine = build_paper_database()

    print("=" * 70)
    print("UQA Academic Paper Search -- Realistic Examples")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Query 1: Basic keyword search with BM25 scoring
    # ------------------------------------------------------------------
    print("\n--- Query 1: Keyword search for 'attention' (BM25 scored) ---")
    results = (
        engine.query()
        .term("attention")
        .score_bm25("attention")
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']}")
        print(f"       BM25 score: {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 2: Bayesian BM25 -- calibrated probability scores
    # ------------------------------------------------------------------
    print("\n--- Query 2: 'transformer attention' (Bayesian BM25) ---")
    results = (
        engine.query()
        .term("transformer")
        .score_bayesian_bm25("transformer attention")
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']}")
        print(f"       P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 3: Semantic vector search -- find papers similar to
    # "Attention Is All You Need"
    # ------------------------------------------------------------------
    print("\n--- Query 3: KNN search (top-5 similar to paper #1) ---")
    rng = np.random.RandomState(2024)
    base_attention = rng.randn(32).astype(np.float32)
    base_attention /= np.linalg.norm(base_attention)
    # Use the same base vector as a query to find attention-related papers
    results = (
        engine.query()
        .knn(base_attention, k=5)
        .execute()
    )
    print(f"Top {len(results)} semantically similar papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']}")
        print(f"       similarity: {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 4: Hybrid search -- text AND vector with filter
    # ------------------------------------------------------------------
    print("\n--- Query 4: Hybrid search (text + vector + filter) ---")
    print("    'attention' AND similar to query vector AND year >= 2020")

    text_query = (
        engine.query()
        .term("attention")
        .score_bayesian_bm25("attention")
    )
    vector_query = engine.query().knn(base_attention, k=8)

    results = (
        engine.query()
        .fuse_log_odds(text_query, vector_query, alpha=0.5)
        .filter("year", GreaterThanOrEqual(2020))
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']})")
        print(f"       fused P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 5: Boolean query -- (attention OR transformer) AND NOT cv
    # ------------------------------------------------------------------
    print("\n--- Query 5: Boolean query ---")
    print("    ('attention' OR 'transformer') AND NOT field='cv'")

    q_attn = engine.query().term("attention")
    q_trans = engine.query().term("transformer")
    q_cv = engine.query().filter("field", Equals("cv"))

    results = q_attn.or_(q_trans).and_(q_cv.not_()).execute()
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']} (field={doc['field']})")

    # ------------------------------------------------------------------
    # Query 6: Citation graph traversal
    # ------------------------------------------------------------------
    print("\n--- Query 6: Papers citing 'Attention Is All You Need' (1-hop) ---")
    results = (
        engine.query()
        .traverse(start=1, label="cited_by", max_hops=1)
        .execute()
    )
    citing_ids = results.doc_ids - {1}  # exclude the start vertex
    print(f"Found {len(citing_ids)} citing papers:")
    for doc_id in sorted(citing_ids):
        v = engine.graph_store.get_vertex(doc_id)
        if v:
            print(f"  [{doc_id}] {v.properties.get('title', '?')}")

    # ------------------------------------------------------------------
    # Query 7: 2-hop citation graph -- papers that cite papers that cite
    # "Attention Is All You Need"
    # ------------------------------------------------------------------
    print("\n--- Query 7: 2-hop citation graph from paper #1 ---")
    results = (
        engine.query()
        .traverse(start=1, label="cited_by", max_hops=2)
        .execute()
    )
    all_ids = results.doc_ids - {1}
    print(f"Found {len(all_ids)} papers within 2 hops:")
    for doc_id in sorted(all_ids):
        v = engine.graph_store.get_vertex(doc_id)
        if v:
            print(f"  [{doc_id}] {v.properties.get('title', '?')}")

    # ------------------------------------------------------------------
    # Query 8: Cross-paradigm -- graph + text + vector fusion
    # Find papers in the citation network of paper #1 that also
    # match "attention" text search and are semantically similar.
    # ------------------------------------------------------------------
    print("\n--- Query 8: Cross-paradigm fusion (graph + text + vector) ---")
    print("    Citation graph(paper #1, 2 hops)")
    print("    AND text('attention', Bayesian BM25)")
    print("    AND vector(similar to attention embedding)")
    print("    Fused via log-odds conjunction (alpha=0.5)")

    graph_query = engine.query().traverse(start=1, label="cited_by", max_hops=2)
    text_query = (
        engine.query()
        .term("attention")
        .score_bayesian_bm25("attention")
    )
    vector_query = engine.query().knn(base_attention, k=8)

    results = (
        engine.query()
        .fuse_log_odds(graph_query, text_query, vector_query, alpha=0.5)
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        if doc:
            print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']})")
            print(f"       fused P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 9: Graph pattern matching -- find citation triangles
    # (A cites B, B cites C, A cites C)
    # ------------------------------------------------------------------
    print("\n--- Query 9: Citation triangles (A->B, B->C, A->C) ---")
    pattern = GraphPattern(
        vertex_patterns=[
            VertexPattern("a"),
            VertexPattern("b"),
            VertexPattern("c"),
        ],
        edge_patterns=[
            EdgePattern("a", "b", "cited_by"),
            EdgePattern("b", "c", "cited_by"),
            EdgePattern("a", "c", "cited_by"),
        ],
    )
    results = engine.query().match_pattern(pattern).execute()
    print(f"Found {len(results)} citation triangles:")
    for entry in results:
        assignment = entry.payload.fields
        names = {}
        for var, vid in assignment.items():
            v = engine.graph_store.get_vertex(vid)
            names[var] = v.properties["title"][:40] if v else "?"
        print(f"  Match #{entry.doc_id}: {names['a']!s} -> {names['b']!s} -> {names['c']!s}")

    # ------------------------------------------------------------------
    # Query 10: Regular path query -- transitive citations
    # ------------------------------------------------------------------
    print("\n--- Query 10: RPQ -- transitive citations (cited_by/cited_by) ---")
    print("    Find papers reachable via exactly 2 citation hops from paper #1")
    results = engine.query().rpq("cited_by/cited_by", start=1).execute()
    print(f"Found {len(results)} reachable endpoints:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        v = engine.graph_store.get_vertex(entry.doc_id)
        if v:
            print(f"  [{entry.doc_id}] {v.properties.get('title', '?')}")

    # ------------------------------------------------------------------
    # Query 11: Faceted search -- distribution by venue
    # ------------------------------------------------------------------
    print("\n--- Query 11: Faceted search for 'attention' by venue ---")
    facets = (
        engine.query()
        .term("attention")
        .facet("venue")
    )
    print(f"Venue distribution:")
    for venue, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
        print(f"  {venue}: {count} paper(s)")

    # ------------------------------------------------------------------
    # Query 12: Aggregation -- average citations for attention papers
    # ------------------------------------------------------------------
    print("\n--- Query 12: Average citations for 'attention' papers ---")
    avg_result = (
        engine.query()
        .term("attention")
        .aggregate("citations", "avg")
    )
    print(f"Average citations: {avg_result.value:.0f}")

    max_result = (
        engine.query()
        .term("attention")
        .aggregate("citations", "max")
    )
    print(f"Max citations: {max_result.value:.0f}")

    count_result = (
        engine.query()
        .term("attention")
        .aggregate("citations", "count")
    )
    print(f"Paper count: {count_result.value}")

    # ------------------------------------------------------------------
    # Query 13: Hierarchical path filter
    # ------------------------------------------------------------------
    print("\n--- Query 13: Filter by venue = 'NeurIPS' AND field = 'nlp' ---")
    results = (
        engine.query()
        .filter("venue", Equals("NeurIPS"))
        .filter("field", Equals("nlp"))
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']}, {doc['venue']})")

    # ------------------------------------------------------------------
    # Query 14: Explain query plan
    # ------------------------------------------------------------------
    print("\n--- Query 14: Query plan explanation ---")
    q1 = engine.query().term("attention", field="title")
    q2 = engine.query().term("transformer", field="abstract")
    plan = q1.and_(q2).explain()
    print(plan)

    print("\n" + "=" * 70)
    print("All examples completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
