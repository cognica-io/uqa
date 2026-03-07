#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the SQL expression evaluator and its compiler integration."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    e = Engine()
    e.sql(
        "CREATE TABLE products ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "price REAL, "
        "quantity INTEGER, "
        "category TEXT"
        ")"
    )
    e.sql(
        "INSERT INTO products (id, name, price, quantity, category) VALUES "
        "(1, 'Widget', 10.50, 100, 'tools'), "
        "(2, 'Gadget', 25.00, 50, 'electronics'), "
        "(3, 'Doohickey', 5.75, 200, NULL)"
    )
    return e


# ==================================================================
# IS NULL / IS NOT NULL
# ==================================================================


class TestNullTests:
    def test_is_null(self, engine):
        r = engine.sql("SELECT id, name FROM products WHERE category IS NULL")
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Doohickey"

    def test_is_not_null(self, engine):
        r = engine.sql(
            "SELECT id, name FROM products WHERE category IS NOT NULL"
        )
        assert len(r.rows) == 2
        names = {row["name"] for row in r.rows}
        assert names == {"Widget", "Gadget"}

    def test_is_null_with_and(self, engine):
        r = engine.sql(
            "SELECT name FROM products "
            "WHERE category IS NOT NULL AND price > 15"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Gadget"

    def test_is_null_on_non_null_column(self, engine):
        r = engine.sql("SELECT id FROM products WHERE name IS NULL")
        assert len(r.rows) == 0

    def test_is_not_null_all_rows(self, engine):
        r = engine.sql("SELECT id FROM products WHERE price IS NOT NULL")
        assert len(r.rows) == 3


# ==================================================================
# Arithmetic expressions in SELECT
# ==================================================================


class TestArithmetic:
    def test_multiply(self, engine):
        r = engine.sql(
            "SELECT name, price * 2 AS double_price FROM products"
        )
        assert len(r.rows) == 3
        assert r.rows[0]["double_price"] == 21.0
        assert r.columns == ["name", "double_price"]

    def test_add(self, engine):
        r = engine.sql(
            "SELECT name, price + 1 AS incremented FROM products"
        )
        assert r.rows[0]["incremented"] == 11.5

    def test_subtract(self, engine):
        r = engine.sql(
            "SELECT name, price - 5 AS discounted FROM products"
        )
        assert r.rows[0]["discounted"] == 5.5

    def test_divide(self, engine):
        r = engine.sql(
            "SELECT name, price / quantity AS unit_cost FROM products"
        )
        # 10.50 / 100 = 0.105
        assert abs(r.rows[0]["unit_cost"] - 0.105) < 0.001

    def test_modulo(self, engine):
        r = engine.sql(
            "SELECT id, quantity % 60 AS remainder FROM products"
        )
        assert r.rows[0]["remainder"] == 40  # 100 % 60
        assert r.rows[1]["remainder"] == 50  # 50 % 60

    def test_integer_division(self, engine):
        r = engine.sql(
            "SELECT id, quantity / 3 AS thirds FROM products"
        )
        assert r.rows[0]["thirds"] == 33  # 100 // 3

    def test_arithmetic_with_null(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity) "
            "VALUES (4, 'NullItem', NULL, 10)"
        )
        r = engine.sql(
            "SELECT name, price * 2 AS dp FROM products WHERE id = 4"
        )
        assert r.rows[0]["dp"] is None

    def test_compound_expression(self, engine):
        r = engine.sql(
            "SELECT name, (price * quantity) + 10 AS total FROM products"
        )
        # Widget: 10.5 * 100 + 10 = 1060.0
        assert abs(r.rows[0]["total"] - 1060.0) < 0.01

    def test_division_by_zero(self, engine):
        r = engine.sql(
            "SELECT name, price / 0 AS bad FROM products LIMIT 1"
        )
        assert r.rows[0]["bad"] is None


# ==================================================================
# String concatenation
# ==================================================================


class TestStringConcat:
    def test_basic_concat(self, engine):
        r = engine.sql(
            "SELECT name || '!' AS excited FROM products"
        )
        assert r.rows[0]["excited"] == "Widget!"

    def test_multi_concat(self, engine):
        r = engine.sql(
            "SELECT name || ' ($' || CAST(price AS TEXT) || ')' "
            "AS label FROM products"
        )
        assert r.rows[0]["label"] == "Widget ($10.5)"

    def test_concat_with_null(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity, category) "
            "VALUES (4, 'NullCat', 1.0, 1, NULL)"
        )
        r = engine.sql(
            "SELECT name || category AS result FROM products WHERE id = 4"
        )
        assert r.rows[0]["result"] is None


