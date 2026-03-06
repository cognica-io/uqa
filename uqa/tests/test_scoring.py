from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import IndexStats
from uqa.scoring.bm25 import BM25Params, BM25Scorer
from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer
from uqa.scoring.vector import VectorScorer


@pytest.fixture
def index_stats() -> IndexStats:
    return IndexStats(total_docs=10000, avg_doc_length=200.0)


@pytest.fixture
def bm25_scorer(index_stats: IndexStats) -> BM25Scorer:
    return BM25Scorer(BM25Params(), index_stats)


@pytest.fixture
def bayesian_scorer(index_stats: IndexStats) -> BayesianBM25Scorer:
    return BayesianBM25Scorer(BayesianBM25Params(), index_stats)


# -- BM25 Tests --


class TestBM25Scorer:
    def test_idf_positive_for_rare_terms(self, bm25_scorer: BM25Scorer) -> None:
        idf = bm25_scorer.idf(doc_freq=10)
        assert idf > 0

    def test_idf_decreases_with_frequency(self, bm25_scorer: BM25Scorer) -> None:
        idf_rare = bm25_scorer.idf(doc_freq=10)
        idf_common = bm25_scorer.idf(doc_freq=5000)
        assert idf_rare > idf_common

    def test_monotonicity_term_frequency(self, bm25_scorer: BM25Scorer) -> None:
        """Higher term frequency should produce higher score."""
        score_low = bm25_scorer.score(term_freq=1, doc_length=200, doc_freq=100)
        score_mid = bm25_scorer.score(term_freq=5, doc_length=200, doc_freq=100)
        score_high = bm25_scorer.score(term_freq=20, doc_length=200, doc_freq=100)
        assert score_low < score_mid < score_high

    def test_monotonicity_doc_length(self, bm25_scorer: BM25Scorer) -> None:
        """Shorter documents should produce higher scores."""
        score_short = bm25_scorer.score(term_freq=5, doc_length=50, doc_freq=100)
        score_avg = bm25_scorer.score(term_freq=5, doc_length=200, doc_freq=100)
        score_long = bm25_scorer.score(term_freq=5, doc_length=500, doc_freq=100)
        assert score_short > score_avg > score_long

    def test_upper_bound(self, bm25_scorer: BM25Scorer) -> None:
        """Score should always be less than boost * IDF for any input."""
        ub = bm25_scorer.upper_bound(doc_freq=100)
        for tf in [1, 5, 10, 50, 100, 1000]:
            for dl in [1, 50, 100, 200, 500, 1000]:
                score = bm25_scorer.score(term_freq=tf, doc_length=dl, doc_freq=100)
                assert score < ub, f"score={score} >= ub={ub} at tf={tf}, dl={dl}"

    def test_score_non_negative(self, bm25_scorer: BM25Scorer) -> None:
        score = bm25_scorer.score(term_freq=1, doc_length=200, doc_freq=100)
        assert score >= 0.0

    def test_boosted_upper_bound(self, index_stats: IndexStats) -> None:
        params = BM25Params(boost=2.5)
        scorer = BM25Scorer(params, index_stats)
        ub = scorer.upper_bound(doc_freq=50)
        score = scorer.score(term_freq=100, doc_length=10, doc_freq=50)
        assert score < ub


# -- Bayesian BM25 Tests --


