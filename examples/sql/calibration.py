#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Calibration and parameter learning examples via Engine API.

Demonstrates:
  - engine.calibration_report() -- compute ECE, Brier score
  - CalibrationMetrics.ece() and .brier() -- standalone metrics
  - CalibrationMetrics.reliability_diagram() -- binned calibration data
  - engine.learn_scoring_params() -- batch parameter learning
  - engine.update_scoring_params() -- online parameter update
  - ParameterLearner standalone usage
"""

from __future__ import annotations

from uqa.engine import Engine
from uqa.scoring.calibration import CalibrationMetrics
from uqa.scoring.parameter_learner import ParameterLearner

# ======================================================================
# Data setup: ML-topic documents for calibration evaluation
# ======================================================================

engine = Engine()

engine.sql("""CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)""")

documents = [
    "machine learning algorithms classification regression",
    "deep learning neural networks backpropagation training",
    "natural language processing text classification sentiment",
    "computer vision image recognition convolutional networks",
    "reinforcement learning reward optimization policy gradient",
    "database systems indexing query optimization storage",
    "distributed computing parallel processing fault tolerance",
    "operating systems kernel scheduling memory management",
]
for doc in documents:
    engine.sql(f"INSERT INTO docs (content) VALUES ('{doc}')")


print("=" * 70)
print("Calibration and Parameter Learning Examples")
print("=" * 70)


# ==================================================================
# 1. engine.calibration_report: compute ECE, Brier score
# ==================================================================
print("\n--- 1. Calibration report for 'learning' query ---")

# Labels: 1 = relevant, 0 = not relevant to "learning"
# Docs 1-5 mention learning-related topics; 6-8 do not
labels = [1, 1, 1, 0, 1, 0, 0, 0]

report = engine.calibration_report("docs", "content", "learning", labels)
print(f"  Report keys: {sorted(report.keys())}")
for key, value in sorted(report.items()):
    if isinstance(value, float):
        print(f"  {key}: {value:.6f}")
    elif isinstance(value, (int, bool)):
        print(f"  {key}: {value}")


# ==================================================================
# 2. CalibrationMetrics.ece() and .brier() directly
# ==================================================================
print("\n--- 2. CalibrationMetrics: ECE and Brier score ---")

# Simulated predictions vs ground truth
probabilities = [0.85, 0.78, 0.72, 0.35, 0.68, 0.15, 0.10, 0.22]
labels_for_metrics = [1, 1, 1, 0, 1, 0, 0, 0]

ece = CalibrationMetrics.ece(probabilities, labels_for_metrics, n_bins=5)
brier = CalibrationMetrics.brier(probabilities, labels_for_metrics)
print(f"  ECE (Expected Calibration Error): {ece:.6f}")
print(f"  Brier score:                      {brier:.6f}")
print("  (Lower is better for both metrics)")


# ==================================================================
# 3. CalibrationMetrics.reliability_diagram()
# ==================================================================
print("\n--- 3. Reliability diagram data ---")

diagram = CalibrationMetrics.reliability_diagram(
    probabilities, labels_for_metrics, n_bins=5
)
print(f"  {'Avg Predicted':>15}  {'Avg Actual':>12}  {'Count':>7}")
print(f"  {'-' * 38}")
for avg_pred, avg_actual, count in diagram:
    print(f"  {avg_pred:>15.4f}  {avg_actual:>12.4f}  {count:>7}")
print("  (Perfect calibration: avg_predicted == avg_actual in every bin)")


# ==================================================================
# 4. engine.learn_scoring_params: batch parameter learning
# ==================================================================
print("\n--- 4. Batch parameter learning for 'learning' query ---")

learned = engine.learn_scoring_params(
    "docs", "content", "learning", labels, mode="balanced"
)
print("  Learned parameters:")
for param, value in sorted(learned.items()):
    print(f"    {param}: {value:.6f}")


# ==================================================================
# 5. engine.update_scoring_params: online update
# ==================================================================
print("\n--- 5. Online parameter update ---")

# Simulate online feedback: user marks documents as relevant/not-relevant
engine.update_scoring_params("docs", "content", score=0.85, label=1)
engine.update_scoring_params("docs", "content", score=0.10, label=0)
engine.update_scoring_params("docs", "content", score=0.72, label=1)
print("  Applied 3 online updates (2 relevant, 1 not-relevant)")
print("  Online updates incrementally adjust calibration parameters")


# ==================================================================
# 6. ParameterLearner standalone usage
# ==================================================================
print("\n--- 6. ParameterLearner standalone usage ---")

learner = ParameterLearner()
print(f"  Initial params: {learner.params()}")

# Batch fit with simulated scores and labels
scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9, 0.15, 0.85]
fit_labels = [0, 0, 0, 1, 1, 1, 0, 1]
learned_params = learner.fit(scores, fit_labels, mode="balanced")
print("  After batch fit:")
for param, value in sorted(learned_params.items()):
    print(f"    {param}: {value:.6f}")

# Online updates
learner.update(score=0.6, label=1)
learner.update(score=0.4, label=0)
updated_params = learner.params()
print("  After 2 online updates:")
for param, value in sorted(updated_params.items()):
    print(f"    {param}: {value:.6f}")


print("\n" + "=" * 70)
print("All calibration examples completed successfully.")
print("=" * 70)
