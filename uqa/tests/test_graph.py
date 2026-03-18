#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import Edge, Payload, PostingEntry, Vertex
from uqa.graph.cross_paradigm import (
    TextToGraphOperator,
    VectorEnhancedMatchOperator,
    VertexEmbeddingOperator,
)
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    TraverseOperator,
)
from uqa.graph.pattern import (
    Alternation,
    Concat,
    EdgePattern,
    GraphPattern,
    KleeneStar,
    Label,
    VertexPattern,
    parse_rpq,
)
from uqa.graph.posting_list import GraphPayload, GraphPostingList
from uqa.graph.store import MemoryGraphStore as GraphStore


class _ExecutionContext:
    """Minimal execution context for testing."""

    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store


@pytest.fixture
def graph_store(
    sample_graph_vertices: list[Vertex],
    sample_graph_edges: list[Edge],
) -> GraphStore:
    store = GraphStore()
    store.create_graph("test")
    for v in sample_graph_vertices:
        store.add_vertex(v, graph="test")
    for e in sample_graph_edges:
        store.add_edge(e, graph="test")
    return store


@pytest.fixture
def ctx(graph_store: GraphStore) -> _ExecutionContext:
    return _ExecutionContext(graph_store)


# -- GraphStore tests --


class TestGraphStore:
    def test_add_and_get_vertex(self, graph_store: GraphStore) -> None:
        v = graph_store.get_vertex(1)
        assert v is not None
        assert v.properties["name"] == "Alice"

    def test_add_and_get_edge(self, graph_store: GraphStore) -> None:
        e = graph_store.get_edge(1)
        assert e is not None
        assert e.source_id == 1
        assert e.target_id == 2
        assert e.label == "knows"

    def test_neighbors_out(self, graph_store: GraphStore) -> None:
        neighbors = graph_store.neighbors(1, direction="out", graph="test")
        assert set(neighbors) == {2, 3}

    def test_neighbors_out_with_label(self, graph_store: GraphStore) -> None:
        neighbors = graph_store.neighbors(
            3, label="works_with", direction="out", graph="test"
        )
        assert set(neighbors) == {5}

    def test_neighbors_in(self, graph_store: GraphStore) -> None:
        neighbors = graph_store.neighbors(3, direction="in", graph="test")
        assert set(neighbors) == {1, 2}

    def test_missing_vertex(self, graph_store: GraphStore) -> None:
        assert graph_store.get_vertex(999) is None

    def test_missing_edge(self, graph_store: GraphStore) -> None:
        assert graph_store.get_edge(999) is None


# -- TraverseOperator tests --


