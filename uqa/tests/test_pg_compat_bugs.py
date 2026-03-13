#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Regression tests for PostgreSQL compatibility fixes."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


# ==================================================================
# CTAS with explicit columns + SELECT *
# ==================================================================


class TestCTASSelectStar:
    """CTAS with specific columns followed by SELECT * must work."""

    def test_ctas_explicit_cols_select_star(self, engine):
        engine.sql(
            "CREATE TABLE employees ("
            "id SERIAL PRIMARY KEY, name TEXT NOT NULL, dept TEXT)"
        )
        engine.sql(
            "INSERT INTO employees (name, dept) VALUES "
            "('Alice', 'Eng'), ('Bob', 'Sales')"
        )
        engine.sql(
            "CREATE TABLE eng AS SELECT id, name FROM employees WHERE dept = 'Eng'"
        )
        result = engine.sql("SELECT * FROM eng")
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "Alice"

    def test_ctas_explicit_cols_select_star_order_by(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER, cat TEXT)")
        engine.sql("INSERT INTO t (val, cat) VALUES (10, 'a'), (20, 'b'), (30, 'a')")
        engine.sql("CREATE TABLE t2 AS SELECT id, val FROM t WHERE cat = 'a'")
        result = engine.sql("SELECT * FROM t2 ORDER BY id")
        assert len(result.rows) == 2
        vals = [r["val"] for r in result.rows]
        assert vals == [10, 30]

    def test_ctas_star_still_works(self, engine):
        engine.sql("CREATE TABLE src (x INTEGER, y TEXT)")
        engine.sql("INSERT INTO src VALUES (1, 'a'), (2, 'b')")
        engine.sql("CREATE TABLE dst AS SELECT * FROM src")
        result = engine.sql("SELECT * FROM dst ORDER BY x")
        assert len(result.rows) == 2
        assert result.rows[0]["x"] == 1


# ==================================================================
# SELECT * after DELETE ... USING
# ==================================================================


class TestDeleteUsingSelectStar:
    """DELETE ... USING followed by SELECT * must work."""

    def test_delete_using_then_select_star(self, engine):
        engine.sql("CREATE TABLE employees (id INTEGER, name TEXT)")
        engine.sql(
            "INSERT INTO employees VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol')"
        )
        engine.sql("CREATE TABLE blacklist (name TEXT PRIMARY KEY)")
        engine.sql("INSERT INTO blacklist VALUES ('Bob')")
        ret = engine.sql(
            "DELETE FROM employees USING blacklist bl "
            "WHERE employees.name = bl.name RETURNING employees.name"
        )
        assert len(ret.rows) == 1
        assert ret.rows[0]["name"] == "Bob"
        result = engine.sql("SELECT * FROM employees ORDER BY id")
        assert len(result.rows) == 2
        names = [r["name"] for r in result.rows]
        assert "Alice" in names
        assert "Carol" in names

    def test_delete_using_select_star_order_by(self, engine):
        engine.sql("CREATE TABLE items (id INTEGER, name TEXT)")
        engine.sql("INSERT INTO items VALUES (1, 'x'), (2, 'y'), (3, 'z')")
        engine.sql("CREATE TABLE remove_list (name TEXT)")
        engine.sql("INSERT INTO remove_list VALUES ('y'), ('z')")
        engine.sql("DELETE FROM items USING remove_list r WHERE items.name = r.name")
        result = engine.sql("SELECT * FROM items ORDER BY id")
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "x"


# ==================================================================
# Aggregate in IN subquery HAVING
# ==================================================================


