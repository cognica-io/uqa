#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Likelihood ratio calibration of vector similarity scores (Paper 5).

Transforms raw cosine similarities into calibrated relevance
probabilities by computing the log density ratio log(f_R(d) / f_G(d))
and combining it with a base-rate prior in log-odds space
(Theorem 3.1.1).

Two estimation strategies for f_R are supported:
    - "kde"  : Weighted kernel density estimation (Section 4.3)
    - "gmm"  : Two-component Gaussian mixture EM (Section 5)

The background distribution f_G is a parametric Gaussian fitted from
IVF intra-cell distances at train time (Section 6.2).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from uqa.scoring.background_distribution import BackgroundDistribution
from uqa.scoring.distance_gmm import DistanceGMM
from uqa.scoring.weighted_kde import WeightedKDE

_LOGIT_CLAMP = 20.0  # clamp log-odds to avoid overflow


class VectorCalibrator:
    """Bayesian calibration of vector similarity scores.

    Parameters
    ----------
    background : BackgroundDistribution
        Global distance density f_G estimated at index build time.
    estimation_method : str
        Local density estimation strategy: ``"kde"`` or ``"gmm"``.
    base_rate : float
        Prior probability of relevance P(R=1) before observing the
        distance.  Defaults to 0.5 (uninformative).
    """

    def __init__(
        self,
        background: BackgroundDistribution,
        estimation_method: str = "kde",
        base_rate: float = 0.5,
        bandwidth_scale: float = 1.0,
    ) -> None:
        if estimation_method not in ("kde", "gmm"):
            raise ValueError(
                f"estimation_method must be 'kde' or 'gmm', got {estimation_method!r}"
            )
        self._background = background
        self._method = estimation_method
        self._base_rate = base_rate
        self._bandwidth_scale = bandwidth_scale

    @property
    def background(self) -> BackgroundDistribution:
        return self._background

    @property
    def estimation_method(self) -> str:
        return self._method

    @property
    def base_rate(self) -> float:
        return self._base_rate

    # ------------------------------------------------------------------
    # Core calibration
    # ------------------------------------------------------------------

    def calibrate(
        self,
        distances: np.ndarray,
        weights: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calibrate a batch of distances to relevance probabilities.

        Parameters
        ----------
        distances : ndarray
            Cosine distances (1 - similarity) for top-K results.
        weights : ndarray or None
            External relevance weights (BM25 probabilities or fallback
            weights).  If ``None``, uniform weights are used.

        Returns
        -------
        ndarray
            Calibrated probabilities in (0, 1) for each input distance.
        """
        distances = np.asarray(distances, dtype=np.float64)
        n = len(distances)
        if n == 0:
            return np.empty(0, dtype=np.float64)

        if weights is None:
            weights = np.ones(n, dtype=np.float64)
        else:
            weights = np.asarray(weights, dtype=np.float64)

        # Estimate f_R.
        if self._method == "gmm":
            f_r_values = self._estimate_gmm(distances, weights)
        else:
            f_r_values = self._estimate_kde(distances, weights)

        # Evaluate f_G.
        f_g_values = self._background.pdf_batch(distances)

        # Compute log likelihood ratio (vector evidence).
        log_lr = np.log(np.maximum(f_r_values, 1e-300)) - np.log(
            np.maximum(f_g_values, 1e-300)
        )

        # Add base-rate prior in log-odds space.
        logit_prior = _logit(self._base_rate)
        logit_posterior = np.clip(log_lr + logit_prior, -_LOGIT_CLAMP, _LOGIT_CLAMP)

        return _sigmoid(logit_posterior)

    def calibrate_single(
        self,
        distance: float,
        all_distances: np.ndarray,
        weights: np.ndarray,
    ) -> float:
        """Calibrate a single distance given the full top-K context.

        The context (all_distances, weights) is needed to estimate f_R.
        The single *distance* is then evaluated against both f_R and f_G.
        """
        probs = self.calibrate(all_distances, weights)
        # Find the entry matching *distance* (float comparison).
        idx = np.argmin(np.abs(all_distances - distance))
        return float(probs[idx])

    # ------------------------------------------------------------------
    # Local distribution estimation
    # ------------------------------------------------------------------

    def _estimate_kde(self, distances: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Weighted KDE estimation of f_R (Section 4.3)."""
        kde = WeightedKDE(distances, weights)
        if self._bandwidth_scale != 1.0:
            scaled_h = kde.bandwidth * self._bandwidth_scale
            kde = WeightedKDE(distances, weights, bandwidth=scaled_h)
        return kde.pdf_batch(distances)

    def _estimate_gmm(self, distances: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """GMM-EM estimation of f_R (Section 5)."""
        gmm = DistanceGMM(
            distances,
            weights,
            background_mu=self._background.mu,
            background_sigma=self._background.sigma,
        )
        return gmm.relevant_pdf_batch(distances)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "background": self._background.to_dict(),
            "estimation_method": self._method,
            "base_rate": self._base_rate,
            "bandwidth_scale": self._bandwidth_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorCalibrator:
        bg = BackgroundDistribution.from_dict(data["background"])
        return cls(
            background=bg,
            estimation_method=data.get("estimation_method", "kde"),
            base_rate=data.get("base_rate", 0.5),
            bandwidth_scale=data.get("bandwidth_scale", 1.0),
        )


# ------------------------------------------------------------------
# Numerical primitives
# ------------------------------------------------------------------


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-x)),
        np.exp(x) / (1.0 + np.exp(x)),
    )


def _logit(p: float) -> float:
    """Log-odds: log(p / (1-p))."""
    p = max(min(p, 1.0 - 1e-15), 1e-15)
    return math.log(p / (1.0 - p))
