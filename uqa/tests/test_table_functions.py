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
        result = engine.sql(
            "SELECT n FROM generate_series(1, 5) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [1, 2, 3, 4, 5]

    def test_with_step(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(0, 10, 3) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [0, 3, 6, 9]

    def test_descending(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(5, 1, -1) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [5, 4, 3, 2, 1]

    def test_single_value(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(1, 1) AS t(n)"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["n"] == 1

    def test_empty_range(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(5, 1) AS t(n)"
        )
        assert len(result.rows) == 0


# ==================================================================
# UNNEST
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
