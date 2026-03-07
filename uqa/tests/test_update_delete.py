#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for UPDATE and DELETE SQL statements."""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    e = Engine()
    e.sql(
        "CREATE TABLE products ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "price REAL, "
        "quantity INTEGER, "
        "category TEXT"
        ")"
    )
    e.sql(
        "INSERT INTO products (id, name, price, quantity, category) VALUES "
        "(1, 'Widget', 10.50, 100, 'tools'), "
        "(2, 'Gadget', 25.00, 50, 'electronics'), "
        "(3, 'Doohickey', 5.75, 200, NULL)"
    )
    return e


# ==================================================================
# UPDATE
# ==================================================================


class TestUpdateBasic:
    def test_update_single_column(self, engine):
        r = engine.sql("UPDATE products SET price = 12.00 WHERE id = 1")
        assert r.rows[0]["updated"] == 1
        r = engine.sql("SELECT price FROM products WHERE id = 1")
        assert r.rows[0]["price"] == 12.0

    def test_update_multiple_columns(self, engine):
        r = engine.sql(
            "UPDATE products SET price = 15.00, quantity = 75 WHERE id = 2"
        )
        assert r.rows[0]["updated"] == 1
        r = engine.sql("SELECT price, quantity FROM products WHERE id = 2")
        assert r.rows[0]["price"] == 15.0
        assert r.rows[0]["quantity"] == 75

    def test_update_multiple_rows(self, engine):
        r = engine.sql("UPDATE products SET category = 'sale' WHERE price < 20")
        assert r.rows[0]["updated"] == 2
        r = engine.sql(
            "SELECT id FROM products WHERE category = 'sale' ORDER BY id"
        )
        assert [row["id"] for row in r.rows] == [1, 3]

    def test_update_all_rows(self, engine):
        r = engine.sql("UPDATE products SET quantity = 0")
        assert r.rows[0]["updated"] == 3
        r = engine.sql("SELECT quantity FROM products")
        assert all(row["quantity"] == 0 for row in r.rows)

    def test_update_no_match(self, engine):
        r = engine.sql("UPDATE products SET price = 0 WHERE id = 999")
        assert r.rows[0]["updated"] == 0

    def test_update_returns_count(self, engine):
        r = engine.sql("UPDATE products SET price = 1.00")
        assert r.columns == ["updated"]
        assert r.rows[0]["updated"] == 3


class TestUpdateExpressions:
    def test_update_with_arithmetic(self, engine):
        engine.sql("UPDATE products SET price = price * 1.1 WHERE id = 1")
        r = engine.sql("SELECT price FROM products WHERE id = 1")
        assert abs(r.rows[0]["price"] - 11.55) < 0.01

    def test_update_with_addition(self, engine):
        engine.sql("UPDATE products SET quantity = quantity + 10 WHERE id = 2")
        r = engine.sql("SELECT quantity FROM products WHERE id = 2")
        assert r.rows[0]["quantity"] == 60

    def test_update_set_to_null(self, engine):
        engine.sql("UPDATE products SET category = NULL WHERE id = 1")
        r = engine.sql("SELECT category FROM products WHERE id = 1")
        assert r.rows[0].get("category") is None

    def test_update_with_coalesce(self, engine):
        engine.sql(
            "UPDATE products SET category = COALESCE(category, 'uncategorized')"
        )
        r = engine.sql("SELECT id, category FROM products WHERE id = 3")
        assert r.rows[0]["category"] == "uncategorized"

    def test_update_with_case(self, engine):
        engine.sql(
            "UPDATE products SET category = "
            "CASE WHEN price > 20 THEN 'premium' ELSE 'standard' END"
        )
        r = engine.sql(
            "SELECT id, category FROM products ORDER BY id"
        )
        assert r.rows[0]["category"] == "standard"
        assert r.rows[1]["category"] == "premium"
        assert r.rows[2]["category"] == "standard"

    def test_update_with_string_function(self, engine):
        engine.sql("UPDATE products SET name = UPPER(name) WHERE id = 1")
        r = engine.sql("SELECT name FROM products WHERE id = 1")
        assert r.rows[0]["name"] == "WIDGET"

    def test_update_with_concat(self, engine):
        engine.sql(
            "UPDATE products SET name = name || ' (v2)' WHERE id = 1"
        )
        r = engine.sql("SELECT name FROM products WHERE id = 1")
        assert r.rows[0]["name"] == "Widget (v2)"


