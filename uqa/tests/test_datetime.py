#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for date/time types, functions, and related operations."""

from __future__ import annotations

import re

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


# ==================================================================
# DATE / TIMESTAMP type support
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
# NOW() / CURRENT_DATE / CURRENT_TIMESTAMP
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
# EXTRACT / DATE_PART / DATE_TRUNC
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
# MAKE_TIMESTAMP
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


# ==================================================================
# MAKE_INTERVAL
# ==================================================================


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


# ==================================================================
# TO_NUMBER
# ==================================================================


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
# OVERLAPS operator
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
