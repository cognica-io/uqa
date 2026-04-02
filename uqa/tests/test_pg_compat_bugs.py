#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Regression tests for PostgreSQL compatibility fixes."""

from __future__ import annotations

import datetime as dt

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


# ==================================================================
# SET / SHOW / RESET / DISCARD
# ==================================================================


class TestSessionVariables:
    """SET, SHOW, RESET, and DISCARD must work like PostgreSQL."""

    def test_set_and_show(self, engine):
        engine.sql("SET client_encoding TO 'UTF8'")
        result = engine.sql("SHOW client_encoding")
        assert result.columns == ["client_encoding"]
        assert result.rows[0]["client_encoding"] == "UTF8"

    def test_set_integer_value(self, engine):
        engine.sql("SET statement_timeout = 5000")
        result = engine.sql("SHOW statement_timeout")
        assert result.rows[0]["statement_timeout"] == "5000"

    def test_set_multiple_values(self, engine):
        engine.sql("SET search_path TO 'myschema', 'public'")
        result = engine.sql("SHOW search_path")
        assert "myschema" in result.rows[0]["search_path"]
        assert "public" in result.rows[0]["search_path"]

    def test_show_defaults(self, engine):
        result = engine.sql("SHOW server_version")
        assert result.rows[0]["server_version"] == "17.0"

    def test_reset(self, engine):
        engine.sql("SET client_encoding TO 'LATIN1'")
        engine.sql("RESET client_encoding")
        result = engine.sql("SHOW client_encoding")
        assert result.rows[0]["client_encoding"] == "UTF8"

    def test_reset_all(self, engine):
        engine.sql("SET client_encoding TO 'LATIN1'")
        engine.sql("SET statement_timeout = 9999")
        engine.sql("RESET ALL")
        result = engine.sql("SHOW client_encoding")
        assert result.rows[0]["client_encoding"] == "UTF8"

    def test_set_local(self, engine):
        engine.sql("SET LOCAL timezone TO 'US/Eastern'")
        result = engine.sql("SHOW timezone")
        assert result.rows[0]["timezone"] == "US/Eastern"

    def test_discard_all(self, engine):
        engine.sql("SET client_encoding TO 'LATIN1'")
        engine.sql("DISCARD ALL")
        result = engine.sql("SHOW client_encoding")
        assert result.rows[0]["client_encoding"] == "UTF8"


# ==================================================================
# In-memory transactions (BEGIN / COMMIT / ROLLBACK)
# ==================================================================


