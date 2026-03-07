#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for parallel execution of independent operator branches."""

from __future__ import annotations

import time

import numpy as np
import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Equals,
    IndexStats,
    Payload,
    PostingEntry,
)
from uqa.engine import Engine
from uqa.operators.base import ExecutionContext, Operator
from uqa.planner.parallel import ParallelExecutor


# ==================================================================
# ParallelExecutor unit tests
# ==================================================================


class _SlowOperator(Operator):
    """Operator that sleeps to simulate I/O-bound work."""

    def __init__(self, doc_ids: list[int], delay: float = 0.05) -> None:
        self._doc_ids = doc_ids
        self._delay = delay

    def execute(self, context: ExecutionContext) -> PostingList:
        time.sleep(self._delay)
        return PostingList([
            PostingEntry(d, Payload(score=1.0)) for d in self._doc_ids
        ])


class TestParallelExecutor:
    def test_sequential_when_disabled(self):
        """max_workers=0 disables parallel execution."""
        par = ParallelExecutor(max_workers=0)
        assert not par.enabled

        ctx = ExecutionContext()
        ops = [_SlowOperator([1]), _SlowOperator([2])]
        results = par.execute_branches(ops, ctx)
        assert len(results) == 2
        assert results[0].doc_ids == {1}
        assert results[1].doc_ids == {2}

    def test_sequential_with_single_branch(self):
        """Single branch always runs sequentially."""
        par = ParallelExecutor(max_workers=4)
        ctx = ExecutionContext()
        ops = [_SlowOperator([1])]
        results = par.execute_branches(ops, ctx)
        assert len(results) == 1
        assert results[0].doc_ids == {1}

    def test_parallel_preserves_order(self):
        """Results come back in the same order as input operators."""
        par = ParallelExecutor(max_workers=4)
        ctx = ExecutionContext()
        ops = [
            _SlowOperator([10, 20], delay=0.05),
            _SlowOperator([30], delay=0.01),
            _SlowOperator([40, 50, 60], delay=0.03),
        ]
        results = par.execute_branches(ops, ctx)
        assert len(results) == 3
        assert results[0].doc_ids == {10, 20}
        assert results[1].doc_ids == {30}
        assert results[2].doc_ids == {40, 50, 60}

    def test_parallel_faster_than_sequential(self):
        """Parallel execution of slow operators is faster than sequential."""
        n_ops = 4
        delay = 0.05
        ops = [_SlowOperator([i], delay=delay) for i in range(n_ops)]
        ctx = ExecutionContext()

        # Sequential
        par_off = ParallelExecutor(max_workers=0)
        t0 = time.perf_counter()
        par_off.execute_branches(ops, ctx)
        seq_time = time.perf_counter() - t0

        # Parallel
        par_on = ParallelExecutor(max_workers=4)
        t0 = time.perf_counter()
        par_on.execute_branches(ops, ctx)
        par_time = time.perf_counter() - t0

        # Parallel should be faster (at most ~1 delay vs n*delay)
        assert par_time < seq_time * 0.75

    def test_parallel_error_propagation(self):
        """Errors in parallel branches propagate correctly."""
        class _FailOperator(Operator):
            def execute(self, context: ExecutionContext) -> PostingList:
                raise ValueError("test error")

        par = ParallelExecutor(max_workers=4)
        ctx = ExecutionContext()
        ops = [_SlowOperator([1]), _FailOperator()]

        with pytest.raises(ValueError, match="test error"):
            par.execute_branches(ops, ctx)


# ==================================================================
# Boolean operators with parallel execution
# ==================================================================


