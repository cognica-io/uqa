#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQLiteDocumentStore."""

from __future__ import annotations

import sqlite3

import pytest

from uqa.storage.sqlite_document_store import SQLiteDocumentStore


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_store(
    tmp_path, table_name="t1", columns=None
) -> tuple[sqlite3.Connection, SQLiteDocumentStore]:
    """Create a connection + store for the given schema."""
    if columns is None:
        columns = [
            ("id", "integer"),
            ("name", "text"),
            ("score", "real"),
            ("active", "boolean"),
        ]
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    store = SQLiteDocumentStore(conn, table_name, columns)
    return conn, store


# ------------------------------------------------------------------
# Basic CRUD
# ------------------------------------------------------------------


class TestCRUD:
    def test_put_and_get(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice", "score": 9.5, "active": 1})
        doc = store.get(1)
        assert doc == {"id": 1, "name": "alice", "score": 9.5, "active": 1}
        conn.close()

    def test_get_missing_returns_none(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert store.get(999) is None
        conn.close()

    def test_delete(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice"})
        store.delete(1)
        assert store.get(1) is None
        conn.close()

    def test_delete_nonexistent_is_noop(self, tmp_path):
        conn, store = _make_store(tmp_path)
        # Should not raise
        store.delete(42)
        conn.close()

    def test_overwrite_same_doc_id(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice", "score": 5.0})
        store.put(1, {"id": 1, "name": "bob", "score": 8.0})
        doc = store.get(1)
        assert doc is not None
        assert doc["name"] == "bob"
        assert doc["score"] == 8.0
        conn.close()


# ------------------------------------------------------------------
# Type handling
# ------------------------------------------------------------------


class TestTypes:
    def test_integer_column(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("val", "int")]
        )
        store.put(1, {"val": 42})
        assert store.get_field(1, "val") == 42
        conn.close()

    def test_text_column(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("val", "text")]
        )
        store.put(1, {"val": "hello"})
        assert store.get_field(1, "val") == "hello"
        conn.close()

    def test_real_column(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("val", "float")]
        )
        store.put(1, {"val": 3.14})
        assert store.get_field(1, "val") == pytest.approx(3.14)
        conn.close()

    def test_boolean_stored_as_integer(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("val", "boolean")]
        )
        store.put(1, {"val": 1})
        store.put(2, {"val": 0})
        assert store.get_field(1, "val") == 1
        assert store.get_field(2, "val") == 0
        conn.close()

    def test_blob_column(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("val", "blob")]
        )
        data = b"\x00\x01\x02\x03"
        store.put(1, {"val": data})
        assert store.get_field(1, "val") == data
        conn.close()

    def test_serial_maps_to_integer(self, tmp_path):
        conn, store = _make_store(
            tmp_path, columns=[("pk", "serial"), ("name", "text")]
        )
        store.put(1, {"pk": 1, "name": "row1"})
        assert store.get_field(1, "pk") == 1
        conn.close()


# ------------------------------------------------------------------
# NULL handling
# ------------------------------------------------------------------


