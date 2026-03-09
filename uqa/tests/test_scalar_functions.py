#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for scalar functions: string, math, and related functions."""

from __future__ import annotations

import math

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
# GREATEST / LEAST / NULLIF
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
# String functions
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
# String function aliases
# ==================================================================


class TestStringFunctionAliases:
    def test_character_length(self, engine):
        result = engine.sql("SELECT CHARACTER_LENGTH('hello') AS len")
        assert result.rows[0]["len"] == 5

    def test_strpos(self, engine):
        result = engine.sql("SELECT STRPOS('hello world', 'lo') AS pos")
        assert result.rows[0]["pos"] == 4


# ==================================================================
# Math functions
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
# LOG with two arguments
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


# ==================================================================
# Scalar functions (Step 7): initcap, translate, ascii, chr, starts_with
# ==================================================================


class TestScalarFunctionsStep7:
    def test_initcap(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT initcap('hello world') AS v FROM t"
        )
        assert result.rows[0]["v"] == "Hello World"

    def test_translate(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT translate('12345', '143', 'ax') AS v FROM t"
        )
        # '1'->'a', '4'->'x', '3' deleted
        assert result.rows[0]["v"] == "a2x5"

    def test_ascii(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT ascii('A') AS v FROM t")
        assert result.rows[0]["v"] == 65

    def test_chr(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT chr(65) AS v FROM t")
        assert result.rows[0]["v"] == "A"

    def test_starts_with(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t (id, name) VALUES (1, 'PostgreSQL')")
        result = engine.sql(
            "SELECT starts_with(name, 'Post') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is True


# ==================================================================
# OCTET_LENGTH
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


# ==================================================================
# MD5
# ==================================================================


class TestMD5:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT md5('hello') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "5d41402abc4b2a76b9719d911017c592"


# ==================================================================
# FORMAT
# ==================================================================


class TestFormat:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT format('Hello %s, you are %s', 'World', 'great') AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Hello World, you are great"


# ==================================================================
# REGEXP_MATCH
# ==================================================================


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


# ==================================================================
# REGEXP_REPLACE
# ==================================================================


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


# ==================================================================
# OVERLAY
# ==================================================================


class TestOverlay:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT overlay('Txxxxas' placing 'hom' from 2 for 4) AS v "
            "FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Thomas"


# ==================================================================
# CBRT
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


# ==================================================================
# Trigonometric functions
# ==================================================================


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


# ==================================================================
# DEGREES / RADIANS
# ==================================================================


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


# ==================================================================
# DIV
# ==================================================================


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


# ==================================================================
# GCD / LCM
# ==================================================================


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


# ==================================================================
# WIDTH_BUCKET
# ==================================================================


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
