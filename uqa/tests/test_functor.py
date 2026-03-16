#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for category-theoretic functors between UQA paradigms."""

from __future__ import annotations

from uqa.core.functor import (
    GraphToRelationalFunctor,
    RelationalToGraphFunctor,
    TextToVectorFunctor,
)
from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_posting_list(
    entries: list[tuple[int, float]],
) -> PostingList:
    """Build a PostingList from (doc_id, score) pairs."""
    return PostingList(
        [PostingEntry(did, Payload(score=score)) for did, score in entries]
    )


def _make_text_posting_list(
    entries: list[tuple[int, tuple[int, ...], float]],
) -> PostingList:
    """Build a PostingList from (doc_id, positions, score) triples."""
    return PostingList(
        [
            PostingEntry(did, Payload(positions=positions, score=score))
            for did, positions, score in entries
        ]
    )


def _make_graph_posting_list(
    entries: list[tuple[int, float]],
) -> GraphPostingList:
    """Build a GraphPostingList from (doc_id, score) pairs."""
    pe_list = [PostingEntry(did, Payload(score=score)) for did, score in entries]
    graph_payloads: dict[int, GraphPayload] = {}
    all_vids = frozenset(did for did, _ in entries)
    for did, score in entries:
        graph_payloads[did] = GraphPayload(
            subgraph_vertices=all_vids,
            subgraph_edges=frozenset(),
            score=score,
        )
    return GraphPostingList(pe_list, graph_payloads)


# ---------------------------------------------------------------------------
# GraphToRelationalFunctor
# ---------------------------------------------------------------------------


def test_graph_to_relational_identity() -> None:
    """F(id(A)) == id(F(A)) for empty GraphPostingList."""
    functor = GraphToRelationalFunctor()
    empty_gpl = GraphPostingList()

    result = functor.map_object(functor.identity(empty_gpl))
    assert len(result) == 0
    assert isinstance(result, PostingList)


def test_graph_to_relational_map_object() -> None:
    """Convert GraphPostingList with entries to PostingList."""
    functor = GraphToRelationalFunctor()
    gpl = _make_graph_posting_list([(1, 0.9), (3, 0.7), (5, 0.5)])

    result = functor.map_object(gpl)

    assert isinstance(result, PostingList)
    assert not isinstance(result, GraphPostingList)
    assert len(result) == 3

    doc_ids = [e.doc_id for e in result]
    assert doc_ids == [1, 3, 5]

    # Graph payload scores should be carried over
    for entry in result:
        assert entry.payload.score > 0.0
        # Graph vertices should be encoded in fields
        assert "_graph_vertices" in entry.payload.fields


# ---------------------------------------------------------------------------
# RelationalToGraphFunctor
# ---------------------------------------------------------------------------


def test_relational_to_graph_map_object() -> None:
    """Convert PostingList to GraphPostingList, verify GraphPayloads."""
    functor = RelationalToGraphFunctor()
    pl = _make_posting_list([(2, 0.8), (4, 0.6), (6, 0.4)])

    result = functor.map_object(pl)

    assert isinstance(result, GraphPostingList)
    assert len(result) == 3

    doc_ids = [e.doc_id for e in result]
    assert doc_ids == [2, 4, 6]

    # Each entry should have a GraphPayload with all vertex IDs
    expected_vids = frozenset({2, 4, 6})
    for did in [2, 4, 6]:
        gp = result.get_graph_payload(did)
        assert gp is not None
        assert gp.subgraph_vertices == expected_vids
        assert gp.subgraph_edges == frozenset()


def test_relational_to_graph_identity() -> None:
    """Empty PostingList maps to empty GraphPostingList."""
    functor = RelationalToGraphFunctor()
    empty_pl = PostingList()

    result = functor.map_object(functor.identity(empty_pl))
    assert isinstance(result, GraphPostingList)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# TextToVectorFunctor
# ---------------------------------------------------------------------------


