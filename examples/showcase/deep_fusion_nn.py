#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deep Fusion as a Neural Network: complete DL pipeline over graphs.

Extends the CNN (ConvLayer) and GNN (PropagateLayer) showcases with
the remaining standard deep learning components:

    PoolLayer      -- spatial downsampling via greedy BFS partitioning
    DenseLayer     -- fully connected: out = W @ input + bias
    FlattenLayer   -- collapse spatial nodes into a single vector
    SoftmaxLayer   -- classification head (numerically stable)
    BatchNormLayer -- per-channel normalization across nodes
    DropoutLayer   -- inference-mode scaling by (1 - p)

Internal data model: channel_map: dict[int, np.ndarray]
    Single-channel (num_channels=1) is backward compatible with the
    original scalar logit model.  New layers operate on all channels.

Demonstrates:
  1. Pooling: max/avg spatial downsampling on a grid
  2. Dense: channel expansion and reduction
  3. Flatten -> Dense -> Softmax: classification pipeline
  4. BatchNorm + Dropout in a spatial pipeline
  5. Full CNN pipeline: conv -> pool -> flatten -> dense -> softmax
  6. EXPLAIN plan for the full pipeline
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
        label TEXT NOT NULL,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

# Simulate a 4x4 image where:
#   Top-left 2x2   = "cat"  (class 0)
#   Top-right 2x2  = "dog"  (class 1)
#   Bottom-left 2x2 = "bird" (class 2)
#   Bottom-right 2x2 = mixed background

class_centers = {
    "cat": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0]),
    "dog": np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "bird": np.array([0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0]),
    "bg": np.array([0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.5]),
}

grid_size = 4
for r in range(grid_size):
    for c in range(grid_size):
        if r < 2 and c < 2:
            label = "cat"
        elif r < 2 and c >= 2:
            label = "dog"
        elif r >= 2 and c < 2:
            label = "bird"
        else:
            label = "bg"

        base = class_centers[label]
        vec = base + rng.randn(8).astype(np.float32) * 0.12
        vec = vec / np.linalg.norm(vec)
        arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        engine.sql(
            f"INSERT INTO patches (image_id, patch_row, patch_col, "
            f"label, embedding) "
            f"VALUES (1, {r}, {c}, '{label}', {arr})"
        )

# Build 4-connected grid graph (horizontal + vertical)
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

# Query: looking for "cat"
query = class_centers["cat"] + rng.randn(8).astype(np.float32) * 0.05
query = (query / np.linalg.norm(query)).astype(np.float32)
arr_q = "ARRAY[" + ",".join(str(float(v)) for v in query) + "]"


def print_grid(result, title=""):
    """Print scores as a 4x4 grid."""
    if title:
        print(f"\n  {title}")
    score_map = {row["id"]: row["_score"] for row in result.rows}
    for r in range(grid_size):
        row_str = "    "
        for c in range(grid_size):
            pid = r * grid_size + c + 1
            score = score_map.get(pid, 0.0)
            row_str += f" {score:.3f}"
        print(row_str)


print("=" * 70)
print("Deep Fusion as Neural Network: Complete DL Pipeline")
print("=" * 70)


# ======================================================================
# 1. Pooling: spatial downsampling
# ======================================================================
print("\n" + "=" * 60)
print("1. Pooling: Spatial Downsampling")
print("=" * 60)
print(
    "\n  PoolLayer groups neighboring nodes via BFS and aggregates:\n"
    "    max pool: takes element-wise max (preserves strongest features)\n"
    "    avg pool: takes element-wise mean (smooths features)\n"
    "\n  On a 4x4 grid with pool_size=2: ~8 nodes remain.\n"
)

raw = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16))
    ) ORDER BY id
""")
print_grid(raw, "Raw scores (16 nodes):")

max_pooled = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        pool('spatial', 'max', 2)
    ) ORDER BY id
""")
print(f"\n  After max pool (size=2): {len(max_pooled.rows)} nodes remain")
for row in max_pooled.rows:
    print(f"    node {row['id']:2d}: score={row['_score']:.4f}")