class TestInMemoryTransactions:
    """BEGIN/COMMIT/ROLLBACK must work in in-memory engines."""

    def test_begin_commit(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        engine.sql("BEGIN")
        engine.sql("INSERT INTO t VALUES (1, 'a')")
        engine.sql("COMMIT")
        result = engine.sql("SELECT * FROM t")
        assert len(result.rows) == 1

    def test_begin_rollback(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'a')")
        engine.sql("BEGIN")
        engine.sql("INSERT INTO t VALUES (2, 'b')")
        engine.sql("ROLLBACK")
        result = engine.sql("SELECT * FROM t")
        assert len(result.rows) == 1
        assert result.rows[0]["v"] == "a"

    def test_context_manager(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        with engine.begin() as txn:
            engine.sql("INSERT INTO t VALUES (1, 'a')")
            txn.commit()
        result = engine.sql("SELECT * FROM t")
        assert len(result.rows) == 1

    def test_nested_begin_raises(self, engine):
        engine.sql("BEGIN")
        with pytest.raises(ValueError, match="already active"):
            engine.sql("BEGIN")
        engine.sql("COMMIT")


# ==================================================================
# SELECT * must not expose internal columns (_doc_id, _score)
# ==================================================================


class TestSelectStarNoInternalColumns:
    """SELECT * should only return user-defined columns."""

    def test_single_table_no_internal_cols(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'Alice'), (2, 'Bob')")
        result = engine.sql("SELECT * FROM t")
        assert "_doc_id" not in result.columns
        assert "_score" not in result.columns
        assert set(result.columns) == {"id", "name"}
        assert len(result.rows) == 2

    def test_explicit_columns_still_work(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'Alice')")
        result = engine.sql("SELECT id, name FROM t")
        assert result.columns == ["id", "name"]

    def test_select_star_with_order_by(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t VALUES (2, 'b'), (1, 'a')")
        result = engine.sql("SELECT * FROM t ORDER BY id")
        assert "_doc_id" not in result.columns
        assert result.rows[0]["id"] == 1


# ==================================================================
# Aggregate results must not have duplicate columns
# ==================================================================


class TestAggregateDuplicateColumns:
    """SELECT COUNT(*) AS c should only have column 'c', not 'count' too."""

    def test_count_alias_only(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t (name) VALUES ('a'), ('b'), ('c')")
        result = engine.sql("SELECT COUNT(*) AS c FROM t")
        assert result.columns == ["c"]
        assert set(result.rows[0].keys()) == {"c"}
        assert result.rows[0]["c"] == 3

    def test_sum_alias_only(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        engine.sql("INSERT INTO t VALUES (1, 10), (2, 20), (3, 30)")
        result = engine.sql("SELECT SUM(val) AS s FROM t")
        assert result.columns == ["s"]
        assert set(result.rows[0].keys()) == {"s"}
        assert result.rows[0]["s"] == 60

    def test_group_by_count_alias(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, cat TEXT, val INTEGER)")
        engine.sql("INSERT INTO t (cat, val) VALUES ('a', 1), ('a', 2), ('b', 3)")
        result = engine.sql(
            "SELECT cat, COUNT(*) AS cnt FROM t GROUP BY cat ORDER BY cat"
        )
        assert result.columns == ["cat", "cnt"]
        assert set(result.rows[0].keys()) == {"cat", "cnt"}

    def test_natural_name_without_alias(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        engine.sql("INSERT INTO t (val) VALUES (1), (2), (3)")
        result = engine.sql("SELECT COUNT(*) FROM t")
        assert result.columns == ["count"]
        assert result.rows[0]["count"] == 3


# ==================================================================
# LEFT JOIN + GROUP BY must produce correct results
# ==================================================================


class TestLeftJoinGroupBy:
    """LEFT JOIN with GROUP BY must handle unmatched rows correctly."""

    def test_left_join_group_by_count(self, engine):
        engine.sql(
            "CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        engine.sql(
            "CREATE TABLE employees ("
            "id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER)"
        )
        engine.sql(
            "INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Sales'), (3, 'HR')"
        )
        engine.sql(
            "INSERT INTO employees VALUES (1, 'Alice', 1), (2, 'Bob', 1), (3, 'Carol', 2)"
        )

        result = engine.sql(
            "SELECT d.name, COUNT(e.id) AS cnt "
            "FROM departments d LEFT JOIN employees e ON d.id = e.dept_id "
            "GROUP BY d.name ORDER BY d.name"
        )
        rows = result.rows
        assert len(rows) == 3
        by_name = {r["name"]: r["cnt"] for r in rows}
        assert by_name["Engineering"] == 2
        assert by_name["Sales"] == 1
        assert by_name["HR"] == 0

    def test_left_join_unmatched_null_columns(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER, data TEXT)")
        engine.sql("INSERT INTO a VALUES (1, 'x'), (2, 'y')")
        engine.sql("INSERT INTO b VALUES (10, 1, 'hello')")

        result = engine.sql(
            "SELECT a.val, b.data FROM a LEFT JOIN b ON a.id = b.a_id ORDER BY a.val"
        )
        rows = result.rows
        assert len(rows) == 2
        assert rows[0]["val"] == "x"
        assert rows[0]["data"] == "hello"
        assert rows[1]["val"] == "y"
        assert rows[1]["data"] is None


# ==================================================================
# DEFAULT with SQL functions (CURRENT_TIMESTAMP, etc.)
# ==================================================================


class TestDefaultSQLFunctions:
    """DEFAULT CURRENT_TIMESTAMP and similar must work."""

    def test_default_current_timestamp(self, engine):
        engine.sql(
            "CREATE TABLE log ("
            "id SERIAL PRIMARY KEY, "
            "msg TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        engine.sql("INSERT INTO log (msg) VALUES ('hello')")
        result = engine.sql("SELECT created_at FROM log")
        ts = result.rows[0]["created_at"]
        assert isinstance(ts, dt.datetime)

    def test_default_current_date(self, engine):
        engine.sql(
            "CREATE TABLE events ("
            "id SERIAL PRIMARY KEY, "
            "event_date DATE DEFAULT CURRENT_DATE)"
        )
        engine.sql("INSERT INTO events (id) VALUES (1)")
        result = engine.sql("SELECT event_date FROM events")
        d = result.rows[0]["event_date"]
        assert isinstance(d, dt.date)

    def test_default_literal_still_works(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active')"
        )
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT status FROM t")
        assert result.rows[0]["status"] == "active"

    def test_explicit_value_overrides_default(self, engine):
        engine.sql(
            "CREATE TABLE t ("
            "id SERIAL PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        engine.sql("INSERT INTO t (created_at) VALUES ('2020-01-01T00:00:00')")
        result = engine.sql("SELECT created_at FROM t")
        assert result.rows[0]["created_at"] == dt.datetime(2020, 1, 1, 0, 0, 0)


# ==================================================================
# ALTER TABLE ADD CONSTRAINT
# ==================================================================


class TestAlterTableAddConstraint:
    """ALTER TABLE ADD CONSTRAINT must work for CHECK, UNIQUE, FK."""

    def test_add_check_constraint(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        engine.sql("INSERT INTO t VALUES (1, 10)")
        engine.sql("ALTER TABLE t ADD CONSTRAINT chk_val CHECK (val > 0)")
        with pytest.raises(ValueError, match="CHECK"):
            engine.sql("INSERT INTO t VALUES (2, -5)")

    def test_add_check_validates_existing(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        engine.sql("INSERT INTO t VALUES (1, -1)")
        with pytest.raises(ValueError, match="violated"):
            engine.sql("ALTER TABLE t ADD CONSTRAINT chk CHECK (val > 0)")

    def test_add_unique_constraint(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, code TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'A')")
        engine.sql("ALTER TABLE t ADD CONSTRAINT uq_code UNIQUE (code)")
        with pytest.raises(ValueError, match="UNIQUE"):
            engine.sql("INSERT INTO t VALUES (2, 'A')")


# ==================================================================
# ON CONFLICT DO NOTHING without column specification
# ==================================================================


class TestOnConflictDoNothing:
    """INSERT ... ON CONFLICT DO NOTHING must work without columns."""

    def test_do_nothing_skips_duplicate_pk(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'a')")
        engine.sql("INSERT INTO t VALUES (1, 'b') ON CONFLICT DO NOTHING")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert result.rows[0]["val"] == "a"

    def test_do_nothing_skips_duplicate_unique(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, code TEXT UNIQUE)")
        engine.sql("INSERT INTO t (code) VALUES ('X')")
        engine.sql("INSERT INTO t (code) VALUES ('X') ON CONFLICT DO NOTHING")
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 1

    def test_do_nothing_inserts_non_duplicate(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'a')")
        engine.sql("INSERT INTO t VALUES (2, 'b') ON CONFLICT DO NOTHING")
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2

    def test_do_nothing_with_explicit_columns(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'a')")
        engine.sql("INSERT INTO t VALUES (1, 'b') ON CONFLICT (id) DO NOTHING")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert result.rows[0]["val"] == "a"


# ==================================================================
# In-memory CREATE INDEX / DROP INDEX
# ==================================================================


class TestInMemoryIndex:
    """CREATE INDEX and DROP INDEX must work in in-memory engines."""

    def test_create_btree_index(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'Alice'), (2, 'Bob')")
        engine.sql("CREATE INDEX idx_name ON t (name)")
        result = engine.sql("SELECT name FROM t WHERE name = 'Alice'")
        assert len(result.rows) == 1

    def test_drop_btree_index(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        engine.sql("CREATE INDEX idx_val ON t (val)")
        engine.sql("DROP INDEX idx_val")
        # After drop, queries still work (just no index)
        engine.sql("INSERT INTO t VALUES (1, 10)")
        result = engine.sql("SELECT val FROM t")
        assert result.rows[0]["val"] == 10

    def test_drop_index_if_exists(self, engine):
        engine.sql("DROP INDEX IF EXISTS nonexistent_idx")

    def test_create_gin_index_in_memory(self, engine):
        engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, body TEXT)")
        engine.sql("INSERT INTO docs (body) VALUES ('hello world')")
        engine.sql("CREATE INDEX idx_body ON docs USING gin (body)")
        # GIN index should enable FTS
        result = engine.sql("SELECT body FROM docs WHERE text_match(body, 'hello')")
        assert len(result.rows) == 1


# ==================================================================
# CREATE SCHEMA / DROP SCHEMA
# ==================================================================


class TestSchemaSupport:
    """Schema namespace must work like PostgreSQL."""

    def test_create_schema(self, engine):
        engine.sql("CREATE SCHEMA myschema")
        assert "myschema" in engine._tables.schemas

    def test_create_schema_if_not_exists(self, engine):
        engine.sql("CREATE SCHEMA myschema")
        engine.sql("CREATE SCHEMA IF NOT EXISTS myschema")

    def test_create_schema_duplicate_raises(self, engine):
        engine.sql("CREATE SCHEMA myschema")
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("CREATE SCHEMA myschema")

    def test_create_table_in_schema(self, engine):
        engine.sql("CREATE SCHEMA sales")
        engine.sql("CREATE TABLE sales.orders (id INTEGER PRIMARY KEY, total INTEGER)")
        engine.sql("INSERT INTO sales.orders VALUES (1, 100)")
        result = engine.sql("SELECT total FROM sales.orders")
        assert result.rows[0]["total"] == 100

    def test_schema_isolation(self, engine):
        engine.sql("CREATE SCHEMA s1")
        engine.sql("CREATE SCHEMA s2")
        engine.sql("CREATE TABLE s1.t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("CREATE TABLE s2.t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO s1.t VALUES (1, 'schema1')")
        engine.sql("INSERT INTO s2.t VALUES (1, 'schema2')")
        r1 = engine.sql("SELECT val FROM s1.t")
        r2 = engine.sql("SELECT val FROM s2.t")
        assert r1.rows[0]["val"] == "schema1"
        assert r2.rows[0]["val"] == "schema2"

    def test_search_path_resolution(self, engine):
        engine.sql("CREATE SCHEMA myschema")
        engine.sql("CREATE TABLE myschema.users (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO myschema.users VALUES (1, 'Alice')")
        engine.sql("SET search_path TO 'myschema', 'public'")
        result = engine.sql("SELECT name FROM users")
        assert result.rows[0]["name"] == "Alice"

    def test_default_public_schema(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t VALUES (1)")
        result = engine.sql("SELECT id FROM public.t")
        assert result.rows[0]["id"] == 1

    def test_drop_schema_empty(self, engine):
        engine.sql("CREATE SCHEMA temp_schema")
        engine.sql("DROP SCHEMA temp_schema")
        assert "temp_schema" not in engine._tables.schemas

    def test_drop_schema_cascade(self, engine):
        engine.sql("CREATE SCHEMA doomed")
        engine.sql("CREATE TABLE doomed.t (id INTEGER)")
        engine.sql("DROP SCHEMA doomed CASCADE")
        assert "doomed" not in engine._tables.schemas

    def test_drop_schema_nonempty_raises(self, engine):
        engine.sql("CREATE SCHEMA nonempty")
        engine.sql("CREATE TABLE nonempty.t (id INTEGER)")
        with pytest.raises(ValueError, match="not empty"):
            engine.sql("DROP SCHEMA nonempty")

    def test_drop_schema_if_exists(self, engine):
        engine.sql("DROP SCHEMA IF EXISTS nonexistent")

    def test_information_schema_tables(self, engine):
        engine.sql("CREATE SCHEMA myschema")
        engine.sql("CREATE TABLE myschema.t (id INTEGER)")
        result = engine.sql(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_name = 't'"
        )
        assert any(r["table_schema"] == "myschema" for r in result.rows)
