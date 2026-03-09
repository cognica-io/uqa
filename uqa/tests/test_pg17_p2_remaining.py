#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for remaining PostgreSQL 17 P2 features.

Covers JSON key existence operators, MAKE_TIMESTAMP/MAKE_INTERVAL/TO_NUMBER,
OVERLAPS, pg_catalog.pg_indexes, FILTER (WHERE) on window aggregates,
standalone VALUES, and JSON table functions.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.engine import Engine


# ==================================================================
# 1. JSON key existence operators (?, ?|, ?&)
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
# 2. MAKE_TIMESTAMP, MAKE_INTERVAL, TO_NUMBER
# ==================================================================


class TestMakeTimestamp:
    """Test make_timestamp() scalar function."""

    def test_basic(self):
        e = Engine()
        r = e.sql("SELECT make_timestamp(2024, 3, 15, 10, 30, 0) AS ts")
        ts = r.rows[0]["ts"]
        assert "2024-03-15" in ts
        assert "10:30:00" in ts

    def test_with_fractional_seconds(self):
        e = Engine()
        r = e.sql("SELECT make_timestamp(2024, 1, 1, 0, 0, 30.5) AS ts")
        ts = r.rows[0]["ts"]
        assert "2024-01-01" in ts
        assert "00:00:30" in ts

    def test_midnight(self):
        e = Engine()
        r = e.sql("SELECT make_timestamp(2024, 12, 31, 0, 0, 0) AS ts")
        ts = r.rows[0]["ts"]
        assert "2024-12-31" in ts
        assert "00:00:00" in ts

    def test_end_of_day(self):
        e = Engine()
        r = e.sql("SELECT make_timestamp(2024, 6, 15, 23, 59, 59) AS ts")
        ts = r.rows[0]["ts"]
        assert "2024-06-15" in ts
        assert "23:59:59" in ts


class TestMakeInterval:
    """Test make_interval() scalar function."""

    def test_days_hours_minutes(self):
        e = Engine()
        # 1 day + 2 hours + 30 minutes = 26:30:00
        r = e.sql("SELECT make_interval(0, 0, 0, 1, 2, 30, 0) AS iv")
        iv = r.rows[0]["iv"]
        assert iv is not None
        assert "26:30:00" in iv

    def test_hours_minutes_only(self):
        e = Engine()
        r = e.sql("SELECT make_interval(0, 0, 0, 0, 1, 30, 0) AS iv")
        assert "01:30:00" in r.rows[0]["iv"]

    def test_zero_interval(self):
        e = Engine()
        r = e.sql("SELECT make_interval(0, 0, 0, 0, 0, 0, 0) AS iv")
        assert "00:00:00" in r.rows[0]["iv"]


class TestToNumber:
    """Test to_number() scalar function."""

    def test_with_currency_and_commas(self):
        e = Engine()
        r = e.sql("SELECT to_number('$1,234.56', '9999.99') AS n")
        assert abs(r.rows[0]["n"] - 1234.56) < 0.01

    def test_plain_integer(self):
        e = Engine()
        r = e.sql("SELECT to_number('42', '99') AS n")
        assert r.rows[0]["n"] == 42.0

    def test_negative_number(self):
        e = Engine()
        r = e.sql("SELECT to_number('-99.5', '999.9') AS n")
        assert abs(r.rows[0]["n"] - (-99.5)) < 0.01

    def test_with_spaces(self):
        e = Engine()
        r = e.sql("SELECT to_number('  100  ', '999') AS n")
        assert abs(r.rows[0]["n"] - 100.0) < 0.01


# ==================================================================
# 3. OVERLAPS operator
# ==================================================================