class TestTraverseOperator:
    def test_single_hop(self, ctx: _ExecutionContext) -> None:
        op = TraverseOperator(start_vertex=1, graph="test", max_hops=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # From vertex 1: can reach 2 and 3 in 1 hop, plus start vertex 1
        assert {1, 2, 3} == doc_ids

    def test_two_hops(self, ctx: _ExecutionContext) -> None:
        op = TraverseOperator(start_vertex=1, graph="test", max_hops=2)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # Hop 1: {2, 3}, Hop 2: from 2->{3,4}, from 3->{4,5}
        assert {1, 2, 3, 4, 5} == doc_ids

    def test_with_label_filter(self, ctx: _ExecutionContext) -> None:
        op = TraverseOperator(start_vertex=1, graph="test", label="knows", max_hops=2)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # Hop 1: {2,3} via "knows", Hop 2: 2->3 "knows", 2->4 "works_with" (skip), 3->4 "knows", 3->5 "works_with" (skip)
        assert {1, 2, 3, 4} == doc_ids

    def test_max_hops_zero(self, ctx: _ExecutionContext) -> None:
        op = TraverseOperator(start_vertex=1, graph="test", max_hops=0)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # Zero hops: only the start vertex
        assert {1} == doc_ids

    def test_bfs_correctness_at_each_depth(self, ctx: _ExecutionContext) -> None:
        """Verify BFS visits correct vertices at each depth."""
        # depth 1
        op1 = TraverseOperator(start_vertex=1, graph="test", max_hops=1)
        r1 = {e.doc_id for e in op1.execute(ctx)}

        # depth 2
        op2 = TraverseOperator(start_vertex=1, graph="test", max_hops=2)
        r2 = {e.doc_id for e in op2.execute(ctx)}

        # depth 2 should be a superset of depth 1
        assert r1.issubset(r2)

        # depth 3
        op3 = TraverseOperator(start_vertex=1, graph="test", max_hops=3)
        r3 = {e.doc_id for e in op3.execute(ctx)}
        assert r2.issubset(r3)


# -- PatternMatchOperator tests --


class TestPatternMatchOperator:
    def test_find_triangles(self, ctx: _ExecutionContext) -> None:
        """Find all triangles (3-cliques) in the graph."""
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a"),
                VertexPattern("b"),
                VertexPattern("c"),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "knows"),
                EdgePattern("b", "c", "knows"),
                EdgePattern("a", "c", "knows"),
            ],
        )
        op = PatternMatchOperator(pattern, graph="test")
        result = op.execute(ctx)
        # Triangle: (1,2,3) - edges: 1->2 knows, 2->3 knows, 1->3 knows
        assert len(result) >= 1
        # Verify at least one match has vertices {1,2,3}
        found_triangle = False
        for entry in result:
            gp = result.get_graph_payload(entry.doc_id)
            if gp is not None and gp.subgraph_vertices == frozenset({1, 2, 3}):
                found_triangle = True
                break
        assert found_triangle

    def test_find_star_pattern(self, ctx: _ExecutionContext) -> None:
        """Find a center vertex connected to two others via 'knows'."""
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("center"),
                VertexPattern("leaf1"),
                VertexPattern("leaf2"),
            ],
            edge_patterns=[
                EdgePattern("center", "leaf1", "knows"),
                EdgePattern("center", "leaf2", "knows"),
            ],
        )
        op = PatternMatchOperator(pattern, graph="test")
        result = op.execute(ctx)
        # Vertex 1 knows 2 and 3, vertex 3 knows 4 (and 1->2, 1->3)
        assert len(result) >= 1

    def test_vertex_constraints(self, ctx: _ExecutionContext) -> None:
        """Pattern match with vertex property constraints."""
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a", [lambda v: v.properties.get("age", 0) < 30]),
                VertexPattern("b"),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "knows"),
            ],
        )
        op = PatternMatchOperator(pattern, graph="test")
        result = op.execute(ctx)
        # Only Bob (25) and Diana (28) have age < 30
        # Bob knows Charlie (edge 3), Diana knows Eve (edge 7)
        for entry in result:
            gp = result.get_graph_payload(entry.doc_id)
            assert gp is not None
            # Source vertex should be Bob(2) or Diana(4)
            for vid in gp.subgraph_vertices:
                v = ctx.graph_store.get_vertex(vid)
                assert v is not None

    def test_empty_pattern_match(self, ctx: _ExecutionContext) -> None:
        """Pattern that cannot match should return empty result."""
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a"),
                VertexPattern("b"),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "nonexistent_label"),
            ],
        )
        op = PatternMatchOperator(pattern, graph="test")
        result = op.execute(ctx)
        assert len(result) == 0


# -- RegularPathQueryOperator tests --


