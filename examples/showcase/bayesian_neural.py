#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""From Bayes to Neurons: neural network structure emerges from probability.

Paper 4 proves that when you combine multiple calibrated probability signals
through Bayesian inference, the end-to-end computation IS a feedforward
neural network:

  raw scores -> sigmoid calibration -> logit -> linear aggregation -> sigmoid
  (input)       (Layer 1 activation) (hidden nonlinearity) (weights) (output)

This example demonstrates the correspondence step by step, then shows how
different gating functions (ReLU, Swish) and attention mechanisms connect
to the same probabilistic framework.

Demonstrates:
  - Step-by-step Bayesian fusion as neural computation
  - Sigmoid as calibration (Bernoulli exponential family)
  - Logit transform as hidden layer activation
  - ReLU gating as MAP estimator under sparse prior
  - Swish gating as Bayesian expected value (posterior mean)
  - fuse_attention as context-dependent Logarithmic Opinion Pooling
  - staged_retrieval as multi-layer depth (iterated marginalization)
"""

from __future__ import annotations

import math

import numpy as np

from uqa.core.types import Edge
from uqa.engine import Engine

# ======================================================================
# Data setup: research papers with text + vector signals
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        year INTEGER NOT NULL,
        field TEXT,
        embedding VECTOR(8)
    )
""")
engine.sql("CREATE INDEX idx_papers_gin ON papers USING gin (title, abstract)")

rng = np.random.RandomState(42)

paper_data = [
    (
        "attention is all you need",
        "self attention mechanisms replacing recurrence and convolutions",
        2017,
        "nlp",
    ),
    (
        "bert pre-training deep bidirectional transformers",
        "masked language modeling pre-training fine-tuning",
        2019,
        "nlp",
    ),
    (
        "deep residual learning for image recognition",
        "residual connections deep convolutional networks",
        2016,
        "cv",
    ),
    (
        "generative adversarial networks",
        "adversarial training generator discriminator minimax",
        2014,
        "generative",
    ),
    (
        "graph attention networks",
        "attention mechanisms for graph neural networks",
        2018,
        "graph",
    ),
    (
        "language models are few-shot learners",
        "scaling language models in-context learning prompting",
        2020,
        "nlp",
    ),
    (
        "vision transformer image recognition at scale",
        "pure transformer applied to sequences of image patches",
        2021,
        "cv",
    ),
    (
        "denoising diffusion probabilistic models",
        "progressive denoising noise schedule image generation",
        2020,
        "generative",
    ),
    (
        "flash attention fast memory-efficient attention",
        "io-aware exact attention algorithm tiling kernel fusion",
        2022,
        "architecture",
    ),
    (
        "neural machine translation by learning to align",
        "soft attention mechanism for alignment in translation",
        2015,
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

for title, abstract, year, field in paper_data:
    center = field_centers[field].astype(np.float32)
    vec = center + rng.randn(8).astype(np.float32) * 0.1
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO papers (title, abstract, year, field, embedding) "
        f"VALUES ('{title}', '{abstract}', {year}, '{field}', {arr})"
    )

# Citation graph for multi-signal fusion
engine.add_graph_edge(Edge(1, 2, 1, "cites"), table="papers")  # BERT -> Transformer
engine.add_graph_edge(Edge(2, 5, 1, "cites"), table="papers")  # GAT -> Transformer
engine.add_graph_edge(Edge(3, 6, 1, "cites"), table="papers")  # GPT-3 -> Transformer
engine.add_graph_edge(Edge(4, 6, 2, "cites"), table="papers")  # GPT-3 -> BERT
engine.add_graph_edge(Edge(5, 7, 1, "cites"), table="papers")  # ViT -> Transformer
engine.add_graph_edge(
    Edge(6, 9, 1, "cites"), table="papers"
)  # FlashAttn -> Transformer

nlp_query = field_centers["nlp"].astype(np.float32)
nlp_query = nlp_query + rng.randn(8).astype(np.float32) * 0.05
nlp_query = (nlp_query / np.linalg.norm(nlp_query)).astype(np.float32)


def logit(p):
    p = max(1e-15, min(1 - 1e-15, p))
    return math.log(p / (1.0 - p))


print("=" * 70)
print("From Bayes to Neurons: The Neural Network Inside Bayesian Fusion")
print("=" * 70)


# ==================================================================
# 1. Layer 0: Raw Scores (Input Layer)
# ==================================================================
print("\n" + "=" * 50)
print("Layer 0: Raw Scores (Input Layer)")
print("=" * 50)

# Get raw BM25 scores
text_result = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE text_match(title, 'attention')
    ORDER BY _score DESC
""")
raw_text = {row["id"]: row["_score"] for row in text_result.rows}

# Get raw cosine similarity scores
vec_result = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE knn_match(embedding, $1, 10)
    ORDER BY _score DESC
""",
    params=[nlp_query],
)
raw_vec = {row["id"]: row["_score"] for row in vec_result.rows}