avg_pooled = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        pool('spatial', 'avg', 2)
    ) ORDER BY id
""")
print(f"\n  After avg pool (size=2): {len(avg_pooled.rows)} nodes remain")
for row in avg_pooled.rows:
    print(f"    node {row['id']:2d}: score={row['_score']:.4f}")


# ======================================================================
# 2. Dense: channel expansion and reduction
# ======================================================================
print("\n" + "=" * 60)
print("2. Dense Layer: Channel Expansion")
print("=" * 60)
print(
    "\n  DenseLayer: out = W @ input + bias, then gating.\n"
    "  Expands 1 channel to 4 channels per node.\n"
    "\n  W = [[1.0], [0.5], [-0.3], [0.8]]  (4x1 matrix)\n"
    "  bias = [0.0, 0.0, 0.0, 0.0]\n"
)

result = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        dense(ARRAY[1.0, 0.5, -0.3, 0.8], ARRAY[0.0, 0.0, 0.0, 0.0],
              output_channels => 4, input_channels => 1)
    ) ORDER BY _score DESC LIMIT 5
""")
print("  Top 5 after dense(1->4):")
for row in result.rows:
    print(f"    node {row['id']:2d}: score={row['_score']:.4f}")

print(
    "\n  Score = sigmoid(max across 4 channels).\n"
    "  Channel expansion gives the network more representational capacity."
)


# ======================================================================
# 3. Flatten -> Dense -> Softmax: classification
# ======================================================================
print("\n" + "=" * 60)
print("3. Classification Pipeline: Flatten -> Dense -> Softmax")
print("=" * 60)
print(
    "\n  Standard CNN classification head:\n"
    "    flatten(): 16 nodes x 1 ch -> 1 node x 16 ch\n"
    "    dense(16->4): project to 4 class logits\n"
    "    softmax(): normalize to probabilities\n"
)

# 16->4 dense weights (4 classes x 16 spatial features)
w_vals = []
for out_ch in range(4):
    for in_ch in range(16):
        # Simple pattern: each class responds to its quadrant
        r, c = divmod(in_ch, grid_size)
        if out_ch == 0 and r < 2 and c < 2:  # cat quadrant
            w_vals.append(0.3)
        elif out_ch == 1 and r < 2 and c >= 2:  # dog quadrant
            w_vals.append(0.3)
        elif out_ch == 2 and r >= 2 and c < 2:  # bird quadrant
            w_vals.append(0.3)
        elif out_ch == 3 and r >= 2 and c >= 2:  # bg quadrant
            w_vals.append(0.3)
        else:
            w_vals.append(0.01)

w_str = ",".join(str(w) for w in w_vals)
b_str = ",".join(["0.0"] * 4)

result = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        flatten(),
        dense(ARRAY[{w_str}], ARRAY[{b_str}],
              output_channels => 4, input_channels => 16),
        softmax()
    ) ORDER BY _score DESC
""")

print(f"  Result: 1 node, score={result.rows[0]['_score']:.4f}")
print("  (score = max class probability after softmax)")
print(
    "\n  The query was for 'cat', and the weights assign high values\n"
    "  to the top-left quadrant (cat region) for class 0."
)


# ======================================================================
# 4. BatchNorm + Dropout in a spatial pipeline
# ======================================================================
print("\n" + "=" * 60)
print("4. BatchNorm + Dropout: Regularized Spatial Pipeline")
print("=" * 60)
print(
    "\n  batch_norm(): per-channel normalize across all nodes\n"
    "    -> zero mean, unit variance per channel\n"
    "    -> stabilizes activations for deeper pipelines\n"
    "\n  dropout(0.3): scale all values by 0.7 (inference mode)\n"
    "    -> prevents over-reliance on any single feature\n"
)

result_bn = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        batch_norm(),
        dropout(0.3),
        convolve('spatial', ARRAY[0.6, 0.4])
    ) ORDER BY _score DESC LIMIT 5
""")
print("  Top 5 after batch_norm -> dropout(0.3) -> conv:")
for row in result_bn.rows:
    print(f"    node {row['id']:2d}: score={row['_score']:.4f}")


