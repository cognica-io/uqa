#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for JSON/JSONB types, operators, and functions."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_json(engine):
    engine.sql(
        "CREATE TABLE docs ("
        "  id INTEGER PRIMARY KEY, data JSON, label TEXT"
        ")"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(1, '{\"name\": \"Alice\", \"age\": 30, \"tags\": [\"a\", \"b\"]}', 'first')"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(2, '{\"name\": \"Bob\", \"age\": 25, \"tags\": [\"c\"]}', 'second')"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(3, '{\"name\": \"Carol\", \"nested\": {\"x\": 10}}', 'third')"
    )
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
# JSON/JSONB type
# ==================================================================


class TestJSONType:
    def test_create_table_with_json(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, data JSON)"
        )
        result = engine.sql("SELECT * FROM t")
        assert "data" in result.columns

    def test_create_table_with_jsonb(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, data JSONB)"
        )
        result = engine.sql("SELECT * FROM t")
        assert "data" in result.columns

    def test_insert_json_string(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data FROM docs WHERE id = 1"
        )
        data = result.rows[0]["data"]
        assert isinstance(data, dict)
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_insert_json_array(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, items JSON)"
        )
        engine.sql(
            "INSERT INTO t (id, items) VALUES (1, '[1, 2, 3]')"
        )
        result = engine.sql("SELECT items FROM t WHERE id = 1")
        assert result.rows[0]["items"] == [1, 2, 3]


# ==================================================================
# JSON operators
# ==================================================================


