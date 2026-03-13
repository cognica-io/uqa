#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for prepared statements (PREPARE / EXECUTE / DEALLOCATE)."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    e = Engine()
    e.sql(
        "CREATE TABLE employees ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "dept TEXT, "
        "salary REAL"
        ")"
    )
    e.sql(
        "INSERT INTO employees (id, name, dept, salary) VALUES "
        "(1, 'Alice', 'eng', 90000), "
        "(2, 'Bob', 'mkt', 75000), "
        "(3, 'Carol', 'eng', 85000), "
        "(4, 'Dave', 'sales', 70000), "
        "(5, 'Eve', 'eng', 95000)"
    )
    return e


# ==================================================================
# PREPARE
# ==================================================================


class TestPrepare:
    def test_prepare_select(self, engine):
        engine.sql(
            "PREPARE get_by_id (INTEGER) AS SELECT name FROM employees WHERE id = $1"
        )
        assert "get_by_id" in engine._prepared

    def test_prepare_duplicate_raises(self, engine):
        engine.sql("PREPARE q AS SELECT name FROM employees")
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("PREPARE q AS SELECT name FROM employees")

    def test_prepare_insert(self, engine):
        engine.sql(
            "PREPARE ins AS "
            "INSERT INTO employees (id, name, dept, salary) "
            "VALUES ($1, $2, $3, $4)"
        )
        assert "ins" in engine._prepared

    def test_prepare_update(self, engine):
        engine.sql("PREPARE upd AS UPDATE employees SET salary = $1 WHERE id = $2")
        assert "upd" in engine._prepared

    def test_prepare_delete(self, engine):
        engine.sql("PREPARE del AS DELETE FROM employees WHERE id = $1")
        assert "del" in engine._prepared


# ==================================================================
# EXECUTE
# ==================================================================


