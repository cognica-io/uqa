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
    PoolSpec,
    SoftmaxSpec,
    TrainedModel,
    _dicts_to_specs,
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
