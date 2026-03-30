#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""BEIR Hybrid Search Benchmark (Paper 5, Section 8).

Metrics: NDCG@10, MAP@10, Recall@10, ECE, Brier, LogLoss
Methods: BM25, Dense, RRF, Convex, Bayesian-Balanced
Protocol: top-1000 per signal, union candidates, pytrec_eval
BM25: Bayesian BM25 on body field with Porter stemmer
Dense: all-MiniLM-L6-v2 cosine similarity via IVF
"""

from __future__ import annotations

import itertools
import math
import sys
import tempfile

import numpy as np
import pytrec_eval
from bayesian_bm25 import balanced_log_odds_fusion

from benchmarks.data.beir_loader import load
from uqa.engine import Engine

K = 1000


# -- Calibration metrics ---------------------------------------------------


def ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    p = np.array(probs)
    y = np.array(labels)
    bins = np.linspace(0, 1, n_bins + 1)
    total = 0.0
    for lo, hi in itertools.pairwise(bins):
        mask = (p >= lo) & (p < hi)
        if mask.sum() == 0:
            continue
        total += mask.sum() * abs(p[mask].mean() - y[mask].mean())
    return total / max(len(p), 1)


def brier(probs: list[float], labels: list[int]) -> float:
    return float(np.mean((np.array(probs) - np.array(labels)) ** 2))


def logloss(probs: list[float], labels: list[int]) -> float:
    p = np.clip(np.array(probs, dtype=np.float64), 1e-15, 1 - 1e-15)
    y = np.array(labels, dtype=np.float64)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


# -- pytrec_eval wrapper ---------------------------------------------------


def ir_metrics(
    run: dict[str, dict[str, float]],
    qrels_dict: dict[str, dict[str, int]],
) -> tuple[float, float, float]:
    evaluator = pytrec_eval.RelevanceEvaluator(
        qrels_dict, {"ndcg_cut_10", "map_cut_10", "recall_10"}
    )
    results = evaluator.evaluate(run)
    ndcg, mapp, rec = [], [], []
    for qid in results:
        ndcg.append(results[qid]["ndcg_cut_10"])
        mapp.append(results[qid]["map_cut_10"])
        rec.append(results[qid]["recall_10"])
    return float(np.mean(ndcg)), float(np.mean(mapp)), float(np.mean(rec))


# -- Per-dataset evaluation -------------------------------------------------


def run_dataset(ds_name: str, max_queries: int = 0) -> None:
    data = load(ds_name)
    db_path = tempfile.mktemp(suffix=".db")
    e = Engine(db_path)
    dim = data.dim
    nlist = max(8, min(64, data.n_docs // 100))

    e.sql(
        f"CREATE TABLE corpus ("
        f"  id SERIAL PRIMARY KEY, doc_str_id TEXT NOT NULL,"
        f"  title TEXT NOT NULL, body TEXT NOT NULL,"
        f"  embedding VECTOR({dim}))"
    )
    e.sql("CREATE INDEX idx_corpus_gin ON corpus USING gin (title, body)")
    e.sql(
        f"CREATE INDEX idx_emb ON corpus USING ivf (embedding) WITH (nlist = {nlist})"
    )
    e.create_analyzer(
        "english_stem",
        {
            "tokenizer": {"type": "standard"},
            "token_filters": [
                {"type": "lowercase"},
                {"type": "porter_stem"},
            ],
        },
    )
    e.set_table_analyzer("corpus", "body", "english_stem")
    e.set_table_analyzer("corpus", "title", "english_stem")

    for i in range(data.n_docs):
        did = data.doc_ids[i]
        title = data.titles[i].replace("'", "''")
        body = data.texts[i].replace("'", "''")
        emb = data.corpus_embeddings[i]
        arr_str = "ARRAY[" + ",".join(str(float(v)) for v in emb) + "]"
        e.sql(
            f"INSERT INTO corpus (doc_str_id, title, body, embedding) "
            f"VALUES ('{did}', '{title}', '{body}', {arr_str})"
        )

    n_q = data.n_queries if max_queries <= 0 else min(max_queries, data.n_queries)

    # pytrec_eval qrels
    pt_qrels: dict[str, dict[str, int]] = {}
    for qid, rels in data.qrels.items():
        pt_qrels[qid] = {d: int(r) for d, r in rels.items() if r > 0}

    runs: dict[str, dict[str, dict[str, float]]] = {
        m: {} for m in ["Dense", "BM25", "RRF", "Convex", "Balanced"]
    }
    cal: dict[str, dict[str, list]] = {
        m: {"probs": [], "labels": []} for m in ["Dense", "BM25", "Balanced"]
    }

    for qi in range(n_q):
        qid = data.query_ids[qi]
        qvec = data.query_embeddings[qi]
        qtext = data.query_texts[qi]
        qrels = data.qrels.get(qid, {})
        if not qrels:
            continue
        sq = qtext.replace("'", "''")

        # Dense
        vec_rows = e.sql(
            "SELECT id, doc_str_id, _score FROM corpus "
            "WHERE knn_match(embedding, $1, $2) ORDER BY _score DESC",
            params=[qvec, K],
        )
        if not vec_rows:
            continue
        vec_map = {r["doc_str_id"]: float(r["_score"]) for r in vec_rows}
        runs["Dense"][qid] = dict(vec_map)

        # BM25
        bm25_rows = e.sql(
            f"SELECT id, doc_str_id, _score FROM corpus "
            f"WHERE bayesian_match(body, '{sq}') "
            f"ORDER BY _score DESC LIMIT {K}"
        )
        bm25_map = (
            {r["doc_str_id"]: float(r["_score"]) for r in bm25_rows}
            if bm25_rows
            else {}
        )
        runs["BM25"][qid] = dict(bm25_map)

        # Union candidates
        all_docs = sorted(set(vec_map) | set(bm25_map))

        # RRF (k=60)
        vr = {r["doc_str_id"]: i for i, r in enumerate(vec_rows)}
        br = {r["doc_str_id"]: i for i, r in enumerate(bm25_rows)} if bm25_rows else {}
        rrf_scores = {}
        for d in all_docs:
            s = 0.0
            if d in vr:
                s += 1.0 / (60 + vr[d] + 1)
            if d in br:
                s += 1.0 / (60 + br[d] + 1)
            rrf_scores[d] = s
        runs["RRF"][qid] = rrf_scores

        # Convex (min-max norm, w=0.5)
        dense_arr = np.array([(1 + vec_map.get(d, -1)) / 2 for d in all_docs])
        sparse_arr = np.array([bm25_map.get(d, 0.0) for d in all_docs])

        def mm(a: np.ndarray) -> np.ndarray:
            mn, mx = a.min(), a.max()
            return (a - mn) / (mx - mn) if mx > mn else np.zeros_like(a)

        cx = 0.5 * mm(dense_arr) + 0.5 * mm(sparse_arr)
        runs["Convex"][qid] = {all_docs[i]: float(cx[i]) for i in range(len(all_docs))}

        # Bayesian-Balanced
        sp = np.clip(sparse_arr, 1e-10, 1 - 1e-10)
        da = np.array([vec_map.get(d, -1.0) for d in all_docs])
        bf = balanced_log_odds_fusion(sp, da, weight=0.5)
        runs["Balanced"][qid] = {
            all_docs[i]: float(bf[i]) for i in range(len(all_docs))
        }

        # Calibration data
        for j, d in enumerate(all_docs):
            label = 1 if qrels.get(d, 0) > 0 else 0
            p_dense = (1 + vec_map.get(d, -1)) / 2
            cal["Dense"]["probs"].append(p_dense)
            cal["Dense"]["labels"].append(label)

            p_bm25 = bm25_map.get(d, 0.0)
            cal["BM25"]["probs"].append(max(p_bm25, 1e-10))
            cal["BM25"]["labels"].append(label)

            bval = float(bf[j])
            p_bal = 1.0 / (1.0 + math.exp(-max(min(bval * 5, 20), -20)))
            cal["Balanced"]["probs"].append(p_bal)
            cal["Balanced"]["labels"].append(label)

    e.close()

    # IR metrics
    ir = {}
    for m in runs:
        if runs[m]:
            ndcg, mapp, rec = ir_metrics(runs[m], pt_qrels)
            ir[m] = {"ndcg": ndcg, "map": mapp, "recall": rec}

    cal_m = {}
    for m in cal:
        if cal[m]["probs"]:
            p, lb = cal[m]["probs"], cal[m]["labels"]
            cal_m[m] = {
                "ece": ece(p, lb),
                "brier": brier(p, lb),
                "logloss": logloss(p, lb),
            }

    # Print
    print(f"\n{'=' * 80}")
    print(f"  BEIR {ds_name} ({data.n_docs} docs, {n_q} queries, K={K})")
    print(f"{'=' * 80}")

    print(f"\n  {'Method':<14} {'NDCG@10':>10} {'MAP@10':>10} {'Recall@10':>10}")
    print(f"  {'-' * 46}")
    for m in ["Dense", "BM25", "RRF", "Convex", "Balanced"]:
        if m in ir:
            print(
                f"  {m:<14} "
                f"{ir[m]['ndcg']:10.4f} "
                f"{ir[m]['map']:10.4f} "
                f"{ir[m]['recall']:10.4f}"
            )

    print(f"\n  {'Method':<14} {'ECE':>10} {'Brier':>10} {'LogLoss':>10}")
    print(f"  {'-' * 46}")
    for m in ["Dense", "BM25", "Balanced"]:
        if m in cal_m:
            print(
                f"  {m:<14} "
                f"{cal_m[m]['ece']:10.4f} "
                f"{cal_m[m]['brier']:10.4f} "
                f"{cal_m[m]['logloss']:10.4f}"
            )

    print()


def main() -> None:
    datasets = sys.argv[1:] if len(sys.argv) > 1 else ["nfcorpus", "scifact", "arguana"]
    for ds in datasets:
        run_dataset(ds)


if __name__ == "__main__":
    main()
