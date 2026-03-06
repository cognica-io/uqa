#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from uqa.scoring.bm25 import BM25Params, BM25Scorer

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


@dataclass(slots=True)
class BayesianBM25Params:
    """Parameters for Bayesian BM25 scoring."""

    bm25: BM25Params = field(default_factory=BM25Params)
    alpha: float = 1.0
    beta: float = 0.0
    base_rate: float = 0.5


class BayesianBM25Scorer:
    """Bayesian BM25 scorer (Section 4, Paper 3).

    Transforms BM25 scores into calibrated probabilities P(R=1|s) in [0,1].

    Three-term posterior decomposition (Theorem 4.4.2):
        logit(P) = logit(L) + logit(b_r) + logit(p)

    Implemented as two successive Bayes updates (Remark 4.4.5)
    for computational efficiency (2 mul + 1 sub + 1 div overhead).
    """

    def __init__(self, params: BayesianBM25Params, index_stats: IndexStats) -> None:
        self.params = params
        self.bm25 = BM25Scorer(params.bm25, index_stats)

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Numerically stable sigmoid function."""
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        else:
            z = math.exp(x)
            return z / (1.0 + z)

    def _composite_prior(self, term_freq: int, doc_length: int) -> float:
        """Composite prior P_prior(f, n) (Definition 4.2.3, Paper 3).

        P_tf(f)   = 0.2 + 0.7 * min(1, f/10)
        P_norm(n) = 0.3 + 0.6 * (1 - min(1, |n - 0.5| * 2))
        P_prior   = clamp(0.7 * P_tf + 0.3 * P_norm, 0.1, 0.9)
        """
        p_tf = 0.2 + 0.7 * min(1.0, term_freq / 10.0)

        avg_dl = self.bm25.stats.avg_doc_length
        norm = doc_length / avg_dl if avg_dl > 0 else 1.0
        p_norm = 0.3 + 0.6 * (1.0 - min(1.0, abs(norm - 0.5) * 2.0))

        prior = 0.7 * p_tf + 0.3 * p_norm
        return max(0.1, min(0.9, prior))

    @staticmethod
    def _bayes_update(likelihood: float, prior: float) -> float:
        """Single Bayes update: P = (L*p) / (L*p + (1-L)*(1-p))"""
        lp = likelihood * prior
        return lp / (lp + (1.0 - likelihood) * (1.0 - prior))

    def score(self, term_freq: int, doc_length: int, doc_freq: int) -> float:
        """Full Bayesian BM25 posterior with three-term decomposition."""
        # Step 1: BM25 raw score
        raw = self.bm25.score(term_freq, doc_length, doc_freq)

        # Step 2: Sigmoid likelihood L = sigma(alpha * (s - beta))
        likelihood = self._sigmoid(
            self.params.alpha * (raw - self.params.beta)
        )

        # Step 3: Composite prior
        prior = self._composite_prior(term_freq, doc_length)

        # Step 4: First Bayes update (likelihood + prior)
        p1 = self._bayes_update(likelihood, prior)

        # Step 5: Second Bayes update (base rate) -- Theorem 4.4.2
        if self.params.base_rate != 0.5:
            p1 = self._bayes_update(p1, self.params.base_rate)

        return p1

    def combine_scores(self, scores: list[float]) -> float:
        """Combine per-term Bayesian probabilities via naive Bayes (log-odds sum)."""
        if not scores:
            return 0.5
        if len(scores) == 1:
            return scores[0]
        total_logit = 0.0
        for p in scores:
            p = max(1e-10, min(1.0 - 1e-10, p))
            total_logit += math.log(p / (1.0 - p))
        return self._sigmoid(total_logit)

    def upper_bound(self, doc_freq: int) -> float:
        """Theorem 6.1.2 (Paper 3): Safe WAND upper bound.

        Uses max likelihood and max prior (p_max = 0.9).
        """
        bm25_ub = self.bm25.upper_bound(doc_freq)
        l_max = self._sigmoid(self.params.alpha * (bm25_ub - self.params.beta))
        p_max = 0.9
        return self._bayes_update(l_max, p_max)
