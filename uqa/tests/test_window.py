#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, etc.)."""

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
# ROW_NUMBER
# ==================================================================


class TestRowNumber:
    def test_row_number_basic(self, engine):
        r = engine.sql(
            "SELECT name, ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn "
            "FROM employees"
        )
        # Sorted by salary DESC: Eve(95k), Alice(90k), Carol(85k),
        # Frank(80k), Bob(75k), Dave(70k)
        rows_by_rn = {row["rn"]: row["name"] for row in r.rows}
        assert rows_by_rn[1] == "Eve"
        assert rows_by_rn[2] == "Alice"
        assert rows_by_rn[6] == "Dave"

    def test_row_number_with_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, "
            "ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn "
            "FROM employees"
        )
        eng_rows = sorted(
            [(row["rn"], row["name"]) for row in r.rows if row["dept"] == "eng"]
        )
        assert eng_rows == [(1, "Eve"), (2, "Alice"), (3, "Carol")]

    def test_row_number_asc(self, engine):
        r = engine.sql(
            "SELECT name, ROW_NUMBER() OVER (ORDER BY salary) AS rn "
            "FROM employees"
        )
        rows_by_rn = {row["rn"]: row["name"] for row in r.rows}
        assert rows_by_rn[1] == "Dave"  # lowest salary
        assert rows_by_rn[6] == "Eve"   # highest salary


# ==================================================================
# RANK / DENSE_RANK
# ==================================================================


class TestRank:
    def test_rank_basic(self, engine):
        # Add duplicate salary
        engine.sql(
            "INSERT INTO employees (id, name, dept, salary) VALUES "
            "(7, 'Grace', 'eng', 90000)"
        )
        r = engine.sql(
            "SELECT name, RANK() OVER (ORDER BY salary DESC) AS rnk "
            "FROM employees"
        )
        rank_map = {row["name"]: row["rnk"] for row in r.rows}
        assert rank_map["Eve"] == 1
        # Alice and Grace tie at 90000 -> both rank 2
        assert rank_map["Alice"] == 2
        assert rank_map["Grace"] == 2
        # Carol at 85000 -> rank 4 (skips 3)
        assert rank_map["Carol"] == 4

    def test_dense_rank(self, engine):
        engine.sql(
            "INSERT INTO employees (id, name, dept, salary) VALUES "
            "(7, 'Grace', 'eng', 90000)"
        )
        r = engine.sql(
            "SELECT name, DENSE_RANK() OVER (ORDER BY salary DESC) AS drnk "
            "FROM employees"
        )
        rank_map = {row["name"]: row["drnk"] for row in r.rows}
        assert rank_map["Eve"] == 1
        assert rank_map["Alice"] == 2
        assert rank_map["Grace"] == 2
        # Carol at 85000 -> dense_rank 3 (no gap)
        assert rank_map["Carol"] == 3

    def test_rank_with_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, "
            "RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk "
            "FROM employees"
        )
        eng_ranks = {
            row["name"]: row["rnk"]
            for row in r.rows if row["dept"] == "eng"
        }
        assert eng_ranks["Eve"] == 1
        assert eng_ranks["Alice"] == 2
        assert eng_ranks["Carol"] == 3


# ==================================================================
# LAG / LEAD
# ==================================================================


class TestLagLead:
    def test_lag_basic(self, engine):
        r = engine.sql(
            "SELECT name, salary, "
            "LAG(salary, 1) OVER (ORDER BY salary) AS prev_sal "
            "FROM employees"
        )
        rows_sorted = sorted(r.rows, key=lambda r: r["salary"])
        # First row has no previous -> NULL
        assert rows_sorted[0]["prev_sal"] is None
        # Second row's prev is first row's salary
        assert rows_sorted[1]["prev_sal"] == rows_sorted[0]["salary"]

    def test_lead_basic(self, engine):
        r = engine.sql(
            "SELECT name, salary, "
            "LEAD(salary, 1) OVER (ORDER BY salary) AS next_sal "
            "FROM employees"
        )
        rows_sorted = sorted(r.rows, key=lambda r: r["salary"])
        # Last row has no next -> NULL
        assert rows_sorted[-1]["next_sal"] is None
        # First row's next is second row's salary
        assert rows_sorted[0]["next_sal"] == rows_sorted[1]["salary"]

    def test_lag_with_default(self, engine):
        r = engine.sql(
            "SELECT name, salary, "
            "LAG(salary, 1, 0) OVER (ORDER BY salary) AS prev_sal "
            "FROM employees"
        )
        rows_sorted = sorted(r.rows, key=lambda r: r["salary"])
        # First row uses default value 0
        assert rows_sorted[0]["prev_sal"] == 0

    def test_lag_with_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, salary, "
            "LAG(salary, 1) OVER (PARTITION BY dept ORDER BY salary) AS prev_sal "
            "FROM employees"
        )
        eng_rows = sorted(
            [row for row in r.rows if row["dept"] == "eng"],
            key=lambda r: r["salary"]
        )
        # First eng employee has no prev in partition
        assert eng_rows[0]["prev_sal"] is None
        assert eng_rows[1]["prev_sal"] == eng_rows[0]["salary"]