print("\n  Two raw scoring signals with different scales:")
print(f"\n  {'Paper':<40} {'BM25':>8} {'Cosine':>8}")
print(f"  {'-' * 58}")
for i, (title, _, _, _) in enumerate(paper_data, 1):
    t = raw_text.get(i, 0.0)
    v = raw_vec.get(i, 0.0)
    if t > 0 or abs(v) > 0.3:
        print(f"  {title[:40]:<40} {t:>8.4f} {v:>8.4f}")

print("\n  These are the INPUTS to the neural network.")
print("  BM25 in [0, +inf), cosine in [-1, 1] -- incompatible scales.")


# ==================================================================
# 2. Layer 1: Sigmoid Calibration (First Activation)
# ==================================================================
print("\n" + "=" * 50)
print("Layer 1: Sigmoid Calibration")
print("=" * 50)

print("""
  Bayesian BM25 applies: P_i = sigma(alpha_i * s_i - beta_i)

  This sigmoid is NOT a design choice. It follows necessarily from
  the Bernoulli exponential family structure of binary relevance:
    R ~ Bernoulli(p), where p is the relevance probability.
  The natural parameter of Bernoulli is logit(p), and the
  inverse link function is the sigmoid. (Paper 4, Theorem 6.3.1)
""")

# Get calibrated probabilities
bayes_result = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE bayesian_match(title, 'attention')
    ORDER BY _score DESC
""")
calibrated_text = {row["id"]: row["_score"] for row in bayes_result.rows}

print(f"  {'Paper':<40} {'Raw BM25':>10} {'P(rel)':>10}")
print(f"  {'-' * 62}")
for i, (title, _, _, _) in enumerate(paper_data, 1):
    if i in raw_text:
        print(
            f"  {title[:40]:<40} {raw_text[i]:>10.4f} {calibrated_text.get(i, 0.0):>10.4f}"
        )

print("\n  Raw BM25 scores are now calibrated probabilities in [0, 1].")
print("  The cosine similarity from knn_match is also calibrated internally.")


# ==================================================================
# 3. Hidden Layer: Logit Transform
# ==================================================================
print("\n" + "=" * 50)
print("Hidden Layer: Logit Transform")
print("=" * 50)

print("""
  Each calibrated probability is transformed to log-odds space:
    l_i = logit(P_i) = log(P_i / (1 - P_i))

  Log-odds space is where Bayesian updates are naturally LINEAR.
  This is the hidden layer's nonlinear activation function.
""")

print(f"  {'Paper':<40} {'P(rel)':>8} {'logit(P)':>10}")
print(f"  {'-' * 60}")
for i, (title, _, _, _) in enumerate(paper_data, 1):
    p = calibrated_text.get(i, 0.0)
    if p > 0:
        lo = logit(p)
        print(f"  {title[:40]:<40} {p:>8.4f} {lo:>10.4f}")


# ==================================================================
# 4. Output Layer: Linear Aggregation + Sigmoid
# ==================================================================
print("\n" + "=" * 50)
print("Output Layer: Aggregation + Sigmoid")
print("=" * 50)

print("""
  The hidden layer outputs are aggregated linearly with confidence
  scaling (the sqrt(n) law prevents over-confidence):

    logit(P_fused) = (1/sqrt(n)) * sum(logit(P_i))
    P_fused = sigma(logit(P_fused))

  This is EXACTLY a feedforward neural network:
    Input:  [s_1, s_2, ..., s_n]   (raw scores)
    Hidden: logit(sigma(alpha*s - beta))  (nonlinear activation)
    Output: sigma(mean / sqrt(n))  (posterior computation)
""")

# Show the fuse_log_odds result
fused_result = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        knn_match(embedding, $1, 10)
    )
    ORDER BY _score DESC
""",
    params=[nlp_query],
)

print(f"  {'Paper':<40} {'fuse_log_odds':>14}")
print(f"  {'-' * 56}")
for row in fused_result.rows[:5]:
    print(f"  {row['title'][:40]:<40} {row['_score']:>14.4f}")

