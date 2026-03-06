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
    score=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)

posting_entry_strategy = st.builds(PostingEntry, doc_id=doc_id_strategy, payload=payload_strategy)

posting_list_strategy = st.lists(
    posting_entry_strategy, min_size=0, max_size=15
).map(PostingList)

universal_doc_ids = list(range(51))
universal_posting_list = PostingList([
    PostingEntry(i, Payload(score=0.0)) for i in universal_doc_ids
])


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
def test_intersect_associativity(a: PostingList, b: PostingList, c: PostingList) -> None:
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
    gpl_a = GeneralizedPostingList([
        GeneralizedPostingEntry((1, 2), Payload(score=1.0)),
        GeneralizedPostingEntry((3, 4), Payload(score=0.5)),
    ])
    gpl_b = GeneralizedPostingList([
        GeneralizedPostingEntry((1, 2), Payload(score=0.8)),
        GeneralizedPostingEntry((5, 6), Payload(score=0.3)),
    ])
    result = gpl_a.union(gpl_b)
    assert len(result) == 3
    ids_set = {e.doc_ids for e in result}
    assert ids_set == {(1, 2), (3, 4), (5, 6)}


def test_generalized_posting_list_sorted() -> None:
    """GeneralizedPostingList entries are sorted by doc_ids."""
    gpl = GeneralizedPostingList([
        GeneralizedPostingEntry((5, 6), Payload(score=0.3)),
        GeneralizedPostingEntry((1, 2), Payload(score=1.0)),
        GeneralizedPostingEntry((3, 4), Payload(score=0.5)),
    ])
    entries = gpl.entries
    for i in range(len(entries) - 1):
        assert entries[i].doc_ids <= entries[i + 1].doc_ids
