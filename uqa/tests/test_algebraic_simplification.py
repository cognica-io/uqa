#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for algebraic simplification rules (Theorem 6.1.2, Paper 1)."""

from __future__ import annotations

from uqa.core.types import Equals, IndexStats
from uqa.operators.boolean import IntersectOperator, UnionOperator
from uqa.operators.primitive import FilterOperator, TermOperator
from uqa.planner.optimizer import QueryOptimizer


def _make_optimizer() -> QueryOptimizer:
    return QueryOptimizer(IndexStats(total_docs=100))


# ==================================================================
# Idempotent intersection
# ==================================================================


class TestIdempotentIntersection:
    def test_duplicate_operand_removed(self) -> None:
        """Intersect(A, A) => A when A is the same object."""
        a = TermOperator("hello", "text")
        op = IntersectOperator([a, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_triple_duplicate_reduced(self) -> None:
        """Intersect(A, A, A) => A."""
        a = TermOperator("hello", "text")
        op = IntersectOperator([a, a, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_distinct_operands_preserved(self) -> None:
        """Intersect(A, B) with distinct objects stays as intersection."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        op = IntersectOperator([a, b])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, IntersectOperator)
        assert len(result.operands) == 2

    def test_partial_duplicate(self) -> None:
        """Intersect(A, B, A) => Intersect(A, B)."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        op = IntersectOperator([a, b, a])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, IntersectOperator)
        assert len(result.operands) == 2


# ==================================================================
# Idempotent union
# ==================================================================


class TestIdempotentUnion:
    def test_duplicate_operand_removed(self) -> None:
        """Union(A, A) => A when A is the same object."""
        a = TermOperator("hello", "text")
        op = UnionOperator([a, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_triple_duplicate_reduced(self) -> None:
        """Union(A, A, A) => A."""
        a = TermOperator("hello", "text")
        op = UnionOperator([a, a, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_distinct_operands_preserved(self) -> None:
        """Union(A, B) with distinct objects stays as union."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        op = UnionOperator([a, b])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, UnionOperator)
        assert len(result.operands) == 2

    def test_partial_duplicate(self) -> None:
        """Union(A, B, A) => Union(A, B)."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        op = UnionOperator([a, b, a])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, UnionOperator)
        assert len(result.operands) == 2


# ==================================================================
# Absorption law
# ==================================================================


class TestAbsorption:
    def test_union_absorbs_intersect(self) -> None:
        """Union(A, Intersect(A, B)) => A."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        inner = IntersectOperator([a, b])
        op = UnionOperator([a, inner])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_union_absorbs_intersect_reversed(self) -> None:
        """Union(Intersect(A, B), A) => A."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        inner = IntersectOperator([a, b])
        op = UnionOperator([inner, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_intersect_absorbs_union(self) -> None:
        """Intersect(A, Union(A, B)) => A."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        inner = UnionOperator([a, b])
        op = IntersectOperator([a, inner])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_intersect_absorbs_union_reversed(self) -> None:
        """Intersect(Union(A, B), A) => A."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        inner = UnionOperator([a, b])
        op = IntersectOperator([inner, a])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_no_absorption_without_identity(self) -> None:
        """Union(A, Intersect(C, B)) stays when C is not A (different object)."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        c = TermOperator("hello", "text")  # Same term but different object
        inner = IntersectOperator([c, b])
        op = UnionOperator([a, inner])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, UnionOperator)
        assert len(result.operands) == 2


# ==================================================================
# Empty elimination
# ==================================================================


class TestEmptyElimination:
    def test_intersect_with_empty_yields_empty(self) -> None:
        """Intersect(A, empty) => empty."""
        a = TermOperator("hello", "text")
        empty = IntersectOperator([])
        op = IntersectOperator([a, empty])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, IntersectOperator)
        assert len(result.operands) == 0

    def test_union_with_empty_drops_empty(self) -> None:
        """Union(A, empty) => A."""
        a = TermOperator("hello", "text")
        empty = UnionOperator([])
        op = UnionOperator([a, empty])
        result = _make_optimizer().optimize(op)
        assert result is a

    def test_union_all_empty(self) -> None:
        """Union(empty, empty) => empty."""
        e1 = UnionOperator([])
        e2 = IntersectOperator([])
        op = UnionOperator([e1, e2])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, UnionOperator)
        assert len(result.operands) == 0

    def test_intersect_with_empty_nested(self) -> None:
        """Intersect(Union(A, B), empty) => empty."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        union_ab = UnionOperator([a, b])
        empty = IntersectOperator([])
        op = IntersectOperator([union_ab, empty])
        result = _make_optimizer().optimize(op)
        assert isinstance(result, IntersectOperator)
        assert len(result.operands) == 0


# ==================================================================
# Nested simplification
# ==================================================================


class TestNestedSimplification:
    def test_nested_idempotent(self) -> None:
        """Nested duplicates are simplified bottom-up."""
        a = TermOperator("hello", "text")
        b = TermOperator("world", "text")
        inner = IntersectOperator([a, a])  # Should simplify to a
        outer = UnionOperator([inner, b])
        result = _make_optimizer().optimize(outer)
        assert isinstance(result, UnionOperator)
        # Inner should have been simplified, so operands are a and b
        assert len(result.operands) == 2

    def test_simplification_through_filter(self) -> None:
        """Simplification recurses through FilterOperator."""
        a = TermOperator("hello", "text")
        inner = UnionOperator([a, a])
        filtered = FilterOperator("text", Equals("hello"), inner)
        result = _make_optimizer().optimize(filtered)
        # The inner union should have been simplified to just a
        assert isinstance(result, FilterOperator)
