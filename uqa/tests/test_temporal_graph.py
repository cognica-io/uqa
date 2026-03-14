#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import Edge, IndexStats, Vertex
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
from uqa.graph.store import GraphStore
from uqa.graph.temporal_filter import TemporalFilter
from uqa.graph.temporal_pattern_match import TemporalPatternMatchOperator
from uqa.graph.temporal_traverse import TemporalTraverseOperator


class _ExecutionContext:
    """Minimal execution context for testing."""

    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store


@pytest.fixture
def temporal_graph() -> GraphStore:
    """Graph with temporal edges for testing.

    Vertices: A(1), B(2), C(3), D(4), E(5)
    Edges with valid_from/valid_to:
      1->2 knows  [100, 200]
      1->3 knows  [150, 300]
      2->3 knows  [50, 120]
      2->4 works  [200, 400]
      3->4 knows  [100, 250]
      3->5 works  (no temporal props -- always valid)
      4->5 knows  [300, 500]
    """
    store = GraphStore()
    vertices = [
        Vertex(1, "person", {"name": "Alice"}),
        Vertex(2, "person", {"name": "Bob"}),
        Vertex(3, "person", {"name": "Charlie"}),
        Vertex(4, "person", {"name": "Diana"}),
        Vertex(5, "person", {"name": "Eve"}),
    ]
    edges = [
        Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
        Edge(2, 1, 3, "knows", {"valid_from": 150, "valid_to": 300}),
        Edge(3, 2, 3, "knows", {"valid_from": 50, "valid_to": 120}),
        Edge(4, 2, 4, "works_with", {"valid_from": 200, "valid_to": 400}),
        Edge(5, 3, 4, "knows", {"valid_from": 100, "valid_to": 250}),
        Edge(6, 3, 5, "works_with", {}),
        Edge(7, 4, 5, "knows", {"valid_from": 300, "valid_to": 500}),
    ]
    for v in vertices:
        store.add_vertex(v)
    for e in edges:
        store.add_edge(e)
    return store


@pytest.fixture
def temporal_ctx(temporal_graph: GraphStore) -> _ExecutionContext:
    return _ExecutionContext(temporal_graph)


# -- TemporalFilter tests --


class TestTemporalFilter:
    def test_timestamp_within_range(self) -> None:
        tf = TemporalFilter(timestamp=150.0)
        props = {"valid_from": 100, "valid_to": 200}
        assert tf.is_valid(props) is True

    def test_timestamp_outside_range(self) -> None:
        tf = TemporalFilter(timestamp=250.0)
        props = {"valid_from": 100, "valid_to": 200}
        assert tf.is_valid(props) is False

    def test_timestamp_at_boundary(self) -> None:
        tf = TemporalFilter(timestamp=100.0)
        props = {"valid_from": 100, "valid_to": 200}
        assert tf.is_valid(props) is True

        tf2 = TemporalFilter(timestamp=200.0)
        assert tf2.is_valid(props) is True

    def test_time_range_overlap(self) -> None:
        tf = TemporalFilter(time_range=(90.0, 150.0))
        props = {"valid_from": 100, "valid_to": 200}
        assert tf.is_valid(props) is True

    def test_time_range_no_overlap(self) -> None:
        tf = TemporalFilter(time_range=(210.0, 300.0))
        props = {"valid_from": 100, "valid_to": 200}
        assert tf.is_valid(props) is False

    def test_no_temporal_properties(self) -> None:
        """Edges without temporal properties are always valid."""
        tf = TemporalFilter(timestamp=150.0)
        assert tf.is_valid({}) is True
        assert tf.is_valid({"other": "value"}) is True

    def test_partial_temporal_properties_valid_from_only(self) -> None:
        """Edge with only valid_from means valid from that point onward."""
        tf = TemporalFilter(timestamp=200.0)
        props = {"valid_from": 100}
        assert tf.is_valid(props) is True

        tf2 = TemporalFilter(timestamp=50.0)
        assert tf2.is_valid(props) is False

    def test_partial_temporal_properties_valid_to_only(self) -> None:
        """Edge with only valid_to means valid up to that point."""
        tf = TemporalFilter(timestamp=100.0)
        props = {"valid_to": 200}
        assert tf.is_valid(props) is True

        tf2 = TemporalFilter(timestamp=250.0)
        assert tf2.is_valid(props) is False

    def test_no_filter_accepts_all(self) -> None:
        """A filter with neither timestamp nor time_range accepts everything."""
        tf = TemporalFilter()
        assert tf.is_valid({"valid_from": 100, "valid_to": 200}) is True
        assert tf.is_valid({}) is True

    def test_both_timestamp_and_range_raises(self) -> None:
        with pytest.raises(ValueError, match="Specify either"):
            TemporalFilter(timestamp=100.0, time_range=(50.0, 150.0))


