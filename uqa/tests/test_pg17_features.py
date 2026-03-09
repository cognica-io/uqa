#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for PostgreSQL 17 P0 feature compatibility."""

from __future__ import annotations

import math
import re

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_data(engine):
    engine.sql("CREATE TABLE users (id INTEGER, name TEXT, age INTEGER)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (3, 'Carol', 35)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (4, 'Dave', 25)")
    return engine


# ==================================================================
# Step 1a: CREATE TABLE IF NOT EXISTS
# ==================================================================


class TestCreateTableIfNotExists:
    def test_basic_if_not_exists(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER)")
        # Should not raise
        result = engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        assert result.rows == []
        assert result.columns == []

    def test_if_not_exists_returns_empty(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER)")
        result = engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        assert result.rows == []

    def test_without_if_not_exists_raises(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER)")
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("CREATE TABLE t (id INTEGER)")

    def test_if_not_exists_preserves_data(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO t (id, val) VALUES (1, 'hello')")
        engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER, val TEXT)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert result.rows[0]["val"] == "hello"


# ==================================================================
# Step 1b: NULLS FIRST / NULLS LAST
# ==================================================================


class TestNullsOrdering:
    @pytest.fixture
    def null_data(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val INTEGER)")
        engine.sql("INSERT INTO t (id, val) VALUES (1, 10)")
        engine.sql("INSERT INTO t (id, val) VALUES (2, 20)")
        engine.sql("INSERT INTO t (id) VALUES (3)")  # val is NULL
        engine.sql("INSERT INTO t (id, val) VALUES (4, 5)")
        return engine

    def test_nulls_first_asc(self, null_data):
        result = null_data.sql(
            "SELECT id, val FROM t ORDER BY val ASC NULLS FIRST"
        )
        vals = [r["val"] for r in result.rows]
        assert vals[0] is None
        assert vals[1:] == [5, 10, 20]

    def test_nulls_last_asc(self, null_data):
        result = null_data.sql(
            "SELECT id, val FROM t ORDER BY val ASC NULLS LAST"
        )
        vals = [r["val"] for r in result.rows]
        assert vals[-1] is None
        assert vals[:-1] == [5, 10, 20]

    def test_nulls_first_desc(self, null_data):
        result = null_data.sql(
            "SELECT id, val FROM t ORDER BY val DESC NULLS FIRST"
        )
        vals = [r["val"] for r in result.rows]
        assert vals[0] is None
        assert vals[1:] == [20, 10, 5]

    def test_nulls_last_desc(self, null_data):
        result = null_data.sql(
            "SELECT id, val FROM t ORDER BY val DESC NULLS LAST"
        )
        vals = [r["val"] for r in result.rows]
        assert vals[-1] is None
        assert vals[:-1] == [20, 10, 5]

    def test_default_nulls_last(self, null_data):
        result = null_data.sql(
            "SELECT id, val FROM t ORDER BY val ASC"
        )
        vals = [r["val"] for r in result.rows]
        # Default: NULLs last for ASC
        assert vals[-1] is None


# ==================================================================
# Step 1c: Column alias in ORDER BY
# ==================================================================


class TestColumnAliasOrderBy:
    def test_order_by_alias(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age AS user_age FROM users ORDER BY user_age DESC"
        )
        ages = [r["user_age"] for r in result.rows]
        assert ages == [35, 30, 25, 25]

    def test_order_by_ordinal(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age FROM users ORDER BY 2 ASC"
        )
        ages = [r["age"] for r in result.rows]
        assert ages == [25, 25, 30, 35]

    def test_order_by_ordinal_desc(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age FROM users ORDER BY 2 DESC, 1 ASC"
        )
        names = [r["name"] for r in result.rows]
        assert names[0] == "Carol"  # age 35
        assert names[-1] in ("Bob", "Dave")  # age 25

    def test_order_by_invalid_ordinal(self, engine_with_data):
        with pytest.raises(ValueError, match="not in select list"):
            engine_with_data.sql(
                "SELECT name FROM users ORDER BY 5"
            )


# ==================================================================
# Step 2a: GREATEST / LEAST / NULLIF
# ==================================================================


