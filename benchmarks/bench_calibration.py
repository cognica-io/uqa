#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for calibration metrics and parameter learning.

Covers ECE, Brier score, reliability diagram, and ParameterLearner.
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.scoring.calibration import CalibrationMetrics
from uqa.scoring.parameter_learner import ParameterLearner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_predictions(
    n: int, seed: int = 42
) -> tuple[list[float], list[int]]:
    """Generate random probabilities and binary labels."""
    rng = np.random.default_rng(seed)
    probabilities = [float(rng.uniform(0.0, 1.0)) for _ in range(n)]
    labels = [int(rng.integers(0, 2)) for _ in range(n)]
    return probabilities, labels


def _make_scores_and_labels(
    n: int, seed: int = 42
) -> tuple[list[float], list[int]]:
    """Generate BM25-like scores and binary labels for parameter learning."""
    rng = np.random.default_rng(seed)
    scores = [float(rng.uniform(0.0, 20.0)) for _ in range(n)]
    labels = [int(rng.integers(0, 2)) for _ in range(n)]
    return scores, labels


# ---------------------------------------------------------------------------
# Calibration Metrics
# ---------------------------------------------------------------------------


class TestCalibrationMetrics:
    @pytest.mark.parametrize("n", [100, 1000, 10000])
    def test_ece(self, benchmark, n: int) -> None:
        probs, labels = _make_predictions(n)
        result = benchmark(CalibrationMetrics.ece, probs, labels)
        assert 0.0 <= result <= 1.0

    @pytest.mark.parametrize("n", [100, 1000, 10000])
    def test_brier(self, benchmark, n: int) -> None:
        probs, labels = _make_predictions(n)
        result = benchmark(CalibrationMetrics.brier, probs, labels)
        assert 0.0 <= result <= 1.0

    @pytest.mark.parametrize("n", [100, 1000])
    def test_reliability_diagram(self, benchmark, n: int) -> None:
        probs, labels = _make_predictions(n)
        result = benchmark(CalibrationMetrics.reliability_diagram, probs, labels)
        assert isinstance(result, list)

    @pytest.mark.parametrize("n", [100, 1000])
    def test_report(self, benchmark, n: int) -> None:
        probs, labels = _make_predictions(n)
        result = benchmark(CalibrationMetrics.report, probs, labels)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Parameter Learner
# ---------------------------------------------------------------------------


class TestParameterLearner:
    @pytest.mark.parametrize("n", [100, 1000])
    def test_fit(self, benchmark, n: int) -> None:
        scores, labels = _make_scores_and_labels(n)
        learner = ParameterLearner()
        result = benchmark(learner.fit, scores, labels)
        assert "alpha" in result

    def test_update_single(self, benchmark) -> None:
        learner = ParameterLearner()
        benchmark(learner.update, 5.0, 1, learning_rate=0.01)

    @pytest.mark.parametrize("n", [100, 1000])
    def test_update_stream(self, benchmark, n: int) -> None:
        scores, labels = _make_scores_and_labels(n)
        learner = ParameterLearner()

        def update_stream() -> None:
            for i in range(n):
                learner.update(scores[i], labels[i], learning_rate=0.01)

        benchmark(update_stream)
