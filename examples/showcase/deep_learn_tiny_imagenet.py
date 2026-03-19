#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""deep_learn() Training Pipeline on Tiny ImageNet.

Tiny ImageNet: 64x64 RGB images, 200 classes.
We use a 50-class subset (25,000 train / 2,500 test).

Architecture: conv(64) -> pool(2) -> conv(128) -> pool(2) ->
  conv(256) -> pool(2) -> flatten -> dense(50) -> softmax
  3-stage conv+pool: 64 -> 32 -> 16 -> 8 spatial dims
  Final features: 256 x 8 x 8 = 16,384
  Data augmentation: horizontal flip (2x training data)

Pipeline:
  1. Download Tiny ImageNet (zip, ~237 MB)
  2. Load 50-class subset as RGB (64x64x3 = 12,288-D)
  3. Create table + 64x64 grid graph via SQL
  4. Train via deep_learn() SQL
  5. Predict via deep_predict() SQL
  6. Inference via deep_fusion(embed()) SQL
  7. Evaluate accuracy on test samples

Same analytical training -- no backpropagation:
  ConvLayer:  random multi-channel kernels (Kaiming prior)
  DenseLayer: ridge regression W = (X^T X + lambda I)^{-1} X^T Y
"""

from __future__ import annotations

import io
import os
import time
import zipfile

import numpy as np
from PIL import Image

from uqa.engine import Engine

# ======================================================================
# 1. Tiny ImageNet data loading
# ======================================================================

TINY_URL = "http://cs231n.stanford.edu/tiny-imagenet-200.zip"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "tiny_imagenet")
ZIP_PATH = os.path.join(DATA_DIR, "tiny-imagenet-200.zip")

# 50 classes selected from Tiny ImageNet (500 train + 50 val each)
NUM_CLASSES = 50
TRAIN_PER_CLASS = 500
TEST_PER_CLASS = 50
IMG_SIZE = 64


def _ensure_downloaded() -> str:
    """Download Tiny ImageNet zip if not present."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ZIP_PATH):
        import urllib.request

        print(f"  Downloading {TINY_URL} ...")
        print("  (237 MB, this may take a few minutes)")
        urllib.request.urlretrieve(TINY_URL, ZIP_PATH)
    return ZIP_PATH


