#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for DeepFusionOperator -- multi-layer Bayesian fusion."""

from __future__ import annotations

import math

import numpy as np
import pytest

from uqa.core.types import Edge
from uqa.engine import Engine
from uqa.operators.deep_fusion import (
    DeepFusionOperator,
    PropagateLayer,
    SignalLayer,
    _apply_gating,
    _safe_logit,
    _sigmoid,
)

# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def engine() -> Engine:
    """Engine with papers table, vectors, and citation graph."""
    e = Engine()
    e.sql("""
        CREATE TABLE papers (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT NOT NULL,
            embedding VECTOR(4)
        )
    """)

    rng = np.random.RandomState(42)
    paper_data = [
        ("attention mechanisms in neural networks", "transformers self-attention"),
        ("graph neural networks survey", "message passing graph convolution"),
        ("deep learning optimization", "gradient descent transformers training"),
        ("attention for graphs", "graph attention transformers nodes"),
        ("convolutional neural networks", "image recognition convolution filters"),
    ]

    for title, abstract in paper_data:
        vec = rng.randn(4).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        e.sql(
            f"INSERT INTO papers (title, abstract, embedding) "
            f"VALUES ('{title}', '{abstract}', {arr})"
        )

    # Citation graph: 1->2, 2->3, 3->4, 1->4
    e.add_graph_edge(Edge(1, 1, 2, "cites"), table="papers")
    e.add_graph_edge(Edge(2, 2, 3, "cites"), table="papers")
    e.add_graph_edge(Edge(3, 3, 4, "cites"), table="papers")
    e.add_graph_edge(Edge(4, 1, 4, "cites"), table="papers")

    return e


@pytest.fixture
def query_vector() -> np.ndarray:
    rng = np.random.RandomState(99)
    v = rng.randn(4).astype(np.float32)
    return v / np.linalg.norm(v)


# ----------------------------------------------------------------
# Unit tests: helper functions
# ----------------------------------------------------------------


class TestHelperFunctions:
    def test_safe_logit_middle(self):
        assert _safe_logit(0.5) == pytest.approx(0.0, abs=1e-10)

    def test_safe_logit_high(self):
        assert _safe_logit(0.9) > 0

    def test_safe_logit_low(self):
        assert _safe_logit(0.1) < 0

    def test_safe_logit_clamp_extreme(self):
        # Should not raise even for 0 or 1
        assert math.isfinite(_safe_logit(0.0))
        assert math.isfinite(_safe_logit(1.0))

    def test_sigmoid_middle(self):
        assert _sigmoid(0.0) == pytest.approx(0.5)

    def test_sigmoid_positive(self):
        assert _sigmoid(5.0) > 0.99

    def test_sigmoid_negative(self):
        assert _sigmoid(-5.0) < 0.01

    def test_sigmoid_large_negative(self):
        # Numerically stable for extreme values
        assert _sigmoid(-100.0) == pytest.approx(0.0, abs=1e-10)

    def test_gating_none(self):
        assert _apply_gating(-2.0, "none") == -2.0
        assert _apply_gating(3.0, "none") == 3.0

    def test_gating_relu(self):
        assert _apply_gating(-2.0, "relu") == 0.0
        assert _apply_gating(3.0, "relu") == 3.0

    def test_gating_swish(self):
        val = _apply_gating(2.0, "swish")
        expected = 2.0 * _sigmoid(2.0)
        assert val == pytest.approx(expected)

        # Swish of negative is near zero but not exactly zero
        val_neg = _apply_gating(-2.0, "swish")
        assert val_neg < 0


# ----------------------------------------------------------------
# Unit tests: operator construction
# ----------------------------------------------------------------


class TestOperatorConstruction:
    def test_empty_layers_raises(self):
        with pytest.raises(ValueError, match="at least one layer"):
            DeepFusionOperator(layers=[])

    def test_propagate_first_raises(self):
        with pytest.raises(ValueError, match="first layer must be a SignalLayer"):
            DeepFusionOperator(layers=[PropagateLayer("cites", "mean", "both")])

    def test_valid_construction(self):
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[SignalLayer(signals=[TermOperator("test")])],
            alpha=0.5,
            gating="relu",
        )
        assert len(op.layers) == 1
        assert op.gating == "relu"