class TestGreatestLeastNullif:
    def test_greatest_basic(self, engine):
        result = engine.sql("SELECT GREATEST(1, 5, 3)")
        assert result.rows[0][result.columns[0]] == 5

    def test_greatest_with_nulls(self, engine):
        result = engine.sql("SELECT GREATEST(1, NULL, 3)")
        assert result.rows[0][result.columns[0]] == 3

    def test_greatest_all_null(self, engine):
        result = engine.sql("SELECT GREATEST(NULL, NULL)")
        assert result.rows[0][result.columns[0]] is None

    def test_least_basic(self, engine):
        result = engine.sql("SELECT LEAST(10, 5, 8)")
        assert result.rows[0][result.columns[0]] == 5

    def test_least_with_nulls(self, engine):
        result = engine.sql("SELECT LEAST(10, NULL, 3)")
        assert result.rows[0][result.columns[0]] == 3

    def test_nullif_equal(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT NULLIF(age, 25) AS result FROM users WHERE name = 'Bob'"
        )
        assert result.rows[0]["result"] is None

    def test_nullif_not_equal(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT NULLIF(age, 99) AS result FROM users WHERE name = 'Alice'"
        )
        assert result.rows[0]["result"] == 30

    def test_nullif_null(self, engine):
        result = engine.sql("SELECT NULLIF(NULL, NULL)")
        assert result.rows[0][result.columns[0]] is None


# ==================================================================
# Step 2b: String functions
# ==================================================================


class TestStringFunctions:
    def test_position(self, engine):
        result = engine.sql("SELECT POSITION('lo' IN 'hello world')")
        assert result.rows[0][result.columns[0]] == 4

    def test_position_not_found(self, engine):
        result = engine.sql("SELECT POSITION('xyz' IN 'hello')")
        assert result.rows[0][result.columns[0]] == 0

    def test_char_length(self, engine):
        result = engine.sql("SELECT CHAR_LENGTH('hello')")
        assert result.rows[0][result.columns[0]] == 5

    def test_lpad(self, engine):
        result = engine.sql("SELECT LPAD('hi', 5, 'x')")
        assert result.rows[0][result.columns[0]] == "xxxhi"

    def test_lpad_default_fill(self, engine):
        result = engine.sql("SELECT LPAD('hi', 5)")
        assert result.rows[0][result.columns[0]] == "   hi"

    def test_lpad_truncate(self, engine):
        result = engine.sql("SELECT LPAD('hello', 3)")
        assert result.rows[0][result.columns[0]] == "hel"

    def test_rpad(self, engine):
        result = engine.sql("SELECT RPAD('hi', 5, 'x')")
        assert result.rows[0][result.columns[0]] == "hixxx"

    def test_repeat(self, engine):
        result = engine.sql("SELECT REPEAT('ab', 3)")
        assert result.rows[0][result.columns[0]] == "ababab"

    def test_reverse(self, engine):
        result = engine.sql("SELECT REVERSE('hello')")
        assert result.rows[0][result.columns[0]] == "olleh"

    def test_split_part(self, engine):
        result = engine.sql("SELECT SPLIT_PART('a,b,c', ',', 2)")
        assert result.rows[0][result.columns[0]] == "b"

    def test_split_part_out_of_range(self, engine):
        result = engine.sql("SELECT SPLIT_PART('a,b', ',', 5)")
        assert result.rows[0][result.columns[0]] == ""


# ==================================================================
# Step 2c: Math functions
# ==================================================================


