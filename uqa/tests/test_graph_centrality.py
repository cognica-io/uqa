#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import Edge, IndexStats, Vertex
from uqa.graph.centrality import (
    BetweennessCentralityOperator,
    HITSOperator,
    PageRankOperator,
)
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext

_GRAPH_NAME = "test"


def _make_star_graph() -> GraphStore:
    """Star/hub graph: center vertex 1, spokes 2, 3, 4.

    Edges: 1->2, 1->3, 1->4, 2->1, 3->1, 4->1 (bidirectional hub).
    """
    g = GraphStore()
    g.create_graph(_GRAPH_NAME)
    for i in range(1, 5):
        g.add_vertex(Vertex(i, "node", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(1, 1, 2, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(2, 1, 3, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(3, 1, 4, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(4, 2, 1, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(5, 3, 1, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(6, 4, 1, "link", {}), graph=_GRAPH_NAME)
    return g


def _make_chain_graph() -> GraphStore:
    """Chain graph: 1 -> 2 -> 3 -> 4."""
    g = GraphStore()
    g.create_graph(_GRAPH_NAME)
    for i in range(1, 5):
        g.add_vertex(Vertex(i, "node", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(1, 1, 2, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(2, 2, 3, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(3, 3, 4, "link", {}), graph=_GRAPH_NAME)
    return g


def _make_bipartite_graph() -> GraphStore:
    """Bipartite graph: hubs {1, 2} point to authorities {3, 4, 5}.

    Edges: 1->3, 1->4, 1->5, 2->3, 2->4, 2->5.
    """
    g = GraphStore()
    g.create_graph(_GRAPH_NAME)
    for i in range(1, 6):
        g.add_vertex(Vertex(i, "node", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(1, 1, 3, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(2, 1, 4, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(3, 1, 5, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(4, 2, 3, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(5, 2, 4, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(6, 2, 5, "link", {}), graph=_GRAPH_NAME)
    return g


def _make_line_graph() -> GraphStore:
    """Line graph: 1 -> 2 -> 3 (3 vertices)."""
    g = GraphStore()
    g.create_graph(_GRAPH_NAME)
    for i in range(1, 4):
        g.add_vertex(Vertex(i, "node", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(1, 1, 2, "link", {}), graph=_GRAPH_NAME)
    g.add_edge(Edge(2, 2, 3, "link", {}), graph=_GRAPH_NAME)
    return g


# ---------------------------------------------------------------------------
# PageRank tests
# ---------------------------------------------------------------------------


class TestPageRankOperator:
    def test_star_topology(self) -> None:
        """Center vertex has highest rank in a star/hub graph."""
        graph = _make_star_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = PageRankOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        scores = {e.doc_id: e.payload.score for e in result}
        # Vertex 1 is the hub; it should have the highest score
        assert scores[1] == max(scores.values())

    def test_chain_graph(self) -> None:
        """Last vertex in a chain receives the most incoming influence."""
        graph = _make_chain_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = PageRankOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        scores = {e.doc_id: e.payload.score for e in result}
        # In a chain 1->2->3->4, vertex 4 gets the highest rank
        assert scores[4] == max(scores.values())

    def test_empty_graph(self) -> None:
        """Empty graph returns empty result."""
        graph = GraphStore()
        graph.create_graph(_GRAPH_NAME)
        ctx = ExecutionContext(graph_store=graph)
        op = PageRankOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        assert len(list(result)) == 0

    def test_single_vertex(self) -> None:
        """Single vertex returns score 1.0."""
        graph = GraphStore()
        graph.create_graph(_GRAPH_NAME)
        graph.add_vertex(Vertex(1, "node", {}), graph=_GRAPH_NAME)
        ctx = ExecutionContext(graph_store=graph)
        op = PageRankOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        entries = list(result)
        assert len(entries) == 1
        assert entries[0].payload.score == pytest.approx(1.0)

    def test_convergence_idempotent(self) -> None:
        """Running PageRank twice gives the same result."""
        graph = _make_star_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = PageRankOperator(graph=_GRAPH_NAME)
        result1 = op.execute(ctx)
        result2 = op.execute(ctx)

        scores1 = {e.doc_id: e.payload.score for e in result1}
        scores2 = {e.doc_id: e.payload.score for e in result2}
        for vid in scores1:
            assert scores1[vid] == pytest.approx(scores2[vid])

    def test_cost_estimate(self) -> None:
        """Verify cost formula: total_docs * max_iterations * 0.1."""
        stats = IndexStats(total_docs=1000)
        op = PageRankOperator(max_iterations=50, graph=_GRAPH_NAME)
        assert op.cost_estimate(stats) == pytest.approx(1000 * 50 * 0.1)


# ---------------------------------------------------------------------------
# HITS tests
# ---------------------------------------------------------------------------


class TestHITSOperator:
    def test_bipartite_graph(self) -> None:
        """Hub vertices have highest hub score, authority vertices highest
        authority score in a bipartite graph."""
        graph = _make_bipartite_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = HITSOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        hub_scores: dict[int, float] = {}
        auth_scores: dict[int, float] = {}
        for entry in result:
            vid = entry.doc_id
            hub_scores[vid] = entry.payload.fields["hub_score"]
            auth_scores[vid] = entry.payload.fields["authority_score"]

        # Vertices 1 and 2 are hubs
        hub_vertices = {1, 2}
        authority_vertices = {3, 4, 5}

        max_hub_among_hubs = max(hub_scores[v] for v in hub_vertices)
        max_hub_among_auths = max(hub_scores[v] for v in authority_vertices)
        assert max_hub_among_hubs > max_hub_among_auths

        max_auth_among_auths = max(auth_scores[v] for v in authority_vertices)
        max_auth_among_hubs = max(auth_scores[v] for v in hub_vertices)
        assert max_auth_among_auths > max_auth_among_hubs

    def test_hub_authority_fields_present(self) -> None:
        """Verify hub_score and authority_score fields are in payload."""
        graph = _make_star_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = HITSOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        for entry in result:
            assert "hub_score" in entry.payload.fields
            assert "authority_score" in entry.payload.fields

    def test_empty_graph(self) -> None:
        """Empty graph returns empty result."""
        graph = GraphStore()
        graph.create_graph(_GRAPH_NAME)
        ctx = ExecutionContext(graph_store=graph)
        op = HITSOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        assert len(list(result)) == 0


# ---------------------------------------------------------------------------
# Betweenness centrality tests
# ---------------------------------------------------------------------------


class TestBetweennessCentralityOperator:
    def test_line_graph(self) -> None:
        """Middle vertex in a line graph has the highest betweenness."""
        graph = _make_line_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = BetweennessCentralityOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        scores = {e.doc_id: e.payload.score for e in result}
        # Vertex 2 is the middle of 1->2->3, highest betweenness
        assert scores[2] == max(scores.values())
        assert scores[2] > 0.0

    def test_star_topology(self) -> None:
        """Center vertex has highest betweenness in a star graph."""
        graph = _make_star_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = BetweennessCentralityOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        scores = {e.doc_id: e.payload.score for e in result}
        assert scores[1] == max(scores.values())

    def test_scores_in_unit_interval(self) -> None:
        """All betweenness scores must be in [0, 1]."""
        graph = _make_star_graph()
        ctx = ExecutionContext(graph_store=graph)
        op = BetweennessCentralityOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        for entry in result:
            assert 0.0 <= entry.payload.score <= 1.0

    def test_empty_graph(self) -> None:
        """Empty graph returns empty result."""
        graph = GraphStore()
        graph.create_graph(_GRAPH_NAME)
        ctx = ExecutionContext(graph_store=graph)
        op = BetweennessCentralityOperator(graph=_GRAPH_NAME)
        result = op.execute(ctx)

        assert len(list(result)) == 0
