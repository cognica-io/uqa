#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for deep_learn() training pipeline and deep_predict() inference."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.engine import Engine
from uqa.operators._backend import ridge_solve
from uqa.operators.deep_learn import (
    ConvSpec,
    DenseSpec,
    FlattenSpec,
    GlobalPoolSpec,
    PoolSpec,
    SoftmaxSpec,
    TrainedModel,
    _dicts_to_specs,
    _generate_kernels,
    _specs_to_dicts,
)

# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def grid_engine() -> Engine:
    """Engine with a 4x4 grid of labeled image patches.

    Creates 8 samples total: 4 'cat' (top rows) and 4 'dog' (bottom rows)
    on a 4x4 grid with 4-connected spatial graph edges.
    Each sample has a 16-dimensional embedding (4x4 grid pixels).
    """
    e = Engine()
    e.sql("""
        CREATE TABLE images (
            id SERIAL PRIMARY KEY,
            label TEXT NOT NULL,
            embedding VECTOR(16)
        )
    """)

    rng = np.random.RandomState(42)

    # Create labeled samples with distinct patterns
    for i in range(8):
        if i < 4:
            # 'cat' pattern: bright top-left
            base = np.zeros(16, dtype=np.float32)
            base[:8] = 0.8
            label = "cat"
        else:
            # 'dog' pattern: bright bottom-right
            base = np.zeros(16, dtype=np.float32)
            base[8:] = 0.8
            label = "dog"

        vec = base + rng.randn(16).astype(np.float32) * 0.1
        vec = np.clip(vec, 0.0, 1.0)
        arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        e.sql(f"INSERT INTO images (label, embedding) VALUES ('{label}', {arr})")

    # Build 4-connected grid graph (4x4 = 16 nodes)
    e.sql("SELECT * FROM build_grid_graph('images', 4, 4, 'spatial')")

    return e


# ----------------------------------------------------------------
# Unit tests: ridge regression
# ----------------------------------------------------------------


class TestRidgeRegression:
    def test_exact_solution_no_regularization(self):
        """With lambda=0, ridge regression should match OLS."""
        X = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        Y = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        W, bias = ridge_solve(X, Y, lam=0.0)
        predictions = X @ W.T + bias
        np.testing.assert_allclose(predictions, Y, atol=0.3)

    def test_regularization_shrinks_weights(self):
        """Higher lambda should produce smaller weight norms."""
        rng = np.random.RandomState(42)
        X = rng.randn(20, 5)
        Y = rng.randn(20, 3)

        W_low, _ = ridge_solve(X, Y, lam=0.01)
        W_high, _ = ridge_solve(X, Y, lam=100.0)

        norm_low = np.linalg.norm(W_low)
        norm_high = np.linalg.norm(W_high)
        assert norm_high < norm_low

    def test_output_shapes(self):
        """W should be (n_classes, n_features), bias (n_classes,)."""
        X = np.random.randn(10, 4)
        Y = np.random.randn(10, 3)
        W, bias = ridge_solve(X, Y, lam=1.0)
        assert W.shape == (3, 4)
        assert bias.shape == (3,)

    def test_single_feature_single_class(self):
        """Degenerate case: 1 feature, 1 class."""
        X = np.array([[1.0], [2.0], [3.0]])
        Y = np.array([[2.0], [4.0], [6.0]])
        W, bias = ridge_solve(X, Y, lam=0.0)
        pred = X @ W.T + bias
        np.testing.assert_allclose(pred, Y, atol=0.01)


# ----------------------------------------------------------------
# Unit tests: LayerSpec serialization
# ----------------------------------------------------------------