class TestMathFunctions:
    def test_power(self, engine):
        result = engine.sql("SELECT POWER(2, 10)")
        assert result.rows[0][result.columns[0]] == 1024

    def test_pow(self, engine):
        result = engine.sql("SELECT POW(3, 2)")
        assert result.rows[0][result.columns[0]] == 9

    def test_sqrt(self, engine):
        result = engine.sql("SELECT SQRT(16)")
        assert result.rows[0][result.columns[0]] == pytest.approx(4.0)

    def test_log(self, engine):
        result = engine.sql("SELECT LOG(100)")
        assert result.rows[0][result.columns[0]] == pytest.approx(2.0)

    def test_ln(self, engine):
        result = engine.sql("SELECT LN(1)")
        assert result.rows[0][result.columns[0]] == pytest.approx(0.0)

    def test_exp(self, engine):
        result = engine.sql("SELECT EXP(0)")
        assert result.rows[0][result.columns[0]] == pytest.approx(1.0)

    def test_mod(self, engine):
        result = engine.sql("SELECT MOD(10, 3)")
        assert result.rows[0][result.columns[0]] == 1

    def test_trunc(self, engine):
        result = engine.sql("SELECT TRUNC(3.7)")
        assert result.rows[0][result.columns[0]] == 3

    def test_trunc_with_precision(self, engine):
        result = engine.sql("SELECT TRUNC(3.456, 2)")
        assert result.rows[0][result.columns[0]] == pytest.approx(3.45)

    def test_sign_positive(self, engine):
        result = engine.sql("SELECT SIGN(42)")
        assert result.rows[0][result.columns[0]] == 1

    def test_sign_negative(self, engine):
        result = engine.sql("SELECT SIGN(-5)")
        assert result.rows[0][result.columns[0]] == -1

    def test_sign_zero(self, engine):
        result = engine.sql("SELECT SIGN(0)")
        assert result.rows[0][result.columns[0]] == 0

    def test_pi(self, engine):
        result = engine.sql("SELECT PI()")
        assert result.rows[0][result.columns[0]] == pytest.approx(math.pi)

    def test_random(self, engine):
        result = engine.sql("SELECT RANDOM()")
        val = result.rows[0][result.columns[0]]
        assert 0.0 <= val < 1.0


# ==================================================================
# Step 3a: COUNT(DISTINCT) and STRING_AGG
# ==================================================================


class TestCountDistinct:
    def test_count_distinct_basic(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT COUNT(DISTINCT age) AS cnt FROM users"
        )
        assert result.rows[0]["cnt"] == 3  # 25, 30, 35

    def test_count_distinct_with_group_by(self, engine):
        engine.sql(
            "CREATE TABLE sales (dept TEXT, product TEXT)"
        )
        engine.sql(
            "INSERT INTO sales (dept, product) VALUES ('A', 'x')"
        )
        engine.sql(
            "INSERT INTO sales (dept, product) VALUES ('A', 'x')"
        )
        engine.sql(
            "INSERT INTO sales (dept, product) VALUES ('A', 'y')"
        )
        engine.sql(
            "INSERT INTO sales (dept, product) VALUES ('B', 'z')"
        )
        result = engine.sql(
            "SELECT dept, COUNT(DISTINCT product) AS cnt "
            "FROM sales GROUP BY dept ORDER BY dept"
        )
        assert result.rows[0]["cnt"] == 2  # dept A: x, y
        assert result.rows[1]["cnt"] == 1  # dept B: z

    def test_count_distinct_with_nulls(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO t (id, val) VALUES (1, 'a')")
        engine.sql("INSERT INTO t (id, val) VALUES (2, 'a')")
        engine.sql("INSERT INTO t (id) VALUES (3)")
        result = engine.sql("SELECT COUNT(DISTINCT val) AS cnt FROM t")
        # NULL is not counted
        assert result.rows[0]["cnt"] == 1


class TestStringAgg:
    def test_string_agg_basic(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT STRING_AGG(name, ', ') AS names FROM users"
        )
        names = result.rows[0]["names"]
        assert "Alice" in names
        assert "Bob" in names
        assert ", " in names

    def test_string_agg_with_group_by(self, engine):
        engine.sql("CREATE TABLE items (category TEXT, name TEXT)")
        engine.sql(
            "INSERT INTO items (category, name) VALUES ('fruit', 'apple')"
        )
        engine.sql(
            "INSERT INTO items (category, name) VALUES ('fruit', 'banana')"
        )
        engine.sql(
            "INSERT INTO items (category, name) VALUES ('veggie', 'carrot')"
        )
        result = engine.sql(
            "SELECT category, STRING_AGG(name, ',') AS items "
            "FROM items GROUP BY category ORDER BY category"
        )
        assert result.rows[0]["items"] in ("apple,banana", "banana,apple")
        assert result.rows[1]["items"] == "carrot"

    def test_string_agg_all_null(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        engine.sql("INSERT INTO t (id) VALUES (2)")
        result = engine.sql(
            "SELECT STRING_AGG(val, ',') AS vals FROM t"
        )
        assert result.rows[0]["vals"] is None

    def test_string_agg_custom_delimiter(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT STRING_AGG(name, ' | ') AS names FROM users"
        )
        names = result.rows[0]["names"]
        assert " | " in names


# ==================================================================
# Step 4a: INSERT INTO ... SELECT
# ==================================================================


class TestInsertSelect:
    def test_insert_select_basic(self, engine_with_data):
        engine_with_data.sql(
            "CREATE TABLE users_copy (id INTEGER, name TEXT, age INTEGER)"
        )
        result = engine_with_data.sql(
            "INSERT INTO users_copy (id, name, age) "
            "SELECT id, name, age FROM users"
        )
        assert result.rows[0]["inserted"] == 4

        result = engine_with_data.sql(
            "SELECT COUNT(*) AS cnt FROM users_copy"
        )
        assert result.rows[0]["cnt"] == 4

    def test_insert_select_with_where(self, engine_with_data):
        engine_with_data.sql(
            "CREATE TABLE young (id INTEGER, name TEXT, age INTEGER)"
        )
        engine_with_data.sql(
            "INSERT INTO young (id, name, age) "
            "SELECT id, name, age FROM users WHERE age < 30"
        )
        result = engine_with_data.sql(
            "SELECT COUNT(*) AS cnt FROM young"
        )
        assert result.rows[0]["cnt"] == 2

    def test_insert_select_with_columns(self, engine_with_data):
        engine_with_data.sql(
            "CREATE TABLE names (name TEXT)"
        )
        engine_with_data.sql(
            "INSERT INTO names (name) SELECT name FROM users"
        )
        result = engine_with_data.sql(
            "SELECT COUNT(*) AS cnt FROM names"
        )
        assert result.rows[0]["cnt"] == 4

    def test_insert_select_empty(self, engine_with_data):
        engine_with_data.sql(
            "CREATE TABLE empty (id INTEGER, name TEXT, age INTEGER)"
        )
        result = engine_with_data.sql(
            "INSERT INTO empty (id, name, age) "
            "SELECT id, name, age FROM users WHERE age > 100"
        )
        assert result.rows[0]["inserted"] == 0


# ==================================================================
# Step 4b: Derived tables (subquery in FROM)
# ==================================================================


class TestDerivedTables:
    def test_simple_derived_table(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age FROM "
            "(SELECT name, age FROM users WHERE age >= 30) AS older"
        )
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}

    def test_derived_table_with_where(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name FROM "
            "(SELECT name, age FROM users) AS t "
            "WHERE age = 25"
        )
        names = {r["name"] for r in result.rows}
        assert names == {"Bob", "Dave"}

    def test_derived_table_with_aggregation(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT COUNT(*) AS cnt FROM "
            "(SELECT name FROM users WHERE age > 25) AS t"
        )
        assert result.rows[0]["cnt"] == 2

    def test_nested_derived_tables(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name FROM "
            "(SELECT name, age FROM "
            " (SELECT name, age FROM users) AS inner_t "
            " WHERE age >= 30"
            ") AS outer_t"
        )
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}