class TestNulls:
    def test_missing_field_stored_as_null(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice"})
        # score and active not provided -> NULL -> excluded from dict
        doc = store.get(1)
        assert doc is not None
        assert "score" not in doc
        assert "active" not in doc
        conn.close()

    def test_explicit_none_stored_as_null(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": None, "score": None, "active": None})
        doc = store.get(1)
        assert doc is not None
        assert "name" not in doc
        assert "score" not in doc
        conn.close()

    def test_get_field_null_returns_none(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        assert store.get_field(1, "name") is None
        conn.close()


# ------------------------------------------------------------------
# doc_ids property
# ------------------------------------------------------------------


class TestDocIDs:
    def test_empty_store(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert store.doc_ids == set()
        conn.close()

    def test_after_inserts(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(10, {"id": 10, "name": "a"})
        store.put(20, {"id": 20, "name": "b"})
        store.put(30, {"id": 30, "name": "c"})
        assert store.doc_ids == {10, 20, 30}
        conn.close()

    def test_after_delete(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        store.put(2, {"id": 2})
        store.delete(1)
        assert store.doc_ids == {2}
        conn.close()


# ------------------------------------------------------------------
# __len__
# ------------------------------------------------------------------


class TestLen:
    def test_empty(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert len(store) == 0
        conn.close()

    def test_after_inserts(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        store.put(2, {"id": 2})
        assert len(store) == 2
        conn.close()

    def test_after_delete(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        store.put(2, {"id": 2})
        store.delete(1)
        assert len(store) == 1
        conn.close()


# ------------------------------------------------------------------
# max_doc_id
# ------------------------------------------------------------------


class TestMaxDocId:
    def test_empty_returns_zero(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert store.max_doc_id() == 0
        conn.close()

    def test_single_row(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(7, {"id": 7})
        assert store.max_doc_id() == 7
        conn.close()

    def test_multiple_rows(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(3, {"id": 3})
        store.put(10, {"id": 10})
        store.put(5, {"id": 5})
        assert store.max_doc_id() == 10
        conn.close()

    def test_after_deleting_max(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        store.put(5, {"id": 5})
        store.delete(5)
        assert store.max_doc_id() == 1
        conn.close()


# ------------------------------------------------------------------
# get_field
# ------------------------------------------------------------------


class TestGetField:
    def test_existing_field(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice", "score": 8.0})
        assert store.get_field(1, "name") == "alice"
        assert store.get_field(1, "score") == 8.0
        conn.close()

    def test_missing_doc(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert store.get_field(99, "name") is None
        conn.close()

    def test_unknown_column_returns_none(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1})
        assert store.get_field(1, "nonexistent") is None
        conn.close()


# ------------------------------------------------------------------
# eval_path
# ------------------------------------------------------------------


class TestEvalPath:
    def test_flat_single_key(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "name": "alice"})
        assert store.eval_path(1, ["name"]) == "alice"
        conn.close()

    def test_flat_missing_doc(self, tmp_path):
        conn, store = _make_store(tmp_path)
        assert store.eval_path(99, ["name"]) is None
        conn.close()

    def test_nested_path_falls_back_to_dict_traversal(self, tmp_path):
        """SQLite stores flat rows, so nested paths go through get() + HierarchicalDocument."""
        conn, store = _make_store(
            tmp_path, columns=[("name", "text")]
        )
        # Nested data cannot be directly stored in a flat SQLite column,
        # but if get() returns a dict we can still traverse it.
        # Since the store only has flat columns, a multi-level path on
        # flat data will return None.
        store.put(1, {"name": "alice"})
        result = store.eval_path(1, ["name", "first"])
        assert result is None
        conn.close()

    def test_single_element_path_uses_get_field(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {"id": 1, "score": 7.5})
        assert store.eval_path(1, ["score"]) == 7.5
        conn.close()


# ------------------------------------------------------------------
# Table isolation (multiple tables on same connection)
# ------------------------------------------------------------------


class TestTableIsolation:
    def test_two_tables_independent(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "shared.db"))
        store_a = SQLiteDocumentStore(
            conn, "alpha", [("x", "integer"), ("y", "text")]
        )
        store_b = SQLiteDocumentStore(
            conn, "beta", [("p", "real"), ("q", "text")]
        )

        store_a.put(1, {"x": 10, "y": "a"})
        store_b.put(1, {"p": 3.14, "q": "pi"})

        # Each store only sees its own data
        assert len(store_a) == 1
        assert len(store_b) == 1

        assert store_a.get(1) == {"x": 10, "y": "a"}
        assert store_b.get(1) == {"p": 3.14, "q": "pi"}

        store_a.delete(1)
        assert len(store_a) == 0
        assert len(store_b) == 1

        conn.close()

    def test_different_schemas(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "schemas.db"))
        store_1 = SQLiteDocumentStore(
            conn, "narrow", [("val", "integer")]
        )
        store_2 = SQLiteDocumentStore(
            conn, "wide",
            [("a", "text"), ("b", "text"), ("c", "real"), ("d", "boolean")],
        )

        store_1.put(1, {"val": 100})
        store_2.put(1, {"a": "x", "b": "y", "c": 1.0, "d": 0})

        assert store_1.get_field(1, "val") == 100
        assert store_2.get_field(1, "c") == 1.0

        assert store_1.doc_ids == {1}
        assert store_2.doc_ids == {1}

        conn.close()


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_document(self, tmp_path):
        conn, store = _make_store(tmp_path)
        store.put(1, {})
        doc = store.get(1)
        # All columns NULL -> empty dict
        assert doc == {}
        conn.close()

    def test_large_doc_id(self, tmp_path):
        conn, store = _make_store(tmp_path)
        big_id = 2**40
        store.put(big_id, {"id": big_id, "name": "big"})
        assert store.get(big_id) == {"id": big_id, "name": "big"}
        assert store.max_doc_id() == big_id
        conn.close()

    def test_idempotent_table_creation(self, tmp_path):
        """Creating SQLiteDocumentStore twice for the same table must not fail."""
        conn = sqlite3.connect(str(tmp_path / "idem.db"))
        cols = [("val", "integer")]
        store1 = SQLiteDocumentStore(conn, "dup", cols)
        store1.put(1, {"val": 42})
        # Re-create -- should reuse existing table
        store2 = SQLiteDocumentStore(conn, "dup", cols)
        assert store2.get(1) == {"val": 42}
        conn.close()
