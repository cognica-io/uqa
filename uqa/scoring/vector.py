#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from bayesian_bm25 import cosine_to_probability

if TYPE_CHECKING:
    from bayesian_bm25.vector_probability import VectorProbabilityTransform
    from numpy.typing import NDArray


class VectorScorer:
    """Vector similarity to probability conversion.

    Two modes:
        - Uncalibrated (Definition 7.1.2, Paper 3):
              P_vector = (1 + score) / 2
        - Calibrated (Theorem 3.1.1, Paper 5):
              P_vector via log(f_R(d) / f_G(d)) + logit(base_rate)
    """

    @staticmethod
    def cosine_similarity(a: NDArray, b: NDArray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = float(np.dot(a, b))
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def similarity_to_probability(cosine_sim: float) -> float:
        """Definition 7.1.2: P_vector = (1 + score) / 2 (uncalibrated)."""
        return float(cosine_to_probability(cosine_sim))

    @staticmethod
    def calibrated_probabilities(
        similarities: NDArray,
        calibrator: VectorProbabilityTransform,
        weights: NDArray | None = None,
    ) -> NDArray:
        """Likelihood ratio calibration (Theorem 3.1.1, Paper 5).

        Parameters
        ----------
        similarities : ndarray
            Cosine similarities in [-1, 1] for the top-K results.
        calibrator : VectorProbabilityTransform
            Pre-configured calibrator with background distribution.
        weights : ndarray or None
            External relevance weights.  If ``None``, uniform weights.

        Returns
        -------
        ndarray
            Calibrated probabilities in (0, 1).
        """
        distances = 1.0 - np.asarray(similarities, dtype=np.float64)
        return np.asarray(
            calibrator.calibrate(distances, weights=weights),
            dtype=np.float64,
        )