# ==================================================================
# Step 4c: UNION / INTERSECT / EXCEPT
# ==================================================================


class TestSetOperations:
    @pytest.fixture
    def two_tables(self, engine):
        engine.sql(
            "CREATE TABLE t1 (id INTEGER, val TEXT)"
        )
        engine.sql(
            "CREATE TABLE t2 (id INTEGER, val TEXT)"
        )
        engine.sql("INSERT INTO t1 (id, val) VALUES (1, 'a')")
        engine.sql("INSERT INTO t1 (id, val) VALUES (2, 'b')")
        engine.sql("INSERT INTO t1 (id, val) VALUES (3, 'c')")
        engine.sql("INSERT INTO t2 (id, val) VALUES (2, 'b')")
        engine.sql("INSERT INTO t2 (id, val) VALUES (3, 'c')")
        engine.sql("INSERT INTO t2 (id, val) VALUES (4, 'd')")
        return engine

    def test_union_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 UNION ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 6

    def test_union_distinct(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 UNION SELECT id, val FROM t2"
        )
        assert len(result.rows) == 4  # 1a, 2b, 3c, 4d

    def test_intersect(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 INTERSECT SELECT id, val FROM t2"
        )
        assert len(result.rows) == 2  # 2b, 3c

    def test_intersect_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 INTERSECT ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 2

    def test_except(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 EXCEPT SELECT id, val FROM t2"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["val"] == "a"

    def test_except_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 EXCEPT ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["val"] == "a"

    def test_union_with_order_by(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 "
            "UNION ALL "
            "SELECT id, val FROM t2 "
            "ORDER BY 1"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == sorted(ids)

    def test_union_with_limit(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 "
            "UNION ALL "
            "SELECT id, val FROM t2 "
            "ORDER BY 1 "
            "LIMIT 3"
        )
        assert len(result.rows) == 3

    def test_column_count_mismatch_error(self, two_tables):
        with pytest.raises(ValueError, match="column count mismatch"):
            two_tables.sql(
                "SELECT id, val FROM t1 UNION SELECT id FROM t2"
            )

    def test_chained_union(self, two_tables):
        two_tables.sql("CREATE TABLE t3 (id INTEGER, val TEXT)")
        two_tables.sql("INSERT INTO t3 (id, val) VALUES (5, 'e')")
        result = two_tables.sql(
            "SELECT id, val FROM t1 "
            "UNION ALL SELECT id, val FROM t2 "
            "UNION ALL SELECT id, val FROM t3"
        )
        assert len(result.rows) == 7  # 3 + 3 + 1


# ==================================================================
# Step 5a: DATE / TIMESTAMP type support
# ==================================================================


class TestDateTimeTypes:
    def test_create_table_with_date(self, engine):
        engine.sql(
            "CREATE TABLE events (id INTEGER, event_date DATE)"
        )
        result = engine.sql(
            "INSERT INTO events (id, event_date) "
            "VALUES (1, '2024-01-15')"
        )
        assert result.rows[0]["inserted"] == 1

    def test_insert_date_values(self, engine):
        engine.sql(
            "CREATE TABLE log (id INTEGER, ts TIMESTAMP)"
        )
        engine.sql(
            "INSERT INTO log (id, ts) VALUES (1, '2024-06-15T10:30:00')"
        )
        engine.sql(
            "INSERT INTO log (id, ts) VALUES (2, '2024-06-16T14:00:00')"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM log")
        assert result.rows[0]["cnt"] == 2

    def test_date_comparison(self, engine):
        engine.sql(
            "CREATE TABLE events (id INTEGER, event_date DATE)"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (1, '2024-01-01')"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (2, '2024-06-15')"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (3, '2024-12-31')"
        )
        result = engine.sql(
            "SELECT id FROM events WHERE event_date > '2024-03-01'"
        )
        ids = {r["id"] for r in result.rows}
        assert ids == {2, 3}

    def test_date_ordering(self, engine):
        engine.sql(
            "CREATE TABLE events (id INTEGER, event_date DATE)"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (1, '2024-12-31')"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (2, '2024-01-01')"
        )
        engine.sql(
            "INSERT INTO events (id, event_date) VALUES (3, '2024-06-15')"
        )
        result = engine.sql(
            "SELECT id, event_date FROM events ORDER BY event_date ASC"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == [2, 3, 1]


# ==================================================================
# Step 5b: NOW() / CURRENT_DATE / CURRENT_TIMESTAMP
# ==================================================================


class TestDateTimeFunctions:
    def test_now(self, engine):
        result = engine.sql("SELECT NOW() AS ts")
        ts = result.rows[0]["ts"]
        # Should be ISO format datetime string
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_current_date(self, engine):
        result = engine.sql("SELECT CURRENT_DATE AS d")
        d = result.rows[0]["d"]
        assert re.match(r"\d{4}-\d{2}-\d{2}$", d)

    def test_current_timestamp(self, engine):
        result = engine.sql("SELECT CURRENT_TIMESTAMP AS ts")
        ts = result.rows[0]["ts"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)


# ==================================================================
# Step 5c: EXTRACT / DATE_PART / DATE_TRUNC
# ==================================================================


class TestExtractDatePartDateTrunc:
    @pytest.fixture
    def ts_table(self, engine):
        engine.sql(
            "CREATE TABLE log (id INTEGER, ts TIMESTAMP)"
        )
        engine.sql(
            "INSERT INTO log (id, ts) "
            "VALUES (1, '2024-06-15T10:30:45')"
        )
        return engine

    def test_extract_year(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(year FROM ts) AS y FROM log"
        )
        assert result.rows[0]["y"] == 2024

    def test_extract_month(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(month FROM ts) AS m FROM log"
        )
        assert result.rows[0]["m"] == 6

    def test_extract_day(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(day FROM ts) AS d FROM log"
        )
        assert result.rows[0]["d"] == 15

    def test_extract_hour(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(hour FROM ts) AS h FROM log"
        )
        assert result.rows[0]["h"] == 10

    def test_extract_dow(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(dow FROM ts) AS dow FROM log"
        )
        # 2024-06-15 is a Saturday -> PostgreSQL dow=6
        assert result.rows[0]["dow"] == 6

    def test_extract_epoch(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(epoch FROM ts) AS e FROM log"
        )
        assert isinstance(result.rows[0]["e"], float)

    def test_date_part(self, ts_table):
        result = ts_table.sql(
            "SELECT DATE_PART('year', ts) AS y FROM log"
        )
        assert result.rows[0]["y"] == 2024

    def test_date_trunc_year(self, ts_table):
        result = ts_table.sql(
            "SELECT DATE_TRUNC('year', ts) AS t FROM log"
        )
        assert result.rows[0]["t"].startswith("2024-01-01")

    def test_date_trunc_month(self, ts_table):
        result = ts_table.sql(
            "SELECT DATE_TRUNC('month', ts) AS t FROM log"
        )
        assert result.rows[0]["t"].startswith("2024-06-01")

    def test_date_trunc_day(self, ts_table):
        result = ts_table.sql(
            "SELECT DATE_TRUNC('day', ts) AS t FROM log"
        )
        assert result.rows[0]["t"].startswith("2024-06-15T00:00:00")

    def test_extract_quarter(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(quarter FROM ts) AS q FROM log"
        )
        assert result.rows[0]["q"] == 2

    def test_extract_week(self, ts_table):
        result = ts_table.sql(
            "SELECT EXTRACT(week FROM ts) AS w FROM log"
        )
        assert isinstance(result.rows[0]["w"], int)
        assert 1 <= result.rows[0]["w"] <= 53


# ==================================================================
# Additional coverage: LOG(b, x), CHARACTER_LENGTH, STRPOS,
# STRING_AGG DISTINCT, derived table alias collision
# ==================================================================


class TestLogTwoArgs:
    def test_log_base_2(self, engine):
        result = engine.sql("SELECT LOG(2, 8) AS val")
        assert result.rows[0]["val"] == pytest.approx(3.0)

    def test_log_base_10_explicit(self, engine):
        result = engine.sql("SELECT LOG(10, 1000) AS val")
        assert result.rows[0]["val"] == pytest.approx(3.0)

    def test_log_single_arg_unchanged(self, engine):
        result = engine.sql("SELECT LOG(100) AS val")
        assert result.rows[0]["val"] == pytest.approx(2.0)


class TestStringFunctionAliases:
    def test_character_length(self, engine):
        result = engine.sql("SELECT CHARACTER_LENGTH('hello') AS len")
        assert result.rows[0]["len"] == 5

    def test_strpos(self, engine):
        result = engine.sql("SELECT STRPOS('hello world', 'lo') AS pos")
        assert result.rows[0]["pos"] == 4


class TestStringAggDistinct:
    def test_string_agg_distinct(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO t (id, val) VALUES (1, 'a')")
        engine.sql("INSERT INTO t (id, val) VALUES (2, 'b')")
        engine.sql("INSERT INTO t (id, val) VALUES (3, 'a')")
        engine.sql("INSERT INTO t (id, val) VALUES (4, 'c')")
        result = engine.sql(
            "SELECT STRING_AGG(DISTINCT val, ',') AS vals FROM t"
        )
        parts = set(result.rows[0]["vals"].split(","))
        assert parts == {"a", "b", "c"}


class TestDerivedTableAliasCollision:
    def test_alias_does_not_destroy_real_table(self, engine):
        engine.sql(
            "CREATE TABLE users (id INTEGER, name TEXT)"
        )
        engine.sql(
            "INSERT INTO users (id, name) VALUES (1, 'Alice')"
        )
        engine.sql(
            "INSERT INTO users (id, name) VALUES (2, 'Bob')"
        )
        # Use alias "users" -- same as the real table name
        result = engine.sql(
            "SELECT name FROM "
            "(SELECT id, name FROM users WHERE id = 1) AS users"
        )
        assert result.rows[0]["name"] == "Alice"

        # Real table must still be intact after the query
        result = engine.sql("SELECT COUNT(*) AS cnt FROM users")
        assert result.rows[0]["cnt"] == 2
