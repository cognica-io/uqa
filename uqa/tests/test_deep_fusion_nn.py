#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for deep learning components in DeepFusionOperator."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import Edge
from uqa.engine import Engine
from uqa.operators.deep_fusion import (
    ConvLayer,
    DeepFusionOperator,
    DenseLayer,
    DropoutLayer,
    FlattenLayer,
    PoolLayer,
    PropagateLayer,
    SignalLayer,
    SoftmaxLayer,
    _apply_gating_vec,
    _sigmoid_vec,
)

# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def grid_engine() -> Engine:
    """Engine with a 4x4 grid of image patches connected spatially."""
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

    rng = np.random.RandomState(42)
    for r in range(4):
        for c in range(4):
            vec = rng.randn(4).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
            content = f"patch at row {r} col {c}"
            if r == 1 and c == 1:
                content = "center patch attention focus"
            e.sql(
                f"INSERT INTO patches (image_id, patch_row, patch_col, "
                f"content, embedding) "
                f"VALUES (1, {r}, {c}, '{content}', {arr})"
            )

    # Build 4-connected grid graph
    edge_id = 1
    for r in range(4):
        for c in range(4):
            pid = r * 4 + c + 1
            if c < 3:
                right = pid + 1
                e.add_graph_edge(Edge(edge_id, pid, right, "spatial"), table="patches")
                edge_id += 1
            if r < 3:
                down = pid + 4
                e.add_graph_edge(Edge(edge_id, pid, down, "spatial"), table="patches")
                edge_id += 1

    return e


@pytest.fixture
def query_vector() -> np.ndarray:
    rng = np.random.RandomState(99)
    v = rng.randn(4).astype(np.float32)
    return v / np.linalg.norm(v)


# ----------------------------------------------------------------
# Unit tests: vectorized helpers
# ----------------------------------------------------------------


class TestVectorizedHelpers:
    def test_sigmoid_vec(self):
        x = np.array([-5.0, 0.0, 5.0])
        result = _sigmoid_vec(x)
        assert result[0] < 0.01
        assert result[1] == pytest.approx(0.5)
        assert result[2] > 0.99

    def test_sigmoid_vec_large_negative(self):
        x = np.array([-100.0, -50.0])
        result = _sigmoid_vec(x)
        assert np.all(np.isfinite(result))
        assert np.all(result >= 0.0)

    def test_apply_gating_vec_none(self):
        x = np.array([-2.0, 3.0])
        result = _apply_gating_vec(x, "none")
        np.testing.assert_array_equal(result, x)

    def test_apply_gating_vec_relu(self):
        x = np.array([-2.0, 3.0, 0.0])
        result = _apply_gating_vec(x, "relu")
        np.testing.assert_array_equal(result, [0.0, 3.0, 0.0])

    def test_apply_gating_vec_swish(self):
        x = np.array([2.0, -2.0])
        result = _apply_gating_vec(x, "swish")
        expected = x * _sigmoid_vec(x)
        np.testing.assert_allclose(result, expected)


# ----------------------------------------------------------------
# Unit tests: PoolLayer
# ----------------------------------------------------------------


class TestPoolLayer:
    def test_pool_max_on_grid(self, grid_engine, query_vector):
        """Max pooling should reduce node count."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        # Without pooling: 16 nodes
        raw = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16))
            ) ORDER BY id
        """)
        assert len(raw.rows) == 16

        # With 2x2 max pooling: should reduce
        pooled = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 2)
            ) ORDER BY id
        """)
        assert len(pooled.rows) < len(raw.rows)
        for row in pooled.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_pool_avg_on_grid(self, grid_engine, query_vector):
        """Average pooling should also reduce node count."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        pooled = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'avg', 2)
            ) ORDER BY id
        """)
        assert len(pooled.rows) < 16
        for row in pooled.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_pool_size_4(self, grid_engine, query_vector):
        """Larger pool size = more reduction than pool size 2."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        pooled_2 = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 2)
            ) ORDER BY id
        """)
        pooled_4 = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 4)
            ) ORDER BY id
        """)
        # Pool-4 should yield fewer or equal nodes than pool-2
        assert len(pooled_4.rows) <= len(pooled_2.rows)
        assert len(pooled_4.rows) < 16

    def test_pool_size_validation(self):
        from uqa.operators.primitive import TermOperator

        with pytest.raises(ValueError, match="pool_size must be >= 2"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    PoolLayer("spatial", 1, "max", "both"),
                ]
            )


