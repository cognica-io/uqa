#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for ARRAY, UUID, and BYTEA types."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_table(engine):
    engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER, name TEXT)")
    engine.sql("INSERT INTO t (id, val, name) VALUES (1, 10, 'alpha')")
    engine.sql("INSERT INTO t (id, val, name) VALUES (2, 20, 'bravo')")
    engine.sql("INSERT INTO t (id, val, name) VALUES (3, 30, 'charlie')")
    return engine


# ==================================================================
# ARRAY literals
# ==================================================================


class TestArrayLiteral:
    def test_select_array(self, engine_with_table):
        result = engine_with_table.sql("SELECT ARRAY[1, 2, 3] AS v FROM t WHERE id = 1")
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


# ==================================================================
# ARRAY columns
# ==================================================================


class TestArrayColumn:
    def test_create_and_insert(self, engine):
        engine.sql("CREATE TABLE arr_test (id SERIAL PRIMARY KEY, tags TEXT[])")
        engine.sql("INSERT INTO arr_test (tags) VALUES (ARRAY['python', 'sql'])")
        result = engine.sql("SELECT tags FROM arr_test WHERE id = 1")
        assert result.rows[0]["tags"] == ["python", "sql"]

    def test_integer_array(self, engine):
        engine.sql("CREATE TABLE int_arr (id SERIAL PRIMARY KEY, nums INTEGER[])")
        engine.sql("INSERT INTO int_arr (nums) VALUES (ARRAY[10, 20, 30])")
        result = engine.sql("SELECT nums FROM int_arr WHERE id = 1")
        assert result.rows[0]["nums"] == [10, 20, 30]


# ==================================================================
# ARRAY functions
# ==================================================================


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
            "SELECT array_cat(ARRAY[1, 2], ARRAY[3, 4]) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 2, 3, 4]

    def test_array_append(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_append(ARRAY[1, 2], 3) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 2, 3]

    def test_array_remove(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT array_remove(ARRAY[1, 2, 3, 2], 2) AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == [1, 3]


# ==================================================================
# UUID type
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
        engine.sql("CREATE TABLE uuid_test (  id SERIAL PRIMARY KEY,  uid UUID)")
        engine.sql(
            "INSERT INTO uuid_test (uid) "
            "VALUES ('550e8400-e29b-41d4-a716-446655440000')"
        )
        result = engine.sql("SELECT uid FROM uuid_test WHERE id = 1")
        assert result.rows[0]["uid"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_uuid_uniqueness(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT gen_random_uuid() AS a, gen_random_uuid() AS b FROM t WHERE id = 1"
        )
        assert result.rows[0]["a"] != result.rows[0]["b"]


# ==================================================================
# BYTEA type
# ==================================================================


class TestBytea:
    def test_bytea_column(self, engine):
        engine.sql("CREATE TABLE bin_test (id SERIAL PRIMARY KEY, data BYTEA)")
        engine.sql("INSERT INTO bin_test (data) VALUES ('hello')")
        result = engine.sql("SELECT data FROM bin_test WHERE id = 1")
        assert result.rows[0]["data"] is not None

    def test_cast_to_bytea(self, engine_with_table):
        result = engine_with_table.sql("SELECT 'hello'::bytea AS v FROM t WHERE id = 1")
        assert result.rows[0]["v"] == b"hello"
