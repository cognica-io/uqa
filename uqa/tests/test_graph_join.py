#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.graph.join import CrossParadigmGraphJoinOperator, GraphGraphJoinOperator
from uqa.graph.posting_list import GraphPayload, GraphPostingList
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext

# -- Helpers --


class _ConstGPL:
    """Return a fixed GraphPostingList."""

    def __init__(self, gpl: GraphPostingList) -> None:
        self._gpl = gpl

    def execute(self, ctx: object) -> GraphPostingList:
        return self._gpl


class _ConstPL:
    """Return a fixed PostingList."""

    def __init__(self, pl: PostingList) -> None:
        self._pl = pl

    def execute(self, ctx: object) -> PostingList:
        return self._pl


def _make_gpl(
    entries: list[tuple[int, dict[str, int]]],
    vertices: list[frozenset[int]] | None = None,
) -> GraphPostingList:
    """Build a GraphPostingList from (doc_id, fields) pairs."""
    pe_list: list[PostingEntry] = []
    gp_map: dict[int, GraphPayload] = {}
    for i, (doc_id, fields) in enumerate(entries):
        pe_list.append(PostingEntry(doc_id, Payload(score=0.9, fields=fields)))
        verts = vertices[i] if vertices else frozenset(fields.values())
        gp_map[doc_id] = GraphPayload(
            subgraph_vertices=verts, subgraph_edges=frozenset()
        )
    return GraphPostingList(pe_list, gp_map)


def _ctx() -> ExecutionContext:
    gs = GraphStore()
    gs.create_graph("test")
    return ExecutionContext(graph_store=gs)


# -- GraphGraphJoinOperator tests --


def test_graph_graph_join_basic():
    left = _make_gpl([(1, {"x": 10}), (2, {"x": 20})])
    right = _make_gpl([(3, {"x": 20}), (4, {"x": 30})])

    op = GraphGraphJoinOperator(_ConstGPL(left), _ConstGPL(right), "x", graph="test")
    result = op.execute(_ctx())
    assert len(result) == 1
    # Joined on x=20
    assert result.entries[0].payload.fields["x"] == 20


def test_graph_graph_join_empty():
    left = _make_gpl([(1, {"x": 10})])
    right = _make_gpl([(2, {"x": 20})])

    op = GraphGraphJoinOperator(_ConstGPL(left), _ConstGPL(right), "x", graph="test")
    result = op.execute(_ctx())
    assert len(result) == 0


def test_graph_graph_join_metadata_merge():
    left = _make_gpl(
        [(1, {"x": 10})],
        vertices=[frozenset({1, 2})],
    )
    right = _make_gpl(
        [(2, {"x": 10})],
        vertices=[frozenset({3, 4})],
    )

    op = GraphGraphJoinOperator(_ConstGPL(left), _ConstGPL(right), "x", graph="test")
    result = op.execute(_ctx())
    assert len(result) == 1
    gp = result.get_graph_payload(1)
    assert gp is not None
    # Union of subgraph_vertices
    assert gp.subgraph_vertices == frozenset({1, 2, 3, 4})


def test_graph_graph_join_commutativity():
    """Graph join is NOT commutative in general (left fields take precedence)."""
    left = _make_gpl([(1, {"x": 10, "side": 1})])
    right = _make_gpl([(2, {"x": 10, "side": 2})])

    op_lr = GraphGraphJoinOperator(_ConstGPL(left), _ConstGPL(right), "x", graph="test")
    op_rl = GraphGraphJoinOperator(_ConstGPL(right), _ConstGPL(left), "x", graph="test")
    ctx = _ctx()
    r_lr = op_lr.execute(ctx)
    r_rl = op_rl.execute(ctx)
    # Both produce 1 result, but "side" field differs
    assert len(r_lr) == 1
    assert len(r_rl) == 1
    assert r_lr.entries[0].payload.fields["side"] == 1  # left wins
    assert r_rl.entries[0].payload.fields["side"] == 2  # left wins


def test_graph_graph_join_multiple_matches():
    left = _make_gpl([(1, {"x": 10}), (2, {"x": 10})])
    right = _make_gpl([(3, {"x": 10}), (4, {"x": 10})])

    op = GraphGraphJoinOperator(_ConstGPL(left), _ConstGPL(right), "x", graph="test")
    result = op.execute(_ctx())
    # 2 left * 2 right = 4 matches
    assert len(result) == 4


def test_graph_graph_join_associativity():
    """(A join B) join C should produce same match count as A join (B join C)."""
    a = _make_gpl([(1, {"x": 5, "src": 1})])
    b = _make_gpl([(2, {"x": 5, "src": 2})])
    c = _make_gpl([(3, {"x": 5, "src": 3})])

    ctx = _ctx()

    # (A join B) join C
    ab_op = GraphGraphJoinOperator(_ConstGPL(a), _ConstGPL(b), "x", graph="test")
    ab_result = ab_op.execute(ctx)
    abc_op = GraphGraphJoinOperator(
        _ConstGPL(ab_result), _ConstGPL(c), "x", graph="test"
    )
    abc_result = abc_op.execute(ctx)

    # A join (B join C)
    bc_op = GraphGraphJoinOperator(_ConstGPL(b), _ConstGPL(c), "x", graph="test")
    bc_result = bc_op.execute(ctx)
    a_bc_op = GraphGraphJoinOperator(
        _ConstGPL(a), _ConstGPL(bc_result), "x", graph="test"
    )
    a_bc_result = a_bc_op.execute(ctx)

    # Same number of results (associative on cardinality)
    assert len(abc_result) == len(a_bc_result)
    assert len(abc_result) == 1  # single match on x=5


# -- CrossParadigmGraphJoinOperator tests --


def test_cross_paradigm_join_basic():
    gpl = _make_gpl([(1, {"vid": 100})])
    rel = PostingList(
        [
            PostingEntry(100, Payload(score=0.5, fields={"name": "Alice"})),
            PostingEntry(200, Payload(score=0.5, fields={"name": "Bob"})),
        ]
    )

    op = CrossParadigmGraphJoinOperator(_ConstGPL(gpl), _ConstPL(rel), "vid", "doc_id")
    result = op.execute(_ctx())
    assert len(result) == 1
    assert result.entries[0].doc_id == 100
    assert result.entries[0].payload.fields["name"] == "Alice"


def test_cross_paradigm_join_empty():
    gpl = _make_gpl([(1, {"vid": 999})])
    rel = PostingList(
        [
            PostingEntry(100, Payload(score=0.5, fields={})),
        ]
    )

    op = CrossParadigmGraphJoinOperator(_ConstGPL(gpl), _ConstPL(rel), "vid", "doc_id")
    result = op.execute(_ctx())
    assert len(result) == 0


def test_cross_paradigm_join_score_merge():
    gpl = _make_gpl([(1, {"vid": 100})])
    rel = PostingList(
        [
            PostingEntry(100, Payload(score=0.3, fields={})),
        ]
    )

    op = CrossParadigmGraphJoinOperator(_ConstGPL(gpl), _ConstPL(rel), "vid", "doc_id")
    result = op.execute(_ctx())
    assert len(result) == 1
    # 0.9 (graph) + 0.3 (relational) = 1.2
    assert abs(result.entries[0].payload.score - 1.2) < 0.01
