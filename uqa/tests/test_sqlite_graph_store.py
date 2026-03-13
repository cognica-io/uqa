#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Section 3.2.4: Persistent Graph Index (SQLiteGraphStore).

Covers:
- SQLite adjacency index creation
- Write-through persistence for vertices and edges
- SQLite-backed neighbors() queries
- edges_by_label() queries
- Persistence across reconnection
- Engine integration (graph survives close/reopen)
- Operator compatibility (TraverseOperator, PatternMatchOperator, RPQ)
"""

from __future__ import annotations

import sqlite3

from uqa.core.types import Edge, Vertex
from uqa.storage.catalog import Catalog
from uqa.storage.sqlite_graph_store import SQLiteGraphStore

# -- Helpers ---------------------------------------------------------------


def _make_catalog(tmp_path) -> Catalog:
    db = str(tmp_path / "test.db")
    return Catalog(db)


def _sample_vertices() -> list[Vertex]:
    return [
        Vertex(1, "", {"name": "Alice", "age": 30}),
        Vertex(2, "", {"name": "Bob", "age": 25}),
        Vertex(3, "", {"name": "Charlie", "age": 35}),
    ]


def _sample_edges() -> list[Edge]:
    return [
        Edge(1, 1, 2, "knows", {"since": 2020}),
        Edge(2, 1, 3, "knows", {"since": 2019}),
        Edge(3, 2, 3, "works_with", {"project": "alpha"}),
    ]


def _populate(store: SQLiteGraphStore) -> None:
    for v in _sample_vertices():
        store.add_vertex(v)
    for e in _sample_edges():
        store.add_edge(e)


# ======================================================================
# Adjacency Index Creation
# ======================================================================


class TestAdjacencyIndexes:
    def test_indexes_exist_after_catalog_init(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        rows = catalog.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE '_graph_edges_%'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        assert "_graph_edges_out" in index_names
        assert "_graph_edges_in" in index_names
        assert "_graph_edges_label" in index_names
        catalog.close()

    def test_indexes_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat1 = Catalog(db)
        cat1.close()

        conn2 = sqlite3.connect(db)
        rows = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE '_graph_edges_%'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        assert "_graph_edges_out" in index_names
        assert "_graph_edges_in" in index_names
        assert "_graph_edges_label" in index_names
        conn2.close()


# ======================================================================
# Write-Through Persistence
# ======================================================================


class TestWriteThrough:
    def test_add_vertex_persisted(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        store.add_vertex(Vertex(1, "", {"name": "Alice"}))

        row = catalog.conn.execute(
            "SELECT vertex_id, properties_json FROM _graph_vertices WHERE vertex_id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        catalog.close()

    def test_add_edge_persisted(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        store.add_vertex(Vertex(1, "", {"name": "Alice"}))
        store.add_vertex(Vertex(2, "", {"name": "Bob"}))
        store.add_edge(Edge(1, 1, 2, "knows", {"since": 2020}))

        row = catalog.conn.execute(
            "SELECT source_id, target_id, label FROM _graph_edges WHERE edge_id = 1"
        ).fetchone()
        assert row == (1, 2, "knows")
        catalog.close()

    def test_in_memory_and_sqlite_consistent(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        # In-memory
        assert len(store._vertices) == 3
        assert len(store._edges) == 3

        # SQLite
        v_count = catalog.conn.execute(
            "SELECT COUNT(*) FROM _graph_vertices"
        ).fetchone()[0]
        e_count = catalog.conn.execute("SELECT COUNT(*) FROM _graph_edges").fetchone()[
            0
        ]
        assert v_count == 3
        assert e_count == 3
        catalog.close()


# ======================================================================
# SQLite-backed neighbors() Queries
# ======================================================================


class TestNeighborsSQL:
    def test_neighbors_out(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        neighbors = store.neighbors(1, direction="out")
        assert set(neighbors) == {2, 3}
        catalog.close()

    def test_neighbors_out_with_label(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        neighbors = store.neighbors(2, label="works_with", direction="out")
        assert set(neighbors) == {3}
        catalog.close()

    def test_neighbors_in(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        neighbors = store.neighbors(3, direction="in")
        assert set(neighbors) == {1, 2}
        catalog.close()

    def test_neighbors_in_with_label(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        neighbors = store.neighbors(3, label="knows", direction="in")
        assert set(neighbors) == {1}
        catalog.close()

    def test_neighbors_nonexistent_vertex(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)

        assert store.neighbors(999) == []
        catalog.close()


# ======================================================================
# edges_by_label()
# ======================================================================


class TestEdgesByLabel:
    def test_edges_by_label(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        knows_edges = store.edges_by_label("knows")
        assert len(knows_edges) == 2
        assert all(e.label == "knows" for e in knows_edges)
        catalog.close()

    def test_edges_by_label_none(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        missing = store.edges_by_label("nonexistent")
        assert missing == []
        catalog.close()


# ======================================================================
# Persistence Across Reconnection
# ======================================================================


class TestPersistence:
    def test_vertices_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        store1 = SQLiteGraphStore(cat1.conn)
        _populate(store1)
        cat1.close()

        cat2 = Catalog(db)
        store2 = SQLiteGraphStore(cat2.conn)

        assert store2.get_vertex(1) is not None
        assert store2.get_vertex(1).properties["name"] == "Alice"
        assert store2.get_vertex(2) is not None
        assert store2.get_vertex(3) is not None
        cat2.close()

    def test_edges_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        store1 = SQLiteGraphStore(cat1.conn)
        _populate(store1)
        cat1.close()

        cat2 = Catalog(db)
        store2 = SQLiteGraphStore(cat2.conn)

        assert store2.get_edge(1) is not None
        assert store2.get_edge(1).label == "knows"
        assert store2.get_edge(3) is not None
        assert store2.get_edge(3).label == "works_with"
        cat2.close()

    def test_adjacency_survives_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        store1 = SQLiteGraphStore(cat1.conn)
        _populate(store1)
        cat1.close()

        cat2 = Catalog(db)
        store2 = SQLiteGraphStore(cat2.conn)

        assert set(store2.neighbors(1, direction="out")) == {2, 3}
        assert set(store2.neighbors(3, direction="in")) == {1, 2}
        cat2.close()

    def test_in_memory_cache_rebuilt_on_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        store1 = SQLiteGraphStore(cat1.conn)
        _populate(store1)
        cat1.close()

        cat2 = Catalog(db)
        store2 = SQLiteGraphStore(cat2.conn)

        # _adj_out should be rebuilt from SQLite
        assert 1 in store2._adj_out
        assert len(store2._adj_out[1]) == 2
        # _label_index should be rebuilt
        assert "knows" in store2._label_index
        assert len(store2._label_index["knows"]) == 2
        cat2.close()


# ======================================================================
# Engine Integration
# ======================================================================


class TestEngineIntegration:
    _TABLE_DDL = "CREATE TABLE g (id SERIAL PRIMARY KEY, name TEXT)"

    def test_graph_uses_sqlite_store(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(self._TABLE_DDL)
            assert isinstance(engine._tables["g"].graph_store, SQLiteGraphStore)

    def test_in_memory_engine_uses_plain_store(self):
        from uqa.engine import Engine
        from uqa.graph.store import GraphStore

        engine = Engine()
        engine.sql(self._TABLE_DDL)
        assert type(engine._tables["g"].graph_store) is GraphStore

    def test_graph_survives_engine_close_reopen(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")

        with Engine(db_path=db) as engine:
            engine.sql(self._TABLE_DDL)
            engine.add_graph_vertex(
                Vertex(1, "", {"name": "Alice", "age": 30}), table="g"
            )
            engine.add_graph_vertex(
                Vertex(2, "", {"name": "Bob", "age": 25}), table="g"
            )
            engine.add_graph_edge(Edge(1, 1, 2, "knows", {"since": 2020}), table="g")

        with Engine(db_path=db) as engine:
            gs = engine._tables["g"].graph_store
            v = gs.get_vertex(1)
            assert v is not None
            assert v.properties["name"] == "Alice"

            e = gs.get_edge(1)
            assert e is not None
            assert e.label == "knows"

            neighbors = gs.neighbors(1, direction="out")
            assert 2 in neighbors

    def test_graph_operators_work_with_sqlite_store(self, tmp_path):
        from uqa.engine import Engine
        from uqa.graph.operators import TraverseOperator

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(self._TABLE_DDL)
            engine.add_graph_vertex(Vertex(1, "", {"name": "Alice"}), table="g")
            engine.add_graph_vertex(Vertex(2, "", {"name": "Bob"}), table="g")
            engine.add_graph_vertex(Vertex(3, "", {"name": "Charlie"}), table="g")
            engine.add_graph_edge(Edge(1, 1, 2, "knows", {}), table="g")
            engine.add_graph_edge(Edge(2, 2, 3, "knows", {}), table="g")

            ctx = engine._context_for_table("g")
            op = TraverseOperator(start_vertex=1, label="knows", max_hops=2)
            result = op.execute(ctx)
            doc_ids = {e.doc_id for e in result}
            assert {1, 2, 3} == doc_ids

    def test_graph_pattern_match_with_sqlite_store(self, tmp_path):
        from uqa.engine import Engine
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(self._TABLE_DDL)
            engine.add_graph_vertex(Vertex(1, "", {"name": "Alice"}), table="g")
            engine.add_graph_vertex(Vertex(2, "", {"name": "Bob"}), table="g")
            engine.add_graph_vertex(Vertex(3, "", {"name": "Charlie"}), table="g")
            engine.add_graph_edge(Edge(1, 1, 2, "knows", {}), table="g")
            engine.add_graph_edge(Edge(2, 1, 3, "knows", {}), table="g")

            ctx = engine._context_for_table("g")
            pattern = GraphPattern(
                vertex_patterns=[VertexPattern("a"), VertexPattern("b")],
                edge_patterns=[EdgePattern("a", "b", "knows")],
            )
            op = PatternMatchOperator(pattern)
            result = op.execute(ctx)
            assert len(result) >= 2

    def test_rpq_with_sqlite_store(self, tmp_path):
        from uqa.engine import Engine
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import Concat, Label

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(self._TABLE_DDL)
            engine.add_graph_vertex(Vertex(1, "", {"name": "A"}), table="g")
            engine.add_graph_vertex(Vertex(2, "", {"name": "B"}), table="g")
            engine.add_graph_vertex(Vertex(3, "", {"name": "C"}), table="g")
            engine.add_graph_edge(Edge(1, 1, 2, "knows", {}), table="g")
            engine.add_graph_edge(Edge(2, 2, 3, "follows", {}), table="g")

            ctx = engine._context_for_table("g")
            expr = Concat(Label("knows"), Label("follows"))
            op = RegularPathQueryOperator(expr, start_vertex=1)
            result = op.execute(ctx)
            doc_ids = {e.doc_id for e in result}
            assert 3 in doc_ids


# ======================================================================
# GraphStore Interface Compatibility
# ======================================================================


class TestInterfaceCompat:
    def test_get_vertex(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        v = store.get_vertex(1)
        assert v is not None
        assert v.properties["name"] == "Alice"
        assert store.get_vertex(999) is None
        catalog.close()

    def test_get_edge(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        e = store.get_edge(1)
        assert e is not None
        assert e.label == "knows"
        assert store.get_edge(999) is None
        catalog.close()

    def test_vertices_property(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        verts = store.vertices
        assert len(verts) == 3
        assert 1 in verts
        catalog.close()

    def test_edges_property(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        store = SQLiteGraphStore(catalog.conn)
        _populate(store)

        edges = store.edges
        assert len(edges) == 3
        assert 1 in edges
        catalog.close()