def _load_image_rgb(data: bytes, flip: bool = False) -> np.ndarray | None:
    """Load JPEG bytes -> 64x64 RGB float32 normalized to [0, 1].

    Returns (3*64*64,) = (12288,) flat array in CHW order.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        img = img.resize((IMG_SIZE, IMG_SIZE))
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        # HWC -> CHW -> flat, scale to [0, 1]
        return np.array(img, dtype=np.float32).transpose(2, 0, 1).reshape(-1) / 255.0
    except Exception:
        return None


def load_tiny_imagenet() -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]
]:
    """Load a subset of Tiny ImageNet from the zip file.

    Returns (train_images, train_labels, test_images, test_labels, class_names).
    Images are 64x64 RGB flattened to 12288-D float32 in [0, 1].
    """
    zip_path = _ensure_downloaded()

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Load human-readable class names
        words_data = zf.read("tiny-imagenet-200/words.txt").decode()
        words_map: dict[str, str] = {}
        for line in words_data.strip().split("\n"):
            parts = line.split("\t", 1)
            words_map[parts[0]] = parts[1].split(",")[0]

        # Build per-class file index in a single pass over namelist
        class_files: dict[str, list[str]] = {}
        for name in zf.namelist():
            if not name.startswith("tiny-imagenet-200/train/n"):
                continue
            parts = name.split("/")
            if len(parts) >= 5 and name.lower().endswith(".jpeg"):
                cls = parts[2]
                class_files.setdefault(cls, []).append(name)

        selected = sorted(class_files.keys())[:NUM_CLASSES]
        class_to_idx = {c: i for i, c in enumerate(selected)}

        # Load training images
        train_images: list[np.ndarray] = []
        train_labels: list[int] = []

        for cls_name in selected:
            members = sorted(class_files.get(cls_name, []))
            for path in members[:TRAIN_PER_CLASS]:
                raw = zf.read(path)
                img = _load_image_rgb(raw)
                if img is not None:
                    train_images.append(img)
                    train_labels.append(class_to_idx[cls_name])
                    # Data augmentation: horizontal flip
                    img_aug = _load_image_rgb(raw, flip=True)
                    if img_aug is not None:
                        train_images.append(img_aug)
                        train_labels.append(class_to_idx[cls_name])

        # Load validation images (Tiny ImageNet stores them flat)
        val_ann_data = zf.read("tiny-imagenet-200/val/val_annotations.txt").decode()
        val_map: dict[str, str] = {}
        for line in val_ann_data.strip().split("\n"):
            parts = line.split("\t")
            val_map[parts[0]] = parts[1]

        test_images: list[np.ndarray] = []
        test_labels: list[int] = []
        counts: dict[int, int] = {}

        for filename, cls_name in sorted(val_map.items()):
            if cls_name not in class_to_idx:
                continue
            idx = class_to_idx[cls_name]
            if counts.get(idx, 0) >= TEST_PER_CLASS:
                continue
            path = f"tiny-imagenet-200/val/images/{filename}"
            try:
                img = _load_image_rgb(zf.read(path))
            except KeyError:
                continue
            if img is not None:
                test_images.append(img)
                test_labels.append(idx)
                counts[idx] = counts.get(idx, 0) + 1

    readable_names = [words_map.get(c, c) for c in selected]
    return (
        np.array(train_images),
        np.array(train_labels),
        np.array(test_images),
        np.array(test_labels),
        readable_names,
    )


# ======================================================================
# 2. Setup
# ======================================================================

print("=" * 70)
print("deep_learn() Training Pipeline on Tiny ImageNet")
print("=" * 70)

print("\n  Loading Tiny ImageNet data ...")
X_train, y_train, X_test, y_test, class_names = load_tiny_imagenet()
print(f"  Train: {len(X_train)} samples, Test: {len(X_test)} samples")
EMB_DIM = 3 * IMG_SIZE * IMG_SIZE
print(f"  Image size: {IMG_SIZE}x{IMG_SIZE} RGB = {EMB_DIM} values")
print(f"  Classes: {NUM_CLASSES} ({', '.join(class_names[:5])}, ...)")

engine = Engine()

engine.sql(f"""
    CREATE TABLE tiny_train (
        id SERIAL PRIMARY KEY,
        label INTEGER NOT NULL,
        embedding VECTOR({EMB_DIM})
    )
""")

print("\n  Inserting training data ...")
t0 = time.time()
for i in range(len(X_train)):
    engine.sql(
        "INSERT INTO tiny_train (label, embedding) VALUES ($1, $2)",
        params=[int(y_train[i]), X_train[i]],
    )
insert_time = time.time() - t0
print(f"  Inserted {len(X_train)} samples in {insert_time:.2f}s")

# Build 64x64 grid graph via SQL
print(f"\n  Building {IMG_SIZE}x{IMG_SIZE} grid graph (4-connected) ...")
t0 = time.time()
grid_result = engine.sql(f"""
    SELECT * FROM build_grid_graph('tiny_train', {IMG_SIZE}, {IMG_SIZE}, 'spatial')
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
    f"\n  Architecture: conv(64ch) -> pool(2) -> conv(128ch) -> pool(2)"
    f" -> conv(256ch) -> pool(2) -> flatten -> dense({NUM_CLASSES}) -> softmax"
    f"\n  Input: RGB ({IMG_SIZE}x{IMG_SIZE}x3 = {EMB_DIM})"
    f"\n  Data augmentation: horizontal flip (2x training data)"
    f"\n  3-stage conv+pool: 64 -> 32 -> 16 -> 8 spatial dims"
    f"\n  Final features: 256 x 8 x 8 = 16384"
    f"\n  Random multi-channel conv (prior) + ridge regression (posterior)"
    f"\n  Gating: relu, Lambda: 500.0"
    f"\n  No backpropagation -- analytical parameter estimation"
)

