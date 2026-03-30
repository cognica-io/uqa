#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import datetime

import pytest

from uqa.core.types import IndexStats
from uqa.engine import Engine
from uqa.scoring.bayesian_bm25 import BayesianBM25Params
from uqa.scoring.external_prior import (
    ExternalPriorScorer,
    authority_prior,
    recency_prior,
)


class TestExternalPriorScorer:
    """Tests for ExternalPriorScorer (Paper 3, Section 12.2 #6)."""

    def test_score_with_neutral_prior(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        stats._doc_freqs[("_default", "test")] = 10

        def neutral_fn(fields: object) -> float:
            return 0.5

        scorer = ExternalPriorScorer(BayesianBM25Params(), stats, neutral_fn)
        score = scorer.score_with_prior(3, 10, 10, {})
        assert 0.0 < score < 1.0

    def test_high_prior_boosts_score(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        stats._doc_freqs[("_default", "test")] = 10

        def neutral_fn(fields: object) -> float:
            return 0.5

        def high_fn(fields: object) -> float:
            return 0.9

        scorer_neutral = ExternalPriorScorer(BayesianBM25Params(), stats, neutral_fn)
        scorer_high = ExternalPriorScorer(BayesianBM25Params(), stats, high_fn)

        base_score = scorer_neutral.score_with_prior(3, 10, 10, {})
        boosted_score = scorer_high.score_with_prior(3, 10, 10, {})
        assert boosted_score > base_score

    def test_low_prior_reduces_score(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        stats._doc_freqs[("_default", "test")] = 10

        def neutral_fn(fields: object) -> float:
            return 0.5

        def low_fn(fields: object) -> float:
            return 0.1

        scorer_neutral = ExternalPriorScorer(BayesianBM25Params(), stats, neutral_fn)
        scorer_low = ExternalPriorScorer(BayesianBM25Params(), stats, low_fn)

        base_score = scorer_neutral.score_with_prior(3, 10, 10, {})
        reduced_score = scorer_low.score_with_prior(3, 10, 10, {})
        assert reduced_score < base_score

    def test_score_in_probability_range(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        stats._doc_freqs[("_default", "test")] = 10

        def fn(fields: object) -> float:
            return 0.7

        scorer = ExternalPriorScorer(BayesianBM25Params(), stats, fn)
        score = scorer.score_with_prior(2, 8, 10, {"authority": "high"})
        assert 0.0 < score < 1.0


class TestRecencyPrior:
    """Tests for recency_prior helper."""

    def test_missing_field_returns_neutral(self) -> None:
        fn = recency_prior("timestamp")
        assert fn({}) == pytest.approx(0.5)

    def test_recent_date_gives_high_prior(self) -> None:
        fn = recency_prior("timestamp", decay_days=30.0)
        now = datetime.datetime.now().isoformat()
        prior = fn({"timestamp": now})
        assert prior > 0.7

    def test_old_date_gives_lower_prior(self) -> None:
        fn = recency_prior("timestamp", decay_days=30.0)
        old = (datetime.datetime.now() - datetime.timedelta(days=365)).isoformat()
        prior = fn({"timestamp": old})
        assert prior < 0.6

    def test_invalid_date_returns_neutral(self) -> None:
        fn = recency_prior("timestamp")
        assert fn({"timestamp": "not-a-date"}) == pytest.approx(0.5)


class TestAuthorityPrior:
    """Tests for authority_prior helper."""

    def test_high_authority(self) -> None:
        fn = authority_prior("level")
        assert fn({"level": "high"}) == pytest.approx(0.8)

    def test_medium_authority(self) -> None:
        fn = authority_prior("level")
        assert fn({"level": "medium"}) == pytest.approx(0.6)

    def test_low_authority(self) -> None:
        fn = authority_prior("level")
        assert fn({"level": "low"}) == pytest.approx(0.4)

    def test_missing_field_returns_neutral(self) -> None:
        fn = authority_prior("level")
        assert fn({}) == pytest.approx(0.5)

    def test_unknown_level_returns_neutral(self) -> None:
        fn = authority_prior("level")
        assert fn({"level": "unknown"}) == pytest.approx(0.5)

    def test_custom_levels(self) -> None:
        fn = authority_prior("rank", levels={"expert": 0.95, "novice": 0.3})
        assert fn({"rank": "expert"}) == pytest.approx(0.95)
        assert fn({"rank": "novice"}) == pytest.approx(0.3)


class TestExternalPriorSQL:
    """Tests for bayesian_match_with_prior via SQL."""

    @pytest.fixture()
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT, authority TEXT)")
        e.sql("CREATE INDEX idx_docs_gin ON docs USING gin (content)")
        e.sql(
            "INSERT INTO docs (content, authority) VALUES ('machine learning', 'high')"
        )
        e.sql("INSERT INTO docs (content, authority) VALUES ('deep learning', 'low')")
        return e

    def test_bayesian_with_prior_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "bayesian_match_with_prior("
            "content, 'learning', 'authority', 'authority')"
        )
        assert result is not None

    def test_bayesian_with_prior_invalid_mode(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unknown prior mode"):
            engine.sql(
                "SELECT * FROM docs WHERE "
                "bayesian_match_with_prior("
                "content, 'learning', 'authority', 'invalid')"
            )


class TestExternalPriorQueryBuilder:
    """Tests for score_bayesian_with_prior via fluent API."""

    def test_fluent_api_with_authority_prior(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE articles (id SERIAL PRIMARY KEY, body TEXT, source TEXT)")
        e.sql("CREATE INDEX idx_articles_gin ON articles USING gin (body)")
        e.sql(
            "INSERT INTO articles (body, source) "
            "VALUES ('information retrieval systems', 'high')"
        )
        e.sql(
            "INSERT INTO articles (body, source) "
            "VALUES ('retrieval augmented generation', 'low')"
        )

        prior_fn = authority_prior("source")
        qb = e.query("articles").score_bayesian_with_prior(
            "retrieval", field="body", prior_fn=prior_fn
        )
        result = qb.execute()
        assert len(result) > 0

    def test_fluent_api_requires_prior_fn(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, text TEXT)")
        with pytest.raises(ValueError, match="prior_fn is required"):
            e.query("t").score_bayesian_with_prior("test")
