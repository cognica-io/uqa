#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for cross-paradigm optimization: fusion signal ordering,
paradigm-aware cardinality estimation, and EXPLAIN for multi-paradigm plans."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import (
    Equals,
    GreaterThan,
    IndexStats,
    Payload,
    PostingEntry,
)
from uqa.core.posting_list import PostingList
from uqa.engine import Engine
from uqa.operators.base import ExecutionContext, Operator
from uqa.planner.cardinality import CardinalityEstimator
from uqa.planner.cost_model import CostModel
from uqa.planner.optimizer import QueryOptimizer


# ==================================================================
# Cross-paradigm cardinality estimation
# ==================================================================


class TestCrossParadigmCardinality:
    @pytest.fixture
    def stats(self):
        return IndexStats(total_docs=1000, dimensions=16)

    def test_score_operator_delegates_to_source(self, stats):
        """ScoreOperator cardinality equals its source cardinality."""
        from uqa.operators.primitive import ScoreOperator, TermOperator

        term_op = TermOperator("test", field="title")
        scorer = _DummyScorer()
        score_op = ScoreOperator(scorer, term_op, ["test"], field="title")

        est = CardinalityEstimator()
        term_card = est.estimate(term_op, stats)
        score_card = est.estimate(score_op, stats)
        assert score_card == term_card

    def test_traverse_operator_branching(self, stats):
        """Graph traversal cardinality uses branching factor heuristic."""
        from uqa.graph.operators import TraverseOperator

        op_1hop = TraverseOperator(1, "cites", max_hops=1)
        op_2hop = TraverseOperator(1, "cites", max_hops=2)

        est = CardinalityEstimator()
        card_1 = est.estimate(op_1hop, stats)
        card_2 = est.estimate(op_2hop, stats)
        # More hops -> larger estimated cardinality
        assert card_2 > card_1

    def test_pattern_match_high_cardinality(self, stats):
        """Pattern matching has high cardinality estimate (expensive)."""
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import GraphPattern

        pattern = GraphPattern(vertex_patterns=[], edge_patterns=[])
        op = PatternMatchOperator(pattern)

        est = CardinalityEstimator()
        card = est.estimate(op, stats)
        # Pattern match should be at least as expensive as linear scan
        assert card >= stats.total_docs

    def test_log_odds_fusion_union_cardinality(self, stats):
        """LogOddsFusion cardinality is union of signal cardinalities."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import TermOperator, KNNOperator

        term = TermOperator("neural", field="title")
        knn = KNNOperator(np.zeros(16, dtype=np.float32), k=10)
        fusion = LogOddsFusionOperator([term, knn])

        est = CardinalityEstimator()
        term_card = est.estimate(term, stats)
        knn_card = est.estimate(knn, stats)
        fusion_card = est.estimate(fusion, stats)
        # Union: fusion_card >= max(term_card, knn_card)
        assert fusion_card >= max(term_card, knn_card) - 0.01

    def test_prob_bool_and_cardinality(self, stats):
        """ProbBoolFusion AND has intersection-like cardinality."""
        from uqa.operators.hybrid import ProbBoolFusionOperator
        from uqa.operators.primitive import KNNOperator, VectorSimilarityOperator

        # Both operands have non-zero cardinality
        vec1 = VectorSimilarityOperator(
            np.zeros(16, dtype=np.float32), threshold=0.5
        )
        knn = KNNOperator(np.zeros(16, dtype=np.float32), k=50)
        fusion = ProbBoolFusionOperator([vec1, knn], mode="and")

        est = CardinalityEstimator()
        vec1_card = est.estimate(vec1, stats)
        knn_card = est.estimate(knn, stats)
        fusion_card = est.estimate(fusion, stats)
        # AND: fusion_card <= min(vec1_card, knn_card)
        assert fusion_card <= min(vec1_card, knn_card) + 0.01

    def test_prob_not_complement(self, stats):
        """ProbNot cardinality is N - source cardinality."""
        from uqa.operators.hybrid import ProbNotOperator
        from uqa.operators.primitive import KNNOperator

        knn = KNNOperator(np.zeros(16, dtype=np.float32), k=10)
        not_op = ProbNotOperator(knn)

        est = CardinalityEstimator()
        knn_card = est.estimate(knn, stats)
        not_card = est.estimate(not_op, stats)
        assert abs(not_card - (1000.0 - knn_card)) < 0.01

    def test_hybrid_text_vector_intersection(self):
        """HybridTextVector cardinality is intersection of text and vector."""
        from uqa.operators.hybrid import HybridTextVectorOperator

        # TermOperator(term) uses field=None -> doc_freq key is ("_default", term)
        stats = IndexStats(total_docs=1000, dimensions=16)
        stats._doc_freqs[("_default", "neural")] = 200

        op = HybridTextVectorOperator(
            "neural", np.zeros(16, dtype=np.float32), 0.5
        )
        est = CardinalityEstimator()
        card = est.estimate(op, stats)
        text_card = est.estimate(op.term_op, stats)
        vec_card = est.estimate(op.vector_op, stats)
        # Intersection: (text_card * vec_card) / N, clamped to >= 1
        assert card <= min(text_card, vec_card) + 0.01

    def test_semantic_filter_intersection(self):
        """SemanticFilter cardinality is intersection of source and vector."""
        from uqa.operators.hybrid import SemanticFilterOperator
        from uqa.operators.primitive import TermOperator

        # Use stats with known doc_freq
        stats = IndexStats(total_docs=1000, dimensions=16)
        stats._doc_freqs[("title", "neural")] = 200

        source = TermOperator("neural", field="title")
        op = SemanticFilterOperator(
            source, np.zeros(16, dtype=np.float32), 0.5
        )
        est = CardinalityEstimator()
        card = est.estimate(op, stats)
        src_card = est.estimate(source, stats)
        assert card <= src_card + 0.01


# ==================================================================
# Fusion signal reordering
# ==================================================================


class TestFusionSignalReordering:
    @pytest.fixture
    def stats(self):
        return IndexStats(total_docs=1000, dimensions=16)

    def test_log_odds_signals_reordered_by_cost(self, stats):
        """Optimizer reorders LogOddsFusion signals by ascending cost."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import KNNOperator, TermOperator

        # KNN is expensive (dimensions * log2(N)), Term is cheap (doc_freq)
        expensive = KNNOperator(np.zeros(16, dtype=np.float32), k=100)
        cheap = TermOperator("rare_term", field="title")

        # Put expensive first intentionally
        fusion = LogOddsFusionOperator([expensive, cheap])
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(fusion)

        assert isinstance(optimized, LogOddsFusionOperator)
        est = CardinalityEstimator()
        costs = [est.estimate(s, stats) for s in optimized.signals]
        # After optimization, signals should be in ascending cost order
        assert costs == sorted(costs)

    def test_prob_bool_signals_reordered(self, stats):
        """Optimizer reorders ProbBoolFusion signals by ascending cost."""
        from uqa.operators.hybrid import ProbBoolFusionOperator
        from uqa.operators.primitive import KNNOperator, TermOperator

        expensive = KNNOperator(np.zeros(16, dtype=np.float32), k=100)
        cheap = TermOperator("rare_term", field="title")

        fusion = ProbBoolFusionOperator([expensive, cheap], mode="and")
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(fusion)

        assert isinstance(optimized, ProbBoolFusionOperator)
        est = CardinalityEstimator()
        costs = [est.estimate(s, stats) for s in optimized.signals]
        assert costs == sorted(costs)

    def test_fusion_preserves_alpha(self, stats):
        """Signal reordering preserves alpha parameter."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import KNNOperator, TermOperator

        sig1 = TermOperator("a", field="title")
        sig2 = TermOperator("b", field="title")
        fusion = LogOddsFusionOperator([sig1, sig2], alpha=0.8)

        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(fusion)

        assert isinstance(optimized, LogOddsFusionOperator)
        assert optimized.alpha == 0.8

    def test_fusion_preserves_mode(self, stats):
        """Signal reordering preserves mode parameter."""
        from uqa.operators.hybrid import ProbBoolFusionOperator
        from uqa.operators.primitive import TermOperator

        sig1 = TermOperator("a", field="title")
        sig2 = TermOperator("b", field="title")
        fusion = ProbBoolFusionOperator([sig1, sig2], mode="or")

        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(fusion)

        assert isinstance(optimized, ProbBoolFusionOperator)
        assert optimized.mode == "or"

    def test_nested_fusion_in_intersect(self, stats):
        """Fusion operators inside intersections are also reordered."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import (
            FilterOperator,
            KNNOperator,
            TermOperator,
        )

        expensive = KNNOperator(np.zeros(16, dtype=np.float32), k=100)
        cheap = TermOperator("rare_term", field="title")
        fusion = LogOddsFusionOperator([expensive, cheap])
        filter_op = FilterOperator("year", GreaterThan(2020))

        # Fusion is inside an intersection with a filter
        tree = IntersectOperator([filter_op, fusion])
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(tree)

        # Find the fusion operator in the optimized tree
        def find_fusion(op):
            if isinstance(op, LogOddsFusionOperator):
                return op
            if hasattr(op, "operands"):
                for child in op.operands:
                    result = find_fusion(child)
                    if result:
                        return result
            return None

        found = find_fusion(optimized)
        assert found is not None
        est = CardinalityEstimator()
        costs = [est.estimate(s, stats) for s in found.signals]
        assert costs == sorted(costs)


