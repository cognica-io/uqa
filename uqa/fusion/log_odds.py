#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
from bayesian_bm25 import log_odds_conjunction


class LogOddsFusion:
    """Log-odds conjunction framework (Section 4, Paper 4).

    Delegates to bayesian-bm25 package's log_odds_conjunction.

    Resolves the conjunction shrinkage problem while preserving:
    - Scale neutrality (Theorem 4.1.2): P_i = p for all i => P_final = p
    - Sign preservation (Theorem 4.2.2): sgn(adjusted) = sgn(mean)
    - Irrelevance preservation (Theorem 4.5.1 iii): all P_i < 0.5 => P_final < 0.5
    - Relevance preservation (Theorem 4.5.1 iv): all P_i > 0.5 => P_final > 0.5
    """

    def __init__(self, confidence_alpha: float = 0.5) -> None:
        """
        Args:
            confidence_alpha: Confidence scaling exponent.
                alpha=0.5 yields the sqrt(n) scaling law (Theorem 4.4.1).
        """
        self.alpha = confidence_alpha

    def fuse(self, probabilities: list[float]) -> float:
        """Combine calibrated probability signals via log-odds conjunction."""
        n = len(probabilities)
        if n == 0:
            return 0.5
        if n == 1:
            return probabilities[0]
        if n <= 4:
            return float(
                log_odds_conjunction(
                    np.asarray(probabilities, dtype=np.float64), alpha=self.alpha
                )
            )
        return float(log_odds_conjunction(np.array(probabilities), alpha=self.alpha))

    def fuse_weighted(self, probabilities: list[float], weights: list[float]) -> float:
        """Weighted log-odds conjunction (attention-like, Section 8, Paper 4)."""
        n = len(probabilities)
        if n == 0:
            return 0.5
        return float(
            log_odds_conjunction(
                np.array(probabilities),
                alpha=self.alpha,
                weights=np.array(weights),
            )
        )
