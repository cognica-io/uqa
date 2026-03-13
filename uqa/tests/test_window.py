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
            "SELECT name, ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn FROM employees"
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
            "SELECT name, ROW_NUMBER() OVER (ORDER BY salary) AS rn FROM employees"
        )
        rows_by_rn = {row["rn"]: row["name"] for row in r.rows}
        assert rows_by_rn[1] == "Dave"  # lowest salary
        assert rows_by_rn[6] == "Eve"  # highest salary


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
            "SELECT name, RANK() OVER (ORDER BY salary DESC) AS rnk FROM employees"
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
        eng_ranks = {row["name"]: row["rnk"] for row in r.rows if row["dept"] == "eng"}
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
            [row for row in r.rows if row["dept"] == "eng"], key=lambda r: r["salary"]
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


# ==================================================================
# Fixtures for appended PG17 test classes
# ==================================================================


@pytest.fixture
def pg17_engine():
    return Engine()


@pytest.fixture
def engine_with_scores(pg17_engine):
    pg17_engine.sql(
        "CREATE TABLE scores (  id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
    )
    pg17_engine.sql("INSERT INTO scores (id, name, score) VALUES (1, 'A', 100)")
    pg17_engine.sql("INSERT INTO scores (id, name, score) VALUES (2, 'B', 200)")
    pg17_engine.sql("INSERT INTO scores (id, name, score) VALUES (3, 'C', 200)")
    pg17_engine.sql("INSERT INTO scores (id, name, score) VALUES (4, 'D', 300)")
    pg17_engine.sql("INSERT INTO scores (id, name, score) VALUES (5, 'E', 400)")
    return pg17_engine


@pytest.fixture
def engine_with_table(pg17_engine):
    pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER, name TEXT)")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (1, 10, 'alpha')")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (2, 20, 'bravo')")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (3, 30, 'charlie')")
    return pg17_engine


# ==================================================================
# PERCENT_RANK
# ==================================================================


class TestPercentRank:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  percent_rank() OVER (ORDER BY score) AS pr "
            "FROM scores ORDER BY score"
        )
        prs = [r["pr"] for r in result.rows]
        # ranks: 1, 2, 2, 4, 5 -> (0/4, 1/4, 1/4, 3/4, 4/4)
        assert prs[0] == 0.0
        assert prs[1] == 0.25
        assert prs[2] == 0.25
        assert prs[3] == 0.75
        assert prs[4] == 1.0


# ==================================================================
# CUME_DIST
# ==================================================================


class TestCumeDist:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  cume_dist() OVER (ORDER BY score) AS cd "
            "FROM scores ORDER BY score"
        )
        cds = [r["cd"] for r in result.rows]
        # A(100): 1/5=0.2, B(200): 3/5=0.6, C(200): 3/5=0.6,
        # D(300): 4/5=0.8, E(400): 5/5=1.0
        assert cds[0] == 0.2
        assert cds[1] == 0.6
        assert cds[2] == 0.6
        assert cds[3] == 0.8
        assert cds[4] == 1.0


# ==================================================================
# NTH_VALUE
# ==================================================================


