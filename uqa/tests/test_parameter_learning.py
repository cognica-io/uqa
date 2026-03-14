#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.engine import Engine
from uqa.scoring.parameter_learner import ParameterLearner


class TestParameterLearner:
    """Tests for ParameterLearner (Paper 3, Section 8)."""

    def test_init_default_params(self) -> None:
        learner = ParameterLearner()
        params = learner.params()
        assert params["alpha"] == pytest.approx(1.0)
        assert params["beta"] == pytest.approx(0.0)
        assert params["base_rate"] == pytest.approx(0.5)

    def test_init_custom_params(self) -> None:
        learner = ParameterLearner(alpha=2.0, beta=0.5, base_rate=0.3)
        params = learner.params()
        assert params["alpha"] == pytest.approx(2.0)
        assert params["beta"] == pytest.approx(0.5)
        assert params["base_rate"] == pytest.approx(0.3)

    def test_fit_returns_dict(self) -> None:
        learner = ParameterLearner()
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        labels = [0, 0, 0, 1, 1]
        result = learner.fit(scores, labels)
        assert isinstance(result, dict)
        assert "alpha" in result
        assert "beta" in result
        assert "base_rate" in result

    def test_fit_changes_params(self) -> None:
        learner = ParameterLearner()
        initial = learner.params()
        scores = [0.1, 0.2, 0.8, 0.9]
        labels = [0, 0, 1, 1]
        learned = learner.fit(scores, labels)
        # At least one parameter should differ after fitting
        changed = (
            abs(learned["alpha"] - initial["alpha"]) > 1e-6
            or abs(learned["beta"] - initial["beta"]) > 1e-6
            or abs(learned["base_rate"] - initial["base_rate"]) > 1e-6
        )
        assert changed

    def test_fit_with_mode(self) -> None:
        learner = ParameterLearner()
        scores = [0.1, 0.3, 0.7, 0.9]
        labels = [0, 0, 1, 1]
        result = learner.fit(scores, labels, mode="balanced")
        assert isinstance(result, dict)

    def test_fit_with_tfs_and_doc_len_ratios(self) -> None:
        learner = ParameterLearner()
        scores = [0.1, 0.3, 0.7, 0.9]
        labels = [0, 0, 1, 1]
        tfs = [1, 2, 3, 4]
        ratios = [0.8, 1.0, 1.2, 0.9]
        result = learner.fit(scores, labels, tfs=tfs, doc_len_ratios=ratios)
        assert isinstance(result, dict)

    def test_update_modifies_params(self) -> None:
        learner = ParameterLearner()
        initial = learner.params()
        for _ in range(100):
            learner.update(0.9, 1)
            learner.update(0.1, 0)
        updated = learner.params()
        changed = (
            abs(updated["alpha"] - initial["alpha"]) > 1e-6
            or abs(updated["beta"] - initial["beta"]) > 1e-6
        )
        assert changed

    def test_update_with_tf_and_doc_len(self) -> None:
        learner = ParameterLearner()
        learner.update(0.5, 1, tf=3, doc_len_ratio=1.2)
        params = learner.params()
        assert isinstance(params, dict)

    def test_params_returns_floats(self) -> None:
        learner = ParameterLearner()
        params = learner.params()
        for key in ("alpha", "beta", "base_rate"):
            assert isinstance(params[key], float)


class TestEngineParameterLearning:
    """Tests for Engine.learn_scoring_params()."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        e.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        e.sql("INSERT INTO docs (content) VALUES ('deep learning neural networks')")
        e.sql("INSERT INTO docs (content) VALUES ('database indexing structures')")
        e.sql("INSERT INTO docs (content) VALUES ('search engine optimization')")
        return e

    def test_learn_returns_dict(self, engine: Engine) -> None:
        labels = [1, 1, 0, 0]
        result = engine.learn_scoring_params("docs", "content", "learning", labels)
        assert isinstance(result, dict)
        assert "alpha" in result
        assert "beta" in result
        assert "base_rate" in result

    def test_learn_wrong_label_count(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="labels length"):
            engine.learn_scoring_params("docs", "content", "learning", [1, 0])

    def test_learn_nonexistent_table(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            engine.learn_scoring_params("nonexistent", "content", "learning", [1])

    def test_update_scoring_params(self, engine: Engine) -> None:
        engine.update_scoring_params("docs", "content", 0.8, 1)
        # Should not raise

    def test_query_builder_learn_params(self, engine: Engine) -> None:
        labels = [1, 1, 0, 0]
        result = engine.query("docs").learn_params("learning", labels, field="content")
        assert isinstance(result, dict)
        assert "alpha" in result