class TestOverlaps:
    """Test OVERLAPS operator for date/time range overlap detection.

    Uses the SQL operator form: (start1, end1) OVERLAPS (start2, end2).
    """

    def test_overlapping_ranges(self):
        e = Engine()
        r = e.sql(
            "SELECT "
            "('2024-01-01'::timestamp, '2024-06-01'::timestamp) OVERLAPS "
            "('2024-03-01'::timestamp, '2024-09-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is True

    def test_non_overlapping_ranges(self):
        e = Engine()
        r = e.sql(
            "SELECT "
            "('2024-01-01'::timestamp, '2024-03-01'::timestamp) OVERLAPS "
            "('2024-06-01'::timestamp, '2024-09-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is False

    def test_adjacent_ranges_do_not_overlap(self):
        e = Engine()
        # In PostgreSQL, adjacent ranges (end1 == start2) do NOT overlap
        r = e.sql(
            "SELECT "
            "('2024-01-01'::timestamp, '2024-03-01'::timestamp) OVERLAPS "
            "('2024-03-01'::timestamp, '2024-06-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is False

    def test_function_form(self):
        e = Engine()
        r = e.sql(
            "SELECT overlaps("
            "'2024-01-01'::timestamp, '2024-06-01'::timestamp, "
            "'2024-03-01'::timestamp, '2024-09-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is True

    def test_function_form_non_overlapping(self):
        e = Engine()
        r = e.sql(
            "SELECT overlaps("
            "'2024-01-01'::timestamp, '2024-02-01'::timestamp, "
            "'2024-06-01'::timestamp, '2024-07-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is False

    def test_one_range_within_another(self):
        e = Engine()
        r = e.sql(
            "SELECT "
            "('2024-01-01'::timestamp, '2024-12-31'::timestamp) OVERLAPS "
            "('2024-03-01'::timestamp, '2024-06-01'::timestamp) AS ov"
        )
        assert r.rows[0]["ov"] is True


# ==================================================================
# 4. pg_catalog.pg_indexes
# ==================================================================


class TestPGIndexes:
    """Test pg_catalog.pg_indexes virtual table.

    Requires a persistent engine (db_path) since CREATE INDEX depends
    on the IndexManager which requires SQLite storage.
    """

    def test_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE items (id INT PRIMARY KEY, name TEXT)")
            e.sql("CREATE INDEX idx_name ON items (name)")
            r = e.sql("SELECT * FROM pg_catalog.pg_indexes")
            assert len(r.rows) >= 1
            idx_row = [
                row for row in r.rows if row["indexname"] == "idx_name"
            ]
            assert len(idx_row) == 1
            assert idx_row[0]["tablename"] == "items"
            assert idx_row[0]["schemaname"] == "public"

    def test_index_definition(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE products (id INT PRIMARY KEY, price INT)")
            e.sql("CREATE INDEX idx_price ON products (price)")
            r = e.sql("SELECT * FROM pg_catalog.pg_indexes")
            idx_row = [
                row for row in r.rows if row["indexname"] == "idx_price"
            ]
            assert len(idx_row) == 1
            assert "price" in idx_row[0]["indexdef"]

    def test_no_indexes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE items (id INT PRIMARY KEY)")
            r = e.sql("SELECT * FROM pg_catalog.pg_indexes")
            assert len(r.rows) == 0

    def test_multiple_indexes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql(
                "CREATE TABLE employees "
                "(id INT PRIMARY KEY, name TEXT, dept TEXT)"
            )
            e.sql("CREATE INDEX idx_emp_name ON employees (name)")
            e.sql("CREATE INDEX idx_emp_dept ON employees (dept)")
            r = e.sql("SELECT * FROM pg_catalog.pg_indexes")
            names = {row["indexname"] for row in r.rows}
            assert "idx_emp_name" in names
            assert "idx_emp_dept" in names

    def test_filter_by_tablename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE t1 (id INT PRIMARY KEY, a TEXT)")
            e.sql("CREATE TABLE t2 (id INT PRIMARY KEY, b TEXT)")
            e.sql("CREATE INDEX idx_a ON t1 (a)")
            e.sql("CREATE INDEX idx_b ON t2 (b)")
            r = e.sql(
                "SELECT indexname FROM pg_catalog.pg_indexes "
                "WHERE tablename = 't1'"
            )
            assert len(r.rows) == 1
            assert r.rows[0]["indexname"] == "idx_a"


# ==================================================================
# 5. FILTER (WHERE ...) on window aggregate
# ==================================================================


class TestWindowFilter:
    """Test FILTER (WHERE ...) clause on window aggregate functions.

    FILTER restricts which rows are included in the aggregate computation
    while still producing a result for every row in the partition.
    """

    @pytest.fixture()
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE sales (id INT PRIMARY KEY, dept TEXT, amount INT)")
        e.sql("INSERT INTO sales VALUES (1, 'A', 100)")
        e.sql("INSERT INTO sales VALUES (2, 'A', 200)")
        e.sql("INSERT INTO sales VALUES (3, 'B', 150)")
        e.sql("INSERT INTO sales VALUES (4, 'B', 50)")
        yield e

    def test_sum_filter(self, engine):
        r = engine.sql(
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

    def test_count_filter(self, engine):
        r = engine.sql(
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

    def test_avg_filter(self, engine):
        r = engine.sql(
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

    def test_filter_excludes_all(self, engine):
        r = engine.sql(
            "SELECT dept, amount, "
            "SUM(amount) FILTER (WHERE amount > 1000) "
            "OVER (PARTITION BY dept) AS s "
            "FROM sales ORDER BY id"
        )
        # No rows match amount > 1000 in any partition
        for row in r.rows:
            assert row["s"] is None or row["s"] == 0


# ==================================================================
# 6. VALUES as standalone query
# ==================================================================


class TestStandaloneValues:
    """Test standalone VALUES queries (without INSERT)."""

    def test_basic(self):
        e = Engine()
        r = e.sql("VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        assert len(r.rows) == 3
        assert r.rows[0]["column1"] == 1
        assert r.rows[0]["column2"] == "a"
        assert r.rows[2]["column1"] == 3
        assert r.rows[2]["column2"] == "c"

    def test_single_column(self):
        e = Engine()
        r = e.sql("VALUES (10), (20), (30)")
        assert len(r.rows) == 3
        assert r.rows[0]["column1"] == 10
        assert r.rows[1]["column1"] == 20
        assert r.rows[2]["column1"] == 30

    def test_with_order_by(self):
        e = Engine()
        r = e.sql("VALUES (3, 'c'), (1, 'a'), (2, 'b') ORDER BY 1")
        assert r.rows[0]["column1"] == 1
        assert r.rows[1]["column1"] == 2
        assert r.rows[2]["column1"] == 3

    def test_with_limit(self):
        e = Engine()
        r = e.sql("VALUES (1), (2), (3), (4), (5) LIMIT 3")
        assert len(r.rows) == 3

    def test_mixed_types(self):
        e = Engine()
        r = e.sql("VALUES (1, 'hello', 3.14), (2, 'world', 2.72)")
        assert len(r.rows) == 2
        assert r.rows[0]["column1"] == 1
        assert r.rows[0]["column2"] == "hello"
        assert abs(r.rows[0]["column3"] - 3.14) < 0.001

    def test_single_row(self):
        e = Engine()
        r = e.sql("VALUES (42, 'only')")
        assert len(r.rows) == 1
        assert r.rows[0]["column1"] == 42
        assert r.rows[0]["column2"] == "only"


# ==================================================================
# 7. JSON_EACH / JSON_EACH_TEXT / JSON_ARRAY_ELEMENTS as table
#    functions
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
