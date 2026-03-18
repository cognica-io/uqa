#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Calibration Matters: why Bayesian fusion beats naive score combination.

BM25 scores are unbounded [0, +inf), cosine similarity is bounded [-1, 1].
Naive combination (adding raw scores) lets BM25 dominate the ranking.
Bayesian BM25 calibrates both signals into P(relevant) in [0, 1], enabling
principled probabilistic fusion via log-odds conjunction.

This example demonstrates the calibration problem and its solution by
comparing ranking quality across four fusion strategies on the same data.

Demonstrates:
  - Signal dominance: raw BM25 >> cosine similarity in magnitude
  - Bayesian calibration: text_match vs bayesian_match score ranges
  - Fusion comparison: naive sum, fuse_prob_and, fuse_prob_or, fuse_log_odds
  - CalibrationMetrics: ECE, Brier score, reliability diagram
  - Parameter learning: learn_scoring_params, update_scoring_params
"""

from __future__ import annotations

import math

import numpy as np

from uqa.engine import Engine
from uqa.scoring.calibration import CalibrationMetrics

# ======================================================================
# Data setup: 10 ML papers with text + vector embeddings
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        field TEXT,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

paper_data = [
    (
        "attention is all you need",
        "self attention mechanisms replacing recurrence and convolutions",
        "nlp",
    ),
    (
        "bert pre-training deep bidirectional transformers",
        "masked language modeling pre-training fine-tuning",
        "nlp",
    ),
    (
        "deep residual learning for image recognition",
        "residual connections deep convolutional networks",
        "cv",
    ),
    (
        "generative adversarial networks",
        "adversarial training generator discriminator minimax",
        "generative",
    ),
    (
        "graph attention networks",
        "attention mechanisms for graph neural networks",
        "graph",
    ),
    (
        "language models are few-shot learners",
        "scaling language models in-context learning prompting",
        "nlp",
    ),
    (
        "vision transformer image recognition at scale",
        "pure transformer applied to sequences of image patches",
        "cv",
    ),
    (
        "denoising diffusion probabilistic models",
        "progressive denoising noise schedule image generation",
        "generative",
    ),
    (
        "flash attention fast memory-efficient attention",
        "io-aware exact attention algorithm tiling kernel fusion",
        "architecture",
    ),
    (
        "neural machine translation by learning to align",
        "soft attention mechanism for alignment in translation",
        "nlp",
    ),
]

field_centers = {
    "nlp": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0]),
    "cv": np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "graph": np.array([0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "generative": np.array([0.0, 0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]),
    "architecture": np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
}

for title, abstract, field in paper_data:
    center = field_centers[field].astype(np.float32)
    vec = center + rng.randn(8).astype(np.float32) * 0.1
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, abstract, field, embedding) "
        f"VALUES ('{title}', '{abstract}', '{field}', {arr})"
    )

# Query: "attention transformer" -- find papers about attention/transformers
# Ground truth relevance labels (1=relevant, 0=not relevant)
# Papers 1,2,5,7,9,10 mention attention or transformer
relevance_labels = [1, 1, 0, 0, 1, 0, 1, 0, 1, 1]

# Vector query pointing toward NLP region
nlp_query = field_centers["nlp"].astype(np.float32)
nlp_query = nlp_query + rng.randn(8).astype(np.float32) * 0.05
nlp_query = (nlp_query / np.linalg.norm(nlp_query)).astype(np.float32)


print("=" * 70)
print("Calibration Matters: Bayesian Fusion vs Naive Combination")
print("=" * 70)


# ==================================================================
# 1. The Scale Problem: BM25 vs Cosine Similarity
# ==================================================================
print("\n" + "=" * 50)
print("1. The Scale Problem")
print("=" * 50)

# Get raw BM25 scores
text_result = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE text_match(title, 'attention transformer')
    ORDER BY _score DESC
""")
text_scores = {}
for row in text_result.rows:
    text_scores[row["id"]] = row["_score"]

# Get vector similarity scores
vec_result = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE knn_match(embedding, $1, 10)
    ORDER BY _score DESC
""",
    params=[nlp_query],
)
vec_scores = {}
for row in vec_result.rows:
    vec_scores[row["id"]] = row["_score"]

# Get calibrated Bayesian BM25 scores
bayes_result = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE bayesian_match(title, 'attention transformer')
    ORDER BY _score DESC
""")
bayes_scores = {}
for row in bayes_result.rows:
    bayes_scores[row["id"]] = row["_score"]

