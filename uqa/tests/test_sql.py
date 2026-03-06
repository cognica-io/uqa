#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the SQL-to-UQA compiler (DDL / DML / DQL)."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.sql.compiler import SQLCompiler, SQLResult


# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def engine() -> Engine:
    """Build an engine with a SQL table and a citation graph."""
    e = Engine(vector_dimensions=8, max_elements=100)

    # -- DDL: create table -------------------------------------------
    e.sql("""
        CREATE TABLE papers (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            venue TEXT,
            field TEXT,
            citations INTEGER DEFAULT 0
        )
    """)

    # -- DML: insert rows --------------------------------------------
    e.sql("""INSERT INTO papers (title, year, venue, field, citations) VALUES
        ('attention is all you need', 2017, 'NeurIPS', 'nlp', 90000),
        ('bert pre-training of deep bidirectional transformers', 2019, 'NAACL', 'nlp', 75000),
        ('graph attention networks', 2018, 'ICLR', 'graph', 15000),
        ('vision transformer for image recognition', 2021, 'ICLR', 'cv', 25000),
        ('scaling language models methods and insights', 2020, 'arXiv', 'nlp', 8000)
    """)

    # -- Graph: citation edges (programmatic API) --------------------
    docs = [
        "attention is all you need",
        "bert pre-training of deep bidirectional transformers",
        "graph attention networks",
        "vision transformer for image recognition",
        "scaling language models methods and insights",
    ]
    for i, title in enumerate(docs, 1):
        e.add_graph_vertex(Vertex(i, {"title": title}))
    e.add_graph_edge(Edge(1, 1, 2, "cited_by"))
    e.add_graph_edge(Edge(2, 1, 3, "cited_by"))
    e.add_graph_edge(Edge(3, 2, 4, "cited_by"))

    return e


# ==================================================================
# DDL: CREATE TABLE / DROP TABLE
# ==================================================================

