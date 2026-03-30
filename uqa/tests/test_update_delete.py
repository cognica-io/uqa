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
    e.sql("CREATE INDEX idx_products_gin ON products USING gin (name, category)")
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
        r = engine.sql("UPDATE products SET price = 15.00, quantity = 75 WHERE id = 2")
        assert r.rows[0]["updated"] == 1
        r = engine.sql("SELECT price, quantity FROM products WHERE id = 2")
        assert r.rows[0]["price"] == 15.0
        assert r.rows[0]["quantity"] == 75

    def test_update_multiple_rows(self, engine):
        r = engine.sql("UPDATE products SET category = 'sale' WHERE price < 20")
        assert r.rows[0]["updated"] == 2
        r = engine.sql("SELECT id FROM products WHERE category = 'sale' ORDER BY id")
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
        engine.sql("UPDATE products SET category = COALESCE(category, 'uncategorized')")
        r = engine.sql("SELECT id, category FROM products WHERE id = 3")
        assert r.rows[0]["category"] == "uncategorized"

    def test_update_with_case(self, engine):
        engine.sql(
            "UPDATE products SET category = "
            "CASE WHEN price > 20 THEN 'premium' ELSE 'standard' END"
        )
        r = engine.sql("SELECT id, category FROM products ORDER BY id")
        assert r.rows[0]["category"] == "standard"
        assert r.rows[1]["category"] == "premium"
        assert r.rows[2]["category"] == "standard"

    def test_update_with_string_function(self, engine):
        engine.sql("UPDATE products SET name = UPPER(name) WHERE id = 1")
        r = engine.sql("SELECT name FROM products WHERE id = 1")
        assert r.rows[0]["name"] == "WIDGET"

    def test_update_with_concat(self, engine):
        engine.sql("UPDATE products SET name = name || ' (v2)' WHERE id = 1")
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
        engine.sql("UPDATE products SET category = 'misc' WHERE category IS NULL")
        r = engine.sql("SELECT category FROM products WHERE id = 3")
        assert r.rows[0]["category"] == "misc"

    def test_update_where_is_not_null(self, engine):
        engine.sql("UPDATE products SET price = price * 2 WHERE category IS NOT NULL")
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
        engine.sql("UPDATE products SET category = 'mid' WHERE price BETWEEN 5 AND 15")
        r = engine.sql("SELECT id FROM products WHERE category = 'mid' ORDER BY id")
        assert [row["id"] for row in r.rows] == [1, 3]

    def test_update_where_and(self, engine):
        engine.sql(
            "UPDATE products SET price = 0 WHERE category = 'tools' AND quantity > 50"
        )
        r = engine.sql("SELECT price FROM products WHERE id = 1")
        assert r.rows[0]["price"] == 0.0


class TestUpdateTextIndex:
    def test_update_reindexes_text(self, engine):
        """After UPDATE, text search should reflect new values."""
        # Before: Widget is searchable
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'widget')")
        assert len(r.rows) == 1

        # Update the name
        engine.sql("UPDATE products SET name = 'Sprocket' WHERE id = 1")

        # 'widget' should no longer match
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'widget')")
        assert len(r.rows) == 0

        # 'sprocket' should match
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'sprocket')")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 1

    def test_update_non_text_preserves_index(self, engine):
        """Updating non-text columns should preserve text search."""
        engine.sql("UPDATE products SET price = 99.99 WHERE id = 1")
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'widget')")
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
        engine.sql("DELETE FROM products WHERE category = 'tools' AND price > 5")
        r = engine.sql("SELECT id FROM products ORDER BY id")
        assert [row["id"] for row in r.rows] == [2, 3]


class TestDeleteTextIndex:
    def test_delete_removes_from_index(self, engine):
        """After DELETE, text search should not find deleted rows."""
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'widget')")
        assert len(r.rows) == 1

        engine.sql("DELETE FROM products WHERE id = 1")

        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'widget')")
        assert len(r.rows) == 0

    def test_delete_preserves_other_index_entries(self, engine):
        """Deleting one doc should not affect other docs in the index."""
        engine.sql("DELETE FROM products WHERE id = 1")
        r = engine.sql("SELECT id FROM products WHERE text_match(name, 'gadget')")
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
                e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
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
                e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
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
                e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, price REAL, name TEXT)")
                e.sql("INSERT INTO t (id, price, name) VALUES (1, 10.0, 'item')")
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


# ==================================================================
# Fixtures for appended PG17 test classes
# ==================================================================


@pytest.fixture
def pg17_engine():
    return Engine()


@pytest.fixture
def engine_with_table(pg17_engine):
    pg17_engine.sql(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
    )
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (3, 'Carol', 35)")
    return pg17_engine


# ==================================================================
# INSERT ... RETURNING
# ==================================================================


