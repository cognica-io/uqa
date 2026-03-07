#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQL views (CREATE VIEW / DROP VIEW / SELECT from views)."""

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
        "(5, 'Eve', 'eng', 95000), "
        "(6, 'Frank', 'mkt', 80000)"
    )
    return e


# ==================================================================
# CREATE VIEW
# ==================================================================


class TestCreateView:
    def test_create_view_basic(self, engine):
        engine.sql(
            "CREATE VIEW eng_employees AS "
            "SELECT name, salary FROM employees WHERE dept = 'eng'"
        )
        assert "eng_employees" in engine._views

    def test_create_view_duplicate_raises(self, engine):
        engine.sql("CREATE VIEW v AS SELECT name FROM employees")
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("CREATE VIEW v AS SELECT name FROM employees")

    def test_create_view_name_conflicts_with_table(self, engine):
        with pytest.raises(ValueError, match="already exists as a table"):
            engine.sql(
                "CREATE VIEW employees AS SELECT name FROM employees"
            )


# ==================================================================
# SELECT from view
# ==================================================================


class TestSelectFromView:
    def test_select_all_from_view(self, engine):
        engine.sql(
            "CREATE VIEW eng AS "
            "SELECT name, salary FROM employees WHERE dept = 'eng'"
        )
        r = engine.sql("SELECT name FROM eng ORDER BY name")
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_view_with_filter(self, engine):
        engine.sql(
            "CREATE VIEW high_sal AS "
            "SELECT name, salary FROM employees WHERE salary > 80000"
        )
        r = engine.sql("SELECT name FROM high_sal WHERE salary > 90000")
        assert [row["name"] for row in r.rows] == ["Eve"]

    def test_view_with_aggregate(self, engine):
        engine.sql(
            "CREATE VIEW dept_stats AS "
            "SELECT dept, COUNT(*) AS cnt, AVG(salary) AS avg_sal "
            "FROM employees GROUP BY dept"
        )
        r = engine.sql("SELECT dept, cnt FROM dept_stats ORDER BY dept")
        assert r.rows[0]["dept"] == "eng"
        assert r.rows[0]["cnt"] == 3

    def test_view_with_order_and_limit(self, engine):
        engine.sql(
            "CREATE VIEW ranked AS "
            "SELECT name, salary FROM employees ORDER BY salary DESC"
        )
        r = engine.sql("SELECT name FROM ranked LIMIT 3")
        assert len(r.rows) == 3
        assert r.rows[0]["name"] == "Eve"

    def test_view_preserves_column_types(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name, salary FROM employees"
        )
        r = engine.sql("SELECT salary FROM v WHERE name = 'Alice'")
        assert r.rows[0]["salary"] == 90000.0

    def test_view_with_distinct(self, engine):
        engine.sql(
            "CREATE VIEW depts AS SELECT DISTINCT dept FROM employees"
        )
        r = engine.sql("SELECT dept FROM depts ORDER BY dept")
        assert [row["dept"] for row in r.rows] == ["eng", "mkt", "sales"]


# ==================================================================
# View cleanup (no leaking temporary tables)
# ==================================================================


class TestViewCleanup:
    def test_view_does_not_leak_temp_table(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name FROM employees"
        )
        engine.sql("SELECT name FROM v")
        # The temporary materialized table should be cleaned up;
        # only the original employees table should remain.
        assert "v" not in engine._tables
        assert "v" in engine._views

    def test_view_does_not_shadow_real_table(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name FROM employees LIMIT 1"
        )
        engine.sql("SELECT name FROM v")
        # Real table still works
        r = engine.sql("SELECT COUNT(*) AS cnt FROM employees")
        assert r.rows[0]["cnt"] == 6

    def test_multiple_view_queries(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name, salary FROM employees"
        )
        r1 = engine.sql("SELECT COUNT(*) AS cnt FROM v")
        r2 = engine.sql("SELECT name FROM v WHERE salary > 90000")
        assert r1.rows[0]["cnt"] == 6
        assert [row["name"] for row in r2.rows] == ["Eve"]


# ==================================================================
# DROP VIEW
# ==================================================================


class TestDropView:
    def test_drop_view(self, engine):
        engine.sql("CREATE VIEW v AS SELECT name FROM employees")
        engine.sql("DROP VIEW v")
        assert "v" not in engine._views

    def test_drop_view_if_exists(self, engine):
        # Should not raise
        engine.sql("DROP VIEW IF EXISTS nonexistent")

    def test_drop_view_nonexistent_raises(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DROP VIEW nonexistent")

    def test_drop_view_then_select_raises(self, engine):
        engine.sql("CREATE VIEW v AS SELECT name FROM employees")
        engine.sql("DROP VIEW v")
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("SELECT name FROM v")

    def test_recreate_view_after_drop(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name FROM employees WHERE dept = 'eng'"
        )
        engine.sql("DROP VIEW v")
        engine.sql(
            "CREATE VIEW v AS SELECT name FROM employees WHERE dept = 'mkt'"
        )
        r = engine.sql("SELECT name FROM v ORDER BY name")
        assert [row["name"] for row in r.rows] == ["Bob", "Frank"]


# ==================================================================
# Views with other SQL features
# ==================================================================


class TestViewIntegration:
    def test_view_reflects_data_changes(self, engine):
        engine.sql(
            "CREATE VIEW v AS SELECT name, salary FROM employees"
        )
        engine.sql(
            "INSERT INTO employees (id, name, dept, salary) VALUES "
            "(7, 'Grace', 'eng', 100000)"
        )
        r = engine.sql("SELECT COUNT(*) AS cnt FROM v")
        assert r.rows[0]["cnt"] == 7

    def test_view_with_window_function(self, engine):
        engine.sql(
            "CREATE VIEW ranked AS "
            "SELECT name, salary, "
            "ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn "
            "FROM employees"
        )
        r = engine.sql("SELECT name, rn FROM ranked WHERE rn <= 3 ORDER BY rn")
        assert len(r.rows) == 3
        assert r.rows[0]["name"] == "Eve"

    def test_view_used_in_subquery(self, engine):
        engine.sql(
            "CREATE VIEW eng_ids AS "
            "SELECT id FROM employees WHERE dept = 'eng'"
        )
        r = engine.sql(
            "SELECT name FROM employees "
            "WHERE id IN (SELECT id FROM eng_ids) "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Alice", "Carol", "Eve"]

    def test_view_of_view(self, engine):
        engine.sql(
            "CREATE VIEW high_sal AS "
            "SELECT name, salary FROM employees WHERE salary > 80000"
        )
        engine.sql(
            "CREATE VIEW very_high AS "
            "SELECT name FROM high_sal WHERE salary > 90000"
        )
        r = engine.sql("SELECT name FROM very_high")
        assert [row["name"] for row in r.rows] == ["Eve"]

    def test_cte_and_view_together(self, engine):
        engine.sql(
            "CREATE VIEW eng AS "
            "SELECT name, salary FROM employees WHERE dept = 'eng'"
        )
        r = engine.sql(
            "WITH top AS (SELECT name FROM eng WHERE salary > 90000) "
            "SELECT name FROM top"
        )
        assert [row["name"] for row in r.rows] == ["Eve"]
