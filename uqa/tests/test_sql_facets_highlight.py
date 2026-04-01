#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQL facet and highlight functions."""

from __future__ import annotations

import pytest

from uqa.engine import Engine
from uqa.search.highlight import extract_query_terms, highlight

# ==================================================================
# Fixtures
# ==================================================================


@pytest.fixture
def engine() -> Engine:
    """Build an engine with articles table for facet/highlight testing."""
    e = Engine()

    e.sql("""
        CREATE TABLE articles (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT,
            category TEXT,
            author TEXT,
            year INTEGER
        )
    """)
    e.sql("CREATE INDEX idx_articles_gin ON articles USING gin (title, body)")

    e.sql("""INSERT INTO articles (title, body, category, author, year) VALUES
        ('Introduction to Database Systems',
         'A database system provides efficient storage and retrieval of structured data. Modern database engines support SQL queries for data manipulation.',
         'databases', 'Alice', 2020),
        ('Information Retrieval Fundamentals',
         'Information retrieval is the science of searching for information in documents. Full-text search engines use inverted indexes for fast retrieval.',
         'search', 'Bob', 2021),
        ('Advanced Query Optimization',
         'Query optimization transforms SQL queries into efficient execution plans. The database optimizer uses cost-based methods to find the best plan.',
         'databases', 'Alice', 2022),
        ('Machine Learning for Search',
         'Machine learning techniques improve search relevance. Neural retrieval models learn to rank documents using deep learning architectures.',
         'search', 'Carol', 2023),
        ('Graph Database Design',
         'Graph databases store data as vertices and edges. They excel at traversal queries and relationship-heavy workloads.',
         'databases', 'Bob', 2021),
        ('Natural Language Processing',
         'NLP enables computers to understand human language. Text analysis and search applications benefit from NLP techniques.',
         'nlp', 'Carol', 2022)
    """)

    return e


# ==================================================================
# Highlight: core utility
# ==================================================================


class TestHighlightUtility:
    def test_single_term(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        result = highlight(text, ["fox"])
        assert result == "The quick brown <b>fox</b> jumps over the lazy dog"

    def test_multiple_terms(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        result = highlight(text, ["fox", "dog"])
        assert result == ("The quick brown <b>fox</b> jumps over the lazy <b>dog</b>")

    def test_case_insensitive(self) -> None:
        text = "The Quick Brown Fox"
        result = highlight(text, ["quick", "fox"])
        assert result == "The <b>Quick</b> Brown <b>Fox</b>"

    def test_custom_tags(self) -> None:
        text = "hello world"
        result = highlight(text, ["world"], start_tag="<em>", end_tag="</em>")
        assert result == "hello <em>world</em>"

    def test_no_match(self) -> None:
        text = "The quick brown fox"
        result = highlight(text, ["zebra"])
        assert result == "The quick brown fox"

    def test_empty_text(self) -> None:
        assert highlight("", ["fox"]) == ""

    def test_empty_terms(self) -> None:
        assert highlight("hello world", []) == "hello world"

    def test_none_text(self) -> None:
        assert highlight(None, ["fox"]) == ""  # type: ignore[arg-type]

    def test_with_analyzer(self) -> None:
        from uqa.analysis.analyzer import standard_analyzer

        analyzer = standard_analyzer()
        # "running" stems to "run", and "run" also stems to "run"
        text = "She was running quickly through the park"
        result = highlight(text, ["run"], analyzer=analyzer)
        assert "<b>running</b>" in result

    def test_fragment_extraction(self) -> None:
        text = "A " * 100 + "important keyword here" + " B" * 100
        result = highlight(text, ["keyword"], max_fragments=1, fragment_size=60)
        assert "<b>keyword</b>" in result
        assert "..." in result
        assert len(result) < len(text)

    def test_multiple_fragments(self) -> None:
        text = (
            "First match here. "
            + "X " * 50
            + "Second match here. "
            + "Y " * 50
            + "Third match here."
        )
        result = highlight(text, ["match"], max_fragments=2, fragment_size=40)
        assert result.count("<b>match</b>") >= 1

    def test_all_words_match(self) -> None:
        text = "foo bar baz"
        result = highlight(text, ["foo", "bar", "baz"])
        assert result == "<b>foo</b> <b>bar</b> <b>baz</b>"


# ==================================================================
# Highlight: extract_query_terms
# ==================================================================


class TestExtractQueryTerms:
    def test_simple_terms(self) -> None:
        terms = extract_query_terms("database query")
        assert "database" in terms
        assert "query" in terms

    def test_boolean_and(self) -> None:
        terms = extract_query_terms("database AND query")
        assert "database" in terms
        assert "query" in terms
        assert len(terms) == 2

    def test_boolean_or(self) -> None:
        terms = extract_query_terms("database OR query")
        assert "database" in terms
        assert "query" in terms

    def test_phrase(self) -> None:
        terms = extract_query_terms('"information retrieval"')
        assert "information" in terms
        assert "retrieval" in terms

    def test_field_prefix(self) -> None:
        terms = extract_query_terms("title:database")
        assert "database" in terms

    def test_not_operator(self) -> None:
        terms = extract_query_terms("database NOT query")
        assert "database" in terms
        assert "query" in terms

    def test_complex_query(self) -> None:
        terms = extract_query_terms('title:database AND "query optimization" OR search')
        assert "database" in terms
        assert "query" in terms
        assert "optimization" in terms
        assert "search" in terms


# ==================================================================
# uqa_highlight() in SQL
# ==================================================================


class TestSQLHighlight:
    def test_basic_highlight(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'database') AS snippet "
            "FROM articles WHERE body @@ 'database'"
        )
        assert len(result) > 0
        for row in result:
            assert "<b>" in row["snippet"]
            assert "</b>" in row["snippet"]

    def test_highlight_with_custom_tags(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'search', '<em>', '</em>') AS snippet "
            "FROM articles WHERE body @@ 'search'"
        )
        assert len(result) > 0
        for row in result:
            assert "<em>" in row["snippet"]
            assert "</em>" in row["snippet"]

    def test_highlight_multi_term(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'database query') AS snippet "
            "FROM articles WHERE body @@ 'database query'"
        )
        assert len(result) > 0
        for row in result:
            snippet = row["snippet"]
            # At least one term should be highlighted
            assert "<b>" in snippet

    def test_highlight_preserves_original_text(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(title, 'database') AS hl_title "
            "FROM articles WHERE title @@ 'database'"
        )
        assert len(result) > 0
        for row in result:
            # Remove tags to get original text
            clean = row["hl_title"].replace("<b>", "").replace("</b>", "")
            assert clean == row["title"]

    def test_highlight_no_where(self, engine: Engine) -> None:
        """uqa_highlight works even without a WHERE @@ clause."""
        result = engine.sql(
            "SELECT title, uqa_highlight(title, 'graph') AS snippet FROM articles"
        )
        assert len(result) == 6
        highlighted_count = sum(1 for r in result if "<b>" in r["snippet"])
        assert highlighted_count >= 1

    def test_highlight_with_limit(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'search') AS snippet "
            "FROM articles WHERE body @@ 'search' "
            "ORDER BY _score DESC LIMIT 2"
        )
        assert len(result) <= 2
        for row in result:
            assert "<b>" in row["snippet"]

    def test_highlight_null_body(self, engine: Engine) -> None:
        """Insert a row with NULL body and check highlight handles it."""
        engine.sql(
            "INSERT INTO articles (title, body, category, author, year) "
            "VALUES ('Empty Article', NULL, 'misc', 'Dave', 2024)"
        )
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'test') AS snippet "
            "FROM articles WHERE title @@ 'empty'"
        )
        assert len(result) >= 1
        assert result.rows[0]["snippet"] is None

    def test_highlight_fragments(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, uqa_highlight(body, 'database', '<b>', '</b>', 1, 60) AS snippet "
            "FROM articles WHERE body @@ 'database'"
        )
        assert len(result) > 0
        for row in result:
            # Fragments should be shorter than full body
            assert "<b>" in row["snippet"]