class TestExecute:
    def test_execute_select_single_param(self, engine):
        engine.sql("PREPARE get_by_id AS SELECT name FROM employees WHERE id = $1")
        r = engine.sql("EXECUTE get_by_id (1)")
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Alice"

    def test_execute_select_different_params(self, engine):
        engine.sql("PREPARE get_by_id AS SELECT name FROM employees WHERE id = $1")
        r1 = engine.sql("EXECUTE get_by_id (1)")
        r2 = engine.sql("EXECUTE get_by_id (3)")
        assert r1.rows[0]["name"] == "Alice"
        assert r2.rows[0]["name"] == "Carol"

    def test_execute_select_multiple_params(self, engine):
        engine.sql(
            "PREPARE get_by_dept_sal AS "
            "SELECT name FROM employees "
            "WHERE dept = $1 AND salary > $2 "
            "ORDER BY name"
        )
        r = engine.sql("EXECUTE get_by_dept_sal ('eng', 87000)")
        assert [row["name"] for row in r.rows] == ["Alice", "Eve"]

    def test_execute_insert(self, engine):
        engine.sql(
            "PREPARE ins AS "
            "INSERT INTO employees (id, name, dept, salary) "
            "VALUES ($1, $2, $3, $4)"
        )
        engine.sql("EXECUTE ins (6, 'Frank', 'mkt', 80000)")
        r = engine.sql("SELECT name FROM employees WHERE id = 6")
        assert r.rows[0]["name"] == "Frank"

    def test_execute_update(self, engine):
        engine.sql("PREPARE upd AS UPDATE employees SET salary = $1 WHERE id = $2")
        engine.sql("EXECUTE upd (100000, 1)")
        r = engine.sql("SELECT salary FROM employees WHERE id = 1")
        assert r.rows[0]["salary"] == 100000.0

    def test_execute_delete(self, engine):
        engine.sql("PREPARE del AS DELETE FROM employees WHERE id = $1")
        engine.sql("EXECUTE del (4)")
        r = engine.sql("SELECT COUNT(*) AS cnt FROM employees")
        assert r.rows[0]["cnt"] == 4

    def test_execute_nonexistent_raises(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("EXECUTE nonexistent (1)")

    def test_execute_missing_param_raises(self, engine):
        engine.sql(
            "PREPARE q AS SELECT name FROM employees WHERE id = $1 AND dept = $2"
        )
        with pytest.raises(ValueError, match="No value supplied"):
            engine.sql("EXECUTE q (1)")

    def test_execute_reusable(self, engine):
        """Prepared statement can be executed multiple times."""
        engine.sql("PREPARE get_name AS SELECT name FROM employees WHERE id = $1")
        names = []
        for i in range(1, 6):
            r = engine.sql(f"EXECUTE get_name ({i})")
            names.append(r.rows[0]["name"])
        assert names == ["Alice", "Bob", "Carol", "Dave", "Eve"]


# ==================================================================
# DEALLOCATE
# ==================================================================


class TestDeallocate:
    def test_deallocate(self, engine):
        engine.sql("PREPARE q AS SELECT name FROM employees")
        engine.sql("DEALLOCATE q")
        assert "q" not in engine._prepared

    def test_deallocate_nonexistent_raises(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DEALLOCATE nonexistent")

    def test_deallocate_all(self, engine):
        engine.sql("PREPARE q1 AS SELECT name FROM employees")
        engine.sql("PREPARE q2 AS SELECT dept FROM employees")
        engine.sql("DEALLOCATE ALL")
        assert len(engine._prepared) == 0

    def test_execute_after_deallocate_raises(self, engine):
        engine.sql("PREPARE q AS SELECT name FROM employees WHERE id = $1")
        engine.sql("DEALLOCATE q")
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("EXECUTE q (1)")

    def test_reprepare_after_deallocate(self, engine):
        engine.sql("PREPARE q AS SELECT name FROM employees WHERE dept = $1")
        engine.sql("DEALLOCATE q")
        engine.sql("PREPARE q AS SELECT salary FROM employees WHERE id = $1")
        r = engine.sql("EXECUTE q (1)")
        assert r.rows[0]["salary"] == 90000.0


# ==================================================================
# Edge cases and integration
# ==================================================================


class TestPreparedIntegration:
    def test_prepare_with_typed_params(self, engine):
        engine.sql("PREPARE q (INTEGER) AS SELECT name FROM employees WHERE id = $1")
        r = engine.sql("EXECUTE q (2)")
        assert r.rows[0]["name"] == "Bob"

    def test_prepare_select_with_order_and_limit(self, engine):
        engine.sql(
            "PREPARE top_earners AS "
            "SELECT name, salary FROM employees "
            "WHERE dept = $1 ORDER BY salary DESC LIMIT 2"
        )
        r = engine.sql("EXECUTE top_earners ('eng')")
        assert len(r.rows) == 2
        assert r.rows[0]["name"] == "Eve"
        assert r.rows[1]["name"] == "Alice"

    def test_prepare_select_no_params(self, engine):
        engine.sql("PREPARE all_names AS SELECT name FROM employees ORDER BY name")
        r = engine.sql("EXECUTE all_names")
        assert [row["name"] for row in r.rows] == [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
            "Eve",
        ]

    def test_prepare_with_null_param(self, engine):
        engine.sql(
            "INSERT INTO employees (id, name, dept, salary) VALUES "
            "(6, 'Frank', NULL, 80000)"
        )
        engine.sql(
            "PREPARE get_null_dept AS SELECT name FROM employees WHERE dept IS NULL"
        )
        r = engine.sql("EXECUTE get_null_dept")
        assert r.rows[0]["name"] == "Frank"

    def test_multiple_prepared_coexist(self, engine):
        engine.sql("PREPARE by_id AS SELECT name FROM employees WHERE id = $1")
        engine.sql(
            "PREPARE by_dept AS "
            "SELECT name FROM employees WHERE dept = $1 ORDER BY name"
        )
        r1 = engine.sql("EXECUTE by_id (1)")
        r2 = engine.sql("EXECUTE by_dept ('eng')")
        assert r1.rows[0]["name"] == "Alice"
        assert [row["name"] for row in r2.rows] == ["Alice", "Carol", "Eve"]