# ==================================================================
# Cross-paradigm cost model
# ==================================================================


class TestCrossParadigmCostModel:
    @pytest.fixture
    def stats(self):
        return IndexStats(total_docs=1000, dimensions=16)

    def test_score_op_cost(self, stats):
        """ScoreOperator cost is source cost * 1.1."""
        from uqa.operators.primitive import ScoreOperator, TermOperator

        term = TermOperator("test", field="title")
        score = ScoreOperator(_DummyScorer(), term, ["test"], field="title")

        model = CostModel()
        term_cost = model.estimate(term, stats)
        score_cost = model.estimate(score, stats)
        assert abs(score_cost - term_cost * 1.1) < 0.01

    def test_fusion_cost_is_sum_of_signals(self, stats):
        """Fusion cost = sum of signal costs."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import KNNOperator, TermOperator

        term = TermOperator("test", field="title")
        knn = KNNOperator(np.zeros(16, dtype=np.float32), k=10)
        fusion = LogOddsFusionOperator([term, knn])

        model = CostModel()
        term_cost = model.estimate(term, stats)
        knn_cost = model.estimate(knn, stats)
        fusion_cost = model.estimate(fusion, stats)
        assert abs(fusion_cost - (term_cost + knn_cost)) < 0.01

    def test_traverse_cost_cheap(self, stats):
        """Traversal is cheaper than full scan."""
        from uqa.graph.operators import TraverseOperator

        op = TraverseOperator(1, "cites", max_hops=2)
        model = CostModel()
        cost = model.estimate(op, stats)
        assert cost < stats.total_docs

    def test_pattern_match_expensive(self, stats):
        """Pattern matching is expensive (quadratic)."""
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import GraphPattern

        pattern = GraphPattern(vertex_patterns=[], edge_patterns=[])
        op = PatternMatchOperator(pattern)
        model = CostModel()
        cost = model.estimate(op, stats)
        assert cost > stats.total_docs


# ==================================================================
# EXPLAIN for cross-paradigm operators
# ==================================================================


class TestCrossParadigmExplain:
    @pytest.fixture
    def ctx(self):
        """Minimal execution context."""
        from uqa.storage.document_store import DocumentStore
        from uqa.storage.inverted_index import InvertedIndex

        return ExecutionContext(
            document_store=DocumentStore(),
            inverted_index=InvertedIndex(),
        )

    def test_explain_score_operator(self, ctx):
        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.planner.executor import PlanExecutor

        term = TermOperator("test", field="title")
        score = ScoreOperator(_DummyScorer(), term, ["test"], field="title")

        plan = PlanExecutor(ctx).explain(score)
        assert "ScoreOp" in plan
        assert "_DummyScorer" in plan
        assert "TermOp" in plan

    def test_explain_log_odds_fusion(self, ctx):
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor

        sig1 = TermOperator("a", field="title")
        sig2 = TermOperator("b", field="title")
        fusion = LogOddsFusionOperator([sig1, sig2], alpha=0.7)

        plan = PlanExecutor(ctx).explain(fusion)
        assert "LogOddsFusion" in plan
        assert "alpha=0.7" in plan
        assert "signals=2" in plan
        assert "TermOp" in plan

    def test_explain_prob_bool_fusion(self, ctx):
        from uqa.operators.hybrid import ProbBoolFusionOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor

        sig1 = TermOperator("a", field="title")
        sig2 = TermOperator("b", field="title")
        fusion = ProbBoolFusionOperator([sig1, sig2], mode="and")

        plan = PlanExecutor(ctx).explain(fusion)
        assert "ProbBoolFusion" in plan
        assert "mode='and'" in plan
        assert "signals=2" in plan

    def test_explain_prob_not(self, ctx):
        from uqa.operators.hybrid import ProbNotOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor

        sig = TermOperator("a", field="title")
        op = ProbNotOperator(sig)

        plan = PlanExecutor(ctx).explain(op)
        assert "ProbNot" in plan
        assert "TermOp" in plan

    def test_explain_traverse(self, ctx):
        from uqa.graph.operators import TraverseOperator
        from uqa.planner.executor import PlanExecutor

        op = TraverseOperator(1, "cites", max_hops=3)
        plan = PlanExecutor(ctx).explain(op)
        assert "TraverseOp" in plan
        assert "start=1" in plan
        assert "label='cites'" in plan
        assert "hops=3" in plan

    def test_explain_pattern_match(self, ctx):
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import (
            EdgePattern,
            GraphPattern,
            VertexPattern,
        )
        from uqa.planner.executor import PlanExecutor

        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a"),
                VertexPattern("b"),
            ],
            edge_patterns=[
                EdgePattern("a", "b", label="knows"),
            ],
        )
        op = PatternMatchOperator(pattern)
        plan = PlanExecutor(ctx).explain(op)
        assert "PatternMatchOp" in plan
        assert "vertices=2" in plan
        assert "edges=1" in plan

    def test_explain_rpq(self, ctx):
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import Label
        from uqa.planner.executor import PlanExecutor

        op = RegularPathQueryOperator(Label("cites"), start_vertex=1)
        plan = PlanExecutor(ctx).explain(op)
        assert "RPQOp" in plan
        assert "start=1" in plan


# ==================================================================
# End-to-end optimizer correctness
# ==================================================================


class TestCrossParadigmOptimizerCorrectness:
    @pytest.fixture
    def engine(self):
        e = Engine(vector_dimensions=16, max_elements=100)
        e.sql(
            "CREATE TABLE papers ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT, "
            "category TEXT, "
            "embedding VECTOR(16))"
        )
        rng = np.random.RandomState(42)
        docs = [
            {"title": "neural network basics", "category": "ml"},
            {"title": "transformer models", "category": "dl"},
            {"title": "graph neural networks", "category": "ml"},
            {"title": "bayesian optimization", "category": "opt"},
        ]
        for i, doc in enumerate(docs, 1):
            emb = rng.randn(16).astype(np.float32)
            emb = emb / np.linalg.norm(emb)
            e.add_document(i, doc, table="papers", embedding=emb)
        return e

    def test_fusion_reorder_preserves_results(self, engine):
        """Fusion signal reordering produces same results."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import KNNOperator, ScoreOperator, TermOperator
        from uqa.scoring.bm25 import BM25Params, BM25Scorer
        from uqa.planner.executor import PlanExecutor

        ctx = engine._context_for_table("papers")
        stats = ctx.inverted_index.stats

        term = TermOperator("neural", field="title")
        scorer = BM25Scorer(BM25Params(), stats)
        text_signal = ScoreOperator(scorer, term, ["neural"], field="title")

        query_vec = np.random.RandomState(99).randn(16).astype(np.float32)
        query_vec = query_vec / np.linalg.norm(query_vec)
        knn_signal = KNNOperator(query_vec, k=3)

        # Unoptimized: expensive first
        fusion_orig = LogOddsFusionOperator([knn_signal, text_signal])
        result_orig = PlanExecutor(ctx).execute(fusion_orig)

        # Optimized
        optimizer = QueryOptimizer(stats)
        fusion_opt = optimizer.optimize(
            LogOddsFusionOperator([knn_signal, text_signal])
        )
        result_opt = PlanExecutor(ctx).execute(fusion_opt)

        # Same doc IDs (order may differ in posting list)
        assert set(result_orig.doc_ids) == set(result_opt.doc_ids)
        # Same scores per doc_id
        orig_scores = {e.doc_id: e.payload.score for e in result_orig}
        opt_scores = {e.doc_id: e.payload.score for e in result_opt}
        for doc_id in orig_scores:
            assert abs(orig_scores[doc_id] - opt_scores[doc_id]) < 1e-10

    def test_intersect_reorder_with_mixed_paradigms(self, engine):
        """Intersect reordering works across paradigm boundaries."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import (
            FilterOperator,
            KNNOperator,
            TermOperator,
        )
        from uqa.planner.executor import PlanExecutor

        ctx = engine._context_for_table("papers")
        stats = ctx.inverted_index.stats

        term = TermOperator("neural", field="title")
        filter_op = FilterOperator("category", Equals("ml"))

        tree = IntersectOperator([filter_op, term])
        unoptimized = PlanExecutor(ctx).execute(tree)

        optimizer = QueryOptimizer(stats)
        optimized_tree = optimizer.optimize(
            IntersectOperator([filter_op, term])
        )
        optimized = PlanExecutor(ctx).execute(optimized_tree)

        assert set(unoptimized.doc_ids) == set(optimized.doc_ids)


# ==================================================================
# SQL-level integration tests
# ==================================================================


class TestSQLCrossParadigmOptimizer:
    def test_explain_shows_fusion_plan(self):
        """EXPLAIN on a fusion query shows LogOddsFusion in the plan."""
        e = Engine(vector_dimensions=4, max_elements=10)
        e.sql(
            "CREATE TABLE docs ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT, "
            "body TEXT"
            ")"
        )
        for i in range(1, 6):
            e.sql(
                f"INSERT INTO docs (id, title, body) VALUES "
                f"({i}, 'neural network {i}', 'deep learning paper {i}')"
            )

        r = e.sql(
            "EXPLAIN SELECT title FROM docs WHERE "
            "fuse_log_odds(text_match(body, 'deep learning'), "
            "text_match(title, 'neural'))"
        )
        plan_text = " ".join(row["plan"] for row in r.rows)
        assert "LogOddsFusion" in plan_text or "ScoreOp" in plan_text

    def test_explain_shows_traverse(self):
        """EXPLAIN on a traverse query shows TraverseOp."""
        e = Engine(vector_dimensions=4, max_elements=10)
        from uqa.core.types import Edge, Vertex

        e.sql(
            "CREATE TABLE docs ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT"
            ")"
        )
        for i in range(1, 4):
            e.add_graph_vertex(Vertex(i, "", {"name": f"v{i}"}), table="docs")
        e.add_graph_edge(Edge(1, 1, 2, "knows"), table="docs")
        e.add_graph_edge(Edge(2, 2, 3, "knows"), table="docs")

        for i in range(1, 4):
            e.sql(
                f"INSERT INTO docs (id, name) VALUES ({i}, 'v{i}')"
            )

        r = e.sql(
            "EXPLAIN SELECT name FROM docs WHERE traverse_match(1, 'knows', 2)"
        )
        plan_text = " ".join(row["plan"] for row in r.rows)
        assert "TraverseOp" in plan_text


# ==================================================================
# Helpers
# ==================================================================


class _DummyScorer:
    """Minimal scorer for testing."""

    def score(self, tf: float, dl: float, df: float) -> float:
        return tf

    def combine_scores(self, scores: list[float]) -> float:
        return sum(scores)
