#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""deep_learn() Training Pipeline on MNIST.

Paper 4 proves neural networks emerge from Bayesian inference.
"Training" is analytical parameter estimation, not backpropagation:

    ConvLayer:    MLE from spatial autocorrelation
    PoolLayer:    stateless (no parameters)
    FlattenLayer: stateless
    DenseLayer:   ridge regression W = (X^T X + lambda I)^{-1} X^T Y
    SoftmaxLayer: stateless

Demonstrates:
  1. Download and load MNIST data (gzip IDX format)
  2. Create table + grid graph
  3. Train via deep_learn() SQL
  4. Predict via deep_predict() SQL
  5. Show equivalent deep_fusion() query with learned weights
  6. Evaluate accuracy on test samples
"""

from __future__ import annotations

import gzip
import os
import struct
import time
import urllib.request

import numpy as np

from uqa.engine import Engine

# ======================================================================
# 1. MNIST data loading (gzip IDX format, standard library only)
# ======================================================================

MNIST_URL = "https://ossci-datasets.s3.amazonaws.com/mnist"
MNIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "mnist")


def _ensure_downloaded(filename: str) -> str:
    """Download MNIST file if not present."""
    os.makedirs(MNIST_DIR, exist_ok=True)
    filepath = os.path.join(MNIST_DIR, filename)
    if not os.path.exists(filepath):
        url = f"{MNIST_URL}/{filename}"
        print(f"  Downloading {url} ...")
        urllib.request.urlretrieve(url, filepath)
    return filepath


def _read_idx_images(filepath: str) -> np.ndarray:
    """Read IDX image file -> (N, 784) float32 normalized to [0, 1]."""
    with gzip.open(filepath, "rb") as f:
        magic, n_images, rows, cols = struct.unpack(">IIII", f.read(16))
        assert magic == 2051
        data = np.frombuffer(f.read(), dtype=np.uint8)
        return data.reshape(n_images, rows * cols).astype(np.float32) / 255.0


def _read_idx_labels(filepath: str) -> np.ndarray:
    """Read IDX label file -> (N,) int."""
    with gzip.open(filepath, "rb") as f:
        magic, n_labels = struct.unpack(">II", f.read(8))
        assert magic == 2049
        return np.frombuffer(f.read(), dtype=np.uint8)


def load_mnist(
    n_train: int = 500, n_test: int = 100
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load a subset of MNIST for demonstration."""
    train_images = _read_idx_images(_ensure_downloaded("train-images-idx3-ubyte.gz"))
    train_labels = _read_idx_labels(_ensure_downloaded("train-labels-idx1-ubyte.gz"))
    test_images = _read_idx_images(_ensure_downloaded("t10k-images-idx3-ubyte.gz"))
    test_labels = _read_idx_labels(_ensure_downloaded("t10k-labels-idx1-ubyte.gz"))

    return (
        train_images[:n_train],
        train_labels[:n_train],
        test_images[:n_test],
        test_labels[:n_test],
    )


# ======================================================================
# 2. Setup engine, table, and grid graph
# ======================================================================

print("=" * 70)
print("deep_learn() Training Pipeline on MNIST")
print("=" * 70)

print("\n  Loading MNIST data ...")
X_train, y_train, X_test, y_test = load_mnist(n_train=60000, n_test=10000)
print(f"  Train: {len(X_train)} samples, Test: {len(X_test)} samples")
print("  Image size: 28x28 = 784 pixels")
print(f"  Classes: {sorted(set(y_train))}")

engine = Engine()

engine.sql("""
    CREATE TABLE mnist_train (
        id SERIAL PRIMARY KEY,
        label INTEGER NOT NULL,
        embedding VECTOR(784)
    )
""")

print("\n  Inserting training data ...")
t0 = time.time()
for i in range(len(X_train)):
    engine.sql(
        "INSERT INTO mnist_train (label, embedding) VALUES ($1, $2)",
        params=[int(y_train[i]), X_train[i]],
    )
insert_time = time.time() - t0
print(f"  Inserted {len(X_train)} samples in {insert_time:.2f}s")

# Build 28x28 grid graph (4-connected: right + down edges)
print("\n  Building 28x28 grid graph (4-connected) ...")
t0 = time.time()
grid_result = engine.sql("""
    SELECT * FROM build_grid_graph('mnist_train', 28, 28, 'spatial')
""")
graph_time = time.time() - t0
print(f"  Created {grid_result.rows[0]['edges']} edges in {graph_time:.2f}s")


# ======================================================================
# 3. Train via deep_learn() SQL
# ======================================================================

print("\n" + "=" * 60)
print("3. Training via deep_learn() SQL")
print("=" * 60)
print(
    "\n  Architecture: conv(32ch) -> pool -> conv(64ch) -> pool"
    " -> flatten -> dense(10) -> softmax"
    "\n  Random multi-channel conv (prior) + ridge regression (posterior)"
    "\n  Gating: relu, Lambda: 1.0"
    "\n  No backpropagation -- analytical parameter estimation"
)