# Show the scale mismatch
print("\n--- Raw BM25 vs Cosine Similarity vs Bayesian BM25 ---")
print(f"  {'Paper':<40} {'BM25':>8} {'Cosine':>8} {'Bayes':>8} {'Rel':>5}")
print(f"  {'-' * 67}")
for i, (title, _, _) in enumerate(paper_data, 1):
    bm25 = text_scores.get(i, 0.0)
    cos = vec_scores.get(i, 0.0)
    bayes = bayes_scores.get(i, 0.0)
    rel = relevance_labels[i - 1]
    marker = " <--" if rel == 1 else ""
    print(f"  {title[:40]:<40} {bm25:>8.4f} {cos:>8.4f} {bayes:>8.4f} {rel:>5}{marker}")

bm25_range = (
    min(text_scores.values()) if text_scores else 0,
    max(text_scores.values()) if text_scores else 0,
)
cos_range = (
    min(vec_scores.values()) if vec_scores else 0,
    max(vec_scores.values()) if vec_scores else 0,
)
print(f"\n  BM25 score range:   [{bm25_range[0]:.4f}, {bm25_range[1]:.4f}]")
print(f"  Cosine sim range:   [{cos_range[0]:.4f}, {cos_range[1]:.4f}]")
print("  Bayesian BM25:      probabilities in [0, 1]")
print("\n  Problem: BM25 scores are ~1-3x, cosine is ~0.0-1.0.")
print("  Naive addition: BM25 signal dominates the ranking.")


# ==================================================================
# 2. Signal Dominance in Naive Combination
# ==================================================================
print("\n" + "=" * 50)
print("2. Signal Dominance: Naive Sum Ranking")
print("=" * 50)

# Compute naive sum scores
naive_ranking = []
for i in range(1, 11):
    bm25 = text_scores.get(i, 0.0)
    cos = vec_scores.get(i, 0.0)
    naive_sum = bm25 + cos
    naive_ranking.append((i, paper_data[i - 1][0], bm25, cos, naive_sum))

# Sort by naive sum
naive_ranking.sort(key=lambda x: x[4], reverse=True)

print("\n--- Naive sum = BM25 + cosine_similarity ---")
print(f"  {'Rank':>4} {'Paper':<40} {'BM25':>8} {'Cosine':>8} {'Sum':>8} {'Rel':>5}")
print(f"  {'-' * 73}")
for rank, (pid, title, bm25, cos, total) in enumerate(naive_ranking[:7], 1):
    rel = relevance_labels[pid - 1]
    print(
        f"  {rank:>4} {title[:40]:<40} {bm25:>8.4f} {cos:>8.4f} {total:>8.4f} {rel:>5}"
    )

print("\n  Observation: documents with high BM25 always rank at top,")
print("  regardless of vector signal. This is Theorem 1.2.2 (Paper 3).")


# ==================================================================
# 3. Bayesian Calibration: The Solution
# ==================================================================
print("\n" + "=" * 50)
print("3. Bayesian Calibration")
print("=" * 50)

print("\n  Bayesian BM25 transforms raw BM25 scores into calibrated")
print("  P(relevant) in [0, 1] via sigmoid likelihood model:")
print("    P(rel | score) = sigma(alpha * score - beta)")
print()
print("  bayesian_match vs text_match:")

print(f"\n  {'Paper':<40} {'text_match':>12} {'bayesian':>12}")
print(f"  {'-' * 65}")
for i, (title, _, _) in enumerate(paper_data, 1):
    bm25 = text_scores.get(i, 0.0)
    bayes = bayes_scores.get(i, 0.0)
    if bm25 > 0 or bayes > 0:
        print(f"  {title[:40]:<40} {bm25:>12.4f} {bayes:>12.4f}")

print("\n  Now both signals share a common probabilistic semantics.")
print("  fuse_log_odds combines them in log-odds space:")
print("    logit(P_fused) = mean(logit(P_text), logit(P_vec)) / sqrt(n)")


# ==================================================================
# 4. Fusion Strategy Comparison
# ==================================================================
print("\n" + "=" * 50)
print("4. Fusion Strategy Comparison")
print("=" * 50)

# fuse_log_odds
fused_logodds = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention transformer'),
        knn_match(embedding, $1, 10)
    )
    ORDER BY _score DESC
""",
    params=[nlp_query],
)
logodds_scores = {row["id"]: row["_score"] for row in fused_logodds.rows}

# fuse_prob_and
fused_pand = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE fuse_prob_and(
        text_match(title, 'attention transformer'),
        knn_match(embedding, $1, 10)
    )
    ORDER BY _score DESC
""",
    params=[nlp_query],
)
pand_scores = {row["id"]: row["_score"] for row in fused_pand.rows}

# fuse_prob_or
fused_por = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE fuse_prob_or(
        text_match(title, 'attention transformer'),
        knn_match(embedding, $1, 10)
    )
    ORDER BY _score DESC
