#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQL JOIN operations (INNER, LEFT, CROSS, RIGHT, FULL OUTER,
multiple FROM tables, and LATERAL)."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_orders(engine):
    """Two related tables: users and orders."""
    engine.sql(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
    )
    engine.sql("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    engine.sql("INSERT INTO users (id, name) VALUES (2, 'Bob')")
    engine.sql("INSERT INTO users (id, name) VALUES (3, 'Carol')")
    engine.sql(
        "CREATE TABLE orders ("
        "  oid INTEGER PRIMARY KEY, user_id INTEGER, product TEXT"
        ")"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) VALUES (10, 1, 'Book')"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) "
        "VALUES (11, 1, 'Pen')"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) "
        "VALUES (12, 2, 'Notebook')"
    )
    return engine


# ==================================================================
# INNER JOIN
# ==================================================================


class TestInnerJoin:
    def test_inner_join_basic(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        assert len(result.rows) == 3
        products = {r["product"] for r in result.rows}
        assert products == {"Book", "Pen", "Notebook"}

    def test_inner_join_excludes_unmatched(self, engine_with_orders):
        # Carol has no orders -- should not appear
        result = engine_with_orders.sql(
            "SELECT users.name "
            "FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        names = {r["name"] for r in result.rows}
        assert "Carol" not in names


# ==================================================================
# LEFT JOIN
# ==================================================================


class TestLeftJoin:
    def test_left_join_preserves_left(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        # Alice(2) + Bob(1) + Carol(unmatched) = 4 rows
        assert len(result.rows) == 4
        names = {r["name"] for r in result.rows}
        assert "Carol" in names

    def test_left_join_null_for_unmatched(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        carol_rows = [r for r in result.rows if r["name"] == "Carol"]
        assert len(carol_rows) == 1
        assert carol_rows[0].get("product") is None


# ==================================================================
# CROSS JOIN
# ==================================================================


class TestCrossJoin:
    def test_cross_join_cartesian(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("INSERT INTO a (id, val) VALUES (2, 'y')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        engine.sql("INSERT INTO b (id, label) VALUES (10, 'p')")
        engine.sql("INSERT INTO b (id, label) VALUES (20, 'q')")
        engine.sql("INSERT INTO b (id, label) VALUES (30, 'r')")
        result = engine.sql(
            "SELECT a.val, b.label FROM a CROSS JOIN b"
        )
        assert len(result.rows) == 6  # 2 * 3

    def test_cross_join_empty_side(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        result = engine.sql("SELECT * FROM a CROSS JOIN b")
        assert len(result.rows) == 0


# ==================================================================
# RIGHT JOIN
# ==================================================================


class TestRightJoin:
    def test_right_join_preserves_right(self, engine_with_orders):
        # All orders preserved, even if user is missing
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        )
        products = {r["product"] for r in result.rows}
        assert "Ghost" in products
        assert len(result.rows) == 4

    def test_right_join_null_for_unmatched_left(self, engine_with_orders):
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        )
        ghost_rows = [r for r in result.rows if r["product"] == "Ghost"]
        assert len(ghost_rows) == 1
        assert ghost_rows[0].get("name") is None


# ==================================================================
# FULL OUTER JOIN
# ==================================================================


class TestFullOuterJoin:
    def test_full_join_preserves_both(self, engine_with_orders):
        # Add order with no matching user
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users FULL OUTER JOIN orders "
            "ON users.id = orders.user_id"
        )
        # Alice(2) + Bob(1) + Carol(unmatched left) + Ghost(unmatched right) = 5
        assert len(result.rows) == 5
        names = {r.get("name") for r in result.rows}
        assert "Carol" in names
        products = {r.get("product") for r in result.rows}
        assert "Ghost" in products

    def test_full_join_no_overlap(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO b (id, val) VALUES (2, 'y')")
        result = engine.sql(
            "SELECT * FROM a FULL OUTER JOIN b ON a.id = b.id"
        )
        assert len(result.rows) == 2


# ==================================================================
# Multiple FROM tables
# ==================================================================


class TestMultipleFromTables:
    def test_implicit_cross_join(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("INSERT INTO a (id, val) VALUES (2, 'y')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        engine.sql("INSERT INTO b (id, label) VALUES (10, 'p')")
        engine.sql("INSERT INTO b (id, label) VALUES (20, 'q')")
        result = engine.sql("SELECT a.val, b.label FROM a, b")
        assert len(result.rows) == 4  # 2 * 2

    def test_implicit_cross_join_with_where(self, engine):
        engine.sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        engine.sql("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        engine.sql(
            "CREATE TABLE orders ("
            "  oid INTEGER PRIMARY KEY, user_id INTEGER, product TEXT"
            ")"
        )
        engine.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (10, 1, 'Book')"
        )
        engine.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (11, 2, 'Pen')"
        )
        result = engine.sql(
            "SELECT users.name, orders.product "
            "FROM users, orders "
            "WHERE users.id = orders.user_id"
        )
        assert len(result.rows) == 2

    def test_three_table_cross_join(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, x TEXT)")
        engine.sql("INSERT INTO a (id, x) VALUES (1, 'a')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, y TEXT)")
        engine.sql("INSERT INTO b (id, y) VALUES (1, 'b')")
        engine.sql("CREATE TABLE c (id INTEGER PRIMARY KEY, z TEXT)")
        engine.sql("INSERT INTO c (id, z) VALUES (1, 'c')")
        engine.sql("INSERT INTO c (id, z) VALUES (2, 'd')")
        result = engine.sql("SELECT a.x, b.y, c.z FROM a, b, c")
        assert len(result.rows) == 2  # 1 * 1 * 2


# ==================================================================
# LATERAL subquery
# ==================================================================


class TestLateral:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE depts (id INT PRIMARY KEY, dept_name TEXT)")
        e.sql(
            "CREATE TABLE emps "
            "(id INT PRIMARY KEY, emp_name TEXT, dept_id INT, salary INT)"
        )
        e.sql("INSERT INTO depts VALUES (1, 'Engineering')")
        e.sql("INSERT INTO depts VALUES (2, 'Sales')")
        e.sql("INSERT INTO emps VALUES (1, 'Alice', 1, 90000)")
        e.sql("INSERT INTO emps VALUES (2, 'Bob', 1, 80000)")
        e.sql("INSERT INTO emps VALUES (3, 'Charlie', 2, 70000)")
        e.sql("INSERT INTO emps VALUES (4, 'Diana', 2, 75000)")
        yield e

    def test_lateral_subquery_with_aggregate(self, engine):
        r = engine.sql(
            "SELECT d.dept_name, sub.top_salary "
            "FROM depts d, "
            "LATERAL (SELECT MAX(salary) AS top_salary "
            "FROM emps WHERE emps.dept_id = d.id) sub "
            "ORDER BY d.dept_name"
        )
        assert len(r.rows) == 2
        assert r.rows[0]["dept_name"] == "Engineering"
        assert r.rows[0]["top_salary"] == 90000
        assert r.rows[1]["dept_name"] == "Sales"
        assert r.rows[1]["top_salary"] == 75000

    def test_lateral_with_limit(self, engine):
        """LATERAL with ORDER BY + LIMIT, selecting the sort column."""
        r = engine.sql(
            "SELECT d.dept_name, sub.top_emp, sub.top_sal "
            "FROM depts d, "
            "LATERAL (SELECT emp_name AS top_emp, salary AS top_sal "
            "FROM emps WHERE emps.dept_id = d.id "
            "ORDER BY salary DESC LIMIT 1) sub "
            "ORDER BY d.dept_name"
        )
        assert len(r.rows) == 2
        # Top earner in Engineering: Alice (90000)
        assert r.rows[0]["top_emp"] == "Alice"
        assert r.rows[0]["top_sal"] == 90000
        # Top earner in Sales: Diana (75000)
        assert r.rows[1]["top_emp"] == "Diana"
        assert r.rows[1]["top_sal"] == 75000

    def test_lateral_with_count(self, engine):
        """LATERAL subquery returning a count per department."""
        r = engine.sql(
            "SELECT d.dept_name, sub.emp_count "
            "FROM depts d, "
            "LATERAL (SELECT COUNT(*) AS emp_count "
            "FROM emps WHERE emps.dept_id = d.id) sub "
            "ORDER BY d.dept_name"
        )
        assert r.rows[0]["dept_name"] == "Engineering"
        assert r.rows[0]["emp_count"] == 2
        assert r.rows[1]["dept_name"] == "Sales"
        assert r.rows[1]["emp_count"] == 2