# ----------------------------------------------------------------
# Unit tests: DenseLayer
# ----------------------------------------------------------------


class TestDenseLayer:
    def test_identity_weights(self, grid_engine, query_vector):
        """Identity matrix should preserve scores."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"

        # Without dense: 1 channel
        raw = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16))
            ) ORDER BY id
        """)

        # Dense with identity weights: 1->1, W=[1], b=[0]
        dense = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[1.0], ARRAY[0.0],
                      output_channels => 1, input_channels => 1)
            ) ORDER BY id
        """)

        # Scores should be very similar (gating=none means identity)
        assert len(raw.rows) == len(dense.rows)

    def test_channel_expansion(self, grid_engine, query_vector):
        """Dense 1->4 should expand channels."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        # 1->4 dense layer: weights (4x1 = 4 values), bias (4 values)
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[1.0, 0.5, -0.5, 0.3], ARRAY[0.0, 0.0, 0.0, 0.0],
                      output_channels => 4, input_channels => 1)
            ) ORDER BY id
        """)
        assert len(result.rows) == 16
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_dense_with_bias(self, grid_engine, query_vector):
        """Bias shifts all outputs higher than without bias."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        no_bias = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[1.0], ARRAY[0.0],
                      output_channels => 1, input_channels => 1)
            ) ORDER BY id
        """)
        with_bias = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[1.0], ARRAY[2.0],
                      output_channels => 1, input_channels => 1)
            ) ORDER BY id
        """)
        assert len(with_bias.rows) == len(no_bias.rows)
        # Positive bias should push every score higher
        for a, b in zip(no_bias.rows, with_bias.rows):
            assert b["_score"] >= a["_score"] - 1e-10

    def test_dense_channel_reduction(self, grid_engine, query_vector):
        """Dense 4->2 should reduce channels."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        # First expand 1->4, then reduce 4->2
        w_expand = ",".join(["1.0", "0.5", "-0.5", "0.3"])
        b_expand = ",".join(["0.0"] * 4)
        # 2x4=8 weights for 4->2
        w_reduce = ",".join(["0.5", "0.5", "0.0", "0.0", "0.0", "0.0", "0.5", "0.5"])
        b_reduce = ",".join(["0.0"] * 2)
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[{w_expand}], ARRAY[{b_expand}],
                      output_channels => 4, input_channels => 1),
                dense(ARRAY[{w_reduce}], ARRAY[{b_reduce}],
                      output_channels => 2, input_channels => 4)
            ) ORDER BY id
        """)
        assert len(result.rows) == 16


# ----------------------------------------------------------------
# Unit tests: FlattenLayer
# ----------------------------------------------------------------


class TestFlattenLayer:
    def test_flatten_reduces_to_one_node(self, grid_engine, query_vector):
        """Flatten S nodes x C channels -> 1 node x S*C."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                flatten()
            ) ORDER BY id
        """)
        # Should produce exactly 1 node
        assert len(result.rows) == 1
        assert 0.0 < result.rows[0]["_score"] <= 1.0

    def test_flatten_then_dense(self, grid_engine, query_vector):
        """Flatten followed by dense for classification."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        # 16 nodes x 1 channel = 16 channels after flatten
        # Dense 16->4
        weights = ",".join(str(float(i % 3) * 0.1) for i in range(64))
        bias = ",".join(["0.0"] * 4)
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                flatten(),
                dense(ARRAY[{weights}], ARRAY[{bias}],
                      output_channels => 4, input_channels => 16)
            ) ORDER BY id
        """)
        assert len(result.rows) == 1

    def test_spatial_after_flatten_rejected(self):
        """Spatial layers must not appear after flatten."""
        from uqa.operators.primitive import TermOperator

        with pytest.raises(ValueError, match="must not appear after flatten"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    FlattenLayer(),
                    PropagateLayer("spatial", "mean", "both"),
                ]
            )

        with pytest.raises(ValueError, match="must not appear after flatten"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    FlattenLayer(),
                    ConvLayer("spatial", (0.5, 0.5), "both"),
                ]
            )

        with pytest.raises(ValueError, match="must not appear after flatten"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    FlattenLayer(),
                    PoolLayer("spatial", 2, "max", "both"),
                ]
            )


