#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.graph.operators import PatternMatchOperator
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext


def _make_social_graph() -> GraphStore:
    """Create a social graph with some edges:
    Alice -> Bob (knows)
    Alice -> Carol (knows)
    Bob -> Carol (knows)
    Alice -> Dave (blocks)
    """
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="g")
    gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="g")
    gs.add_vertex(Vertex(3, "person", {"name": "Carol"}), graph="g")
    gs.add_vertex(Vertex(4, "person", {"name": "Dave"}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g")
    gs.add_edge(Edge(11, 1, 3, "knows", {}), graph="g")
    gs.add_edge(Edge(12, 2, 3, "knows", {}), graph="g")
    gs.add_edge(Edge(13, 1, 4, "blocks", {}), graph="g")
    return gs


def test_positive_edge_pattern():
    """Baseline: positive edge pattern works as before."""
    gs = _make_social_graph()
    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[EdgePattern("a", "b", "knows")],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # Alice->Bob, Alice->Carol, Bob->Carol = 3 matches
    assert len(result) == 3


def test_negated_edge_basic():
    """Find pairs (a, b) where a knows b but a does NOT block b."""
    gs = _make_social_graph()
    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[
            EdgePattern("a", "b", "knows"),
            EdgePattern("a", "b", "blocks", negated=True),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # Alice knows Bob (no block), Alice knows Carol (no block), Bob knows Carol (no block)
    # But Alice does NOT block Bob or Carol, so all 3 pass
    assert len(result) == 3


def test_negated_edge_filters_match():
    """Find pairs (a, b) where a->b via 'blocks' AND a does NOT know b."""
    gs = _make_social_graph()
    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[
            EdgePattern("a", "b", "blocks"),
            EdgePattern("a", "b", "knows", negated=True),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # Alice blocks Dave, and Alice does NOT know Dave -> 1 match
    assert len(result) == 1
    assert result.entries[0].payload.fields["a"] == 1
    assert result.entries[0].payload.fields["b"] == 4


def test_negated_edge_removes_all():
    """When negation removes all matches."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g")
    gs.add_edge(Edge(11, 1, 2, "blocks", {}), graph="g")

    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[
            EdgePattern("a", "b", "knows"),
            EdgePattern("a", "b", "blocks", negated=True),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # 1->2 via "knows" exists, but 1->2 via "blocks" also exists, so negation fails
    assert len(result) == 0


def test_negated_only_pattern():
    """Pattern with only negated edges: all vertex pairs where no edge exists."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")

    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[
            EdgePattern("a", "b", "e", negated=True),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # Without positive edges, backtracking produces all (a,b) pairs where a!=b
    # = 6 pairs. Negation removes (1,2) where edge exists.
    # Remaining: (1,3), (2,1), (2,3), (3,1), (3,2) = 5
    assert len(result) == 5


def test_negated_edge_no_label():
    """Negated edge with no label means 'no edge of any label'."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e1", {}), graph="g")

    pattern = GraphPattern(
        vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
        edge_patterns=[
            EdgePattern("a", "b", None, negated=True),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g")
    result = op.execute(ctx)
    # (1,2) has edge with any label -> removed by negation
    # Remaining: (1,3), (2,1), (2,3), (3,1), (3,2) = 5
    assert len(result) == 5


def test_negated_edge_default_false():
    """EdgePattern.negated defaults to False."""
    ep = EdgePattern("a", "b", "knows")
    assert ep.negated is False

    ep_neg = EdgePattern("a", "b", "knows", negated=True)
    assert ep_neg.negated is True
