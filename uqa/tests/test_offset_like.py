#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for OFFSET and LIKE/ILIKE SQL features."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    e = Engine()
    e.sql(
        "CREATE TABLE items ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "category TEXT, "
        "price REAL"
        ")"
    )
    e.sql(
        "INSERT INTO items (id, name, category, price) VALUES "
        "(1, 'Apple', 'fruit', 1.50), "
        "(2, 'Banana', 'fruit', 0.75), "
        "(3, 'Carrot', 'vegetable', 2.00), "
        "(4, 'Date', 'fruit', 5.00), "
        "(5, 'Eggplant', 'vegetable', 3.50), "
        "(6, 'Fig', 'fruit', 4.00), "
        "(7, 'Grape', 'fruit', 2.50), "
        "(8, 'Habanero', 'pepper', 1.00)"
    )
    return e


# ==================================================================
# OFFSET
# ==================================================================


class TestOffset:
    def test_limit_offset(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id LIMIT 3 OFFSET 2")
        assert [row["id"] for row in r.rows] == [3, 4, 5]

    def test_offset_zero(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id LIMIT 3 OFFSET 0")
        assert [row["id"] for row in r.rows] == [1, 2, 3]

    def test_offset_past_end(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id LIMIT 5 OFFSET 100")
        assert r.rows == []

    def test_offset_last_rows(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id LIMIT 10 OFFSET 6")
        assert [row["id"] for row in r.rows] == [7, 8]

    def test_offset_with_where(self, engine):
        r = engine.sql(
            "SELECT id FROM items WHERE category = 'fruit' "
            "ORDER BY id LIMIT 2 OFFSET 1"
        )
        assert [row["id"] for row in r.rows] == [2, 4]

    def test_offset_with_order_desc(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id DESC LIMIT 3 OFFSET 2")
        assert [row["id"] for row in r.rows] == [6, 5, 4]

    def test_offset_single_row(self, engine):
        r = engine.sql("SELECT id FROM items ORDER BY id LIMIT 1 OFFSET 4")
        assert [row["id"] for row in r.rows] == [5]

    def test_offset_with_aggregation(self, engine):
        """OFFSET should apply after GROUP BY aggregation."""
        r = engine.sql(
            "SELECT category, COUNT(*) AS cnt FROM items "
            "GROUP BY category ORDER BY category LIMIT 2 OFFSET 1"
        )
        assert len(r.rows) == 2
        # categories sorted: fruit, pepper, vegetable
        assert r.rows[0]["category"] == "pepper"
        assert r.rows[1]["category"] == "vegetable"


# ==================================================================
# LIKE
# ==================================================================


class TestLike:
    def test_like_prefix(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE 'A%'")
        assert [row["name"] for row in r.rows] == ["Apple"]

    def test_like_suffix(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE '%e'")
        names = sorted(row["name"] for row in r.rows)
        assert names == ["Apple", "Date", "Grape"]

    def test_like_contains(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE '%an%'")
        names = sorted(row["name"] for row in r.rows)
        # Banana, Eggplant, Habanero all contain 'an'
        assert names == ["Banana", "Eggplant", "Habanero"]

    def test_like_single_char_wildcard(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE '_ig'")
        assert [row["name"] for row in r.rows] == ["Fig"]

    def test_like_exact_match(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE 'Apple'")
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Apple"

    def test_like_no_match(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name LIKE 'Xyz%'")
        assert r.rows == []

    def test_like_case_sensitive(self, engine):
        """LIKE is case-sensitive."""
        r = engine.sql("SELECT name FROM items WHERE name LIKE 'apple'")
        assert r.rows == []

    def test_not_like(self, engine):
        r = engine.sql(
            "SELECT name FROM items WHERE name NOT LIKE '%a%' ORDER BY name"
        )
        # Case-sensitive: lowercase 'a' appears in Banana, Carrot, Date, Eggplant, Grape, Habanero
        # Only Apple (uppercase A only) and Fig (no a at all) lack lowercase 'a'
        names = [row["name"] for row in r.rows]
        assert names == ["Apple", "Fig"]


class TestILike:
    def test_ilike_case_insensitive(self, engine):
        """ILIKE should match case-insensitively."""
        r = engine.sql("SELECT name FROM items WHERE name ILIKE 'apple'")
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Apple"

    def test_ilike_prefix(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name ILIKE 'a%'")
        assert [row["name"] for row in r.rows] == ["Apple"]

    def test_ilike_suffix(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name ILIKE '%E'")
        names = sorted(row["name"] for row in r.rows)
        assert names == ["Apple", "Date", "Grape"]

    def test_ilike_pattern_mixed_case(self, engine):
        r = engine.sql("SELECT name FROM items WHERE name ILIKE '%BANANA%'")
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Banana"

    def test_not_ilike(self, engine):
        r = engine.sql(
            "SELECT name FROM items WHERE name NOT ILIKE '%A%' ORDER BY name"
        )
        # NOT ILIKE '%A%' (case insensitive): exclude names containing 'a' or 'A'
        # All names have 'a' or 'A' except: Fig, Eggplant has 'a'... let's check
        # Apple(A), Banana(a), Carrot(a), Date(a), Eggplant(a), Fig(no a/A), Grape(a), Habanero(a)
        assert [row["name"] for row in r.rows] == ["Fig"]


class TestLikeWithExpressions:
    def test_like_in_case(self, engine):
        """LIKE inside CASE WHEN expression."""
        r = engine.sql(
            "SELECT name, "
            "CASE WHEN name LIKE 'A%' THEN 'starts_A' "
            "     WHEN name LIKE 'B%' THEN 'starts_B' "
            "     ELSE 'other' END AS grp "
            "FROM items ORDER BY id LIMIT 3"
        )
        assert r.rows[0]["grp"] == "starts_A"
        assert r.rows[1]["grp"] == "starts_B"
        assert r.rows[2]["grp"] == "other"

    def test_like_with_and(self, engine):
        r = engine.sql(
            "SELECT name FROM items "
            "WHERE name LIKE '%a%' AND category = 'fruit' "
            "ORDER BY name"
        )
        # fruit items with lowercase 'a': Banana, Date, Grape
        assert [row["name"] for row in r.rows] == ["Banana", "Date", "Grape"]

    def test_like_with_or(self, engine):
        r = engine.sql(
            "SELECT name FROM items "
            "WHERE name LIKE 'A%' OR name LIKE 'B%' "
            "ORDER BY name"
        )
        assert [row["name"] for row in r.rows] == ["Apple", "Banana"]

    def test_like_with_order_and_limit(self, engine):
        r = engine.sql(
            "SELECT name FROM items WHERE name LIKE '%a%' "
            "ORDER BY name LIMIT 2"
        )
        # 6 matches sorted: Banana, Carrot, Date, Eggplant, Grape, Habanero
        assert [row["name"] for row in r.rows] == ["Banana", "Carrot"]

    def test_ilike_in_where_expr(self, engine):
        """ILIKE should work in expression-based WHERE."""
        r = engine.sql(
            "SELECT name FROM items WHERE name ILIKE '%egg%'"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["name"] == "Eggplant"


class TestLikeUpdate:
    def test_update_where_like(self, engine):
        engine.sql("UPDATE items SET category = 'tropical' WHERE name LIKE '%an%'")
        r = engine.sql(
            "SELECT name FROM items WHERE category = 'tropical' ORDER BY name"
        )
        # Banana, Eggplant, Habanero all contain 'an'
        assert [row["name"] for row in r.rows] == [
            "Banana", "Eggplant", "Habanero"
        ]

    def test_delete_where_like(self, engine):
        engine.sql("DELETE FROM items WHERE name LIKE 'E%'")
        r = engine.sql("SELECT id FROM items ORDER BY id")
        ids = [row["id"] for row in r.rows]
        assert 5 not in ids  # Eggplant removed
        assert len(ids) == 7
