#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Integration tests for the UQA system (Phase 5 gate).

Tests cross-paradigm queries, full pipeline, optimizer correctness,
and WAND vs exhaustive equivalence.
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import (
    Edge,
    GreaterThanOrEqual,
    Vertex,
)
from uqa.engine import Engine


@pytest.fixture
def engine_with_docs() -> Engine:
    """Engine populated with sample documents, vectors, and graph data."""
    engine = Engine()
    engine.sql(
        "CREATE TABLE papers ("
        "id INTEGER PRIMARY KEY, "
        "title TEXT, "
        "abstract TEXT, "
        "year INTEGER, "
        "category TEXT, "
        "embedding VECTOR(16))"
    )
    rng = np.random.RandomState(42)

    docs = [
        {
            "title": "neural network basics",
            "abstract": "introduction to neural networks and deep learning",
            "year": 2023,
            "category": "ml",
        },
        {
            "title": "transformer architecture",
            "abstract": "attention is all you need for transformer models",
            "year": 2024,
            "category": "dl",
        },
        {
            "title": "graph neural networks",
            "abstract": "neural networks for graph structured data",
            "year": 2024,
            "category": "ml",
        },
        {
            "title": "bayesian optimization",
            "abstract": "bayesian methods for optimization problems",
            "year": 2025,
            "category": "opt",
        },
        {
            "title": "reinforcement learning",
            "abstract": "deep reinforcement learning agents",
            "year": 2025,
            "category": "rl",
        },
        {
            "title": "vector search",
            "abstract": "efficient vector similarity search methods",
            "year": 2024,
            "category": "ir",
        },
        {
            "title": "text retrieval",
            "abstract": "neural text retrieval with transformers",
            "year": 2023,
            "category": "ir",
        },
        {
            "title": "knowledge graphs",
            "abstract": "knowledge graph embedding methods",
            "year": 2024,
            "category": "kg",
        },
    ]

    for i, doc in enumerate(docs, 1):
        embedding = rng.randn(16).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        engine.add_document(i, doc, table="papers", embedding=embedding)

    vertices = [
        Vertex(1, "", {"type": "paper", "title": "neural network basics"}),
        Vertex(2, "", {"type": "paper", "title": "transformer architecture"}),
        Vertex(3, "", {"type": "paper", "title": "graph neural networks"}),
        Vertex(4, "", {"type": "paper", "title": "bayesian optimization"}),
        Vertex(5, "", {"type": "paper", "title": "reinforcement learning"}),
        Vertex(6, "", {"type": "paper", "title": "vector search"}),
        Vertex(7, "", {"type": "paper", "title": "text retrieval"}),
        Vertex(8, "", {"type": "paper", "title": "knowledge graphs"}),
    ]
    for v in vertices:
        engine.add_graph_vertex(v, table="papers")

    edges = [
        Edge(1, 2, 1, "cites"),
        Edge(2, 3, 1, "cites"),
        Edge(3, 3, 2, "cites"),
        Edge(4, 5, 1, "cites"),
        Edge(5, 7, 6, "cites"),
        Edge(6, 7, 2, "cites"),
        Edge(7, 8, 3, "cites"),
    ]
    for e in edges:
        engine.add_graph_edge(e, table="papers")

    return engine


class TestFullPipeline:
    """Test the add/index/query pipeline."""

    def test_term_search(self, engine_with_docs: Engine):
        results = engine_with_docs.query(table="papers").term("neural").execute()
        assert len(results) > 0
        doc_ids = results.doc_ids
        assert 1 in doc_ids
        assert 3 in doc_ids

    def test_term_search_with_field(self, engine_with_docs: Engine):
        results = (
            engine_with_docs.query(table="papers")
            .term("neural", field="title")
            .execute()
        )
        assert len(results) > 0

    def test_filter_query(self, engine_with_docs: Engine):
        results = (
            engine_with_docs.query(table="papers")
            .term("neural")
            .filter("year", GreaterThanOrEqual(2024))
            .execute()
        )
        for entry in results:
            doc = engine_with_docs._tables["papers"].document_store.get(entry.doc_id)
            assert doc is not None
            assert doc["year"] >= 2024

    def test_boolean_or(self, engine_with_docs: Engine):
        q1 = engine_with_docs.query(table="papers").term("neural")
        q2 = engine_with_docs.query(table="papers").term("bayesian")
        results = q1.or_(q2).execute()
        assert len(results) > 0
        ids = results.doc_ids
        assert 1 in ids or 3 in ids
        assert 4 in ids

    def test_boolean_and(self, engine_with_docs: Engine):
        q1 = engine_with_docs.query(table="papers").term("neural")
        q2 = engine_with_docs.query(table="papers").term("networks")
        results = q1.and_(q2).execute()
        ids = results.doc_ids
        for doc_id in ids:
            doc = engine_with_docs._tables["papers"].document_store.get(doc_id)
            text = " ".join(v for v in doc.values() if isinstance(v, str)).lower()
            assert "neural" in text
            assert "networks" in text