# ==================================================================
# Aggregate window functions
# ==================================================================


class TestAggregateWindow:
    def test_sum_over_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, salary, "
            "SUM(salary) OVER (PARTITION BY dept) AS dept_total "
            "FROM employees"
        )
        eng_rows = [row for row in r.rows if row["dept"] == "eng"]
        # eng total: 90000 + 85000 + 95000 = 270000
        for row in eng_rows:
            assert row["dept_total"] == 270000

        mkt_rows = [row for row in r.rows if row["dept"] == "mkt"]
        # mkt total: 75000 + 80000 = 155000
        for row in mkt_rows:
            assert row["dept_total"] == 155000

    def test_count_over_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, "
            "COUNT(*) OVER (PARTITION BY dept) AS dept_cnt "
            "FROM employees"
        )
        eng_rows = [row for row in r.rows if row["dept"] == "eng"]
        for row in eng_rows:
            assert row["dept_cnt"] == 3

    def test_avg_over_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, "
            "AVG(salary) OVER (PARTITION BY dept) AS avg_sal "
            "FROM employees"
        )
        eng_rows = [row for row in r.rows if row["dept"] == "eng"]
        expected_avg = (90000 + 85000 + 95000) / 3
        for row in eng_rows:
            assert abs(row["avg_sal"] - expected_avg) < 0.01

    def test_min_max_over_partition(self, engine):
        r = engine.sql(
            "SELECT name, dept, "
            "MIN(salary) OVER (PARTITION BY dept) AS min_sal, "
            "MAX(salary) OVER (PARTITION BY dept) AS max_sal "
            "FROM employees"
        )
        eng_rows = [row for row in r.rows if row["dept"] == "eng"]
        for row in eng_rows:
            assert row["min_sal"] == 85000
            assert row["max_sal"] == 95000


# ==================================================================
# Window functions with other clauses
# ==================================================================


class TestWindowIntegration:
    def test_window_with_where(self, engine):
        r = engine.sql(
            "SELECT name, salary, "
            "ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn "
            "FROM employees WHERE dept = 'eng'"
        )
        assert len(r.rows) == 3
        rows_by_rn = {row["rn"]: row["name"] for row in r.rows}
        assert rows_by_rn[1] == "Eve"
        assert rows_by_rn[2] == "Alice"
        assert rows_by_rn[3] == "Carol"

    def test_window_with_order_by(self, engine):
        r = engine.sql(
            "SELECT name, "
            "ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn "
            "FROM employees ORDER BY rn"
        )
        rns = [row["rn"] for row in r.rows]
        assert rns == [1, 2, 3, 4, 5, 6]

    def test_window_with_limit(self, engine):
        r = engine.sql(
            "SELECT name, "
            "ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn "
            "FROM employees ORDER BY rn LIMIT 3"
        )
        assert len(r.rows) == 3
        assert r.rows[0]["name"] == "Eve"
        assert r.rows[2]["name"] == "Carol"

    def test_multiple_window_functions(self, engine):
        r = engine.sql(
            "SELECT name, salary, "
            "ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn, "
            "SUM(salary) OVER (PARTITION BY dept) AS dept_total "
            "FROM employees"
        )
        assert "rn" in r.columns
        assert "dept_total" in r.columns
        assert len(r.rows) == 6