class TestJSONOperators:
    def test_arrow_text_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'name' AS name FROM docs WHERE id = 1"
        )
        assert result.rows[0]["name"] == "Alice"

    def test_double_arrow_text_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->>'name' AS name FROM docs WHERE id = 1"
        )
        # ->> returns text
        assert result.rows[0]["name"] == "Alice"
        assert isinstance(result.rows[0]["name"], str)

    def test_arrow_integer_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'tags'->0 AS first_tag FROM docs WHERE id = 1"
        )
        assert result.rows[0]["first_tag"] == "a"

    def test_arrow_nested_object(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'nested'->'x' AS x FROM docs WHERE id = 3"
        )
        assert result.rows[0]["x"] == 10

    def test_double_arrow_returns_text_for_nested(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->>'tags' AS tags FROM docs WHERE id = 1"
        )
        # ->> on array returns JSON string representation
        assert isinstance(result.rows[0]["tags"], str)
        assert '"a"' in result.rows[0]["tags"]

    def test_arrow_missing_key_returns_null(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'nonexistent' AS v FROM docs WHERE id = 1"
        )
        assert result.rows[0]["v"] is None

    def test_json_in_where(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT id FROM docs WHERE data->>'name' = 'Bob'"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 2


# ==================================================================
# JSON functions
# ==================================================================


class TestJSONFunctions:
    def test_json_build_object(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT json_build_object('a', 1, 'b', 2) AS obj FROM t"
        )
        assert result.rows[0]["obj"] == {"a": 1, "b": 2}

    def test_json_build_array(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT json_build_array(1, 2, 3) AS arr FROM t"
        )
        assert result.rows[0]["arr"] == [1, 2, 3]

    def test_json_build_array_mixed_types(self, engine):
        result = engine.sql(
            "SELECT json_build_array(1, 2, 3, 'four') AS arr"
        )
        assert result.rows[0]["arr"] == ["1", "2", "3", "four"]

    def test_json_build_array_mixed_int_float_str_bool(self, engine):
        result = engine.sql(
            "SELECT json_build_array(1, 2.5, 'hello', true) AS arr"
        )
        arr = result.rows[0]["arr"]
        assert len(arr) == 4
        assert all(isinstance(x, str) for x in arr)

    def test_json_build_array_empty(self, engine):
        result = engine.sql("SELECT json_build_array() AS arr")
        assert result.rows[0]["arr"] == []

    def test_json_typeof_object(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_typeof(data) AS t FROM docs WHERE id = 1"
        )
        assert result.rows[0]["t"] == "object"

    def test_json_typeof_array(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_typeof(data->'tags') AS t FROM docs WHERE id = 1"
        )
        assert result.rows[0]["t"] == "array"

    def test_json_array_length(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_array_length(data->'tags') AS n FROM docs WHERE id = 1"
        )
        assert result.rows[0]["n"] == 2

    def test_json_array_length_single(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_array_length(data->'tags') AS n FROM docs WHERE id = 2"
        )
        assert result.rows[0]["n"] == 1

    def test_json_extract_path(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_extract_path(data, 'nested', 'x') AS v "
            "FROM docs WHERE id = 3"
        )
        assert result.rows[0]["v"] == 10

    def test_json_extract_path_text(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_extract_path_text(data, 'name') AS v "
            "FROM docs WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Alice"
        assert isinstance(result.rows[0]["v"], str)

    def test_cast_to_json(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, raw TEXT)")
        engine.sql(
            "INSERT INTO t (id, raw) VALUES (1, '{\"x\": 42}')"
        )
        result = engine.sql(
            "SELECT CAST(raw AS json)->'x' AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 42


# ==================================================================
# JSON object aggregation
# ==================================================================


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
# JSON path operators
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


# ==================================================================
# JSON containment
# ==================================================================


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


# ==================================================================
# JSONB set
# ==================================================================


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


# ==================================================================
# JSON object keys
# ==================================================================


class TestJSONObjectKeys:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT json_object_keys('{\"a\": 1, \"b\": 2}'::json) AS v "
            "FROM t WHERE id = 1"
        )
        v = result.rows[0]["v"]
        assert set(v) == {"a", "b"}


# ==================================================================
# JSON key existence
# ==================================================================


class TestJSONKeyExistence:
    """Test JSONB key existence operators via SELECT expressions.

    The ?, ?|, and ?& operators check whether a JSONB object contains
    specified keys.  Tests use JSONB literals in SELECT to exercise
    the ExprEvaluator path directly.
    """

    @pytest.fixture()
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INT PRIMARY KEY)")
        e.sql("INSERT INTO t VALUES (1)")
        yield e

    def test_has_key_present(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1, \"b\": 2, \"c\": 3}'::jsonb ? 'a' AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is True

    def test_has_key_missing(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1, \"b\": 2}'::jsonb ? 'z' AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is False

    def test_has_any_key_match(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1, \"b\": 2, \"c\": 3}'::jsonb "
            "?| ARRAY['a', 'z'] AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is True

    def test_has_any_key_no_match(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1}'::jsonb ?| ARRAY['x', 'y'] AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is False

    def test_has_all_keys_present(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1, \"b\": 2, \"c\": 3}'::jsonb "
            "?& ARRAY['a', 'b'] AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is True

    def test_has_all_keys_missing_one(self, engine):
        r = engine.sql(
            "SELECT '{\"a\": 1, \"b\": 2}'::jsonb "
            "?& ARRAY['a', 'z'] AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is False

    def test_has_key_on_empty_object(self, engine):
        r = engine.sql(
            "SELECT '{}'::jsonb ? 'a' AS v FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is False

    def test_has_all_keys_on_single_key(self, engine):
        r = engine.sql(
            "SELECT '{\"x\": 10}'::jsonb ?& ARRAY['x'] AS v "
            "FROM t WHERE id = 1"
        )
        assert r.rows[0]["v"] is True


# ==================================================================
# JSON each
# ==================================================================


class TestJSONEach:
    """Test json_each() and json_each_text() table functions."""

    def test_json_each(self):
        e = Engine()
        r = e.sql("""SELECT * FROM json_each('{"a": 1, "b": 2}')""")
        assert len(r.rows) == 2
        keys = {row["key"] for row in r.rows}
        assert keys == {"a", "b"}

    def test_json_each_key_value_pairs(self):
        e = Engine()
        r = e.sql("""SELECT key, value FROM json_each('{"x": 10, "y": 20}')""")
        assert len(r.rows) == 2
        kv = {row["key"]: row["value"] for row in r.rows}
        assert kv["x"] == "10"
        assert kv["y"] == "20"

    def test_json_each_text(self):
        e = Engine()
        r = e.sql(
            """SELECT * FROM json_each_text('{"name": "Alice", "age": "30"}')"""
        )
        assert len(r.rows) == 2
        for row in r.rows:
            assert isinstance(row["value"], str)

    def test_json_each_text_values(self):
        e = Engine()
        r = e.sql(
            """SELECT key, value FROM json_each_text('{"k1": "v1", "k2": "v2"}')"""
        )
        kv = {row["key"]: row["value"] for row in r.rows}
        assert kv["k1"] == "v1"
        assert kv["k2"] == "v2"

    def test_jsonb_each(self):
        e = Engine()
        r = e.sql("""SELECT * FROM jsonb_each('{"p": 100}')""")
        assert len(r.rows) == 1
        assert r.rows[0]["key"] == "p"


# ==================================================================
# JSON array elements
# ==================================================================


class TestJSONArrayElements:
    """Test json_array_elements() and json_array_elements_text() table functions."""

    def test_basic(self):
        e = Engine()
        r = e.sql("""SELECT * FROM json_array_elements('[1, 2, 3]')""")
        assert len(r.rows) == 3

    def test_values(self):
        e = Engine()
        r = e.sql("""SELECT value FROM json_array_elements('[10, 20, 30]')""")
        values = [row["value"] for row in r.rows]
        assert "10" in values
        assert "20" in values
        assert "30" in values

    def test_text_variant(self):
        e = Engine()
        r = e.sql(
            """SELECT * FROM json_array_elements_text('["a", "b", "c"]')"""
        )
        assert len(r.rows) == 3
        values = [row["value"] for row in r.rows]
        assert "a" in values
        assert "b" in values
        assert "c" in values

    def test_jsonb_array_elements(self):
        e = Engine()
        r = e.sql("""SELECT * FROM jsonb_array_elements('[4, 5]')""")
        assert len(r.rows) == 2

    def test_single_element_array(self):
        e = Engine()
        r = e.sql("""SELECT * FROM json_array_elements('[42]')""")
        assert len(r.rows) == 1
        assert r.rows[0]["value"] == "42"


# ==================================================================
# JSON array elements table function
# ==================================================================


class TestJSONArrayElementsTableFunction:
    """Test JSON table functions."""

    def test_array_elements_from_literal(self):
        e = Engine()
        r = e.sql(
            "SELECT value FROM "
            "json_array_elements('[\"python\", \"sql\", \"rust\"]')"
        )
        assert len(r.rows) == 3
        values = [row["value"] for row in r.rows]
        assert "python" in values
        assert "sql" in values
        assert "rust" in values

    def test_array_elements_integers(self):
        e = Engine()
        r = e.sql(
            "SELECT value FROM json_array_elements('[1, 2, 3]')"
        )
        assert len(r.rows) == 3