class TestScoringPipeline:
    """Test BM25 and Bayesian BM25 scoring through the API."""

    def test_bm25_scoring(self, engine_with_docs: Engine):
        results = (
            engine_with_docs.query(table="papers")
            .term("neural")
            .score_bm25("neural")
            .execute()
        )
        assert len(results) > 0
        scores = [e.payload.score for e in results]
        assert all(s >= 0 for s in scores)

    def test_bayesian_bm25_scoring(self, engine_with_docs: Engine):
        results = (
            engine_with_docs.query(table="papers")
            .term("neural")
            .score_bayesian_bm25("neural")
            .execute()
        )
        assert len(results) > 0
        scores = [e.payload.score for e in results]
        assert all(0 <= s <= 1 for s in scores)


class TestVectorSearch:
    """Test vector search through the API."""

    def test_knn_search(self, engine_with_docs: Engine):
        rng = np.random.RandomState(99)
        query_vec = rng.randn(16).astype(np.float32)
        query_vec = query_vec / np.linalg.norm(query_vec)

        results = engine_with_docs.query(table="papers").knn(query_vec, k=3).execute()
        assert len(results) <= 3
        assert len(results) > 0


class TestFusion:
    """Test log-odds and probabilistic fusion."""

    def test_log_odds_fusion(self, engine_with_docs: Engine):
        rng = np.random.RandomState(99)
        query_vec = rng.randn(16).astype(np.float32)
        query_vec = query_vec / np.linalg.norm(query_vec)

        text_q = (
            engine_with_docs.query(table="papers")
            .term("neural")
            .score_bayesian_bm25("neural")
        )
        vec_q = engine_with_docs.query(table="papers").knn(query_vec, k=5)

        results = (
            engine_with_docs.query(table="papers")
            .fuse_log_odds(text_q, vec_q, alpha=0.5)
            .execute()
        )
        assert len(results) > 0
        scores = [e.payload.score for e in results]
        assert all(0 <= s <= 1 for s in scores)


class TestCoverageBasedDefault:
    """Test coverage-based default probability in fusion operators."""

    def test_coverage_based_default_formula(self):
        from uqa.operators.hybrid import _coverage_based_default

        # Zero coverage: fully neutral
        assert _coverage_based_default(0, 10) == pytest.approx(0.5)
        assert _coverage_based_default(0, 0) == pytest.approx(0.5)

        # Full coverage: floor value
        assert _coverage_based_default(10, 10) == pytest.approx(0.01)

        # 50% coverage: midpoint
        assert _coverage_based_default(5, 10) == pytest.approx(0.255)

        # 10% coverage: mostly neutral
        assert _coverage_based_default(1, 10) == pytest.approx(0.451)

        # Monotonically decreasing as coverage increases
        values = [_coverage_based_default(i, 10) for i in range(11)]
        for i in range(len(values) - 1):
            assert values[i] > values[i + 1]

    def test_log_odds_zero_coverage_preserves_knn_ranking(self):
        """When BM25 has zero coverage, KNN ranking should be preserved."""
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry
        from uqa.operators.base import ExecutionContext, Operator
        from uqa.operators.hybrid import LogOddsFusionOperator

        class FixedOperator(Operator):
            def __init__(self, entries):
                self._entries = entries

            def execute(self, context):
                return PostingList.from_sorted(self._entries)

            def cost_estimate(self, stats):
                return 1.0

        # BM25 returns nothing
        bm25 = FixedOperator([])

        # KNN returns 5 docs with decreasing scores
        knn = FixedOperator([
            PostingEntry(0, Payload(score=0.9)),
            PostingEntry(1, Payload(score=0.8)),
            PostingEntry(2, Payload(score=0.7)),
            PostingEntry(3, Payload(score=0.6)),
            PostingEntry(4, Payload(score=0.5)),
        ])

        ctx = ExecutionContext(document_store=None, inverted_index=None)
        fusion = LogOddsFusionOperator([bm25, knn])
        result = fusion.execute(ctx)
        scores = {e.doc_id: e.payload.score for e in result}

        # Ranking must be preserved
        assert scores[0] > scores[1] > scores[2] > scores[3] > scores[4]

        # Scores should NOT be crushed below 0.5 for highly relevant docs
        assert scores[0] > 0.5, (
            f"Doc 0 (KNN=0.9) fused to {scores[0]:.4f}, "
            f"expected > 0.5 with zero BM25 coverage"
        )

    def test_log_odds_full_coverage_penalizes_missing(self):
        """When a signal has full coverage, missing docs get strong penalty."""
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry
        from uqa.operators.base import ExecutionContext, Operator
        from uqa.operators.hybrid import LogOddsFusionOperator

        class FixedOperator(Operator):
            def __init__(self, entries):
                self._entries = entries

            def execute(self, context):
                return PostingList.from_sorted(self._entries)

            def cost_estimate(self, stats):
                return 1.0

        # Signal A covers all 3 docs
        sig_a = FixedOperator([
            PostingEntry(0, Payload(score=0.8)),
            PostingEntry(1, Payload(score=0.7)),
            PostingEntry(2, Payload(score=0.6)),
        ])

        # Signal B covers only doc 0
        sig_b = FixedOperator([
            PostingEntry(0, Payload(score=0.85)),
        ])

        ctx = ExecutionContext(document_store=None, inverted_index=None)
        fusion = LogOddsFusionOperator([sig_a, sig_b])
        result = fusion.execute(ctx)
        scores = {e.doc_id: e.payload.score for e in result}

        # Doc 0 (both signals match) should score highest
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_log_odds_partial_coverage_moderate_penalty(self):
        """Partial coverage gives a gentler penalty than full coverage."""
        from bayesian_bm25 import log_odds_conjunction
        from uqa.operators.hybrid import _coverage_based_default

        # Same KNN score for a missing doc
        knn_score = 0.8

        # Full coverage: 10/10 -> default near 0.01
        default_full = _coverage_based_default(10, 10)
        fused_full = float(log_odds_conjunction(
            np.array([default_full, knn_score]), alpha=0.5
        ))

        # Partial: 5/10 -> default near 0.255
        default_partial = _coverage_based_default(5, 10)
        fused_partial = float(log_odds_conjunction(
            np.array([default_partial, knn_score]), alpha=0.5
        ))

        # Zero coverage: 0/10 -> default = 0.5
        default_zero = _coverage_based_default(0, 10)
        fused_zero = float(log_odds_conjunction(
            np.array([default_zero, knn_score]), alpha=0.5
        ))

        # Zero coverage should preserve score most, full coverage penalizes most
        assert fused_zero > fused_partial > fused_full

    def test_prob_bool_coverage_default(self):
        """ProbBoolFusionOperator also uses coverage-based defaults."""
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry
        from uqa.operators.base import ExecutionContext, Operator
        from uqa.operators.hybrid import ProbBoolFusionOperator

        class FixedOperator(Operator):
            def __init__(self, entries):
                self._entries = entries

            def execute(self, context):
                return PostingList.from_sorted(self._entries)

            def cost_estimate(self, stats):
                return 1.0

        # Signal A: zero coverage
        sig_a = FixedOperator([])

        # Signal B: has results
        sig_b = FixedOperator([
            PostingEntry(0, Payload(score=0.8)),
            PostingEntry(1, Payload(score=0.6)),
        ])

        ctx = ExecutionContext(document_store=None, inverted_index=None)
        fusion = ProbBoolFusionOperator([sig_a, sig_b], mode="and")
        result = fusion.execute(ctx)
        scores = {e.doc_id: e.payload.score for e in result}

        # With zero-coverage signal A, prob_and(0.5, 0.8) > prob_and(0.01, 0.8)
        # (0.5 * 0.8 = 0.4 vs 0.01 * 0.8 = 0.008)
        assert scores[0] > 0.1, (
            f"prob_and with zero-coverage signal gave {scores[0]:.4f}, "
            f"expected > 0.1"
        )