class TestBayesianBM25Scorer:
    def test_output_in_unit_interval(self, bayesian_scorer: BayesianBM25Scorer) -> None:
        """Bayesian BM25 output must be in [0, 1]."""
        for tf in [0, 1, 5, 10, 50]:
            for dl in [10, 100, 200, 500, 1000]:
                for df in [1, 10, 100, 1000, 5000]:
                    p = bayesian_scorer.score(term_freq=tf, doc_length=dl, doc_freq=df)
                    assert 0.0 <= p <= 1.0, (
                        f"p={p} out of [0,1] at tf={tf}, dl={dl}, df={df}"
                    )

    def test_monotonicity_higher_bm25_higher_posterior(
        self, index_stats: IndexStats
    ) -> None:
        """Higher BM25 score should produce higher posterior for fixed prior."""
        scorer = BayesianBM25Scorer(BayesianBM25Params(), index_stats)
        # Same doc_length and doc_freq, vary term_freq to change BM25 score
        p_low = scorer.score(term_freq=1, doc_length=200, doc_freq=100)
        p_mid = scorer.score(term_freq=5, doc_length=200, doc_freq=100)
        p_high = scorer.score(term_freq=20, doc_length=200, doc_freq=100)
        assert p_low < p_mid < p_high

    def test_composite_prior_bounds(
        self, bayesian_scorer: BayesianBM25Scorer
    ) -> None:
        """Composite prior must be in [0.1, 0.9] for all inputs."""
        for tf in [0, 1, 5, 10, 50, 100]:
            for dl in [1, 10, 100, 200, 500, 2000]:
                prior = bayesian_scorer._composite_prior(tf, dl)
                assert 0.1 <= prior <= 0.9, (
                    f"prior={prior} out of [0.1, 0.9] at tf={tf}, dl={dl}"
                )

    def test_base_rate_identity(self, index_stats: IndexStats) -> None:
        """When base_rate=0.5, the second Bayes update is identity."""
        params_05 = BayesianBM25Params(base_rate=0.5)
        scorer_05 = BayesianBM25Scorer(params_05, index_stats)

        # Score with base_rate=0.5 (second update skipped)
        p = scorer_05.score(term_freq=5, doc_length=200, doc_freq=100)

        # Manually compute: raw -> likelihood -> prior -> first update only
        raw = scorer_05.bm25.score(5, 200, 100)
        likelihood = BayesianBM25Scorer._sigmoid(params_05.alpha * (raw - params_05.beta))
        prior = scorer_05._composite_prior(5, 200)
        expected = BayesianBM25Scorer._bayes_update(likelihood, prior)

        assert abs(p - expected) < 1e-12

    def test_base_rate_shifts_posterior(self, index_stats: IndexStats) -> None:
        """Non-0.5 base rate should shift the posterior."""
        p_low_br = BayesianBM25Scorer(
            BayesianBM25Params(base_rate=0.2), index_stats
        ).score(5, 200, 100)
        p_default = BayesianBM25Scorer(
            BayesianBM25Params(base_rate=0.5), index_stats
        ).score(5, 200, 100)
        p_high_br = BayesianBM25Scorer(
            BayesianBM25Params(base_rate=0.8), index_stats
        ).score(5, 200, 100)
        assert p_low_br < p_default < p_high_br

    def test_upper_bound_at_least_score(
        self, bayesian_scorer: BayesianBM25Scorer
    ) -> None:
        ub = bayesian_scorer.upper_bound(doc_freq=100)
        for tf in [1, 5, 10, 50]:
            for dl in [50, 200, 500]:
                score = bayesian_scorer.score(tf, dl, 100)
                assert score <= ub + 1e-10

    def test_sigmoid_numerically_stable(self) -> None:
        """Sigmoid should not overflow for extreme inputs."""
        assert BayesianBM25Scorer._sigmoid(500.0) == pytest.approx(1.0)
        assert BayesianBM25Scorer._sigmoid(-500.0) == pytest.approx(0.0)
        assert BayesianBM25Scorer._sigmoid(0.0) == pytest.approx(0.5)


# -- Vector Scorer Tests --


class TestVectorScorer:
    def test_cosine_similarity_identical(self) -> None:
        v = np.array([1.0, 2.0, 3.0])
        assert VectorScorer.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_opposite(self) -> None:
        v = np.array([1.0, 0.0, 0.0])
        assert VectorScorer.cosine_similarity(v, -v) == pytest.approx(-1.0)

    def test_cosine_similarity_orthogonal(self) -> None:
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert VectorScorer.cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        z = np.zeros(3)
        assert VectorScorer.cosine_similarity(a, z) == 0.0
        assert VectorScorer.cosine_similarity(z, z) == 0.0

    def test_similarity_to_probability_range(self) -> None:
        assert VectorScorer.similarity_to_probability(1.0) == pytest.approx(1.0)
        assert VectorScorer.similarity_to_probability(-1.0) == pytest.approx(0.0)
        assert VectorScorer.similarity_to_probability(0.0) == pytest.approx(0.5)

    def test_similarity_to_probability_monotonic(self) -> None:
        sims = [-0.8, -0.3, 0.0, 0.4, 0.9]
        probs = [VectorScorer.similarity_to_probability(s) for s in sims]
        for i in range(len(probs) - 1):
            assert probs[i] < probs[i + 1]
