#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deep Fusion as CNN: spatial convolution over grid graphs.

ConvLayer performs weighted multi-hop BFS aggregation:

    conv(v) = sum_h( w_h * mean(prob(h-hop neighbors of v)) )

On a 4-connected grid this IS a CNN convolution:
    - hop 0 = self (center pixel)
    - hop 1 = 3x3 receptive field
    - hop 2 = 5x5 receptive field
    - stacking 2 ConvLayers of hop 1 = 5x5 effective receptive field

Weights are learned via MLE (estimate_conv_weights), not backpropagation:
    w_h = normalized spatial autocorrelation at hop distance h

Demonstrates:
  1. Grid graph construction (image patches)
  2. Weight estimation from spatial autocorrelation
  3. Single conv layer (3x3 equivalent)
  4. Stacked conv layers (deeper receptive field)
  5. Smoothing effect visualization
  6. EXPLAIN plan with convolve layers
"""

from __future__ import annotations

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: 4x4 image as patches with spatial graph
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE patches (
        id SERIAL PRIMARY KEY,
        image_id INTEGER NOT NULL,
        patch_row INTEGER NOT NULL,
        patch_col INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

# Simulate a 4x4 image where:
# - Top-left quadrant has "object" embeddings (similar to query)
# - Rest has "background" embeddings (dissimilar to query)
# This creates a spatial pattern that convolution should smooth

object_center = np.array([1.0, 0.8, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0])
background_center = np.array([0.0, 0.0, 0.8, 1.0, 0.0, 0.5, 0.0, 0.0])

grid_size = 4
for r in range(grid_size):
    for c in range(grid_size):
        # Top-left quadrant = object, rest = background
        if r < 2 and c < 2:
            base = object_center
            content = f"object patch r{r}c{c} feature"
        else:
            base = background_center
            content = f"background patch r{r}c{c} noise"

        vec = base + rng.randn(8).astype(np.float32) * 0.15
        vec = vec / np.linalg.norm(vec)
        arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        engine.sql(
            f"INSERT INTO patches (image_id, patch_row, patch_col, "
            f"content, embedding) "
            f"VALUES (1, {r}, {c}, '{content}', {arr})"
        )

# Build 4-connected grid graph
edge_id = 1
for r in range(grid_size):
    for c in range(grid_size):
        pid = r * grid_size + c + 1
        if c < grid_size - 1:
            right = pid + 1
            engine.add_graph_edge(Edge(edge_id, pid, right, "spatial"), table="patches")
            edge_id += 1
        if r < grid_size - 1:
            down = pid + grid_size
            engine.add_graph_edge(Edge(edge_id, pid, down, "spatial"), table="patches")
            edge_id += 1

# Query vector: looking for the "object"
query = object_center + rng.randn(8).astype(np.float32) * 0.05
query = (query / np.linalg.norm(query)).astype(np.float32)
arr_q = "ARRAY[" + ",".join(str(float(v)) for v in query) + "]"


def print_grid(result, grid_size=4):
    """Print scores as a grid for visualization."""
    score_map = {row["id"]: row["_score"] for row in result.rows}
    for r in range(grid_size):
        row_str = "    "
        for c in range(grid_size):
            pid = r * grid_size + c + 1
            score = score_map.get(pid, 0.0)
            row_str += f" {score:.3f}"
        print(row_str)


print("=" * 70)
print("Deep Fusion as CNN: Spatial Convolution over Grid Graphs")
print("=" * 70)


# ======================================================================
# 1. Grid setup visualization
# ======================================================================
print("\n" + "=" * 60)
print("1. Grid Setup: 4x4 image patches")
print("=" * 60)
print(
    "\n  Top-left 2x2 = 'object' (high similarity to query)\n"
    "  Rest = 'background' (low similarity)\n"
    "\n  Spatial graph: 4-connected grid (horizontal + vertical edges)\n"
)


# ======================================================================
# 2. Weight estimation from spatial autocorrelation
# ======================================================================
print("=" * 60)
print("2. Weight Estimation (MLE)")
print("=" * 60)
print(
    "\n  estimate_conv_weights computes cosine similarity at each\n"
    "  hop distance. No backpropagation -- just data statistics.\n"
)

weights_1 = engine.estimate_conv_weights(
    table="patches",
    edge_label="spatial",
    kernel_hops=1,
)
weights_2 = engine.estimate_conv_weights(
    table="patches",
    edge_label="spatial",
    kernel_hops=2,
)

print(f"\n  1-hop weights: [{', '.join(f'{w:.4f}' for w in weights_1)}]")
print(f"  2-hop weights: [{', '.join(f'{w:.4f}' for w in weights_2)}]")
print("\n  hop 0 (self) > hop 1 > hop 2: spatial coherence decays with distance")


# ======================================================================
# 3. Raw scores vs convolved scores
# ======================================================================
print("\n" + "=" * 60)
print("3. Raw vs Convolved Scores (3x3 kernel)")
print("=" * 60)

raw = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16))
    ) ORDER BY id
""")