class TestLayerSpecSerialization:
    def test_specs_to_dicts_roundtrip(self):
        specs = [
            ConvSpec(kernel_hops=2),
            PoolSpec(method="avg", pool_size=3),
            FlattenSpec(),
            DenseSpec(output_channels=5),
            SoftmaxSpec(),
        ]
        dicts = _specs_to_dicts(specs)
        recovered = _dicts_to_specs(dicts)
        assert len(recovered) == len(specs)
        assert isinstance(recovered[0], ConvSpec)
        assert recovered[0].kernel_hops == 2
        assert isinstance(recovered[1], PoolSpec)
        assert recovered[1].method == "avg"
        assert recovered[1].pool_size == 3
        assert isinstance(recovered[2], FlattenSpec)
        assert isinstance(recovered[3], DenseSpec)
        assert recovered[3].output_channels == 5
        assert isinstance(recovered[4], SoftmaxSpec)

    def test_trained_model_json_roundtrip(self):
        model = TrainedModel(
            model_name="test_model",
            table_name="test_table",
            label_field="label",
            embedding_field="embedding",
            edge_label="spatial",
            gating="relu",
            lam=1.0,
            layer_specs=[{"type": "conv", "kernel_hops": 1}],
            conv_weights=[[0.6, 0.4]],
            dense_weights=[1.0, 2.0, 3.0, 4.0],
            dense_bias=[0.1, 0.2],
            dense_input_channels=2,
            dense_output_channels=2,
            num_classes=2,
            class_labels=["cat", "dog"],
            grid_size=4,
            embedding_dim=16,
            training_accuracy=0.85,
            training_samples=100,
        )
        json_str = model.to_json()
        recovered = TrainedModel.from_json(json_str)
        assert recovered.model_name == "test_model"
        assert recovered.conv_weights == [[0.6, 0.4]]
        assert recovered.dense_weights == [1.0, 2.0, 3.0, 4.0]
        assert recovered.training_accuracy == 0.85

    def test_to_deep_fusion_layers(self):
        """Trained model should produce valid deep_fusion layers."""
        from uqa.operators.deep_fusion import (
            ConvLayer,
            DenseLayer,
            FlattenLayer,
            SoftmaxLayer,
        )

        model = TrainedModel(
            model_name="test",
            table_name="t",
            label_field="label",
            embedding_field="emb",
            edge_label="spatial",
            gating="none",
            lam=1.0,
            layer_specs=[
                {"type": "conv", "kernel_hops": 1},
                {"type": "flatten"},
                {"type": "dense", "output_channels": 2},
                {"type": "softmax"},
            ],
            conv_weights=[[0.7, 0.3]],
            dense_weights=[1.0, 2.0, 3.0, 4.0],
            dense_bias=[0.0, 0.0],
            dense_input_channels=2,
            dense_output_channels=2,
            num_classes=2,
            class_labels=["a", "b"],
        )
        layers = model.to_deep_fusion_layers()
        assert len(layers) == 4
        assert isinstance(layers[0], ConvLayer)
        assert layers[0].hop_weights == (0.7, 0.3)
        assert isinstance(layers[1], FlattenLayer)
        assert isinstance(layers[2], DenseLayer)
        assert layers[2].output_channels == 2
        assert isinstance(layers[3], SoftmaxLayer)


# ----------------------------------------------------------------
# Integration tests: train + predict via Python API
# ----------------------------------------------------------------


class TestDeepLearnAPI:
    def test_train_and_predict(self, grid_engine):
        """End-to-end: train a model and predict with it."""
        result = grid_engine.deep_learn(
            model_name="test_clf",
            table_name="images",
            label_field="label",
            embedding_field="embedding",
            edge_label="spatial",
            layer_specs=[
                ConvSpec(kernel_hops=1),
                PoolSpec(method="max", pool_size=2),
                FlattenSpec(),
                DenseSpec(output_channels=2),
                SoftmaxSpec(),
            ],
            gating="relu",
            lam=1.0,
        )

        assert result["model_name"] == "test_clf"
        assert result["num_classes"] == 2
        assert result["training_samples"] == 8
        assert 0.0 <= result["training_accuracy"] <= 1.0

        # Predict with a 'cat'-like input
        cat_input = [0.8] * 8 + [0.0] * 8
        predictions = grid_engine.deep_predict("test_clf", cat_input)
        assert len(predictions) == 2
        # Probabilities should sum to ~1
        total_prob = sum(p for _, p in predictions)
        assert total_prob == pytest.approx(1.0, abs=1e-6)

    def test_predict_nonexistent_model(self, grid_engine):
        with pytest.raises(ValueError, match="does not exist"):
            grid_engine.deep_predict("nonexistent", [0.0] * 16)

    def test_train_empty_table(self):
        e = Engine()
        e.sql("""
            CREATE TABLE empty (
                id SERIAL PRIMARY KEY,
                label TEXT NOT NULL,
                embedding VECTOR(4)
            )
        """)
        with pytest.raises(ValueError, match="no documents"):
            e.deep_learn(
                model_name="fail",
                table_name="empty",
                label_field="label",
                embedding_field="embedding",
                edge_label="spatial",
                layer_specs=[
                    FlattenSpec(),
                    DenseSpec(output_channels=2),
                    SoftmaxSpec(),
                ],
            )