class TestGraphQueries:
    """Test graph operations through the API."""

    def test_traverse(self, engine_with_docs: Engine):
        results = (
            engine_with_docs.query(table="papers")
            .traverse(start=1, label="cites", max_hops=2)
            .execute()
        )
        assert len(results) > 0

    def test_traverse_multi_hop(self, engine_with_docs: Engine):
        results_1hop = (
            engine_with_docs.query(table="papers")
            .traverse(start=1, label="cites", max_hops=1)
            .execute()
        )
        results_2hop = (
            engine_with_docs.query(table="papers")
            .traverse(start=1, label="cites", max_hops=2)
            .execute()
        )
        assert len(results_2hop) >= len(results_1hop)


class TestAggregation:
    """Test aggregation through the API."""

    def test_count(self, engine_with_docs: Engine):
        result = (
            engine_with_docs.query(table="papers")
            .term("neural")
            .aggregate("title", "count")
        )
        assert result.value is not None
        assert result.value > 0

    def test_facet(self, engine_with_docs: Engine):
        result = engine_with_docs.query(table="papers").term("neural").facet("category")
        assert isinstance(result.counts, dict)


class TestExplain:
    """Test query plan explanation."""

    def test_explain_term(self, engine_with_docs: Engine):
        plan = engine_with_docs.query(table="papers").term("neural").explain()
        assert "TermOp" in plan

    def test_explain_intersection(self, engine_with_docs: Engine):
        q1 = engine_with_docs.query(table="papers").term("neural")
        q2 = engine_with_docs.query(table="papers").term("networks")
        plan = q1.and_(q2).explain()
        assert "Intersect" in plan


class TestOptimizerCorrectness:
    """Verify optimizer produces same results as unoptimized execution."""

    def test_intersect_reordering_same_results(self, engine_with_docs: Engine):
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.optimizer import QueryOptimizer

        ctx = engine_with_docs._context_for_table("papers")

        op = IntersectOperator(
            [
                TermOperator("neural"),
                TermOperator("networks"),
            ]
        )

        unoptimized = PlanExecutor(ctx).execute(op)

        optimizer = QueryOptimizer(ctx.inverted_index.stats)
        optimized_op = optimizer.optimize(op)
        optimized = PlanExecutor(ctx).execute(optimized_op)

        assert unoptimized.doc_ids == optimized.doc_ids
