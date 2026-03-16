#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Property-based tests for PostingList Boolean algebra axioms.

Uses Hypothesis to verify the 5 Boolean algebra axioms from
Theorem 2.1.2 (Paper 1):
  A1: Commutativity
  A2: Associativity
  A3: Distributivity
  A4: Identity
  A5: Complement
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uqa.core.posting_list import GeneralizedPostingList, PostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry

# -- Hypothesis strategies --

doc_id_strategy = st.integers(min_value=0, max_value=50)

payload_strategy = st.builds(
    Payload,
    positions=st.tuples(
        *[st.integers(min_value=0, max_value=100) for _ in range(3)]
    ).map(lambda t: tuple(sorted(set(t)))),
    score=st.floats(
        min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False
    ),
)

posting_entry_strategy = st.builds(
    PostingEntry, doc_id=doc_id_strategy, payload=payload_strategy
)

posting_list_strategy = st.lists(posting_entry_strategy, min_size=0, max_size=15).map(
    PostingList
)

universal_doc_ids = list(range(51))
universal_posting_list = PostingList(
    [PostingEntry(i, Payload(score=0.0)) for i in universal_doc_ids]
)


def posting_list_doc_ids_equal(a: PostingList, b: PostingList) -> bool:
    """Compare posting lists by doc_id sets (ignoring payloads)."""
    return a.doc_ids == b.doc_ids


# -- Axiom A1: Commutativity --


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_union_commutativity(a: PostingList, b: PostingList) -> None:
    """A union B == B union A (by doc_ids)."""
    assert posting_list_doc_ids_equal(a.union(b), b.union(a))


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_intersect_commutativity(a: PostingList, b: PostingList) -> None:
    """A intersect B == B intersect A (by doc_ids)."""
    assert posting_list_doc_ids_equal(a.intersect(b), b.intersect(a))


# -- Axiom A2: Associativity --


@given(a=posting_list_strategy, b=posting_list_strategy, c=posting_list_strategy)
@settings(max_examples=100)
def test_union_associativity(a: PostingList, b: PostingList, c: PostingList) -> None:
    """A union (B union C) == (A union B) union C."""
    lhs = a.union(b.union(c))
    rhs = a.union(b).union(c)
    assert posting_list_doc_ids_equal(lhs, rhs)


@given(a=posting_list_strategy, b=posting_list_strategy, c=posting_list_strategy)
@settings(max_examples=100)
def test_intersect_associativity(
    a: PostingList, b: PostingList, c: PostingList
) -> None:
    """A intersect (B intersect C) == (A intersect B) intersect C."""
    lhs = a.intersect(b.intersect(c))
    rhs = a.intersect(b).intersect(c)
    assert posting_list_doc_ids_equal(lhs, rhs)


# -- Axiom A3: Distributivity --


@given(a=posting_list_strategy, b=posting_list_strategy, c=posting_list_strategy)
@settings(max_examples=100)
def test_intersect_distributes_over_union(
    a: PostingList, b: PostingList, c: PostingList
) -> None:
    """A intersect (B union C) == (A intersect B) union (A intersect C)."""
    lhs = a.intersect(b.union(c))
    rhs = a.intersect(b).union(a.intersect(c))
    assert posting_list_doc_ids_equal(lhs, rhs)


@given(a=posting_list_strategy, b=posting_list_strategy, c=posting_list_strategy)
@settings(max_examples=100)
def test_union_distributes_over_intersect(
    a: PostingList, b: PostingList, c: PostingList
) -> None:
    """A union (B intersect C) == (A union B) intersect (A union C)."""
    lhs = a.union(b.intersect(c))
    rhs = a.union(b).intersect(a.union(c))
    assert posting_list_doc_ids_equal(lhs, rhs)


# -- Axiom A4: Identity --


@given(a=posting_list_strategy)
@settings(max_examples=100)
def test_union_identity(a: PostingList) -> None:
    """A union empty == A."""
    empty = PostingList()
    assert posting_list_doc_ids_equal(a.union(empty), a)
    assert posting_list_doc_ids_equal(empty.union(a), a)


