#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
from bayesian_bm25 import prob_and as _prob_and
from bayesian_bm25 import prob_not as _prob_not
from bayesian_bm25 import prob_or as _prob_or


class ProbabilisticBoolean:
    """Probabilistic Boolean operations for hybrid search (Section 5, Paper 3).

    Delegates to bayesian-bm25 package's prob_and, prob_or, prob_not.

    AND: P = prod(p_i)               -- joint satisfaction
    OR:  P = 1 - prod(1 - p_i)       -- at least one
    NOT: P = 1 - p                    -- complement

    Computed in log-space for numerical stability (Theorem 5.3.1).
    """

    @staticmethod
    def prob_and(probabilities: list[float]) -> float:
        """Theorem 5.1.1: P(AND) = exp(sum(ln(p_i)))"""
        return float(_prob_and(np.array(probabilities)))

    @staticmethod
    def prob_or(probabilities: list[float]) -> float:
        """Theorem 5.2.1: P(OR) = 1 - exp(sum(ln(1-p_i)))"""
        return float(_prob_or(np.array(probabilities)))

    @staticmethod
    def prob_not(p: float) -> float:
        """Complement: P(NOT) = 1 - p"""
        return float(_prob_not(p))
