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
from uqa.operators.sparse import SparseThresholdOperator


class _FixedScoreOperator(Operator):
    """Test helper: produces a fixed posting list."""

    def __init__(self, entries: list[PostingEntry]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return PostingList.from_sorted(self._entries)


class TestSparseThresholdOperator:
    """Tests for SparseThresholdOperator (Paper 4, Section 6.5)."""

    def test_filters_below_threshold(self) -> None:
        entries = [
            PostingEntry(1, Payload(score=0.3)),
            PostingEntry(2, Payload(score=0.7)),
            PostingEntry(3, Payload(score=0.5)),
        ]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.5)
        result = op.execute(ExecutionContext())
        assert len(result) == 1
        assert result.entries[0].doc_id == 2
        assert result.entries[0].payload.score == pytest.approx(0.2)

    def test_zero_threshold_keeps_all_positive(self) -> None:
        entries = [
            PostingEntry(1, Payload(score=0.1)),
            PostingEntry(2, Payload(score=0.5)),
        ]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.0)
        result = op.execute(ExecutionContext())
        assert len(result) == 2

    def test_high_threshold_excludes_all(self) -> None:
        entries = [
            PostingEntry(1, Payload(score=0.3)),
            PostingEntry(2, Payload(score=0.5)),
        ]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=1.0)
        result = op.execute(ExecutionContext())
        assert len(result) == 0

    def test_exact_threshold_excluded(self) -> None:
        entries = [PostingEntry(1, Payload(score=0.5))]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.5)
        result = op.execute(ExecutionContext())
        assert len(result) == 0

    def test_adjusted_scores(self) -> None:
        entries = [
            PostingEntry(1, Payload(score=0.8)),
            PostingEntry(2, Payload(score=0.6)),
        ]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.3)
        result = op.execute(ExecutionContext())
        assert len(result) == 2
        scores = {e.doc_id: e.payload.score for e in result}
        assert scores[1] == pytest.approx(0.5)
        assert scores[2] == pytest.approx(0.3)

    def test_preserves_doc_id_order(self) -> None:
        entries = [
            PostingEntry(1, Payload(score=0.9)),
            PostingEntry(5, Payload(score=0.8)),
            PostingEntry(10, Payload(score=0.7)),
        ]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.1)
        result = op.execute(ExecutionContext())
        doc_ids = [e.doc_id for e in result]
        assert doc_ids == [1, 5, 10]

    def test_cost_estimate(self) -> None:
        entries = [PostingEntry(1, Payload(score=0.5))]
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.3)
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost == source.cost_estimate(stats)

    def test_empty_source(self) -> None:
        source = _FixedScoreOperator([])
        op = SparseThresholdOperator(source, threshold=0.5)
        result = op.execute(ExecutionContext())
        assert len(result) == 0


class TestSparseThresholdSQL:
    """Test sparse_threshold via SQL compiler."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        e.sql("INSERT INTO docs (content) VALUES ('deep learning neural networks')")
        e.sql("INSERT INTO docs (content) VALUES ('database indexing structures')")
        return e

    def test_sparse_threshold_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE sparse_threshold(bayesian_match(content, 'learning'), 0.3)"
        )
        assert result is not None

    def test_sparse_threshold_invalid_args(self, engine: Engine) -> None:
        with pytest.raises(ValueError):
            engine.sql(
                "SELECT * FROM docs WHERE sparse_threshold(bayesian_match(content, 'learning'))"
            )


class TestSparseThresholdQueryBuilder:
    """Test sparse_threshold via QueryBuilder."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        e.sql("INSERT INTO docs (content) VALUES ('deep learning neural networks')")
        return e

    def test_query_builder_sparse_threshold(self, engine: Engine) -> None:
        result = (
            engine.query("docs")
            .term("learning", "content")
            .score_bayesian_bm25("learning", "content")
            .sparse_threshold(0.3)
            .execute()
        )
        for entry in result:
            assert entry.payload.score > 0.0

    def test_query_builder_requires_source(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="requires a source"):
            engine.query("docs").sparse_threshold(0.3)