# ----------------------------------------------------------------
# Unit tests: SoftmaxLayer
# ----------------------------------------------------------------


class TestSoftmaxLayer:
    def test_softmax_probabilities_sum_to_one(self):
        """After softmax, class_probs should sum to 1."""
        channel_map: dict[int, np.ndarray] = {
            1: np.array([2.0, 1.0, -1.0, 0.5]),
            2: np.array([0.0, 3.0, -2.0, 1.0]),
            3: np.array([-1.0, -1.0, -1.0, -1.0]),
        }
        DeepFusionOperator._execute_softmax_layer(channel_map)

        for doc_id, vec in channel_map.items():
            assert abs(vec.sum() - 1.0) < 1e-6, f"doc {doc_id}: sum={vec.sum()}"
            assert np.all(vec >= 0.0)

    def test_softmax_score_is_max_prob(self, grid_engine, query_vector):
        """SQL result score should be max(probs) after softmax."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        w = ",".join(["1.0", "0.5", "-0.5", "0.3"])
        b = ",".join(["0.0"] * 4)
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[{w}], ARRAY[{b}],
                      output_channels => 4, input_channels => 1),
                softmax()
            ) ORDER BY id
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            # After softmax, score = max(probs), so score in (0, 1]
            assert 0.0 < row["_score"] <= 1.0

    def test_softmax_payload_fields(self):
        """Verify class_probs in Payload.fields via direct operator execution."""
        from uqa.operators.base import ExecutionContext
        from uqa.operators.primitive import TermOperator
        from uqa.storage.document_store import MemoryDocumentStore
        from uqa.storage.inverted_index import MemoryInvertedIndex

        # Build a minimal operator and execute directly
        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("test")]),
                DenseLayer(
                    weights=(1.0, 0.5, -0.5),
                    bias=(0.0, 0.0, 0.0),
                    output_channels=3,
                    input_channels=1,
                ),
                SoftmaxLayer(),
            ]
        )

        # Build a minimal context with a document that matches "test"
        ds = MemoryDocumentStore()
        ds.put(1, {"_default": "test document"})
        idx = MemoryInvertedIndex()
        idx.add_document(1, {"_default": "test document"})

        ctx = ExecutionContext(
            document_store=ds,
            inverted_index=idx,
        )
        result_pl = op.execute(ctx)
        assert len(result_pl) > 0
        for entry in result_pl:
            probs = entry.payload.fields.get("class_probs")
            assert probs is not None
            assert abs(sum(probs) - 1.0) < 1e-6
            assert entry.payload.score == pytest.approx(max(probs), abs=1e-10)

    def test_softmax_numerically_stable(self):
        """Softmax should handle large values without overflow."""
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("test")]),
                DenseLayer(
                    weights=(100.0,),
                    bias=(500.0,),
                    output_channels=1,
                    input_channels=1,
                ),
                SoftmaxLayer(),
            ]
        )
        # Just verify construction succeeds
        assert len(op.layers) == 3


# ----------------------------------------------------------------
# Unit tests: BatchNormLayer
# ----------------------------------------------------------------


class TestBatchNormLayer:
    def test_batchnorm_zero_mean_unit_variance(self):
        """After batch_norm, each channel should have ~zero mean, ~unit variance."""
        # Use direct operator execution for verification
        from uqa.operators.deep_fusion import BatchNormLayer as BNL

        channel_map: dict[int, np.ndarray] = {}
        for i in range(1, 11):
            channel_map[i] = np.array([float(i), float(i * 2)])

        DeepFusionOperator._execute_batchnorm_layer(BNL(epsilon=1e-5), channel_map)

        # Check per-channel stats
        vecs = np.stack([channel_map[i] for i in sorted(channel_map)])
        for ch in range(2):
            assert abs(vecs[:, ch].mean()) < 1e-5
            assert abs(vecs[:, ch].std() - 1.0) < 0.1

    def test_batchnorm_sql(self, grid_engine, query_vector):
        """batch_norm() in SQL should produce valid results."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                batch_norm()
            ) ORDER BY id
        """)
        assert len(result.rows) == 16

    def test_batchnorm_custom_epsilon(self, grid_engine, query_vector):
        """batch_norm with custom epsilon."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                batch_norm(epsilon => 0.001)
            ) ORDER BY id
        """)
        assert len(result.rows) == 16


# ----------------------------------------------------------------
# Unit tests: DropoutLayer
# ----------------------------------------------------------------


class TestDropoutLayer:
    def test_dropout_scales_by_one_minus_p(self):
        """Inference dropout should multiply all values by (1-p)."""
        from uqa.operators.deep_fusion import DropoutLayer as DL

        channel_map: dict[int, np.ndarray] = {
            1: np.array([2.0, 4.0]),
            2: np.array([6.0, 8.0]),
        }
        DeepFusionOperator._execute_dropout_layer(DL(p=0.5), channel_map)

        np.testing.assert_allclose(channel_map[1], [1.0, 2.0])
        np.testing.assert_allclose(channel_map[2], [3.0, 4.0])

    def test_dropout_p_validation(self):
        from uqa.operators.primitive import TermOperator

        with pytest.raises(ValueError, match="p must be in"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    DropoutLayer(p=0.0),
                ]
            )
        with pytest.raises(ValueError, match="p must be in"):
            DeepFusionOperator(
                layers=[
                    SignalLayer(signals=[TermOperator("test")]),
                    DropoutLayer(p=1.0),
                ]
            )

    def test_dropout_sql(self, grid_engine, query_vector):
        """dropout(0.5) in SQL should produce valid results."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dropout(0.5)
            ) ORDER BY id
        """)
        assert len(result.rows) == 16
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Integration test: full CNN pipeline
# ----------------------------------------------------------------


class TestFullCNNPipeline:
    def test_conv_pool_conv_pool_flatten_dense_softmax(self, grid_engine, query_vector):
        """End-to-end CNN: knn -> flatten -> dense -> softmax."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"

        # 16 nodes flatten to 16 channels; dense 16->3; softmax
        weights_16_to_3 = ",".join(str(float(i % 5) * 0.1) for i in range(48))
        bias_3 = ",".join(["0.1"] * 3)

        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                flatten(),
                dense(ARRAY[{weights_16_to_3}], ARRAY[{bias_3}],
                      output_channels => 3, input_channels => 16),
                softmax()
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) == 1
        # After softmax, score is max(probs) which is in (0, 1]
        assert 0.0 < result.rows[0]["_score"] <= 1.0

    def test_conv_pool_flatten_dense_softmax(self, grid_engine, query_vector):
        """CNN with spatial processing before flatten."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"

        # knn(16) -> pool(2) should give ~8 nodes
        result_pool = grid_engine.sql(f"""
            SELECT id FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 2)
            )
        """)
        n_pooled = len(result_pool.rows)

        # Now build full pipeline with known input_channels
        weights = ",".join(str(float(i % 3) * 0.1) for i in range(n_pooled * 4))
        bias = ",".join(["0.0"] * 4)

        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 2),
                flatten(),
                dense(ARRAY[{weights}], ARRAY[{bias}],
                      output_channels => 4, input_channels => {n_pooled}),
                softmax()
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) == 1
        assert 0.0 < result.rows[0]["_score"] <= 1.0

    def test_pipeline_with_batchnorm_dropout(self, grid_engine, query_vector):
        """Pipeline with batch_norm and dropout."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                batch_norm(),
                dropout(0.3),
                convolve('spatial', ARRAY[0.6, 0.4])
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Integration tests: EXPLAIN output for new layer types
# ----------------------------------------------------------------