class TestInsertReturning:
    def test_returning_star(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
        )
        result = pg17_engine.sql(
            "INSERT INTO t (id, name, age) VALUES (1, 'Alice', 30) RETURNING *"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[0]["age"] == 30

    def test_returning_specific_columns(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
        )
        result = pg17_engine.sql(
            "INSERT INTO t (id, name, age) VALUES (1, 'Alice', 30) RETURNING id, name"
        )
        assert result.columns == ["id", "name"]
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        assert "age" not in result.rows[0]

    def test_returning_with_alias(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        result = pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice') "
            "RETURNING id AS user_id, name AS user_name"
        )
        assert result.rows[0]["user_id"] == 1
        assert result.rows[0]["user_name"] == "Alice"

    def test_returning_multi_row(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        result = pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice'), (2, 'Bob') "
            "RETURNING id, name"
        )
        assert len(result.rows) == 2
        ids = [r["id"] for r in result.rows]
        assert 1 in ids
        assert 2 in ids

    def test_returning_serial(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        result = pg17_engine.sql("INSERT INTO t (name) VALUES ('Alice') RETURNING id")
        assert result.rows[0]["id"] == 1


# ==================================================================
# UPDATE ... RETURNING
# ==================================================================


class TestUpdateReturning:
    def test_returning_updated_values(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 31 WHERE id = 1 RETURNING id, age"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["age"] == 31

    def test_returning_star(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 99 WHERE id = 2 RETURNING *"
        )
        assert result.rows[0]["id"] == 2
        assert result.rows[0]["name"] == "Bob"
        assert result.rows[0]["age"] == 99

    def test_returning_multiple_rows(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = age + 1 WHERE age < 35 RETURNING id, age"
        )
        assert len(result.rows) == 2
        for row in result.rows:
            if row["id"] == 1:
                assert row["age"] == 31
            elif row["id"] == 2:
                assert row["age"] == 26

    def test_returning_no_match(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 0 WHERE id = 999 RETURNING id"
        )
        assert len(result.rows) == 0


# ==================================================================
# DELETE ... RETURNING
# ==================================================================


class TestDeleteReturning:
    def test_returning_deleted_row(self, engine_with_table):
        result = engine_with_table.sql("DELETE FROM users WHERE id = 1 RETURNING *")
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        # Verify row is actually gone
        check = engine_with_table.sql("SELECT COUNT(*) AS cnt FROM users WHERE id = 1")
        assert check.rows[0]["cnt"] == 0

    def test_returning_specific_columns(self, engine_with_table):
        result = engine_with_table.sql("DELETE FROM users WHERE id = 2 RETURNING name")
        assert result.columns == ["name"]
        assert result.rows[0]["name"] == "Bob"

    def test_returning_multiple_deletes(self, engine_with_table):
        result = engine_with_table.sql(
            "DELETE FROM users WHERE age >= 30 RETURNING id, name"
        )
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}

    def test_returning_no_match(self, engine_with_table):
        result = engine_with_table.sql("DELETE FROM users WHERE id = 999 RETURNING id")
        assert result.columns == ["id"]
        assert len(result.rows) == 0


# ==================================================================
# INSERT ... ON CONFLICT DO NOTHING
# ==================================================================


class TestOnConflictDoNothing:
    def test_skip_on_conflict(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        pg17_engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Bob') ON CONFLICT (id) DO NOTHING"
        )
        result = pg17_engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"

    def test_insert_non_conflicting(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        pg17_engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (2, 'Bob') ON CONFLICT (id) DO NOTHING"
        )
        result = pg17_engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2

    def test_multi_row_partial_conflict(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        pg17_engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Dup'), (2, 'Bob') "
            "ON CONFLICT (id) DO NOTHING"
        )
        result = pg17_engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2
        result = pg17_engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"


# ==================================================================
# INSERT ... ON CONFLICT DO UPDATE (UPSERT)
# ==================================================================


class TestOnConflictDoUpdate:
    def test_upsert_basic(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        pg17_engine.sql("INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)")
        pg17_engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 200) "
            "ON CONFLICT (id) DO UPDATE SET score = excluded.score"
        )
        result = pg17_engine.sql("SELECT score FROM t WHERE id = 1")
        assert result.rows[0]["score"] == 200

    def test_upsert_multiple_set_columns(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        pg17_engine.sql("INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)")
        pg17_engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alicia', 200) "
            "ON CONFLICT (id) DO UPDATE "
            "SET name = excluded.name, score = excluded.score"
        )
        result = pg17_engine.sql("SELECT name, score FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alicia"
        assert result.rows[0]["score"] == 200

    def test_upsert_no_conflict_inserts(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        pg17_engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice') "
            "ON CONFLICT (id) DO UPDATE SET name = excluded.name"
        )
        result = pg17_engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"

    def test_upsert_with_returning(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        pg17_engine.sql("INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)")
        result = pg17_engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 200) "
            "ON CONFLICT (id) DO UPDATE SET score = excluded.score "
            "RETURNING id, score"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["score"] == 200

    def test_upsert_on_unique_column(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER, email TEXT UNIQUE, name TEXT)")
        pg17_engine.sql(
            "INSERT INTO t (id, email, name) VALUES (1, 'a@b.com', 'Alice')"
        )
        pg17_engine.sql(
            "INSERT INTO t (id, email, name) "
            "VALUES (2, 'a@b.com', 'Bob') "
            "ON CONFLICT (email) DO UPDATE SET name = excluded.name"
        )
        result = pg17_engine.sql("SELECT name FROM t WHERE email = 'a@b.com'")
        assert result.rows[0]["name"] == "Bob"
        result = pg17_engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 1


# ==================================================================
# UPDATE ... FROM
# ==================================================================


class TestUpdateFrom:
    @pytest.fixture
    def uf_engine(self):
        e = Engine()
        e.sql(
            "CREATE TABLE employees "
            "(id INT PRIMARY KEY, name TEXT, dept_id INT, salary INT)"
        )
        e.sql("CREATE TABLE departments (id INT PRIMARY KEY, name TEXT, budget INT)")
        e.sql("INSERT INTO departments VALUES (1, 'Engineering', 100000)")
        e.sql("INSERT INTO departments VALUES (2, 'Sales', 50000)")
        e.sql("INSERT INTO employees VALUES (1, 'Alice', 1, 50000)")
        e.sql("INSERT INTO employees VALUES (2, 'Bob', 2, 40000)")
        e.sql("INSERT INTO employees VALUES (3, 'Charlie', 1, 60000)")
        yield e

    def test_basic_update_from(self, uf_engine):
        uf_engine.sql(
            "UPDATE employees SET salary = departments.budget / 2 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Engineering'"
        )
        r = uf_engine.sql("SELECT id, name, dept_id, salary FROM employees ORDER BY id")
        # Alice: Engineering budget 100000 / 2 = 50000
        assert r.rows[0]["salary"] == 50000
        # Bob: Sales, not updated
        assert r.rows[1]["salary"] == 40000
        # Charlie: Engineering budget 100000 / 2 = 50000
        assert r.rows[2]["salary"] == 50000

    def test_update_from_returning(self, uf_engine):
        r = uf_engine.sql(
            "UPDATE employees SET salary = 99999 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Sales' "
            "RETURNING employees.id, employees.salary"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 2
        assert r.rows[0]["salary"] == 99999

    def test_update_from_no_match(self, uf_engine):
        r = uf_engine.sql(
            "UPDATE employees SET salary = 0 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Marketing'"
        )
        assert r.rows[0]["updated"] == 0

    def test_update_from_multiple_matches(self, uf_engine):
        """UPDATE FROM updates both Engineering employees."""
        uf_engine.sql(
            "UPDATE employees SET salary = salary + 1000 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Engineering'"
        )
        r = uf_engine.sql("SELECT id, salary FROM employees ORDER BY id")
        assert r.rows[0]["salary"] == 51000  # Alice
        assert r.rows[1]["salary"] == 40000  # Bob unchanged
        assert r.rows[2]["salary"] == 61000  # Charlie


# ==================================================================
# DELETE ... USING
# ==================================================================


class TestDeleteUsing:
    @pytest.fixture
    def du_engine(self):
        e = Engine()
        e.sql("CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, total INT)")
        e.sql("CREATE TABLE blacklist (customer_id INT PRIMARY KEY)")
        e.sql("INSERT INTO orders VALUES (1, 10, 100)")
        e.sql("INSERT INTO orders VALUES (2, 20, 200)")
        e.sql("INSERT INTO orders VALUES (3, 10, 300)")
        e.sql("INSERT INTO blacklist VALUES (10)")
        yield e

    def test_basic_delete_using(self, du_engine):
        du_engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        r = du_engine.sql("SELECT id, customer_id, total FROM orders ORDER BY id")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 2

    def test_delete_using_returning(self, du_engine):
        r = du_engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id "
            "RETURNING orders.id"
        )
        assert len(r.rows) == 2
        ids = {row["id"] for row in r.rows}
        assert ids == {1, 3}

    def test_delete_using_no_match(self, du_engine):
        du_engine.sql("DELETE FROM blacklist WHERE customer_id = 10")
        r = du_engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        assert r.rows[0]["deleted"] == 0

    def test_delete_using_preserves_unmatched(self, du_engine):
        """Rows not matching the USING condition remain intact."""
        du_engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        r = du_engine.sql("SELECT id, customer_id, total FROM orders")
        assert len(r.rows) == 1
        assert r.rows[0]["customer_id"] == 20
        assert r.rows[0]["total"] == 200