class TestAggregateInSubqueryHaving:
    """Aggregates in HAVING clause of IN subquery must be recognized."""

    def test_count_in_having_subquery(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, dept TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'A'), (2, 'A'), (3, 'B')")
        result = engine.sql(
            "SELECT dept FROM t "
            "WHERE dept IN ("
            "  SELECT dept FROM t GROUP BY dept HAVING COUNT(*) > 1"
            ")"
        )
        depts = [r["dept"] for r in result.rows]
        assert sorted(depts) == ["A", "A"]

    def test_sum_in_having_subquery(self, engine):
        engine.sql("CREATE TABLE sales (id INTEGER, region TEXT, amount INTEGER)")
        engine.sql(
            "INSERT INTO sales VALUES "
            "(1, 'East', 100), (2, 'East', 200), "
            "(3, 'West', 50), (4, 'North', 300)"
        )
        result = engine.sql(
            "SELECT region FROM sales "
            "WHERE region IN ("
            "  SELECT region FROM sales "
            "  GROUP BY region HAVING SUM(amount) > 100"
            ")"
        )
        regions = sorted({r["region"] for r in result.rows})
        assert regions == ["East", "North"]

    def test_having_with_multiple_aggregates(self, engine):
        engine.sql("CREATE TABLE t (dept TEXT, salary INTEGER)")
        engine.sql(
            "INSERT INTO t VALUES "
            "('A', 100), ('A', 200), ('A', 300), "
            "('B', 50), ('C', 400), ('C', 500)"
        )
        result = engine.sql(
            "SELECT dept FROM t "
            "WHERE dept IN ("
            "  SELECT dept FROM t "
            "  GROUP BY dept HAVING COUNT(*) >= 2 AND AVG(salary) > 100"
            ")"
        )
        depts = sorted({r["dept"] for r in result.rows})
        assert depts == ["A", "C"]


# ==================================================================
# Aggregate nested inside scalar function
# ==================================================================


class TestNestedAggregate:
    """Aggregates wrapped in scalar functions must be recognized."""

    def test_round_stddev(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, salary NUMERIC(10,2))")
        engine.sql("INSERT INTO t VALUES (1, 95000), (2, 82000), (3, 105000)")
        result = engine.sql("SELECT ROUND(STDDEV(salary)::NUMERIC, 2) AS sd FROM t")
        assert len(result.rows) == 1
        sd = float(result.rows[0]["sd"])
        assert sd > 0

    def test_round_variance(self, engine):
        engine.sql("CREATE TABLE t (v NUMERIC(10,2))")
        engine.sql("INSERT INTO t VALUES (10), (20), (30)")
        result = engine.sql("SELECT ROUND(VARIANCE(v)::NUMERIC, 2) AS var FROM t")
        assert len(result.rows) == 1
        assert float(result.rows[0]["var"]) > 0

    def test_round_corr(self, engine):
        engine.sql("CREATE TABLE stats_data (x REAL, y REAL)")
        engine.sql(
            "INSERT INTO stats_data VALUES (1, 2), (2, 4), (3, 5), (4, 4), (5, 5)"
        )
        result = engine.sql(
            "SELECT ROUND(CORR(x, y)::NUMERIC, 4) AS correlation FROM stats_data"
        )
        assert len(result.rows) == 1
        corr = float(result.rows[0]["correlation"])
        assert 0 < corr < 1

    def test_round_covar(self, engine):
        engine.sql("CREATE TABLE xy (x REAL, y REAL)")
        engine.sql("INSERT INTO xy VALUES (1, 2), (2, 4), (3, 6)")
        result = engine.sql(
            "SELECT ROUND(COVAR_POP(x, y)::NUMERIC, 4) AS cp, "
            "ROUND(COVAR_SAMP(x, y)::NUMERIC, 4) AS cs FROM xy"
        )
        assert len(result.rows) == 1
        assert float(result.rows[0]["cp"]) > 0
        assert float(result.rows[0]["cs"]) > 0

    def test_round_regr(self, engine):
        engine.sql("CREATE TABLE xy (x REAL, y REAL)")
        engine.sql("INSERT INTO xy VALUES (1, 2), (2, 4), (3, 6)")
        result = engine.sql(
            "SELECT ROUND(REGR_SLOPE(y, x)::NUMERIC, 4) AS slope, "
            "ROUND(REGR_INTERCEPT(y, x)::NUMERIC, 4) AS intercept, "
            "REGR_COUNT(y, x) AS cnt FROM xy"
        )
        assert len(result.rows) == 1
        assert float(result.rows[0]["slope"]) == 2.0
        assert result.rows[0]["cnt"] == 3

    def test_abs_of_aggregate(self, engine):
        engine.sql("CREATE TABLE t (v INTEGER)")
        engine.sql("INSERT INTO t VALUES (-10), (-20), (-30)")
        result = engine.sql("SELECT ABS(SUM(v)) AS abs_sum FROM t")
        assert result.rows[0]["abs_sum"] == 60


