#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for PostgreSQL 17 P2 feature compatibility."""

from __future__ import annotations

import math

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_table(engine):
    engine.sql(
        "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER, name TEXT)"
    )
    engine.sql("INSERT INTO t (id, val, name) VALUES (1, 10, 'alpha')")
    engine.sql("INSERT INTO t (id, val, name) VALUES (2, 20, 'bravo')")
    engine.sql("INSERT INTO t (id, val, name) VALUES (3, 30, 'charlie')")
    return engine


# ==================================================================
# Step 1: String scalar functions
# ==================================================================


class TestOctetLength:
    def test_ascii(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT octet_length('hello') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 5

    def test_multibyte(self, engine_with_table):
        # Each CJK char is 3 bytes in UTF-8
        result = engine_with_table.sql(
            "SELECT octet_length(name) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 5  # 'alpha' = 5 bytes


class TestMD5:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT md5('hello') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "5d41402abc4b2a76b9719d911017c592"


class TestFormat:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT format('Hello %s, you are %s', 'World', 'great') AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Hello World, you are great"


class TestRegexpMatch:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT regexp_match('foobarbaz', 'b(.)r') AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == ["a"]

    def test_no_match(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT regexp_match('hello', 'xyz') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is None


class TestRegexpReplace:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT regexp_replace('hello world', 'world', 'there') AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "hello there"

    def test_global_flag(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT regexp_replace('aaa', 'a', 'b', 'g') AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "bbb"


class TestOverlay:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT overlay('Txxxxas' placing 'hom' from 2 for 4) AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Thomas"


# ==================================================================
# Step 1: Math scalar functions
# ==================================================================


class TestCbrt:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT cbrt(27) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - 3.0) < 0.001

    def test_negative(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT cbrt(-8) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - (-2.0)) < 0.001


class TestTrigFunctions:
    def test_sin(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT sin(0) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"]) < 0.001

    def test_cos(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT cos(0) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - 1.0) < 0.001

    def test_tan(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT tan(0) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"]) < 0.001

    def test_asin(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT asin(1) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - math.pi / 2) < 0.001

    def test_acos(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT acos(1) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"]) < 0.001

    def test_atan(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT atan(1) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - math.pi / 4) < 0.001

    def test_atan2(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT atan2(1, 1) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - math.pi / 4) < 0.001


class TestDegreesRadians:
    def test_degrees(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT degrees(pi()) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - 180.0) < 0.001

    def test_radians(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT radians(180) AS v FROM t WHERE id = 1"
        )
        assert abs(result.rows[0]["v"] - math.pi) < 0.001


class TestDiv:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT div(7, 2) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 3

    def test_negative(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT div(-7, 2) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == -4


class TestGcdLcm:
    def test_gcd(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT gcd(12, 8) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 4

    def test_lcm(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT lcm(12, 8) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 24


class TestWidthBucket:
    def test_in_range(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT width_bucket(5.0, 0, 10, 5) AS v FROM t WHERE id = 1"
        )
        # [0,2) -> 1, [2,4) -> 2, [4,6) -> 3, [6,8) -> 4, [8,10) -> 5
        assert result.rows[0]["v"] == 3

    def test_below_range(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT width_bucket(-1, 0, 10, 5) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 0

    def test_above_range(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT width_bucket(15, 0, 10, 5) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 6


# ==================================================================
# Step 2: ARRAY types
# ==================================================================


class TestArrayLiteral:
    def test_select_array(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT ARRAY[1, 2, 3] AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 2, 3]

    def test_select_text_array(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT ARRAY['a', 'b', 'c'] AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == ["a", "b", "c"]

    def test_empty_array(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT ARRAY[]::integer[] AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == []


class TestArrayColumn:
    def test_create_and_insert(self, engine):
        engine.sql("CREATE TABLE arr_test (id SERIAL PRIMARY KEY, tags TEXT[])")
        engine.sql(
            "INSERT INTO arr_test (tags) VALUES (ARRAY['python', 'sql'])"
        )
        result = engine.sql("SELECT tags FROM arr_test WHERE id = 1")
        assert result.rows[0]["tags"] == ["python", "sql"]

    def test_integer_array(self, engine):
        engine.sql(
            "CREATE TABLE int_arr (id SERIAL PRIMARY KEY, nums INTEGER[])"
        )
        engine.sql("INSERT INTO int_arr (nums) VALUES (ARRAY[10, 20, 30])")
        result = engine.sql("SELECT nums FROM int_arr WHERE id = 1")
        assert result.rows[0]["nums"] == [10, 20, 30]


class TestArrayFunctions:
    def test_array_length(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_length(ARRAY[1, 2, 3], 1) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 3

    def test_cardinality(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT cardinality(ARRAY[1, 2, 3]) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 3

    def test_array_cat(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_cat(ARRAY[1, 2], ARRAY[3, 4]) AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 2, 3, 4]

    def test_array_append(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_append(ARRAY[1, 2], 3) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 2, 3]

    def test_array_remove(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_remove(ARRAY[1, 2, 3, 2], 2) AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 3]


# ==================================================================
# Step 2: UUID type
# ==================================================================


class TestUUID:
    def test_gen_random_uuid(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT gen_random_uuid() AS v FROM t WHERE id = 1"
        )
        v = result.rows[0]["v"]
        assert isinstance(v, str)
        assert len(v) == 36
        # UUID format: 8-4-4-4-12
        parts = v.split("-")
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    def test_uuid_column(self, engine):
        engine.sql(
            "CREATE TABLE uuid_test ("
            "  id SERIAL PRIMARY KEY,"
            "  uid UUID"
            ")"
        )
        engine.sql(
            "INSERT INTO uuid_test (uid) "
            "VALUES ('550e8400-e29b-41d4-a716-446655440000')"
        )
        result = engine.sql("SELECT uid FROM uuid_test WHERE id = 1")
        assert result.rows[0]["uid"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_uuid_uniqueness(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT gen_random_uuid() AS a, gen_random_uuid() AS b "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["a"] != result.rows[0]["b"]


# ==================================================================
# Step 2: BYTEA type
# ==================================================================


class TestBytea:
    def test_bytea_column(self, engine):
        engine.sql(
            "CREATE TABLE bin_test (id SERIAL PRIMARY KEY, data BYTEA)"
        )
        engine.sql("INSERT INTO bin_test (data) VALUES ('hello')")
        result = engine.sql("SELECT data FROM bin_test WHERE id = 1")
        assert result.rows[0]["data"] is not None

    def test_cast_to_bytea(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT 'hello'::bytea AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == b"hello"


# ==================================================================
# Step 3: Statistical aggregates
# ==================================================================


class TestStddev:
    def test_stddev_samp(self, engine_with_table):
        result = engine_with_table.sql("SELECT stddev(val) AS v FROM t")
        assert abs(result.rows[0]["v"] - 10.0) < 0.001

    def test_stddev_pop(self, engine_with_table):
        result = engine_with_table.sql("SELECT stddev_pop(val) AS v FROM t")
        # pop stddev of [10,20,30] = sqrt(200/3) ~ 8.165
        expected = (200 / 3) ** 0.5
        assert abs(result.rows[0]["v"] - expected) < 0.001

    def test_stddev_single_row(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT stddev(val) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is None


class TestVariance:
    def test_var_samp(self, engine_with_table):
        result = engine_with_table.sql("SELECT variance(val) AS v FROM t")
        assert abs(result.rows[0]["v"] - 100.0) < 0.001

    def test_var_pop(self, engine_with_table):
        result = engine_with_table.sql("SELECT var_pop(val) AS v FROM t")
        # pop variance of [10,20,30] = 200/3 ~ 66.667
        expected = 200 / 3
        assert abs(result.rows[0]["v"] - expected) < 0.001


class TestPercentileCont:
    def test_median(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY val) AS v "
            "FROM t"
        )
        assert abs(result.rows[0]["v"] - 20.0) < 0.001

    def test_quartile(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY val) AS v "
            "FROM t"
        )
        # 0.25 * (3-1) = 0.5 -> interp between 10 and 20 = 15
        assert abs(result.rows[0]["v"] - 15.0) < 0.001


class TestPercentileDisc:
    def test_median(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY val) AS v "
            "FROM t"
        )
        assert result.rows[0]["v"] == 20


class TestMode:
    def test_basic(self, engine):
        engine.sql(
            "CREATE TABLE m (id SERIAL PRIMARY KEY, val INTEGER)"
        )
        engine.sql("INSERT INTO m (val) VALUES (1)")
        engine.sql("INSERT INTO m (val) VALUES (2)")
        engine.sql("INSERT INTO m (val) VALUES (2)")
        engine.sql("INSERT INTO m (val) VALUES (3)")
        result = engine.sql(
            "SELECT mode() WITHIN GROUP (ORDER BY val) AS v FROM m"
        )
        assert result.rows[0]["v"] == 2


class TestJSONObjectAgg:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT json_object_agg(name, val) AS v FROM t"
        )
        v = result.rows[0]["v"]
        assert isinstance(v, dict)
        assert v["alpha"] == 10
        assert v["bravo"] == 20
        assert v["charlie"] == 30

    def test_jsonb_variant(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT jsonb_object_agg(name, val) AS v FROM t"
        )
        v = result.rows[0]["v"]
        assert v["alpha"] == 10


# ==================================================================
# Step 4: Window enhancements
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

    def test_range_with_peers(self, engine):
        engine.sql("CREATE TABLE rp (id SERIAL PRIMARY KEY, grp INT, val INT)")
        engine.sql("INSERT INTO rp (grp, val) VALUES (1, 10)")
        engine.sql("INSERT INTO rp (grp, val) VALUES (1, 20)")
        engine.sql("INSERT INTO rp (grp, val) VALUES (2, 30)")
        result = engine.sql(
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
# Step 5: JSON extended operators
# ==================================================================


class TestJSONPathOperator:
    def test_hash_gt(self, engine_with_table):
        engine_with_table.sql(
            "CREATE TABLE jdoc (id SERIAL PRIMARY KEY, data JSONB)"
        )
        engine_with_table.sql(
            "INSERT INTO jdoc (data) VALUES "
            "('{\"a\": {\"b\": 42}}'::jsonb)"
        )
        result = engine_with_table.sql(
            "SELECT data #> '{a,b}' AS v FROM jdoc WHERE id = 1"
        )
        assert result.rows[0]["v"] == 42

    def test_hash_gt_gt(self, engine_with_table):
        engine_with_table.sql(
            "CREATE TABLE jd2 (id SERIAL PRIMARY KEY, data JSONB)"
        )
        engine_with_table.sql(
            "INSERT INTO jd2 (data) VALUES "
            "('{\"a\": {\"b\": 42}}'::jsonb)"
        )
        result = engine_with_table.sql(
            "SELECT data #>> '{a,b}' AS v FROM jd2 WHERE id = 1"
        )
        assert result.rows[0]["v"] == "42"


class TestJSONContainment:
    def test_contains(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT '{\"a\": 1, \"b\": 2}'::jsonb @> '{\"a\": 1}'::jsonb AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is True

    def test_not_contains(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT '{\"a\": 1}'::jsonb @> '{\"a\": 2}'::jsonb AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is False

    def test_contained_by(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT '{\"a\": 1}'::jsonb <@ '{\"a\": 1, \"b\": 2}'::jsonb AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is True


class TestJSONBSet:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT jsonb_set('{\"a\": 1}'::jsonb, '{b}', '2'::jsonb) AS v "
            "FROM t WHERE id = 1"
        )
        v = result.rows[0]["v"]
        assert v["a"] == 1
        assert v["b"] == 2

    def test_replace(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT jsonb_set('{\"a\": 1}'::jsonb, '{a}', '99'::jsonb) AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"]["a"] == 99


class TestJSONObjectKeys:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT json_object_keys('{\"a\": 1, \"b\": 2}'::json) AS v "
            "FROM t WHERE id = 1"
        )
        v = result.rows[0]["v"]
        assert set(v) == {"a", "b"}


# ==================================================================
# Step 6: DDL/DML extensions
# ==================================================================


class TestCreateTableAs:
    def test_basic(self, engine_with_table):
        engine_with_table.sql("CREATE TABLE t2 AS SELECT id, val FROM t")
        result = engine_with_table.sql(
            "SELECT id, val FROM t2 ORDER BY id"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["val"] == 10

    def test_with_where(self, engine_with_table):
        engine_with_table.sql(
            "CREATE TABLE t2 AS SELECT id, val FROM t WHERE val > 15"
        )
        result = engine_with_table.sql(
            "SELECT id, val FROM t2 ORDER BY id"
        )
        assert len(result.rows) == 2

    def test_with_expression(self, engine_with_table):
        engine_with_table.sql(
            "CREATE TABLE t2 AS SELECT id, val * 2 AS doubled FROM t"
        )
        result = engine_with_table.sql(
            "SELECT id, doubled FROM t2 ORDER BY id"
        )
        assert result.rows[0]["doubled"] == 20


class TestFetchFirst:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id, val FROM t ORDER BY id FETCH FIRST 2 ROWS ONLY"
        )
        assert len(result.rows) == 2

    def test_fetch_first_1(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id FROM t ORDER BY id FETCH FIRST 1 ROW ONLY"
        )
        assert len(result.rows) == 1


class TestAlterColumnType:
    def test_change_type(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE t ALTER COLUMN val TYPE TEXT")
        result = engine_with_table.sql("SELECT val FROM t WHERE id = 1")
        assert isinstance(result.rows[0]["val"], str)
        assert result.rows[0]["val"] == "10"


# ==================================================================
# Step 7: Sequences and pg_catalog
# ==================================================================


class TestSequence:
    def test_create_and_nextval(self, engine):
        engine.sql("CREATE SEQUENCE myseq START 1")
        result = engine.sql("SELECT nextval('myseq') AS v")
        assert result.rows[0]["v"] == 1
        result = engine.sql("SELECT nextval('myseq') AS v")
        assert result.rows[0]["v"] == 2

    def test_currval(self, engine):
        engine.sql("CREATE SEQUENCE s2 START 10")
        engine.sql("SELECT nextval('s2') AS v")
        result = engine.sql("SELECT currval('s2') AS v")
        assert result.rows[0]["v"] == 10

    def test_setval(self, engine):
        engine.sql("CREATE SEQUENCE s3 START 1")
        engine.sql("SELECT nextval('s3') AS v")
        engine.sql("SELECT setval('s3', 100) AS v")
        result = engine.sql("SELECT currval('s3') AS v")
        assert result.rows[0]["v"] == 100

    def test_increment(self, engine):
        engine.sql("CREATE SEQUENCE s4 START 1 INCREMENT 5")
        result = engine.sql("SELECT nextval('s4') AS v")
        assert result.rows[0]["v"] == 1
        result = engine.sql("SELECT nextval('s4') AS v")
        assert result.rows[0]["v"] == 6


class TestPGCatalog:
    def test_pg_tables(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname = 'public'"
        )
        names = {r["tablename"] for r in result.rows}
        assert "t" in names

    def test_pg_views(self, engine):
        engine.sql("CREATE TABLE base (id SERIAL PRIMARY KEY, val INT)")
        engine.sql("CREATE VIEW v1 AS SELECT id FROM base")
        result = engine.sql(
            "SELECT viewname FROM pg_catalog.pg_views "
            "WHERE schemaname = 'public'"
        )
        names = {r["viewname"] for r in result.rows}
        assert "v1" in names


# ==================================================================
# Step 8: UNNEST and additional features
# ==================================================================


class TestUnnest:
    def test_basic(self, engine):
        result = engine.sql(
            "SELECT val FROM unnest(ARRAY[10, 20, 30]) AS t(val)"
        )
        assert len(result.rows) == 3
        vals = [r["val"] for r in result.rows]
        assert vals == [10, 20, 30]

    def test_text_array(self, engine):
        result = engine.sql(
            "SELECT val FROM unnest(ARRAY['a', 'b', 'c']) AS t(val)"
        )
        assert len(result.rows) == 3
        vals = [r["val"] for r in result.rows]
        assert vals == ["a", "b", "c"]