@given(a=posting_list_strategy)
@settings(max_examples=100)
def test_intersect_identity(a: PostingList) -> None:
    """A intersect U == A (where U is the universal set containing all doc_ids in a)."""
    # Build a universal set that contains all doc_ids from a
    all_ids = a.doc_ids | set(universal_doc_ids)
    u = PostingList([PostingEntry(i, Payload(score=0.0)) for i in all_ids])
    result = a.intersect(u)
    assert posting_list_doc_ids_equal(result, a)


# -- Axiom A5: Complement --


@given(a=posting_list_strategy)
@settings(max_examples=100)
def test_complement_union_is_universal(a: PostingList) -> None:
    """A union complement(A) == U."""
    complement_a = a.complement(universal_posting_list)
    result = a.union(complement_a)
    # Result should contain all doc_ids in the universal set
    assert result.doc_ids == universal_posting_list.doc_ids


@given(a=posting_list_strategy)
@settings(max_examples=100)
def test_complement_intersect_is_empty(a: PostingList) -> None:
    """A intersect complement(A) == empty."""
    complement_a = a.complement(universal_posting_list)
    result = a.intersect(complement_a)
    assert len(result) == 0


# -- Sorted invariant --


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_sorted_invariant_after_union(a: PostingList, b: PostingList) -> None:
    """Entries are sorted by doc_id after union."""
    result = a.union(b)
    entries = result.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_id < entries[i + 1].doc_id


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_sorted_invariant_after_intersect(a: PostingList, b: PostingList) -> None:
    """Entries are sorted by doc_id after intersect."""
    result = a.intersect(b)
    entries = result.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_id < entries[i + 1].doc_id


@given(a=posting_list_strategy)
@settings(max_examples=100)
def test_sorted_invariant_after_complement(a: PostingList) -> None:
    """Entries are sorted by doc_id after complement."""
    result = a.complement(universal_posting_list)
    entries = result.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_id < entries[i + 1].doc_id


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_sorted_invariant_after_difference(a: PostingList, b: PostingList) -> None:
    """Entries are sorted by doc_id after difference."""
    result = a.difference(b)
    entries = result.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_id < entries[i + 1].doc_id


@given(a=posting_list_strategy, b=posting_list_strategy)
@settings(max_examples=100)
def test_difference_correctness(a: PostingList, b: PostingList) -> None:
    """difference() returns entries in A but not in B."""
    result = a.difference(b)
    result_ids = {e.doc_id for e in result}
    expected_ids = a.doc_ids - b.doc_ids
    assert result_ids == expected_ids


# -- Merge payloads --


def test_merge_payloads_positions() -> None:
    """Merged positions are the sorted union of both positions."""
    a = PostingList([PostingEntry(1, Payload(positions=(0, 2), score=1.0))])
    b = PostingList([PostingEntry(1, Payload(positions=(1, 3), score=0.5))])
    result = a.union(b)
    entry = result.get_entry(1)
    assert entry is not None
    assert entry.payload.positions == (0, 1, 2, 3)


def test_merge_payloads_scores() -> None:
    """Merged score is the sum of both scores."""
    a = PostingList([PostingEntry(1, Payload(score=1.0))])
    b = PostingList([PostingEntry(1, Payload(score=0.5))])
    result = a.union(b)
    entry = result.get_entry(1)
    assert entry is not None
    assert entry.payload.score == 1.5


def test_merge_payloads_fields() -> None:
    """Merged fields combine both field dicts."""
    a = PostingList([PostingEntry(1, Payload(fields={"a": 1}))])
    b = PostingList([PostingEntry(1, Payload(fields={"b": 2}))])
    result = a.union(b)
    entry = result.get_entry(1)
    assert entry is not None
    assert entry.payload.fields == {"a": 1, "b": 2}


# -- GeneralizedPostingList --


