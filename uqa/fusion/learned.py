#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from bayesian_bm25 import LearnableLogOddsWeights, log_odds_conjunction

if TYPE_CHECKING:
    from numpy.typing import NDArray


class LearnedFusion:
    """Learnable signal fusion without query features (Section 8, Paper 4).

    Uses learned per-signal weights (no query features needed) to fuse
    via weighted log-odds conjunction.
    """

    def __init__(self, n_signals: int, alpha: float = 0.5) -> None:
        self._learnable = LearnableLogOddsWeights(n_signals=n_signals, alpha=alpha)

    @property
    def n_signals(self) -> int:
        return self._learnable.n_signals

    def fuse(self, probabilities: list[float]) -> float:
        """Fuse signals using learned weights."""
        probs = np.array(probabilities)
        weights = self._learnable.weights
        return float(
            log_odds_conjunction(probs, alpha=self._learnable.alpha, weights=weights)
        )

    def fit(self, probs: NDArray, labels: NDArray, **kwargs: Any) -> None:
        """Batch train signal weights."""
        self._learnable.fit(probs, labels, **kwargs)

    def update(self, probs: NDArray, label: float, **kwargs: Any) -> None:
        """Online update of signal weights."""
        self._learnable.update(probs, label, **kwargs)

    def state_dict(self) -> dict:
        """Export learned state."""
        return {
            "weights": self._learnable.weights.tolist(),
            "alpha": float(self._learnable.alpha),
            "n_signals": self._learnable.n_signals,
        }

    def load_state_dict(self, state: dict) -> None:
        """Restore learned state."""
        self._learnable = LearnableLogOddsWeights(
            n_signals=state["n_signals"],
            alpha=state["alpha"],
        )
        self._learnable.weights[:] = np.array(state["weights"])
