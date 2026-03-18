#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import Edge, Vertex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    TraverseOperator,
)
from uqa.graph.pattern import (
    EdgePattern,
    GraphPattern,
    Label,
    VertexPattern,
)
from uqa.graph.posting_list import GraphPayload
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.operators.base import ExecutionContext

# -- Helpers --


def _make_graph_store() -> GraphStore:
    gs = GraphStore()
    gs.create_graph("g1")
    gs.create_graph("g2")
    return gs


def _add_triangle(gs: GraphStore, graph: str, start_vid: int = 1) -> None:
    """Add a triangle (3 vertices, 3 edges) to a named graph."""
    a, b, c = start_vid, start_vid + 1, start_vid + 2
    gs.add_vertex(Vertex(a, "person", {"name": "Alice"}), graph=graph)
    gs.add_vertex(Vertex(b, "person", {"name": "Bob"}), graph=graph)
    gs.add_vertex(Vertex(c, "person", {"name": "Carol"}), graph=graph)
    gs.add_edge(Edge(a * 10, a, b, "knows", {}), graph=graph)
    gs.add_edge(Edge(a * 10 + 1, b, c, "knows", {}), graph=graph)
    gs.add_edge(Edge(a * 10 + 2, c, a, "knows", {}), graph=graph)


# -- Graph lifecycle tests --


def test_create_graph():
    gs = GraphStore()
    gs.create_graph("test")
    assert gs.has_graph("test")
    assert "test" in gs.graph_names()


def test_create_duplicate_graph_raises():
    gs = GraphStore()
    gs.create_graph("test")
    with pytest.raises(ValueError, match="already exists"):
        gs.create_graph("test")


def test_drop_graph():
    gs = GraphStore()
    gs.create_graph("test")
    gs.add_vertex(Vertex(1, "node", {}), graph="test")
    gs.drop_graph("test")
    assert not gs.has_graph("test")
    assert "test" not in gs.graph_names()


def test_drop_nonexistent_graph_raises():
    gs = GraphStore()
    with pytest.raises(ValueError, match="does not exist"):
        gs.drop_graph("nonexistent")


def test_graph_names_sorted():
    gs = GraphStore()
    gs.create_graph("zebra")
    gs.create_graph("apple")
    gs.create_graph("mango")
    assert gs.graph_names() == ["apple", "mango", "zebra"]


# -- Graph isolation tests --


def test_graph_isolation_vertices():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="g1")
    gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="g2")

    assert gs.vertex_ids_in_graph("g1") == {1}
    assert gs.vertex_ids_in_graph("g2") == {2}


def test_graph_isolation_edges():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "person", {}), graph="g1")
    gs.add_vertex(Vertex(2, "person", {}), graph="g1")
    gs.add_vertex(Vertex(3, "person", {}), graph="g2")
    gs.add_vertex(Vertex(4, "person", {}), graph="g2")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g1")
    gs.add_edge(Edge(20, 3, 4, "knows", {}), graph="g2")

    assert gs.out_edge_ids(1, graph="g1") == {10}
    assert gs.out_edge_ids(1, graph="g2") == set()
    assert gs.out_edge_ids(3, graph="g2") == {20}
    assert gs.out_edge_ids(3, graph="g1") == set()


def test_graph_isolation_neighbors():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "person", {}), graph="g1")
    gs.add_vertex(Vertex(2, "person", {}), graph="g1")
    gs.add_vertex(Vertex(1, "person", {}), graph="g2")
    gs.add_vertex(Vertex(3, "person", {}), graph="g2")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g1")
    gs.add_edge(Edge(20, 1, 3, "knows", {}), graph="g2")

    assert gs.neighbors(1, graph="g1") == [2]
    assert gs.neighbors(1, graph="g2") == [3]


def test_graph_isolation_traversal():
    gs = _make_graph_store()
    _add_triangle(gs, "g1", start_vid=1)
    gs.add_vertex(Vertex(10, "person", {}), graph="g2")
    gs.add_vertex(Vertex(11, "person", {}), graph="g2")
    gs.add_edge(Edge(100, 10, 11, "knows", {}), graph="g2")

    ctx = ExecutionContext(graph_store=gs)
    op = TraverseOperator(1, graph="g1", label="knows", max_hops=2)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    # Should find vertices 1, 2, 3 (triangle in g1)
    assert doc_ids == {1, 2, 3}


# -- Cross-graph vertex sharing --


def test_cross_graph_vertex_sharing():
    gs = _make_graph_store()
    v = Vertex(1, "shared", {"name": "shared"})
    gs.add_vertex(v, graph="g1")
    gs.add_vertex(v, graph="g2")

    assert 1 in gs.vertex_ids_in_graph("g1")
    assert 1 in gs.vertex_ids_in_graph("g2")
    assert gs.vertex_graphs(1) == {"g1", "g2"}


def test_drop_graph_preserves_shared_vertex():
    gs = _make_graph_store()
    v = Vertex(1, "shared", {})
    gs.add_vertex(v, graph="g1")
    gs.add_vertex(v, graph="g2")
    gs.drop_graph("g1")

    # Vertex should still exist in g2
    assert gs.get_vertex(1) is not None
    assert 1 in gs.vertex_ids_in_graph("g2")