class TestUpdateConstraints:
    def test_update_not_null_violation(self, engine):
        with pytest.raises(ValueError, match="NOT NULL"):
            engine.sql("UPDATE products SET name = NULL WHERE id = 1")

    def test_update_unknown_column(self, engine):
        with pytest.raises(ValueError, match="Unknown column"):
            engine.sql("UPDATE products SET nonexistent = 1 WHERE id = 1")

    def test_update_nonexistent_table(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("UPDATE nonexistent SET x = 1")


class TestUpdateWithWhere:
    def test_update_where_is_null(self, engine):
        engine.sql(
            "UPDATE products SET category = 'misc' WHERE category IS NULL"
        )
        r = engine.sql("SELECT category FROM products WHERE id = 3")
        assert r.rows[0]["category"] == "misc"

    def test_update_where_is_not_null(self, engine):
        engine.sql(
            "UPDATE products SET price = price * 2 WHERE category IS NOT NULL"
        )
        r = engine.sql("SELECT id, price FROM products ORDER BY id")
        assert r.rows[0]["price"] == 21.0  # Widget
        assert r.rows[1]["price"] == 50.0  # Gadget
        assert r.rows[2]["price"] == 5.75  # Doohickey (NULL category)

    def test_update_where_in(self, engine):
        engine.sql("UPDATE products SET quantity = 0 WHERE id IN (1, 3)")
        r = engine.sql("SELECT id, quantity FROM products ORDER BY id")
        assert r.rows[0]["quantity"] == 0
        assert r.rows[1]["quantity"] == 50
        assert r.rows[2]["quantity"] == 0

    def test_update_where_between(self, engine):
        engine.sql(
            "UPDATE products SET category = 'mid' "
            "WHERE price BETWEEN 5 AND 15"
        )
        r = engine.sql(
            "SELECT id FROM products WHERE category = 'mid' ORDER BY id"
        )
        assert [row["id"] for row in r.rows] == [1, 3]

    def test_update_where_and(self, engine):
        engine.sql(
            "UPDATE products SET price = 0 "
            "WHERE category = 'tools' AND quantity > 50"
        )
        r = engine.sql("SELECT price FROM products WHERE id = 1")
        assert r.rows[0]["price"] == 0.0


class TestUpdateTextIndex:
    def test_update_reindexes_text(self, engine):
        """After UPDATE, text search should reflect new values."""
        # Before: Widget is searchable
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'widget')"
        )
        assert len(r.rows) == 1

        # Update the name
        engine.sql("UPDATE products SET name = 'Sprocket' WHERE id = 1")

        # 'widget' should no longer match
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'widget')"
        )
        assert len(r.rows) == 0

        # 'sprocket' should match
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'sprocket')"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 1

    def test_update_non_text_preserves_index(self, engine):
        """Updating non-text columns should preserve text search."""
        engine.sql("UPDATE products SET price = 99.99 WHERE id = 1")
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'widget')"
        )
        assert len(r.rows) == 1


# ==================================================================
# DELETE
# ==================================================================