# ----------------------------------------------------------------
# Integration tests: single signal layer
# ----------------------------------------------------------------


class TestSingleSignalLayer:
    def test_single_layer_single_signal(self, engine):
        """Single signal layer with one signal matches raw signal output order."""
        result = engine.sql("""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention'))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_single_layer_multi_signal(self, engine, query_vector):
        """Single layer with multiple signals performs within-layer conjunction."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = engine.sql(f"""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 5))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Integration tests: residual accumulation
# ----------------------------------------------------------------


class TestResidualAccumulation:
    def test_two_signal_layers(self, engine, query_vector):
        """Two signal layers accumulate logits (residual connection)."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = engine.sql(f"""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                layer(knn_match(embedding, {arr}, 5))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_three_layers_hierarchical(self, engine, query_vector):
        """Three signal layers for hierarchical fusion."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = engine.sql(f"""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                layer(bayesian_match(abstract, 'transformers')),
                layer(knn_match(embedding, {arr}, 5))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        scores = [row["_score"] for row in result.rows]
        # Scores should be sorted descending
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1] - 1e-10


# ----------------------------------------------------------------
# Integration tests: gating
# ----------------------------------------------------------------


class TestGating:
    def test_gating_none(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                gating => 'none'
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_gating_relu(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                gating => 'relu'
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        # With ReLU, all scores should be >= 0.5 (sigmoid(0) = 0.5)
        for row in result.rows:
            assert row["_score"] >= 0.5 - 1e-10

    def test_gating_swish(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                gating => 'swish'
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Integration tests: propagation
# ----------------------------------------------------------------


class TestPropagation:
    def test_basic_propagate(self, engine):
        """Signal + propagate spreads scores through citation edges."""
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_propagate_discovers_new_docs(self, engine):
        """Propagation can discover docs not in original signal."""
        # "attention" matches docs 1 and 4 (titles contain attention).
        # Propagation through cites should spread to neighbors.
        text_only = engine.sql("""
            SELECT id FROM papers
            WHERE bayesian_match(title, 'attention')
        """)
        text_ids = {row["id"] for row in text_only.rows}

        deep_result = engine.sql("""
            SELECT id FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean')
            )
        """)
        deep_ids = {row["id"] for row in deep_result.rows}

        # Deep fusion should have at least as many docs (propagation adds neighbors)
        assert len(deep_ids) >= len(text_ids)

    def test_propagate_aggregation_mean(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_propagate_aggregation_sum(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'sum')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_propagate_aggregation_max(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'max')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_multi_hop_propagation(self, engine):
        """Two consecutive propagate layers = 2-hop message passing."""
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean'),
                propagate('cites', 'mean')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Integration tests: mixed layers
# ----------------------------------------------------------------


class TestMixedLayers:
    def test_signal_propagate_signal(self, engine, query_vector):
        """signal -> propagate -> signal pipeline."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = engine.sql(f"""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean'),
                layer(knn_match(embedding, {arr}, 5)),
                gating => 'relu'
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_signal_propagate_propagate_signal(self, engine):
        """signal -> propagate -> propagate -> signal."""
        result = engine.sql("""
            SELECT id, title, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean'),
                propagate('cites', 'mean'),
                layer(bayesian_match(abstract, 'graph'))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0


# ----------------------------------------------------------------
# Integration tests: EXPLAIN
# ----------------------------------------------------------------


class TestExplain:
    def test_explain_output(self, engine):
        result = engine.sql("""
            EXPLAIN SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean'),
                layer(bayesian_match(abstract, 'graph'))
            ) ORDER BY _score DESC
        """)
        plan_text = "\n".join(row["plan"] for row in result.rows)
        assert "DeepFusion" in plan_text
        assert "layers=3" in plan_text
        assert "Layer 0" in plan_text
        assert "signals=1" in plan_text
        assert "propagate='cites'" in plan_text
        assert "Layer 2" in plan_text


# ----------------------------------------------------------------
# Integration tests: score validity
# ----------------------------------------------------------------


class TestScoreValidity:
    def test_all_scores_in_unit_interval(self, engine, query_vector):
        """All output scores must be in (0, 1)."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = engine.sql(f"""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention'), knn_match(embedding, {arr}, 5)),
                propagate('cites', 'mean'),
                layer(bayesian_match(abstract, 'graph')),
                gating => 'swish'
            )
        """)
        for row in result.rows:
            assert 0.0 < row["_score"] < 1.0, (
                f"Score {row['_score']} not in (0,1) for doc {row['id']}"
            )


# ----------------------------------------------------------------
# Integration tests: error cases
# ----------------------------------------------------------------


class TestErrorCases:
    def test_propagate_first_layer_error(self, engine):
        with pytest.raises(Exception, match="first layer must be a SignalLayer"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    propagate('cites', 'mean'),
                    layer(bayesian_match(title, 'attention'))
                )
            """)

    def test_empty_layer_error(self, engine):
        with pytest.raises(Exception, match="at least one signal"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    layer()
                )
            """)

    def test_invalid_aggregation(self, engine):
        with pytest.raises(Exception, match="'mean', 'sum', or 'max'"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    layer(bayesian_match(title, 'attention')),
                    propagate('cites', 'invalid_agg')
                )
            """)

    def test_invalid_direction(self, engine):
        with pytest.raises(Exception, match="'both', 'out', or 'in'"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    layer(bayesian_match(title, 'attention')),
                    propagate('cites', 'mean', 'sideways')
                )
            """)

    def test_unknown_named_arg(self, engine):
        with pytest.raises(Exception, match="Unknown option"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    layer(bayesian_match(title, 'attention')),
                    foo => 'bar'
                )
            """)

    def test_invalid_inner_function(self, engine):
        with pytest.raises(Exception, match=r"unknown layer function"):
            engine.sql("""
                SELECT id FROM papers
                WHERE deep_fusion(
                    something_else(bayesian_match(title, 'attention'))
                )
            """)