# -- TemporalTraverseOperator tests --


class TestTemporalTraverse:
    def test_traverse_at_timestamp(self, temporal_ctx: _ExecutionContext) -> None:
        """At t=110, from vertex 1: edge 1 (1->2, [100,200]) is valid.
        Edge 2 (1->3, [150,300]) is NOT valid (110 < 150).
        So from vertex 1, only vertex 2 is reachable in 1 hop.
        """
        tf = TemporalFilter(timestamp=110.0)
        op = TemporalTraverseOperator(1, "knows", 1, tf)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 not in reached

    def test_traverse_at_later_timestamp(
        self, temporal_ctx: _ExecutionContext
    ) -> None:
        """At t=160, from vertex 1: both edge 1 (1->2, [100,200]) and
        edge 2 (1->3, [150,300]) are valid. So vertices 2 and 3 are
        reachable in 1 hop.
        """
        tf = TemporalFilter(timestamp=160.0)
        op = TemporalTraverseOperator(1, "knows", 1, tf)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 in reached

    def test_traverse_multi_hop(self, temporal_ctx: _ExecutionContext) -> None:
        """At t=110, from vertex 1 with 2 hops (knows):
        Hop 1: 1->2 valid (edge 1, [100,200]).  1->3 invalid (edge 2, [150,300]).
        Hop 2: 2->3 valid (edge 3, [50,120]).
        So vertices 2 and 3 should be reachable.
        """
        tf = TemporalFilter(timestamp=110.0)
        op = TemporalTraverseOperator(1, "knows", 2, tf)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 in reached

    def test_traverse_with_time_range(
        self, temporal_ctx: _ExecutionContext
    ) -> None:
        """Range [90, 110]: from vertex 1 with "knows":
        Edge 1 (1->2, [100,200]): overlaps [90,110]? 100<=110 and 200>=90 -> yes
        Edge 2 (1->3, [150,300]): overlaps [90,110]? 150<=110? no
        Only vertex 2 reachable.
        """
        tf = TemporalFilter(time_range=(90.0, 110.0))
        op = TemporalTraverseOperator(1, "knows", 1, tf)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 not in reached

    def test_traverse_no_filter(self, temporal_ctx: _ExecutionContext) -> None:
        """Without a temporal filter, all edges are traversable."""
        op = TemporalTraverseOperator(1, "knows", 1, None)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 in reached

    def test_traverse_all_labels(self, temporal_ctx: _ExecutionContext) -> None:
        """Traverse all edge labels at t=250. From vertex 3:
        Edge 5 (3->4, knows, [100,250]): 100<=250<=250 -> valid
        Edge 6 (3->5, works_with, no temporal): always valid
        Both 4 and 5 reachable.
        """
        tf = TemporalFilter(timestamp=250.0)
        op = TemporalTraverseOperator(3, None, 1, tf)
        result = op.execute(temporal_ctx)
        reached = {e.doc_id for e in result}
        assert 4 in reached
        assert 5 in reached

    def test_cost_estimate(self) -> None:
        stats = IndexStats(total_docs=100)
        tf = TemporalFilter(timestamp=100.0)
        op = TemporalTraverseOperator(1, "knows", 1, tf)
        cost = op.cost_estimate(stats)
        assert cost == pytest.approx(10.0)


