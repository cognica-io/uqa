#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Self-Attention in the Analytical Training Pipeline (Paper 4, Section 8).

Paper 4, Theorem 8.3 derives the attention mechanism as context-dependent
Logarithmic Opinion Pooling (Product of Experts):

    P_LogOP = sigma( sum_i  w_i(q, s_i) * logit(P_i) )

Static weights -> feedforward network     (Section 5)
Query-dependent weights -> attention       (Section 8)
Multi-head -> ensemble of parallel PoEs    (Remark 8.6)

This example compares three attention training modes on MNIST:

    "content"    -- Q=K=V=X, pure content-based attention.
                    Each position attends based on feature similarity.
                    No learned parameters.

    "random_qk"  -- Q=XW_q, K=XW_k, V=X.
                    Random projections create diverse attention patterns
                    (ELM prior). The downstream ridge regression finds
                    the optimal linear combination (posterior).

    "learned_v"  -- Q=XW_q, K=XW_k (random), V=XW_v (learned).
                    Supervised search over random orthogonal V projections
                    selects the one maximizing classification accuracy.
                    Consistent with the conv layer's grid search approach.

All training is analytical -- no backpropagation:
    ConvLayer:      random multi-channel kernels (Kaiming prior)
    AttentionLayer: content / random Q,K / learned V (see above)
    DenseLayer:     ridge regression W = (X^T X + lambda I)^{-1} X^T Y
"""

from __future__ import annotations

import gzip
import os
import struct
import time

import numpy as np

from uqa.engine import Engine
from uqa.operators._backend import device_name

# ======================================================================
# 1. MNIST data loading (same as deep_learn_mnist.py)
# ======================================================================

MNIST_URL = "https://ossci-datasets.s3.amazonaws.com/mnist"
MNIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "mnist")


def _ensure_downloaded(filename: str) -> str:
    os.makedirs(MNIST_DIR, exist_ok=True)
    filepath = os.path.join(MNIST_DIR, filename)
    if not os.path.exists(filepath):
        import urllib.request

        print(f"  Downloading {MNIST_URL}/{filename} ...")
        urllib.request.urlretrieve(f"{MNIST_URL}/{filename}", filepath)
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
    n_train: int = 500, n_test: int = 100
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
# 2. Setup
# ======================================================================

print("=" * 70)
print("Self-Attention in the Analytical Training Pipeline")
print("Paper 4, Section 8: Attention as Context-Dependent PoE")
print("=" * 70)

N_TRAIN = 60000
N_TEST = 10000
N_HEADS = 4

print(f"\n  Compute device: {device_name()}")
print(f"\n  Loading MNIST data ({N_TRAIN} train, {N_TEST} test) ...")
X_train, y_train, X_test, y_test = load_mnist(n_train=N_TRAIN, n_test=N_TEST)
print(f"  Train: {len(X_train)} samples, Test: {len(X_test)} samples")
print(f"  Image size: 28x28 = 784 pixels, Classes: {len(set(y_train))}")


# ======================================================================
# 3. Baseline: CNN without attention
# ======================================================================

print("\n" + "=" * 70)
print("3. Baseline: conv(8) -> pool -> conv(16) -> pool")
print("=" * 70)

engine = Engine()

engine.sql("""
    CREATE TABLE mnist (
        id SERIAL PRIMARY KEY,
        label INTEGER NOT NULL,
        embedding VECTOR(784)
    )
