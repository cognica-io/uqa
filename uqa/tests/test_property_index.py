#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.graph.index import EdgePropertyIndex, VertexPropertyIndex
from uqa.graph.store import GraphStore


def _make_store() -> GraphStore:
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "person", {"name": "Alice", "age": 30}), graph="g")
    gs.add_vertex(Vertex(2, "person", {"name": "Bob", "age": 25}), graph="g")
    gs.add_vertex(Vertex(3, "person", {"name": "Carol", "age": 35}), graph="g")
    gs.add_vertex(Vertex(4, "company", {"name": "Acme", "size": 100}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "knows", {"since": 2020, "weight": 0.8}), graph="g")
    gs.add_edge(Edge(11, 2, 3, "knows", {"since": 2021, "weight": 0.6}), graph="g")
    gs.add_edge(Edge(12, 1, 4, "works_at", {"since": 2019, "weight": 1.0}), graph="g")
    return gs


# -- VertexPropertyIndex tests --


def test_vertex_property_index_build():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["name", "age"])
    assert idx.has_property("name")
    assert idx.has_property("age")
    assert not idx.has_property("nonexistent")


def test_vertex_property_eq_lookup():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["name"])
    assert idx.lookup_eq("name", "Alice") == [1]
    assert idx.lookup_eq("name", "Bob") == [2]
    assert idx.lookup_eq("name", "Nonexistent") == []


def test_vertex_property_range_lookup():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["age"])
    # Range [25, 30] should include Bob(25) and Alice(30)
    result = idx.lookup_range("age", 25, 30)
    assert sorted(result) == [1, 2]


def test_vertex_property_range_narrow():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["age"])
    # Narrow range [31, 40] should include only Carol(35)
    result = idx.lookup_range("age", 31, 40)
    assert result == [3]


def test_vertex_property_range_empty():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["age"])
    result = idx.lookup_range("age", 100, 200)
    assert result == []


def test_vertex_property_multiple_properties():
    gs = _make_store()
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["name", "age"])
    assert idx.lookup_eq("name", "Carol") == [3]
    assert idx.lookup_range("age", 30, 35) == [1, 3]  # sorted by (val, vid)


def test_vertex_property_missing_values():
    gs = _make_store()
    # "size" only exists on vertex 4
    idx = VertexPropertyIndex.build(gs, graph="g", properties=["size"])
    assert idx.lookup_eq("size", 100) == [4]
    assert idx.lookup_eq("size", 200) == []


# -- EdgePropertyIndex tests --


def test_edge_property_index_build():
    gs = _make_store()
    idx = EdgePropertyIndex.build(gs, graph="g", properties=["since", "weight"])
    assert idx.has_property("since")
    assert idx.has_property("weight")


def test_edge_property_eq_lookup():
    gs = _make_store()
    idx = EdgePropertyIndex.build(gs, graph="g", properties=["since"])
    assert idx.lookup_eq("since", 2020) == [10]
    assert idx.lookup_eq("since", 2021) == [11]
    assert idx.lookup_eq("since", 9999) == []


def test_edge_property_range_lookup():
    gs = _make_store()
    idx = EdgePropertyIndex.build(gs, graph="g", properties=["weight"])
    # Range [0.7, 1.0] should include edges 10(0.8) and 12(1.0)
    result = idx.lookup_range("weight", 0.7, 1.0)
    assert sorted(result) == [10, 12]


def test_edge_property_range_all():
    gs = _make_store()
    idx = EdgePropertyIndex.build(gs, graph="g", properties=["since"])
    result = idx.lookup_range("since", 2019, 2021)
    assert sorted(result) == [10, 11, 12]


def test_edge_property_empty_graph():
    gs = GraphStore()
    gs.create_graph("empty")
    idx = EdgePropertyIndex.build(gs, graph="empty", properties=["weight"])
    assert idx.lookup_eq("weight", 1.0) == []
    assert idx.lookup_range("weight", 0, 10) == []


# -- Graph isolation --


def test_property_index_respects_graph_scope():
    gs = GraphStore()
    gs.create_graph("g1")
    gs.create_graph("g2")
    gs.add_vertex(Vertex(1, "a", {"val": 10}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {"val": 20}), graph="g2")

    idx1 = VertexPropertyIndex.build(gs, graph="g1", properties=["val"])
    idx2 = VertexPropertyIndex.build(gs, graph="g2", properties=["val"])

    assert idx1.lookup_eq("val", 10) == [1]
    assert idx1.lookup_eq("val", 20) == []
    assert idx2.lookup_eq("val", 20) == [2]
    assert idx2.lookup_eq("val", 10) == []