t0 = time.time()
result = engine.sql("""
    SELECT deep_learn(
        'mnist_cnn', label, embedding, 'spatial',
        convolve(n_channels => 32),
        pool('max', 2),
        convolve(n_channels => 64),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist_train
""")
train_time = time.time() - t0

row = result.rows[0]["deep_learn"]
print(f"\n  Training completed in {train_time:.2f}s")
print(f"  Model name:         {row['model_name']}")
print(f"  Training samples:   {row['training_samples']}")
print(f"  Number of classes:  {row['num_classes']}")
print(f"  Feature dimension:  {row['feature_dim']}")
print(f"  Training accuracy:  {row['training_accuracy']:.4f}")


# ======================================================================
# 4. Predict via deep_predict() SQL
# ======================================================================

print("\n" + "=" * 60)
print("4. Inference via deep_predict() SQL")
print("=" * 60)

# Pick a sample from the test set
sample_idx = 0
sample_label = int(y_test[sample_idx])

predictions = engine.deep_predict("mnist_cnn", X_test[sample_idx].tolist())

print(f"\n  Test sample {sample_idx}: true label = {sample_label}")
print("  Predicted class probabilities:")
for ci, prob in predictions[:5]:
    config_tmp = engine.load_model("mnist_cnn")
    cl = config_tmp["class_labels"]
    label = cl[ci] if ci < len(cl) else ci
    marker = " <--" if label == sample_label else ""
    print(f"    class {label}: {prob:.4f}{marker}")
if len(predictions) > 5:
    print(f"    ... ({len(predictions) - 5} more classes)")


# ======================================================================
# 5. Evaluate accuracy on test set
# ======================================================================

print("\n" + "=" * 60)
print("5. Test Set Evaluation")
print("=" * 60)

correct = 0
t0 = time.time()
for i in range(len(X_test)):
    predictions = engine.deep_predict("mnist_cnn", X_test[i].tolist())
    predicted_class = predictions[0][0]  # highest probability
    config = engine.load_model("mnist_cnn")
    class_labels = config["class_labels"] if config else []
    if predicted_class < len(class_labels):
        pred_label = class_labels[predicted_class]
    else:
        pred_label = predicted_class
    if pred_label == int(y_test[i]):
        correct += 1
eval_time = time.time() - t0

test_accuracy = correct / len(X_test)
print(f"\n  Test samples:   {len(X_test)}")
print(f"  Correct:        {correct}")
print(f"  Test accuracy:  {test_accuracy:.4f}")
print(f"  Eval time:      {eval_time:.2f}s")


# ======================================================================
# 6. deep_fusion(embed(), model()) with learned weights
# ======================================================================

print("\n" + "=" * 60)
print("6. deep_fusion(embed(), model()) with Learned Weights")
print("=" * 60)

config = engine.load_model("mnist_cnn")
assert config is not None

in_ch = config["dense_input_channels"]
out_ch = config["dense_output_channels"]
dense_w_arr = np.array(config["dense_weights"])
print(f"\n  Conv kernels: {len(config.get('conv_kernel_shapes', []))} stages")
for i, shape in enumerate(config.get("conv_kernel_shapes", [])):
    print(f"    Stage {i}: {shape} (random, Kaiming init)")
print(f"\n  Dense layer: {in_ch} -> {out_ch}")
print(f"    Weight norm: {np.linalg.norm(dense_w_arr):.4f}")
n_experts = len(config.get("expert_weights", [])) + 1
print(f"\n  PoE experts: {n_experts} (Theorem 8.3)")

# Build grid table for deep_fusion
print("\n  Building 28x28 grid table ...")
engine.sql("""
    CREATE TABLE grid_28x28 (
        id SERIAL PRIMARY KEY,
        pixel TEXT NOT NULL
    )
""")
for px in range(784):
    engine.sql(f"INSERT INTO grid_28x28 (pixel) VALUES ('px{px}')")
engine.sql("SELECT * FROM build_grid_graph('grid_28x28', 28, 28, 'spatial')")

# model('mnist_cnn') loads multi-channel kernels + dense weights from catalog
print("\n  Executing deep_fusion(model('mnist_cnn', $1)) ...")
t0 = time.time()
fusion_result = engine.sql(
    """
    SELECT id, _score, class_probs FROM grid_28x28
    WHERE deep_fusion(
        model('mnist_cnn', $1),
        gating => 'relu'
    ) ORDER BY _score DESC
""",
    params=[X_test[0]],
)
fusion_time = time.time() - t0
print(f"  deep_fusion() completed in {fusion_time:.2f}s")

fusion_probs = fusion_result.rows[0].get("class_probs", [])
print(f"\n  deep_fusion() class probabilities (sample 0, true label = {sample_label}):")
sorted_probs = sorted(enumerate(fusion_probs), key=lambda x: -x[1])
for ci, cp in sorted_probs[:5]:
    class_labels = config.get("class_labels", [])
    label = class_labels[ci] if ci < len(class_labels) else ci
    marker = " <--" if label == sample_label else ""
    print(f"    class {label}: {cp:.4f}{marker}")


print("\n" + "=" * 70)
print("MNIST demonstration completed successfully.")
print("=" * 70)