def test_generalized_posting_list_union() -> None:
    """GeneralizedPostingList union deduplicates by doc_ids tuple."""
    gpl_a = GeneralizedPostingList(
        [
            GeneralizedPostingEntry((1, 2), Payload(score=1.0)),
            GeneralizedPostingEntry((3, 4), Payload(score=0.5)),
        ]
    )
    gpl_b = GeneralizedPostingList(
        [
            GeneralizedPostingEntry((1, 2), Payload(score=0.8)),
            GeneralizedPostingEntry((5, 6), Payload(score=0.3)),
        ]
    )
    result = gpl_a.union(gpl_b)
    assert len(result) == 3
    ids_set = {e.doc_ids for e in result}
    assert ids_set == {(1, 2), (3, 4), (5, 6)}


def test_generalized_posting_list_sorted() -> None:
    """GeneralizedPostingList entries are sorted by doc_ids."""
    gpl = GeneralizedPostingList(
        [
            GeneralizedPostingEntry((5, 6), Payload(score=0.3)),
            GeneralizedPostingEntry((1, 2), Payload(score=1.0)),
            GeneralizedPostingEntry((3, 4), Payload(score=0.5)),
        ]
    )
    entries = gpl.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_ids <= entries[i + 1].doc_ids


# -- GeneralizedPostingList Boolean Algebra --


