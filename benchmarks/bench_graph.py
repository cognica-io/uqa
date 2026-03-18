#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for graph operations.

Covers graph traversal, pattern matching, RPQ compilation,
and Cypher query execution.
"""

from __future__ import annotations

from collections import deque

import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.graph.pattern import (
    EdgePattern,
    GraphPattern,
    VertexPattern,
    parse_rpq,
)
from uqa.graph.store import MemoryGraphStore as GraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


GRAPH_NAME = "bench"


def _build_graph(sf: int = 1) -> GraphStore:
    gen = BenchmarkDataGenerator(scale_factor=sf, seed=42)
    vertices, edges = gen.graph()
    gs = GraphStore()
    gs.create_graph(GRAPH_NAME)
    for v in vertices:
        gs.add_vertex(v, graph=GRAPH_NAME)
    for e in edges:
        gs.add_edge(e, graph=GRAPH_NAME)
    return gs


def _bfs(
    gs: GraphStore, start: int, max_depth: int, label: str | None = None
) -> set[int]:
    """BFS traversal returning visited vertex IDs."""
    visited: set[int] = {start}
    frontier = deque([start])
    depth = 0
    while frontier and depth < max_depth:
        next_frontier: deque[int] = deque()
        for _ in range(len(frontier)):
            v = frontier.popleft()
            for neighbor in gs.neighbors(
                v, label=label, direction="out", graph=GRAPH_NAME
            ):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier
        depth += 1
    return visited


# ---------------------------------------------------------------------------
# BFS Traversal
# ---------------------------------------------------------------------------


class TestBFSTraversal:
    @pytest.mark.parametrize("depth", [1, 2, 3])
    def test_bfs_depth(self, benchmark, depth: int) -> None:
        gs = _build_graph(sf=1)
        start = 1
        result = benchmark(_bfs, gs, start, depth)
        assert len(result) >= 1

    def test_bfs_with_label(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        result = benchmark(_bfs, gs, 1, 2, "knows")
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Neighbors Lookup
# ---------------------------------------------------------------------------


class TestNeighbors:
    def test_out_neighbors(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        benchmark(gs.neighbors, 1, None, "out", graph=GRAPH_NAME)

    def test_in_neighbors(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        benchmark(gs.neighbors, 1, None, "in", graph=GRAPH_NAME)

    def test_labeled_neighbors(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        benchmark(gs.neighbors, 1, "knows", "out", graph=GRAPH_NAME)


# ---------------------------------------------------------------------------
# Vertices by Label
# ---------------------------------------------------------------------------


class TestVertexLookup:
    def test_vertices_by_label(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        result = benchmark(gs.vertices_by_label, "Person", graph=GRAPH_NAME)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Pattern Matching
# ---------------------------------------------------------------------------


class TestPatternMatch:
    def _match_pattern(self, gs: GraphStore, pattern: GraphPattern) -> list[dict]:
        """Brute-force pattern match for benchmarking."""
        # Single edge pattern matching
        results: list[dict] = []
        if len(pattern.edge_patterns) == 0:
            return results

        ep = pattern.edge_patterns[0]
        for _eid, edge in gs._edges.items():
            if ep.label is not None and edge.label != ep.label:
                continue
            src = gs.get_vertex(edge.source_id)
            tgt = gs.get_vertex(edge.target_id)
            if src is None or tgt is None:
                continue
            # Check vertex constraints
            src_ok = (
                all(c(src) for c in pattern.vertex_patterns[0].constraints)
                if pattern.vertex_patterns
                else True
            )
            tgt_ok = (
                all(c(tgt) for c in pattern.vertex_patterns[1].constraints)
                if len(pattern.vertex_patterns) > 1
                else True
            )
            if src_ok and tgt_ok:
                results.append({ep.source_var: src, ep.target_var: tgt})
        return results

    def test_single_edge_pattern(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", label="knows")],
        )
        results = benchmark(self._match_pattern, gs, pattern)
        assert len(results) >= 0

    def test_labeled_edge_pattern(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", label="works_at")],
        )
        results = benchmark(self._match_pattern, gs, pattern)
        assert len(results) >= 0


# ---------------------------------------------------------------------------
# RPQ Compilation
# ---------------------------------------------------------------------------


class TestRPQ:
    def test_parse_simple(self, benchmark) -> None:
        benchmark(parse_rpq, "knows")

    def test_parse_concat(self, benchmark) -> None:
        benchmark(parse_rpq, "knows/works_at")

    def test_parse_alternation(self, benchmark) -> None:
        benchmark(parse_rpq, "knows|works_at|located_in")

    def test_parse_kleene(self, benchmark) -> None:
        benchmark(parse_rpq, "knows*")

    def test_parse_complex(self, benchmark) -> None:
        benchmark(parse_rpq, "(knows|works_at)*/located_in")


# ---------------------------------------------------------------------------
# Cypher Compilation
# ---------------------------------------------------------------------------


class TestCypherCompile:
    def test_simple_match(self, benchmark) -> None:
        from uqa.graph.cypher.parser import parse_cypher

        benchmark(parse_cypher, "MATCH (a)-[:knows]->(b) RETURN a, b")

    def test_multi_hop(self, benchmark) -> None:
        from uqa.graph.cypher.parser import parse_cypher

        benchmark(
            parse_cypher,
            "MATCH (a)-[:knows]->(b)-[:works_at]->(c) RETURN a, b, c",
        )

    def test_filtered(self, benchmark) -> None:
        from uqa.graph.cypher.parser import parse_cypher

        benchmark(
            parse_cypher,
            "MATCH (a:Person)-[:knows]->(b) WHERE a.name = 'Person_1' RETURN b",
        )
