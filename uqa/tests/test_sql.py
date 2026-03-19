#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the SQL-to-UQA compiler (DDL / DML / DQL)."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# ==================================================================
# Fixtures
# ==================================================================


@pytest.fixture
def engine() -> Engine:
    """Build an engine with a SQL table and a citation graph."""
    e = Engine()

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

    # -- Graph: citation edges (per-table graph store) ---------------
    e.add_graph_edge(Edge(1, 1, 2, "cited_by"), table="papers")
    e.add_graph_edge(Edge(2, 1, 3, "cited_by"), table="papers")
    e.add_graph_edge(Edge(3, 2, 4, "cited_by"), table="papers")

    return e


# ==================================================================
# DDL: CREATE TABLE / DROP TABLE
# ==================================================================


class TestDDL:
    def test_create_table(self) -> None:
        e = Engine()
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
        e = Engine()
        e.sql("CREATE TABLE temp (id SERIAL PRIMARY KEY)")
        assert "temp" in e._tables
        e.sql("DROP TABLE temp")
        assert "temp" not in e._tables

    def test_drop_table_if_exists(self) -> None:
        e = Engine()
        # Should not raise
        e.sql("DROP TABLE IF EXISTS nonexistent")

    def test_drop_table_missing_raises(self) -> None:
        e = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("DROP TABLE nonexistent")


# ==================================================================
# DML: INSERT INTO
# ==================================================================