t0 = time.time()
result = engine.sql(f"""
    SELECT deep_learn(
        'tiny_cnn', label, embedding, 'spatial',
        convolve(n_channels => 64),
        pool('max', 2),
        convolve(n_channels => 128),
        pool('max', 2),
        convolve(n_channels => 256),
        pool('max', 2),
        flatten(),
        dense(output_channels => {NUM_CLASSES}),
        softmax(),
        gating => 'relu', lambda => 500.0
    ) FROM tiny_train
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

sample_idx = 0
sample_label = int(y_test[sample_idx])

predictions = engine.deep_predict("tiny_cnn", X_test[sample_idx].tolist())

print(
    f"\n  Test sample {sample_idx}: true label = {sample_label} ({class_names[sample_label]})"
)
print("  Predicted class probabilities:")
for ci, prob in predictions[:5]:
    cn = class_names[ci] if ci < len(class_names) else str(ci)
    marker = " <--" if ci == sample_label else ""
    print(f"    {cn}: {prob:.4f}{marker}")
if len(predictions) > 5:
    print(f"    ... ({len(predictions) - 5} more classes)")


# ======================================================================
# 5. Evaluate accuracy on test set
# ======================================================================

print("\n" + "=" * 60)
print("5. Test Set Evaluation")
print("=" * 60)

config = engine.load_model("tiny_cnn")
assert config is not None
model_class_labels = config["class_labels"]

correct = 0
t0 = time.time()
for i in range(len(X_test)):
    predictions = engine.deep_predict("tiny_cnn", X_test[i].tolist())
    predicted_class = predictions[0][0]
    if predicted_class < len(model_class_labels):
        pred_label = model_class_labels[predicted_class]
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
# 6. deep_fusion(embed()) with learned weights
# ======================================================================

print("\n" + "=" * 60)
print("6. deep_fusion(embed()) with Learned Weights")
print("=" * 60)

kernel_shapes = config.get("conv_kernel_shapes", [])
print(f"\n  Conv kernels: {len(kernel_shapes)} stages")
for i, shape in enumerate(kernel_shapes):
    print(f"    Stage {i}: {shape} (random, Kaiming init)")

in_ch = config["dense_input_channels"]
out_ch = config["dense_output_channels"]
dense_w_arr = np.array(config["dense_weights"])
print(f"\n  Dense layer: {in_ch} -> {out_ch}")
print(f"    Weight norm: {np.linalg.norm(dense_w_arr):.4f}")

n_experts = len(config.get("expert_weights", [])) + 1
print(f"\n  PoE experts: {n_experts} (Theorem 8.3)")
print(f"  Shrinkage alpha: {config.get('shrinkage_alpha', 0.5)} (Theorem 4.4.1)")

# Build grid table for deep_fusion inference
print(f"\n  Building {IMG_SIZE}x{IMG_SIZE} grid table ...")
engine.sql(f"""
    CREATE TABLE grid_{IMG_SIZE}x{IMG_SIZE} (
        id SERIAL PRIMARY KEY,
        pixel TEXT NOT NULL
    )
""")
grid_table = f"grid_{IMG_SIZE}x{IMG_SIZE}"
for px in range(IMG_SIZE * IMG_SIZE):
    engine.sql(f"INSERT INTO {grid_table} (pixel) VALUES ('px{px}')")

engine.sql(
    f"SELECT * FROM build_grid_graph('{grid_table}', {IMG_SIZE}, {IMG_SIZE}, 'spatial')"
)

# model('tiny_cnn') loads multi-channel kernels + dense weights from catalog
print("\n  Executing deep_fusion(model('tiny_cnn', $1)) ...")
t0 = time.time()
fusion_result = engine.sql(
    f"""
    SELECT id, _score, class_probs FROM {grid_table}
    WHERE deep_fusion(
        model('tiny_cnn', $1),
        gating => 'relu'
    ) ORDER BY _score DESC
""",
    params=[X_test[0]],
)
fusion_time = time.time() - t0
print(f"  deep_fusion() completed in {fusion_time:.2f}s")

fusion_probs = fusion_result.rows[0].get("class_probs", [])
print(
    f"\n  deep_fusion() class probabilities "
    f"(sample 0, true = {class_names[sample_label]}):"
)
sorted_probs = sorted(enumerate(fusion_probs), key=lambda x: -x[1])
for ci, cp in sorted_probs[:5]:
    cn = class_names[ci] if ci < len(class_names) else str(ci)
    marker = " <--" if ci == sample_label else ""
    print(f"    {cn}: {cp:.4f}{marker}")


print("\n" + "=" * 70)
print("Tiny ImageNet demonstration completed successfully.")
print("=" * 70)
