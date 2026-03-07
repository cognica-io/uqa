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

    def test_drop_cascades_postings_and_stats(self, tmp_path):
        """DROP TABLE removes postings, doc_lengths, and column_stats."""
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_table_schema("t1", [{"name": "x", "type_name": "text",
            "primary_key": False, "not_null": False,
            "auto_increment": False, "default": None}])
        cat.save_postings("t1", 1, {"x": 3}, {("x", "hello"): (0, 1, 2)})
        cat.save_column_stats("t1", "x", 5, 0, "a", "z", 10)
        cat.drop_table_schema("t1")
        assert cat.load_postings("t1") == []
        assert cat.load_doc_lengths("t1") == []
        assert cat.load_column_stats("t1") == []
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

    def test_delete_cascades_postings(self, tmp_path):
        """delete_document also removes postings and doc_lengths."""
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"x": "hello"})
        cat.save_postings("t1", 1, {"x": 1}, {("x", "hello"): (0,)})
        cat.delete_document("t1", 1)
        assert cat.load_postings("t1") == []
        assert cat.load_doc_lengths("t1") == []
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


class TestCatalogPostings:
    """Tests for inverted index posting persistence."""

    def test_save_and_load_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        field_lengths = {"title": 3, "body": 5}
        postings = {
            ("title", "hello"): (0,),
            ("title", "world"): (1,),
            ("body", "hello"): (0, 2, 4),
        }
        cat.save_postings("t1", 1, field_lengths, postings)

        loaded = cat.load_postings("t1")
        assert len(loaded) == 3
        loaded_dict = {(f, t, d): pos for f, t, d, pos in loaded}
        assert loaded_dict[("title", "hello", 1)] == (0,)
        assert loaded_dict[("title", "world", 1)] == (1,)
        assert loaded_dict[("body", "hello", 1)] == (0, 2, 4)
        cat.close()

    def test_doc_lengths_round_trip(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_postings("t1", 1, {"title": 3, "body": 5}, {})
        cat.save_postings("t1", 2, {"title": 2}, {})
        loaded = cat.load_doc_lengths("t1")
        assert len(loaded) == 2
        lengths_dict = {did: lens for did, lens in loaded}
        assert lengths_dict[1] == {"title": 3, "body": 5}
        assert lengths_dict[2] == {"title": 2}
        cat.close()

    def test_delete_postings(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_postings("t1", 1, {"x": 1}, {("x", "a"): (0,)})
        cat.save_postings("t1", 2, {"x": 1}, {("x", "b"): (0,)})
        cat.delete_postings("t1", 1)
        loaded = cat.load_postings("t1")
        assert len(loaded) == 1
        assert loaded[0][2] == 2  # doc_id = 2
        assert cat.load_doc_lengths("t1") == [(2, {"x": 1})]
        cat.close()

    def test_tables_isolated(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_postings("t1", 1, {"x": 1}, {("x", "a"): (0,)})
        cat.save_postings("t2", 1, {"x": 1}, {("x", "b"): (0,)})
        t1 = cat.load_postings("t1")
        t2 = cat.load_postings("t2")
        assert len(t1) == 1
        assert len(t2) == 1
        assert t1[0][1] == "a"
        assert t2[0][1] == "b"
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

    def test_delete_vector(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_vector(1, np.array([1.0, 2.0], dtype=np.float32))
        cat.save_vector(2, np.array([3.0, 4.0], dtype=np.float32))
        cat.delete_vector(1)
        loaded = cat.load_vectors()
        assert len(loaded) == 1
        assert loaded[0][0] == 2
        cat.close()


class TestCatalogColumnStats:
    """Tests for ANALYZE result persistence."""

    def test_save_and_load(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_column_stats("t1", "age", 10, 2, 18, 65, 100)
        cat.save_column_stats("t1", "name", 50, 0, "alice", "zoe", 100)
        loaded = cat.load_column_stats("t1")
        assert len(loaded) == 2
        stats_dict = {row[0]: row[1:6] for row in loaded}
        assert stats_dict["age"] == (10, 2, 18, 65, 100)
        assert stats_dict["name"] == (50, 0, "alice", "zoe", 100)
        cat.close()

    def test_overwrite(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_column_stats("t1", "x", 5, 0, 1, 10, 20)
        cat.save_column_stats("t1", "x", 8, 1, 2, 15, 30)
        loaded = cat.load_column_stats("t1")
        assert len(loaded) == 1
        assert loaded[0][:6] == ("x", 8, 1, 2, 15, 30)
        cat.close()

    def test_delete(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_column_stats("t1", "x", 5, 0, 1, 10, 20)
        cat.delete_column_stats("t1")
        assert cat.load_column_stats("t1") == []
        cat.close()

    def test_tables_isolated(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_column_stats("t1", "x", 5, 0, 1, 10, 20)
        cat.save_column_stats("t2", "x", 8, 0, 1, 20, 40)
        assert len(cat.load_column_stats("t1")) == 1
        assert len(cat.load_column_stats("t2")) == 1
        assert cat.load_column_stats("t1")[0][1] == 5
        assert cat.load_column_stats("t2")[0][1] == 8
        cat.close()


class TestCatalogScoringParams:
    """Tests for Bayesian calibration parameter persistence (Papers 3-4)."""

    def test_save_and_load(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        params = {"alpha": 1.5, "beta": 0.3, "base_rate": 0.01}
        cat.save_scoring_params("bm25_body", params)
        loaded = cat.load_scoring_params("bm25_body")
        assert loaded == params
        cat.close()

    def test_load_missing_returns_none(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        assert cat.load_scoring_params("nonexistent") is None
        cat.close()

    def test_overwrite(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_scoring_params("sig1", {"alpha": 1.0})
        cat.save_scoring_params("sig1", {"alpha": 2.0, "beta": 0.5})
        loaded = cat.load_scoring_params("sig1")
        assert loaded == {"alpha": 2.0, "beta": 0.5}
        cat.close()

    def test_load_all(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_scoring_params("s1", {"alpha": 1.0})
        cat.save_scoring_params("s2", {"alpha": 2.0})
        all_params = cat.load_all_scoring_params()
        assert len(all_params) == 2
        names = {name for name, _ in all_params}
        assert names == {"s1", "s2"}
        cat.close()

    def test_delete(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_scoring_params("s1", {"alpha": 1.0})
        cat.delete_scoring_params("s1")
        assert cat.load_scoring_params("s1") is None
        cat.close()


class TestCatalogTransactions:
    """Tests for begin/commit/rollback transaction support."""

    def test_batch_commit(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.begin()
        cat.save_document("t1", 1, {"x": 1})
        cat.save_document("t1", 2, {"x": 2})
        cat.save_document("t1", 3, {"x": 3})
        cat.commit()
        assert len(cat.load_documents("t1")) == 3
        cat.close()

    def test_rollback(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"x": 1})  # committed
        cat.begin()
        cat.save_document("t1", 2, {"x": 2})  # uncommitted
        cat.rollback()
        docs = cat.load_documents("t1")
        assert len(docs) == 1
        assert docs[0][0] == 1
        cat.close()

    def test_auto_commit_outside_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        cat = Catalog(db)
        cat.save_document("t1", 1, {"x": 1})
        # Close without explicit commit -- write-through should have committed
        cat.close()
        cat2 = Catalog(db)
        assert len(cat2.load_documents("t1")) == 1
        cat2.close()


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
        cat.save_postings("t", 1, {"x": 1}, {("x", "hello"): (0,)})
        cat.save_column_stats("t", "x", 5, 0, 1, 10, 20)
        cat.save_scoring_params("bm25", {"alpha": 1.5})
        cat.close()

        cat2 = Catalog(db)
        assert len(cat2.load_table_schemas()) == 1
        assert len(cat2.load_documents("t")) == 1
        assert len(cat2.load_vertices()) == 1
        assert len(cat2.load_edges()) == 1
        assert len(cat2.load_vectors()) == 1
        assert len(cat2.load_postings("t")) == 1
        assert len(cat2.load_doc_lengths("t")) == 1
        assert len(cat2.load_column_stats("t")) == 1
        assert cat2.load_scoring_params("bm25") == {"alpha": 1.5}
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

    def test_analyze_persists(self, tmp_path):
        """ANALYZE results survive restart."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE stats_test (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    value INT NOT NULL
                )
            """)
            engine.sql("""
                INSERT INTO stats_test (category, value) VALUES
                    ('a', 10), ('b', 20), ('a', 30),
                    ('c', 40), ('b', 50)
            """)
            engine.sql("ANALYZE stats_test")
            table = engine._tables["stats_test"]
            assert table._stats["category"].distinct_count == 3
            assert table._stats["value"].row_count == 5

        with Engine(db_path=db) as engine:
            table = engine._tables["stats_test"]
            assert table._stats["category"].distinct_count == 3
            assert table._stats["value"].row_count == 5
            assert table._stats["value"].min_value == 10
            assert table._stats["value"].max_value == 50


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

    def test_delete_document(self, tmp_path):
        """delete_document removes from all stores and catalog."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db, vector_dimensions=4) as engine:
            engine.add_document(1, {"title": "hello world"})
            engine.add_document(2, {"title": "foo bar"})
            engine.delete_document(1)
            assert engine.document_store.get(1) is None
            assert engine.document_store.get(2) is not None

        with Engine(db_path=db, vector_dimensions=4) as engine:
            assert engine.document_store.get(1) is None
            assert engine.document_store.get(2) == {"title": "foo bar"}
            # Inverted index should not contain deleted doc
            pl = engine.inverted_index.get_posting_list("title", "hello")
            doc_ids = [e.doc_id for e in pl.entries]
            assert 1 not in doc_ids

    def test_scoring_params_persist(self, tmp_path):
        """Bayesian calibration parameters survive restart (Papers 3-4)."""
        db = str(tmp_path / "test.db")
        params = {"alpha": 1.5, "beta": 0.3, "base_rate": 0.01}
        with Engine(db_path=db) as engine:
            engine.save_scoring_params("bayesian_bm25_body", params)

        with Engine(db_path=db) as engine:
            loaded = engine.load_scoring_params("bayesian_bm25_body")
            assert loaded == params

    def test_scoring_params_in_memory_returns_none(self):
        """In-memory engine returns None for scoring params."""
        engine = Engine()
        assert engine.load_scoring_params("anything") is None
        assert engine.load_all_scoring_params() == []
        engine.close()


class TestEnginePersistencePostings:
    """Test that inverted index is restored from postings, not re-tokenized."""

    def test_inverted_index_stats_after_restart(self, tmp_path):
        """Corpus stats (doc_count, avg_doc_length) match after restart."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.add_document(1, {"title": "the quick brown fox"})
            engine.add_document(2, {"title": "lazy dog"})
            engine.add_document(3, {"title": "quick fox jumps high"})
            stats_before = engine.inverted_index.stats

        with Engine(db_path=db) as engine:
            stats_after = engine.inverted_index.stats
            assert stats_after.total_docs == stats_before.total_docs
            assert abs(stats_after.avg_doc_length - stats_before.avg_doc_length) < 1e-10

    def test_posting_positions_preserved(self, tmp_path):
        """Token positions are correctly round-tripped through SQLite."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.add_document(1, {"body": "the cat sat on the mat"})
            pl_before = engine.inverted_index.get_posting_list("body", "the")
            positions_before = pl_before.entries[0].payload.positions

        with Engine(db_path=db) as engine:
            pl_after = engine.inverted_index.get_posting_list("body", "the")
            positions_after = pl_after.entries[0].payload.positions
            assert positions_after == positions_before

    def test_doc_lengths_preserved(self, tmp_path):
        """Per-document field lengths survive restart for BM25 scoring."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.add_document(1, {"title": "hello world", "body": "a b c d e"})
            len_before = engine.inverted_index.get_doc_length(1, "title")
            body_len_before = engine.inverted_index.get_doc_length(1, "body")

        with Engine(db_path=db) as engine:
            assert engine.inverted_index.get_doc_length(1, "title") == len_before
            assert engine.inverted_index.get_doc_length(1, "body") == body_len_before

    def test_bm25_scores_match_after_restart(self, tmp_path):
        """BM25 text search produces identical scores before/after restart."""
        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("""
                CREATE TABLE papers (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL
                )
            """)
            engine.sql("""
                INSERT INTO papers (title) VALUES
                    ('neural network learning'),
                    ('deep learning with transformers'),
                    ('bayesian inference methods'),
                    ('learning to rank documents')
            """)
            result_before = engine.sql("""
                SELECT id, title, _score FROM papers
                WHERE text_match(title, 'learning')
                ORDER BY _score DESC
            """)
            scores_before = [(r["id"], r["_score"]) for r in result_before.rows]

        with Engine(db_path=db) as engine:
            result_after = engine.sql("""
                SELECT id, title, _score FROM papers
                WHERE text_match(title, 'learning')
                ORDER BY _score DESC
            """)
            scores_after = [(r["id"], r["_score"]) for r in result_after.rows]
            assert len(scores_after) == len(scores_before)
            for (id_b, s_b), (id_a, s_a) in zip(scores_before, scores_after):
                assert id_b == id_a
                assert abs(s_b - s_a) < 1e-10


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

    def test_delete_document_in_memory(self):
        """delete_document works in pure in-memory mode."""
        engine = Engine(vector_dimensions=4)
        engine.add_document(1, {"title": "hello world"})
        engine.add_document(2, {"title": "foo bar"})
        engine.delete_document(1)
        assert engine.document_store.get(1) is None
        assert engine.document_store.get(2) is not None
        pl = engine.inverted_index.get_posting_list("title", "hello")
        assert all(e.doc_id != 1 for e in pl.entries)
        engine.close()


class TestEnginePersistenceMigration:
    """Test backward compat migration from old databases without _postings."""

    def test_old_database_migrates_on_open(self, tmp_path):
        """A database created without _postings gets auto-migrated."""
        import sqlite3

        db = str(tmp_path / "test.db")

        # Simulate an old-format database by inserting directly into SQLite
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE _metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE _catalog_tables (
                name TEXT PRIMARY KEY, columns_json TEXT NOT NULL
            );
            CREATE TABLE _documents (
                table_name TEXT NOT NULL, doc_id INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                PRIMARY KEY (table_name, doc_id)
            );
            CREATE TABLE _graph_vertices (
                vertex_id INTEGER PRIMARY KEY, properties_json TEXT NOT NULL
            );
            CREATE TABLE _graph_edges (
                edge_id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL, label TEXT NOT NULL,
                properties_json TEXT NOT NULL
            );
            CREATE TABLE _vectors (
                doc_id INTEGER PRIMARY KEY, dimensions INTEGER NOT NULL,
                embedding BLOB NOT NULL
            );
        """)
        conn.execute(
            "INSERT INTO _metadata VALUES ('vector_dimensions', '64')"
        )
        conn.execute(
            "INSERT INTO _metadata VALUES ('max_elements', '10000')"
        )
        # Insert a document directly (old format, no _postings table)
        import json
        conn.execute(
            "INSERT INTO _documents VALUES ('', 1, ?)",
            (json.dumps({"title": "hello world test"}),),
        )
        conn.commit()
        conn.close()

        # Open with Engine -- should auto-migrate (create _postings, etc.)
        with Engine(db_path=db) as engine:
            assert engine.document_store.get(1) == {"title": "hello world test"}
            # Inverted index should be populated via migration
            pl = engine.inverted_index.get_posting_list("title", "hello")
            assert len(pl.entries) == 1
            assert pl.entries[0].doc_id == 1

        # Re-open -- should use fast path now (postings exist)
        with Engine(db_path=db) as engine:
            pl = engine.inverted_index.get_posting_list("title", "world")
            assert len(pl.entries) == 1