class TestNthValue:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  nth_value(name, 2) OVER (ORDER BY score) AS second "
            "FROM scores"
        )
        # 2nd value in the partition ordered by score: B
        for row in result.rows:
            assert row["second"] == "B"

    def test_nth_value_out_of_range(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        pg17_engine.sql("INSERT INTO t (id, val) VALUES (1, 10)")
        result = pg17_engine.sql(
            "SELECT nth_value(val, 5) OVER (ORDER BY id) AS v FROM t"
        )
        assert result.rows[0]["v"] is None


# ==================================================================
# Window frames
# ==================================================================


class TestWindowFrames:
    def test_running_sum(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, score, "
            "  SUM(score) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
            "  ) AS running_total "
            "FROM scores ORDER BY id"
        )
        totals = [r["running_total"] for r in result.rows]
        assert totals == [100, 300, 500, 800, 1200]

    def test_sliding_window_avg(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        for i, v in enumerate([10, 20, 30, 40, 50], start=1):
            pg17_engine.sql(f"INSERT INTO t (id, val) VALUES ({i}, {v})")
        result = pg17_engine.sql(
            "SELECT id, val, "
            "  AVG(val) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING"
            "  ) AS moving_avg "
            "FROM t ORDER BY id"
        )
        avgs = [r["moving_avg"] for r in result.rows]
        # Row 1: avg(10,20) = 15
        # Row 2: avg(10,20,30) = 20
        # Row 3: avg(20,30,40) = 30
        # Row 4: avg(30,40,50) = 40
        # Row 5: avg(40,50) = 45
        assert avgs == [15.0, 20.0, 30.0, 40.0, 45.0]

    def test_unbounded_frame(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  SUM(score) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING"
            "  ) AS total "
            "FROM scores"
        )
        # Every row sees the full partition sum
        for row in result.rows:
            assert row["total"] == 1200


# ==================================================================
# Named window
# ==================================================================


class TestNamedWindow:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id, sum(val) OVER w AS running "
            "FROM t WINDOW w AS (ORDER BY id) "
            "ORDER BY id"
        )
        assert result.rows[0]["running"] is not None

    def test_named_window_ref(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id, row_number() OVER (w) AS rn "
            "FROM t WINDOW w AS (ORDER BY id) "
            "ORDER BY id"
        )
        assert result.rows[0]["rn"] == 1
        assert result.rows[1]["rn"] == 2
        assert result.rows[2]["rn"] == 3


# ==================================================================
# RANGE BETWEEN
# ==================================================================


class TestRangeBetween:
    def test_range_unbounded_preceding(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id, sum(val) OVER ("
            "  ORDER BY id RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
            ") AS running "
            "FROM t ORDER BY id"
        )
        assert result.rows[0]["running"] == 10
        assert result.rows[1]["running"] == 30
        assert result.rows[2]["running"] == 60

    def test_range_with_peers(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE rp (id SERIAL PRIMARY KEY, grp INT, val INT)")
        pg17_engine.sql("INSERT INTO rp (grp, val) VALUES (1, 10)")
        pg17_engine.sql("INSERT INTO rp (grp, val) VALUES (1, 20)")
        pg17_engine.sql("INSERT INTO rp (grp, val) VALUES (2, 30)")
        result = pg17_engine.sql(
            "SELECT grp, sum(val) OVER ("
            "  ORDER BY grp RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
            ") AS running "
            "FROM rp ORDER BY id"
        )
        # Peers (grp=1) get the same cumulative sum
        assert result.rows[0]["running"] == 30  # includes both grp=1 rows
        assert result.rows[1]["running"] == 30
        assert result.rows[2]["running"] == 60


# ==================================================================
# FILTER (WHERE) on window aggregate
# ==================================================================


class TestWindowFilter:
    """Test FILTER (WHERE ...) clause on window aggregate functions.

    FILTER restricts which rows are included in the aggregate computation
    while still producing a result for every row in the partition.
    """

    @pytest.fixture()
    def wf_engine(self):
        e = Engine()
        e.sql("CREATE TABLE sales (id INT PRIMARY KEY, dept TEXT, amount INT)")
        e.sql("INSERT INTO sales VALUES (1, 'A', 100)")
        e.sql("INSERT INTO sales VALUES (2, 'A', 200)")
        e.sql("INSERT INTO sales VALUES (3, 'B', 150)")
        e.sql("INSERT INTO sales VALUES (4, 'B', 50)")
        yield e

    def test_sum_filter(self, wf_engine):
        r = wf_engine.sql(
            "SELECT dept, amount, "
            "SUM(amount) FILTER (WHERE amount > 100) "
            "OVER (PARTITION BY dept) AS big_sum "
            "FROM sales ORDER BY id"
        )
        # dept A: only 200 > 100, so big_sum = 200
        assert r.rows[0]["big_sum"] == 200  # id=1, dept=A
        assert r.rows[1]["big_sum"] == 200  # id=2, dept=A
        # dept B: only 150 > 100, so big_sum = 150
        assert r.rows[2]["big_sum"] == 150  # id=3, dept=B
        assert r.rows[3]["big_sum"] == 150  # id=4, dept=B

    def test_count_filter(self, wf_engine):
        r = wf_engine.sql(
            "SELECT dept, amount, "
            "COUNT(*) FILTER (WHERE amount >= 150) "
            "OVER (PARTITION BY dept) AS cnt "
            "FROM sales ORDER BY id"
        )
        # dept A: only 200 >= 150, count = 1
        assert r.rows[0]["cnt"] == 1
        assert r.rows[1]["cnt"] == 1
        # dept B: only 150 >= 150, count = 1
        assert r.rows[2]["cnt"] == 1
        assert r.rows[3]["cnt"] == 1

    def test_avg_filter(self, wf_engine):
        r = wf_engine.sql(
            "SELECT dept, amount, "
            "AVG(amount) FILTER (WHERE amount <= 150) "
            "OVER (PARTITION BY dept) AS avg_small "
            "FROM sales ORDER BY id"
        )
        # dept A: only 100 <= 150, avg = 100
        assert r.rows[0]["avg_small"] == 100
        assert r.rows[1]["avg_small"] == 100
        # dept B: 150 and 50 <= 150, avg = 100
        assert r.rows[2]["avg_small"] == 100
        assert r.rows[3]["avg_small"] == 100

    def test_filter_excludes_all(self, wf_engine):
        r = wf_engine.sql(
            "SELECT dept, amount, "
            "SUM(amount) FILTER (WHERE amount > 1000) "
            "OVER (PARTITION BY dept) AS s "
            "FROM sales ORDER BY id"
        )
        # No rows match amount > 1000 in any partition
        for row in r.rows:
            assert row["s"] is None or row["s"] == 0


# ==================================================================
# Window FILTER edge cases
# ==================================================================


class TestWindowFilterEdgeCases:
    """Additional window FILTER tests."""

    def test_avg_filter(self):
        e = Engine()
        e.sql("CREATE TABLE scores (id INT PRIMARY KEY, subject TEXT, score INT)")
        e.sql("INSERT INTO scores VALUES (1, 'math', 90)")
        e.sql("INSERT INTO scores VALUES (2, 'math', 60)")
        e.sql("INSERT INTO scores VALUES (3, 'sci', 80)")
        e.sql("INSERT INTO scores VALUES (4, 'sci', 40)")
        r = e.sql(
            "SELECT subject, score, "
            "AVG(score) FILTER (WHERE score >= 70) "
            "OVER (PARTITION BY subject) AS high_avg "
            "FROM scores ORDER BY id"
        )
        # math: only 90 qualifies -> avg = 90.0
        assert r.rows[0]["high_avg"] == 90.0
        assert r.rows[1]["high_avg"] == 90.0
        # sci: only 80 qualifies -> avg = 80.0
        assert r.rows[2]["high_avg"] == 80.0
        assert r.rows[3]["high_avg"] == 80.0

    def test_sum_filter(self):
        e = Engine()
        e.sql("CREATE TABLE vals (id INT PRIMARY KEY, grp TEXT, amount INT)")
        e.sql("INSERT INTO vals VALUES (1, 'a', 10)")
        e.sql("INSERT INTO vals VALUES (2, 'a', 20)")
        e.sql("INSERT INTO vals VALUES (3, 'a', 30)")
        r = e.sql(
            "SELECT id, "
            "SUM(amount) FILTER (WHERE amount > 10) "
            "OVER (PARTITION BY grp) AS filtered_sum "
            "FROM vals ORDER BY id"
        )
        # Only 20 and 30 qualify -> sum = 50
        assert r.rows[0]["filtered_sum"] == 50
        assert r.rows[1]["filtered_sum"] == 50
        assert r.rows[2]["filtered_sum"] == 50

    def test_count_filter(self):
        e = Engine()
        e.sql("CREATE TABLE items (id INT PRIMARY KEY, category TEXT, price INT)")
        e.sql("INSERT INTO items VALUES (1, 'food', 5)")
        e.sql("INSERT INTO items VALUES (2, 'food', 15)")
        e.sql("INSERT INTO items VALUES (3, 'food', 25)")
        r = e.sql(
            "SELECT id, "
            "COUNT(*) FILTER (WHERE price >= 10) "
            "OVER (PARTITION BY category) AS expensive_count "
            "FROM items ORDER BY id"
        )
        # 15 and 25 qualify -> count = 2
        assert r.rows[0]["expensive_count"] == 2
        assert r.rows[1]["expensive_count"] == 2
        assert r.rows[2]["expensive_count"] == 2
