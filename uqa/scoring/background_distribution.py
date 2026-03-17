#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Global background distance distribution f_G (Definition 4.5.1, Paper 5).

The background distribution models the density of query-document
distances for a *typical* (random) query.  It is estimated via KDE
over top-K distances from random queries sampled at IVF train time.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

_LOG_SQRT_2PI = 0.5 * math.log(2.0 * math.pi)


class BackgroundDistribution:
    """KDE-based background distance density f_G (Definition 4.5.1).

    Built from a sample of distances from random queries to their
    nearest corpus documents.  Evaluated as a standard (unweighted)
    Gaussian KDE.

    Parameters
    ----------
    samples : ndarray
        Raw distance samples from random queries' top-K results.
    bandwidth : float or None
        KDE bandwidth.  If ``None``, Silverman's rule is used.
    """

    def __init__(
        self,
        samples: np.ndarray,
        bandwidth: float | None = None,
    ) -> None:
        self._samples = np.asarray(samples, dtype=np.float64)
        self.mu = float(np.mean(self._samples)) if len(self._samples) else 0.0
        self.sigma = (
            max(float(np.std(self._samples)), 1e-10) if len(self._samples) else 1.0
        )
        if bandwidth is not None:
            self._h = bandwidth
        else:
            self._h = self._silverman_bandwidth()
        self._h = max(self._h, 1e-10)

    def _silverman_bandwidth(self) -> float:
        n = len(self._samples)
        if n < 2:
            return 1.0
        return 1.06 * self.sigma * n ** (-0.2)

    def pdf(self, d: float) -> float:
        """Evaluate f_G(d) via KDE."""
        if len(self._samples) == 0:
            return 1e-10
        z = (d - self._samples) / self._h
        return float(
            np.mean(np.exp(-0.5 * z * z)) / (self._h * math.sqrt(2.0 * math.pi))
        )

    def log_pdf(self, d: float) -> float:
        return math.log(max(self.pdf(d), 1e-300))

    def pdf_batch(self, distances: np.ndarray) -> np.ndarray:
        """Vectorised f_G(d) via KDE."""
        distances = np.asarray(distances, dtype=np.float64)
        if len(self._samples) == 0:
            return np.full_like(distances, 1e-10)
        # (len(distances), len(samples))
        diff = distances[:, np.newaxis] - self._samples[np.newaxis, :]
        z = diff / self._h
        kernels = np.exp(-0.5 * z * z)
        return np.mean(kernels, axis=1) / (self._h * math.sqrt(2.0 * math.pi))

    def log_pdf_batch(self, distances: np.ndarray) -> np.ndarray:
        return np.log(np.maximum(self.pdf_batch(distances), 1e-300))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "mu": self.mu,
            "sigma": self.sigma,
            "samples": self._samples.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackgroundDistribution:
        samples = np.array(data.get("samples", []), dtype=np.float64)
        if len(samples) == 0:
            # Backward compat: construct from mu/sigma with synthetic samples.
            mu = float(data["mu"])
            sigma = float(data["sigma"])
            rng = np.random.RandomState(0)
            samples = rng.normal(mu, sigma, size=1000)
        return cls(samples=samples)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_ivf_stats(
        cls, mu: float, sigma: float, samples: np.ndarray | None = None
    ) -> BackgroundDistribution:
        """Create from IVF background statistics."""
        if samples is not None and len(samples) > 0:
            return cls(samples=samples)
        # Fallback: generate synthetic samples from Gaussian params.
        rng = np.random.RandomState(0)
        return cls(samples=rng.normal(mu, sigma, size=1000))

    @classmethod
    def from_distance_sample(cls, distances: np.ndarray) -> BackgroundDistribution:
        """Estimate from a sample of distances."""
        return cls(samples=distances)