class TestDeleteBasic:
    def test_delete_single_row(self, engine):
        r = engine.sql("DELETE FROM products WHERE id = 2")
        assert r.rows[0]["deleted"] == 1
        assert engine.sql("SELECT * FROM products WHERE id = 2").rows == []

    def test_delete_multiple_rows(self, engine):
        r = engine.sql("DELETE FROM products WHERE price < 20")
        assert r.rows[0]["deleted"] == 2
        r = engine.sql("SELECT id FROM products")
        assert [row["id"] for row in r.rows] == [2]

    def test_delete_all_rows(self, engine):
        r = engine.sql("DELETE FROM products")
        assert r.rows[0]["deleted"] == 3
        r = engine.sql("SELECT * FROM products")
        assert len(r.rows) == 0

    def test_delete_no_match(self, engine):
        r = engine.sql("DELETE FROM products WHERE id = 999")
        assert r.rows[0]["deleted"] == 0

    def test_delete_returns_count(self, engine):
        r = engine.sql("DELETE FROM products WHERE id = 1")
        assert r.columns == ["deleted"]
        assert r.rows[0]["deleted"] == 1

    def test_delete_nonexistent_table(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DELETE FROM nonexistent WHERE id = 1")


class TestDeleteWithWhere:
    def test_delete_where_is_null(self, engine):
        engine.sql("DELETE FROM products WHERE category IS NULL")
        r = engine.sql("SELECT id FROM products ORDER BY id")
        assert [row["id"] for row in r.rows] == [1, 2]

    def test_delete_where_is_not_null(self, engine):
        engine.sql("DELETE FROM products WHERE category IS NOT NULL")
        r = engine.sql("SELECT id FROM products")
        assert [row["id"] for row in r.rows] == [3]

    def test_delete_where_comparison(self, engine):
        engine.sql("DELETE FROM products WHERE price > 10")
        r = engine.sql("SELECT id FROM products ORDER BY id")
        assert [row["id"] for row in r.rows] == [3]

    def test_delete_where_and(self, engine):
        engine.sql(
            "DELETE FROM products "
            "WHERE category = 'tools' AND price > 5"
        )
        r = engine.sql("SELECT id FROM products ORDER BY id")
        assert [row["id"] for row in r.rows] == [2, 3]


class TestDeleteTextIndex:
    def test_delete_removes_from_index(self, engine):
        """After DELETE, text search should not find deleted rows."""
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'widget')"
        )
        assert len(r.rows) == 1

        engine.sql("DELETE FROM products WHERE id = 1")

        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'widget')"
        )
        assert len(r.rows) == 0

    def test_delete_preserves_other_index_entries(self, engine):
        """Deleting one doc should not affect other docs in the index."""
        engine.sql("DELETE FROM products WHERE id = 1")
        r = engine.sql(
            "SELECT id FROM products WHERE text_match(name, 'gadget')"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 2


# ==================================================================
# Persistence
# ==================================================================


class TestUpdateDeletePersistence:
    def test_update_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            with Engine(db_path=db) as e:
                e.sql(
                    "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)"
                )
                e.sql("INSERT INTO t (id, val) VALUES (1, 10), (2, 20)")
                e.sql("UPDATE t SET val = 99 WHERE id = 1")

            with Engine(db_path=db) as e:
                r = e.sql("SELECT id, val FROM t ORDER BY id")
                assert r.rows[0]["val"] == 99
                assert r.rows[1]["val"] == 20

    def test_delete_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            with Engine(db_path=db) as e:
                e.sql(
                    "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)"
                )
                e.sql("INSERT INTO t (id, val) VALUES (1, 10), (2, 20)")
                e.sql("DELETE FROM t WHERE id = 1")

            with Engine(db_path=db) as e:
                r = e.sql("SELECT id FROM t")
                assert len(r.rows) == 1
                assert r.rows[0]["id"] == 2

    def test_update_expression_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            with Engine(db_path=db) as e:
                e.sql(
                    "CREATE TABLE t ("
                    "id INTEGER PRIMARY KEY, "
                    "price REAL, "
                    "name TEXT"
                    ")"
                )
                e.sql(
                    "INSERT INTO t (id, price, name) "
                    "VALUES (1, 10.0, 'item')"
                )
                e.sql("UPDATE t SET price = price * 2, name = UPPER(name)")

            with Engine(db_path=db) as e:
                r = e.sql("SELECT price, name FROM t WHERE id = 1")
                assert r.rows[0]["price"] == 20.0
                assert r.rows[0]["name"] == "ITEM"


# ==================================================================
# Combined operations
# ==================================================================


class TestCombinedOperations:
    def test_insert_update_select(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity, category) "
            "VALUES (4, 'NewItem', 1.00, 1, 'new')"
        )
        engine.sql("UPDATE products SET price = 99.99 WHERE id = 4")
        r = engine.sql("SELECT price FROM products WHERE id = 4")
        assert r.rows[0]["price"] == 99.99

    def test_insert_delete_count(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity) "
            "VALUES (4, 'Extra', 1.00, 1)"
        )
        assert len(engine.sql("SELECT * FROM products").rows) == 4
        engine.sql("DELETE FROM products WHERE id = 4")
        assert len(engine.sql("SELECT * FROM products").rows) == 3

    def test_update_then_aggregate(self, engine):
        engine.sql("UPDATE products SET price = 10 WHERE price < 10")
        r = engine.sql("SELECT MIN(price) AS min_p FROM products")
        assert r.rows[0]["min_p"] == 10.0

    def test_delete_then_aggregate(self, engine):
        engine.sql("DELETE FROM products WHERE id = 3")
        r = engine.sql("SELECT COUNT(*) AS cnt FROM products")
        assert r.rows[0]["cnt"] == 2