# ==================================================================
# CASE / WHEN
# ==================================================================


class TestCase:
    def test_simple_case(self, engine):
        r = engine.sql(
            "SELECT name, "
            "CASE WHEN price > 20 THEN 'expensive' "
            "ELSE 'affordable' END AS tier "
            "FROM products"
        )
        assert r.rows[0]["tier"] == "affordable"  # Widget 10.50
        assert r.rows[1]["tier"] == "expensive"  # Gadget 25.00

    def test_multi_when(self, engine):
        r = engine.sql(
            "SELECT name, "
            "CASE WHEN price > 20 THEN 'high' "
            "WHEN price > 8 THEN 'medium' "
            "ELSE 'low' END AS tier "
            "FROM products"
        )
        assert r.rows[0]["tier"] == "medium"  # Widget 10.50
        assert r.rows[1]["tier"] == "high"  # Gadget 25.00
        assert r.rows[2]["tier"] == "low"  # Doohickey 5.75

    def test_case_no_else(self, engine):
        r = engine.sql(
            "SELECT name, "
            "CASE WHEN price > 20 THEN 'expensive' END AS tier "
            "FROM products"
        )
        assert r.rows[0]["tier"] is None  # Widget
        assert r.rows[1]["tier"] == "expensive"  # Gadget

    def test_case_with_null(self, engine):
        r = engine.sql(
            "SELECT name, "
            "CASE WHEN category IS NULL THEN 'uncategorized' "
            "ELSE category END AS cat "
            "FROM products"
        )
        assert r.rows[2]["cat"] == "uncategorized"


# ==================================================================
# CAST
# ==================================================================


class TestCast:
    def test_cast_int_to_text(self, engine):
        r = engine.sql(
            "SELECT CAST(quantity AS TEXT) AS qty_text FROM products"
        )
        assert r.rows[0]["qty_text"] == "100"

    def test_cast_text_to_int(self, engine):
        engine.sql(
            "CREATE TABLE nums (id INTEGER, val TEXT)"
        )
        engine.sql("INSERT INTO nums (id, val) VALUES (1, '42')")
        r = engine.sql("SELECT CAST(val AS INTEGER) AS num FROM nums")
        assert r.rows[0]["num"] == 42

    def test_cast_float_to_int(self, engine):
        r = engine.sql(
            "SELECT CAST(price AS INTEGER) AS price_int FROM products"
        )
        assert r.rows[0]["price_int"] == 10  # 10.50 -> 10

    def test_cast_null(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity) "
            "VALUES (4, 'NullItem', NULL, 1)"
        )
        r = engine.sql(
            "SELECT CAST(price AS TEXT) AS p FROM products WHERE id = 4"
        )
        assert r.rows[0]["p"] is None


# ==================================================================
# COALESCE
# ==================================================================


class TestCoalesce:
    def test_basic_coalesce(self, engine):
        r = engine.sql(
            "SELECT id, COALESCE(category, 'none') AS cat FROM products"
        )
        assert r.rows[0]["cat"] == "tools"
        assert r.rows[2]["cat"] == "none"

    def test_coalesce_first_non_null(self, engine):
        r = engine.sql(
            "SELECT COALESCE(NULL, NULL, 'fallback') AS val FROM products "
            "LIMIT 1"
        )
        assert r.rows[0]["val"] == "fallback"

    def test_coalesce_all_non_null(self, engine):
        r = engine.sql(
            "SELECT COALESCE(name, 'default') AS val FROM products LIMIT 1"
        )
        assert r.rows[0]["val"] == "Widget"


# ==================================================================
# String functions
# ==================================================================