class TestGeneralizedPostingListAlgebra:
    """Tests for GeneralizedPostingList intersect, difference, complement,
    doc_ids_set, operator overloads, and __eq__."""

    # Shared fixtures

    @staticmethod
    def _make_gpl(
        tuples: list[tuple[int, ...]],
    ) -> GeneralizedPostingList:
        entries = [
            GeneralizedPostingEntry(t, Payload(score=float(sum(t)))) for t in tuples
        ]
        return GeneralizedPostingList(entries)

    # -- intersect --

    def test_intersect_shared_tuples_only(self) -> None:
        """intersect keeps only doc_ids tuples present in both operands."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6)])
        b = self._make_gpl([(3, 4), (5, 6), (7, 8)])
        result = a.intersect(b)
        assert {e.doc_ids for e in result} == {(3, 4), (5, 6)}

    def test_intersect_preserves_left_payload(self) -> None:
        """intersect keeps the entry from self (left operand)."""
        a = GeneralizedPostingList(
            [GeneralizedPostingEntry((1, 2), Payload(score=9.0))]
        )
        b = GeneralizedPostingList(
            [GeneralizedPostingEntry((1, 2), Payload(score=1.0))]
        )
        result = a.intersect(b)
        assert len(result) == 1
        assert next(iter(result)).payload.score == 9.0

    def test_intersect_sorted_invariant(self) -> None:
        """intersect result is sorted by doc_ids."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6), (7, 8)])
        b = self._make_gpl([(5, 6), (1, 2)])
        result = a.intersect(b)
        entries = result.entries
        for i in range(len(entries) - 1):
            assert entries[i].doc_ids <= entries[i + 1].doc_ids

    # -- difference --

    def test_difference_self_minus_other(self) -> None:
        """difference removes tuples present in other."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6)])
        b = self._make_gpl([(3, 4)])
        result = a.difference(b)
        assert {e.doc_ids for e in result} == {(1, 2), (5, 6)}

    def test_difference_preserves_payload(self) -> None:
        """difference keeps original payloads from self."""
        a = GeneralizedPostingList(
            [
                GeneralizedPostingEntry((1, 2), Payload(score=5.0)),
                GeneralizedPostingEntry((3, 4), Payload(score=7.0)),
            ]
        )
        b = self._make_gpl([(3, 4)])
        result = a.difference(b)
        assert len(result) == 1
        assert next(iter(result)).payload.score == 5.0

    def test_difference_sorted_invariant(self) -> None:
        """difference result is sorted by doc_ids."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6), (7, 8)])
        b = self._make_gpl([(3, 4)])
        result = a.difference(b)
        entries = result.entries
        for i in range(len(entries) - 1):
            assert entries[i].doc_ids <= entries[i + 1].doc_ids

    # -- complement --

    def test_complement_universal_minus_self(self) -> None:
        """complement returns universal - self."""
        universal = self._make_gpl([(1, 2), (3, 4), (5, 6), (7, 8)])
        a = self._make_gpl([(3, 4), (7, 8)])
        result = a.complement(universal)
        assert {e.doc_ids for e in result} == {(1, 2), (5, 6)}

    def test_complement_of_empty_is_universal(self) -> None:
        """complement of empty set is the universal set."""
        universal = self._make_gpl([(1, 2), (3, 4)])
        empty = GeneralizedPostingList()
        result = empty.complement(universal)
        assert result == universal

    def test_complement_of_universal_is_empty(self) -> None:
        """complement of universal set is empty."""
        universal = self._make_gpl([(1, 2), (3, 4)])
        result = universal.complement(universal)
        assert len(result) == 0

    # -- doc_ids_set --

    def test_doc_ids_set_property(self) -> None:
        """doc_ids_set returns the set of all doc_ids tuples."""
        gpl = self._make_gpl([(1, 2), (3, 4), (5, 6)])
        assert gpl.doc_ids_set == {(1, 2), (3, 4), (5, 6)}

    def test_doc_ids_set_empty(self) -> None:
        """doc_ids_set on empty list returns empty set."""
        gpl = GeneralizedPostingList()
        assert gpl.doc_ids_set == set()

    # -- operator overloads --

    def test_and_operator(self) -> None:
        """__and__ delegates to intersect."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6)])
        b = self._make_gpl([(3, 4), (7, 8)])
        result = a & b
        assert {e.doc_ids for e in result} == {(3, 4)}

    def test_or_operator(self) -> None:
        """__or__ delegates to union."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(3, 4), (5, 6)])
        result = a | b
        assert {e.doc_ids for e in result} == {(1, 2), (3, 4), (5, 6)}

    def test_sub_operator(self) -> None:
        """__sub__ delegates to difference."""
        a = self._make_gpl([(1, 2), (3, 4), (5, 6)])
        b = self._make_gpl([(3, 4)])
        result = a - b
        assert {e.doc_ids for e in result} == {(1, 2), (5, 6)}

    # -- __eq__ --

    def test_eq_same_entries(self) -> None:
        """Two GPLs with same doc_ids tuples (same order) are equal."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(1, 2), (3, 4)])
        assert a == b

    def test_eq_different_entries(self) -> None:
        """Two GPLs with different doc_ids tuples are not equal."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(1, 2), (5, 6)])
        assert a != b

    def test_eq_different_lengths(self) -> None:
        """Two GPLs with different lengths are not equal."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(1, 2)])
        assert a != b

    def test_eq_not_implemented_for_other_types(self) -> None:
        """__eq__ returns NotImplemented for non-GPL objects."""
        a = self._make_gpl([(1, 2)])
        assert a.__eq__("not a gpl") is NotImplemented

    def test_eq_ignores_payload_differences(self) -> None:
        """__eq__ compares only doc_ids, not payloads."""
        a = GeneralizedPostingList(
            [GeneralizedPostingEntry((1, 2), Payload(score=1.0))]
        )
        b = GeneralizedPostingList(
            [GeneralizedPostingEntry((1, 2), Payload(score=99.0))]
        )
        assert a == b

    # -- empty operands --

    def test_intersect_with_empty(self) -> None:
        """intersect with empty returns empty."""
        a = self._make_gpl([(1, 2), (3, 4)])
        empty = GeneralizedPostingList()
        assert len(a.intersect(empty)) == 0
        assert len(empty.intersect(a)) == 0

    def test_difference_with_empty(self) -> None:
        """difference from empty returns self; difference with empty returns self."""
        a = self._make_gpl([(1, 2), (3, 4)])
        empty = GeneralizedPostingList()
        assert a.difference(empty) == a
        assert len(empty.difference(a)) == 0

    def test_union_with_empty(self) -> None:
        """union with empty returns self."""
        a = self._make_gpl([(1, 2), (3, 4)])
        empty = GeneralizedPostingList()
        assert a.union(empty) == a
        assert empty.union(a) == a

    # -- no-overlap cases --

    def test_intersect_no_overlap(self) -> None:
        """intersect of disjoint sets is empty."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(5, 6), (7, 8)])
        result = a.intersect(b)
        assert len(result) == 0

    def test_difference_no_overlap(self) -> None:
        """difference of disjoint sets returns self unchanged."""
        a = self._make_gpl([(1, 2), (3, 4)])
        b = self._make_gpl([(5, 6), (7, 8)])
        result = a.difference(b)
        assert result == a