def test_text_to_vector_map_object() -> None:
    """Convert text PostingList (with positions) to normalized scores."""
    functor = TextToVectorFunctor(dimensions=64)
    pl = _make_text_posting_list(
        [
            (1, (0, 5, 10), 1.0),  # 3 positions, score 1.0 -> raw = 3.0
            (2, (3,), 1.0),  # 1 position, score 1.0 -> raw = 1.0
            (3, (1, 7), 0.5),  # 2 positions, score 0.5 -> raw = 1.0
        ]
    )

    result = functor.map_object(pl)

    assert isinstance(result, PostingList)
    assert len(result) == 3

    scores = {e.doc_id: e.payload.score for e in result}

    # doc_id=1 has highest raw score (3.0), should be normalized to 1.0
    assert scores[1] == 1.0

    # doc_id=2 and doc_id=3 both have raw=1.0, normalized to 1/3
    assert abs(scores[2] - 1.0 / 3.0) < 1e-9
    assert abs(scores[3] - 1.0 / 3.0) < 1e-9

    # Positions should be preserved
    for entry in result:
        original = pl.get_entry(entry.doc_id)
        assert original is not None
        assert entry.payload.positions == original.payload.positions


def test_text_to_vector_empty() -> None:
    """Empty input returns empty output."""
    functor = TextToVectorFunctor()
    empty_pl = PostingList()

    result = functor.map_object(empty_pl)
    assert isinstance(result, PostingList)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Functor laws
# ---------------------------------------------------------------------------


def test_identity_law_graph_relational() -> None:
    """F(id(A)) == id(F(A)) -- identity preservation for GraphToRelational."""
    functor = GraphToRelationalFunctor()
    gpl = _make_graph_posting_list([(10, 0.5), (20, 0.3)])

    # F(id(A)): apply identity in source category, then map
    lhs = functor.map_object(functor.identity(gpl))

    # id(F(A)): map first, then apply identity in target category
    rhs = functor.identity(functor.map_object(gpl))

    assert len(lhs) == len(rhs)
    lhs_ids = [e.doc_id for e in lhs]
    rhs_ids = [e.doc_id for e in rhs]
    assert lhs_ids == rhs_ids

    for l_entry, r_entry in zip(lhs, rhs):
        assert l_entry.doc_id == r_entry.doc_id
        assert abs(l_entry.payload.score - r_entry.payload.score) < 1e-9


def test_composition_law_graph_relational() -> None:
    """F(g . f) == F(g) . F(f) -- composition preservation.

    We model morphisms as PostingList operations (intersect, union).
    Apply two operations in sequence, verify the functor respects composition.
    """
    functor = GraphToRelationalFunctor()

    gpl_a = _make_graph_posting_list([(1, 0.9), (2, 0.8), (3, 0.7)])
    gpl_b = _make_graph_posting_list([(2, 0.6), (3, 0.5), (4, 0.4)])
    gpl_c = _make_graph_posting_list([(3, 0.3), (4, 0.2), (5, 0.1)])

    # Composition in source (graph) category: (A intersect B) union C
    composed_src = gpl_a.intersect(gpl_b).union(gpl_c)
    # Map the composed result
    lhs = functor.map_object(composed_src)

    # Apply functor to individual operations, compose in target (relational)
    fa = functor.map_object(gpl_a)
    fb = functor.map_object(gpl_b)
    fc = functor.map_object(gpl_c)
    rhs = fa.intersect(fb).union(fc)

    # The doc_id sets must match
    lhs_ids = sorted(e.doc_id for e in lhs)
    rhs_ids = sorted(e.doc_id for e in rhs)
    assert lhs_ids == rhs_ids


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


def test_roundtrip_relational_graph() -> None:
    """PL -> GPL -> PL preserves doc_ids."""
    r2g = RelationalToGraphFunctor()
    g2r = GraphToRelationalFunctor()

    original = _make_posting_list([(1, 0.9), (3, 0.7), (5, 0.5), (7, 0.3)])

    # Relational -> Graph -> Relational
    gpl = r2g.map_object(original)
    roundtripped = g2r.map_object(gpl)

    original_ids = sorted(e.doc_id for e in original)
    roundtripped_ids = sorted(e.doc_id for e in roundtripped)
    assert original_ids == roundtripped_ids