print("""
  The computation graph:

    BM25 score -----> sigma(a1*s - b1) --> logit --> \\
                                                      mean/sqrt(n) --> sigma --> P(rel)
    cosine sim -----> sigma(a2*s - b2) --> logit --> /

  When both signals use the SAME sigmoid calibration (homogeneous),
  logit(sigma(x)) = x (identity), and the network collapses to
  logistic regression. When calibrations DIFFER (heterogeneous,
  the practical case), the logit is a genuine nonlinearity --
  yielding a true two-layer neural network. (Paper 4, Theorem 5.2.1)
""")


# ==================================================================
# 5. Gating Functions: Probabilistic Meanings
# ==================================================================
print("=" * 50)
print("Gating Functions: The Probabilistic Hierarchy")
print("=" * 50)

print("""
  Paper 4 derives three activation functions from three probabilistic
  questions applied to the same evidence:

    Sigmoid: "How probable is relevance?"
             MAP: argmax P(R=1|evidence) = sigma(evidence)
             The posterior probability itself.

    ReLU:    "How much relevant signal, if any?"
             MAP: argmax P(signal|R=1, signal >= 0)
             Sparse non-negative prior => max(0, evidence)
             Zeroes out negative log-odds (non-evidence).

    Swish:   "What is the expected amount of relevant signal?"
             E[signal * I(signal>0) | evidence]
             Posterior mean under sparse gating = x * sigma(x)
             Smooth version of ReLU; lets weak signals leak through.

  ReLU is the MAP estimator; Swish is the Bayesian posterior mean.
  The MAP-to-Bayes duality in classical statistics manifests as
  the ReLU-to-Swish transition in neural activations.
""")

# Compare gating strategies on the same query
print("--- Gating comparison: 'attention' + graph_traversal ---")
print(f"  {'Paper':<40} {'None':>8} {'ReLU':>8} {'Swish':>8}")
print(f"  {'-' * 66}")

for gating in ("none", "relu", "swish"):
    if gating == "none":
        result = engine.sql("""
            SELECT id, title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cites', 1)
            )
            ORDER BY _score DESC
        """)
    else:
        result = engine.sql(f"""
            SELECT id, title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cites', 1),
                '{gating}'
            )
            ORDER BY _score DESC
        """)
    if gating == "none":
        gating_scores = {}
        gating_order = []
        for row in result.rows:
            gating_scores[("none", row["id"])] = row["_score"]
            gating_order.append(row["id"])
    else:
        for row in result.rows:
            gating_scores[(gating, row["id"])] = row["_score"]

for pid in gating_order:
    title = paper_data[pid - 1][0]
    none_s = gating_scores.get(("none", pid), 0.0)
    relu_s = gating_scores.get(("relu", pid), 0.0)
    swish_s = gating_scores.get(("swish", pid), 0.0)
    print(f"  {title[:40]:<40} {none_s:>8.4f} {relu_s:>8.4f} {swish_s:>8.4f}")

print("""
  ReLU zeroes out negative log-odds: only positive evidence contributes.
  Swish smoothly gates: weak evidence contributes proportionally.
  No gating: all evidence contributes equally (standard log-odds mean).
""")


# ==================================================================
# 6. Attention: Context-Dependent Weights
# ==================================================================
print("=" * 50)
print("Attention Mechanism: Logarithmic Opinion Pooling")
print("=" * 50)

print("""
  Standard fuse_log_odds uses UNIFORM weights for all signals.
  fuse_attention allows signal RELIABILITY to depend on context --
  mathematically, this is Logarithmic Opinion Pooling with
  context-dependent weights, equivalent to Hinton's Product of
  Experts (PoE). This IS the attention mechanism.

  In fuse_log_odds:  logit(P) = (1/n) * sum(logit(P_i))
  In fuse_attention: logit(P) = sum(w_i * logit(P_i))
                     where w_i depends on query-signal interaction.
""")

# Compare uniform vs attention-weighted fusion
print("--- fuse_log_odds vs fuse_attention ---")
print(f"  {'Paper':<40} {'LogOdds':>10} {'Attention':>10}")
print(f"  {'-' * 62}")

logodds_r = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE fuse_log_odds(
        bayesian_match(title, 'attention'),
        bayesian_match(abstract, 'attention')
    )
    ORDER BY _score DESC
""")

attention_r = engine.sql("""
    SELECT id, title, _score FROM papers
    WHERE fuse_attention(
        bayesian_match(title, 'attention'),
        bayesian_match(abstract, 'attention')
    )
    ORDER BY _score DESC
