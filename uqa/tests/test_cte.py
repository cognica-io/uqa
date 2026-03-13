#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Common Table Expressions (WITH ... AS)."""

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
        "(5, 'Eve', 1, 95000)"
    )
    return e


# ==================================================================
# Basic CTE
# ==================================================================


class TestCTEBasic:
    def test_simple_cte(self, engine):
        r = engine.sql(
            "WITH eng AS ("
            "  SELECT name FROM employees WHERE dept_id = 1"
            ") "
            "SELECT name FROM eng ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_cte_with_filter(self, engine):
        r = engine.sql(
            "WITH high_sal AS ("
            "  SELECT name, salary FROM employees WHERE salary > 80000"
            ") "
            "SELECT name FROM high_sal WHERE salary > 90000"
        )
        assert [row["name"] for row in r.rows] == ["Eve"]

    def test_cte_with_aggregate(self, engine):
        r = engine.sql(
            "WITH dept_stats AS ("
            "  SELECT dept_id, COUNT(*) AS cnt, AVG(salary) AS avg_sal "
            "  FROM employees GROUP BY dept_id"
            ") "
            "SELECT dept_id, cnt FROM dept_stats ORDER BY dept_id"
        )
        assert r.rows[0]["dept_id"] == 1
        assert r.rows[0]["cnt"] == 3
        assert r.rows[1]["cnt"] == 1
        assert r.rows[2]["cnt"] == 1

    def test_cte_with_order_and_limit(self, engine):
        r = engine.sql(
            "WITH ranked AS ("
            "  SELECT name, salary FROM employees ORDER BY salary DESC"
            ") "
            "SELECT name FROM ranked LIMIT 3"
        )
        names = [row["name"] for row in r.rows]
        assert len(names) == 3
        assert names[0] == "Eve"

    def test_cte_cleanup(self, engine):
        """CTE temporary tables should be cleaned up after query."""
        engine.sql("WITH temp_cte AS (SELECT 1 AS val) SELECT val FROM temp_cte")
        # The CTE table should not exist after the query
        assert "temp_cte" not in engine._tables

    def test_cte_does_not_shadow_real_table(self, engine):
        """After CTE query, real table is still accessible."""
        engine.sql("WITH x AS (SELECT name FROM employees LIMIT 1) SELECT name FROM x")
        r = engine.sql("SELECT COUNT(*) AS cnt FROM employees")
        assert r.rows[0]["cnt"] == 5


# ==================================================================
# Multiple CTEs
# ==================================================================


class TestMultipleCTEs:
    def test_two_ctes(self, engine):
        r = engine.sql(
            "WITH "
            "  eng AS (SELECT id, name FROM employees WHERE dept_id = 1), "
            "  mkt AS (SELECT id, name FROM employees WHERE dept_id = 2) "
            "SELECT name FROM eng ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_second_cte_used(self, engine):
        r = engine.sql(
            "WITH "
            "  eng AS (SELECT name FROM employees WHERE dept_id = 1), "
            "  mkt AS (SELECT name FROM employees WHERE dept_id = 2) "
            "SELECT name FROM mkt"
        )
        assert [row["name"] for row in r.rows] == ["Bob"]

    def test_cte_referencing_another(self, engine):
        """A CTE can reference a previously defined CTE."""
        r = engine.sql(
            "WITH "
            "  high_sal AS (SELECT name, salary FROM employees WHERE salary > 80000), "
            "  very_high AS (SELECT name FROM high_sal WHERE salary > 90000) "
            "SELECT name FROM very_high"
        )
        assert [row["name"] for row in r.rows] == ["Eve"]


# ==================================================================
# CTE with subqueries
# ==================================================================


class TestCTEWithSubquery:
    def test_cte_used_in_subquery(self, engine):
        """CTE can be referenced in a subquery."""
        r = engine.sql(
            "WITH eng_ids AS ("
            "  SELECT id FROM employees WHERE dept_id = 1"
            ") "
            "SELECT name FROM employees "
            "WHERE id IN (SELECT id FROM eng_ids) "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_cte_with_distinct(self, engine):
        r = engine.sql(
            "WITH dept_ids AS ("
            "  SELECT DISTINCT dept_id FROM employees"
            ") "
            "SELECT dept_id FROM dept_ids ORDER BY dept_id"
        )
        assert [row["dept_id"] for row in r.rows] == [1, 2, 3]


# ==================================================================
# Fixture for appended PG17 test classes
# ==================================================================


@pytest.fixture
def pg17_engine():
    return Engine()


# ==================================================================
# WITH RECURSIVE
# ==================================================================


class TestWithRecursive:
    def test_recursive_count(self, pg17_engine):
        result = pg17_engine.sql(
            "WITH RECURSIVE cnt(x) AS ("
            "  SELECT 1"
            "  UNION ALL"
            "  SELECT x + 1 FROM cnt WHERE x < 5"
            ") SELECT x FROM cnt"
        )
        values = [r["x"] for r in result.rows]
        assert values == [1, 2, 3, 4, 5]

    def test_recursive_union_dedup(self, pg17_engine):
        # UNION (not ALL) should deduplicate
        result = pg17_engine.sql(
            "WITH RECURSIVE seq(n) AS ("
            "  SELECT 1"
            "  UNION"
            "  SELECT n + 1 FROM seq WHERE n < 3"
            ") SELECT n FROM seq"
        )
        values = sorted(r["n"] for r in result.rows)
        assert values == [1, 2, 3]

    def test_recursive_hierarchy(self, pg17_engine):
        pg17_engine.sql(
            "CREATE TABLE employees ("
            "  eid INTEGER PRIMARY KEY, ename TEXT, manager_id INTEGER"
            ")"
        )
        pg17_engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) VALUES (1, 'CEO', 0)"
        )
        pg17_engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) VALUES (2, 'VP', 1)"
        )
        pg17_engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) VALUES (3, 'Manager', 2)"
        )
        pg17_engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) VALUES (4, 'Developer', 3)"
        )
        # Use distinct column names to avoid collision in join
        result = pg17_engine.sql(
            "WITH RECURSIVE chain(cid, cname, lvl) AS ("
            "  SELECT eid, ename, 0 FROM employees WHERE eid = 1"
            "  UNION ALL"
            "  SELECT e.eid, e.ename, c.lvl + 1 "
            "  FROM employees e "
            "  INNER JOIN chain c ON e.manager_id = c.cid"
            ") SELECT cname, lvl FROM chain"
        )
        assert len(result.rows) == 4
        names = {r["cname"] for r in result.rows}
        assert names == {"CEO", "VP", "Manager", "Developer"}

    def test_recursive_empty_base(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        result = pg17_engine.sql(
            "WITH RECURSIVE r(n) AS ("
            "  SELECT id FROM t WHERE id = 999"
            "  UNION ALL"
            "  SELECT n + 1 FROM r WHERE n < 5"
            ") SELECT n FROM r"
        )
        assert len(result.rows) == 0
