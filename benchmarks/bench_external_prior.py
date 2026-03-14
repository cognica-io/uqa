#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for external prior scoring.

Covers ExternalPriorScorer with recency and authority priors.
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import IndexStats
from uqa.scoring.bayesian_bm25 import BayesianBM25Params
from uqa.scoring.external_prior import (
    ExternalPriorScorer,
    authority_prior,
    recency_prior,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_index_stats(total_docs: int = 10000) -> IndexStats:
    return IndexStats(
        total_docs=total_docs,
        avg_doc_length=100.0,
        _doc_freqs={("body", "term"): total_docs // 10},
    )


def _neutral_prior(doc_fields: dict) -> float:
    """A trivial prior that always returns 0.6."""
    return 0.6


# ---------------------------------------------------------------------------
# External Prior Scorer
# ---------------------------------------------------------------------------


class TestExternalPrior:
    def test_score_with_prior(self, benchmark) -> None:
        stats = _make_index_stats()
        scorer = ExternalPriorScorer(
            BayesianBM25Params(), stats, _neutral_prior
        )
        doc_fields = {"authority": "high"}
        benchmark(scorer.score_with_prior, 5, 120, 1000, doc_fields)

    @pytest.mark.parametrize("n", [100, 1000])
    def test_score_batch(self, benchmark, n: int) -> None:
        stats = _make_index_stats()
        scorer = ExternalPriorScorer(
            BayesianBM25Params(), stats, _neutral_prior
        )
        rng = np.random.default_rng(42)
        tfs = rng.integers(1, 20, size=n)
        dls = rng.integers(50, 200, size=n)
        df = 1000
        doc_fields = {"authority": "high"}

        def score_all() -> float:
            total = 0.0
            for i in range(n):
                total += scorer.score_with_prior(
                    int(tfs[i]), int(dls[i]), df, doc_fields
                )
            return total

        benchmark(score_all)

    def test_recency_prior_computation(self, benchmark) -> None:
        import datetime

        prior_fn = recency_prior("updated_at", decay_days=30.0)
        now = datetime.datetime.now(tz=datetime.UTC)
        doc_fields = {
            "updated_at": (now - datetime.timedelta(days=5)).isoformat()
        }
        benchmark(prior_fn, doc_fields)

    def test_authority_prior_computation(self, benchmark) -> None:
        prior_fn = authority_prior("authority")
        doc_fields = {"authority": "high"}
        benchmark(prior_fn, doc_fields)
