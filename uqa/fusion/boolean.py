#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math


class ProbabilisticBoolean:
    """Probabilistic Boolean operations for hybrid search (Section 5, Paper 3).

    AND: P = prod(p_i)               -- joint satisfaction
    OR:  P = 1 - prod(1 - p_i)       -- at least one
    NOT: P = 1 - p                    -- complement

    Computed in log-space for numerical stability (Theorem 5.3.1).
    """

    EPSILON = 1e-10

    @staticmethod
    def prob_and(probabilities: list[float]) -> float:
        """Theorem 5.1.1: P(AND) = exp(sum(ln(p_i)))"""
        log_sum = sum(
            math.log(max(p, ProbabilisticBoolean.EPSILON))
            for p in probabilities
        )
        return math.exp(log_sum)

    @staticmethod
    def prob_or(probabilities: list[float]) -> float:
        """Theorem 5.2.1: P(OR) = 1 - exp(sum(ln(1-p_i)))"""
        log_sum = sum(
            math.log(max(1.0 - p, ProbabilisticBoolean.EPSILON))
            for p in probabilities
        )
        return 1.0 - math.exp(log_sum)

    @staticmethod
    def prob_not(p: float) -> float:
        """Complement: P(NOT) = 1 - p"""
        return 1.0 - p
