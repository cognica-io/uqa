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
    from numpy.typing import NDArray


class VectorScorer:
    """Vector similarity to probability conversion (Definition 7.1.2, Paper 3).

    Delegates cosine-to-probability conversion to bayesian-bm25 package.

    For cosine distance d in [0, 2]:
        score_vector = 1 - d  (in [-1, 1])
        P_vector = (1 + score_vector) / 2  (in [0, 1])
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
        """Definition 7.1.2: P_vector = (1 + score) / 2"""
        return float(cosine_to_probability(cosine_sim))