class TestRegularPathQueryOperator:
    def test_single_label(self, ctx: _ExecutionContext) -> None:
        expr = Label("knows")
        op = RegularPathQueryOperator(expr, graph="test", start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # 1 -knows-> 2, 1 -knows-> 3
        assert doc_ids == {2, 3}

    def test_concat(self, ctx: _ExecutionContext) -> None:
        expr = Concat(Label("knows"), Label("knows"))
        op = RegularPathQueryOperator(expr, graph="test", start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # 1-knows->2-knows->3, 1-knows->3-knows->4
        # 1-knows->2 then 2-knows->3 => end 3
        # 1-knows->3 then 3-knows->4 => end 4
        assert {3, 4}.issubset(doc_ids)

    def test_alternation(self, ctx: _ExecutionContext) -> None:
        expr = Alternation(Label("knows"), Label("works_with"))
        op = RegularPathQueryOperator(expr, graph="test", start_vertex=2)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # 2-knows->3, 2-works_with->4
        assert doc_ids == {3, 4}

    def test_kleene_star(self, ctx: _ExecutionContext) -> None:
        expr = KleeneStar(Label("knows"))
        op = RegularPathQueryOperator(expr, graph="test", start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # Kleene star includes zero hops (start vertex itself)
        assert 1 in doc_ids
        # And transitive closure via "knows": 1->2, 1->3, 2->3, 3->4, 4->5
        assert {1, 2, 3, 4, 5}.issubset(doc_ids)

    def test_all_vertices_start(self, ctx: _ExecutionContext) -> None:
        """RPQ without start_vertex searches from all vertices."""
        expr = Label("works_with")
        op = RegularPathQueryOperator(expr, graph="test")
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # edges: 2-works_with->4, 3-works_with->5
        assert {4, 5}.issubset(doc_ids)


# -- RPQ parser tests --


class TestParseRPQ:
    def test_single_label(self) -> None:
        result = parse_rpq("knows")
        assert isinstance(result, Label)
        assert result.name == "knows"

    def test_concat(self) -> None:
        result = parse_rpq("knows/works_with")
        assert isinstance(result, Concat)
        assert isinstance(result.left, Label)
        assert isinstance(result.right, Label)

    def test_alternation(self) -> None:
        result = parse_rpq("knows|works_with")
        assert isinstance(result, Alternation)

    def test_kleene_star(self) -> None:
        result = parse_rpq("knows*")
        assert isinstance(result, KleeneStar)
        assert isinstance(result.inner, Label)

    def test_parentheses(self) -> None:
        result = parse_rpq("(knows|works_with)*")
        assert isinstance(result, KleeneStar)
        assert isinstance(result.inner, Alternation)

    def test_complex_expression(self) -> None:
        result = parse_rpq("knows/works_with|knows*")
        # alternation is lowest precedence:
        # (knows/works_with) | (knows*)
        assert isinstance(result, Alternation)

    def test_invalid_expression(self) -> None:
        with pytest.raises(ValueError):
            parse_rpq(")")


# -- GraphPostingList isomorphism tests --


class TestGraphPostingListIsomorphism:
    def test_round_trip(self) -> None:
        """to_posting_list then from_posting_list should preserve data."""
        entries = [
            PostingEntry(1, Payload(score=0.5)),
            PostingEntry(2, Payload(score=0.8)),
        ]
        gpl = GraphPostingList(entries)
        gpl.set_graph_payload(1, GraphPayload(frozenset({1, 2}), frozenset({10}), 0.5))
        gpl.set_graph_payload(2, GraphPayload(frozenset({2, 3}), frozenset({20}), 0.8))

        # Convert to standard posting list and back
        pl = gpl.to_posting_list()
        gpl2 = GraphPostingList.from_posting_list(pl)

        # Verify graph payloads are preserved
        gp1 = gpl2.get_graph_payload(1)
        assert gp1 is not None
        assert gp1.subgraph_vertices == frozenset({1, 2})
        assert gp1.subgraph_edges == frozenset({10})

        gp2 = gpl2.get_graph_payload(2)
        assert gp2 is not None
        assert gp2.subgraph_vertices == frozenset({2, 3})
        assert gp2.subgraph_edges == frozenset({20})

    def test_functor_property_union(self) -> None:
        """Phi(A union B) = Phi(A) union Phi(B)

        The isomorphism should preserve union operations.
        """
        entries_a = [
            PostingEntry(1, Payload(score=0.5)),
            PostingEntry(3, Payload(score=0.3)),
        ]
        entries_b = [
            PostingEntry(2, Payload(score=0.8)),
            PostingEntry(3, Payload(score=0.4)),
        ]

        gpl_a = GraphPostingList(entries_a)
        gpl_a.set_graph_payload(1, GraphPayload(frozenset({1}), frozenset(), 0.5))
        gpl_a.set_graph_payload(3, GraphPayload(frozenset({3}), frozenset(), 0.3))

        gpl_b = GraphPostingList(entries_b)
        gpl_b.set_graph_payload(2, GraphPayload(frozenset({2}), frozenset(), 0.8))
        gpl_b.set_graph_payload(3, GraphPayload(frozenset({3}), frozenset(), 0.4))

        # Phi(A union B) -- compute union at graph level, then convert
        gpl_union = gpl_a.union(gpl_b)
        pl_of_union = GraphPostingList(gpl_union.entries).to_posting_list()

        # Phi(A) union Phi(B) -- convert each, then union
        pl_a = gpl_a.to_posting_list()
        pl_b = gpl_b.to_posting_list()
        union_of_pl = pl_a.union(pl_b)

        # Both should have the same doc_ids
        assert pl_of_union.doc_ids == union_of_pl.doc_ids


# -- VertexEmbeddingOperator tests --


class TestVertexEmbeddingOperator:
    def test_basic_embedding_search(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.9, 0.1, 0.0])
        v3 = np.array([0.0, 0.0, 1.0])
        store.add_vertex(Vertex(1, "", {"embedding": v1}), graph="test")
        store.add_vertex(Vertex(2, "", {"embedding": v2}), graph="test")
        store.add_vertex(Vertex(3, "", {"embedding": v3}), graph="test")
        ctx = _ExecutionContext(store)

        query = np.array([1.0, 0.0, 0.0])
        op = VertexEmbeddingOperator(query, threshold=0.8, graph="test")
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        # v1 is identical (sim=1.0), v2 is close, v3 is orthogonal
        assert 1 in doc_ids
        assert 2 in doc_ids
        assert 3 not in doc_ids

    def test_no_embedding_field(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {"name": "Alice"}), graph="test")
        ctx = _ExecutionContext(store)

        query = np.array([1.0, 0.0])
        op = VertexEmbeddingOperator(query, threshold=0.0, graph="test")
        result = op.execute(ctx)
        assert len(result) == 0

    def test_sorted_output(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        for i in [5, 3, 1]:
            store.add_vertex(
                Vertex(i, "", {"embedding": np.array([1.0, 0.0])}), graph="test"
            )
        ctx = _ExecutionContext(store)

        query = np.array([1.0, 0.0])
        op = VertexEmbeddingOperator(query, threshold=0.0, graph="test")
        result = op.execute(ctx)
        ids = [e.doc_id for e in result]
        assert ids == sorted(ids)


# -- VectorEnhancedMatchOperator tests --


class TestVectorEnhancedMatchOperator:
    def test_pattern_match_with_vector_scoring(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        v_embed = np.array([1.0, 0.0])
        store.add_vertex(Vertex(1, "", {"embedding": v_embed}), graph="test")
        store.add_vertex(
            Vertex(2, "", {"embedding": np.array([0.9, 0.1])}), graph="test"
        )
        store.add_vertex(
            Vertex(3, "", {"embedding": np.array([0.0, 1.0])}), graph="test"
        )
        store.add_edge(Edge(1, 1, 2, "knows"), graph="test")
        store.add_edge(Edge(2, 1, 3, "knows"), graph="test")
        ctx = _ExecutionContext(store)

        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "knows")],
        )
        query = np.array([1.0, 0.0])
        op = VectorEnhancedMatchOperator(
            pattern, query, score_variable="b", threshold=0.5, graph="test"
        )
        result = op.execute(ctx)
        # Matches: (a=1,b=2) with sim(v2, query) high
        #          (a=1,b=3) with sim(v3, query)=0.0 < 0.5
        scored_entries = [e for e in result if e.payload.score >= 0.5]
        assert len(scored_entries) >= 1

    def test_threshold_filtering(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(
            Vertex(1, "", {"embedding": np.array([1.0, 0.0])}), graph="test"
        )
        store.add_vertex(
            Vertex(2, "", {"embedding": np.array([0.0, 1.0])}), graph="test"
        )
        store.add_edge(Edge(1, 1, 2, "link"), graph="test")
        ctx = _ExecutionContext(store)

        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "link")],
        )
        query = np.array([1.0, 0.0])
        # High threshold: v2 is orthogonal to query
        op = VectorEnhancedMatchOperator(
            pattern, query, score_variable="b", threshold=0.9, graph="test"
        )
        result = op.execute(ctx)
        assert len(result) == 0


