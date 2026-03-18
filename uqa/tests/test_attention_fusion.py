#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.engine import Engine
from uqa.fusion.attention import AttentionFusion
from uqa.fusion.learned import LearnedFusion
from uqa.fusion.query_features import QueryFeatureExtractor
from uqa.operators.attention import AttentionFusionOperator
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.learned_fusion import LearnedFusionOperator
from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

# -- Helpers --


class _FixedOperator(Operator):
    """Test helper: operator that returns a fixed posting list."""

    def __init__(self, entries: list[PostingEntry]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return PostingList.from_sorted(self._entries)


def _make_entry(doc_id: int, score: float) -> PostingEntry:
    return PostingEntry(doc_id, Payload(score=score))


# -- TestQueryFeatureExtractor --


class TestQueryFeatureExtractor:
    def test_n_features(self) -> None:
        idx = InvertedIndex()
        ext = QueryFeatureExtractor(idx)
        assert ext.n_features == 6

    def test_empty_index_returns_zeros(self) -> None:
        idx = InvertedIndex()
        ext = QueryFeatureExtractor(idx)
        features = ext.extract(["hello", "world"])
        assert features.shape == (6,)
        np.testing.assert_array_equal(features, np.zeros(6))

    def test_no_matching_terms(self) -> None:
        from uqa.analysis.analyzer import whitespace_analyzer

        idx = InvertedIndex(analyzer=whitespace_analyzer())
        idx.add_document(1, {"_default": "cat sat mat"})
        ext = QueryFeatureExtractor(idx)
        features = ext.extract(["xyz", "qqq"])
        assert features[0] == 0.0  # mean_idf
        assert features[4] == 2.0  # query_length
        assert features[5] == 0.0  # vocab_overlap

    def test_matching_terms_produce_nonzero_features(self) -> None:
        from uqa.analysis.analyzer import whitespace_analyzer

        idx = InvertedIndex(analyzer=whitespace_analyzer())
        idx.add_document(1, {"_default": "hello world foo"})
        idx.add_document(2, {"_default": "hello bar baz"})
        idx.add_document(3, {"_default": "world baz qux"})
        ext = QueryFeatureExtractor(idx)
        features = ext.extract(["hello", "world"])
        assert features[0] > 0  # mean_idf > 0
        assert features[1] > 0  # max_idf > 0
        assert features[2] > 0  # min_idf > 0
        assert features[4] == 2.0  # query_length
        assert features[5] == 1.0  # vocab_overlap = 2/2


# -- TestAttentionFusion --


class TestAttentionFusion:
    def test_construction(self) -> None:
        af = AttentionFusion(n_signals=3, n_query_features=6, alpha=0.5)
        assert af.n_signals == 3
        assert af.n_query_features == 6

    def test_fuse_result_in_unit_interval(self) -> None:
        af = AttentionFusion(n_signals=2)
        qf = np.zeros(6, dtype=np.float64)
        result = af.fuse([0.8, 0.6], qf)
        assert 0.0 <= result <= 1.0

    def test_fuse_with_nonzero_features(self) -> None:
        af = AttentionFusion(n_signals=2)
        qf = np.array([1.0, 2.0, 0.5, 0.1, 3.0, 0.8])
        result = af.fuse([0.7, 0.3], qf)
        assert 0.0 <= result <= 1.0

    def test_state_dict_roundtrip(self) -> None:
        af = AttentionFusion(n_signals=2, n_query_features=6, alpha=0.3)
        state = af.state_dict()
        assert state["n_signals"] == 2
        assert state["n_query_features"] == 6
        assert state["alpha"] == pytest.approx(0.3)

        af2 = AttentionFusion(n_signals=2, n_query_features=6)
        af2.load_state_dict(state)
        state2 = af2.state_dict()
        np.testing.assert_array_almost_equal(
            state["weights_matrix"], state2["weights_matrix"]
        )

    def test_fuse_three_signals(self) -> None:
        af = AttentionFusion(n_signals=3)
        qf = np.zeros(6, dtype=np.float64)
        result = af.fuse([0.9, 0.5, 0.2], qf)
        assert 0.0 <= result <= 1.0


# -- TestLearnedFusion --


class TestLearnedFusion:
    def test_construction(self) -> None:
        lf = LearnedFusion(n_signals=3, alpha=0.4)
        assert lf.n_signals == 3

    def test_fuse_result_in_unit_interval(self) -> None:
        lf = LearnedFusion(n_signals=2)
        result = lf.fuse([0.8, 0.6])
        assert 0.0 <= result <= 1.0

    def test_state_dict_roundtrip(self) -> None:
        lf = LearnedFusion(n_signals=3, alpha=0.7)
        state = lf.state_dict()
        assert state["n_signals"] == 3
        assert state["alpha"] == pytest.approx(0.7)

        lf2 = LearnedFusion(n_signals=3)
        lf2.load_state_dict(state)
        state2 = lf2.state_dict()
        np.testing.assert_array_almost_equal(state["weights"], state2["weights"])

    def test_fuse_three_signals(self) -> None:
        lf = LearnedFusion(n_signals=3)
        result = lf.fuse([0.9, 0.5, 0.2])
        assert 0.0 <= result <= 1.0


# -- TestAttentionFusionOperator --


class TestAttentionFusionOperator:
    def test_empty_signals_return_empty(self) -> None:
        af = AttentionFusion(n_signals=2)
        qf = np.zeros(6, dtype=np.float64)
        sig1 = _FixedOperator([])
        sig2 = _FixedOperator([])
        op = AttentionFusionOperator([sig1, sig2], af, qf)
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 0

    def test_fuses_two_signals(self) -> None:
        af = AttentionFusion(n_signals=2)
        qf = np.zeros(6, dtype=np.float64)
        sig1 = _FixedOperator([_make_entry(1, 0.8), _make_entry(2, 0.6)])
        sig2 = _FixedOperator([_make_entry(1, 0.7), _make_entry(3, 0.5)])
        op = AttentionFusionOperator([sig1, sig2], af, qf)
        ctx = ExecutionContext()
        result = op.execute(ctx)
        # Documents 1, 2, 3 should all appear (union)
        doc_ids = [e.doc_id for e in result]
        assert sorted(doc_ids) == [1, 2, 3]
        # All scores should be in (0, 1)
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0

    def test_cost_estimate(self) -> None:
        from uqa.core.types import IndexStats

        af = AttentionFusion(n_signals=2)
        qf = np.zeros(6, dtype=np.float64)
        sig1 = _FixedOperator([_make_entry(1, 0.8)])
        sig2 = _FixedOperator([_make_entry(2, 0.7)])
        op = AttentionFusionOperator([sig1, sig2], af, qf)
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        cost = op.cost_estimate(stats)
        assert cost >= 0


# -- TestLearnedFusionOperator --


class TestLearnedFusionOperator:
    def test_empty_signals_return_empty(self) -> None:
        lf = LearnedFusion(n_signals=2)
        sig1 = _FixedOperator([])
        sig2 = _FixedOperator([])
        op = LearnedFusionOperator([sig1, sig2], lf)
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 0

    def test_fuses_two_signals(self) -> None:
        lf = LearnedFusion(n_signals=2)
        sig1 = _FixedOperator([_make_entry(1, 0.8), _make_entry(2, 0.6)])
        sig2 = _FixedOperator([_make_entry(1, 0.7), _make_entry(3, 0.5)])
        op = LearnedFusionOperator([sig1, sig2], lf)
        ctx = ExecutionContext()
        result = op.execute(ctx)
        doc_ids = [e.doc_id for e in result]
        assert sorted(doc_ids) == [1, 2, 3]
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0

    def test_cost_estimate(self) -> None:
        from uqa.core.types import IndexStats

        lf = LearnedFusion(n_signals=2)
        sig1 = _FixedOperator([_make_entry(1, 0.8)])
        sig2 = _FixedOperator([_make_entry(2, 0.7)])
        op = LearnedFusionOperator([sig1, sig2], lf)
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        cost = op.cost_estimate(stats)
        assert cost >= 0


# -- TestAttentionFusionSQL --


class TestAttentionFusionSQL:
    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (title TEXT, body TEXT)")
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('machine learning basics', 'deep neural networks for classification'), "
            "('database systems intro', 'query optimization techniques overview'), "
            "('information retrieval', 'search engine ranking algorithms today')"
        )
        return e

    def test_fuse_attention_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_attention("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural')"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_attention_normalize_sql(self, engine: Engine) -> None:
        """fuse_attention with normalize => true (Bayesian-Attn-Norm)."""
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_attention("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural'),"
            "  normalized => true,"
            "  alpha => 0.5"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_attention_with_base_rate(self, engine: Engine) -> None:
        """fuse_attention with base_rate option."""
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_attention("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural'),"
            "  base_rate => 0.01"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_multihead_sql(self, engine: Engine) -> None:
        """fuse_multihead with 4 heads and normalize."""
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_multihead("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural'),"
            "  n_heads => 4,"
            "  normalized => true"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_multihead_default_heads(self, engine: Engine) -> None:
        """fuse_multihead with defaults."""
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_multihead("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural')"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_learned_with_alpha(self, engine: Engine) -> None:
        """fuse_learned with alpha option."""
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_learned("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural'),"
            "  alpha => 0.7"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_learned_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE fuse_learned("
            "  bayesian_match(title, 'machine'),"
            "  bayesian_match(body, 'neural')"
            ") ORDER BY _score DESC"
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0


# -- TestAttentionFusionQueryBuilder --


class TestAttentionFusionQueryBuilder:
    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE qb_docs (title TEXT, body TEXT)")
        e.sql(
            "INSERT INTO qb_docs (title, body) VALUES "
            "('machine learning basics', 'deep neural networks'), "
            "('database systems intro', 'query optimization')"
        )
        return e

    def test_fuse_attention_builder(self, engine: Engine) -> None:
        qb = engine.query("qb_docs")
        sig1 = engine.query("qb_docs").term("machine", "title")
        sig2 = engine.query("qb_docs").term("neural", "body")
        result = qb.fuse_attention(sig1, sig2).execute()
        assert len(result) > 0

    def test_fuse_learned_builder(self, engine: Engine) -> None:
        qb = engine.query("qb_docs")
        sig1 = engine.query("qb_docs").term("machine", "title")
        sig2 = engine.query("qb_docs").term("neural", "body")
        result = qb.fuse_learned(sig1, sig2).execute()
        assert len(result) > 0
