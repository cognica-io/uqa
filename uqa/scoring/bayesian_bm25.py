#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from bayesian_bm25 import BayesianProbabilityTransform, log_odds_conjunction

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

    Transforms BM25 scores into calibrated probabilities P(R=1|s) in [0,1]
    using bayesian-bm25 package's BayesianProbabilityTransform.

    Three-term posterior decomposition (Theorem 4.4.2):
        logit(P) = logit(L) + logit(b_r) + logit(p)

    Implemented as two successive Bayes updates (Remark 4.4.5)
    for computational efficiency (2 mul + 1 sub + 1 div overhead).
    """

    def __init__(self, params: BayesianBM25Params, index_stats: IndexStats) -> None:
        self.params = params
        self.bm25 = BM25Scorer(params.bm25, index_stats)
        base_rate = params.base_rate if params.base_rate != 0.5 else None
        self._transform = BayesianProbabilityTransform(
            alpha=params.alpha,
            beta=params.beta,
            base_rate=base_rate,
        )

    def score(self, term_freq: int, doc_length: int, doc_freq: int) -> float:
        """Full Bayesian BM25 posterior with three-term decomposition."""
        raw = self.bm25.score(term_freq, doc_length, doc_freq)
        avg_dl = self.bm25.stats.avg_doc_length
        doc_len_ratio = doc_length / avg_dl if avg_dl > 0 else 1.0
        return float(
            self._transform.score_to_probability(raw, term_freq, doc_len_ratio)
        )

    def combine_scores(self, scores: list[float]) -> float:
        """Combine per-term Bayesian probabilities via log-odds conjunction."""
        if not scores:
            return 0.5
        if len(scores) == 1:
            return scores[0]
        return float(log_odds_conjunction(np.array(scores), alpha=0.0))

    def upper_bound(self, doc_freq: int) -> float:
        """Theorem 6.1.2 (Paper 3): Safe WAND upper bound."""
        bm25_ub = self.bm25.upper_bound(doc_freq)
        return float(self._transform.wand_upper_bound(bm25_ub))