""")

lo_map = {row["id"]: row["_score"] for row in logodds_r.rows}
at_map = {row["id"]: row["_score"] for row in attention_r.rows}

all_ids = sorted(set(lo_map.keys()) | set(at_map.keys()))
for pid in all_ids:
    title = paper_data[pid - 1][0]
    print(
        f"  {title[:40]:<40} {lo_map.get(pid, 0.0):>10.4f} {at_map.get(pid, 0.0):>10.4f}"
    )

print("\n  fuse_attention dynamically re-weights signals based on")
print("  query-signal interaction, giving more weight to the more")
print("  informative signal for each specific query.")


# ==================================================================
# 7. Depth: staged_retrieval as Multi-Layer Network
# ==================================================================
print("\n" + "=" * 50)
print("Depth: staged_retrieval as Multi-Layer Network")
print("=" * 50)

print("""
  Paper 4 (Section 9) proves that deep networks correspond to
  iterated Bayesian marginalization over latent variables. Each
  layer constructs the evidence required by the next.

  staged_retrieval implements this: each stage refines the
  candidate set, constructing better evidence for subsequent stages.

    Stage 1: broad recall (text_match, top-k1)
    Stage 2: precise re-ranking (bayesian_match, top-k2)
    Stage 3: final fusion (knn_match, top-k3)
""")

# 2-stage pipeline
result_2stage = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE staged_retrieval(
        text_match(title, 'attention'),
        5,
        bayesian_match(abstract, 'attention mechanisms'),
        3
    )
    ORDER BY _score DESC
""",
)

print("--- 2-stage pipeline: text(top-5) -> abstract(top-3) ---")
for row in result_2stage.rows:
    print(f"  score={row['_score']:.4f}  {row['title']}")

# 3-stage pipeline
result_3stage = engine.sql(
    """
    SELECT id, title, _score FROM papers
    WHERE staged_retrieval(
        text_match(title, 'attention'),
        6,
        bayesian_match(abstract, 'attention'),
        4,
        knn_match(embedding, $1, 3),
        2
    )
    ORDER BY _score DESC
""",
    params=[nlp_query],
)

print("\n--- 3-stage cascade: text(6) -> abstract(4) -> vector(2) ---")
for row in result_3stage.rows:
    print(f"  score={row['_score']:.4f}  {row['title']}")

print("""
  Each stage is a "layer" that:
    1. Receives candidates from the previous layer
    2. Applies its own scoring function (evidence construction)
    3. Selects top-k candidates (marginalization)
    4. Passes refined candidates to the next layer
""")


# ==================================================================
# 8. The Full Picture
# ==================================================================
print("=" * 50)
print("The Full Picture")
print("=" * 50)

print("""
  UQA's multi-signal fusion IS a neural network, derived from
  first-principles Bayesian inference:

  +---------------------------------------------------------------+
  | INPUT LAYER           raw scores from each paradigm           |
  |   text_match(s1)      knn_match(s2)      pagerank(s3)         |
  +---------------------------------------------------------------+
                                 |
  +---------------------------------------------------------------+
  | CALIBRATION           sigmoid: P_i = sigma(a_i*s_i - b_i)     |
  |   (Bernoulli exponential family => sigmoid is inevitable)     |
  +---------------------------------------------------------------+
                                 |
  +---------------------------------------------------------------+
  | HIDDEN LAYER          logit: l_i = log(P_i / (1-P_i))         |
  |   Optional gating:                                            |
  |     none  -> l_i              (standard)                      |
  |     ReLU  -> max(0, l_i)      (MAP estimator, sparse prior)   |
  |     Swish -> l_i*sigma(l_i)   (Bayes posterior mean)          |
  +---------------------------------------------------------------+
                                 |
  +---------------------------------------------------------------+
  | AGGREGATION           sum(l_i) / n^alpha                      |
  |   Uniform:    fuse_log_odds    (equal weights)                |
  |   Attention:  fuse_attention   (context-dependent weights)    |
  |   Depth:      staged_retrieval (iterated marginalization)     |
  +---------------------------------------------------------------+
                                 |
  +---------------------------------------------------------------+
  | OUTPUT LAYER          sigmoid: P_fused = sigma(aggregated)    |
  |   The final P(relevant | all evidence)                        |
  +---------------------------------------------------------------+

  The direction of explanation is reversed:
    Traditional: design a neural network, then analyze it probabilistically
    UQA (Paper 4): start with probability, arrive at neural network

  Every architectural choice -- sigmoid activation, ReLU gating,
  attention mechanism, network depth -- is a CONSEQUENCE of
  probabilistic reasoning, not a design decision.
""")


print("=" * 70)
print("All Bayesian neural examples completed successfully.")
print("=" * 70)