class TestStringFunctions:
    def test_upper(self, engine):
        r = engine.sql("SELECT UPPER(name) AS up FROM products")
        assert r.rows[0]["up"] == "WIDGET"

    def test_lower(self, engine):
        r = engine.sql("SELECT LOWER(name) AS low FROM products")
        assert r.rows[0]["low"] == "widget"

    def test_length(self, engine):
        r = engine.sql("SELECT LENGTH(name) AS len FROM products")
        assert r.rows[0]["len"] == 6  # Widget

    def test_substring(self, engine):
        r = engine.sql(
            "SELECT SUBSTRING(name, 1, 3) AS prefix FROM products"
        )
        assert r.rows[0]["prefix"] == "Wid"

    def test_replace(self, engine):
        r = engine.sql(
            "SELECT REPLACE(name, 'dget', 'DGET') AS replaced FROM products"
        )
        assert r.rows[0]["replaced"] == "WiDGET"
        assert r.rows[1]["replaced"] == "GaDGET"

    def test_trim(self, engine):
        engine.sql("CREATE TABLE ws (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO ws (id, val) VALUES (1, '  hello  ')")
        r = engine.sql("SELECT TRIM(val) AS trimmed FROM ws")
        assert r.rows[0]["trimmed"] == "hello"

    def test_concat_function(self, engine):
        r = engine.sql(
            "SELECT CONCAT(name, ' - ', category) AS label FROM products"
        )
        assert r.rows[0]["label"] == "Widget - tools"
        # NULL category becomes empty string in concat()
        assert r.rows[2]["label"] == "Doohickey - "

    def test_left(self, engine):
        r = engine.sql("SELECT LEFT(name, 3) AS prefix FROM products")
        assert r.rows[0]["prefix"] == "Wid"

    def test_right(self, engine):
        r = engine.sql("SELECT RIGHT(name, 3) AS suffix FROM products")
        assert r.rows[0]["suffix"] == "get"

    def test_string_function_on_null(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity, category) "
            "VALUES (4, 'X', 1.0, 1, NULL)"
        )
        r = engine.sql(
            "SELECT UPPER(category) AS up FROM products WHERE id = 4"
        )
        assert r.rows[0]["up"] is None


# ==================================================================
# Math functions
# ==================================================================


class TestMathFunctions:
    def test_abs(self, engine):
        r = engine.sql(
            "SELECT ABS(price - 10) AS diff FROM products"
        )
        assert abs(r.rows[0]["diff"] - 0.5) < 0.01

    def test_round(self, engine):
        r = engine.sql(
            "SELECT ROUND(price, 1) AS rounded FROM products"
        )
        assert r.rows[0]["rounded"] == 10.5

    def test_round_no_decimals(self, engine):
        r = engine.sql("SELECT ROUND(price) AS rounded FROM products")
        # round(10.5, 0) -> 10 (banker's rounding)
        assert r.rows[0]["rounded"] in (10, 11)

    def test_ceil(self, engine):
        r = engine.sql("SELECT CEIL(price) AS c FROM products")
        assert r.rows[0]["c"] == 11  # ceil(10.5)

    def test_floor(self, engine):
        r = engine.sql("SELECT FLOOR(price) AS f FROM products")
        assert r.rows[0]["f"] == 10  # floor(10.5)


# ==================================================================
# Expression-based WHERE clause
# ==================================================================


