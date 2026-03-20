#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Neural network pruning via deep_learn() on MNIST.

Block-WAND pruning (Paper 4, neural-index research) applied to
analytical CNN training. Three independent pruning techniques:

  1. Elastic Net (L1+L2): proximal gradient descent creates sparse weights
  2. Magnitude Pruning: post-training threshold zeroes smallest weights
  3. Combined: L1 sparsity + magnitude pruning for maximum compression

Demonstrates:
  - Accuracy vs sparsity trade-off across pruning configurations
  - Weight distribution before and after pruning
  - Inference with pruned models (same deep_predict() API)

Same analytical training -- no backpropagation:
  ConvLayer:  random multi-channel kernels (Kaiming prior)
  DenseLayer: ridge/elastic net regression (Bayesian posterior)
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
# 1. MNIST data loading
# ======================================================================

MNIST_URL = "https://ossci-datasets.s3.amazonaws.com/mnist"
MNIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "mnist")


def _ensure_downloaded(filename: str) -> str:
    os.makedirs(MNIST_DIR, exist_ok=True)
    filepath = os.path.join(MNIST_DIR, filename)
    if not os.path.exists(filepath):
        url = f"{MNIST_URL}/{filename}"
        print(f"  Downloading {url} ...")
        urllib.request.urlretrieve(url, filepath)
    return filepath


def _read_idx_images(filepath: str) -> np.ndarray:
    with gzip.open(filepath, "rb") as f:
        magic, n_images, rows, cols = struct.unpack(">IIII", f.read(16))
        assert magic == 2051
        data = np.frombuffer(f.read(), dtype=np.uint8)
        return data.reshape(n_images, rows * cols).astype(np.float32) / 255.0


def _read_idx_labels(filepath: str) -> np.ndarray:
    with gzip.open(filepath, "rb") as f:
        magic, n_labels = struct.unpack(">II", f.read(8))
        assert magic == 2049
        return np.frombuffer(f.read(), dtype=np.uint8)