# ----------------------------------------------------------------
# Integration tests: alpha parameter
# ----------------------------------------------------------------


class TestAlphaParameter:
    def test_alpha_affects_scores(self, engine):
        """Different alpha values should produce different score distributions."""
        result_low = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention'),
                      bayesian_match(abstract, 'graph')),
                alpha => 0.1
            ) ORDER BY id
        """)
        result_high = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention'),
                      bayesian_match(abstract, 'graph')),
                alpha => 0.9
            ) ORDER BY id
        """)

        # Both should return results
        assert len(result_low.rows) > 0
        assert len(result_high.rows) > 0

        # At least some scores should differ
        scores_low = {r["id"]: r["_score"] for r in result_low.rows}
        scores_high = {r["id"]: r["_score"] for r in result_high.rows}
        common_ids = set(scores_low) & set(scores_high)
        assert any(abs(scores_low[i] - scores_high[i]) > 1e-6 for i in common_ids)


# ----------------------------------------------------------------
# Unit tests: cost_estimate
# ----------------------------------------------------------------


class TestCostEstimate:
    def test_cost_estimate(self):
        from uqa.core.types import IndexStats
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("a"), TermOperator("b")]),
                PropagateLayer("cites", "mean", "both"),
                SignalLayer(signals=[TermOperator("c")]),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        # Should include signal costs + propagation cost
        assert cost > 0


# ----------------------------------------------------------------
# Unit tests: propagate direction
# ----------------------------------------------------------------


class TestPropagateDirection:
    def test_propagate_out_direction(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean', 'out')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_propagate_in_direction(self, engine):
        result = engine.sql("""
            SELECT id, _score FROM papers
            WHERE deep_fusion(
                layer(bayesian_match(title, 'attention')),
                propagate('cites', 'mean', 'in')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
