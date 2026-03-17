#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Importance-weighted kernel density estimation for f_R (Section 4.3, Paper 5).

Estimates the local distance distribution among relevant documents using
external relevance weights that break the circularity of unsupervised
density estimation (Theorem 4.3.2).
"""

from __future__ import annotations

import math

import numpy as np


class WeightedKDE:
    """Weighted Gaussian kernel density estimator (Definition 4.3.1).

    Parameters
    ----------
    distances : ndarray
        Observed distances for the top-K retrieved documents.
    weights : ndarray
        External relevance weights w_i in [0, 1] for each document.
    bandwidth : float or None
        Kernel bandwidth *h*.  If ``None``, Silverman's rule adapted
        for weighted samples is used (Definition 4.4.1).
    """

    def __init__(
        self,
        distances: np.ndarray,
        weights: np.ndarray,
        bandwidth: float | None = None,
    ) -> None:
        self._distances = np.asarray(distances, dtype=np.float64)
        self._weights = np.asarray(weights, dtype=np.float64)

        # Clamp weights to [0, 1] and drop zero-weight entries.
        self._weights = np.clip(self._weights, 0.0, 1.0)
        mask = self._weights > 0
        self._distances = self._distances[mask]
        self._weights = self._weights[mask]

        self._weight_sum = float(np.sum(self._weights))
        if self._weight_sum == 0:
            self._weight_sum = 1.0

        if bandwidth is not None:
            self._h = bandwidth
        else:
            self._h = self._silverman_bandwidth()
        self._h = max(self._h, 1e-10)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def pdf(self, d: float) -> float:
        """Evaluate the weighted KDE at distance *d*."""
        if len(self._distances) == 0:
            return 0.0
        z = (d - self._distances) / self._h
        kernels = np.exp(-0.5 * z * z)
        return float(
            np.sum(self._weights * kernels)
            / (self._weight_sum * self._h * math.sqrt(2.0 * math.pi))
        )

    def log_pdf(self, d: float) -> float:
        """Evaluate log f_R(d) with numerical stability."""
        val = self.pdf(d)
        return math.log(max(val, 1e-300))

    def pdf_batch(self, distances: np.ndarray) -> np.ndarray:
        """Vectorised KDE evaluation."""
        distances = np.asarray(distances, dtype=np.float64)
        if len(self._distances) == 0:
            return np.zeros_like(distances)
        # (len(distances), len(self._distances))
        diff = distances[:, np.newaxis] - self._distances[np.newaxis, :]
        z = diff / self._h
        kernels = np.exp(-0.5 * z * z)
        weighted = kernels * self._weights[np.newaxis, :]
        return np.sum(weighted, axis=1) / (
            self._weight_sum * self._h * math.sqrt(2.0 * math.pi)
        )

    @property
    def bandwidth(self) -> float:
        return self._h

    # ------------------------------------------------------------------
    # Bandwidth selection
    # ------------------------------------------------------------------

    def _silverman_bandwidth(self) -> float:
        """Silverman's rule for weighted KDE (Definition 4.4.1).

        h = 1.06 * sigma_w * K_eff^{-1/5}

        where sigma_w is the weighted standard deviation and K_eff is
        the effective sample size accounting for weight variation.
        """
        if len(self._distances) < 2:
            return 1.0

        w = self._weights
        d = self._distances

        w_sum = np.sum(w)
        if w_sum == 0:
            return 1.0

        # Weighted mean and standard deviation.
        mu_w = np.sum(w * d) / w_sum
        var_w = np.sum(w * (d - mu_w) ** 2) / w_sum
        sigma_w = max(math.sqrt(var_w), 1e-10)

        # Effective sample size: K_eff = (sum w_i)^2 / sum(w_i^2).
        k_eff = w_sum**2 / max(np.sum(w**2), 1e-10)
        k_eff = max(k_eff, 1.0)

        return 1.06 * sigma_w * k_eff ** (-0.2)