""",
    params=[nlp_query],
)
por_scores = {row["id"]: row["_score"] for row in fused_por.rows}

print("\n--- Side-by-side: four fusion strategies ---")
print(
    f"  {'Paper':<40} {'Naive':>7} {'LogOdds':>8} {'ProbAND':>8} {'ProbOR':>8} {'Rel':>5}"
)
print(f"  {'-' * 79}")
for i, (title, _, _) in enumerate(paper_data, 1):
    bm25 = text_scores.get(i, 0.0)
    cos = vec_scores.get(i, 0.0)
    naive = bm25 + cos
    lo = logodds_scores.get(i, 0.0)
    pa = pand_scores.get(i, 0.0)
    po = por_scores.get(i, 0.0)
    rel = relevance_labels[i - 1]
    if naive > 0 or lo > 0 or pa > 0 or po > 0:
        print(
            f"  {title[:40]:<40} {naive:>7.4f} {lo:>8.4f} {pa:>8.4f} {po:>8.4f} {rel:>5}"
        )

print("\n  fuse_log_odds: Bayesian conjunction (highest precision)")
print("  fuse_prob_and: P(A and B) = P(A) * P(B) (strict intersection)")
print("  fuse_prob_or:  P(A or B) = 1 - (1-P(A))*(1-P(B)) (broad recall)")


# ==================================================================
# 5. Calibration Metrics: ECE and Brier Score
# ==================================================================
print("\n" + "=" * 50)
print("5. Calibration Metrics")
print("=" * 50)


# Collect predictions from different methods for all 10 documents
# For documents not returned by a method, use 0.0 as predicted probability
def collect_predictions(score_map, n=10):
    return [score_map.get(i, 0.0) for i in range(1, n + 1)]


naive_preds = []
for i in range(1, 11):
    bm25 = text_scores.get(i, 0.0)
    cos = vec_scores.get(i, 0.0)
    raw_sum = bm25 + cos
    # Clamp naive sum into [0, 1] with sigmoid for fair comparison
    naive_preds.append(1.0 / (1.0 + math.exp(-raw_sum)) if raw_sum != 0 else 0.0)

logodds_preds = collect_predictions(logodds_scores)

print("\n--- ECE and Brier score comparison ---")
print(f"  {'Method':<25} {'ECE':>10} {'Brier':>10}  (lower = better)")
print(f"  {'-' * 47}")

for method_name, preds in [
    ("Naive (sigmoid(sum))", naive_preds),
    ("fuse_log_odds", logodds_preds),
]:
    ece = CalibrationMetrics.ece(preds, relevance_labels, n_bins=5)
    brier = CalibrationMetrics.brier(preds, relevance_labels)
    print(f"  {method_name:<25} {ece:>10.6f} {brier:>10.6f}")


# ==================================================================
# 6. Reliability Diagram
# ==================================================================
print("\n" + "=" * 50)
print("6. Reliability Diagram")
print("=" * 50)

print("\n  A perfectly calibrated model has avg_predicted == avg_actual")
print("  in every bin. Deviations indicate miscalibration.")

for method_name, preds in [
    ("Naive (sigmoid(sum))", naive_preds),
    ("fuse_log_odds", logodds_preds),
]:
    diagram = CalibrationMetrics.reliability_diagram(preds, relevance_labels, n_bins=5)
    print(f"\n--- {method_name} ---")
    print(f"  {'Avg Predicted':>15} {'Avg Actual':>12} {'Count':>7}")
    print(f"  {'-' * 36}")
    for avg_pred, avg_actual, count in diagram:
        gap = abs(avg_pred - avg_actual)
        bar = "*" * int(gap * 50)
        print(f"  {avg_pred:>15.4f} {avg_actual:>12.4f} {count:>7}  {bar}")


# ==================================================================
# 7. Parameter Learning
# ==================================================================
print("\n" + "=" * 50)
print("7. Parameter Learning")
print("=" * 50)

print("\n  learn_scoring_params uses labeled relevance judgments to")
print("  optimize sigmoid calibration parameters (alpha, beta).")

learned = engine.learn_scoring_params(
    "papers", "title", "attention", relevance_labels, mode="balanced"
)
print("\n--- Learned parameters for 'attention' query ---")
for param, value in sorted(learned.items()):
    print(f"  {param}: {value:.6f}")

print("\n  These parameters can be saved and applied to future queries,")
print("  progressively improving calibration quality over time.")


# ==================================================================
# 8. Online Parameter Update
# ==================================================================
print("\n" + "=" * 50)
print("8. Online Parameter Update")
print("=" * 50)

print("\n  Simulating user feedback: incrementally updating calibration.")
engine.update_scoring_params("papers", "title", score=0.85, label=1)
engine.update_scoring_params("papers", "title", score=0.10, label=0)
engine.update_scoring_params("papers", "title", score=0.72, label=1)
engine.update_scoring_params("papers", "title", score=0.05, label=0)
print("  Applied 4 online updates (2 relevant, 2 not-relevant)")
print("  Online updates adjust calibration without full retraining.")


print("\n" + "=" * 70)
print("All calibration examples completed successfully.")
print("=" * 70)