# ======================================================================
# 5. Full CNN pipeline
# ======================================================================
print("\n" + "=" * 60)
print("5. Full CNN Pipeline")
print("=" * 60)
print(
    "\n  knn(16 nodes)\n"
    "    -> conv(3x3 equivalent)\n"
    "    -> pool(size=2, max) -> ~8 nodes\n"
    "    -> flatten() -> 1 node x N channels\n"
    "    -> dense(N -> 4 classes)\n"
    "    -> softmax()\n"
)

# Step 1: determine pooled node count (depends on graph structure)
pool_result = engine.sql(f"""
    SELECT id FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', ARRAY[0.6, 0.4]),
        pool('spatial', 'max', 2)
    )
""")
n_pooled = len(pool_result.rows)
print(f"  After conv + pool: {n_pooled} nodes")

# Step 2: build dense weights (n_pooled -> 4 classes)
n_weights = n_pooled * 4
w_full = ",".join(str(float(i % 5) * 0.1 + 0.05) for i in range(n_weights))
b_full = ",".join(["0.0"] * 4)

result_full = engine.sql(f"""
    SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', ARRAY[0.6, 0.4]),
        pool('spatial', 'max', 2),
        flatten(),
        dense(ARRAY[{w_full}], ARRAY[{b_full}],
              output_channels => 4, input_channels => {n_pooled}),
        softmax(),
        gating => 'relu'
    ) ORDER BY _score DESC
""")

print(f"  After full pipeline: {len(result_full.rows)} node(s)")
print(f"  Classification score: {result_full.rows[0]['_score']:.4f}")
print(
    "\n  This is a complete CNN: spatial features extracted by conv,\n"
    "  downsampled by pool, collapsed by flatten, projected by dense,\n"
    "  and normalized by softmax -- all expressed as SQL."
)


# ======================================================================
# 6. EXPLAIN plan
# ======================================================================
print("\n" + "=" * 60)
print("6. EXPLAIN: Full Pipeline Plan")
print("=" * 60)
print()

explain = engine.sql(f"""
    EXPLAIN SELECT id, _score FROM patches
    WHERE deep_fusion(
        layer(knn_match(embedding, {arr_q}, 16)),
        convolve('spatial', ARRAY[0.6, 0.4]),
        pool('spatial', 'max', 2),
        batch_norm(),
        dropout(0.3),
        flatten(),
        dense(ARRAY[{w_full}], ARRAY[{b_full}],
              output_channels => 4, input_channels => {n_pooled}),
        softmax(),
        gating => 'relu'
    ) ORDER BY _score DESC
""")
for row in explain.rows:
    print(f"  {row['plan']}")


# ======================================================================
# SQL syntax summary
# ======================================================================
print("\n" + "=" * 60)
print("SQL Syntax Summary")
print("=" * 60)
print(
    """
  deep_fusion(
      layer(signal1, signal2, ...),    -- SignalLayer (ResNet)
      propagate('label', 'agg'),       -- PropagateLayer (GNN)
      convolve('label', ARRAY[w...]),   -- ConvLayer (CNN)
      pool('label', 'max', 2),         -- PoolLayer (downsampling)
      batch_norm(),                     -- BatchNormLayer
      dropout(0.5),                     -- DropoutLayer
      flatten(),                        -- FlattenLayer
      dense(ARRAY[W], ARRAY[b],        -- DenseLayer
            output_channels => N,
            input_channels => M),
      softmax(),                        -- SoftmaxLayer
      gating => 'relu'                 -- global gating function
  )
"""
)

print("=" * 70)
print("Neural network demonstration completed successfully.")
print("=" * 70)