# -- TextToGraphOperator tests --


class TestTextToGraphOperator:
    def test_basic_co_occurrence(self) -> None:
        docs = [
            {"text": "the quick brown fox"},
            {"text": "the quick red fox"},
        ]
        op = TextToGraphOperator(docs, text_field="text")
        graph = op.execute(None)

        tokens = {v.properties["token"] for v in graph._vertices.values()}
        assert "quick" in tokens
        assert "fox" in tokens
        assert "brown" in tokens
        assert "red" in tokens
        assert "the" not in tokens  # stop word removed by standard analyzer
        # "quick" and "fox" co-occur in both documents
        assert len(graph._edges) > 0

    def test_window_size(self) -> None:
        docs = [{"text": "a b c d e"}]
        op_full = TextToGraphOperator(docs, text_field="text", window_size=0)
        graph_full = op_full.execute(None)

        op_window = TextToGraphOperator(docs, text_field="text", window_size=1)
        graph_window = op_window.execute(None)

        # Window=1 should produce fewer edges than full co-occurrence
        assert len(graph_window._edges) <= len(graph_full._edges)

    def test_empty_input(self) -> None:
        op = TextToGraphOperator([], text_field="text")
        graph = op.execute(None)
        assert len(graph._vertices) == 0
        assert len(graph._edges) == 0

    def test_edge_weights(self) -> None:
        docs = [
            {"text": "a b"},
            {"text": "a b"},
        ]
        op = TextToGraphOperator(docs, text_field="text")
        graph = op.execute(None)

        for edge in graph._edges.values():
            if edge.label == "co_occurs":
                # "a" and "b" co-occur in 2 documents
                assert edge.properties["weight"] == 2
