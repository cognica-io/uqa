#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.joins.semi import AntiJoinOperator, SemiJoinOperator
from uqa.operators.base import ExecutionContext, Operator


class _ConstantOperator(Operator):
    """Returns a fixed PostingList regardless of context."""

    def __init__(self, pl: PostingList) -> None:
        self._pl = pl

    def execute(self, context: ExecutionContext) -> PostingList:
        return self._pl


def _make_pl(*doc_ids: int) -> PostingList:
    """Create a PostingList with default payloads for the given doc_ids."""
    entries = [PostingEntry(d, Payload(score=float(d))) for d in doc_ids]
    return PostingList(entries)


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext()


class TestSemiJoin:
    def test_basic_semi_join(self, context: ExecutionContext) -> None:
        """Default doc_id equality: left=[1,2,3], right=[2,3,4] -> [2,3]."""
        left = _ConstantOperator(_make_pl(1, 2, 3))
        right = _ConstantOperator(_make_pl(2, 3, 4))

        result = SemiJoinOperator(left, right).execute(context)

        assert [e.doc_id for e in result] == [2, 3]

    def test_basic_anti_join(self, context: ExecutionContext) -> None:
        """Default doc_id equality: left=[1,2,3], right=[2,3,4] -> [1]."""
        left = _ConstantOperator(_make_pl(1, 2, 3))
        right = _ConstantOperator(_make_pl(2, 3, 4))

        result = AntiJoinOperator(left, right).execute(context)

        assert [e.doc_id for e in result] == [1]

    def test_semi_join_with_custom_condition(self, context: ExecutionContext) -> None:
        """Custom condition based on payload field values."""
        left_pl = PostingList(
            [
                PostingEntry(1, Payload(fields={"dept": "eng"})),
                PostingEntry(2, Payload(fields={"dept": "sales"})),
                PostingEntry(3, Payload(fields={"dept": "hr"})),
            ]
        )
        right_pl = PostingList(
            [
                PostingEntry(10, Payload(fields={"department": "eng"})),
                PostingEntry(11, Payload(fields={"department": "sales"})),
            ]
        )

        def dept_match(l: PostingEntry, r: PostingEntry) -> bool:
            return l.payload.fields.get("dept") == r.payload.fields.get("department")

        result = SemiJoinOperator(
            _ConstantOperator(left_pl),
            _ConstantOperator(right_pl),
            condition=dept_match,
        ).execute(context)

        assert [e.doc_id for e in result] == [1, 2]

    def test_anti_join_with_custom_condition(self, context: ExecutionContext) -> None:
        """Custom condition: keep left entries with NO match in right."""
        left_pl = PostingList(
            [
                PostingEntry(1, Payload(fields={"dept": "eng"})),
                PostingEntry(2, Payload(fields={"dept": "sales"})),
                PostingEntry(3, Payload(fields={"dept": "hr"})),
            ]
        )
        right_pl = PostingList(
            [
                PostingEntry(10, Payload(fields={"department": "eng"})),
                PostingEntry(11, Payload(fields={"department": "sales"})),
            ]
        )

        def dept_match(l: PostingEntry, r: PostingEntry) -> bool:
            return l.payload.fields.get("dept") == r.payload.fields.get("department")

        result = AntiJoinOperator(
            _ConstantOperator(left_pl),
            _ConstantOperator(right_pl),
            condition=dept_match,
        ).execute(context)

        assert [e.doc_id for e in result] == [3]

    def test_empty_left(self, context: ExecutionContext) -> None:
        """Empty left produces empty result for both semi and anti."""
        left = _ConstantOperator(PostingList())
        right = _ConstantOperator(_make_pl(1, 2))

        semi_result = SemiJoinOperator(left, right).execute(context)
        anti_result = AntiJoinOperator(left, right).execute(context)

        assert len(semi_result) == 0
        assert len(anti_result) == 0

    def test_empty_right(self, context: ExecutionContext) -> None:
        """Empty right: semi returns nothing, anti returns everything."""
        left = _ConstantOperator(_make_pl(1, 2, 3))
        right = _ConstantOperator(PostingList())

        semi_result = SemiJoinOperator(left, right).execute(context)
        anti_result = AntiJoinOperator(left, right).execute(context)

        assert len(semi_result) == 0
        assert [e.doc_id for e in anti_result] == [1, 2, 3]

    def test_no_overlap(self, context: ExecutionContext) -> None:
        """Disjoint doc_ids: semi empty, anti returns all left."""
        left = _ConstantOperator(_make_pl(1, 2, 3))
        right = _ConstantOperator(_make_pl(4, 5, 6))

        semi_result = SemiJoinOperator(left, right).execute(context)
        anti_result = AntiJoinOperator(left, right).execute(context)

        assert len(semi_result) == 0
        assert [e.doc_id for e in anti_result] == [1, 2, 3]

    def test_not_commutative(self, context: ExecutionContext) -> None:
        """Semi-join is NOT commutative: semi(A,B) != semi(B,A) in general.

        Use asymmetric sets where the overlap is a strict subset of one
        side but not the other, producing different result sizes.
        """
        # A = {1, 2, 3}, B = {3, 4, 5}
        # semi(A, B) keeps A entries whose doc_id is in B -> {3}
        # semi(B, A) keeps B entries whose doc_id is in A -> {3}
        # Same doc_id set here, but try with different cardinalities:

        # C = {1, 2, 3}, D = {1, 2, 3, 4, 5}
        # semi(C, D) = {1, 2, 3}  (all of C found in D)
        # semi(D, C) = {1, 2, 3}  (only 3 of D's 5 entries found in C)
        # Result sizes equal, but the returned entries come from different
        # source PostingLists -- the payloads differ because score=doc_id.
        c = _ConstantOperator(_make_pl(1, 2, 3))
        d = _ConstantOperator(_make_pl(1, 2, 3, 4, 5))

        result_cd = SemiJoinOperator(c, d).execute(context)
        result_dc = SemiJoinOperator(d, c).execute(context)

        assert [e.doc_id for e in result_cd] == [1, 2, 3]
        assert [e.doc_id for e in result_dc] == [1, 2, 3]

        # Verify payloads come from the LEFT operand in each case.
        # In result_cd, entries come from C (scores 1.0, 2.0, 3.0).
        # In result_dc, entries come from D (same scores here, but the
        # identity of the source operator differs).

        # Clearest non-commutativity -- different result sizes:
        # E = {1, 2}, F = {2, 3, 4}
        # semi(E, F) = {2}   (only doc_id 2 from E is in F)
        # semi(F, E) = {2}   (only doc_id 2 from F is in E)
        # Still same size. Use disjoint-heavy sets:

        # G = {10, 20, 30}, H = {10}
        # semi(G, H) = {10}     (size 1)
        # semi(H, G) = {10}     (size 1)
        # To get truly different sizes, we need A subset B:
        # P = {1}, Q = {1, 2}
        # semi(P, Q) = {1}      (size 1)
        # semi(Q, P) = {1}      (size 1)
        # Semi-join with doc_id equality always yields the intersection
        # projected onto the left side, so |semi(A,B)| = |A intersect B|
        # = |semi(B,A)|. The non-commutativity shows in the *identity*
        # of entries (which source they come from), not the doc_id set.

        # Demonstrate identity difference via payloads:
        left_pl = PostingList(
            [
                PostingEntry(1, Payload(score=0.1, fields={"src": "left"})),
            ]
        )
        right_pl = PostingList(
            [
                PostingEntry(1, Payload(score=0.9, fields={"src": "right"})),
            ]
        )
        p = _ConstantOperator(left_pl)
        q = _ConstantOperator(right_pl)

        result_pq = SemiJoinOperator(p, q).execute(context)
        result_qp = SemiJoinOperator(q, p).execute(context)

        # Same doc_id set {1}, but payloads differ.
        assert result_pq.entries[0].payload.fields["src"] == "left"
        assert result_qp.entries[0].payload.fields["src"] == "right"
        assert result_pq.entries[0].payload.score != result_qp.entries[0].payload.score

    def test_payload_preservation(self, context: ExecutionContext) -> None:
        """Left entry payloads must be preserved exactly."""
        left_pl = PostingList(
            [
                PostingEntry(
                    1,
                    Payload(
                        positions=(10, 20),
                        score=0.95,
                        fields={"name": "Alice", "role": "admin"},
                    ),
                ),
                PostingEntry(
                    2,
                    Payload(
                        positions=(30,),
                        score=0.50,
                        fields={"name": "Bob", "role": "user"},
                    ),
                ),
                PostingEntry(
                    3,
                    Payload(
                        positions=(),
                        score=0.10,
                        fields={"name": "Charlie", "role": "guest"},
                    ),
                ),
            ]
        )
        right_pl = PostingList(
            [
                PostingEntry(2, Payload(score=999.0, fields={"unrelated": True})),
                PostingEntry(3, Payload(score=888.0, fields={"other": "data"})),
            ]
        )

        result = SemiJoinOperator(
            _ConstantOperator(left_pl),
            _ConstantOperator(right_pl),
        ).execute(context)

        assert len(result) == 2

        entry_2 = result.entries[0]
        assert entry_2.doc_id == 2
        assert entry_2.payload.score == 0.50
        assert entry_2.payload.positions == (30,)
        assert entry_2.payload.fields == {"name": "Bob", "role": "user"}

        entry_3 = result.entries[1]
        assert entry_3.doc_id == 3
        assert entry_3.payload.score == 0.10
        assert entry_3.payload.positions == ()
        assert entry_3.payload.fields == {"name": "Charlie", "role": "guest"}

    def test_cost_estimate(self) -> None:
        """cost_estimate returns sum of both children."""
        from uqa.core.types import IndexStats

        left = _ConstantOperator(_make_pl(1, 2))
        right = _ConstantOperator(_make_pl(3, 4))

        stats = IndexStats(total_docs=100)
        op = SemiJoinOperator(left, right)
        # Both children use default cost_estimate = total_docs = 100
        assert op.cost_estimate(stats) == 200.0

        anti_op = AntiJoinOperator(left, right)
        assert anti_op.cost_estimate(stats) == 200.0

    def test_semi_and_anti_are_complementary(self, context: ExecutionContext) -> None:
        """semi(L,R) union anti(L,R) should equal L (as sets of doc_ids)."""
        left = _ConstantOperator(_make_pl(1, 2, 3, 4, 5))
        right = _ConstantOperator(_make_pl(2, 4))

        semi_result = SemiJoinOperator(left, right).execute(context)
        anti_result = AntiJoinOperator(left, right).execute(context)

        semi_ids = {e.doc_id for e in semi_result}
        anti_ids = {e.doc_id for e in anti_result}

        assert semi_ids == {2, 4}
        assert anti_ids == {1, 3, 5}
        assert semi_ids | anti_ids == {1, 2, 3, 4, 5}
        assert semi_ids & anti_ids == set()

    def test_full_overlap(self, context: ExecutionContext) -> None:
        """When right contains all left doc_ids, semi returns all, anti none."""
        left = _ConstantOperator(_make_pl(1, 2, 3))
        right = _ConstantOperator(_make_pl(1, 2, 3, 4, 5))

        semi_result = SemiJoinOperator(left, right).execute(context)
        anti_result = AntiJoinOperator(left, right).execute(context)

        assert [e.doc_id for e in semi_result] == [1, 2, 3]
        assert len(anti_result) == 0
