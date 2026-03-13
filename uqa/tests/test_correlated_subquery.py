#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for correlated subqueries."""

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
        "(5, 'Eve', 1, 95000), "
        "(6, 'Frank', 2, 80000)"
    )
    return e


# ==================================================================
# Correlated scalar subqueries (WHERE col op (SELECT ...))
# ==================================================================


class TestCorrelatedScalar:
    def test_salary_above_dept_avg(self, engine):
        """Employees earning more than their department average."""
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE e.salary > ("
            "  SELECT AVG(salary) FROM employees "
            "  WHERE dept_id = e.dept_id"
            ") ORDER BY e.name"
        )
        # eng avg = 90000, mkt avg = 77500, sales avg = 70000
        # Above avg: Eve(95k > 90k), Frank(80k > 77.5k)
        # Alice(90k = 90k) is NOT above avg
        assert [row["name"] for row in r.rows] == ["Eve", "Frank"]

    def test_salary_equal_dept_max(self, engine):
        """Employees earning exactly the department maximum."""
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE e.salary = ("
            "  SELECT MAX(salary) FROM employees "
            "  WHERE dept_id = e.dept_id"
            ") ORDER BY e.name"
        )
        # eng max = 95k (Eve), mkt max = 80k (Frank), sales max = 70k (Dave)
        assert [row["name"] for row in r.rows] == ["Dave", "Eve", "Frank"]

    def test_correlated_count(self, engine):
        """Employees in departments with more than 1 person."""
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE ("
            "  SELECT COUNT(*) FROM employees "
            "  WHERE dept_id = e.dept_id"
            ") > 1 "
            "ORDER BY e.name"
        )
        # eng has 3, mkt has 2, sales has 1
        assert [row["name"] for row in r.rows] == [
            "Alice",
            "Bob",
            "Carol",
            "Eve",
            "Frank",
        ]


# ==================================================================
# Correlated EXISTS
# ==================================================================


class TestCorrelatedExists:
    def test_exists_basic(self, engine):
        """Departments that have at least one employee."""
        r = engine.sql(
            "SELECT d.name FROM departments d "
            "WHERE EXISTS ("
            "  SELECT 1 FROM employees e WHERE e.dept_id = d.id"
            ") ORDER BY d.name"
        )
        assert [row["name"] for row in r.rows] == ["Engineering", "Marketing", "Sales"]

    def test_not_exists(self, engine):
        """Departments with no employees."""
        engine.sql("INSERT INTO departments (id, name) VALUES (4, 'HR')")
        r = engine.sql(
            "SELECT d.name FROM departments d "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM employees e WHERE e.dept_id = d.id"
            ") ORDER BY d.name"
        )
        assert [row["name"] for row in r.rows] == ["HR"]

    def test_exists_with_additional_condition(self, engine):
        """Departments that have high earners (salary > 90000)."""
        r = engine.sql(
            "SELECT d.name FROM departments d "
            "WHERE EXISTS ("
            "  SELECT 1 FROM employees e "
            "  WHERE e.dept_id = d.id AND e.salary > 90000"
            ") ORDER BY d.name"
        )
        # Only Engineering has Eve at 95000
        assert [row["name"] for row in r.rows] == ["Engineering"]


# ==================================================================
# Correlated IN
# ==================================================================


class TestCorrelatedIn:
    def test_correlated_in(self, engine):
        """Employees whose dept_id is in departments with name starting
        with specific pattern."""
        engine.sql(
            "CREATE TABLE managers ("
            "id INTEGER PRIMARY KEY, "
            "dept_id INTEGER, "
            "level INTEGER"
            ")"
        )
        engine.sql(
            "INSERT INTO managers (id, dept_id, level) VALUES (1, 1, 5), (2, 2, 3)"
        )
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE e.dept_id IN ("
            "  SELECT m.dept_id FROM managers m "
            "  WHERE m.level > 2"
            ") ORDER BY e.name"
        )
        # Non-correlated IN -- managers with level > 2 -> dept_id 1, 2
        assert [row["name"] for row in r.rows] == [
            "Alice",
            "Bob",
            "Carol",
            "Eve",
            "Frank",
        ]


# ==================================================================
# Mixed and edge cases
# ==================================================================


class TestCorrelatedEdgeCases:
    def test_correlated_with_min(self, engine):
        """Correlated subquery using MIN."""
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE e.salary = ("
            "  SELECT MIN(salary) FROM employees "
            "  WHERE dept_id = e.dept_id"
            ") ORDER BY e.name"
        )
        # eng min = 85k (Carol), mkt min = 75k (Bob), sales min = 70k (Dave)
        assert [row["name"] for row in r.rows] == ["Bob", "Carol", "Dave"]

    def test_correlated_subquery_in_and(self, engine):
        """Correlated subquery combined with regular WHERE condition."""
        r = engine.sql(
            "SELECT e.name FROM employees e "
            "WHERE e.dept_id = 1 AND e.salary > ("
            "  SELECT AVG(salary) FROM employees "
            "  WHERE dept_id = e.dept_id"
            ") ORDER BY e.name"
        )
        # eng avg = 90000; only Eve (95k) is above
        assert [row["name"] for row in r.rows] == ["Eve"]

    def test_non_correlated_still_works(self, engine):
        """Ensure non-correlated subqueries still work after changes."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE dept_id IN ("
            "  SELECT id FROM departments WHERE name = 'Engineering'"
            ") ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_exists_non_correlated_still_works(self, engine):
        """Non-correlated EXISTS still works."""
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE EXISTS (SELECT 1 FROM departments WHERE id = 1) "
            "ORDER BY name"
        )
        assert len(r.rows) == 6
