#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.delta import GraphDelta
from uqa.graph.store import GraphStore
from uqa.graph.versioned_store import VersionedGraphStore

_GRAPH_NAME = "test"


class TestGraphDelta:
    """Tests for GraphDelta (Paper 2, Section 9.3)."""

    def test_empty_delta(self) -> None:
        delta = GraphDelta()
        assert delta.is_empty()
        assert len(delta) == 0

    def test_add_vertex_op(self) -> None:
        delta = GraphDelta()
        v = Vertex(1, "person", {"name": "Alice"})
        delta.add_vertex(v)
        assert not delta.is_empty()
        assert len(delta) == 1

    def test_remove_vertex_op(self) -> None:
        delta = GraphDelta()
        delta.remove_vertex(1)
        assert len(delta) == 1

    def test_add_edge_op(self) -> None:
        delta = GraphDelta()
        e = Edge(1, 1, 2, "knows")
        delta.add_edge(e)
        assert len(delta) == 1

    def test_remove_edge_op(self) -> None:
        delta = GraphDelta()
        delta.remove_edge(1)
        assert len(delta) == 1

    def test_affected_vertex_ids(self) -> None:
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person"))
        delta.add_edge(Edge(1, 2, 3, "knows"))
        ids = delta.affected_vertex_ids()
        assert 1 in ids
        assert 2 in ids
        assert 3 in ids

    def test_affected_edge_labels(self) -> None:
        delta = GraphDelta()
        delta.add_edge(Edge(1, 1, 2, "knows"))
        delta.add_edge(Edge(2, 2, 3, "works_with"))
        labels = delta.affected_edge_labels()
        assert "knows" in labels
        assert "works_with" in labels

    def test_multiple_ops(self) -> None:
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person"))
        delta.add_vertex(Vertex(2, "person"))
        delta.add_edge(Edge(1, 1, 2, "knows"))
        assert len(delta) == 3


