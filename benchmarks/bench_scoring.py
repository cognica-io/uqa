#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for scoring and fusion operations.

Covers BM25, Bayesian BM25, vector scoring, and log-odds fusion.
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import IndexStats
from uqa.scoring.bm25 import BM25Params, BM25Scorer
from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer
from uqa.scoring.vector import VectorScorer
from uqa.fusion.log_odds import LogOddsFusion
from benchmarks.data.generators import BenchmarkDataGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index_stats(total_docs: int = 10000) -> IndexStats:
    return IndexStats(
        total_docs=total_docs,
        avg_doc_length=100.0,
        _doc_freqs={("body", "term"): total_docs // 10},
    )


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class TestBM25:
    def test_score_single(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = BM25Scorer(BM25Params(), stats)
        benchmark(scorer.score, 5, 120, 1000)

    def test_score_batch(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = BM25Scorer(BM25Params(), stats)
        rng = np.random.default_rng(42)
        tfs = rng.integers(1, 20, size=10000)
        dls = rng.integers(50, 200, size=10000)
        df = 1000

        def score_all() -> float:
            total = 0.0
            for i in range(len(tfs)):
                total += scorer.score(int(tfs[i]), int(dls[i]), df)
            return total

        benchmark(score_all)

    def test_idf(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = BM25Scorer(BM25Params(), stats)
        benchmark(scorer.idf, 500)

    @pytest.mark.parametrize("num_terms", [1, 3, 5, 10])
    def test_combine_scores(self, benchmark, num_terms: int) -> None:
        stats = _make_index_stats()
        scorer = BM25Scorer(BM25Params(), stats)
        scores = [scorer.score(5, 120, 1000) for _ in range(num_terms)]
        benchmark(scorer.combine_scores, scores)


# ---------------------------------------------------------------------------
# Bayesian BM25
# ---------------------------------------------------------------------------

class TestBayesianBM25:
    def test_score_single(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = BayesianBM25Scorer(BayesianBM25Params(), stats)
        benchmark(scorer.score, 5, 120, 1000)

    def test_score_batch(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = BayesianBM25Scorer(BayesianBM25Params(), stats)
        rng = np.random.default_rng(42)
        tfs = rng.integers(1, 20, size=1000)
        dls = rng.integers(50, 200, size=1000)
        df = 1000

        def score_all() -> float:
            total = 0.0
            for i in range(len(tfs)):
                total += scorer.score(int(tfs[i]), int(dls[i]), df)
            return total

        benchmark(score_all)

    @pytest.mark.parametrize("num_terms", [1, 3, 5, 10])
    def test_combine_scores(self, benchmark, num_terms: int) -> None:
        stats = _make_index_stats()
        scorer = BayesianBM25Scorer(BayesianBM25Params(), stats)
        scores = [scorer.score(5, 120, 1000) for _ in range(num_terms)]
        benchmark(scorer.combine_scores, scores)


# ---------------------------------------------------------------------------
# Vector Scoring
# ---------------------------------------------------------------------------

class TestVectorScoring:
    @pytest.mark.parametrize("dim", [64, 128, 256])
    def test_cosine_similarity(self, benchmark, dim: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        a = gen.query_vector(dim=dim)
        b = gen.query_vector(dim=dim)
        benchmark(VectorScorer.cosine_similarity, a, b)

    def test_similarity_to_probability(self, benchmark) -> None:
        benchmark(VectorScorer.similarity_to_probability, 0.85)

    def test_cosine_batch(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vecs = gen.vectors(dim=128)[:1000]
        query = gen.query_vector(dim=128)

        def score_all() -> float:
            total = 0.0
            for v in vecs:
                total += VectorScorer.cosine_similarity(query, v)
            return total

        benchmark(score_all)


# ---------------------------------------------------------------------------
# Log-Odds Fusion
# ---------------------------------------------------------------------------

class TestLogOddsFusion:
    @pytest.mark.parametrize("n_signals", [2, 3, 5, 10])
    def test_fuse(self, benchmark, n_signals: int) -> None:
        fusion = LogOddsFusion(confidence_alpha=0.5)
        rng = np.random.default_rng(42)
        probs = [float(rng.uniform(0.3, 0.9)) for _ in range(n_signals)]
        benchmark(fusion.fuse, probs)

    def test_fuse_batch(self, benchmark) -> None:
        """Fuse scores for many documents."""
        fusion = LogOddsFusion(confidence_alpha=0.5)
        rng = np.random.default_rng(42)
        n_docs = 10000
        n_signals = 3
        all_probs = [
            [float(rng.uniform(0.3, 0.9)) for _ in range(n_signals)]
            for _ in range(n_docs)
        ]

        def fuse_all() -> float:
            total = 0.0
            for probs in all_probs:
                total += fusion.fuse(probs)
            return total

        benchmark(fuse_all)

    @pytest.mark.parametrize("n_signals", [2, 3, 5])
    def test_fuse_weighted(self, benchmark, n_signals: int) -> None:
        fusion = LogOddsFusion(confidence_alpha=0.5)
        rng = np.random.default_rng(42)
        probs = [float(rng.uniform(0.3, 0.9)) for _ in range(n_signals)]
        raw_weights = [float(rng.uniform(0.5, 2.0)) for _ in range(n_signals)]
        total = sum(raw_weights)
        weights = [w / total for w in raw_weights]
        benchmark(fusion.fuse_weighted, probs, weights)
