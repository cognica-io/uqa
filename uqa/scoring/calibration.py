#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
from bayesian_bm25 import (
    brier_score,
    calibration_report,
    expected_calibration_error,
    reliability_diagram,
)


class CalibrationMetrics:
    """Calibration diagnostics for Bayesian BM25 scoring (Section 11.3, Paper 3).

    Wraps bayesian_bm25 calibration functions into a unified API for
    evaluating how well predicted relevance probabilities match actual
    relevance rates.
    """

    @staticmethod
    def ece(
        probabilities: list[float], labels: list[int], n_bins: int = 10
    ) -> float:
        """Expected Calibration Error.

        Measures how well predicted probabilities match actual relevance
        rates.  Lower is better.  Perfect calibration = 0.
        """
        return float(
            expected_calibration_error(
                np.array(probabilities), np.array(labels), n_bins=n_bins
            )
        )

    @staticmethod
    def brier(probabilities: list[float], labels: list[int]) -> float:
        """Brier score: mean squared error between probabilities and labels.

        Decomposes into calibration + discrimination.  Lower is better.
        """
        return float(brier_score(np.array(probabilities), np.array(labels)))

    @staticmethod
    def report(
        probabilities: list[float], labels: list[int], n_bins: int = 10
    ) -> dict:
        """Full calibration diagnostic report.

        Returns a dict with keys: ece, brier, bin_data, and any
        additional diagnostics from the bayesian_bm25 package.
        """
        probs = np.array(probabilities)
        lbls = np.array(labels)
        raw = calibration_report(probs, lbls, n_bins=n_bins)
        # calibration_report returns a CalibrationReport object; convert to dict.
        if hasattr(raw, "__dict__"):
            return dict(raw.__dict__)
        if isinstance(raw, dict):
            return raw
        # Fallback: build report manually
        return {
            "ece": float(
                expected_calibration_error(probs, lbls, n_bins=n_bins)
            ),
            "brier": float(brier_score(probs, lbls)),
        }

    @staticmethod
    def reliability_diagram(
        probabilities: list[float], labels: list[int], n_bins: int = 10
    ) -> list[tuple[float, float, int]]:
        """Compute reliability diagram data: (avg_predicted, avg_actual, count) per bin.

        Perfect calibration means avg_predicted == avg_actual for every bin.
        """
        probs = np.array(probabilities)
        lbls = np.array(labels)
        result = reliability_diagram(probs, lbls, n_bins=n_bins)
        # result is a list of tuples (avg_predicted, avg_actual, count)
        return [(float(p), float(a), int(c)) for p, a, c in result]