# -- TemporalPatternMatchOperator tests --


class TestTemporalPatternMatch:
    def test_pattern_match_at_timestamp(
        self, temporal_ctx: _ExecutionContext
    ) -> None:
        """Find (a)-[:knows]->(b) at t=110.
        Valid knows edges at t=110:
          1->2 [100,200]: yes
          1->3 [150,300]: no (110<150)
          2->3 [50,120]:  yes
          3->4 [100,250]: yes
          4->5 [300,500]: no (110<300)
        So valid patterns: (1,2), (2,3), (3,4)
        """
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "knows")],
        )
        tf = TemporalFilter(timestamp=110.0)
        op = TemporalPatternMatchOperator(pattern, tf)
        result = op.execute(temporal_ctx)
        assignments = [
            (e.payload.fields["a"], e.payload.fields["b"]) for e in result
        ]
        assert (1, 2) in assignments
        assert (2, 3) in assignments
        assert (3, 4) in assignments
        assert (1, 3) not in assignments
        assert (4, 5) not in assignments

    def test_pattern_match_no_filter(
        self, temporal_ctx: _ExecutionContext
    ) -> None:
        """Without temporal filter, all knows edges participate."""
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "knows")],
        )
        op = TemporalPatternMatchOperator(pattern, None)
        result = op.execute(temporal_ctx)
        assignments = [
            (e.payload.fields["a"], e.payload.fields["b"]) for e in result
        ]
        # All 5 knows edges should be found
        assert (1, 2) in assignments
        assert (1, 3) in assignments
        assert (2, 3) in assignments
        assert (3, 4) in assignments
        assert (4, 5) in assignments

    def test_pattern_match_with_time_range(
        self, temporal_ctx: _ExecutionContext
    ) -> None:
        """Range [200, 350]: valid knows edges:
          1->2 [100,200]: 100<=350 and 200>=200 -> yes
          1->3 [150,300]: 150<=350 and 300>=200 -> yes
          2->3 [50,120]:  50<=350 and 120>=200 -> no
          3->4 [100,250]: 100<=350 and 250>=200 -> yes
          4->5 [300,500]: 300<=350 and 500>=200 -> yes
        """
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "knows")],
        )
        tf = TemporalFilter(time_range=(200.0, 350.0))
        op = TemporalPatternMatchOperator(pattern, tf)
        result = op.execute(temporal_ctx)
        assignments = [
            (e.payload.fields["a"], e.payload.fields["b"]) for e in result
        ]
        assert (1, 2) in assignments
        assert (1, 3) in assignments
        assert (2, 3) not in assignments
        assert (3, 4) in assignments
        assert (4, 5) in assignments

    def test_cost_estimate(self) -> None:
        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
            edge_patterns=[EdgePattern("a", "b", "knows")],
        )
        stats = IndexStats(total_docs=10)
        op = TemporalPatternMatchOperator(pattern, None)
        cost = op.cost_estimate(stats)
        assert cost == pytest.approx(100.0)


# -- SQL temporal_traverse tests --