# ==================================================================
# Window default frame with ORDER BY
# ==================================================================


class TestWindowDefaultFrame:
    """Window with ORDER BY but no explicit frame must use running frame."""

    def test_running_sum(self, engine):
        engine.sql("CREATE TABLE ws (v INTEGER)")
        engine.sql("INSERT INTO ws VALUES (1), (2), (3), (4), (5)")
        result = engine.sql("SELECT v, SUM(v) OVER (ORDER BY v) AS running_sum FROM ws")
        sums = {r["v"]: r["running_sum"] for r in result.rows}
        assert sums[1] == 1
        assert sums[2] == 3
        assert sums[3] == 6
        assert sums[4] == 10
        assert sums[5] == 15

    def test_running_avg(self, engine):
        engine.sql("CREATE TABLE ws (v INTEGER)")
        engine.sql("INSERT INTO ws VALUES (1), (2), (3), (4), (5)")
        result = engine.sql("SELECT v, AVG(v) OVER (ORDER BY v) AS running_avg FROM ws")
        avgs = {r["v"]: float(r["running_avg"]) for r in result.rows}
        assert avgs[1] == pytest.approx(1.0)
        assert avgs[2] == pytest.approx(1.5)
        assert avgs[3] == pytest.approx(2.0)

    def test_running_count(self, engine):
        engine.sql("CREATE TABLE ws (v INTEGER)")
        engine.sql("INSERT INTO ws VALUES (10), (20), (30)")
        result = engine.sql(
            "SELECT v, COUNT(*) OVER (ORDER BY v) AS running_cnt FROM ws"
        )
        cnts = {r["v"]: r["running_cnt"] for r in result.rows}
        assert cnts[10] == 1
        assert cnts[20] == 2
        assert cnts[30] == 3

    def test_no_order_by_uses_whole_partition(self, engine):
        engine.sql("CREATE TABLE ws (v INTEGER)")
        engine.sql("INSERT INTO ws VALUES (1), (2), (3)")
        result = engine.sql("SELECT v, SUM(v) OVER () AS total FROM ws")
        for r in result.rows:
            assert r["total"] == 6

    def test_running_sum_with_partition(self, engine):
        engine.sql("CREATE TABLE ws (grp TEXT, v INTEGER)")
        engine.sql(
            "INSERT INTO ws VALUES ('a', 1), ('a', 2), ('a', 3), ('b', 10), ('b', 20)"
        )
        result = engine.sql(
            "SELECT grp, v, "
            "SUM(v) OVER (PARTITION BY grp ORDER BY v) AS running "
            "FROM ws"
        )
        by_grp = {}
        for r in result.rows:
            by_grp.setdefault(r["grp"], {})[r["v"]] = r["running"]
        assert by_grp["a"][1] == 1
        assert by_grp["a"][2] == 3
        assert by_grp["a"][3] == 6
        assert by_grp["b"][10] == 10
        assert by_grp["b"][20] == 30


# ==================================================================
# LTRIM/RTRIM with character set
# ==================================================================


