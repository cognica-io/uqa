#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for advanced scoring and retrieval features.

Covers sparse thresholding, attention fusion, learned fusion,
multi-stage pipeline, and fusion WAND.
"""

from __future__ import annotations

import numpy as np
import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.fusion.attention import AttentionFusion
from uqa.fusion.learned import LearnedFusion
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.multi_stage import MultiStageOperator
from uqa.operators.sparse import SparseThresholdOperator
from uqa.scoring.fusion_wand import FusionWANDScorer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FixedScoreOperator(Operator):
    """Produces a fixed posting list for benchmark setup."""

    def __init__(self, entries: list[PostingEntry]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return PostingList.from_sorted(self._entries)


def _make_entries(size: int, seed: int = 42) -> list[PostingEntry]:
    """Generate sorted PostingEntry list with random scores."""
    rng = np.random.default_rng(seed)
    doc_ids = sorted(rng.choice(size * 10, size=size, replace=False))
    return [
        PostingEntry(
            doc_id=int(did),
            payload=Payload(score=float(rng.uniform(0.0, 1.0))),
        )
        for did in doc_ids
    ]


# ---------------------------------------------------------------------------
# Sparse Thresholding
# ---------------------------------------------------------------------------


class TestSparseThreshold:
    @pytest.mark.parametrize("size", [100, 1000, 10000])
    def test_threshold_operator(self, benchmark, size: int) -> None:
        entries = _make_entries(size)
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=0.5)
        ctx = ExecutionContext()
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0

    @pytest.mark.parametrize("threshold", [0.1, 0.3, 0.5, 0.7])
    def test_threshold_levels(self, benchmark, threshold: float) -> None:
        entries = _make_entries(1000)
        source = _FixedScoreOperator(entries)
        op = SparseThresholdOperator(source, threshold=threshold)
        ctx = ExecutionContext()
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Attention Fusion
# ---------------------------------------------------------------------------


class TestAttentionFusion:
    @pytest.mark.parametrize("n_signals", [2, 3, 5, 10])
    def test_fuse(self, benchmark, n_signals: int) -> None:
        fusion = AttentionFusion(n_signals=n_signals, n_query_features=6)
        rng = np.random.default_rng(42)
        probs = [float(rng.uniform(0.3, 0.9)) for _ in range(n_signals)]
        query_features = rng.standard_normal(6).astype(np.float64)
        benchmark(fusion.fuse, probs, query_features)

    def test_extract_query_features(self, benchmark) -> None:
        from uqa.fusion.query_features import QueryFeatureExtractor
        from uqa.storage.inverted_index import MemoryInvertedIndex

        idx = MemoryInvertedIndex()
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        term_docs = gen.term_documents(num_docs=500, terms_per_doc=50)
        for doc_id, fields in term_docs:
            idx.add_document(doc_id, fields)

        extractor = QueryFeatureExtractor(idx)
        query_terms = ["term_000000", "term_000001", "term_000002"]
        benchmark(extractor.extract, query_terms, "body")


# ---------------------------------------------------------------------------
# Learned Fusion
# ---------------------------------------------------------------------------


class TestLearnedFusion:
    @pytest.mark.parametrize("n_signals", [2, 3, 5, 10])
    def test_fuse(self, benchmark, n_signals: int) -> None:
        fusion = LearnedFusion(n_signals=n_signals)
        rng = np.random.default_rng(42)
        probs = [float(rng.uniform(0.3, 0.9)) for _ in range(n_signals)]
        benchmark(fusion.fuse, probs)

    def test_fit(self, benchmark) -> None:
        n_signals = 3
        n_samples = 100
        fusion = LearnedFusion(n_signals=n_signals)
        rng = np.random.default_rng(42)
        probs = rng.uniform(0.3, 0.9, size=(n_samples, n_signals))
        labels = rng.integers(0, 2, size=n_samples).astype(np.float64)
        benchmark(fusion.fit, probs, labels)


# ---------------------------------------------------------------------------
# Fusion WAND
# ---------------------------------------------------------------------------


class TestFusionWAND:
    @pytest.mark.parametrize("k", [10, 50, 100])
    def test_top_k(self, benchmark, k: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        n_signals = 3
        pls = [
            gen.posting_list(size=1000, score_range=(0.1, 0.9))
            for _ in range(n_signals)
        ]
        ubs = [0.9] * n_signals
        scorer = FusionWANDScorer(pls, ubs, alpha=0.5, k=k)
        result = benchmark(scorer.score_top_k)
        assert len(result) <= k

    @pytest.mark.parametrize("n_signals", [2, 3, 5])
    def test_vs_exhaustive(self, benchmark, n_signals: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pls = [
            gen.posting_list(size=500, score_range=(0.1, 0.9)) for _ in range(n_signals)
        ]
        ubs = [0.9] * n_signals
        scorer = FusionWANDScorer(pls, ubs, alpha=0.5, k=10)
        result = benchmark(scorer.score_top_k)
        assert len(result) <= 10


# ---------------------------------------------------------------------------
# Multi-Stage Pipeline
# ---------------------------------------------------------------------------


class TestMultiStage:
    @pytest.mark.parametrize("size", [100, 1000])
    def test_two_stage(self, benchmark, size: int) -> None:
        rng = np.random.default_rng(42)
        doc_ids = sorted(rng.choice(size * 10, size=size, replace=False))
        stage1_entries = [
            PostingEntry(int(did), Payload(score=float(rng.uniform(0.0, 1.0))))
            for did in doc_ids
        ]
        stage2_entries = [
            PostingEntry(int(did), Payload(score=float(rng.uniform(0.0, 1.0))))
            for did in doc_ids
        ]
        stage1_op = _FixedScoreOperator(stage1_entries)
        stage2_op = _FixedScoreOperator(stage2_entries)
        ms = MultiStageOperator([(stage1_op, size // 2), (stage2_op, size // 4)])
        ctx = ExecutionContext()
        result = benchmark(ms.execute, ctx)
        assert len(result) == size // 4

    def test_three_stage(self, benchmark) -> None:
        size = 500
        rng = np.random.default_rng(42)
        doc_ids = sorted(rng.choice(size * 10, size=size, replace=False))
        entries_1 = [
            PostingEntry(int(did), Payload(score=float(rng.uniform(0.0, 1.0))))
            for did in doc_ids
        ]
        entries_2 = [
            PostingEntry(int(did), Payload(score=float(rng.uniform(0.0, 1.0))))
            for did in doc_ids
        ]
        entries_3 = [
            PostingEntry(int(did), Payload(score=float(rng.uniform(0.0, 1.0))))
            for did in doc_ids
        ]
        op1 = _FixedScoreOperator(entries_1)
        op2 = _FixedScoreOperator(entries_2)
        op3 = _FixedScoreOperator(entries_3)
        ms = MultiStageOperator([(op1, 200), (op2, 50), (op3, 10)])
        ctx = ExecutionContext()
        result = benchmark(ms.execute, ctx)
        assert len(result) == 10
