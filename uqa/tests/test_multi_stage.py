#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.engine import Engine
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.multi_stage import MultiStageOperator


class _FixedScoreOperator(Operator):
    def __init__(self, entries: list[tuple[int, float]]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return PostingList.from_sorted(
            [PostingEntry(d, Payload(score=s)) for d, s in self._entries]
        )


class TestMultiStageOperator:
    """Tests for MultiStageOperator (Paper 4, Section 9)."""

    def test_single_stage_top_k(self) -> None:
        op = _FixedScoreOperator([(1, 0.9), (2, 0.5), (3, 0.3)])
        ms = MultiStageOperator([(op, 2)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 2

    def test_single_stage_threshold(self) -> None:
        op = _FixedScoreOperator([(1, 0.9), (2, 0.5), (3, 0.3)])
        ms = MultiStageOperator([(op, 0.4)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 2

    def test_two_stage_pipeline(self) -> None:
        stage1 = _FixedScoreOperator([(1, 0.9), (2, 0.7), (3, 0.5), (4, 0.3)])
        stage2 = _FixedScoreOperator([(1, 0.95), (2, 0.6), (3, 0.4)])
        ms = MultiStageOperator([(stage1, 3), (stage2, 2)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 2

    def test_stage_rescoring(self) -> None:
        stage1 = _FixedScoreOperator([(1, 0.5), (2, 0.9)])
        stage2 = _FixedScoreOperator([(1, 0.95), (2, 0.3)])
        ms = MultiStageOperator([(stage1, 2), (stage2, 1)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 1
        # Doc 1 should be the top after stage2 rescoring
        assert result.entries[0].doc_id == 1

    def test_threshold_stage(self) -> None:
        stage1 = _FixedScoreOperator([(1, 0.9), (2, 0.5), (3, 0.1)])
        stage2 = _FixedScoreOperator([(1, 0.8), (2, 0.6), (3, 0.2)])
        ms = MultiStageOperator([(stage1, 0.3), (stage2, 0.5)])
        result = ms.execute(ExecutionContext())
        # Stage1: keeps 1 (0.9) and 2 (0.5)
        # Stage2: re-scores to 1 (0.8) and 2 (0.6), both >= 0.5
        assert len(result) == 2

    def test_empty_after_cutoff(self) -> None:
        stage1 = _FixedScoreOperator([(1, 0.3), (2, 0.2)])
        ms = MultiStageOperator([(stage1, 0.5)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 0

    def test_requires_at_least_one_stage(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            MultiStageOperator([])

    def test_cost_estimate_cascading(self) -> None:
        stage1 = _FixedScoreOperator([(1, 0.9)])
        stage2 = _FixedScoreOperator([(1, 0.8)])
        ms = MultiStageOperator([(stage1, 10), (stage2, 5)])
        stats = IndexStats(total_docs=100)
        cost = ms.cost_estimate(stats)
        assert cost > 0

    def test_three_stages(self) -> None:
        s1 = _FixedScoreOperator([(i, 0.9 - i * 0.1) for i in range(1, 8)])
        s2 = _FixedScoreOperator([(i, 0.8 - i * 0.05) for i in range(1, 8)])
        s3 = _FixedScoreOperator([(1, 0.99), (2, 0.5)])
        ms = MultiStageOperator([(s1, 5), (s2, 3), (s3, 1)])
        result = ms.execute(ExecutionContext())
        assert len(result) == 1


class TestMultiStageSQL:
    """Tests for staged_retrieval via SQL."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql(
            "INSERT INTO docs (content) VALUES ('machine learning algorithms')"
        )
        e.sql(
            "INSERT INTO docs (content) VALUES ('deep learning neural networks')"
        )
        e.sql(
            "INSERT INTO docs (content) VALUES ('database indexing structures')"
        )
        e.sql(
            "INSERT INTO docs (content) VALUES ('search engine optimization')"
        )
        return e

    def test_staged_retrieval_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "staged_retrieval("
            "bayesian_match(content, 'learning'), 3, "
            "bayesian_match(content, 'algorithms'), 1)"
        )
        assert result is not None

    def test_staged_retrieval_single_stage(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "staged_retrieval(bayesian_match(content, 'learning'), 2)"
        )
        assert result is not None


class TestMultiStageQueryBuilder:
    """Tests for QueryBuilder.multi_stage()."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql(
            "INSERT INTO docs (content) VALUES ('machine learning algorithms')"
        )
        e.sql(
            "INSERT INTO docs (content) VALUES ('deep learning neural networks')"
        )
        return e

    def test_query_builder_multi_stage(self, engine: Engine) -> None:
        s1 = (
            engine.query("docs")
            .term("learning", "content")
            .score_bayesian_bm25("learning", "content")
        )
        s2 = (
            engine.query("docs")
            .term("algorithms", "content")
            .score_bayesian_bm25("algorithms", "content")
        )
        result = (
            engine.query("docs").multi_stage([(s1, 2), (s2, 1)]).execute()
        )
        assert len(result) <= 1

    def test_query_builder_stage_requires_operator(
        self, engine: Engine
    ) -> None:
        empty = engine.query("docs")
        s1 = (
            engine.query("docs")
            .term("learning", "content")
            .score_bayesian_bm25("learning", "content")
        )
        with pytest.raises(ValueError, match="must have an operator"):
            engine.query("docs").multi_stage([(empty, 2), (s1, 1)])