""")

print("\n  Inserting training data ...")
t0 = time.time()
for i in range(len(X_train)):
    engine.sql(
        "INSERT INTO mnist (label, embedding) VALUES ($1, $2)",
        params=[int(y_train[i]), X_train[i]],
    )
insert_time = time.time() - t0
print(f"  Inserted {len(X_train)} rows in {insert_time:.1f}s")

print("\n  Building 28x28 grid graph ...")
engine.sql("SELECT * FROM build_grid_graph('mnist', 28, 28, 'spatial')")

# Baseline CNN: no attention
print("\n  Training baseline (no attention) ...")
t0 = time.time()
result_base = engine.sql("""
    SELECT deep_learn(
        'baseline', label, embedding, 'spatial',
        convolve(n_channels => 8),
        pool('max', 2),
        convolve(n_channels => 16),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist
""")
base_time = time.time() - t0
base_acc = result_base.rows[0]["deep_learn"]["training_accuracy"]
print(f"  Train accuracy: {base_acc:.4f}  ({base_time:.1f}s)")


# ======================================================================
# 4. Attention mode: "content" (Q=K=V=X, no parameters)
# ======================================================================

print("\n" + "=" * 70)
print("4. Content-Based Attention (Q=K=V=X)")
print("   Each position attends to all others based on feature similarity.")
print(f"   Multi-head: {N_HEADS} parallel PoE aggregators (Remark 8.6)")
print("=" * 70)

print("\n  Architecture: conv(8) -> pool -> attention(content) -> conv(16) -> pool")
t0 = time.time()
result_content = engine.sql(f"""
    SELECT deep_learn(
        'attn_content', label, embedding, 'spatial',
        convolve(n_channels => 8),
        pool('max', 2),
        attention(n_heads => {N_HEADS}, mode => 'content'),
        convolve(n_channels => 16),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist
""")
content_time = time.time() - t0
content_acc = result_content.rows[0]["deep_learn"]["training_accuracy"]
print(f"  Train accuracy: {content_acc:.4f}  ({content_time:.1f}s)")


# ======================================================================
# 5. Attention mode: "random_qk" (ELM prior for Q, K)
# ======================================================================

print("\n" + "=" * 70)
print("5. Random Q,K Attention (ELM Prior)")
print("   Random projections create diverse attention patterns.")
print("   Ridge regression (posterior) finds the optimal combination.")
print("=" * 70)

print("\n  Architecture: conv(8) -> pool -> attention(random_qk) -> conv(16) -> pool")
t0 = time.time()
result_rqk = engine.sql(f"""
    SELECT deep_learn(
        'attn_random_qk', label, embedding, 'spatial',
        convolve(n_channels => 8),
        pool('max', 2),
        attention(n_heads => {N_HEADS}, mode => 'random_qk'),
        convolve(n_channels => 16),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist
""")
rqk_time = time.time() - t0
rqk_acc = result_rqk.rows[0]["deep_learn"]["training_accuracy"]
print(f"  Train accuracy: {rqk_acc:.4f}  ({rqk_time:.1f}s)")


# ======================================================================
# 6. Attention mode: "learned_v" (supervised V projection search)
# ======================================================================

print("\n" + "=" * 70)
print("6. Learned V Attention (Supervised Search)")
print("   Random Q,K + supervised search over orthogonal V projections.")
print("   Picks the W_v maximizing classification accuracy via ridge.")
print("=" * 70)

print("\n  Architecture: conv(8) -> pool -> attention(learned_v) -> conv(16) -> pool")
t0 = time.time()
result_lv = engine.sql(f"""
    SELECT deep_learn(
        'attn_learned_v', label, embedding, 'spatial',
        convolve(n_channels => 8),
        pool('max', 2),
        attention(n_heads => {N_HEADS}, mode => 'learned_v'),
        convolve(n_channels => 16),
        pool('max', 2),
        flatten(),
        dense(output_channels => 10),
        softmax(),
        gating => 'relu', lambda => 1.0
    ) FROM mnist
""")
lv_time = time.time() - t0
lv_acc = result_lv.rows[0]["deep_learn"]["training_accuracy"]
print(f"  Train accuracy: {lv_acc:.4f}  ({lv_time:.1f}s)")


# ======================================================================
# 7. Training accuracy comparison
# ======================================================================

print("\n" + "=" * 70)
print("7. Training Accuracy Comparison")
print("=" * 70)

results = [
    ("Baseline (no attention)", base_acc, base_time),
    (f"Content (Q=K=V=X, {N_HEADS} heads)", content_acc, content_time),
    (f"Random Q,K (ELM prior, {N_HEADS} heads)", rqk_acc, rqk_time),
    (f"Learned V (supervised, {N_HEADS} heads)", lv_acc, lv_time),
]

print(f"\n  {'Model':<42}  {'Train Acc':>10}  {'Time':>8}")
print("  " + "-" * 66)
for name, acc, t in results:
    print(f"  {name:<42}  {acc:>10.4f}  {t:>7.1f}s")


# ======================================================================
# 8. Test set evaluation
# ======================================================================

print("\n" + "=" * 70)
print("8. Test Set Evaluation")
print("=" * 70)

models = [
    ("baseline", "Baseline"),
    ("attn_content", "Content"),
    ("attn_random_qk", "Random Q,K"),
    ("attn_learned_v", "Learned V"),
]

print(f"\n  {'Model':<14}  {'Correct':>8}  {'Test Acc':>10}  {'Time':>8}")
print("  " + "-" * 48)

for model_name, display_name in models:
    config = engine.load_model(model_name)
    assert config is not None
    class_labels = config["class_labels"]

    correct = 0
    t0 = time.time()
    for i in range(len(X_test)):
        predictions = engine.deep_predict(model_name, X_test[i].tolist())
        predicted_class = predictions[0][0]
        if predicted_class < len(class_labels):
            pred_label = class_labels[predicted_class]
        else:
            pred_label = predicted_class
        if pred_label == int(y_test[i]):
            correct += 1
    eval_time = time.time() - t0

    test_acc = correct / len(X_test)
    print(f"  {display_name:<14}  {correct:>8}  {test_acc:>10.4f}  {eval_time:>7.1f}s")


# ======================================================================
# 9. Inference via deep_fusion SQL
# ======================================================================

print("\n" + "=" * 70)
print("9. Inference via deep_fusion(model()) SQL")
print("=" * 70)

sample_idx = 0
sample_label = int(y_test[sample_idx])

# Build grid table for deep_fusion inference
engine.sql("""
    CREATE TABLE grid_28x28 (
        id SERIAL PRIMARY KEY,
        pixel TEXT NOT NULL
    )
""")
for px in range(784):
    engine.sql(f"INSERT INTO grid_28x28 (pixel) VALUES ('px{px}')")
engine.sql("SELECT * FROM build_grid_graph('grid_28x28', 28, 28, 'spatial')")

print(f"\n  Test sample {sample_idx}: true label = {sample_label}")
print()

for model_name, display_name in models:
    t0 = time.time()
    fusion_result = engine.sql(
        """
        SELECT id, _score, class_probs FROM grid_28x28
        WHERE deep_fusion(
            model($1, $2),
            gating => 'relu'
        ) ORDER BY _score DESC
    """,
        params=[model_name, X_test[sample_idx]],
    )
    fusion_time = time.time() - t0

    probs = fusion_result.rows[0].get("class_probs", [])
    if probs:
        top = sorted(enumerate(probs), key=lambda x: -x[1])
        config = engine.load_model(model_name)
        assert config is not None
        cl = config["class_labels"]
        top_label = cl[top[0][0]] if top[0][0] < len(cl) else top[0][0]
        correct_mark = "correct" if top_label == sample_label else "wrong"
        print(
            f"  {display_name:<14}  predicted={top_label}  "
            f"prob={top[0][1]:.4f}  ({correct_mark})  "
            f"{fusion_time:.2f}s"
        )


# ======================================================================
# 10. Model internals
# ======================================================================

print("\n" + "=" * 70)
print("10. Attention Model Internals")
print("=" * 70)

for model_name, display_name in models[1:]:
    config = engine.load_model(model_name)
    assert config is not None

    attn_params = config.get("attention_params", [])
    n_experts = len(config.get("expert_weights", [])) + 1

    print(f"\n  {display_name} ({model_name}):")
    print(f"    PoE experts: {n_experts}")
    print(f"    Shrinkage alpha: {config.get('shrinkage_alpha', 0):.4f}")

    for i, ap in enumerate(attn_params):
        mode = ap.get("mode", "content")
        n_h = ap.get("n_heads", 1)
        d = ap.get("d_model", "?")
        has_qk = "W_q" in ap
        has_v = "W_v" in ap
        print(f"    Attention layer {i}:")
        print(f"      mode={mode}, n_heads={n_h}, d_model={d}")
        if has_qk:
            W_q = np.array(ap["W_q"])
            print(f"      W_q norm={np.linalg.norm(W_q):.4f}")
        if has_v:
            W_v = np.array(ap["W_v"])
            print(f"      W_v norm={np.linalg.norm(W_v):.4f}")


print("\n" + "=" * 70)
print("Attention demonstration completed successfully.")
print("=" * 70)