arr_w1 = "ARRAY[" + ",".join(str(w) for w in weights_1) + "]"

conv = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', {arr_w1})
    ) ORDER BY id
""")

print("\n  Raw scores (no convolution):")
print_grid(raw, grid_size)

print("\n  After 1-hop convolution (3x3 equivalent):")
print_grid(conv, grid_size)

raw_scores = [r["_score"] for r in raw.rows]
conv_scores = [r["_score"] for r in conv.rows]
print(
    f"\n  Score variance: raw={np.var(raw_scores):.6f}, conv={np.var(conv_scores):.6f}"
)
print("  Convolution smooths the spatial score distribution.")


# ======================================================================
# 4. Stacked conv layers (deeper receptive field)
# ======================================================================
print("\n" + "=" * 60)
print("4. Stacked ConvLayers: deeper receptive field")
print("=" * 60)
print(
    "\n  1 layer of 1-hop = 3x3 receptive field\n"
    "  2 layers of 1-hop = 5x5 effective receptive field\n"
)

conv_deep = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', {arr_w1}),
        convolve('spatial', {arr_w1}),
        gating => 'relu'
    ) ORDER BY id
""")

print("  After 2 stacked conv layers (5x5 effective, ReLU gating):")
print_grid(conv_deep, grid_size)

deep_scores = [r["_score"] for r in conv_deep.rows]
print(
    f"\n  Score variance: 1-layer={np.var(conv_scores):.6f}, "
    f"2-layer={np.var(deep_scores):.6f}"
)


# ======================================================================
# 5. Using estimated 2-hop weights directly
# ======================================================================
print("\n" + "=" * 60)
print("5. Estimated 2-Hop Weights (5x5 kernel in one layer)")
print("=" * 60)
print(
    "\n  Instead of stacking two 1-hop layers, use a single 2-hop\n"
    "  layer with MLE-estimated weights.\n"
)

arr_w2 = "ARRAY[" + ",".join(str(w) for w in weights_2) + "]"

conv_2hop = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', {arr_w2}),
        gating => 'relu'
    ) ORDER BY id
""")

print("  Single 2-hop conv layer (5x5 equivalent, ReLU gating):")
print_grid(conv_2hop, grid_size)


# ======================================================================
# 6. EXPLAIN plan
# ======================================================================
print("\n" + "=" * 60)
print("6. EXPLAIN Output")
print("=" * 60)
print()

explain = engine.sql(f"""
    EXPLAIN SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', {arr_w1}),
        convolve('spatial', {arr_w1}),
        gating => 'relu'
    ) ORDER BY _score DESC
""")
for row in explain.rows:
    print(f"  {row['plan']}")

print("\n" + "=" * 70)
print("CNN demonstration completed successfully.")
print("=" * 70)
