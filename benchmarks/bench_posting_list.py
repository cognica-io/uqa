#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for PostingList merge operations.

PostingList is UQA's universal abstraction. Two-pointer merge performance
directly impacts every query paradigm.
"""

from __future__ import annotations

import functools

import pytest

from benchmarks.data.generators import BenchmarkDataGenerator

# ---------------------------------------------------------------------------
# Union
# ---------------------------------------------------------------------------


class TestUnion:
    @pytest.mark.parametrize("size", [1_000, 10_000, 100_000])
    def test_union_by_size(self, benchmark, size: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=size, overlap=0.3)
        result = benchmark(pl1.union, pl2)
        assert len(result) > 0

    @pytest.mark.parametrize("overlap", [0.0, 0.3, 0.7, 1.0])
    def test_union_by_overlap(self, benchmark, overlap: float) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=10_000, overlap=overlap)
        result = benchmark(pl1.union, pl2)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Intersect
# ---------------------------------------------------------------------------


class TestIntersect:
    @pytest.mark.parametrize("size", [1_000, 10_000, 100_000])
    def test_intersect_by_size(self, benchmark, size: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=size, overlap=0.3)
        result = benchmark(pl1.intersect, pl2)
        assert len(result) >= 0

    @pytest.mark.parametrize("overlap", [0.0, 0.3, 0.7, 1.0])
    def test_intersect_by_overlap(self, benchmark, overlap: float) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=10_000, overlap=overlap)
        result = benchmark(pl1.intersect, pl2)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Difference
# ---------------------------------------------------------------------------


class TestDifference:
    @pytest.mark.parametrize("size", [1_000, 10_000, 100_000])
    def test_difference_by_size(self, benchmark, size: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=size, overlap=0.3)
        result = benchmark(pl1.difference, pl2)
        assert len(result) >= 0

    @pytest.mark.parametrize("overlap", [0.0, 0.3, 0.7, 1.0])
    def test_difference_by_overlap(self, benchmark, overlap: float) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=10_000, overlap=overlap)
        result = benchmark(pl1.difference, pl2)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Top-K
# ---------------------------------------------------------------------------


class TestTopK:
    @pytest.mark.parametrize("k", [10, 100, 1_000])
    def test_top_k(self, benchmark, k: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        pl = gen.posting_list(size=100_000, score_range=(0.0, 1.0))
        result = benchmark(pl.top_k, k)
        assert len(result) == k


# ---------------------------------------------------------------------------
# N-way merge
# ---------------------------------------------------------------------------


class TestMultiMerge:
    @pytest.mark.parametrize("n", [2, 4, 8, 16])
    def test_nway_union(self, benchmark, n: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        lists = gen.posting_lists_multi(n=n, size=10_000, overlap=0.3)

        def nway_union() -> object:
            return functools.reduce(lambda a, b: a | b, lists)

        result = benchmark(nway_union)
        assert len(result) > 0

    @pytest.mark.parametrize("n", [2, 4, 8, 16])
    def test_nway_intersect(self, benchmark, n: int) -> None:
        gen = BenchmarkDataGenerator(seed=42)
        lists = gen.posting_lists_multi(n=n, size=10_000, overlap=0.5)

        def nway_intersect() -> object:
            return functools.reduce(lambda a, b: a & b, lists)

        result = benchmark(nway_intersect)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Payload merge overhead
# ---------------------------------------------------------------------------


class TestPayloadMerge:
    def test_union_with_scores(self, benchmark) -> None:
        """Measure overhead of score merging during union."""
        gen = BenchmarkDataGenerator(seed=42)
        pl1, pl2 = gen.posting_lists(size=10_000, overlap=0.5)
        benchmark(pl1.union, pl2)

    def test_get_entry_binary_search(self, benchmark) -> None:
        """Measure binary search lookup performance."""
        gen = BenchmarkDataGenerator(seed=42)
        pl = gen.posting_list(size=100_000)
        target_id = pl.entries[50_000].doc_id
        result = benchmark(pl.get_entry, target_id)
        assert result is not None
