#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""BM25-independent fallback weight estimation (Section 4.6, Paper 5).

Provides importance weights for local distribution estimation when no
external relevance signal (e.g., BM25) is available.  Three strategies
are offered, with a graceful degradation hierarchy (Remark 4.6.4):

    cross-modal > index density prior > distance gap > naive unweighted
"""

from __future__ import annotations

import math

import numpy as np


class VectorFallbackEstimator:
    """Fallback weight estimation for pure vector environments."""

    @staticmethod
    def distance_gap_weights(distances: np.ndarray) -> np.ndarray:
        """Strategy 4.6.1 -- partition top-K by the largest distance gap.

        Documents before the gap are treated as relevant (weight 1),
        documents after as background (weight 0).

        Parameters
        ----------
        distances : ndarray
            Sorted or unsorted cosine distances (1 - similarity).

        Returns
        -------
        ndarray
            Binary weights aligned to the *sorted* input order.
        """
        d = np.sort(distances)
        n = len(d)
        if n < 2:
            return np.ones(n, dtype=np.float64)

        gaps = np.diff(d)
        split = int(np.argmax(gaps))

        weights = np.zeros(n, dtype=np.float64)
        weights[: split + 1] = 1.0
        return weights

    @staticmethod
    def index_density_weights(
        cell_populations: dict[int, int],
        centroid_ids: np.ndarray,
        total_vectors: int,
        num_cells: int,
        gamma: float = 1.0,
    ) -> np.ndarray:
        """Strategy 4.6.2 -- IVF cell population as relevance prior.

        w_i = sigmoid(gamma * (avg_pop / n_j - 1))

        Documents in sparse cells receive higher weights because vector
        proximity is more discriminative there (analogous to IDF).

        Parameters
        ----------
        cell_populations : dict
            Mapping centroid_id -> population count.
        centroid_ids : ndarray
            Centroid assignment for each top-K result.
        total_vectors : int
            Total vectors in the index (N).
        num_cells : int
            Number of IVF cells (C).
        gamma : float
            Sensitivity parameter (default 1.0).

        Returns
        -------
        ndarray
            Weights in (0, 1) for each document.
        """
        avg_pop = total_vectors / max(num_cells, 1)
        weights = np.empty(len(centroid_ids), dtype=np.float64)
        for i, cid in enumerate(centroid_ids):
            n_j = cell_populations.get(int(cid), 1)
            x = gamma * (avg_pop / max(n_j, 1) - 1.0)
            weights[i] = 1.0 / (1.0 + math.exp(-x))
        return weights

    @staticmethod
    def cross_model_weights(
        similarities_model_b: np.ndarray,
    ) -> np.ndarray:
        """Strategy 4.6.3 -- use scores from a second embedding model.

        The similarity from model B is converted to a probability via
        linear rescaling and used as the importance weight for
        calibrating model A.

        Parameters
        ----------
        similarities_model_b : ndarray
            Cosine similarities from the second embedding model,
            in [-1, 1].

        Returns
        -------
        ndarray
            Weights in [0, 1].
        """
        return np.clip((similarities_model_b + 1.0) / 2.0, 0.0, 1.0)
