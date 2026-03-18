#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for ConvLayer and estimate_conv_weights."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import Edge
from uqa.engine import Engine
from uqa.operators.deep_fusion import (
    ConvLayer,
    DeepFusionOperator,
    SignalLayer,
)

# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def grid_engine() -> Engine:
    """Engine with a 3x3 grid of image patches connected spatially."""
    e = Engine()
    e.sql("""
        CREATE TABLE patches (
            id SERIAL PRIMARY KEY,
            image_id INTEGER NOT NULL,
            patch_row INTEGER NOT NULL,
            patch_col INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(4)
        )
    """)

    # 3x3 grid of patches for image_id=1
    # Patches with similar positions have similar embeddings
    rng = np.random.RandomState(42)
    base_vecs = {
        (0, 0): np.array([1.0, 0.0, 0.0, 0.0]),
        (0, 1): np.array([0.9, 0.1, 0.0, 0.0]),
        (0, 2): np.array([0.8, 0.2, 0.0, 0.0]),
        (1, 0): np.array([0.7, 0.0, 0.3, 0.0]),
        (1, 1): np.array([0.6, 0.1, 0.3, 0.0]),
        (1, 2): np.array([0.5, 0.2, 0.3, 0.0]),
        (2, 0): np.array([0.3, 0.0, 0.7, 0.0]),
        (2, 1): np.array([0.2, 0.1, 0.7, 0.0]),
        (2, 2): np.array([0.1, 0.2, 0.7, 0.0]),
    }

    for (r, c), base in base_vecs.items():
        vec = base + rng.randn(4).astype(np.float32) * 0.05
        vec = vec / np.linalg.norm(vec)
        arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        # Use descriptive content for text matching
        content = f"patch at row {r} col {c}"
        if r == 1 and c == 1:
            content = "center patch attention focus"
        e.sql(
            f"INSERT INTO patches (image_id, patch_row, patch_col, "
            f"content, embedding) "
            f"VALUES (1, {r}, {c}, '{content}', {arr})"
        )

    # Build 4-connected grid graph (horizontal + vertical adjacency)
    # Patch IDs are 1-9 in row-major order
    edge_id = 1
    for r in range(3):
        for c in range(3):
            pid = r * 3 + c + 1
            # Right neighbor
            if c < 2:
                right = pid + 1
                e.add_graph_edge(Edge(edge_id, pid, right, "spatial"), table="patches")
                edge_id += 1
            # Down neighbor
            if r < 2:
                down = pid + 3
                e.add_graph_edge(Edge(edge_id, pid, down, "spatial"), table="patches")
                edge_id += 1

    return e


@pytest.fixture
def query_vector() -> np.ndarray:
    return np.array([0.8, 0.05, 0.15, 0.0], dtype=np.float32)


# ----------------------------------------------------------------
# Unit tests: ConvLayer construction
# ----------------------------------------------------------------


class TestConvLayerConstruction:
    def test_conv_layer_first_raises(self):
        with pytest.raises(ValueError, match="first layer must be a SignalLayer"):
            DeepFusionOperator(layers=[ConvLayer("spatial", (0.5, 0.5), "both")])

    def test_valid_conv_layer(self):
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("test")]),
                ConvLayer("spatial", (0.6, 0.4), "both"),
            ],
        )
        assert len(op.layers) == 2


# ----------------------------------------------------------------
# Integration tests: ConvLayer execution
# ----------------------------------------------------------------