class TestTemporalTraverseSQL:
    def test_temporal_traverse_from_clause(self) -> None:
        """Test temporal_traverse() as a FROM-clause function via SQL."""
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE tg (id INTEGER, name TEXT)")
        engine.sql("INSERT INTO tg VALUES (1, 'Alice')")

        engine.add_graph_vertex(
            Vertex(1, "person", {"name": "Alice"}), table="tg"
        )
        engine.add_graph_vertex(
            Vertex(2, "person", {"name": "Bob"}), table="tg"
        )
        engine.add_graph_vertex(
            Vertex(3, "person", {"name": "Charlie"}), table="tg"
        )
        engine.add_graph_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
            table="tg",
        )
        engine.add_graph_edge(
            Edge(2, 1, 3, "knows", {"valid_from": 150, "valid_to": 300}),
            table="tg",
        )

        # At t=110, only 1->2 is valid
        result = engine.sql(
            "SELECT * FROM temporal_traverse(1, 'knows', 1, 110, 'tg')"
        )
        doc_ids = {row["_doc_id"] for row in result.rows}
        assert 2 in doc_ids
        assert 3 not in doc_ids

    def test_temporal_traverse_range_from_clause(self) -> None:
        """Test temporal_traverse() with range as a FROM-clause function."""
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE tg2 (id INTEGER, name TEXT)")
        engine.sql("INSERT INTO tg2 VALUES (1, 'Alice')")

        engine.add_graph_vertex(
            Vertex(1, "person", {"name": "Alice"}), table="tg2"
        )
        engine.add_graph_vertex(
            Vertex(2, "person", {"name": "Bob"}), table="tg2"
        )
        engine.add_graph_vertex(
            Vertex(3, "person", {"name": "Charlie"}), table="tg2"
        )
        engine.add_graph_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
            table="tg2",
        )
        engine.add_graph_edge(
            Edge(2, 1, 3, "knows", {"valid_from": 150, "valid_to": 300}),
            table="tg2",
        )

        # Range [160, 250]: both edges overlap
        result = engine.sql(
            "SELECT * FROM temporal_traverse(1, 'knows', 1, 160, 250, 'tg2')"
        )
        doc_ids = {row["_doc_id"] for row in result.rows}
        assert 2 in doc_ids
        assert 3 in doc_ids


# -- QueryBuilder temporal_traverse tests --


class TestTemporalTraverseQueryBuilder:
    def test_query_builder_temporal_traverse(self) -> None:
        """Test temporal_traverse via QueryBuilder fluent API."""
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE qbt (id INTEGER)")
        engine.sql("INSERT INTO qbt VALUES (1)")

        engine.add_graph_vertex(
            Vertex(1, "person", {"name": "Alice"}), table="qbt"
        )
        engine.add_graph_vertex(
            Vertex(2, "person", {"name": "Bob"}), table="qbt"
        )
        engine.add_graph_vertex(
            Vertex(3, "person", {"name": "Charlie"}), table="qbt"
        )
        engine.add_graph_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
            table="qbt",
        )
        engine.add_graph_edge(
            Edge(2, 1, 3, "knows", {"valid_from": 150, "valid_to": 300}),
            table="qbt",
        )

        qb = engine.query("qbt")
        result = qb.temporal_traverse(1, "knows", 1, timestamp=110.0).execute()
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 not in reached

    def test_query_builder_temporal_traverse_range(self) -> None:
        """Test temporal_traverse via QueryBuilder with time_range."""
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE qbt2 (id INTEGER)")
        engine.sql("INSERT INTO qbt2 VALUES (1)")

        engine.add_graph_vertex(
            Vertex(1, "person", {"name": "Alice"}), table="qbt2"
        )
        engine.add_graph_vertex(
            Vertex(2, "person", {"name": "Bob"}), table="qbt2"
        )
        engine.add_graph_vertex(
            Vertex(3, "person", {"name": "Charlie"}), table="qbt2"
        )
        engine.add_graph_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
            table="qbt2",
        )
        engine.add_graph_edge(
            Edge(2, 1, 3, "knows", {"valid_from": 150, "valid_to": 300}),
            table="qbt2",
        )

        qb = engine.query("qbt2")
        result = qb.temporal_traverse(
            1, "knows", 1, time_range=(160.0, 250.0)
        ).execute()
        reached = {e.doc_id for e in result}
        assert 2 in reached
        assert 3 in reached