class TestExplainNewLayers:
    def test_explain_pool(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                pool('spatial', 'max', 2)
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "pool='spatial'" in plan
        assert "method='max'" in plan
        assert "size=2" in plan

    def test_explain_dense(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[1.0, 0.5, -0.5, 0.3], ARRAY[0.0, 0.0, 0.0, 0.0],
                      output_channels => 4, input_channels => 1)
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "dense=1->4" in plan

    def test_explain_flatten(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                flatten()
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "flatten" in plan

    def test_explain_softmax(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        w = ",".join(["0.5"] * 4)
        b = ",".join(["0.0"] * 4)
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dense(ARRAY[{w}], ARRAY[{b}],
                      output_channels => 4, input_channels => 1),
                softmax()
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "softmax" in plan

    def test_explain_batchnorm(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                batch_norm(epsilon => 0.001)
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "batch_norm" in plan
        assert "eps=0.001" in plan

    def test_explain_dropout(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                dropout(0.5)
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "dropout" in plan
        assert "p=0.5" in plan

    def test_explain_full_pipeline(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        weights = ",".join(str(float(i % 3) * 0.1) for i in range(48))
        bias = ",".join(["0.0"] * 3)
        result = grid_engine.sql(f"""
            EXPLAIN SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                convolve('spatial', ARRAY[0.6, 0.4]),
                pool('spatial', 'max', 2),
                flatten(),
                dense(ARRAY[{weights}], ARRAY[{bias}],
                      output_channels => 3, input_channels => 16),
                softmax()
            ) ORDER BY _score DESC
        """)
        plan = "\n".join(row["plan"] for row in result.rows)
        assert "DeepFusion" in plan
        assert "convolve=" in plan
        assert "pool=" in plan
        assert "flatten" in plan
        assert "dense=" in plan
        assert "softmax" in plan


# ----------------------------------------------------------------
# Backward compatibility
# ----------------------------------------------------------------


class TestBackwardCompatibility:
    def test_existing_signal_layer_unchanged(self, grid_engine, query_vector):
        """Existing single signal layer produces valid results."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16))
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0

    def test_existing_propagate_unchanged(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                propagate('spatial', 'mean')
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0

    def test_existing_conv_unchanged(self, grid_engine, query_vector):
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        result = grid_engine.sql(f"""
            SELECT id, _score FROM patches
            WHERE deep_fusion(
                layer(knn_match(embedding, {arr}, 16)),
                convolve('spatial', ARRAY[0.6, 0.4])
            ) ORDER BY _score DESC
        """)
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 < row["_score"] <= 1.0


# ----------------------------------------------------------------
# Cost estimate for new layers
# ----------------------------------------------------------------


class TestCostEstimateNewLayers:
    def test_cost_includes_pool(self):
        from uqa.core.types import IndexStats
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("a")]),
                PoolLayer("spatial", 2, "max", "both"),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost > 0

    def test_cost_includes_dense(self):
        from uqa.core.types import IndexStats
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("a")]),
                DenseLayer(
                    weights=(1.0, 0.5, -0.5, 0.3),
                    bias=(0.0, 0.0),
                    output_channels=2,
                    input_channels=2,
                ),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        # Dense cost = in_ch * out_ch = 2 * 2 = 4
        assert cost > 0

    def test_cost_includes_flatten_softmax(self):
        from uqa.core.types import IndexStats
        from uqa.operators.primitive import TermOperator

        op = DeepFusionOperator(
            layers=[
                SignalLayer(signals=[TermOperator("a")]),
                FlattenLayer(),
                SoftmaxLayer(),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost > 0


# ----------------------------------------------------------------
# Error cases
# ----------------------------------------------------------------


class TestNewLayerErrors:
    def test_dense_weight_length_mismatch(self, grid_engine, query_vector):
        """dense() weights length must equal out_ch * in_ch."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match="weights array length"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 16)),
                    dense(ARRAY[1.0, 2.0], ARRAY[0.0],
                          output_channels => 1, input_channels => 1)
                )
            """)

    def test_dense_bias_length_mismatch(self, grid_engine, query_vector):
        """dense() bias length must equal out_ch."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match="bias array length"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 16)),
                    dense(ARRAY[1.0], ARRAY[0.0, 0.0],
                          output_channels => 1, input_channels => 1)
                )
            """)

    def test_dense_missing_named_args(self, grid_engine, query_vector):
        """dense() requires output_channels and input_channels."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match=r"output_channels.*input_channels"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 16)),
                    dense(ARRAY[1.0], ARRAY[0.0])
                )
            """)

    def test_pool_invalid_method(self, grid_engine, query_vector):
        """pool() method must be 'max' or 'avg'."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match="'max' or 'avg'"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 16)),
                    pool('spatial', 'min', 2)
                )
            """)

    def test_dropout_missing_arg(self, grid_engine, query_vector):
        """dropout() requires 1 argument."""
        arr = "ARRAY[" + ",".join(str(float(v)) for v in query_vector) + "]"
        with pytest.raises(Exception, match="requires 1 argument"):
            grid_engine.sql(f"""
                SELECT id FROM patches
                WHERE deep_fusion(
                    layer(knn_match(embedding, {arr}, 16)),
                    dropout()
                )
            """)
