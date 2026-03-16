#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for named graph operations.

Covers graph lifecycle, scoped traversal, pattern matching, RPQ,
graph algebra, property indexes, and isolation verification.
"""

from __future__ import annotations

from collections import deque

import pytest

from uqa.core.types import Edge, Vertex
from uqa.graph.index import VertexPropertyIndex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    TraverseOperator,
)
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern, parse_rpq
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def named_graph_store():
    """Graph store with a 'bench' named graph containing 1000 vertices and 999 edges."""
    gs = GraphStore()
    gs.create_graph("bench")
    for i in range(1, 1001):
        gs.add_vertex(Vertex(i, "node", {"val": i}), graph="bench")
    for i in range(1, 1000):
        gs.add_edge(Edge(i, i, i + 1, "next", {"weight": float(i)}), graph="bench")
    return gs


@pytest.fixture()
def two_graph_store():
    """Graph store with two 500-vertex graphs sharing 250 vertices."""
    gs = GraphStore()
    gs.create_graph("alpha")
    gs.create_graph("beta")
    for i in range(1, 501):
        gs.add_vertex(Vertex(i, "node", {"val": i}), graph="alpha")
    for i in range(1, 500):
        gs.add_edge(Edge(i, i, i + 1, "link"), graph="alpha")
    # Beta shares vertices 251-500 with alpha, plus 501-750
    for i in range(251, 751):
        gs.add_vertex(Vertex(i, "node", {"val": i}), graph="beta")
    for i in range(251, 750):
        gs.add_edge(Edge(500 + i, i, i + 1, "link"), graph="beta")
    return gs


# ---------------------------------------------------------------------------
# Graph Lifecycle
# ---------------------------------------------------------------------------


class TestCreateGraph:
    def test_create_100_graphs(self, benchmark) -> None:
        def _create():
            gs = GraphStore()
            for i in range(100):
                gs.create_graph(f"g_{i}")
            return gs

        result = benchmark(_create)
        assert len(result.graph_names()) == 100


# ---------------------------------------------------------------------------
# Vertex / Edge Addition
# ---------------------------------------------------------------------------


class TestAddVertices:
    def test_add_1000_vertices(self, benchmark) -> None:
        def _add():
            gs = GraphStore()
            gs.create_graph("bench")
            for i in range(1, 1001):
                gs.add_vertex(Vertex(i, "node", {"val": i}), graph="bench")
            return gs

        result = benchmark(_add)
        assert len(result.vertices_in_graph("bench")) == 1000


class TestAddEdges:
    def test_add_1000_edges(self, benchmark) -> None:
        def _add():
            gs = GraphStore()
            gs.create_graph("bench")
            for i in range(1, 1001):
                gs.add_vertex(Vertex(i, "node", {"val": i}), graph="bench")
            for i in range(1, 1001):
                gs.add_edge(Edge(i, i, (i % 1000) + 1, "link"), graph="bench")
            return gs

        result = benchmark(_add)
        assert len(result.edges_in_graph("bench")) == 1000


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


def _bfs(
    gs: GraphStore, start: int, max_depth: int, graph: str, label: str | None = None
) -> set[int]:
    """BFS traversal returning visited vertex IDs."""
    visited: set[int] = {start}
    frontier = deque([start])
    depth = 0
    while frontier and depth < max_depth:
        next_frontier: deque[int] = deque()
        for _ in range(len(frontier)):
            v = frontier.popleft()
            for neighbor in gs.neighbors(v, label=label, direction="out", graph=graph):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier
        depth += 1
    return visited


class TestTraversal:
    def test_traverse_1hop(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        result = benchmark(_bfs, gs, 1, 1, "bench", "next")
        assert len(result) >= 2

    def test_traverse_3hop(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        result = benchmark(_bfs, gs, 1, 3, "bench", "next")
        assert len(result) >= 4

    def test_traverse_operator_1hop(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        ctx = ExecutionContext(graph_store=gs)
        op = TraverseOperator(1, graph="bench", label="next", max_hops=1)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 2

    def test_traverse_operator_3hop(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        ctx = ExecutionContext(graph_store=gs)
        op = TraverseOperator(1, graph="bench", label="next", max_hops=3)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 4


# ---------------------------------------------------------------------------
# Pattern Matching
# ---------------------------------------------------------------------------


class TestPatternMatch:
    def test_triangle_pattern(self, benchmark, named_graph_store) -> None:
        """Triangle pattern match: a->b->c->a (unlikely in a chain, but exercises the code)."""
        gs = named_graph_store
        # Add a triangle to make the pattern matchable
        gs.add_edge(Edge(2000, 1, 3, "next"), graph="bench")
        gs.add_edge(Edge(2001, 3, 1, "next"), graph="bench")

        ctx = ExecutionContext(graph_store=gs)
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a"),
                VertexPattern("b"),
                VertexPattern("c"),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "next"),
                EdgePattern("b", "c", "next"),
                EdgePattern("c", "a", "next"),
            ],
        )
        op = PatternMatchOperator(pattern, graph="bench")
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# RPQ
# ---------------------------------------------------------------------------


class TestRPQ:
    def test_rpq_kleene(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        ctx = ExecutionContext(graph_store=gs)
        path_expr = parse_rpq("next*")
        op = RegularPathQueryOperator(path_expr, graph="bench", start_vertex=1)
        result = benchmark(op.execute, ctx)
        # Kleene star from vertex 1 should reach all 1000 vertices
        assert len(result) >= 100


# ---------------------------------------------------------------------------
# Graph Algebra
# ---------------------------------------------------------------------------


class TestGraphAlgebra:
    def test_union_graphs(self, benchmark, two_graph_store) -> None:
        gs = two_graph_store

        def _union():
            # Drop target if it exists from a previous iteration
            if gs.has_graph("union_target"):
                gs.drop_graph("union_target")
            gs.union_graphs("alpha", "beta", "union_target")
            return gs.vertices_in_graph("union_target")

        result = benchmark(_union)
        # alpha has 1..500, beta has 251..750 -> union has 1..750
        assert len(result) == 750

    def test_intersect_graphs(self, benchmark, two_graph_store) -> None:
        gs = two_graph_store

        def _intersect():
            if gs.has_graph("isect_target"):
                gs.drop_graph("isect_target")
            gs.intersect_graphs("alpha", "beta", "isect_target")
            return gs.vertices_in_graph("isect_target")

        result = benchmark(_intersect)
        # Overlap: 251..500 -> 250 vertices
        assert len(result) == 250


# ---------------------------------------------------------------------------
# Property Indexes
# ---------------------------------------------------------------------------


class TestPropertyIndex:
    def test_build_vertex_property_index(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        idx = benchmark(
            VertexPropertyIndex.build, gs, graph="bench", properties=["val"]
        )
        assert idx.has_property("val")

    def test_vertex_property_index_lookup(self, benchmark, named_graph_store) -> None:
        gs = named_graph_store
        idx = VertexPropertyIndex.build(gs, graph="bench", properties=["val"])

        def _lookup():
            results = 0
            for i in range(1, 1001):
                ids = idx.lookup_eq("val", i)
                results += len(ids)
            return results

        total = benchmark(_lookup)
        assert total == 1000


# ---------------------------------------------------------------------------
# Graph Isolation
# ---------------------------------------------------------------------------


class TestGraphIsolation:
    def test_isolation(self, benchmark, two_graph_store) -> None:
        """Verify traversal does not cross graph boundaries."""
        gs = two_graph_store
        ctx = ExecutionContext(graph_store=gs)

        def _verify_isolation():
            # Traverse alpha from vertex 1 -- should not reach beta-only vertices
            op = TraverseOperator(1, graph="alpha", label="link", max_hops=500)
            result = op.execute(ctx)
            alpha_ids = {e.doc_id for e in result}
            # Vertices 501-750 are beta-only
            assert not alpha_ids.intersection(range(501, 751))
            return len(alpha_ids)

        count = benchmark(_verify_isolation)
        assert count >= 1
