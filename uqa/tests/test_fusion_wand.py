#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.engine import Engine
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.hybrid import LogOddsFusionOperator
from uqa.scoring.fusion_wand import FusionWANDScorer


def _make_posting_list(entries: list[tuple[int, float]]) -> PostingList:
    return PostingList([PostingEntry(d, Payload(score=s)) for d, s in entries])


class _FixedOperator(Operator):
    def __init__(self, entries: list[tuple[int, float]]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return _make_posting_list(self._entries)


class TestFusionWANDScorer:
    """Tests for FusionWANDScorer (Paper 4, Section 8.7)."""

    def test_basic_top_k(self) -> None:
        pl1 = _make_posting_list([(1, 0.9), (2, 0.7), (3, 0.5)])
        pl2 = _make_posting_list([(1, 0.8), (2, 0.6), (4, 0.4)])
        scorer = FusionWANDScorer([pl1, pl2], [0.9, 0.8], k=2)
        result = scorer.score_top_k()
        assert len(result) == 2

    def test_top_k_returns_highest(self) -> None:
        pl1 = _make_posting_list([(1, 0.9), (2, 0.3), (3, 0.1)])
        pl2 = _make_posting_list([(1, 0.8), (2, 0.2), (3, 0.1)])
        scorer = FusionWANDScorer([pl1, pl2], [0.9, 0.8], k=1)
        result = scorer.score_top_k()
        assert len(result) == 1
        assert result.entries[0].doc_id == 1

    def test_top_k_larger_than_docs(self) -> None:
        pl1 = _make_posting_list([(1, 0.7)])
        pl2 = _make_posting_list([(1, 0.6)])
        scorer = FusionWANDScorer([pl1, pl2], [0.7, 0.6], k=10)
        result = scorer.score_top_k()
        assert len(result) == 1

    def test_empty_signals(self) -> None:
        scorer = FusionWANDScorer([], [], k=5)
        result = scorer.score_top_k()
        assert len(result) == 0

    def test_single_signal(self) -> None:
        pl = _make_posting_list([(1, 0.9), (2, 0.3)])
        scorer = FusionWANDScorer([pl], [0.9], k=1)
        result = scorer.score_top_k()
        assert len(result) == 1
        assert result.entries[0].doc_id == 1

    def test_fused_upper_bound(self) -> None:
        scorer = FusionWANDScorer([], [0.9, 0.8], k=5)
        ub = scorer._compute_fused_upper_bound([0.9, 0.8])
        assert 0.0 < ub < 1.0

    def test_scores_are_probabilities(self) -> None:
        pl1 = _make_posting_list([(1, 0.7), (2, 0.6)])
        pl2 = _make_posting_list([(1, 0.8), (2, 0.5)])
        scorer = FusionWANDScorer([pl1, pl2], [0.8, 0.8], k=5)
        result = scorer.score_top_k()
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0

    def test_alpha_parameter(self) -> None:
        pl1 = _make_posting_list([(1, 0.7)])
        pl2 = _make_posting_list([(1, 0.6)])
        s1 = FusionWANDScorer([pl1, pl2], [0.7, 0.6], alpha=0.1, k=5)
        s2 = FusionWANDScorer([pl1, pl2], [0.7, 0.6], alpha=0.9, k=5)
        r1 = s1.score_top_k()
        r2 = s2.score_top_k()
        # Different alpha should produce different scores
        assert r1.entries[0].payload.score != pytest.approx(
            r2.entries[0].payload.score, abs=1e-3
        )


class TestLogOddsFusionTopK:
    """Tests for LogOddsFusionOperator with top_k parameter."""

    def test_top_k_parameter(self) -> None:
        sig1 = _FixedOperator([(1, 0.9), (2, 0.7), (3, 0.5), (4, 0.3)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.6), (3, 0.4), (4, 0.2)])
        op = LogOddsFusionOperator([sig1, sig2], top_k=2)
        result = op.execute(ExecutionContext())
        assert len(result) == 2

    def test_without_top_k_returns_all(self) -> None:
        sig1 = _FixedOperator([(1, 0.9), (2, 0.7)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.6)])
        op = LogOddsFusionOperator([sig1, sig2])
        result = op.execute(ExecutionContext())
        assert len(result) == 2

    def test_top_k_preserves_ranking(self) -> None:
        sig1 = _FixedOperator([(1, 0.9), (2, 0.3), (3, 0.1)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.2), (3, 0.1)])
        op = LogOddsFusionOperator([sig1, sig2], top_k=2)
        result = op.execute(ExecutionContext())
        doc_ids = sorted([e.doc_id for e in result])
        assert 1 in doc_ids

    def test_top_k_results_match_full_results(self) -> None:
        sig1 = _FixedOperator([(1, 0.9), (2, 0.7), (3, 0.5)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.6), (3, 0.4)])

        full_op = LogOddsFusionOperator([sig1, sig2])
        full_result = full_op.execute(ExecutionContext())
        full_scores = sorted(
            [(e.doc_id, e.payload.score) for e in full_result],
            key=lambda x: -x[1],
        )

        # Re-create operators since they were consumed
        sig1b = _FixedOperator([(1, 0.9), (2, 0.7), (3, 0.5)])
        sig2b = _FixedOperator([(1, 0.8), (2, 0.6), (3, 0.4)])
        top_op = LogOddsFusionOperator([sig1b, sig2b], top_k=2)
        top_result = top_op.execute(ExecutionContext())
        top_scores = sorted(
            [(e.doc_id, e.payload.score) for e in top_result],
            key=lambda x: -x[1],
        )

        # Top-k should contain the highest-scored documents
        for doc_id, score in top_scores:
            matching = [s for d, s in full_scores if d == doc_id]
            assert len(matching) == 1
            assert score == pytest.approx(matching[0], abs=1e-6)


class TestFusionWANDSQL:
    """Tests for FusionWAND integration."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        e.sql("INSERT INTO docs (content) VALUES ('deep learning neural networks')")
        e.sql("INSERT INTO docs (content) VALUES ('database indexing structures')")
        return e

    def test_log_odds_fusion_with_limit(self, engine: Engine) -> None:
        # Standard fusion query (LIMIT is handled at SELECT level)
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "fuse_log_odds(bayesian_match(content, 'learning'), "
            "bayesian_match(content, 'algorithms')) "
            "LIMIT 1"
        )
        assert result is not None

    def test_fusion_result_scores(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "fuse_log_odds(bayesian_match(content, 'learning'), "
            "bayesian_match(content, 'algorithms'))"
        )
        assert result is not None
