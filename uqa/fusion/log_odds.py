#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from dataclasses import dataclass

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

    def __init__(
        self, confidence_alpha: float = 0.5, gating: str | None = None
    ) -> None:
        """
        Args:
            confidence_alpha: Confidence scaling exponent.
                alpha=0.5 yields the sqrt(n) scaling law (Theorem 4.4.1).
            gating: Gating mechanism for log-odds signals.
                "none" (default), "relu", or "swish".
        """
        self.alpha = confidence_alpha
        self.gating = gating

    def fuse(self, probabilities: list[float]) -> float:
        """Combine calibrated probability signals via log-odds conjunction."""
        n = len(probabilities)
        if n == 0:
            return 0.5
        if n == 1:
            return probabilities[0]
        gating = self.gating or "none"
        if n <= 4:
            return float(
                log_odds_conjunction(
                    np.asarray(probabilities, dtype=np.float64),
                    alpha=self.alpha,
                    gating=gating,
                )
            )
        return float(
            log_odds_conjunction(
                np.array(probabilities), alpha=self.alpha, gating=gating
            )
        )

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
                gating=self.gating or "none",
            )
        )


@dataclass(frozen=True, slots=True)
class SignalQuality:
    """Quality metrics for a single signal (Paper 4, Section 6).

    Used to compute per-signal confidence scaling.
    """

    coverage_ratio: float  # fraction of candidate docs returned
    score_variance: float  # variance of signal scores
    calibration_error: float  # mean absolute calibration error


class AdaptiveLogOddsFusion(LogOddsFusion):
    """Log-odds fusion with per-signal adaptive confidence scaling.

    Instead of a uniform alpha, each signal gets an alpha computed
    from its quality metrics: signals with higher coverage, lower
    variance, and lower calibration error get higher confidence.

    alpha_i = base_alpha * (coverage * (1 - cal_error)) / (1 + variance)
    """

    def __init__(
        self,
        base_alpha: float = 0.5,
        gating: str | None = None,
    ) -> None:
        super().__init__(confidence_alpha=base_alpha, gating=gating)
        self.base_alpha = base_alpha

    def compute_signal_alpha(self, quality: SignalQuality) -> float:
        """Compute per-signal confidence scaling from quality metrics."""
        coverage = max(0.0, min(1.0, quality.coverage_ratio))
        cal_error = max(0.0, min(1.0, quality.calibration_error))
        variance = max(0.0, quality.score_variance)

        alpha = self.base_alpha * (coverage * (1.0 - cal_error)) / (1.0 + variance)
        return max(0.01, min(1.0, alpha))

    def fuse_adaptive(
        self,
        probabilities: list[float],
        qualities: list[SignalQuality],
    ) -> float:
        """Fuse with per-signal adaptive weights.

        Computes raw alpha for each signal from its quality metrics,
        then normalizes to sum to 1.0 (required by log_odds_conjunction).
        """
        n = len(probabilities)
        if n == 0:
            return 0.5
        if n == 1:
            return probabilities[0]

        raw_weights = [self.compute_signal_alpha(q) for q in qualities]
        total = sum(raw_weights)
        normalized = [w / total for w in raw_weights]
        return self.fuse_weighted(probabilities, normalized)
