#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQLite-backed catalog and Engine persistence."""

from __future__ import annotations

import tempfile
import os

import numpy as np
import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.storage.catalog import Catalog


# ======================================================================
# Catalog unit tests
# ======================================================================


class TestCatalogMetadata:
    def test_set_and_get(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.set_metadata("key1", "value1")
        assert cat.get_metadata("key1") == "value1"
        cat.close()

    def test_get_missing_returns_none(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        assert cat.get_metadata("nonexistent") is None
        cat.close()

    def test_overwrite(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.set_metadata("k", "v1")
        cat.set_metadata("k", "v2")
        assert cat.get_metadata("k") == "v2"
        cat.close()


class TestCatalogTableSchemas:
    def test_save_and_load_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cols = [
            {
                "name": "id",
                "type_name": "serial",
                "primary_key": True,
                "not_null": True,
                "auto_increment": True,
                "default": None,
            },
            {
                "name": "title",
                "type_name": "text",
                "primary_key": False,
                "not_null": True,
                "auto_increment": False,
                "default": None,
            },
        ]
        cat.save_table_schema("papers", cols)
        schemas = cat.load_table_schemas()
        assert len(schemas) == 1
        name, loaded_cols = schemas[0]
        assert name == "papers"
        assert loaded_cols == cols
        cat.close()

    def test_drop_removes_schema_and_documents(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_table_schema("t1", [{"name": "a", "type_name": "int",
            "primary_key": False, "not_null": False,
            "auto_increment": False, "default": None}])
        cat.save_document("t1", 1, {"a": 10})
        cat.save_document("t1", 2, {"a": 20})
        cat.drop_table_schema("t1")
        assert cat.load_table_schemas() == []
        assert cat.load_documents("t1") == []
        cat.close()

    def test_multiple_tables(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        for name in ("t1", "t2", "t3"):
            cat.save_table_schema(name, [{"name": "x", "type_name": "int",
                "primary_key": False, "not_null": False,
                "auto_increment": False, "default": None}])
        schemas = cat.load_table_schemas()
        assert {s[0] for s in schemas} == {"t1", "t2", "t3"}
        cat.close()


class TestCatalogDocuments:
    def test_save_and_load(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"name": "alice", "age": 30})
        cat.save_document("t1", 2, {"name": "bob", "age": 25})
        docs = cat.load_documents("t1")
        assert len(docs) == 2
        docs_dict = {did: data for did, data in docs}
        assert docs_dict[1] == {"name": "alice", "age": 30}
        assert docs_dict[2] == {"name": "bob", "age": 25}
        cat.close()

    def test_tables_isolated(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"x": 1})
        cat.save_document("t2", 1, {"x": 2})
        assert len(cat.load_documents("t1")) == 1
        assert len(cat.load_documents("t2")) == 1
        assert cat.load_documents("t1")[0][1]["x"] == 1
        cat.close()

    def test_delete_document(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"x": 1})
        cat.save_document("t1", 2, {"x": 2})
        cat.delete_document("t1", 1)
        docs = cat.load_documents("t1")
        assert len(docs) == 1
        assert docs[0][0] == 2
        cat.close()

    def test_upsert_overwrites(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"v": "old"})
        cat.save_document("t1", 1, {"v": "new"})
        docs = cat.load_documents("t1")
        assert len(docs) == 1
        assert docs[0][1]["v"] == "new"
        cat.close()


class TestCatalogGraph:
    def test_vertices_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_vertex(1, {"name": "A"})
        cat.save_vertex(2, {"name": "B"})
        verts = cat.load_vertices()
        assert len(verts) == 2
        verts_dict = {vid: props for vid, props in verts}
        assert verts_dict[1] == {"name": "A"}
        assert verts_dict[2] == {"name": "B"}
        cat.close()

    def test_edges_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_edge(10, 1, 2, "knows", {"weight": 0.5})
        edges = cat.load_edges()
        assert len(edges) == 1
        eid, src, dst, label, props = edges[0]
        assert (eid, src, dst, label) == (10, 1, 2, "knows")
        assert props == {"weight": 0.5}
        cat.close()


class TestCatalogVectors:
    def test_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        cat.save_vector(1, vec)
        loaded = cat.load_vectors()
        assert len(loaded) == 1
        doc_id, loaded_vec = loaded[0]
        assert doc_id == 1
        np.testing.assert_array_almost_equal(loaded_vec, vec)
        cat.close()

    def test_multiple_vectors(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        for i in range(5):
            cat.save_vector(i, np.random.rand(8).astype(np.float32))
        assert len(cat.load_vectors()) == 5
        cat.close()


class TestCatalogPersistence:
    def test_close_and_reopen(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_table_schema("t", [{"name": "x", "type_name": "int",
            "primary_key": False, "not_null": False,
            "auto_increment": False, "default": None}])
        cat.save_document("t", 1, {"x": 42})
        cat.save_vertex(1, {"label": "A"})
        cat.save_edge(1, 1, 2, "link", {})
        cat.save_vector(1, np.array([1.0, 2.0], dtype=np.float32))
        cat.close()

        cat2 = Catalog(db)
        assert len(cat2.load_table_schemas()) == 1
        assert len(cat2.load_documents("t")) == 1
        assert len(cat2.load_vertices()) == 1
        assert len(cat2.load_edges()) == 1
        assert len(cat2.load_vectors()) == 1
        cat2.close()


# ======================================================================
# Engine persistence integration tests
# ======================================================================


class TestEnginePersistenceSQL:
    """Test SQL DDL/DML persistence through Engine."""

    def test_create_table_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER DEFAULT 0
                )
            """)
        with Engine(db_path=db) as engine:
            tables = list(engine._tables.keys())
            assert "users" in tables
            table = engine._tables["users"]
            assert "id" in table.columns
            assert "name" in table.columns
            assert "age" in table.columns

    def test_insert_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE items (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    price INTEGER DEFAULT 0
                )
            """)
            engine.sql("""
                INSERT INTO items (title, price) VALUES
                    ('Widget', 100),
                    ('Gadget', 200)
            """)

        with Engine(db_path=db) as engine:
            result = engine.sql("SELECT id, title, price FROM items ORDER BY id")
            assert len(result.rows) == 2
            assert result.rows[0]["title"] == "Widget"
            assert result.rows[0]["price"] == 100
            assert result.rows[1]["title"] == "Gadget"
            assert result.rows[1]["price"] == 200

    def test_auto_increment_continues_after_restart(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE seq (id SERIAL PRIMARY KEY, val TEXT NOT NULL)
            """)
            engine.sql("INSERT INTO seq (val) VALUES ('first')")
            engine.sql("INSERT INTO seq (val) VALUES ('second')")

        with Engine(db_path=db) as engine:
            engine.sql("INSERT INTO seq (val) VALUES ('third')")
            result = engine.sql("SELECT id, val FROM seq ORDER BY id")
            assert len(result.rows) == 3
            ids = [r["id"] for r in result.rows]
            assert ids == [1, 2, 3]

    def test_text_search_works_after_restart(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE docs (
                    id SERIAL PRIMARY KEY,
                    body TEXT NOT NULL
                )
            """)
            engine.sql("""
                INSERT INTO docs (body) VALUES
                    ('the quick brown fox'),
                    ('lazy dog sleeps'),
                    ('quick fox jumps')
            """)

        with Engine(db_path=db) as engine:
            result = engine.sql("""
                SELECT id, body, _score FROM docs
                WHERE text_match(body, 'quick fox')
                ORDER BY _score DESC
            """)
            assert len(result.rows) >= 2
            bodies = [r["body"] for r in result.rows]
            assert "the quick brown fox" in bodies
            assert "quick fox jumps" in bodies

    def test_drop_table_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE tmp (id SERIAL PRIMARY KEY, x INT)")
            engine.sql("INSERT INTO tmp (x) VALUES (1)")
            engine.sql("DROP TABLE tmp")

        with Engine(db_path=db) as engine:
            assert "tmp" not in engine._tables

    def test_drop_table_if_exists_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE tmp (id INT PRIMARY KEY)")
            engine.sql("DROP TABLE IF EXISTS tmp")
            engine.sql("DROP TABLE IF EXISTS nonexistent")

        with Engine(db_path=db) as engine:
            assert "tmp" not in engine._tables

    def test_multiple_tables_independent(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE a (id SERIAL PRIMARY KEY, x INT)")
            engine.sql("CREATE TABLE b (id SERIAL PRIMARY KEY, y TEXT)")
            engine.sql("INSERT INTO a (x) VALUES (10), (20)")
            engine.sql("INSERT INTO b (y) VALUES ('hello')")

        with Engine(db_path=db) as engine:
            ra = engine.sql("SELECT x FROM a ORDER BY x")
            rb = engine.sql("SELECT y FROM b")
            assert len(ra.rows) == 2
            assert len(rb.rows) == 1
            assert ra.rows[0]["x"] == 10
            assert rb.rows[0]["y"] == "hello"


class TestEnginePersistenceAPI:
    """Test programmatic API persistence."""

    def test_add_document_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db, vector_dimensions=4) as engine:
            engine.add_document(1, {"title": "hello world"})
            engine.add_document(2, {"title": "foo bar"})

        with Engine(db_path=db, vector_dimensions=4) as engine:
            assert engine.document_store.get(1) == {"title": "hello world"}
            assert engine.document_store.get(2) == {"title": "foo bar"}

    def test_add_document_with_vector_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        with Engine(db_path=db, vector_dimensions=4) as engine:
            engine.add_document(1, {"title": "test"}, embedding=vec)

        with Engine(db_path=db, vector_dimensions=4) as engine:
            assert engine.document_store.get(1) is not None
            # Vector search should work
            query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            pl = engine.vector_index.search_knn(query, k=1)
            assert len(pl.entries) == 1
            assert pl.entries[0].doc_id == 1

    def test_add_graph_persists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.add_graph_vertex(Vertex(vertex_id=1, properties={"name": "A"}))
            engine.add_graph_vertex(Vertex(vertex_id=2, properties={"name": "B"}))
            engine.add_graph_edge(Edge(
                edge_id=1, source_id=1, target_id=2,
                label="knows", properties={},
            ))

        with Engine(db_path=db) as engine:
            v1 = engine.graph_store.get_vertex(1)
            assert v1 is not None
            assert v1.properties == {"name": "A"}
            neighbors = engine.graph_store.neighbors(1, "knows")
            assert neighbors == [2]


class TestEnginePersistenceBackwardCompat:
    """Ensure db_path=None works exactly as before."""

    def test_no_db_path_is_in_memory(self):
        engine = Engine()
        assert engine._catalog is None
        engine.sql("CREATE TABLE t (id INT PRIMARY KEY, x INT)")
        engine.sql("INSERT INTO t (id, x) VALUES (1, 42)")
        result = engine.sql("SELECT x FROM t")
        assert result.rows[0]["x"] == 42
        engine.close()

    def test_add_document_without_persistence(self):
        engine = Engine(vector_dimensions=4)
        engine.add_document(1, {"title": "test"})
        assert engine.document_store.get(1) == {"title": "test"}
        engine.close()

    def test_context_manager(self):
        with Engine() as engine:
            engine.sql("CREATE TABLE t (id INT PRIMARY KEY)")
            assert "t" in engine._tables