# -- De Morgan property tests (Theorem 2.1.2, Paper 1) --


class TestDeMorganProperties:
    """De Morgan's laws for PostingList Boolean algebra:

    NOT (A AND B) == (NOT A) OR (NOT B)
    NOT (A OR B) == (NOT A) AND (NOT B)
    """

    @staticmethod
    def _ids(pl: PostingList) -> set[int]:
        return {e.doc_id for e in pl}

    @given(posting_list_strategy, posting_list_strategy)
    @settings(max_examples=50, deadline=None)
    def test_de_morgan_intersect(self, a: PostingList, b: PostingList) -> None:
        """NOT (A AND B) == (NOT A) OR (NOT B)."""
        u = a.union(b).union(
            PostingList([PostingEntry(i, Payload()) for i in range(51)])
        )
        lhs = a.intersect(b).complement(u)
        rhs = a.complement(u).union(b.complement(u))
        assert self._ids(lhs) == self._ids(rhs)

    @given(posting_list_strategy, posting_list_strategy)
    @settings(max_examples=50, deadline=None)
    def test_de_morgan_union(self, a: PostingList, b: PostingList) -> None:
        """NOT (A OR B) == (NOT A) AND (NOT B)."""
        u = a.union(b).union(
            PostingList([PostingEntry(i, Payload()) for i in range(51)])
        )
        lhs = a.union(b).complement(u)
        rhs = a.complement(u).intersect(b.complement(u))
        assert self._ids(lhs) == self._ids(rhs)

    @given(posting_list_strategy, posting_list_strategy, posting_list_strategy)
    @settings(max_examples=30, deadline=None)
    def test_distributivity(
        self, a: PostingList, b: PostingList, c: PostingList
    ) -> None:
        """A AND (B OR C) == (A AND B) OR (A AND C)."""
        lhs = a.intersect(b.union(c))
        rhs = a.intersect(b).union(a.intersect(c))
        assert self._ids(lhs) == self._ids(rhs)


# -- GeneralizedPostingList algebra property tests --


gpl_entry_strategy = st.builds(
    GeneralizedPostingEntry,
    doc_ids=st.tuples(
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=10),
    ),
    payload=st.builds(Payload, score=st.just(0.0)),
)

gpl_strategy = st.lists(gpl_entry_strategy, min_size=0, max_size=8).map(
    GeneralizedPostingList
)


class TestGPLAlgebraProperties:
    """Property-based tests for GeneralizedPostingList algebra."""

    @staticmethod
    def _tuples(gpl: GeneralizedPostingList) -> set[tuple[int, ...]]:
        return {e.doc_ids for e in gpl}

    @given(gpl_strategy, gpl_strategy)
    @settings(max_examples=30, deadline=None)
    def test_gpl_union_commutative(
        self, a: GeneralizedPostingList, b: GeneralizedPostingList
    ) -> None:
        assert self._tuples(a.union(b)) == self._tuples(b.union(a))

    @given(gpl_strategy, gpl_strategy)
    @settings(max_examples=30, deadline=None)
    def test_gpl_intersect_commutative(
        self, a: GeneralizedPostingList, b: GeneralizedPostingList
    ) -> None:
        assert self._tuples(a.intersect(b)) == self._tuples(b.intersect(a))

    @given(gpl_strategy, gpl_strategy)
    @settings(max_examples=30, deadline=None)
    def test_gpl_de_morgan_intersect(
        self, a: GeneralizedPostingList, b: GeneralizedPostingList
    ) -> None:
        """NOT (A AND B) == (NOT A) OR (NOT B) for GPL."""
        u = a.union(b)
        lhs = self._tuples(a.intersect(b).complement(u))
        rhs = self._tuples(a.complement(u).union(b.complement(u)))
        assert lhs == rhs