class TestVersionedGraphStore:
    """Tests for VersionedGraphStore (Paper 2, Section 9.3)."""

    def test_initial_version(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        assert vg.version == 0

    def test_apply_increments_version(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        version = vg.apply(delta)
        assert version == 1
        assert vg.version == 1

    def test_apply_adds_vertex(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        vg.apply(delta)
        assert g.get_vertex(1) is not None
        assert g.get_vertex(1).properties["name"] == "Alice"

    def test_apply_adds_edge(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        g.add_vertex(Vertex(1, "person"), graph=_GRAPH_NAME)
        g.add_vertex(Vertex(2, "person"), graph=_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.add_edge(Edge(1, 1, 2, "knows"))
        vg.apply(delta)
        assert g.get_edge(1) is not None

    def test_apply_removes_vertex(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        g.add_vertex(Vertex(1, "person"), graph=_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.remove_vertex(1)
        vg.apply(delta)
        assert g.get_vertex(1) is None

    def test_apply_removes_edge(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        g.add_vertex(Vertex(1, "person"), graph=_GRAPH_NAME)
        g.add_vertex(Vertex(2, "person"), graph=_GRAPH_NAME)
        g.add_edge(Edge(1, 1, 2, "knows"), graph=_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.remove_edge(1)
        vg.apply(delta)
        assert g.get_edge(1) is None

    def test_rollback_to_initial(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        vg.apply(delta)
        assert g.get_vertex(1) is not None
        vg.rollback(0)
        assert vg.version == 0
        assert g.get_vertex(1) is None

    def test_rollback_partial(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        d1 = GraphDelta()
        d1.add_vertex(Vertex(1, "person"))
        vg.apply(d1)
        d2 = GraphDelta()
        d2.add_vertex(Vertex(2, "person"))
        vg.apply(d2)
        assert vg.version == 2
        vg.rollback(1)
        assert vg.version == 1
        assert g.get_vertex(1) is not None
        assert g.get_vertex(2) is None

    def test_rollback_edge_removal(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        g.add_vertex(Vertex(1, "person"), graph=_GRAPH_NAME)
        g.add_vertex(Vertex(2, "person"), graph=_GRAPH_NAME)
        g.add_edge(Edge(1, 1, 2, "knows"), graph=_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        delta = GraphDelta()
        delta.remove_edge(1)
        vg.apply(delta)
        assert g.get_edge(1) is None
        vg.rollback(0)
        assert g.get_edge(1) is not None

    def test_rollback_invalid_version(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        with pytest.raises(ValueError, match="Cannot rollback"):
            vg.rollback(5)

    def test_multiple_deltas(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        for i in range(1, 6):
            d = GraphDelta()
            d.add_vertex(Vertex(i, "person"))
            vg.apply(d)
        assert vg.version == 5
        assert len(g._vertices) == 5

    def test_invalidation_callback(self) -> None:
        g = GraphStore()
        g.create_graph(_GRAPH_NAME)
        g.add_vertex(Vertex(1, "person"), graph=_GRAPH_NAME)
        g.add_vertex(Vertex(2, "person"), graph=_GRAPH_NAME)
        vg = VersionedGraphStore(g, graph_name=_GRAPH_NAME)
        invalidated: list[set[str]] = []
        vg.on_invalidate(lambda labels: invalidated.append(labels))
        delta = GraphDelta()
        delta.add_edge(Edge(1, 1, 2, "knows"))
        vg.apply(delta)
        assert len(invalidated) == 1
        assert "knows" in invalidated[0]


class TestEngineGraphDelta:
    """Tests for Engine.apply_graph_delta()."""

    def test_apply_delta(self) -> None:
        e = Engine()
        e.create_graph("social")
        delta = GraphDelta()
        delta.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        delta.add_vertex(Vertex(2, "person", {"name": "Bob"}))
        delta.add_edge(Edge(1, 1, 2, "knows"))
        version = e.apply_graph_delta("social", delta)
        assert version == 1

    def test_apply_delta_nonexistent_graph(self) -> None:
        e = Engine()
        delta = GraphDelta()
        with pytest.raises(ValueError, match="does not exist"):
            e.apply_graph_delta("nonexistent", delta)

    def test_apply_delta_invalidates_path_index(self) -> None:
        e = Engine()
        g = e.create_graph("social")
        g.add_vertex(Vertex(1, "person"), graph="social")
        g.add_vertex(Vertex(2, "person"), graph="social")
        g.add_edge(Edge(1, 1, 2, "knows"), graph="social")
        e.build_path_index("social", [["knows"]])
        assert e.get_path_index("social") is not None

        delta = GraphDelta()
        delta.add_edge(Edge(2, 2, 1, "knows"))
        e.apply_graph_delta("social", delta)
        # Path index should be invalidated
        assert e.get_path_index("social") is None

    def test_apply_delta_no_invalidation_for_unrelated_labels(self) -> None:
        e = Engine()
        g = e.create_graph("social")
        g.add_vertex(Vertex(1, "person"), graph="social")
        g.add_vertex(Vertex(2, "person"), graph="social")
        g.add_edge(Edge(1, 1, 2, "knows"), graph="social")
        e.build_path_index("social", [["knows"]])

        delta = GraphDelta()
        delta.add_vertex(Vertex(3, "person"))
        e.apply_graph_delta("social", delta)
        # Path index should NOT be invalidated (no edge label changes)
        assert e.get_path_index("social") is not None

    def test_multiple_deltas(self) -> None:
        e = Engine()
        e.create_graph("social")
        d1 = GraphDelta()
        d1.add_vertex(Vertex(1, "person"))
        v1 = e.apply_graph_delta("social", d1)
        d2 = GraphDelta()
        d2.add_vertex(Vertex(2, "person"))
        v2 = e.apply_graph_delta("social", d2)
        assert v1 == 1
        assert v2 == 2