def test_drop_graph_removes_unshared_vertex():
    gs = GraphStore()
    gs.create_graph("g1")
    gs.add_vertex(Vertex(1, "node", {}), graph="g1")
    gs.drop_graph("g1")

    # Vertex should be gone (no other graph references it)
    assert gs.get_vertex(1) is None


# -- Graph algebra tests --


def test_union_graphs():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g2")
    gs.add_vertex(Vertex(3, "c", {}), graph="g2")

    gs.union_graphs("g1", "g2", "union")
    assert gs.vertex_ids_in_graph("union") == {1, 2, 3}


def test_intersect_graphs():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g2")
    gs.add_vertex(Vertex(3, "c", {}), graph="g2")

    gs.intersect_graphs("g1", "g2", "inter")
    assert gs.vertex_ids_in_graph("inter") == {2}


def test_difference_graphs():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g2")
    gs.add_vertex(Vertex(3, "c", {}), graph="g2")

    gs.difference_graphs("g1", "g2", "diff")
    assert gs.vertex_ids_in_graph("diff") == {1}


def test_copy_graph():
    gs = _make_graph_store()
    _add_triangle(gs, "g1")
    gs.copy_graph("g1", "copy")

    assert gs.vertex_ids_in_graph("copy") == gs.vertex_ids_in_graph("g1")
    assert len(gs.edges_in_graph("copy")) == len(gs.edges_in_graph("g1"))


# -- Graph algebra with edges --


def test_union_graphs_with_edges():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "e1", {}), graph="g1")

    gs.add_vertex(Vertex(2, "b", {}), graph="g2")
    gs.add_vertex(Vertex(3, "c", {}), graph="g2")
    gs.add_edge(Edge(20, 2, 3, "e2", {}), graph="g2")

    gs.union_graphs("g1", "g2", "union")
    edges = gs.edges_in_graph("union")
    edge_ids = {e.edge_id for e in edges}
    assert edge_ids == {10, 20}


# -- Scoped traversal / pattern match / RPQ --


def test_scoped_traverse():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "link", {}), graph="g1")

    ctx = ExecutionContext(graph_store=gs)
    op = TraverseOperator(1, graph="g1", label="link", max_hops=1)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    assert 2 in doc_ids


def test_scoped_pattern_match():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="g1")
    gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g1")

    pattern = GraphPattern(
        vertex_patterns=[
            VertexPattern("a"),
            VertexPattern("b"),
        ],
        edge_patterns=[
            EdgePattern("a", "b", "knows"),
        ],
    )
    ctx = ExecutionContext(graph_store=gs)
    op = PatternMatchOperator(pattern, graph="g1")
    result = op.execute(ctx)
    assert len(result) == 1
    assert result.entries[0].payload.fields["a"] == 1
    assert result.entries[0].payload.fields["b"] == 2


def test_scoped_rpq():
    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_vertex(Vertex(3, "c", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g1")
    gs.add_edge(Edge(11, 2, 3, "knows", {}), graph="g1")

    ctx = ExecutionContext(graph_store=gs)
    op = RegularPathQueryOperator(Label("knows"), graph="g1", start_vertex=1)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    assert 2 in doc_ids


# -- Statistics (per-graph) --


def test_degree_distribution():
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")
    gs.add_edge(Edge(11, 1, 3, "e", {}), graph="g")

    dist = gs.degree_distribution("g")
    assert dist[0] == 2  # vertices 2 and 3 have degree 0
    assert dist[2] == 1  # vertex 1 has degree 2


def test_label_degree():
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g")
    gs.add_edge(Edge(11, 1, 3, "knows", {}), graph="g")

    # vertex 1 has 2 "knows" edges, so avg = 2/1 = 2.0
    assert gs.label_degree("knows", "g") == 2.0


def test_vertex_label_counts():
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "person", {}), graph="g")
    gs.add_vertex(Vertex(2, "person", {}), graph="g")
    gs.add_vertex(Vertex(3, "company", {}), graph="g")

    counts = gs.vertex_label_counts("g")
    assert counts["person"] == 2
    assert counts["company"] == 1


# -- GraphPayload graph_name field --


def test_graph_payload_has_graph_name():
    gp = GraphPayload(
        subgraph_vertices=frozenset({1, 2}),
        subgraph_edges=frozenset(),
        graph_name="my_graph",
    )
    assert gp.graph_name == "my_graph"


def test_graph_payload_default_graph_name():
    gp = GraphPayload()
    assert gp.graph_name == ""


# -- Remove vertex/edge --


def test_remove_vertex_from_graph():
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")

    gs.remove_vertex(1, graph="g")
    assert gs.vertex_ids_in_graph("g") == {2}
    # Edge should also be removed from partition
    assert len(gs.edges_in_graph("g")) == 0


def test_remove_edge_from_graph():
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")

    gs.remove_edge(10, graph="g")
    assert len(gs.edges_in_graph("g")) == 0
    # Vertices should still exist
    assert gs.vertex_ids_in_graph("g") == {1, 2}