class TestTrimCharacterSet:
    """LTRIM/RTRIM with a character-set argument must strip those characters."""

    def test_ltrim_with_chars(self, engine):
        result = engine.sql("SELECT LTRIM('xxhello', 'x') AS lt")
        assert result.rows[0]["lt"] == "hello"

    def test_rtrim_with_chars(self, engine):
        result = engine.sql("SELECT RTRIM('helloxx', 'x') AS rt")
        assert result.rows[0]["rt"] == "hello"

    def test_btrim_with_chars(self, engine):
        result = engine.sql("SELECT BTRIM('xxhelloxx', 'x') AS bt")
        assert result.rows[0]["bt"] == "hello"

    def test_ltrim_multiple_chars(self, engine):
        result = engine.sql("SELECT LTRIM('xyxhello', 'xy') AS lt")
        assert result.rows[0]["lt"] == "hello"

    def test_rtrim_multiple_chars(self, engine):
        result = engine.sql("SELECT RTRIM('helloxyxy', 'xy') AS rt")
        assert result.rows[0]["rt"] == "hello"

    def test_ltrim_no_match(self, engine):
        result = engine.sql("SELECT LTRIM('hello', 'x') AS lt")
        assert result.rows[0]["lt"] == "hello"

    def test_ltrim_whitespace_default(self, engine):
        result = engine.sql("SELECT LTRIM('  hello') AS lt")
        assert result.rows[0]["lt"] == "hello"

    def test_rtrim_whitespace_default(self, engine):
        result = engine.sql("SELECT RTRIM('hello  ') AS rt")
        assert result.rows[0]["rt"] == "hello"


# ==================================================================
# CONCAT_WS
# ==================================================================


class TestConcatWS:
    """CONCAT_WS must join arguments with the given separator."""

    def test_concat_ws_basic(self, engine):
        result = engine.sql("SELECT CONCAT_WS('-', 'a', 'b', 'c') AS result")
        assert result.rows[0]["result"] == "a-b-c"

    def test_concat_ws_comma(self, engine):
        result = engine.sql("SELECT CONCAT_WS(', ', 'Alice', 'Bob', 'Carol') AS names")
        assert result.rows[0]["names"] == "Alice, Bob, Carol"

    def test_concat_ws_single_arg(self, engine):
        result = engine.sql("SELECT CONCAT_WS('-', 'only') AS result")
        assert result.rows[0]["result"] == "only"

    def test_concat_ws_with_nulls(self, engine):
        engine.sql("CREATE TABLE t (a TEXT, b TEXT, c TEXT)")
        engine.sql("INSERT INTO t VALUES ('x', NULL, 'z')")
        result = engine.sql("SELECT CONCAT_WS('-', a, b, c) AS result FROM t")
        assert result.rows[0]["result"] == "x-z"

    def test_concat_ws_null_separator(self, engine):
        result = engine.sql("SELECT CONCAT_WS(NULL, 'a', 'b') AS result")
        assert result.rows[0]["result"] is None


# ==================================================================
# JSON operators in WHERE clause
# ==================================================================