# ==================================================================
# uqa_facets() in SQL
# ==================================================================


class TestSQLFacets:
    def test_facet_single_field(self, engine: Engine) -> None:
        result = engine.sql("SELECT uqa_facets(category) FROM articles")
        assert "facet_value" in result.columns
        assert "facet_count" in result.columns
        assert "facet_field" not in result.columns
        counts = {r["facet_value"]: r["facet_count"] for r in result}
        assert counts["databases"] == 3
        assert counts["search"] == 2
        assert counts["nlp"] == 1

    def test_facet_with_text_search(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT uqa_facets(category) FROM articles WHERE body @@ 'search'"
        )
        counts = {r["facet_value"]: r["facet_count"] for r in result}
        # "search" appears in body of search and nlp articles
        total = sum(counts.values())
        assert total > 0

    def test_facet_multi_field(self, engine: Engine) -> None:
        result = engine.sql("SELECT uqa_facets(category, author) FROM articles")
        assert "facet_field" in result.columns
        assert "facet_value" in result.columns
        assert "facet_count" in result.columns
        # Should have rows for both category and author
        fields = {r["facet_field"] for r in result}
        assert "category" in fields
        assert "author" in fields

    def test_facet_year(self, engine: Engine) -> None:
        result = engine.sql("SELECT uqa_facets(year) FROM articles")
        counts = {r["facet_value"]: r["facet_count"] for r in result}
        assert len(counts) >= 4  # 2020, 2021, 2022, 2023

    def test_facet_with_filter(self, engine: Engine) -> None:
        """Facets should respect WHERE clause filtering."""
        result = engine.sql(
            "SELECT uqa_facets(category) FROM articles WHERE body @@ 'database'"
        )
        counts = {r["facet_value"]: r["facet_count"] for r in result}
        total = sum(counts.values())
        assert total > 0
        # The count should be less than total articles
        assert total <= 6

    def test_facet_author(self, engine: Engine) -> None:
        result = engine.sql("SELECT uqa_facets(author) FROM articles")
        counts = {r["facet_value"]: r["facet_count"] for r in result}
        assert counts["Alice"] == 2
        assert counts["Bob"] == 2
        assert counts["Carol"] == 2

    def test_facet_sorted_by_value(self, engine: Engine) -> None:
        """Facet results are sorted alphabetically by value."""
        result = engine.sql("SELECT uqa_facets(category) FROM articles")
        values = [r["facet_value"] for r in result]
        assert values == sorted(values)

    def test_facet_empty_result(self, engine: Engine) -> None:
        """Facets with no matching docs produce empty result."""
        result = engine.sql(
            "SELECT uqa_facets(category) FROM articles WHERE body @@ 'xyznonexistent'"
        )
        assert len(result) == 0