# -- Clear --


def test_clear_removes_all():
    gs = _make_graph_store()
    _add_triangle(gs, "g1")
    _add_triangle(gs, "g2", start_vid=10)
    gs.clear()

    assert gs.graph_names() == []
    assert gs.vertices == {}
    assert gs.edges == {}


# -- Edge case: require graph for queries --


def test_query_nonexistent_graph_raises():
    gs = GraphStore()
    with pytest.raises(ValueError, match="does not exist"):
        gs.neighbors(1, graph="nonexistent")


def test_add_to_nonexistent_graph_auto_creates():
    gs = GraphStore()
    # _ensure_graph auto-creates when adding
    gs.add_vertex(Vertex(1, "a", {}), graph="auto")
    assert gs.has_graph("auto")
    assert 1 in gs.vertex_ids_in_graph("auto")


# -- SQLite persistence tests --


def test_sqlite_named_graph_persistence(tmp_path):
    """Named graphs survive close and reopen via SQLiteGraphStore."""
    from uqa.storage.catalog import Catalog
    from uqa.storage.sqlite_graph_store import SQLiteGraphStore

    db = str(tmp_path / "graph_persist.db")

    cat1 = Catalog(db)
    store1 = SQLiteGraphStore(cat1.conn)
    store1.create_graph("social")
    store1.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="social")
    store1.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="social")
    store1.add_edge(Edge(10, 1, 2, "knows", {}), graph="social")
    cat1.close()

    cat2 = Catalog(db)
    store2 = SQLiteGraphStore(cat2.conn)
    assert store2.has_graph("social")
    assert store2.vertex_ids_in_graph("social") == {1, 2}
    assert len(store2.edges_in_graph("social")) == 1
    assert store2.neighbors(1, graph="social") == [2]
    cat2.close()


def test_sqlite_graph_catalog_table(tmp_path):
    """Graph catalog table tracks created/dropped graphs."""
    from uqa.storage.catalog import Catalog
    from uqa.storage.sqlite_graph_store import SQLiteGraphStore

    db = str(tmp_path / "catalog.db")
    cat = Catalog(db)
    store = SQLiteGraphStore(cat.conn)

    store.create_graph("g1")
    store.create_graph("g2")
    assert sorted(store.graph_names()) == ["g1", "g2"]

    store.drop_graph("g1")
    assert store.graph_names() == ["g2"]

    # Verify catalog table in SQLite
    rows = cat.conn.execute(
        f'SELECT graph_name FROM "{store._catalog_table}"'
    ).fetchall()
    assert [r[0] for r in rows] == ["g2"]
    cat.close()


def test_sqlite_multiple_graphs_isolation(tmp_path):
    """Multiple named graphs in SQLite are fully isolated."""
    from uqa.storage.catalog import Catalog
    from uqa.storage.sqlite_graph_store import SQLiteGraphStore

    db = str(tmp_path / "multi.db")
    cat = Catalog(db)
    store = SQLiteGraphStore(cat.conn)

    store.create_graph("g1")
    store.create_graph("g2")
    store.add_vertex(Vertex(1, "a", {}), graph="g1")
    store.add_vertex(Vertex(2, "b", {}), graph="g2")

    assert store.vertex_ids_in_graph("g1") == {1}
    assert store.vertex_ids_in_graph("g2") == {2}
    cat.close()


# -- Scoped index building tests --


def test_scoped_label_index_building():
    """LabelIndex.build respects graph scope."""
    from uqa.graph.index import LabelIndex

    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g1")

    gs.add_vertex(Vertex(3, "c", {}), graph="g2")
    gs.add_vertex(Vertex(4, "d", {}), graph="g2")
    gs.add_edge(Edge(20, 3, 4, "works_with", {}), graph="g2")

    idx1 = LabelIndex.build(gs, graph_name="g1")
    idx2 = LabelIndex.build(gs, graph_name="g2")

    assert idx1.labels() == ["knows"]
    assert idx2.labels() == ["works_with"]


def test_scoped_path_index_building():
    """PathIndex.build respects graph scope."""
    from uqa.graph.index import PathIndex

    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_vertex(Vertex(3, "c", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "x", {}), graph="g1")
    gs.add_edge(Edge(11, 2, 3, "y", {}), graph="g1")

    idx = PathIndex.build(gs, [["x", "y"]], graph_name="g1")
    pairs = idx.lookup(["x", "y"])
    assert pairs is not None
    assert (1, 3) in pairs


def test_scoped_neighborhood_index_building():
    """NeighborhoodIndex.build respects graph scope."""
    from uqa.graph.index import NeighborhoodIndex

    gs = _make_graph_store()
    gs.add_vertex(Vertex(1, "a", {}), graph="g1")
    gs.add_vertex(Vertex(2, "b", {}), graph="g1")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g1")

    idx = NeighborhoodIndex.build(gs, max_hops=1, graph_name="g1")
    assert 2 in idx.neighbors(1, 1)
    # Vertex 3 is in g2, not in g1's index
    assert not idx.has_vertex(3)