class TestDDL:
    def test_create_table(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT NOT NULL)")
        assert "users" in e._tables
        table = e._tables["users"]
        assert table.column_names == ["id", "name"]
        assert table.columns["id"].auto_increment is True
        assert table.columns["name"].not_null is True

    def test_create_table_duplicate_raises(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("CREATE TABLE papers (id SERIAL PRIMARY KEY)")

    def test_drop_table(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE temp (id SERIAL PRIMARY KEY)")
        assert "temp" in e._tables
        e.sql("DROP TABLE temp")
        assert "temp" not in e._tables

    def test_drop_table_if_exists(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        # Should not raise
        e.sql("DROP TABLE IF EXISTS nonexistent")

    def test_drop_table_missing_raises(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("DROP TABLE nonexistent")


# ==================================================================
# DML: INSERT INTO
# ==================================================================

class TestInsert:
    def test_insert_single_row(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        result = e.sql("INSERT INTO t (name) VALUES ('alice')")
        assert result.rows[0]["inserted"] == 1
        assert e._tables["t"].row_count == 1

    def test_insert_multiple_rows(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        result = e.sql("INSERT INTO t (val) VALUES (10), (20), (30)")
        assert result.rows[0]["inserted"] == 3
        assert e._tables["t"].row_count == 3

    def test_insert_auto_increment(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        e.sql("INSERT INTO t (name) VALUES ('a')")
        e.sql("INSERT INTO t (name) VALUES ('b')")
        r = e.sql("SELECT id, name FROM t ORDER BY id")
        assert r.rows[0]["id"] == 1
        assert r.rows[1]["id"] == 2

    def test_insert_missing_table_raises(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("INSERT INTO missing (x) VALUES (1)")

    def test_insert_not_null_violation(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT NOT NULL)")
        with pytest.raises(ValueError, match="NOT NULL"):
            e.sql("INSERT INTO t (id) VALUES (1)")


# ==================================================================
# DQL: Basic SELECT
# ==================================================================

class TestBasicSelect:
    def test_select_all(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers")
        assert len(result) == 5
        assert "id" in result.columns

    def test_select_columns(self, engine: Engine) -> None:
        result = engine.sql("SELECT title, year FROM papers")
        assert result.columns == ["title", "year"]
        assert len(result) == 5
        for row in result:
            assert "title" in row
            assert "year" in row
            assert "venue" not in row

    def test_select_limit(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers LIMIT 3")
        assert len(result) == 3

    def test_select_order_by_asc(self, engine: Engine) -> None:
        result = engine.sql("SELECT title, year FROM papers ORDER BY year")
        years = [r["year"] for r in result]
        assert years == sorted(years)

    def test_select_order_by_desc(self, engine: Engine) -> None:
        result = engine.sql("SELECT title, year FROM papers ORDER BY year DESC")
        years = [r["year"] for r in result]
        assert years == sorted(years, reverse=True)

    def test_order_by_with_limit(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, year FROM papers ORDER BY year DESC LIMIT 2"
        )
        assert len(result) == 2
        assert result.rows[0]["year"] >= result.rows[1]["year"]

    def test_select_from_missing_table_raises(self) -> None:
        e = Engine(vector_dimensions=8, max_elements=100)
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("SELECT * FROM missing")


# ==================================================================
# DQL: WHERE clause
# ==================================================================

class TestWhereClause:
    def test_equals(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM papers WHERE field = 'nlp'")
        assert len(result) == 3

    def test_not_equals(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM papers WHERE field != 'nlp'")
        assert len(result) == 2

    def test_greater_than(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE year > 2019")
        for row in result:
            assert row["year"] > 2019

    def test_greater_than_or_equal(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE year >= 2020")
        for row in result:
            assert row["year"] >= 2020

    def test_less_than(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE year < 2019")
        for row in result:
            assert row["year"] < 2019

    def test_in_clause(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE field IN ('nlp', 'cv')")
        assert len(result) == 4
        for row in result:
            assert row["field"] in ("nlp", "cv")

    def test_between(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE year BETWEEN 2018 AND 2020")
        for row in result:
            assert 2018 <= row["year"] <= 2020

    def test_and(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM papers WHERE field = 'nlp' AND year >= 2019"
        )
        for row in result:
            assert row["field"] == "nlp"
            assert row["year"] >= 2019

    def test_or(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM papers WHERE field = 'graph' OR field = 'cv'"
        )
        assert len(result) == 2
        for row in result:
            assert row["field"] in ("graph", "cv")

    def test_not(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE NOT field = 'nlp'")
        for row in result:
            assert row["field"] != "nlp"

    def test_complex_boolean(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM papers WHERE (field = 'nlp' OR field = 'cv') AND year >= 2020"
        )
        for row in result:
            assert row["field"] in ("nlp", "cv")
            assert row["year"] >= 2020


# ==================================================================
# DQL: Text search
# ==================================================================

class TestTextSearch:
    def test_text_match_single_term(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM papers "
            "WHERE text_match(title, 'attention') ORDER BY _score DESC"
        )
        assert len(result) >= 2
        scores = [r["_score"] for r in result]
        assert scores == sorted(scores, reverse=True)
        assert all(s > 0 for s in scores)

    def test_text_match_multi_term(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM papers "
            "WHERE text_match(title, 'attention transformer')"
        )
        assert len(result) >= 2

    def test_text_match_with_filter(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM papers "
            "WHERE text_match(title, 'attention') AND year >= 2018 "
            "ORDER BY _score DESC"
        )
        for row in result:
            assert row["_score"] > 0

    def test_bayesian_match(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM papers "
            "WHERE bayesian_match(title, 'attention') ORDER BY _score DESC"
        )
        assert len(result) >= 2
        for row in result:
            assert 0 < row["_score"] < 1

    def test_text_search_from_clause(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score "
            "FROM text_search('attention', 'title', 'papers') "
            "ORDER BY _score DESC"
        )
        assert len(result) >= 2
        assert all(r["_score"] > 0 for r in result)


# ==================================================================
# DQL: Aggregation
# ==================================================================

class TestAggregation:
    def test_count_all(self, engine: Engine) -> None:
        result = engine.sql("SELECT COUNT(*) AS total FROM papers")
        assert len(result) == 1
        assert result.rows[0]["total"] == 5

    def test_avg(self, engine: Engine) -> None:
        result = engine.sql("SELECT AVG(citations) AS avg_cites FROM papers")
        assert len(result) == 1
        avg = result.rows[0]["avg_cites"]
        assert isinstance(avg, float)
        assert avg > 0

    def test_min_max(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT MIN(year) AS earliest, MAX(year) AS latest FROM papers"
        )
        assert result.rows[0]["earliest"] == 2017
        assert result.rows[0]["latest"] == 2021

    def test_group_by(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT field, COUNT(*) AS cnt FROM papers "
            "GROUP BY field ORDER BY cnt DESC"
        )
        assert len(result) >= 3
        counts = [r["cnt"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_group_by_with_avg(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT field, AVG(citations) AS avg_cites FROM papers GROUP BY field"
        )
        nlp_row = next(r for r in result if r["field"] == "nlp")
        assert nlp_row["avg_cites"] > 0

    def test_having(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT field, COUNT(*) AS cnt FROM papers "
            "GROUP BY field HAVING COUNT(*) >= 2"
        )
        for row in result:
            assert row["cnt"] >= 2


# ==================================================================
# DQL: Graph queries
# ==================================================================

class TestGraphQueries:
    def test_traverse(self, engine: Engine) -> None:
        result = engine.sql("SELECT _doc_id, title FROM traverse(1, 'cited_by', 1)")
        doc_ids = {r["_doc_id"] for r in result}
        assert 2 in doc_ids
        assert 3 in doc_ids

    def test_traverse_2_hops(self, engine: Engine) -> None:
        result = engine.sql("SELECT _doc_id FROM traverse(1, 'cited_by', 2)")
        doc_ids = {r["_doc_id"] for r in result}
        assert 4 in doc_ids  # 1->2->4

    def test_rpq(self, engine: Engine) -> None:
        result = engine.sql("SELECT _doc_id FROM rpq('cited_by/cited_by', 1)")
        doc_ids = {r["_doc_id"] for r in result}
        assert 4 in doc_ids  # 1->2->4


# ==================================================================
# SQLResult formatting
# ==================================================================

class TestSQLResult:
    def test_str_format(self, engine: Engine) -> None:
        result = engine.sql("SELECT title, year FROM papers LIMIT 2")
        s = str(result)
        assert "title" in s
        assert "year" in s
        assert "(2 rows)" in s

    def test_empty_result(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers WHERE year > 9999")
        assert len(result) == 0
        assert str(result) == "(0 rows)"

    def test_iter(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM papers LIMIT 3")
        rows = list(result)
        assert len(rows) == 3

    def test_repr(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers")
        assert "5 rows" in repr(result)


# ==================================================================
# Edge cases
# ==================================================================

class TestEdgeCases:
    def test_no_where_clause(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers")
        assert len(result) == 5

    def test_filtered_aggregate(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT COUNT(*) AS cnt FROM papers WHERE year >= 2020"
        )
        assert result.rows[0]["cnt"] == 2

    def test_knn_without_vector_raises(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="No query vector"):
            engine.sql("SELECT * FROM papers WHERE knn_match(5)")

    def test_unsupported_statement(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unsupported statement"):
            engine.sql("UPDATE papers SET year = 2025")

    def test_unknown_function(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unknown function"):
            engine.sql(
                "SELECT * FROM papers WHERE unknown_func(title, 'test')"
            )
