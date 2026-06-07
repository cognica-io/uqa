#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for table-returning functions (generate_series, unnest)."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


# ==================================================================
# generate_series
# ==================================================================


class TestGenerateSeries:
    def test_basic(self, engine):
        result = engine.sql("SELECT n FROM generate_series(1, 5) AS t(n)")
        values = [r["n"] for r in result.rows]
        assert values == [1, 2, 3, 4, 5]

    def test_with_step(self, engine):
        result = engine.sql("SELECT n FROM generate_series(0, 10, 3) AS t(n)")
        values = [r["n"] for r in result.rows]
        assert values == [0, 3, 6, 9]

    def test_descending(self, engine):
        result = engine.sql("SELECT n FROM generate_series(5, 1, -1) AS t(n)")
        values = [r["n"] for r in result.rows]
        assert values == [5, 4, 3, 2, 1]

    def test_single_value(self, engine):
        result = engine.sql("SELECT n FROM generate_series(1, 1) AS t(n)")
        assert len(result.rows) == 1
        assert result.rows[0]["n"] == 1

    def test_empty_range(self, engine):
        result = engine.sql("SELECT n FROM generate_series(5, 1) AS t(n)")
        assert len(result.rows) == 0

    def test_expression_arguments(self, engine):
        result = engine.sql("SELECT n FROM generate_series(0, 2 + 1) AS t(n)")
        values = [r["n"] for r in result.rows]
        assert values == [0, 1, 2, 3]

    def test_scalar_subquery_argument(self, engine):
        result = engine.sql("SELECT n FROM generate_series(0, (SELECT 2)) AS t(n)")
        values = [r["n"] for r in result.rows]
        assert values == [0, 1, 2]

    def test_alias_without_column_list_names_single_column(self, engine):
        result = engine.sql("SELECT gs FROM generate_series(1, 3) AS gs")
        values = [r["gs"] for r in result.rows]
        assert values == [1, 2, 3]

    def test_implicit_lateral_argument(self, engine):
        result = engine.sql(
            "WITH params AS (SELECT 3::int AS stop) "
            "SELECT n FROM params p, generate_series(1, p.stop) AS gs(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [1, 2, 3]

    def test_unqualified_function_column_in_join_filter(self, engine):
        result = engine.sql(
            "WITH art AS ("
            "  SELECT t.line, t.sy::int - 1 AS sy "
            "  FROM unnest(ARRAY['aa', 'bb']) WITH ORDINALITY AS t(line, sy)"
            ") "
            "SELECT x, a.sy FROM generate_series(0, 4) x, art a "
            "WHERE a.sy = x / 2 ORDER BY x, a.sy"
        )
        assert result.rows == [
            {"x": 0, "sy": 0},
            {"x": 1, "sy": 0},
            {"x": 2, "sy": 1},
            {"x": 3, "sy": 1},
        ]

    def test_join_lateral_argument(self, engine):
        engine.sql("CREATE TABLE spans(id INT, x0 INT, x1 INT)")
        engine.sql("INSERT INTO spans VALUES (1, 2, 4), (2, 7, 8)")
        result = engine.sql(
            "SELECT id, px FROM spans s "
            "JOIN LATERAL generate_series(s.x0, s.x1) AS px ON TRUE "
            "ORDER BY id, px"
        )
        assert result.rows == [
            {"id": 1, "px": 2},
            {"id": 1, "px": 3},
            {"id": 1, "px": 4},
            {"id": 2, "px": 7},
            {"id": 2, "px": 8},
        ]


# ==================================================================
# UNNEST
# ==================================================================


class TestUnnest:
    def test_basic(self, engine):
        result = engine.sql("SELECT val FROM unnest(ARRAY[10, 20, 30]) AS t(val)")
        assert len(result.rows) == 3
        vals = [r["val"] for r in result.rows]
        assert vals == [10, 20, 30]

    def test_text_array(self, engine):
        result = engine.sql("SELECT val FROM unnest(ARRAY['a', 'b', 'c']) AS t(val)")
        assert len(result.rows) == 3
        vals = [r["val"] for r in result.rows]
        assert vals == ["a", "b", "c"]

    def test_with_ordinality(self, engine):
        result = engine.sql(
            "SELECT line, sy FROM "
            "unnest(ARRAY['a', 'b']) WITH ORDINALITY AS t(line, sy)"
        )
        assert result.rows == [
            {"line": "a", "sy": 1},
            {"line": "b", "sy": 2},
        ]