class TestExpressionWhere:
    def test_arithmetic_comparison(self, engine):
        r = engine.sql(
            "SELECT name FROM products WHERE price * quantity > 1100"
        )
        # Gadget: 25 * 50 = 1250, Doohickey: 5.75 * 200 = 1150
        assert len(r.rows) == 2
        names = {row["name"] for row in r.rows}
        assert names == {"Gadget", "Doohickey"}

    def test_expression_left_side(self, engine):
        r = engine.sql(
            "SELECT name FROM products WHERE price * 2 > 15"
        )
        names = {row["name"] for row in r.rows}
        assert names == {"Widget", "Gadget"}

    def test_combined_expression_and_column(self, engine):
        r = engine.sql(
            "SELECT name FROM products "
            "WHERE quantity >= 100 AND price * 2 > 15"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Widget"

    def test_expression_no_match(self, engine):
        r = engine.sql(
            "SELECT name FROM products WHERE price * quantity > 99999"
        )
        assert len(r.rows) == 0


# ==================================================================
# Mixed: computed expressions with simple columns
# ==================================================================


class TestMixedProjection:
    def test_simple_and_computed(self, engine):
        r = engine.sql(
            "SELECT id, name, price * quantity AS total FROM products"
        )
        assert r.columns == ["id", "name", "total"]
        assert r.rows[0]["id"] == 1
        assert r.rows[0]["name"] == "Widget"
        assert abs(r.rows[0]["total"] - 1050.0) < 0.01

    def test_all_computed(self, engine):
        r = engine.sql(
            "SELECT price * 2 AS dp, quantity + 10 AS q10 FROM products"
        )
        assert r.columns == ["dp", "q10"]
        assert r.rows[0]["dp"] == 21.0
        assert r.rows[0]["q10"] == 110

    def test_computed_with_order_by(self, engine):
        r = engine.sql(
            "SELECT name, price * quantity AS total "
            "FROM products ORDER BY total DESC"
        )
        # Gadget: 1250, Doohickey: 1150, Widget: 1050
        assert r.rows[0]["name"] == "Gadget"
        assert r.rows[2]["name"] == "Widget"

    def test_computed_with_limit(self, engine):
        r = engine.sql(
            "SELECT name, price * 2 AS dp FROM products LIMIT 2"
        )
        assert len(r.rows) == 2


# ==================================================================
# ExprEvaluator unit tests (direct)
# ==================================================================


class TestExprEvaluatorDirect:
    def test_column_ref(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT x FROM t")
        node = stmts[0].stmt.targetList[0].val
        assert ev.evaluate(node, {"x": 42}) == 42

    def test_const_integer(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT 42 FROM t")
        node = stmts[0].stmt.targetList[0].val
        assert ev.evaluate(node, {}) == 42

    def test_const_string(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT 'hello' FROM t")
        node = stmts[0].stmt.targetList[0].val
        assert ev.evaluate(node, {}) == "hello"

    def test_const_float(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT 3.14 FROM t")
        node = stmts[0].stmt.targetList[0].val
        assert ev.evaluate(node, {}) == 3.14

    def test_bool_and(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE x > 5 AND y < 10")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 10, "y": 3}) is True
        assert ev.evaluate(node, {"x": 10, "y": 20}) is False

    def test_bool_or(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE x > 100 OR y < 10")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 1, "y": 3}) is True
        assert ev.evaluate(node, {"x": 1, "y": 20}) is False

    def test_bool_not(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE NOT x > 5")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 3}) is True
        assert ev.evaluate(node, {"x": 10}) is False

    def test_in_expr(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE x IN (1, 2, 3)")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 2}) is True
        assert ev.evaluate(node, {"x": 5}) is False

    def test_between(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE x BETWEEN 10 AND 20")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 15}) is True
        assert ev.evaluate(node, {"x": 25}) is False

    def test_not_between(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT * FROM t WHERE x NOT BETWEEN 10 AND 20")
        node = stmts[0].stmt.whereClause
        assert ev.evaluate(node, {"x": 25}) is True
        assert ev.evaluate(node, {"x": 15}) is False

    def test_typeof(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT typeof(x) FROM t")
        node = stmts[0].stmt.targetList[0].val
        assert ev.evaluate(node, {"x": 42}) == "integer"
        assert ev.evaluate(node, {"x": 3.14}) == "real"
        assert ev.evaluate(node, {"x": "hello"}) == "text"
        assert ev.evaluate(node, {"x": None}) == "null"

    def test_unsupported_node(self):
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        with pytest.raises(ValueError, match="Unsupported expression"):
            ev.evaluate(object(), {})

    def test_unsupported_function(self):
        from pglast import parse_sql
        from uqa.sql.expr_evaluator import ExprEvaluator

        ev = ExprEvaluator()
        stmts = parse_sql("SELECT pg_sleep(1) FROM t")
        node = stmts[0].stmt.targetList[0].val
        with pytest.raises(ValueError, match="Unknown scalar function"):
            ev.evaluate(node, {})


# ==================================================================
# Integration: IS NULL with physical operators
# ==================================================================


class TestNullPhysical:
    def test_is_null_with_group_by(self, engine):
        r = engine.sql(
            "SELECT category, COUNT(*) AS cnt "
            "FROM products GROUP BY category"
        )
        rows_by_cat = {row["category"]: row["cnt"] for row in r.rows}
        assert rows_by_cat[None] == 1
        assert rows_by_cat["tools"] == 1
        assert rows_by_cat["electronics"] == 1

    def test_is_null_with_order_by(self, engine):
        r = engine.sql(
            "SELECT name FROM products "
            "WHERE category IS NOT NULL "
            "ORDER BY name"
        )
        assert r.rows[0]["name"] == "Gadget"
        assert r.rows[1]["name"] == "Widget"

    def test_is_null_with_distinct(self, engine):
        engine.sql(
            "INSERT INTO products (id, name, price, quantity, category) "
            "VALUES (4, 'Thingamajig', 3.00, 10, NULL)"
        )
        r = engine.sql(
            "SELECT DISTINCT category FROM products "
            "WHERE category IS NOT NULL"
        )
        cats = {row["category"] for row in r.rows}
        assert cats == {"tools", "electronics"}