class TestConvLayerExecution:
    def test_single_hop_convolution(self, grid_engine, query_vector):
        """ConvLayer with 1-hop weights smooths scores spatially."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.6, 0.4])
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_two_hop_convolution(self, grid_engine, query_vector):
        """ConvLayer with 2-hop weights (5x5 receptive field)."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.5, 0.3, 0.2])
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_stacked_conv_layers(self, grid_engine, query_vector):
        """Two stacked ConvLayers = deeper receptive field (like deeper CNN)."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.6, 0.4]),
                convolve('spatial', ARRAY[0.6, 0.4]),
                gating => 'relu'
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_conv_smooths_scores(self, grid_engine, query_vector):
        """Convolution should reduce score variance (spatial smoothing)."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"

        # Without convolution
        raw = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9))
            ) ORDER BY id
        """)

        # With convolution
        conv = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.5, 0.5])
            ) ORDER BY id
        """)

        raw_scores = [r["_score"] for r in raw.rows]
        conv_scores = [r["_score"] for r in conv.rows]

        # Convolution should reduce variance (smoothing effect)
        raw_var = np.var(raw_scores)
        conv_var = np.var(conv_scores)
        assert conv_var <= raw_var + 1e-10, (
            f"Convolution should smooth scores: raw_var={raw_var:.6f}, "
            f"conv_var={conv_var:.6f}"
        )

    def test_conv_with_text_signal(self, grid_engine):
        """ConvLayer works with text signals too."""
        result = grid_engine.sql("""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(bayesian_match(content, 'center attention')),
                convolve('spatial', ARRAY[0.5, 0.3, 0.2])
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_conv_direction_out(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.6, 0.4], 'out')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_conv_with_gating(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        for gating in ("none", "relu", "swish"):
            result = grid_engine.sql(f"""
                SELECT id, _score FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 9)),
                    convolve('spatial', ARRAY[0.6, 0.4]),
                    gating => '{gating}'
                ) ORDER BY _score DESC
            """)
            assert len(result.rows) > 0


# ----------------------------------------------------------------
# Integration tests: mixed Conv + Propagate + Signal
# ----------------------------------------------------------------


class TestMixedConvLayers:
    def test_signal_conv_signal(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(bayesian_match(content, 'attention')),
                convolve('spatial', ARRAY[0.6, 0.4]),
                layer(knn_match(embedding, {arr}, 9))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0


# ----------------------------------------------------------------
# Integration tests: EXPLAIN
# ----------------------------------------------------------------


class TestConvExplain:
    def test_explain_conv_layer(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 9)),
                convolve('spatial', ARRAY[0.6, 0.4]),
                convolve('spatial', ARRAY[0.5, 0.3, 0.2])
            ) ORDER BY _score DESC
        """)
        plan_text = "\n".join(row["plan"] for row in result.rows)
        assert "DeepFusion" in plan_text
        assert "convolve='spatial'" in plan_text
        assert "hops=1" in plan_text
        assert "hops=2" in plan_text


# ----------------------------------------------------------------
# Tests: estimate_conv_weights
# ----------------------------------------------------------------


class TestEstimateConvWeights:
    def test_basic_estimation(self, grid_engine):
        """Estimate weights from spatial autocorrelation."""
        weights = grid_engine.estimate_conv_weights(
            table="patches",
            edge_label="spatial",
            kernel_hops=2,
            embedding_field="embedding",
        )
        assert len(weights) == 3  # hop 0, 1, 2
        assert all(w >= 0 for w in weights)
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_weights_decrease_with_distance(self, grid_engine):
        """Spatial autocorrelation should decrease with hop distance."""
        weights = grid_engine.estimate_conv_weights(
            table="patches",
            edge_label="spatial",
            kernel_hops=2,
        )
        # Self-similarity (hop 0) should have the highest weight
        assert weights[0] >= weights[1]

    def test_single_hop(self, grid_engine):
        weights = grid_engine.estimate_conv_weights(
            table="patches",
            edge_label="spatial",
            kernel_hops=1,
        )
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_nonexistent_table_raises(self, grid_engine):
        with pytest.raises(ValueError, match="does not exist"):
            grid_engine.estimate_conv_weights(
                table="nonexistent",
                edge_label="spatial",
                kernel_hops=1,
            )

    def test_estimated_weights_improve_retrieval(self, grid_engine):
        """Estimated weights should produce valid results when used."""
        weights = grid_engine.estimate_conv_weights(
            table="patches",
            edge_label="spatial",
            kernel_hops=1,
        )
        arr_w = "ARRAY[" + ",".join(str(w) for w in weights) + "]"
        query = np.array([0.8, 0.05, 0.15, 0.0], dtype=np.float32)
        arr_q = "ARRAY[" + ",".join(str(float(v)) for v in query) + "]"

        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr_q}, 9)),
                convolve('spatial', {arr_w})
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Tests: error cases
# ----------------------------------------------------------------


class TestConvErrors:
    def test_invalid_direction(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match="'both', 'out', or 'in'"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 9)),
                    convolve('spatial', ARRAY[0.5, 0.5], 'wrong')
                )
            """)

    def test_empty_weights_array(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 9)),
                    convolve('spatial', ARRAY[]::float[])
                )
            """)


# ----------------------------------------------------------------
# Tests: cost estimate
# ----------------------------------------------------------------


class TestConvCostEstimate:
    def test_cost_includes_conv(self):
        from uqa.core.types import IndexStats
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("a")]),
                ConvLayer("spatial", (0.6, 0.4), "both"),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost > 0
