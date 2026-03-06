from __future__ import annotations

import math


class LogOddsFusion:
    """Log-odds conjunction framework (Section 4, Paper 4).

    Resolves the conjunction shrinkage problem while preserving:
    - Scale neutrality (Theorem 4.1.2): P_i = p for all i => P_final = p
    - Sign preservation (Theorem 4.2.2): sgn(adjusted) = sgn(mean)
    - Irrelevance preservation (Theorem 4.5.1 iii): all P_i < 0.5 => P_final < 0.5
    - Relevance preservation (Theorem 4.5.1 iv): all P_i > 0.5 => P_final > 0.5

    Equivalent to normalized Logarithmic Opinion Pooling / Product of Experts
    (Theorem 4.1.2a).
    """

    EPSILON = 1e-10

    def __init__(self, confidence_alpha: float = 0.5) -> None:
        """
        Args:
            confidence_alpha: Confidence scaling exponent.
                alpha=0.5 yields the sqrt(n) scaling law (Theorem 4.4.1).
        """
        self.alpha = confidence_alpha

    @staticmethod
    def _logit(p: float) -> float:
        """Log-odds transform with clamping for numerical stability."""
        p = max(LogOddsFusion.EPSILON, min(1.0 - LogOddsFusion.EPSILON, p))
        return math.log(p / (1.0 - p))

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Numerically stable sigmoid function."""
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        else:
            z = math.exp(x)
            return z / (1.0 + z)

    def fuse(self, probabilities: list[float]) -> float:
        """Combine calibrated probability signals via log-odds conjunction.

        P_final = sigmoid( (1/n^{1-alpha}) * sum(logit(P_i)) )
        """
        n = len(probabilities)
        if n == 0:
            return 0.5
        if n == 1:
            return probabilities[0]

        logit_sum = sum(self._logit(p) for p in probabilities)
        weight = 1.0 / (n ** (1.0 - self.alpha))
        adjusted = logit_sum * weight

        return self._sigmoid(adjusted)

    def fuse_weighted(
        self, probabilities: list[float], weights: list[float]
    ) -> float:
        """Weighted log-odds conjunction (attention-like, Section 8, Paper 4).

        S = sum(w_i * logit(P_i)) where sum(w_i) = 1
        P_final = sigmoid(S * n^alpha)
        """
        n = len(probabilities)
        if n == 0:
            return 0.5

        logit_sum = sum(
            w * self._logit(p) for w, p in zip(weights, probabilities)
        )
        scaled = logit_sum * (n ** self.alpha)

        return self._sigmoid(scaled)
