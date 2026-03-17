#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Two-component Gaussian mixture EM for f_R estimation (Section 5, Paper 5).

Models the top-K distance distribution as a mixture of a relevant
component (estimated) and a background component (fixed from index
statistics).  External relevance weights inform the E-step
initialisation, resolving the local-optima problem (Theorem 5.2.3).
"""

from __future__ import annotations

import math

import numpy as np


class DistanceGMM:
    """Two-component Gaussian mixture with EM (Algorithm 5.3.1).

    Parameters
    ----------
    distances : ndarray
        Observed distances for the top-K retrieved documents.
    weights : ndarray
        External relevance weights for informed initialisation.
    background_mu, background_sigma : float
        Fixed background component parameters from index statistics.
    max_iter : int
        Maximum EM iterations.
    tol : float
        Convergence tolerance on log-likelihood change.
    """

    def __init__(
        self,
        distances: np.ndarray,
        weights: np.ndarray,
        background_mu: float,
        background_sigma: float,
        max_iter: int = 50,
        tol: float = 1e-4,
    ) -> None:
        self._distances = np.asarray(distances, dtype=np.float64)
        self._weights = np.asarray(weights, dtype=np.float64)
        self._bg_mu = background_mu
        self._bg_sigma = max(background_sigma, 1e-10)
        self._max_iter = max_iter
        self._tol = tol

        # Fitted parameters (populated by fit()).
        self._mu_r: float = 0.0
        self._sigma_r: float = 1.0
        self._pi: float = 0.5
        self._fitted = False

        self.fit()

    # ------------------------------------------------------------------
    # EM algorithm
    # ------------------------------------------------------------------

    def fit(self) -> None:
        """Run EM with informed initialisation (Algorithm 5.3.1)."""
        d = self._distances
        k = len(d)
        if k == 0:
            self._fitted = True
            return

        # Informed initialisation: gamma_i^(0) = w_i.
        gamma = np.clip(self._weights.copy(), 1e-8, 1.0 - 1e-8)
        g_sum = np.sum(gamma)
        if g_sum < 1e-8:
            gamma[:] = 0.5
            g_sum = 0.5 * k

        # Initial M-step from informed responsibilities.
        self._pi = float(g_sum / k)
        self._mu_r = float(np.sum(gamma * d) / g_sum)
        var_r = float(np.sum(gamma * (d - self._mu_r) ** 2) / g_sum)
        self._sigma_r = max(math.sqrt(var_r), 1e-10)

        prev_ll = -math.inf
        for _ in range(self._max_iter):
            # E-step.
            log_r = _log_gauss(d, self._mu_r, self._sigma_r) + math.log(
                max(self._pi, 1e-300)
            )
            log_g = _log_gauss(d, self._bg_mu, self._bg_sigma) + math.log(
                max(1.0 - self._pi, 1e-300)
            )

            # Log-sum-exp for numerical stability.
            log_denom = np.logaddexp(log_r, log_g)
            gamma = np.exp(log_r - log_denom)

            # M-step (background component fixed, Remark 5.3.2).
            g_sum = float(np.sum(gamma))
            if g_sum < 1e-8:
                break
            self._pi = g_sum / k
            self._mu_r = float(np.sum(gamma * d) / g_sum)
            var_r = float(np.sum(gamma * (d - self._mu_r) ** 2) / g_sum)
            self._sigma_r = max(math.sqrt(var_r), 1e-10)

            # Log-likelihood for convergence check.
            ll = float(np.sum(log_denom))
            if abs(ll - prev_ll) < self._tol:
                break
            prev_ll = ll

        self._fitted = True

    # ------------------------------------------------------------------
    # Density evaluation
    # ------------------------------------------------------------------

    @property
    def mu_r(self) -> float:
        return self._mu_r

    @property
    def sigma_r(self) -> float:
        return self._sigma_r

    @property
    def mixing_coefficient(self) -> float:
        return self._pi

    def relevant_pdf(self, d: float) -> float:
        """Evaluate f_R(d) -- the estimated relevant-document density."""
        z = (d - self._mu_r) / self._sigma_r
        return math.exp(-0.5 * z * z) / (self._sigma_r * math.sqrt(2.0 * math.pi))

    def relevant_log_pdf(self, d: float) -> float:
        """Evaluate log f_R(d)."""
        z = (d - self._mu_r) / self._sigma_r
        return -0.5 * z * z - math.log(self._sigma_r) - 0.5 * math.log(2.0 * math.pi)

    def relevant_pdf_batch(self, distances: np.ndarray) -> np.ndarray:
        """Vectorised f_R(d)."""
        z = (distances - self._mu_r) / self._sigma_r
        return np.exp(-0.5 * z * z) / (self._sigma_r * math.sqrt(2.0 * math.pi))


def _log_gauss(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """Log of a Gaussian density (vectorised)."""
    z = (x - mu) / sigma
    return -0.5 * z * z - math.log(sigma) - 0.5 * math.log(2.0 * math.pi)