# ----------------------------------------------------------------
# Pruning tests
# ----------------------------------------------------------------


class TestPruning:
    def test_elastic_net(self, grid_engine):
        """L1 regularization should produce sparser weights."""
        result = grid_engine.deep_learn(
            model_name="l1_model",
            table_name="images",
            label_field="label",
            embedding_field="embedding",
            edge_label="spatial",
            layer_specs=[
                FlattenSpec(),
                DenseSpec(output_channels=2),
                SoftmaxSpec(),
            ],
            gating="relu",
            lam=1.0,
            l1_ratio=0.5,
        )
        assert result["l1_ratio"] == 0.5
        assert result["num_classes"] == 2
        # Should still predict
        predictions = grid_engine.deep_predict("l1_model", [0.8] * 8 + [0.0] * 8)
        assert len(predictions) == 2
        total = sum(p for _, p in predictions)
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_magnitude_pruning(self, grid_engine):
        """Magnitude pruning should create sparse weights."""
        result = grid_engine.deep_learn(
            model_name="pruned_model",
            table_name="images",
            label_field="label",
            embedding_field="embedding",
            edge_label="spatial",
            layer_specs=[
                FlattenSpec(),
                DenseSpec(output_channels=2),
                SoftmaxSpec(),
            ],
            lam=1.0,
            prune_ratio=0.5,
        )
        assert result["prune_ratio"] == 0.5
        assert result["weight_sparsity"] > 0
        # Should still predict
        predictions = grid_engine.deep_predict("pruned_model", [0.8] * 8 + [0.0] * 8)
        assert len(predictions) == 2

    def test_elastic_net_plus_pruning(self, grid_engine):
        """Combined L1 + magnitude pruning."""
        result = grid_engine.deep_learn(
            model_name="combo_model",
            table_name="images",
            label_field="label",
            embedding_field="embedding",
            edge_label="spatial",
            layer_specs=[
                FlattenSpec(),
                DenseSpec(output_channels=2),
                SoftmaxSpec(),
            ],
            lam=1.0,
            l1_ratio=0.3,
            prune_ratio=0.5,
        )
        assert result["weight_sparsity"] > 0
        predictions = grid_engine.deep_predict("combo_model", [0.8] * 8 + [0.0] * 8)
        total = sum(p for _, p in predictions)
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_pruning_sql(self, grid_engine):
        """Pruning via SQL named args."""
        result = grid_engine.sql("""
            SELECT deep_learn(
                'sql_pruned', label, embedding, 'spatial',
                flatten(),
                dense(output_channels => 2),
                softmax(),
                lambda => 1.0,
                l1_ratio => 0.3,
                prune_ratio => 0.5
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        assert row["l1_ratio"] == 0.3
        assert row["prune_ratio"] == 0.5


# ----------------------------------------------------------------
# SQL syntax tests
# ----------------------------------------------------------------


class TestDeepLearnSQL:
    def test_deep_learn_sql(self, grid_engine):
        """Train via SQL syntax."""
        result = grid_engine.sql("""
            SELECT deep_learn(
                'sql_model', label, embedding, 'spatial',
                convolve(kernel_hops => 1),
                pool('max', 2),
                flatten(),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        assert len(result.rows) == 1
        row = result.rows[0]
        assert row["deep_learn"]["model_name"] == "sql_model"
        assert row["deep_learn"]["num_classes"] == 2
        assert row["deep_learn"]["training_samples"] == 8

    def test_deep_predict_sql(self, grid_engine):
        """Train then predict via SQL scalar function."""
        grid_engine.sql("""
            SELECT deep_learn(
                'pred_model', label, embedding, 'spatial',
                convolve(kernel_hops => 1),
                pool('max', 2),
                flatten(),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)

        predictions = grid_engine.deep_predict("pred_model", [0.8] * 8 + [0.0] * 8)
        assert len(predictions) == 2
        total = sum(p for _, p in predictions)
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_deep_predict_per_row(self, grid_engine):
        """Predict as per-row scalar function on table rows."""
        grid_engine.sql("""
            SELECT deep_learn(
                'row_model', label, embedding, 'spatial',
                flatten(),
                dense(output_channels => 2),
                softmax(),
                lambda => 1.0
            ) FROM images
        """)

        result = grid_engine.sql("""
            SELECT id, deep_predict('row_model', embedding) as pred
            FROM images WHERE id <= 2
        """)
        assert len(result.rows) == 2
        for row in result.rows:
            assert "pred" in row

    def test_deep_learn_no_layers_raises(self, grid_engine):
        with pytest.raises(ValueError, match="requires at least one layer"):
            grid_engine.sql("""
                SELECT deep_learn(
                    'fail', label, embedding, 'spatial'
                ) FROM images
            """)


# ----------------------------------------------------------------
# Compatibility: deep_predict == deep_fusion output
# ----------------------------------------------------------------


class TestDeepPredictFusionCompat:
    def test_predict_matches_fusion_simple(self, grid_engine):
        """deep_predict output should match deep_fusion with same weights (no conv/pool)."""
        grid_engine.sql("""
            SELECT deep_learn(
                'compat_model', label, embedding, 'spatial',
                flatten(),
                dense(output_channels => 2),
                softmax(),
                lambda => 1.0
            ) FROM images
        """)

        test_input = [0.8] * 8 + [0.0] * 8
        predictions = grid_engine.deep_predict("compat_model", test_input)

        probs = dict(predictions)
        assert len(probs) == 2
        total = sum(probs.values())
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_predict_poe_with_conv_pool(self, grid_engine):
        """PoE predict with conv+pool must produce valid probabilities."""
        grid_engine.sql("""
            SELECT deep_learn(
                'eq_model', label, embedding, 'spatial',
                convolve(kernel_hops => 1),
                pool('max', 2),
                flatten(),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)

        # 'cat'-like input
        predictions = grid_engine.deep_predict("eq_model", [0.8] * 8 + [0.0] * 8)
        probs = dict(predictions)
        assert len(probs) == 2
        assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)

        # 'dog'-like input should give different ranking
        predictions_dog = grid_engine.deep_predict("eq_model", [0.0] * 8 + [0.8] * 8)
        probs_dog = dict(predictions_dog)
        assert sum(probs_dog.values()) == pytest.approx(1.0, abs=1e-6)


# ----------------------------------------------------------------
# Catalog persistence
# ----------------------------------------------------------------


class TestModelCatalogPersistence:
    def test_save_and_load_model(self, tmp_path):
        """Models should persist across engine restarts."""
        db_path = str(tmp_path / "test.db")

        # Train with first engine instance
        e1 = Engine(db_path=db_path)
        e1.sql("""
            CREATE TABLE images (
                id SERIAL PRIMARY KEY,
                label TEXT NOT NULL,
                embedding VECTOR(4)
            )
        """)

        rng = np.random.RandomState(42)
        for i in range(4):
            label = "a" if i < 2 else "b"
            vec = rng.randn(4).astype(np.float32)
            arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
            e1.sql(f"INSERT INTO images (label, embedding) VALUES ('{label}', {arr})")

        # Build grid graph for 2x2
        e1.sql("SELECT * FROM build_grid_graph('images', 2, 2, 'spatial')")

        e1.sql("""
            SELECT deep_learn(
                'persist_model', label, embedding, 'spatial',
                flatten(),
                dense(output_channels => 2),
                softmax(),
                lambda => 1.0
            ) FROM images
        """)
        e1.close()

        # Load with second engine instance
        e2 = Engine(db_path=db_path)
        config = e2.load_model("persist_model")
        assert config is not None
        assert config["model_name"] == "persist_model"
        assert config["num_classes"] == 2

        # Predict should still work
        predictions = e2.deep_predict("persist_model", [0.5, 0.5, 0.0, 0.0])
        assert len(predictions) == 2
        e2.close()

    def test_delete_model(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        e = Engine(db_path=db_path)
        e.save_model("to_delete", {"model_name": "to_delete"})
        assert e.load_model("to_delete") is not None
        e.delete_model("to_delete")
        assert e.load_model("to_delete") is None
        e.close()


# ----------------------------------------------------------------
# Tests: Global Pooling
# ----------------------------------------------------------------


class TestGlobalPooling:
    def test_grid_global_pool_avg(self):
        """Global average pooling reduces (batch, C*H*W) -> (batch, C)."""
        from uqa.operators._backend import grid_global_pool

        # 2 samples, 3 channels, 4x4 spatial = 48 features
        rng = np.random.RandomState(42)
        features = rng.randn(2, 48).astype(np.float32)
        result = grid_global_pool(features, 4, 4, "avg")
        assert result.shape == (2, 3)
        # Verify: manual mean over spatial dims
        reshaped = features.reshape(2, 3, 4, 4)
        expected = reshaped.mean(axis=(2, 3))
        np.testing.assert_allclose(result, expected, atol=1e-5)

    def test_grid_global_pool_max(self):
        """Global max pooling reduces (batch, C*H*W) -> (batch, C)."""
        from uqa.operators._backend import grid_global_pool

        rng = np.random.RandomState(42)
        features = rng.randn(2, 48).astype(np.float32)
        result = grid_global_pool(features, 4, 4, "max")
        assert result.shape == (2, 3)
        reshaped = features.reshape(2, 3, 4, 4)
        expected = reshaped.max(axis=(2, 3))
        np.testing.assert_allclose(result, expected, atol=1e-5)

    def test_grid_global_pool_avg_max(self):
        """avg_max concatenates avg and max -> (batch, 2*C)."""
        from uqa.operators._backend import grid_global_pool

        rng = np.random.RandomState(42)
        features = rng.randn(2, 48).astype(np.float32)
        result = grid_global_pool(features, 4, 4, "avg_max")
        assert result.shape == (2, 6)  # 2*3 channels
        reshaped = features.reshape(2, 3, 4, 4)
        expected_avg = reshaped.mean(axis=(2, 3))
        expected_max = reshaped.max(axis=(2, 3))
        np.testing.assert_allclose(result[:, :3], expected_avg, atol=1e-5)
        np.testing.assert_allclose(result[:, 3:], expected_max, atol=1e-5)

    def test_global_pool_spec_serialization(self):
        """GlobalPoolSpec round-trips through dict serialization."""
        specs = [
            ConvSpec(n_channels=8),
            PoolSpec(),
            GlobalPoolSpec(method="avg_max"),
            DenseSpec(output_channels=3),
            SoftmaxSpec(),
        ]
        dicts = _specs_to_dicts(specs)
        assert dicts[2] == {"type": "global_pool", "method": "avg_max"}
        restored = _dicts_to_specs(dicts)
        assert isinstance(restored[2], GlobalPoolSpec)
        assert restored[2].method == "avg_max"

    def test_global_pool_training_sql(self, grid_engine):
        """Train with global_pool('avg') via SQL and verify feature dim."""
        e = grid_engine
        result = e.sql("""
            SELECT deep_learn(
                'gp_test', label, embedding, 'spatial',
                convolve(n_channels => 4),
                pool('max', 2),
                global_pool('avg'),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        # After conv(4ch) + pool(2) on 4x4 -> 2x2, global_pool('avg') -> 4-D
        assert row["feature_dim"] == 4
        assert row["num_classes"] == 2

    def test_global_pool_avg_max_training_sql(self, grid_engine):
        """Train with global_pool('avg_max') -- feature dim is 2*C."""
        e = grid_engine
        result = e.sql("""
            SELECT deep_learn(
                'gp_am_test', label, embedding, 'spatial',
                convolve(n_channels => 4),
                pool('max', 2),
                global_pool('avg_max'),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        # avg_max concatenates: 4 + 4 = 8
        assert row["feature_dim"] == 8

    def test_global_pool_predict(self, grid_engine):
        """Predictions work with global_pool-trained models."""
        e = grid_engine
        e.sql("""
            SELECT deep_learn(
                'gp_pred', label, embedding, 'spatial',
                convolve(n_channels => 4),
                pool('max', 2),
                global_pool('avg'),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        rng = np.random.RandomState(42)
        test_vec = rng.rand(16).tolist()
        predictions = e.deep_predict("gp_pred", test_vec)
        assert len(predictions) == 2
        # Probabilities sum to 1
        total_prob = sum(p for _, p in predictions)
        assert abs(total_prob - 1.0) < 0.01


# ----------------------------------------------------------------
# Tests: Kernel Initialization Modes
# ----------------------------------------------------------------


class TestKernelInitModes:
    def test_kaiming_default(self):
        """Default Kaiming init produces correct shape."""
        kernels = _generate_kernels(16, 3, seed=42)
        assert kernels.shape == (16, 3, 3, 3)
        assert kernels.dtype == np.float32

    def test_orthogonal_shape(self):
        """Orthogonal init produces correct shape."""
        kernels = _generate_kernels(16, 3, seed=42, init_mode="orthogonal")
        assert kernels.shape == (16, 3, 3, 3)

    def test_orthogonal_diversity(self):
        """Orthogonal filters have higher pairwise distances than Kaiming."""
        kaiming = _generate_kernels(32, 3, seed=42, init_mode="kaiming")
        ortho = _generate_kernels(32, 3, seed=42, init_mode="orthogonal")

        # Flatten to (n_channels, fan_in) and compute pairwise cosine similarity
        k_flat = kaiming.reshape(32, -1)
        o_flat = ortho.reshape(32, -1)

        k_norms = k_flat / np.linalg.norm(k_flat, axis=1, keepdims=True)
        o_norms = o_flat / np.linalg.norm(o_flat, axis=1, keepdims=True)

        k_cos = np.abs(k_norms @ k_norms.T)
        o_cos = np.abs(o_norms @ o_norms.T)

        # Mask diagonal
        np.fill_diagonal(k_cos, 0)
        np.fill_diagonal(o_cos, 0)

        # Orthogonal should have lower off-diagonal cosine similarity
        assert o_cos.mean() < k_cos.mean()

    def test_gabor_shape(self):
        """Gabor init produces correct shape."""
        kernels = _generate_kernels(48, 3, seed=42, init_mode="gabor")
        assert kernels.shape == (48, 3, 3, 3)

    def test_gabor_structured(self):
        """First Gabor filters should have near-zero mean (bandpass)."""
        kernels = _generate_kernels(48, 1, seed=42, init_mode="gabor")
        # First 48 filters are structured Gabor: zero-mean by construction
        for i in range(min(48, 48)):
            assert abs(kernels[i].mean()) < 0.1

    def test_kmeans_shape(self):
        """K-means init produces correct shape with training data."""
        rng = np.random.RandomState(42)
        # 20 samples of 1-channel 8x8 = 64-dim
        data = rng.randn(20, 64).astype(np.float32)
        kernels = _generate_kernels(
            8,
            1,
            seed=42,
            init_mode="kmeans",
            training_data=data,
            grid_h=8,
            grid_w=8,
        )
        assert kernels.shape == (8, 1, 3, 3)

    def test_kmeans_data_dependent(self):
        """K-means kernels differ based on training data distribution."""
        rng = np.random.RandomState(42)
        data1 = rng.randn(20, 64).astype(np.float32)
        data2 = rng.randn(20, 64).astype(np.float32) * 5.0
        k1 = _generate_kernels(
            4,
            1,
            seed=42,
            init_mode="kmeans",
            training_data=data1,
            grid_h=8,
            grid_w=8,
        )
        k2 = _generate_kernels(
            4,
            1,
            seed=42,
            init_mode="kmeans",
            training_data=data2,
            grid_h=8,
            grid_w=8,
        )
        assert not np.allclose(k1, k2)

    def test_orthogonal_training_sql(self, grid_engine):
        """Train with orthogonal init via SQL."""
        e = grid_engine
        result = e.sql("""
            SELECT deep_learn(
                'ortho_test', label, embedding, 'spatial',
                convolve(n_channels => 4, init => 'orthogonal'),
                pool('max', 2),
                flatten(),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        assert row["num_classes"] == 2
        assert row["training_accuracy"] > 0.0

    def test_gabor_training_sql(self, grid_engine):
        """Train with gabor init via SQL."""
        e = grid_engine
        result = e.sql("""
            SELECT deep_learn(
                'gabor_test', label, embedding, 'spatial',
                convolve(n_channels => 4, init => 'gabor'),
                pool('max', 2),
                flatten(),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        assert row["num_classes"] == 2

    def test_combined_global_pool_and_orthogonal(self, grid_engine):
        """Orthogonal init + global pooling combined -- the full Tier 1+2 stack."""
        e = grid_engine
        result = e.sql("""
            SELECT deep_learn(
                'combined_test', label, embedding, 'spatial',
                convolve(n_channels => 8, init => 'orthogonal'),
                pool('max', 2),
                global_pool('avg_max'),
                dense(output_channels => 2),
                softmax(),
                gating => 'relu', lambda => 1.0
            ) FROM images
        """)
        row = result.rows[0]["deep_learn"]
        # 8 channels, avg_max -> 16-D
        assert row["feature_dim"] == 16
        assert row["training_accuracy"] > 0.0

        # Verify prediction works end-to-end
        rng = np.random.RandomState(42)
        predictions = e.deep_predict("combined_test", rng.rand(16).tolist())
        assert len(predictions) == 2
        total_prob = sum(p for _, p in predictions)
        assert abs(total_prob - 1.0) < 0.01
