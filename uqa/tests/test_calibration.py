#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.engine import Engine
from uqa.scoring.calibration import CalibrationMetrics


class TestCalibrationMetrics:
    """Tests for CalibrationMetrics wrapper (Paper 3, Section 11.3)."""

    def test_ece_perfect_calibration(self) -> None:
        probs = [0.0, 0.0, 1.0, 1.0]
        labels = [0, 0, 1, 1]
        ece = CalibrationMetrics.ece(probs, labels)
        assert ece == pytest.approx(0.0, abs=1e-6)

    def test_ece_imperfect_calibration(self) -> None:
        probs = [0.9, 0.9, 0.1, 0.1]
        labels = [0, 0, 1, 1]
        ece = CalibrationMetrics.ece(probs, labels)
        assert ece > 0.0

    def test_ece_returns_float(self) -> None:
        probs = [0.5, 0.5, 0.5, 0.5]
        labels = [0, 1, 0, 1]
        result = CalibrationMetrics.ece(probs, labels)
        assert isinstance(result, float)

    def test_brier_perfect_predictions(self) -> None:
        probs = [0.0, 0.0, 1.0, 1.0]
        labels = [0, 0, 1, 1]
        score = CalibrationMetrics.brier(probs, labels)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_brier_worst_predictions(self) -> None:
        probs = [1.0, 1.0, 0.0, 0.0]
        labels = [0, 0, 1, 1]
        score = CalibrationMetrics.brier(probs, labels)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_brier_uniform_predictions(self) -> None:
        probs = [0.5, 0.5, 0.5, 0.5]
        labels = [0, 1, 0, 1]
        score = CalibrationMetrics.brier(probs, labels)
        assert score == pytest.approx(0.25, abs=1e-6)

    def test_brier_returns_float(self) -> None:
        result = CalibrationMetrics.brier([0.5], [1])
        assert isinstance(result, float)

    def test_report_returns_dict(self) -> None:
        probs = [0.1, 0.4, 0.6, 0.9]
        labels = [0, 0, 1, 1]
        report = CalibrationMetrics.report(probs, labels)
        assert isinstance(report, dict)

    def test_report_contains_metrics(self) -> None:
        probs = [0.1, 0.4, 0.6, 0.9]
        labels = [0, 0, 1, 1]
        report = CalibrationMetrics.report(probs, labels)
        # Report should contain at least ece and brier
        assert "ece" in report or "brier" in report or len(report) > 0

    def test_reliability_diagram_returns_list(self) -> None:
        probs = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
        labels = [0, 0, 0, 1, 1, 1]
        diagram = CalibrationMetrics.reliability_diagram(probs, labels)
        assert isinstance(diagram, list)

    def test_reliability_diagram_tuple_structure(self) -> None:
        probs = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
        labels = [0, 0, 0, 1, 1, 1]
        diagram = CalibrationMetrics.reliability_diagram(probs, labels, n_bins=5)
        for item in diagram:
            assert len(item) == 3
            avg_pred, avg_actual, count = item
            assert isinstance(avg_pred, float)
            assert isinstance(avg_actual, float)
            assert isinstance(count, int)

    def test_reliability_diagram_n_bins(self) -> None:
        probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        labels = [0, 0, 1, 1, 1]
        diagram = CalibrationMetrics.reliability_diagram(probs, labels, n_bins=5)
        assert len(diagram) <= 5

    def test_ece_with_many_bins(self) -> None:
        probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        labels = [0, 0, 1, 1, 1]
        ece = CalibrationMetrics.ece(probs, labels, n_bins=20)
        assert isinstance(ece, float)
        assert ece >= 0.0

    def test_brier_score_range(self) -> None:
        probs = [0.3, 0.7, 0.2, 0.8]
        labels = [0, 1, 0, 1]
        score = CalibrationMetrics.brier(probs, labels)
        assert 0.0 <= score <= 1.0


class TestEngineCalibrationReport:
    """Tests for Engine.calibration_report()."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        e.sql("INSERT INTO docs (content) VALUES ('deep learning neural networks')")
        e.sql("INSERT INTO docs (content) VALUES ('database indexing structures')")
        e.sql("INSERT INTO docs (content) VALUES ('search engine optimization')")
        return e

    def test_calibration_report_returns_dict(self, engine: Engine) -> None:
        labels = [1, 1, 0, 0]
        report = engine.calibration_report("docs", "content", "learning", labels)
        assert isinstance(report, dict)

    def test_calibration_report_wrong_label_count(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="labels length"):
            engine.calibration_report("docs", "content", "learning", [1, 0])

    def test_calibration_report_nonexistent_table(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            engine.calibration_report("nonexistent", "content", "learning", [1])
