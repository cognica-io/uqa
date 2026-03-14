#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from bayesian_bm25 import AttentionLogOddsWeights, log_odds_conjunction

if TYPE_CHECKING:
    from numpy.typing import NDArray


class AttentionFusion:
    """Attention-based multi-signal fusion (Section 8, Paper 4).

    Uses query features to compute per-signal attention weights,
    then fuses via weighted log-odds conjunction.
    """

    def __init__(
        self,
        n_signals: int,
        n_query_features: int = 6,
        alpha: float = 0.5,
    ) -> None:
        self._attn = AttentionLogOddsWeights(
            n_signals=n_signals,
            n_query_features=n_query_features,
            alpha=alpha,
        )

    @property
    def n_signals(self) -> int:
        return self._attn.n_signals

    @property
    def n_query_features(self) -> int:
        return self._attn.n_query_features

    def fuse(self, probabilities: list[float], query_features: NDArray) -> float:
        """Fuse signals using attention-weighted log-odds conjunction."""
        probs = np.array(probabilities)
        # Compute attention weights: W @ query_features
        weights = self._attn.weights_matrix @ query_features
        # Softmax normalization
        weights = weights - np.max(weights)
        exp_w = np.exp(weights)
        weights = exp_w / np.sum(exp_w)
        return float(
            log_odds_conjunction(probs, alpha=self._attn.alpha, weights=weights)
        )

    def fit(
        self,
        probs: NDArray,
        labels: NDArray,
        query_features: NDArray,
        **kwargs: Any,
    ) -> None:
        """Batch train attention weights."""
        self._attn.fit(probs, labels, query_features, **kwargs)

    def update(
        self,
        probs: NDArray,
        label: float,
        query_features: NDArray,
        **kwargs: Any,
    ) -> None:
        """Online update of attention weights."""
        self._attn.update(probs, label, query_features, **kwargs)

    def state_dict(self) -> dict:
        """Export learned state."""
        return {
            "weights_matrix": self._attn.weights_matrix.tolist(),
            "alpha": float(self._attn.alpha),
            "n_signals": self._attn.n_signals,
            "n_query_features": self._attn.n_query_features,
        }

    def load_state_dict(self, state: dict) -> None:
        """Restore learned state."""
        self._attn = AttentionLogOddsWeights(
            n_signals=state["n_signals"],
            n_query_features=state["n_query_features"],
            alpha=state["alpha"],
        )
        self._attn.weights_matrix[:] = np.array(state["weights_matrix"])
