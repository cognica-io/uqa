#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for subquery support: IN (SELECT ...), EXISTS, scalar subqueries."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    e = Engine()
    e.sql("CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    e.sql(
        "INSERT INTO departments (id, name) VALUES "
        "(1, 'Engineering'), "
        "(2, 'Marketing'), "
        "(3, 'Sales')"
    )
    e.sql(
        "CREATE TABLE employees ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "dept_id INTEGER, "
        "salary REAL"
        ")"
    )
    e.sql(
        "INSERT INTO employees (id, name, dept_id, salary) VALUES "
        "(1, 'Alice', 1, 90000), "
        "(2, 'Bob', 2, 75000), "
        "(3, 'Carol', 1, 85000), "
        "(4, 'Dave', 3, 70000), "
        "(5, 'Eve', NULL, 95000)"
    )
    return e


# ==================================================================
# IN (SELECT ...)
# ==================================================================


class TestInSubquery:
    def test_in_subquery_basic(self, engine):
        """WHERE col IN (SELECT ...) filters using subquery results."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments WHERE name = 'Engineering') "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol"]

    def test_in_subquery_multiple_values(self, engine):
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments WHERE name != 'Sales') "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Bob", "Carol"]

    def test_in_subquery_no_match(self, engine):
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments WHERE name = 'HR')"
        )
        assert r.rows == []

    def test_in_subquery_null_excluded(self, engine):
        """NULL dept_id should not match IN subquery results."""
        r = engine.sql(
            "SELECT name FROM employees WHERE dept_id IN (SELECT id FROM departments)"
        )
        # Eve has NULL dept_id, should not appear
        names = sorted(row["name"] for row in r.rows)
        assert "Eve" not in names
        assert len(names) == 4

    def test_not_in_subquery(self, engine):
        """NOT IN subquery via NOT (...IN (SELECT ...))."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id NOT IN (SELECT id FROM departments WHERE name = 'Engineering') "
            "ORDER BY name"
        )
        # Bob (Marketing), Dave (Sales), Eve (NULL dept_id passes complement)
        assert [row["name"] for row in r.rows] == ["Bob", "Dave", "Eve"]

    def test_in_subquery_with_aggregate(self, engine):
        """Subquery with aggregate function."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE salary IN ("
            "  SELECT MAX(salary) AS max_sal FROM employees"
            ") "
            "ORDER BY name"
        )
        # Eve has highest salary (95000)
        assert [row["name"] for row in r.rows] == ["Eve"]


# ==================================================================
# EXISTS (SELECT ...)
# ==================================================================


class TestExistsSubquery:
    def test_exists_true(self, engine):
        """EXISTS returns all rows when subquery has results."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE EXISTS (SELECT 1 FROM departments WHERE name = 'Engineering') "
            "ORDER BY name"
        )
        # Subquery returns rows, so all employees are returned
        assert len(r.rows) == 5

    def test_exists_false(self, engine):
        """EXISTS returns no rows when subquery is empty."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE EXISTS (SELECT 1 FROM departments WHERE name = 'HR')"
        )
        assert r.rows == []

    def test_not_exists(self, engine):
        """NOT EXISTS inverts the EXISTS check."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE NOT EXISTS (SELECT 1 FROM departments WHERE name = 'HR') "
            "ORDER BY name"
        )
        # Subquery is empty, NOT EXISTS is true, all rows returned
        assert len(r.rows) == 5

    def test_not_exists_with_results(self, engine):
        """NOT EXISTS with non-empty subquery returns nothing."""
        r = engine.sql(
            "SELECT name FROM employees WHERE NOT EXISTS (SELECT 1 FROM departments)"
        )
        assert r.rows == []


# ==================================================================
# Scalar subquery in SELECT
# ==================================================================


class TestScalarSubquery:
    def test_scalar_subquery_in_select(self, engine):
        """Scalar subquery returns a single value in SELECT."""
        r = engine.sql(
            "SELECT name, "
            "(SELECT COUNT(*) FROM departments) AS dept_count "
            "FROM employees ORDER BY name LIMIT 1"
        )
        assert r.rows[0]["name"] == "Alice"
        assert r.rows[0]["dept_count"] == 3

    def test_scalar_subquery_aggregate(self, engine):
        r = engine.sql(
            "SELECT name, "
            "(SELECT MAX(salary) FROM employees) AS max_salary "
            "FROM employees WHERE id = 1"
        )
        assert r.rows[0]["max_salary"] == 95000

    def test_scalar_subquery_empty(self, engine):
        """Scalar subquery with no rows returns NULL."""
        r = engine.sql(
            "SELECT name, "
            "(SELECT salary FROM employees WHERE id = 999) AS other_sal "
            "FROM employees WHERE id = 1"
        )
        assert r.rows[0]["other_sal"] is None


# ==================================================================
# Subqueries with other features
# ==================================================================


class TestSubqueryIntegration:
    def test_in_subquery_with_like(self, engine):
        """IN subquery combined with LIKE in the inner query."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN ("
            "  SELECT id FROM departments WHERE name LIKE 'Eng%'"
            ") ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol"]

    def test_in_subquery_with_order_and_limit(self, engine):
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments) "
            "ORDER BY name LIMIT 2"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Bob"]

    def test_in_subquery_with_and(self, engine):
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments WHERE name = 'Engineering') "
            "AND salary > 87000"
        )
        assert [row["name"] for row in r.rows] == ["Alice"]

    def test_multiple_subquery_conditions(self, engine):
        """Multiple IN subqueries combined with AND."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN (SELECT id FROM departments) "
            "AND salary IN (SELECT salary FROM employees WHERE salary >= 85000) "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol"]