def load_mnist(
    n_train: int = 60000, n_test: int = 10000
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
# Helpers
# ======================================================================


def evaluate(engine: Engine, model_name: str, X_test, y_test) -> float:
    """Evaluate test accuracy for a trained model."""
    config = engine.load_model(model_name)
    class_labels = config["class_labels"] if config else []
    correct = 0
    for i in range(len(X_test)):
        predictions = engine.deep_predict(model_name, X_test[i].tolist())
        pred_idx = predictions[0][0]
        pred_label = (
            class_labels[pred_idx] if pred_idx < len(class_labels) else pred_idx
        )
        if pred_label == int(y_test[i]):
            correct += 1
    return correct / len(X_test)


def weight_stats(engine: Engine, model_name: str) -> dict:
    """Compute weight statistics for a trained model."""
    config = engine.load_model(model_name)
    W = np.array(config["dense_weights"])
    total = len(W)
    zeros = int(np.sum(W == 0))
    return {
        "total_weights": total,
        "zero_weights": zeros,
        "sparsity": zeros / total if total > 0 else 0.0,
        "weight_norm": float(np.linalg.norm(W)),
        "weight_mean_abs": float(np.mean(np.abs(W))),
    }


# ======================================================================
# 2. Setup
# ======================================================================

print("=" * 70)
print("Neural Network Pruning via deep_learn() on MNIST")
print("=" * 70)

print("\n  Loading MNIST data ...")
X_train, y_train, X_test, y_test = load_mnist(n_train=60000, n_test=10000)
print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

engine = Engine()

engine.sql("""
    CREATE TABLE mnist (
        id SERIAL PRIMARY KEY,
        label INTEGER NOT NULL,
        embedding VECTOR(784)
    )
""")

print("  Inserting training data ...")
t0 = time.time()
for i in range(len(X_train)):
    engine.sql(
        "INSERT INTO mnist (label, embedding) VALUES ($1, $2)",
        params=[int(y_train[i]), X_train[i]],
    )
print(f"  Inserted {len(X_train)} samples in {time.time() - t0:.2f}s")

print("  Building 28x28 grid graph ...")
engine.sql("SELECT * FROM build_grid_graph('mnist', 28, 28, 'spatial')")


# ======================================================================
# 3. Baseline: no pruning
# ======================================================================

print("\n" + "=" * 60)
print("3. Baseline: Ridge Regression (no pruning)")
print("=" * 60)

t0 = time.time()
result = engine.sql("""
    SELECT deep_learn(
        'baseline', label, embedding, 'spatial',
        convolve(n_channels => 32),
        pool('max', 2),
        convolve(n_channels => 64),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist
""")
train_time = time.time() - t0
row = result.rows[0]["deep_learn"]
print(f"\n  Training: {train_time:.2f}s")
print(f"  Training accuracy: {row['training_accuracy']:.4f}")

t0 = time.time()
test_acc = evaluate(engine, "baseline", X_test, y_test)
eval_time = time.time() - t0
stats = weight_stats(engine, "baseline")
print(f"  Test accuracy:     {test_acc:.4f} ({eval_time:.1f}s)")
print(
    f"  Weight sparsity:   {stats['sparsity']:.2%} ({stats['zero_weights']}/{stats['total_weights']})"
)
print(f"  Weight norm:       {stats['weight_norm']:.4f}")


# ======================================================================
# 4. Elastic Net (L1 regularization)
# ======================================================================

print("\n" + "=" * 60)
print("4. Elastic Net: L1 + L2 Regularization")
print("=" * 60)

print("\n  L1 creates weight sparsity via proximal gradient descent.")
print("  Warm-started from ridge solution for fast convergence.\n")

for l1r in [0.1, 0.3, 0.5, 0.7]:
    name = f"elastic_{int(l1r * 100)}"
    t0 = time.time()
    result = engine.sql(f"""
        SELECT deep_learn(
            '{name}', label, embedding, 'spatial',
            convolve(n_channels => 32),
            pool('max', 2),
            convolve(n_channels => 64),
            pool('max', 2),
            flatten(),
            dense(output_channels => 10),
            softmax(),
            gating => 'relu', lambda => 1.0, l1_ratio => {l1r}
        ) FROM mnist
    """)
    train_time = time.time() - t0
    row = result.rows[0]["deep_learn"]
    test_acc = evaluate(engine, name, X_test, y_test)
    stats = weight_stats(engine, name)
    print(
        f"  l1_ratio={l1r:.1f}  "
        f"train={row['training_accuracy']:.4f}  "
        f"test={test_acc:.4f}  "
        f"sparsity={stats['sparsity']:.1%}  "
        f"norm={stats['weight_norm']:.2f}  "
        f"({train_time:.1f}s)"
    )


# ======================================================================
# 5. Magnitude Pruning
# ======================================================================

print("\n" + "=" * 60)
print("5. Magnitude Pruning: Post-Training Weight Removal")
print("=" * 60)

print("\n  Train with ridge, then zero out smallest weights.\n")

for pr in [0.5, 0.7, 0.8, 0.9]:
    name = f"pruned_{int(pr * 100)}"
    t0 = time.time()
    result = engine.sql(f"""
        SELECT deep_learn(
            '{name}', label, embedding, 'spatial',
            convolve(n_channels => 32),
            pool('max', 2),
            convolve(n_channels => 64),
            pool('max', 2),
            flatten(),
            dense(output_channels => 10),
            softmax(),
            gating => 'relu', lambda => 1.0, prune_ratio => {pr}
        ) FROM mnist
    """)
    train_time = time.time() - t0
    row = result.rows[0]["deep_learn"]
    test_acc = evaluate(engine, name, X_test, y_test)
    stats = weight_stats(engine, name)
    print(
        f"  prune_ratio={pr:.1f}  "
        f"train={row['training_accuracy']:.4f}  "
        f"test={test_acc:.4f}  "
        f"sparsity={stats['sparsity']:.1%}  "
        f"norm={stats['weight_norm']:.2f}  "
        f"({train_time:.1f}s)"
    )


# ======================================================================
# 6. Combined: Elastic Net + Magnitude Pruning
# ======================================================================

print("\n" + "=" * 60)
print("6. Combined: L1 Sparsity + Magnitude Pruning")
print("=" * 60)

print("\n  L1 creates natural sparsity pattern, magnitude pruning amplifies it.\n")

combos = [
    (0.3, 0.5),
    (0.3, 0.8),
    (0.5, 0.7),
    (0.5, 0.9),
]

for l1r, pr in combos:
    name = f"combo_{int(l1r * 100)}_{int(pr * 100)}"
    t0 = time.time()
    result = engine.sql(f"""
        SELECT deep_learn(
            '{name}', label, embedding, 'spatial',
            convolve(n_channels => 32),
            pool('max', 2),
            convolve(n_channels => 64),
            pool('max', 2),
            flatten(),
            dense(output_channels => 10),
            softmax(),
            gating => 'relu', lambda => 1.0,
            l1_ratio => {l1r}, prune_ratio => {pr}
        ) FROM mnist
    """)
    train_time = time.time() - t0
    row = result.rows[0]["deep_learn"]
    test_acc = evaluate(engine, name, X_test, y_test)
    stats = weight_stats(engine, name)
    print(
        f"  l1={l1r:.1f} prune={pr:.1f}  "
        f"train={row['training_accuracy']:.4f}  "
        f"test={test_acc:.4f}  "
        f"sparsity={stats['sparsity']:.1%}  "
        f"norm={stats['weight_norm']:.2f}  "
        f"({train_time:.1f}s)"
    )


# ======================================================================
# 7. Summary
# ======================================================================

print("\n" + "=" * 60)
print("7. Summary: Accuracy vs Sparsity")
print("=" * 60)

print(f"\n  {'Model':<25} {'Test Acc':>9} {'Sparsity':>9} {'W Norm':>9}")
print("  " + "-" * 55)

models = ["baseline"]
models += [f"elastic_{int(l1r * 100)}" for l1r in [0.1, 0.3, 0.5, 0.7]]
models += [f"pruned_{int(pr * 100)}" for pr in [0.5, 0.7, 0.8, 0.9]]
models += [f"combo_{int(l1r * 100)}_{int(pr * 100)}" for l1r, pr in combos]

for name in models:
    stats = weight_stats(engine, name)
    test_acc = evaluate(engine, name, X_test, y_test)
    print(
        f"  {name:<25} {test_acc:>8.2%} {stats['sparsity']:>8.1%} "
        f"{stats['weight_norm']:>9.2f}"
    )


print("\n" + "=" * 70)
print("Pruning demonstration completed successfully.")
print("=" * 70)