class TestInsert:
    def test_insert_single_row(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        result = e.sql("INSERT INTO t (name) VALUES ('alice')")
        assert result.rows[0]["inserted"] == 1
        assert e._tables["t"].row_count == 1

    def test_insert_multiple_rows(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        result = e.sql("INSERT INTO t (val) VALUES (10), (20), (30)")
        assert result.rows[0]["inserted"] == 3
        assert e._tables["t"].row_count == 3

    def test_insert_auto_increment(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        e.sql("INSERT INTO t (name) VALUES ('a')")
        e.sql("INSERT INTO t (name) VALUES ('b')")
        r = e.sql("SELECT id, name FROM t ORDER BY id")
        assert r.rows[0]["id"] == 1
        assert r.rows[1]["id"] == 2

    def test_insert_missing_table_raises(self) -> None:
        e = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("INSERT INTO missing (x) VALUES (1)")

    def test_insert_not_null_violation(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT NOT NULL)")
        with pytest.raises(ValueError, match="NOT NULL"):
            e.sql("INSERT INTO t (id) VALUES (1)")

    def test_insert_parameterized_scalar(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT, val INTEGER)")
        e.sql("INSERT INTO t (name, val) VALUES ($1, $2)", params=["alice", 42])
        r = e.sql("SELECT name, val FROM t")
        assert r.rows[0]["name"] == "alice"
        assert r.rows[0]["val"] == 42

    def test_insert_parameterized_vector(self) -> None:
        import numpy as np

        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, embedding VECTOR(3))")
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        e.sql("INSERT INTO t (embedding) VALUES ($1)", params=[vec])
        r = e.sql("SELECT embedding FROM t")
        assert r.rows[0]["embedding"] == [1.0, 2.0, 3.0]

    def test_insert_parameterized_missing_param(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        with pytest.raises(ValueError, match="not provided"):
            e.sql("INSERT INTO t (val) VALUES ($2)", params=[1])


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
        result = engine.sql("SELECT title, year FROM papers ORDER BY year DESC LIMIT 2")
        assert len(result) == 2
        assert result.rows[0]["year"] >= result.rows[1]["year"]

    def test_select_from_missing_table_raises(self) -> None:
        e = Engine()
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
        result = engine.sql("SELECT * FROM papers WHERE field = 'nlp' AND year >= 2019")
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
            "SELECT title FROM papers WHERE text_match(title, 'attention transformer')"
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
            "SELECT field, COUNT(*) AS cnt FROM papers GROUP BY field ORDER BY cnt DESC"
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
        result = engine.sql(
            "SELECT _doc_id, title FROM traverse(1, 'cited_by', 1, 'papers')"
        )
        doc_ids = {r["_doc_id"] for r in result}
        assert 2 in doc_ids
        assert 3 in doc_ids

    def test_traverse_2_hops(self, engine: Engine) -> None:
        result = engine.sql("SELECT _doc_id FROM traverse(1, 'cited_by', 2, 'papers')")
        doc_ids = {r["_doc_id"] for r in result}
        assert 4 in doc_ids  # 1->2->4

    def test_rpq(self, engine: Engine) -> None:
        result = engine.sql("SELECT _doc_id FROM rpq('cited_by/cited_by', 1, 'papers')")
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

    def test_to_arrow(self, engine: Engine) -> None:
        import pyarrow as pa

        result = engine.sql("SELECT title, year, citations FROM papers ORDER BY year")
        table = result.to_arrow()
        assert isinstance(table, pa.Table)
        assert table.num_rows == 5
        assert table.column_names == ["title", "year", "citations"]
        assert table.column("year").type == pa.int64()
        assert table.column("title").type == pa.string()
        assert table.column("year").to_pylist() == [2017, 2018, 2019, 2020, 2021]

    def test_to_arrow_empty(self, engine: Engine) -> None:
        import pyarrow as pa

        result = engine.sql("SELECT title, year FROM papers WHERE year > 9999")
        table = result.to_arrow()
        assert isinstance(table, pa.Table)
        assert table.num_rows == 0
        assert table.column_names == ["title", "year"]

    def test_to_arrow_mixed_types(self, engine: Engine) -> None:
        import pyarrow as pa

        result = engine.sql("SELECT 1 AS i, 3.14 AS f, 'hello' AS s, TRUE AS b")
        table = result.to_arrow()
        assert table.column("i").type == pa.int64()
        assert table.column("f").type == pa.float64()
        assert table.column("s").type == pa.string()
        assert table.column("b").type == pa.bool_()

    def test_to_arrow_with_nulls(self, engine: Engine) -> None:
        result = engine.sql("SELECT 1 AS v UNION ALL SELECT NULL")
        table = result.to_arrow()
        assert table.num_rows == 2
        assert table.column("v").null_count == 1

    def test_to_parquet(self, engine: Engine, tmp_path) -> None:
        import pyarrow.parquet as pq

        path = str(tmp_path / "test.parquet")
        result = engine.sql("SELECT title, year, citations FROM papers ORDER BY year")
        result.to_parquet(path)

        table = pq.read_table(path)
        assert table.num_rows == 5
        assert table.column_names == ["title", "year", "citations"]
        assert table.column("year").to_pylist() == [2017, 2018, 2019, 2020, 2021]

    def test_to_parquet_roundtrip(self, engine: Engine, tmp_path) -> None:
        import pyarrow.parquet as pq

        path = str(tmp_path / "roundtrip.parquet")
        result = engine.sql(
            "SELECT title, year FROM papers WHERE year >= 2020 ORDER BY year"
        )
        result.to_parquet(path)

        table = pq.read_table(path)
        assert table.num_rows == 2
        titles = table.column("title").to_pylist()
        assert "scaling language models methods and insights" in titles
        assert "vision transformer for image recognition" in titles


# ==================================================================
# EXPLAIN / ANALYZE
# ==================================================================


class TestExplain:
    def test_explain_select(self, engine: Engine) -> None:
        result = engine.sql(
            "EXPLAIN SELECT * FROM papers WHERE text_match(title, 'attention')"
        )
        assert len(result) >= 1
        assert result.columns == ["plan"]
        plan_text = "\n".join(r["plan"] for r in result)
        assert "estimated cost" in plan_text

    def test_explain_filter(self, engine: Engine) -> None:
        result = engine.sql("EXPLAIN SELECT * FROM papers WHERE year > 2020")
        assert len(result) >= 1
        plan_text = "\n".join(r["plan"] for r in result)
        assert "FilterOp" in plan_text

    def test_explain_no_where(self, engine: Engine) -> None:
        result = engine.sql("EXPLAIN SELECT * FROM papers")
        assert len(result) >= 1
        plan_text = "\n".join(r["plan"] for r in result)
        assert "Seq Scan" in plan_text


class TestAnalyze:
    def test_analyze_table(self, engine: Engine) -> None:
        engine.sql("ANALYZE papers")
        table = engine._tables["papers"]
        assert len(table._stats) > 0
        year_stats = table.get_column_stats("year")
        assert year_stats is not None
        assert year_stats.min_value == 2017
        assert year_stats.max_value == 2021
        assert year_stats.row_count == 5
        assert year_stats.null_count == 0
        assert year_stats.distinct_count == 5

    def test_analyze_all_tables(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t1 (id SERIAL PRIMARY KEY, val INTEGER)")
        e.sql("CREATE TABLE t2 (id SERIAL PRIMARY KEY, name TEXT)")
        e.sql("INSERT INTO t1 (val) VALUES (1), (2), (3)")
        e.sql("INSERT INTO t2 (name) VALUES ('a'), ('b')")
        e.sql("ANALYZE")
        assert len(e._tables["t1"]._stats) > 0
        assert len(e._tables["t2"]._stats) > 0

    def test_column_stats_selectivity(self, engine: Engine) -> None:
        engine.sql("ANALYZE papers")
        table = engine._tables["papers"]
        field_stats = table.get_column_stats("field")
        assert field_stats is not None
        # 3 distinct fields: nlp, graph, cv
        assert field_stats.distinct_count == 3
        # Equality selectivity = 1/ndv
        assert abs(field_stats.selectivity - 1.0 / 3.0) < 0.01

    def test_analyze_improves_cardinality(self, engine: Engine) -> None:
        """After ANALYZE, filter selectivity should use real statistics."""
        from uqa.core.types import Equals, IndexStats
        from uqa.operators.primitive import FilterOperator
        from uqa.planner.cardinality import CardinalityEstimator

        engine.sql("ANALYZE papers")
        table = engine._tables["papers"]

        # Without stats: default selectivity = 0.5
        est_no_stats = CardinalityEstimator()
        stats = IndexStats(total_docs=5)
        op = FilterOperator("field", Equals("nlp"))
        card_no_stats = est_no_stats.estimate(op, stats)

        # With stats: MCV gives exact frequency for 'nlp' (3/5 = 0.6)
        est_with_stats = CardinalityEstimator(table._stats)
        card_with_stats = est_with_stats.estimate(op, stats)

        # Stats-based estimate should be different (more precise)
        assert card_no_stats == 5 * 0.5  # 2.5
        # MCV: nlp appears 3/5 = 0.6, so estimated cardinality = 5 * 0.6 = 3.0
        assert abs(card_with_stats - 3.0) < 0.01


# ==================================================================
# Edge cases
# ==================================================================

# ==================================================================
# DISTINCT
# ==================================================================


class TestDistinct:
    def test_select_distinct(self, engine: Engine) -> None:
        result = engine.sql("SELECT DISTINCT field FROM papers")
        fields = [r["field"] for r in result]
        assert len(fields) == len(set(fields))

    def test_distinct_with_order_by(self, engine: Engine) -> None:
        result = engine.sql("SELECT DISTINCT field FROM papers ORDER BY field")
        fields = [r["field"] for r in result]
        assert fields == sorted(fields)
        assert len(fields) == len(set(fields))

    def test_distinct_multiple_columns(self, engine: Engine) -> None:
        result = engine.sql("SELECT DISTINCT field, year FROM papers")
        pairs = [(r["field"], r["year"]) for r in result]
        assert len(pairs) == len(set(pairs))

    def test_distinct_preserves_all_unique_rows(self, engine: Engine) -> None:
        all_result = engine.sql("SELECT year FROM papers")
        distinct_result = engine.sql("SELECT DISTINCT year FROM papers")
        all_years = {r["year"] for r in all_result}
        distinct_years = {r["year"] for r in distinct_result}
        assert all_years == distinct_years


# ==================================================================
# Edge cases
# ==================================================================


class TestEdgeCases:
    def test_no_where_clause(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM papers")
        assert len(result) == 5

    def test_filtered_aggregate(self, engine: Engine) -> None:
        result = engine.sql("SELECT COUNT(*) AS cnt FROM papers WHERE year >= 2020")
        assert result.rows[0]["cnt"] == 2

    def test_knn_wrong_arg_count_raises(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="requires 3 arguments"):
            engine.sql("SELECT * FROM papers WHERE knn_match(ARRAY[1.0, 2.0], 5)")

    def test_unsupported_statement(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unsupported statement"):
            engine.sql("LISTEN channel")

    def test_unknown_function(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unknown scalar function"):
            engine.sql("SELECT * FROM papers WHERE unknown_func(title, 'test')")


# ==================================================================
# Hybrid queries: fusion of text + vector + graph + filter
# ==================================================================


@pytest.fixture
def hybrid_engine() -> Engine:
    """Engine with table, graph, and vector data for hybrid queries."""
    e = Engine()
    e.sql("""
        CREATE TABLE papers (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            field TEXT,
            embedding VECTOR(8)
        )
    """)

    rng = np.random.RandomState(42)
    base = rng.randn(8).astype(np.float32)
    base /= np.linalg.norm(base)

    titles = [
        ("attention is all you need", 2017, "nlp"),
        ("bert pre-training", 2019, "nlp"),
        ("graph attention networks", 2018, "graph"),
        ("vision transformer", 2021, "cv"),
        ("scaling language models", 2020, "nlp"),
    ]
    for title, year, fld in titles:
        emb = base + rng.randn(8).astype(np.float32) * 0.3
        emb = (emb / np.linalg.norm(emb)).astype(np.float32)
        arr_str = "ARRAY[" + ",".join(str(float(v)) for v in emb) + "]"
        e.sql(
            f"INSERT INTO papers (title, year, field, embedding) "
            f"VALUES ('{title}', {year}, '{fld}', {arr_str})"
        )

    e.add_graph_edge(Edge(1, 1, 2, "cited_by"), table="papers")
    e.add_graph_edge(Edge(2, 1, 3, "cited_by"), table="papers")
    e.add_graph_edge(Edge(3, 1, 4, "cited_by"), table="papers")
    e.add_graph_edge(Edge(4, 2, 4, "cited_by"), table="papers")

    return e


class TestTraverseMatch:
    def test_traverse_match_basic(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT _doc_id, _score FROM papers
            WHERE traverse_match(1, 'cited_by', 1)
        """)
        doc_ids = {r["_doc_id"] for r in result}
        # 1-hop from vertex 1: reaches 1, 2, 3, 4
        assert 1 in doc_ids
        assert 2 in doc_ids
        assert 3 in doc_ids

    def test_traverse_match_score(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT _doc_id, _score FROM papers
            WHERE traverse_match(1, 'cited_by', 1)
        """)
        for row in result:
            assert row["_score"] == pytest.approx(0.9)


class TestFusionLogOdds:
    def test_fuse_two_signals(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            )
            ORDER BY _score DESC
        """)
        assert len(result) > 0
        # All scores must be calibrated probabilities in (0, 1)
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_text_uses_bayesian(self, hybrid_engine: Engine) -> None:
        """text_match inside fusion is compiled as bayesian_match."""
        result = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 1)
            )
            ORDER BY _score DESC
        """)
        # Papers with "attention" AND reachable should score highest
        titles = [r["title"] for r in result]
        top = titles[0]
        assert "attention" in top

    def test_fuse_with_alpha(self, hybrid_engine: Engine) -> None:
        r1 = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2),
                0.3
            )
            ORDER BY _score DESC
        """)
        r2 = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2),
                0.8
            )
            ORDER BY _score DESC
        """)
        # Different alpha should produce different scores
        scores_1 = [r["_score"] for r in r1]
        scores_2 = [r["_score"] for r in r2]
        assert scores_1 != scores_2

    def test_fuse_with_filter(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT title, year, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            ) AND year >= 2018
            ORDER BY _score DESC
        """)
        for row in result:
            assert row["year"] >= 2018

    def test_fuse_three_signals(self, hybrid_engine: Engine) -> None:
        rng = np.random.RandomState(42)
        qv = rng.randn(8).astype(np.float32)
        qv /= np.linalg.norm(qv)

        result = hybrid_engine.sql(
            """
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                text_match(title, 'attention'),
                knn_match(embedding, $1, 5),
                traverse_match(1, 'cited_by', 1)
            )
            ORDER BY _score DESC
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_in_fusion(self, hybrid_engine: Engine) -> None:
        """knn_match inside fusion applies P = (1 + cosine_sim) / 2."""
        rng = np.random.RandomState(42)
        qv = rng.randn(8).astype(np.float32)
        qv /= np.linalg.norm(qv)

        result = hybrid_engine.sql(
            """
            SELECT title, _score FROM papers
            WHERE fuse_log_odds(
                bayesian_match(title, 'attention'),
                knn_match(embedding, $1, 5)
            )
            ORDER BY _score DESC
        """,
            params=[qv],
        )
        for row in result:
            assert 0.0 < row["_score"] < 1.0


class TestFusionProbBoolean:
    def test_fuse_prob_and(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_prob_and(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            )
            ORDER BY _score DESC
        """)
        assert len(result) > 0
        for row in result:
            assert 0.0 <= row["_score"] <= 1.0

    def test_fuse_prob_or(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_prob_or(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            )
            ORDER BY _score DESC
        """)
        assert len(result) > 0
        for row in result:
            assert 0.0 <= row["_score"] <= 1.0

    def test_fuse_prob_not(self, hybrid_engine: Engine) -> None:
        result = hybrid_engine.sql("""
            SELECT title, _score FROM papers
            WHERE fuse_prob_not(
                text_match(title, 'attention')
            )
            ORDER BY _score DESC
        """)
        assert len(result) > 0
        for row in result:
            assert 0.0 <= row["_score"] <= 1.0
        # Papers WITHOUT "attention" should score highest (close to 1.0)
        scores = {r["title"]: r["_score"] for r in result}
        assert scores["scaling language models"] > scores["attention is all you need"]

    def test_prob_and_less_than_prob_or(self, hybrid_engine: Engine) -> None:
        """P(A AND B) <= P(A OR B) for all documents."""
        r_and = hybrid_engine.sql("""
            SELECT _doc_id, _score FROM papers
            WHERE fuse_prob_and(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            )
        """)
        r_or = hybrid_engine.sql("""
            SELECT _doc_id, _score FROM papers
            WHERE fuse_prob_or(
                text_match(title, 'attention'),
                traverse_match(1, 'cited_by', 2)
            )
        """)
        and_map = {r["_doc_id"]: r["_score"] for r in r_and}
        or_map = {r["_doc_id"]: r["_score"] for r in r_or}
        for doc_id in and_map:
            if doc_id in or_map:
                assert and_map[doc_id] <= or_map[doc_id] + 1e-9


class TestFusionErrors:
    def test_fusion_needs_two_signals(self, hybrid_engine: Engine) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            hybrid_engine.sql("""
                SELECT * FROM papers
                WHERE fuse_log_odds(text_match(title, 'attention'))
            """)

    def test_prob_not_needs_one_signal(self, hybrid_engine: Engine) -> None:
        with pytest.raises(ValueError, match="exactly 1"):
            hybrid_engine.sql("""
                SELECT * FROM papers
                WHERE fuse_prob_not(
                    text_match(title, 'attention'),
                    traverse_match(1, 'cited_by', 1)
                )
            """)

    def test_fusion_unknown_signal(self, hybrid_engine: Engine) -> None:
        with pytest.raises(ValueError, match="Unknown signal function"):
            hybrid_engine.sql("""
                SELECT * FROM papers
                WHERE fuse_log_odds(
                    text_match(title, 'attention'),
                    some_func(title, 'test')
                )
            """)


# ==================================================================
# SQL integration: hierarchical path functions
# ==================================================================


class TestSQLPathFunctions:
    """Tests for path_agg, path_value, and path_filter SQL functions."""

    @pytest.fixture
    def order_engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE orders (id INTEGER PRIMARY KEY, data TEXT)")
        e.add_document(
            1,
            {
                "order_id": "ORD-001",
                "customer": "Alice",
                "items": [
                    {"name": "Widget A", "price": 29.99, "quantity": 2},
                    {"name": "Widget B", "price": 49.99, "quantity": 1},
                ],
                "shipping": {"city": "Seoul", "method": "express", "cost": 15.0},
            },
            table="orders",
        )
        e.add_document(
            2,
            {
                "order_id": "ORD-002",
                "customer": "Bob",
                "items": [
                    {"name": "Gadget X", "price": 99.99, "quantity": 1},
                ],
                "shipping": {"city": "Busan", "method": "standard", "cost": 5.0},
            },
            table="orders",
        )
        e.add_document(
            3,
            {
                "order_id": "ORD-003",
                "customer": "Charlie",
                "items": [
                    {"name": "Widget A", "price": 29.99, "quantity": 3},
                    {"name": "Gadget X", "price": 99.99, "quantity": 2},
                    {"name": "Part Z", "price": 9.99, "quantity": 10},
                ],
                "shipping": {"city": "Seoul", "method": "express", "cost": 20.0},
            },
            table="orders",
        )
        return e

    # -- path_agg --

    def test_path_agg_sum(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_agg('items.price', 'sum') AS total FROM orders"
        )
        assert len(result.rows) == 3
        totals = sorted(r["total"] for r in result.rows)
        assert abs(totals[0] - 79.98) < 0.01  # ORD-001: 29.99 + 49.99
        assert abs(totals[1] - 99.99) < 0.01  # ORD-002: 99.99
        assert abs(totals[2] - 139.97) < 0.01  # ORD-003: 29.99 + 99.99 + 9.99

    def test_path_agg_count(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_agg('items.name', 'count') AS n FROM orders"
        )
        counts = sorted(r["n"] for r in result.rows)
        assert counts == [1, 2, 3]

    def test_path_agg_avg(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_agg('items.price', 'avg') AS avg_price FROM orders"
        )
        avgs = sorted(r["avg_price"] for r in result.rows)
        assert abs(avgs[0] - 39.99) < 0.01  # ORD-001: (29.99+49.99)/2
        assert abs(avgs[2] - 99.99) < 0.01  # ORD-002: 99.99/1

    def test_path_agg_min_max(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_agg('items.price', 'min') AS lo, "
            "path_agg('items.price', 'max') AS hi FROM orders"
        )
        assert len(result.rows) == 3
        for row in result.rows:
            assert row["lo"] <= row["hi"]

    # -- path_value --

    def test_path_value_scalar(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_value('shipping.city') AS city FROM orders"
        )
        cities = sorted(r["city"] for r in result.rows)
        assert cities == ["Busan", "Seoul", "Seoul"]

    def test_path_value_nested(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_value('shipping.cost') AS cost FROM orders"
        )
        costs = sorted(r["cost"] for r in result.rows)
        assert costs == [5.0, 15.0, 20.0]

    # -- path_filter in WHERE --

    def test_path_filter_equality(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT * FROM orders WHERE path_filter('shipping.city', 'Seoul')"
        )
        assert len(result.rows) == 2
        customers = sorted(r["customer"] for r in result.rows)
        assert customers == ["Alice", "Charlie"]

    def test_path_filter_with_operator(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT * FROM orders WHERE path_filter('shipping.cost', '>', 10)"
        )
        assert len(result.rows) == 2
        customers = sorted(r["customer"] for r in result.rows)
        assert customers == ["Alice", "Charlie"]

    def test_path_filter_array_any_match(self, order_engine: Engine) -> None:
        """path_filter on an array field should match if ANY element matches."""
        result = order_engine.sql(
            "SELECT * FROM orders WHERE path_filter('items.name', 'Widget A')"
        )
        assert len(result.rows) == 2
        customers = sorted(r["customer"] for r in result.rows)
        assert customers == ["Alice", "Charlie"]

    def test_path_filter_combined_with_path_agg(self, order_engine: Engine) -> None:
        result = order_engine.sql(
            "SELECT path_agg('items.price', 'sum') AS total FROM orders "
            "WHERE path_filter('shipping.city', 'Seoul')"
        )
        assert len(result.rows) == 2
        totals = sorted(r["total"] for r in result.rows)
        assert abs(totals[0] - 79.98) < 0.01
        assert abs(totals[1] - 139.97) < 0.01


# ==================================================================
# SQL integration: graph aggregates via standard SQL
# ==================================================================


class TestSQLGraphAggregates:
    """Standard SQL aggregates should work on graph traversal results."""

    @pytest.fixture
    def graph_engine(self) -> Engine:
        e = Engine()
        e.sql(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, role TEXT, salary INTEGER)"
        )
        # Build org chart: CEO -> VP -> Engineers
        e.add_graph_vertex(
            Vertex(1, "", {"name": "CEO", "role": "executive", "salary": 200000}),
            table="employees",
        )
        e.add_graph_vertex(
            Vertex(2, "", {"name": "VP-Eng", "role": "vp", "salary": 150000}),
            table="employees",
        )
        e.add_graph_vertex(
            Vertex(3, "", {"name": "VP-Sales", "role": "vp", "salary": 140000}),
            table="employees",
        )
        e.add_graph_vertex(
            Vertex(4, "", {"name": "Alice", "role": "engineer", "salary": 120000}),
            table="employees",
        )
        e.add_graph_vertex(
            Vertex(5, "", {"name": "Bob", "role": "engineer", "salary": 110000}),
            table="employees",
        )
        e.add_graph_vertex(
            Vertex(6, "", {"name": "Carol", "role": "sales", "salary": 100000}),
            table="employees",
        )

        e.add_graph_edge(Edge(1, 1, 2, "manages"), table="employees")
        e.add_graph_edge(Edge(2, 1, 3, "manages"), table="employees")
        e.add_graph_edge(Edge(3, 2, 4, "manages"), table="employees")
        e.add_graph_edge(Edge(4, 2, 5, "manages"), table="employees")
        e.add_graph_edge(Edge(5, 3, 6, "manages"), table="employees")
        return e

    def test_sum_from_traverse(self, graph_engine: Engine) -> None:
        result = graph_engine.sql(
            "SELECT SUM(salary) AS total FROM traverse(1, 'manages', 1, 'employees')"
        )
        assert len(result.rows) == 1
        # CEO (200k) + VP-Eng (150k) + VP-Sales (140k) = 490k (includes start)
        assert result.rows[0]["total"] == 490000

    def test_avg_from_traverse(self, graph_engine: Engine) -> None:
        result = graph_engine.sql(
            "SELECT AVG(salary) AS avg_salary FROM traverse(2, 'manages', 1, 'employees')"
        )
        assert len(result.rows) == 1
        # VP-Eng (150k) + Alice (120k) + Bob (110k) -> avg = 126666.67
        avg = result.rows[0]["avg_salary"]
        assert abs(avg - 126666.67) < 1.0

    def test_count_from_traverse(self, graph_engine: Engine) -> None:
        result = graph_engine.sql(
            "SELECT COUNT(*) AS cnt FROM traverse(1, 'manages', 2, 'employees')"
        )
        assert len(result.rows) == 1
        # CEO + 2 VPs + 2 engineers + 1 sales = 6 (all reachable within 2 hops)
        assert result.rows[0]["cnt"] == 6

    def test_group_by_from_traverse(self, graph_engine: Engine) -> None:
        result = graph_engine.sql(
            "SELECT role, COUNT(*) AS cnt FROM traverse(1, 'manages', 2, 'employees') GROUP BY role"
        )
        role_counts = {r["role"]: r["cnt"] for r in result.rows}
        assert role_counts["executive"] == 1
        assert role_counts["vp"] == 2
        assert role_counts["engineer"] == 2
        assert role_counts["sales"] == 1

    def test_select_star_from_traverse(self, graph_engine: Engine) -> None:
        result = graph_engine.sql(
            "SELECT * FROM traverse(2, 'manages', 1, 'employees')"
        )
        # VP-Eng + Alice + Bob = 3 (includes start vertex)
        assert len(result.rows) == 3
        names = sorted(r["name"] for r in result.rows)
        assert names == ["Alice", "Bob", "VP-Eng"]

    def test_rpq_query(self, graph_engine: Engine) -> None:
        result = graph_engine.sql("SELECT * FROM rpq('manages*', 1, 'employees')")
        # Kleene star: all reachable from CEO via manages (including CEO)
        assert len(result.rows) >= 5


# ==================================================================
# REGEXP_SPLIT_TO_TABLE
# ==================================================================


class TestRegexpSplitToTable:
    def test_basic_split(self) -> None:
        e = Engine()
        result = e.sql(
            "SELECT * FROM regexp_split_to_table('hello world foo', '\\s+') AS t(word)"
        )
        words = [r["word"] for r in result.rows]
        assert words == ["hello", "world", "foo"]

    def test_comma_split(self) -> None:
        e = Engine()
        result = e.sql("SELECT * FROM regexp_split_to_table('a,b,c', ',') AS t(item)")
        items = [r["item"] for r in result.rows]
        assert items == ["a", "b", "c"]

    def test_empty_parts(self) -> None:
        e = Engine()
        result = e.sql("SELECT * FROM regexp_split_to_table('a,,b', ',') AS t(v)")
        vals = [r["v"] for r in result.rows]
        assert vals == ["a", "", "b"]

    def test_flags_case_insensitive(self) -> None:
        e = Engine()
        result = e.sql(
            "SELECT * FROM regexp_split_to_table('AXbXc', 'x', 'i') AS t(part)"
        )
        parts = [r["part"] for r in result.rows]
        assert parts == ["A", "b", "c"]

    def test_default_column_name(self) -> None:
        e = Engine()
        result = e.sql(
            "SELECT regexp_split_to_table FROM regexp_split_to_table('a-b', '-')"
        )
        vals = [r["regexp_split_to_table"] for r in result.rows]
        assert vals == ["a", "b"]


# ==================================================================
# CORR / COVAR_POP / COVAR_SAMP
# ==================================================================


class TestCovarianceCorrelation:
    @pytest.fixture
    def stats_engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE xy (x REAL, y REAL)")
        # y = 2x, perfect linear relationship
        e.sql("INSERT INTO xy VALUES (1, 2), (2, 4), (3, 6), (4, 8), (5, 10)")
        return e

    def test_corr_perfect(self, stats_engine: Engine) -> None:
        r = stats_engine.sql("SELECT corr(y, x) AS c FROM xy")
        assert abs(r.rows[0]["c"] - 1.0) < 1e-10

    def test_covar_pop(self, stats_engine: Engine) -> None:
        r = stats_engine.sql("SELECT covar_pop(y, x) AS cp FROM xy")
        assert abs(r.rows[0]["cp"] - 4.0) < 1e-10

    def test_covar_samp(self, stats_engine: Engine) -> None:
        r = stats_engine.sql("SELECT covar_samp(y, x) AS cs FROM xy")
        assert abs(r.rows[0]["cs"] - 5.0) < 1e-10

    def test_corr_constant_returns_null(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE c (x REAL, y REAL)")
        e.sql("INSERT INTO c VALUES (1, 5), (2, 5), (3, 5)")
        r = e.sql("SELECT corr(y, x) AS c FROM c")
        assert r.rows[0]["c"] is None

    def test_covar_samp_single_row(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE s (x REAL, y REAL)")
        e.sql("INSERT INTO s VALUES (1, 2)")
        r = e.sql("SELECT covar_samp(y, x) AS cs FROM s")
        assert r.rows[0]["cs"] is None


# ==================================================================
# REGR_* regression functions
# ==================================================================


class TestRegressionFunctions:
    @pytest.fixture
    def regr_engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE pts (x REAL, y REAL)")
        # y = 2x + 1
        e.sql("INSERT INTO pts VALUES (1, 3), (2, 5), (3, 7), (4, 9), (5, 11)")
        return e

    def test_regr_count(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_count(y, x) AS rc FROM pts")
        assert r.rows[0]["rc"] == 5

    def test_regr_avgx(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_avgx(y, x) AS ax FROM pts")
        assert abs(r.rows[0]["ax"] - 3.0) < 1e-10

    def test_regr_avgy(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_avgy(y, x) AS ay FROM pts")
        assert abs(r.rows[0]["ay"] - 7.0) < 1e-10

    def test_regr_slope(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_slope(y, x) AS s FROM pts")
        assert abs(r.rows[0]["s"] - 2.0) < 1e-10

    def test_regr_intercept(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_intercept(y, x) AS i FROM pts")
        assert abs(r.rows[0]["i"] - 1.0) < 1e-10

    def test_regr_r2(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_r2(y, x) AS r2 FROM pts")
        assert abs(r.rows[0]["r2"] - 1.0) < 1e-10

    def test_regr_sxx(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_sxx(y, x) AS sxx FROM pts")
        assert abs(r.rows[0]["sxx"] - 10.0) < 1e-10

    def test_regr_syy(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_syy(y, x) AS syy FROM pts")
        assert abs(r.rows[0]["syy"] - 40.0) < 1e-10

    def test_regr_sxy(self, regr_engine: Engine) -> None:
        r = regr_engine.sql("SELECT regr_sxy(y, x) AS sxy FROM pts")
        assert abs(r.rows[0]["sxy"] - 20.0) < 1e-10

    def test_regr_slope_constant_x_null(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE cx (x REAL, y REAL)")
        e.sql("INSERT INTO cx VALUES (5, 1), (5, 2), (5, 3)")
        r = e.sql("SELECT regr_slope(y, x) AS s FROM cx")
        assert r.rows[0]["s"] is None

    def test_regr_r2_constant_y_null(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE cy (x REAL, y REAL)")
        e.sql("INSERT INTO cy VALUES (1, 5), (2, 5), (3, 5)")
        r = e.sql("SELECT regr_r2(y, x) AS r2 FROM cy")
        assert r.rows[0]["r2"] is None


# ==================================================================
# pg_catalog.pg_type
# ==================================================================


class TestPgType:
    def test_pg_type_exists(self) -> None:
        e = Engine()
        r = e.sql("SELECT COUNT(*) AS cnt FROM pg_catalog.pg_type")
        assert r.rows[0]["cnt"] >= 18

    def test_pg_type_integer_oid(self) -> None:
        e = Engine()
        r = e.sql(
            "SELECT oid, typlen FROM pg_catalog.pg_type WHERE typname = 'integer'"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["oid"] == 23
        assert r.rows[0]["typlen"] == 4

    def test_pg_type_text(self) -> None:
        e = Engine()
        r = e.sql(
            "SELECT oid, typcategory FROM pg_catalog.pg_type WHERE typname = 'text'"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["oid"] == 25
        assert r.rows[0]["typcategory"] == "S"

    def test_pg_type_numeric_category(self) -> None:
        e = Engine()
        r = e.sql(
            "SELECT typname FROM pg_catalog.pg_type "
            "WHERE typcategory = 'N' ORDER BY oid"
        )
        names = [row["typname"] for row in r.rows]
        assert "integer" in names
        assert "real" in names
        assert "numeric" in names


# ==================================================================
# ALTER SEQUENCE
# ==================================================================


class TestAlterSequence:
    def test_restart_with_value(self) -> None:
        e = Engine()
        e.sql("CREATE SEQUENCE seq1 START 1 INCREMENT 1")
        e.sql("SELECT nextval('seq1')")
        e.sql("SELECT nextval('seq1')")
        e.sql("ALTER SEQUENCE seq1 RESTART WITH 10")
        r = e.sql("SELECT nextval('seq1') AS v")
        assert r.rows[0]["v"] == 10

    def test_restart_without_value(self) -> None:
        e = Engine()
        e.sql("CREATE SEQUENCE seq2 START 5 INCREMENT 1")
        e.sql("SELECT nextval('seq2')")
        e.sql("SELECT nextval('seq2')")
        e.sql("ALTER SEQUENCE seq2 RESTART")
        r = e.sql("SELECT nextval('seq2') AS v")
        assert r.rows[0]["v"] == 5

    def test_alter_increment(self) -> None:
        e = Engine()
        e.sql("CREATE SEQUENCE seq3 START 1 INCREMENT 1")
        e.sql("ALTER SEQUENCE seq3 INCREMENT BY 3")
        e.sql("ALTER SEQUENCE seq3 RESTART")
        r = e.sql("SELECT nextval('seq3') AS v")
        assert r.rows[0]["v"] == 1
        r = e.sql("SELECT nextval('seq3') AS v")
        assert r.rows[0]["v"] == 4

    def test_alter_nonexistent_sequence_raises(self) -> None:
        e = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("ALTER SEQUENCE nosuchseq RESTART")

    def test_alter_start(self) -> None:
        e = Engine()
        e.sql("CREATE SEQUENCE seq4 START 1 INCREMENT 1")
        e.sql("ALTER SEQUENCE seq4 START WITH 100")
        # START only affects what RESTART (without value) uses
        e.sql("ALTER SEQUENCE seq4 RESTART")
        r = e.sql("SELECT nextval('seq4') AS v")
        assert r.rows[0]["v"] == 100


# ==================================================================
# TABLE name (shorthand for SELECT * FROM name)
# ==================================================================


class TestTableShorthand:
    def test_table_returns_all_rows(self) -> None:
        e = Engine()
        e.sql("CREATE TABLE t1 (id INTEGER, name TEXT)")
        e.sql("INSERT INTO t1 VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        r = e.sql("TABLE t1")
        assert len(r.rows) == 3
        names = sorted(row["name"] for row in r.rows)
        assert names == ["a", "b", "c"]


# ==================================================================
# Fixtures for appended PG17 test classes
# ==================================================================


@pytest.fixture
def pg17_engine():
    return Engine()


@pytest.fixture
def engine_with_data(pg17_engine):
    pg17_engine.sql("CREATE TABLE users (id INTEGER, name TEXT, age INTEGER)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (3, 'Carol', 35)")
    pg17_engine.sql("INSERT INTO users (id, name, age) VALUES (4, 'Dave', 25)")
    return pg17_engine


@pytest.fixture
def engine_with_table(pg17_engine):
    pg17_engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER, name TEXT)")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (1, 10, 'alpha')")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (2, 20, 'bravo')")
    pg17_engine.sql("INSERT INTO t (id, val, name) VALUES (3, 30, 'charlie')")
    return pg17_engine


# ==================================================================
# CREATE TABLE IF NOT EXISTS
# ==================================================================


class TestCreateTableIfNotExists:
    def test_basic_if_not_exists(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER)")
        # Should not raise
        result = pg17_engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        assert result.rows == []
        assert result.columns == []

    def test_if_not_exists_returns_empty(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER)")
        result = pg17_engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        assert result.rows == []

    def test_without_if_not_exists_raises(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER)")
        with pytest.raises(ValueError, match="already exists"):
            pg17_engine.sql("CREATE TABLE t (id INTEGER)")

    def test_if_not_exists_preserves_data(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        pg17_engine.sql("INSERT INTO t (id, val) VALUES (1, 'hello')")
        pg17_engine.sql("CREATE TABLE IF NOT EXISTS t (id INTEGER, val TEXT)")
        result = pg17_engine.sql("SELECT val FROM t WHERE id = 1")
        assert result.rows[0]["val"] == "hello"


# ==================================================================
# NULLS FIRST / NULLS LAST
# ==================================================================


class TestNullsOrdering:
    @pytest.fixture
    def null_data(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t (id INTEGER, val INTEGER)")
        pg17_engine.sql("INSERT INTO t (id, val) VALUES (1, 10)")
        pg17_engine.sql("INSERT INTO t (id, val) VALUES (2, 20)")
        pg17_engine.sql("INSERT INTO t (id) VALUES (3)")  # val is NULL
        pg17_engine.sql("INSERT INTO t (id, val) VALUES (4, 5)")
        return pg17_engine

    def test_nulls_first_asc(self, null_data):
        result = null_data.sql("SELECT id, val FROM t ORDER BY val ASC NULLS FIRST")
        vals = [r["val"] for r in result.rows]
        assert vals[0] is None
        assert vals[1:] == [5, 10, 20]

    def test_nulls_last_asc(self, null_data):
        result = null_data.sql("SELECT id, val FROM t ORDER BY val ASC NULLS LAST")
        vals = [r["val"] for r in result.rows]
        assert vals[-1] is None
        assert vals[:-1] == [5, 10, 20]

    def test_nulls_first_desc(self, null_data):
        result = null_data.sql("SELECT id, val FROM t ORDER BY val DESC NULLS FIRST")
        vals = [r["val"] for r in result.rows]
        assert vals[0] is None
        assert vals[1:] == [20, 10, 5]

    def test_nulls_last_desc(self, null_data):
        result = null_data.sql("SELECT id, val FROM t ORDER BY val DESC NULLS LAST")
        vals = [r["val"] for r in result.rows]
        assert vals[-1] is None
        assert vals[:-1] == [20, 10, 5]

    def test_default_nulls_last(self, null_data):
        result = null_data.sql("SELECT id, val FROM t ORDER BY val ASC")
        vals = [r["val"] for r in result.rows]
        # Default: NULLs last for ASC
        assert vals[-1] is None


# ==================================================================
# Column alias in ORDER BY
# ==================================================================


class TestColumnAliasOrderBy:
    def test_order_by_alias(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age AS user_age FROM users ORDER BY user_age DESC"
        )
        ages = [r["user_age"] for r in result.rows]
        assert ages == [35, 30, 25, 25]

    def test_order_by_ordinal(self, engine_with_data):
        result = engine_with_data.sql("SELECT name, age FROM users ORDER BY 2 ASC")
        ages = [r["age"] for r in result.rows]
        assert ages == [25, 25, 30, 35]

    def test_order_by_ordinal_desc(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age FROM users ORDER BY 2 DESC, 1 ASC"
        )
        names = [r["name"] for r in result.rows]
        assert names[0] == "Carol"  # age 35
        assert names[-1] in ("Bob", "Dave")  # age 25

    def test_order_by_invalid_ordinal(self, engine_with_data):
        with pytest.raises(ValueError, match="not in select list"):
            engine_with_data.sql("SELECT name FROM users ORDER BY 5")


# ==================================================================
# INSERT INTO ... SELECT
# ==================================================================


class TestInsertSelect:
    def test_insert_select_basic(self, engine_with_data):
        engine_with_data.sql(
            "CREATE TABLE users_copy (id INTEGER, name TEXT, age INTEGER)"
        )
        result = engine_with_data.sql(
            "INSERT INTO users_copy (id, name, age) SELECT id, name, age FROM users"
        )
        assert result.rows[0]["inserted"] == 4

        result = engine_with_data.sql("SELECT COUNT(*) AS cnt FROM users_copy")
        assert result.rows[0]["cnt"] == 4

    def test_insert_select_with_where(self, engine_with_data):
        engine_with_data.sql("CREATE TABLE young (id INTEGER, name TEXT, age INTEGER)")
        engine_with_data.sql(
            "INSERT INTO young (id, name, age) "
            "SELECT id, name, age FROM users WHERE age < 30"
        )
        result = engine_with_data.sql("SELECT COUNT(*) AS cnt FROM young")
        assert result.rows[0]["cnt"] == 2

    def test_insert_select_with_columns(self, engine_with_data):
        engine_with_data.sql("CREATE TABLE names (name TEXT)")
        engine_with_data.sql("INSERT INTO names (name) SELECT name FROM users")
        result = engine_with_data.sql("SELECT COUNT(*) AS cnt FROM names")
        assert result.rows[0]["cnt"] == 4

    def test_insert_select_empty(self, engine_with_data):
        engine_with_data.sql("CREATE TABLE empty (id INTEGER, name TEXT, age INTEGER)")
        result = engine_with_data.sql(
            "INSERT INTO empty (id, name, age) "
            "SELECT id, name, age FROM users WHERE age > 100"
        )
        assert result.rows[0]["inserted"] == 0


# ==================================================================
# Derived tables (subquery in FROM)
# ==================================================================


class TestDerivedTables:
    def test_simple_derived_table(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name, age FROM "
            "(SELECT name, age FROM users WHERE age >= 30) AS older"
        )
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}

    def test_derived_table_with_where(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name FROM (SELECT name, age FROM users) AS t WHERE age = 25"
        )
        names = {r["name"] for r in result.rows}
        assert names == {"Bob", "Dave"}

    def test_derived_table_with_aggregation(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT COUNT(*) AS cnt FROM (SELECT name FROM users WHERE age > 25) AS t"
        )
        assert result.rows[0]["cnt"] == 2

    def test_nested_derived_tables(self, engine_with_data):
        result = engine_with_data.sql(
            "SELECT name FROM "
            "(SELECT name, age FROM "
            " (SELECT name, age FROM users) AS inner_t "
            " WHERE age >= 30"
            ") AS outer_t"
        )
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}


# ==================================================================
# Derived table alias collision
# ==================================================================


class TestDerivedTableAliasCollision:
    def test_alias_does_not_destroy_real_table(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE users (id INTEGER, name TEXT)")
        pg17_engine.sql("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        pg17_engine.sql("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        # Use alias "users" -- same as the real table name
        result = pg17_engine.sql(
            "SELECT name FROM (SELECT id, name FROM users WHERE id = 1) AS users"
        )
        assert result.rows[0]["name"] == "Alice"

        # Real table must still be intact after the query
        result = pg17_engine.sql("SELECT COUNT(*) AS cnt FROM users")
        assert result.rows[0]["cnt"] == 2


# ==================================================================
# UNION / INTERSECT / EXCEPT
# ==================================================================


class TestSetOperations:
    @pytest.fixture
    def two_tables(self, pg17_engine):
        pg17_engine.sql("CREATE TABLE t1 (id INTEGER, val TEXT)")
        pg17_engine.sql("CREATE TABLE t2 (id INTEGER, val TEXT)")
        pg17_engine.sql("INSERT INTO t1 (id, val) VALUES (1, 'a')")
        pg17_engine.sql("INSERT INTO t1 (id, val) VALUES (2, 'b')")
        pg17_engine.sql("INSERT INTO t1 (id, val) VALUES (3, 'c')")
        pg17_engine.sql("INSERT INTO t2 (id, val) VALUES (2, 'b')")
        pg17_engine.sql("INSERT INTO t2 (id, val) VALUES (3, 'c')")
        pg17_engine.sql("INSERT INTO t2 (id, val) VALUES (4, 'd')")
        return pg17_engine

    def test_union_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 UNION ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 6

    def test_union_distinct(self, two_tables):
        result = two_tables.sql("SELECT id, val FROM t1 UNION SELECT id, val FROM t2")
        assert len(result.rows) == 4  # 1a, 2b, 3c, 4d

    def test_intersect(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 INTERSECT SELECT id, val FROM t2"
        )
        assert len(result.rows) == 2  # 2b, 3c

    def test_intersect_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 INTERSECT ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 2

    def test_except(self, two_tables):
        result = two_tables.sql("SELECT id, val FROM t1 EXCEPT SELECT id, val FROM t2")
        assert len(result.rows) == 1
        assert result.rows[0]["val"] == "a"

    def test_except_all(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 EXCEPT ALL SELECT id, val FROM t2"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["val"] == "a"

    def test_union_with_order_by(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 UNION ALL SELECT id, val FROM t2 ORDER BY 1"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == sorted(ids)

    def test_union_with_limit(self, two_tables):
        result = two_tables.sql(
            "SELECT id, val FROM t1 UNION ALL SELECT id, val FROM t2 ORDER BY 1 LIMIT 3"
        )
        assert len(result.rows) == 3

    def test_column_count_mismatch_error(self, two_tables):
        with pytest.raises(ValueError, match="column count mismatch"):
            two_tables.sql("SELECT id, val FROM t1 UNION SELECT id FROM t2")

    def test_chained_union(self, two_tables):
        two_tables.sql("CREATE TABLE t3 (id INTEGER, val TEXT)")
        two_tables.sql("INSERT INTO t3 (id, val) VALUES (5, 'e')")
        result = two_tables.sql(
            "SELECT id, val FROM t1 "
            "UNION ALL SELECT id, val FROM t2 "
            "UNION ALL SELECT id, val FROM t3"
        )
        assert len(result.rows) == 7  # 3 + 3 + 1


# ==================================================================
# CREATE TABLE AS
# ==================================================================


class TestCreateTableAs:
    def test_basic(self, engine_with_table):
        engine_with_table.sql("CREATE TABLE t2 AS SELECT id, val FROM t")
        result = engine_with_table.sql("SELECT id, val FROM t2 ORDER BY id")
        assert len(result.rows) == 3
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["val"] == 10

    def test_with_where(self, engine_with_table):
        engine_with_table.sql("CREATE TABLE t2 AS SELECT id, val FROM t WHERE val > 15")
        result = engine_with_table.sql("SELECT id, val FROM t2 ORDER BY id")
        assert len(result.rows) == 2

    def test_with_expression(self, engine_with_table):
        engine_with_table.sql("CREATE TABLE t2 AS SELECT id, val * 2 AS doubled FROM t")
        result = engine_with_table.sql("SELECT id, doubled FROM t2 ORDER BY id")
        assert result.rows[0]["doubled"] == 20


# ==================================================================
# FETCH FIRST
# ==================================================================


class TestFetchFirst:
    def test_basic(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id, val FROM t ORDER BY id FETCH FIRST 2 ROWS ONLY"
        )
        assert len(result.rows) == 2

    def test_fetch_first_1(self, engine_with_table):
        result = engine_with_table.sql(
            "SELECT id FROM t ORDER BY id FETCH FIRST 1 ROW ONLY"
        )
        assert len(result.rows) == 1


# ==================================================================
# Standalone VALUES
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
# VALUES in INSERT
# ==================================================================


class TestValuesInInsert:
    """Ensure standalone VALUES does not break INSERT INTO ... VALUES."""

    def test_insert_still_works(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INT, val TEXT)")
        e.sql("INSERT INTO t VALUES (1, 'a'), (2, 'b')")
        r = e.sql("SELECT id, val FROM t ORDER BY id")
        assert len(r.rows) == 2
        assert r.rows[0]["id"] == 1
        assert r.rows[0]["val"] == "a"
        assert r.rows[1]["id"] == 2
        assert r.rows[1]["val"] == "b"

    def test_insert_single_row(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
        e.sql("INSERT INTO t VALUES (42, 'answer')")
        r = e.sql("SELECT id, val FROM t")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 42


# ==================================================================
# CREATE TEMPORARY TABLE
# ==================================================================


class TestCreateTemporaryTable:
    def test_basic_temp_table(self):
        e = Engine()
        e.sql("CREATE TEMPORARY TABLE tmp (id INT PRIMARY KEY, val TEXT)")
        e.sql("INSERT INTO tmp VALUES (1, 'hello')")
        r = e.sql("SELECT id, val FROM tmp")
        assert len(r.rows) == 1
        assert r.rows[0]["val"] == "hello"

    def test_temp_table_dropped_on_close(self):
        e = Engine()
        e.sql("CREATE TEMP TABLE tmp (id INT, val TEXT)")
        e.sql("INSERT INTO tmp VALUES (1, 'test')")
        assert "tmp" in e._tables
        e.close()
        assert "tmp" not in e._tables

    def test_temp_table_not_persisted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE perm (id INT PRIMARY KEY)")
            e.sql("CREATE TEMP TABLE tmp (id INT PRIMARY KEY)")
            e.sql("INSERT INTO perm VALUES (1)")
            e.sql("INSERT INTO tmp VALUES (1)")
            e.close()

            # Re-open: permanent table should exist, temp should not
            e2 = Engine(db_path=db_path)
            r = e2.sql("SELECT id FROM perm")
            assert len(r.rows) == 1
            with pytest.raises(ValueError, match="does not exist"):
                e2.sql("SELECT id FROM tmp")
            e2.close()

    def test_temp_table_create_as_select(self):
        e = Engine()
        e.sql("CREATE TABLE src (id INT PRIMARY KEY, val INT)")
        e.sql("INSERT INTO src VALUES (1, 10)")
        e.sql("INSERT INTO src VALUES (2, 20)")
        e.sql("CREATE TEMP TABLE tmp AS SELECT id, val FROM src WHERE val > 10")
        r = e.sql("SELECT id, val FROM tmp")
        assert len(r.rows) == 1
        assert r.rows[0]["val"] == 20

    def test_temp_table_insert_and_query(self):
        """Temp tables support normal DML operations."""
        e = Engine()
        e.sql("CREATE TEMPORARY TABLE staging (id INT PRIMARY KEY, status TEXT)")
        e.sql("INSERT INTO staging VALUES (1, 'pending')")
        e.sql("INSERT INTO staging VALUES (2, 'done')")
        e.sql("UPDATE staging SET status = 'done' WHERE id = 1")
        r = e.sql("SELECT id, status FROM staging ORDER BY id")
        assert r.rows[0]["status"] == "done"
        assert r.rows[1]["status"] == "done"
