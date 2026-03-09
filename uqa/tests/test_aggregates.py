#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for aggregate functions: COUNT DISTINCT, STRING_AGG, ARRAY_AGG,
BOOL_AND/OR, statistical aggregates, percentile, mode, and related features."""

from __future__ import annotations

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


@pytest.fixture
def engine_with_products(engine):
    engine.sql(
        "CREATE TABLE products ("
        "  id INTEGER PRIMARY KEY, category TEXT, name TEXT,"
        "  price INTEGER, active BOOLEAN"
        ")"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (1, 'fruit', 'Apple', 3, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (2, 'fruit', 'Banana', 2, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (3, 'fruit', 'Cherry', 5, false)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (4, 'veggie', 'Daikon', 4, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (5, 'veggie', 'Eggplant', 6, false)"
    )
    return engine


# ==================================================================
# COUNT(DISTINCT)
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


# ==================================================================
# STRING_AGG
# ==================================================================


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
# STRING_AGG DISTINCT
# ==================================================================


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


# ==================================================================
# ARRAY_AGG
# ==================================================================


class TestArrayAgg:
    def test_basic(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name) AS names FROM products"
        )
        names = result.rows[0]["names"]
        assert isinstance(names, list)
        assert set(names) == {"Apple", "Banana", "Cherry", "Daikon", "Eggplant"}

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, array_agg(name) AS names "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["names"] for r in result.rows}
        assert set(by_cat["fruit"]) == {"Apple", "Banana", "Cherry"}
        assert set(by_cat["veggie"]) == {"Daikon", "Eggplant"}

    def test_with_order_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name ORDER BY name) AS names FROM products"
        )
        assert result.rows[0]["names"] == [
            "Apple", "Banana", "Cherry", "Daikon", "Eggplant"
        ]

    def test_with_order_by_desc(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name ORDER BY name DESC) AS names FROM products"
        )
        assert result.rows[0]["names"] == [
            "Eggplant", "Daikon", "Cherry", "Banana", "Apple"
        ]


# ==================================================================
# BOOL_AND
# ==================================================================


class TestBoolAnd:
    def test_all_true(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, flag BOOLEAN)"
        )
        engine.sql("INSERT INTO t (id, flag) VALUES (1, true)")
        engine.sql("INSERT INTO t (id, flag) VALUES (2, true)")
        result = engine.sql("SELECT bool_and(flag) AS result FROM t")
        assert result.rows[0]["result"] is True

    def test_mixed(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT bool_and(active) AS result FROM products"
        )
        assert result.rows[0]["result"] is False

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, bool_and(active) AS all_active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["all_active"] for r in result.rows}
        assert by_cat["fruit"] is False
        assert by_cat["veggie"] is False


# ==================================================================
# BOOL_OR
# ==================================================================


class TestBoolOr:
    def test_all_false(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, flag BOOLEAN)"
        )
        engine.sql("INSERT INTO t (id, flag) VALUES (1, false)")
        engine.sql("INSERT INTO t (id, flag) VALUES (2, false)")
        result = engine.sql("SELECT bool_or(flag) AS result FROM t")
        assert result.rows[0]["result"] is False

    def test_mixed(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT bool_or(active) AS result FROM products"
        )
        assert result.rows[0]["result"] is True

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, bool_or(active) AS any_active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["any_active"] for r in result.rows}
        assert by_cat["fruit"] is True
        assert by_cat["veggie"] is True


# ==================================================================
# Aggregate FILTER
# ==================================================================


class TestAggregateFilter:
    def test_count_with_filter(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT COUNT(*) FILTER (WHERE active) AS active_count "
            "FROM products"
        )
        assert result.rows[0]["active_count"] == 3

    def test_sum_with_filter(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT SUM(price) FILTER (WHERE active) AS active_total "
            "FROM products"
        )
        # Apple=3, Banana=2, Daikon=4 -> 9
        assert result.rows[0]["active_total"] == 9

    def test_filter_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, "
            "  COUNT(*) AS total, "
            "  COUNT(*) FILTER (WHERE active) AS active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r for r in result.rows}
        assert by_cat["fruit"]["total"] == 3
        assert by_cat["fruit"]["active"] == 2
        assert by_cat["veggie"]["total"] == 2
        assert by_cat["veggie"]["active"] == 1

    def test_filter_with_comparison(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT COUNT(*) FILTER (WHERE price > 3) AS expensive "
            "FROM products"
        )
        # Daikon=4, Cherry=5, Eggplant=6 -> 3
        assert result.rows[0]["expensive"] == 3


# ==================================================================
# Aggregate ORDER BY
# ==================================================================


class TestAggregateOrderBy:
    def test_string_agg_ordered(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT string_agg(name, ', ' ORDER BY name) AS names "
            "FROM products"
        )
        assert result.rows[0]["names"] == (
            "Apple, Banana, Cherry, Daikon, Eggplant"
        )

    def test_string_agg_ordered_desc(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT string_agg(name, ', ' ORDER BY name DESC) AS names "
            "FROM products"
        )
        assert result.rows[0]["names"] == (
            "Eggplant, Daikon, Cherry, Banana, Apple"
        )

    def test_array_agg_ordered_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, "
            "  array_agg(name ORDER BY price DESC) AS by_price "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["by_price"] for r in result.rows}
        assert by_cat["fruit"] == ["Cherry", "Apple", "Banana"]
        assert by_cat["veggie"] == ["Eggplant", "Daikon"]


# ==================================================================
# GROUP BY enhanced (ordinal and alias)
# ==================================================================


class TestGroupByEnhanced:
    def test_group_by_ordinal(self, engine):
        engine.sql(
            "CREATE TABLE sales ("
            "  id INTEGER PRIMARY KEY, region TEXT, amount INTEGER"
            ")"
        )
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (1, 'East', 100)")
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (2, 'West', 200)")
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (3, 'East', 150)")
        result = engine.sql(
            "SELECT region, SUM(amount) AS total FROM sales GROUP BY 1"
        )
        assert len(result.rows) == 2
        totals = {r["region"]: r["total"] for r in result.rows}
        assert totals["East"] == 250
        assert totals["West"] == 200

    def test_group_by_alias(self, engine):
        engine.sql(
            "CREATE TABLE items ("
            "  id INTEGER PRIMARY KEY, category TEXT, price INTEGER"
            ")"
        )
        engine.sql("INSERT INTO items (id, category, price) VALUES (1, 'A', 10)")
        engine.sql("INSERT INTO items (id, category, price) VALUES (2, 'B', 20)")
        engine.sql("INSERT INTO items (id, category, price) VALUES (3, 'A', 30)")
        result = engine.sql(
            "SELECT category AS cat, COUNT(*) AS cnt "
            "FROM items GROUP BY cat"
        )
        assert len(result.rows) == 2
        counts = {r["cat"]: r["cnt"] for r in result.rows}
        assert counts["A"] == 2
        assert counts["B"] == 1


# ==================================================================
# Complex HAVING
# ==================================================================


class TestComplexHaving:
    def test_having_with_and(self, engine):
        engine.sql(
            "CREATE TABLE sales ("
            "  id INTEGER PRIMARY KEY, region TEXT, amount INTEGER"
            ")"
        )
        for i, (region, amount) in enumerate([
            ("East", 100), ("East", 200), ("East", 50),
            ("West", 300), ("West", 400),
            ("North", 10),
        ], 1):
            engine.sql(
                f"INSERT INTO sales (id, region, amount) "
                f"VALUES ({i}, '{region}', {amount})"
            )
        result = engine.sql(
            "SELECT region, COUNT(*) AS cnt, SUM(amount) AS total "
            "FROM sales GROUP BY region "
            "HAVING COUNT(*) > 2 AND SUM(amount) > 300"
        )
        # East: count=3>2, sum=350>300 -> pass
        # West: count=2, not >2 -> fail
        # North: count=1, not >2 -> fail
        assert len(result.rows) == 1
        assert result.rows[0]["region"] == "East"

    def test_having_aggregate_comparison(self, engine):
        engine.sql(
            "CREATE TABLE scores ("
            "  id INTEGER PRIMARY KEY, team TEXT, score INTEGER"
            ")"
        )
        engine.sql("INSERT INTO scores (id, team, score) VALUES (1, 'A', 90)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (2, 'A', 80)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (3, 'B', 50)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (4, 'B', 60)")
        # Teams where max > 2 * min
        result = engine.sql(
            "SELECT team, MAX(score) AS hi, MIN(score) AS lo "
            "FROM scores GROUP BY team "
            "HAVING MAX(score) > MIN(score) + 20"
        )
        # A: max=90, min=80, diff=10 -> no
        # B: max=60, min=50, diff=10 -> no
        assert len(result.rows) == 0

    def test_having_simple(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, cat TEXT, val INTEGER)"
        )
        engine.sql("INSERT INTO t (id, cat, val) VALUES (1, 'a', 10)")
        engine.sql("INSERT INTO t (id, cat, val) VALUES (2, 'a', 20)")
        engine.sql("INSERT INTO t (id, cat, val) VALUES (3, 'b', 30)")
        result = engine.sql(
            "SELECT cat, COUNT(*) AS cnt FROM t "
            "GROUP BY cat HAVING COUNT(*) > 1"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["cat"] == "a"


# ==================================================================
# NUMERIC(precision, scale)
# ==================================================================


class TestNumericPrecisionScale:
    def test_create_table_numeric(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, price NUMERIC(10, 2))"
        )
        result = engine.sql("SELECT * FROM t")
        assert "price" in result.columns

    def test_insert_rounds_to_scale(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, price NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, price) VALUES (1, 19.999)")
        result = engine.sql("SELECT price FROM t WHERE id = 1")
        assert result.rows[0]["price"] == 20.00

    def test_insert_preserves_scale(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, amount NUMERIC(8, 3))"
        )
        engine.sql("INSERT INTO t (id, amount) VALUES (1, 123.456)")
        result = engine.sql("SELECT amount FROM t WHERE id = 1")
        assert result.rows[0]["amount"] == 123.456

    def test_numeric_arithmetic(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, a NUMERIC(10, 2), b NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, a, b) VALUES (1, 10.50, 3.25)")
        result = engine.sql("SELECT a + b AS total FROM t WHERE id = 1")
        assert abs(result.rows[0]["total"] - 13.75) < 0.001

    def test_numeric_comparison(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 10.50)")
        engine.sql("INSERT INTO t (id, val) VALUES (2, 20.75)")
        engine.sql("INSERT INTO t (id, val) VALUES (3, 5.25)")
        result = engine.sql(
            "SELECT id FROM t WHERE val > 10.00 ORDER BY id"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == [1, 2]

    def test_numeric_no_scale_specified(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC(10))"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 42.9)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        # NUMERIC(10) with scale=0 rounds to integer
        assert result.rows[0]["val"] == 43.0

    def test_plain_numeric_no_precision(self, engine):
        # Plain NUMERIC without precision/scale works as float
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC)"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 3.14159)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert abs(result.rows[0]["val"] - 3.14159) < 0.001


# ==================================================================
# Statistical aggregates: STDDEV, VARIANCE
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


# ==================================================================
# PERCENTILE_CONT
# ==================================================================


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


# ==================================================================
# PERCENTILE_DISC
# ==================================================================


class TestPercentileDisc:
    def test_median(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY val) AS v "
            "FROM t"
        )
        assert result.rows[0]["v"] == 20


# ==================================================================
# MODE
# ==================================================================


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