class TestJSONOperatorsInWhere:
    """JSON containment/existence operators must work in WHERE clauses."""

    @pytest.fixture
    def engine_with_jsonb(self, engine):
        engine.sql("CREATE TABLE jdocs (id SERIAL PRIMARY KEY, data JSONB)")
        engine.sql(
            "INSERT INTO jdocs (data) VALUES "
            '(\'{"name":"Alice","age":30,"tags":["a","b"]}\')'
        )
        engine.sql('INSERT INTO jdocs (data) VALUES (\'{"name":"Bob","age":25}\')')
        return engine

    def test_contains_operator_in_where(self, engine_with_jsonb):
        result = engine_with_jsonb.sql(
            "SELECT id FROM jdocs WHERE data @> '{\"age\":30}'"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == [1]

    def test_key_exists_operator_in_where(self, engine_with_jsonb):
        result = engine_with_jsonb.sql("SELECT id FROM jdocs WHERE data ? 'tags'")
        ids = [r["id"] for r in result.rows]
        assert ids == [1]

    def test_has_all_keys_operator_in_where(self, engine_with_jsonb):
        result = engine_with_jsonb.sql(
            "SELECT id FROM jdocs WHERE data ?& '{name,age}'"
        )
        ids = [r["id"] for r in result.rows]
        assert sorted(ids) == [1, 2]

    def test_has_any_keys_operator_in_where(self, engine_with_jsonb):
        result = engine_with_jsonb.sql(
            "SELECT id FROM jdocs WHERE data ?| '{tags,missing}'"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == [1]

    def test_contains_no_match(self, engine_with_jsonb):
        result = engine_with_jsonb.sql(
            "SELECT id FROM jdocs WHERE data @> '{\"age\":99}'"
        )
        assert len(result.rows) == 0

    def test_key_exists_no_match(self, engine_with_jsonb):
        result = engine_with_jsonb.sql(
            "SELECT id FROM jdocs WHERE data ? 'nonexistent'"
        )
        assert len(result.rows) == 0


# ==================================================================
# Date/time formatting and construction functions
# ==================================================================


class TestDateTimeFunctions:
    """TO_CHAR, TO_DATE, TO_TIMESTAMP, MAKE_DATE, AGE must work."""

    def test_to_char(self, engine):
        result = engine.sql(
            "SELECT TO_CHAR(TIMESTAMP '2024-06-15 10:30:00', 'YYYY-MM-DD') AS formatted"
        )
        assert result.rows[0]["formatted"] == "2024-06-15"

    def test_to_char_with_time(self, engine):
        result = engine.sql(
            "SELECT TO_CHAR(TIMESTAMP '2024-06-15 14:30:45', "
            "'YYYY-MM-DD HH24:MI:SS') AS formatted"
        )
        assert result.rows[0]["formatted"] == "2024-06-15 14:30:45"

    def test_to_date(self, engine):
        result = engine.sql("SELECT TO_DATE('2024-06-15', 'YYYY-MM-DD') AS parsed_date")
        val = str(result.rows[0]["parsed_date"])
        assert "2024-06-15" in val

    def test_to_timestamp(self, engine):
        result = engine.sql(
            "SELECT TO_TIMESTAMP('2024-06-15 10:30:00', "
            "'YYYY-MM-DD HH24:MI:SS') AS parsed_ts"
        )
        val = str(result.rows[0]["parsed_ts"])
        assert "2024-06-15" in val
        assert "10:30" in val

    def test_make_date(self, engine):
        result = engine.sql("SELECT MAKE_DATE(2024, 6, 15) AS d")
        val = str(result.rows[0]["d"])
        assert "2024-06-15" in val

    def test_age(self, engine):
        result = engine.sql(
            "SELECT AGE(TIMESTAMP '2024-06-15', TIMESTAMP '2020-01-01') AS age_result"
        )
        val = str(result.rows[0]["age_result"])
        assert "4 year" in val


# ==================================================================
# INTERVAL type and NamedArgExpr
# ==================================================================


class TestIntervalAndNamedArg:
    """INTERVAL literals and MAKE_INTERVAL with named args must work."""

    def test_interval_literal(self, engine):
        result = engine.sql("SELECT INTERVAL '2 hours 30 minutes' AS dur")
        val = str(result.rows[0]["dur"])
        assert "2" in val
        assert "30" in val

    def test_interval_simple(self, engine):
        result = engine.sql("SELECT INTERVAL '1 day' AS dur")
        val = str(result.rows[0]["dur"])
        assert "day" in val or "1" in val

    def test_make_interval_named_args(self, engine):
        result = engine.sql("SELECT MAKE_INTERVAL(days => 5, hours => 3) AS iv")
        assert result.rows[0]["iv"] is not None

    def test_make_interval_single_arg(self, engine):
        result = engine.sql("SELECT MAKE_INTERVAL(hours => 12) AS iv")
        assert result.rows[0]["iv"] is not None
