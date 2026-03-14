#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
from bayesian_bm25 import BayesianProbabilityTransform


class ParameterLearner:
    """Online parameter learning for Bayesian BM25 (Section 8, Paper 3).

    Wraps BayesianProbabilityTransform.fit() and .update() to learn
    calibration parameters (alpha, beta, base_rate) from relevance
    judgments.
    """

    def __init__(
        self,
        alpha: float = 1.0,
        beta: float = 0.0,
        base_rate: float = 0.5,
    ) -> None:
        base = base_rate if base_rate != 0.5 else None
        self._transform = BayesianProbabilityTransform(
            alpha=alpha, beta=beta, base_rate=base
        )

    def fit(
        self,
        scores: list[float],
        labels: list[int],
        *,
        mode: str = "balanced",
        tfs: list[int] | None = None,
        doc_len_ratios: list[float] | None = None,
    ) -> dict[str, float]:
        """Batch-learn calibration parameters from scored documents.

        Returns the learned parameters as a dict.
        """
        s = np.array(scores)
        y = np.array(labels)
        kwargs: dict = {"mode": mode}
        if tfs is not None:
            kwargs["tfs"] = np.array(tfs)
        if doc_len_ratios is not None:
            kwargs["doc_len_ratios"] = np.array(doc_len_ratios)
        self._transform.fit(s, y, **kwargs)
        return self.params()

    def update(
        self,
        score: float,
        label: int,
        *,
        learning_rate: float = 0.01,
        tf: int | None = None,
        doc_len_ratio: float | None = None,
    ) -> None:
        """Online update with a single observation."""
        kwargs: dict = {"learning_rate": learning_rate}
        if tf is not None:
            kwargs["tf"] = float(tf)
        if doc_len_ratio is not None:
            kwargs["doc_len_ratio"] = doc_len_ratio
        self._transform.update(float(score), float(label), **kwargs)

    def params(self) -> dict[str, float]:
        """Return current learned parameters."""
        return {
            "alpha": float(self._transform.alpha),
            "beta": float(self._transform.beta),
            "base_rate": float(
                self._transform.base_rate
                if self._transform.base_rate is not None
                else 0.5
            ),
        }