class TestParallelBooleanOps:
    @pytest.fixture
    def engine(self):
        e = Engine(vector_dimensions=4, max_elements=10, parallel_workers=4)
        docs = [
            {"title": "neural network basics", "cat": "ml"},
            {"title": "transformer models", "cat": "dl"},
            {"title": "graph neural networks", "cat": "ml"},
            {"title": "bayesian optimization", "cat": "opt"},
            {"title": "reinforcement learning", "cat": "rl"},
        ]
        for i, doc in enumerate(docs, 1):
            e.add_document(i, doc)
        return e

    def test_union_parallel_same_as_sequential(self, engine):
        """Union with parallel execution produces same results."""
        from uqa.operators.boolean import UnionOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor

        ctx_par = engine._build_context()
        ops = [
            TermOperator("neural"),
            TermOperator("bayesian"),
            TermOperator("reinforcement"),
        ]
        par_result = PlanExecutor(ctx_par).execute(UnionOperator(ops))

        # Sequential
        ctx_seq = ExecutionContext(
            document_store=engine.document_store,
            inverted_index=engine.inverted_index,
            parallel_executor=ParallelExecutor(max_workers=0),
        )
        seq_result = PlanExecutor(ctx_seq).execute(
            UnionOperator([
                TermOperator("neural"),
                TermOperator("bayesian"),
                TermOperator("reinforcement"),
            ])
        )

        assert set(par_result.doc_ids) == set(seq_result.doc_ids)

    def test_intersect_parallel_same_as_sequential(self, engine):
        """Intersect with parallel execution produces same results."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.executor import PlanExecutor

        ctx_par = engine._build_context()
        ops = [TermOperator("neural"), TermOperator("networks")]
        par_result = PlanExecutor(ctx_par).execute(IntersectOperator(ops))

        ctx_seq = ExecutionContext(
            document_store=engine.document_store,
            inverted_index=engine.inverted_index,
            parallel_executor=ParallelExecutor(max_workers=0),
        )
        seq_result = PlanExecutor(ctx_seq).execute(
            IntersectOperator([
                TermOperator("neural"),
                TermOperator("networks"),
            ])
        )

        assert set(par_result.doc_ids) == set(seq_result.doc_ids)


# ==================================================================
# Fusion operators with parallel execution
# ==================================================================


class TestParallelFusion:
    @pytest.fixture
    def engine(self):
        e = Engine(vector_dimensions=4, max_elements=10, parallel_workers=4)
        docs = [
            {"title": "neural network basics", "cat": "ml"},
            {"title": "transformer models", "cat": "dl"},
            {"title": "graph neural networks", "cat": "ml"},
        ]
        for i, doc in enumerate(docs, 1):
            rng = np.random.RandomState(i)
            emb = rng.randn(4).astype(np.float32)
            emb = emb / np.linalg.norm(emb)
            e.add_document(i, doc, emb)
        return e

    def test_log_odds_fusion_parallel(self, engine):
        """LogOddsFusion with parallel signals produces correct results."""
        from uqa.operators.hybrid import LogOddsFusionOperator
        from uqa.operators.primitive import KNNOperator, ScoreOperator, TermOperator
        from uqa.scoring.bm25 import BM25Params, BM25Scorer
        from uqa.planner.executor import PlanExecutor

        ctx = engine._build_context()
        stats = ctx.inverted_index.stats

        term = TermOperator("neural", field="title")
        scorer = BM25Scorer(BM25Params(), stats)
        text_sig = ScoreOperator(scorer, term, ["neural"], field="title")

        qv = np.random.RandomState(42).randn(4).astype(np.float32)
        qv = qv / np.linalg.norm(qv)
        knn_sig = KNNOperator(qv, k=3)

        fusion = LogOddsFusionOperator([text_sig, knn_sig])
        result = PlanExecutor(ctx).execute(fusion)

        assert len(result) > 0
        scores = [e.payload.score for e in result]
        assert all(0 <= s <= 1 for s in scores)


# ==================================================================
# Engine parallel_workers configuration
# ==================================================================


class TestEngineParallelConfig:
    def test_default_parallel_workers(self):
        """Engine creates parallel executor with default workers."""
        e = Engine()
        assert e._parallel_executor.enabled
        assert e._parallel_executor._max_workers == 4

    def test_custom_parallel_workers(self):
        """Engine respects custom parallel_workers."""
        e = Engine(parallel_workers=8)
        assert e._parallel_executor._max_workers == 8

    def test_parallel_disabled(self):
        """parallel_workers=0 disables parallel execution."""
        e = Engine(parallel_workers=0)
        assert not e._parallel_executor.enabled

    def test_context_has_parallel_executor(self):
        """ExecutionContext carries parallel executor."""
        e = Engine(parallel_workers=2)
        ctx = e._build_context()
        assert ctx.parallel_executor is not None
        assert ctx.parallel_executor._max_workers == 2


# ==================================================================
# SQL-level integration
# ==================================================================


class TestSQLParallel:
    def test_sql_union_query_with_parallel(self):
        """SQL query with OR (union) executes with parallel context."""
        e = Engine(parallel_workers=4)
        e.sql(
            "CREATE TABLE docs ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT"
            ")"
        )
        for i in range(1, 6):
            e.sql(
                f"INSERT INTO docs (id, title) VALUES "
                f"({i}, 'neural network paper {i}')"
            )
        r = e.sql(
            "SELECT title FROM docs WHERE title = 'neural network paper 1' "
            "OR title = 'neural network paper 3'"
        )
        titles = [row["title"] for row in r.rows]
        assert "neural network paper 1" in titles
        assert "neural network paper 3" in titles

    def test_sql_fusion_query_with_parallel(self):
        """SQL fusion query works with parallel execution."""
        e = Engine(parallel_workers=4, vector_dimensions=4)
        e.sql(
            "CREATE TABLE docs ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT, "
            "body TEXT"
            ")"
        )
        for i in range(1, 4):
            e.sql(
                f"INSERT INTO docs (id, title, body) VALUES "
                f"({i}, 'deep learning {i}', 'neural networks paper {i}')"
            )
        r = e.sql(
            "SELECT title FROM docs WHERE "
            "fuse_log_odds("
            "text_match(body, 'neural'), "
            "text_match(title, 'deep'))"
        )
        assert len(r.rows) > 0
