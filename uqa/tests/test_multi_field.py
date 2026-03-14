#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import IndexStats
from uqa.engine import Engine
from uqa.scoring.bayesian_bm25 import BayesianBM25Params
from uqa.scoring.multi_field import MultiFieldBayesianScorer


class TestMultiFieldBayesianScorer:
    """Tests for MultiFieldBayesianScorer (Paper 3, Section 12.2 #1)."""

    def test_single_field(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        scorer = MultiFieldBayesianScorer([("title", BayesianBM25Params(), 1.0)], stats)
        score = scorer.score_document(
            1,
            term_freq_per_field={"title": 3},
            doc_length_per_field={"title": 10},
            doc_freq_per_field={"title": 10},
        )
        assert 0.0 < score < 1.0

    def test_two_fields_higher_than_one(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        scorer = MultiFieldBayesianScorer(
            [
                ("title", BayesianBM25Params(), 1.0),
                ("body", BayesianBM25Params(), 0.5),
            ],
            stats,
        )
        one_field = scorer.score_document(
            1,
            term_freq_per_field={"title": 3, "body": 0},
            doc_length_per_field={"title": 10, "body": 100},
            doc_freq_per_field={"title": 10, "body": 50},
        )
        two_fields = scorer.score_document(
            1,
            term_freq_per_field={"title": 3, "body": 5},
            doc_length_per_field={"title": 10, "body": 100},
            doc_freq_per_field={"title": 10, "body": 50},
        )
        assert two_fields > one_field

    def test_zero_tf_gives_neutral(self) -> None:
        stats = IndexStats(total_docs=100, avg_doc_length=10.0)
        scorer = MultiFieldBayesianScorer([("title", BayesianBM25Params(), 1.0)], stats)
        score = scorer.score_document(
            1,
            term_freq_per_field={"title": 0},
            doc_length_per_field={"title": 10},
            doc_freq_per_field={"title": 10},
        )
        assert score == pytest.approx(0.5, abs=0.01)


class TestMultiFieldSearchOperator:
    """Tests for MultiFieldSearchOperator."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, body TEXT)")
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('machine learning guide', 'intro to ML algorithms')"
        )
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('database systems', 'indexing and learning structures')"
        )
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('cooking recipes', 'delicious pasta dishes')"
        )
        return e

    def test_multi_field_search_returns_results(self, engine: Engine) -> None:
        from uqa.operators.multi_field import MultiFieldSearchOperator

        ctx = engine._context_for_table("docs")
        op = MultiFieldSearchOperator(["title", "body"], "learning")
        result = op.execute(ctx)
        assert len(result) > 0

    def test_multi_field_scores_are_probabilities(self, engine: Engine) -> None:
        from uqa.operators.multi_field import MultiFieldSearchOperator

        ctx = engine._context_for_table("docs")
        op = MultiFieldSearchOperator(["title", "body"], "learning")
        result = op.execute(ctx)
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0

    def test_multi_field_with_weights(self, engine: Engine) -> None:
        from uqa.operators.multi_field import MultiFieldSearchOperator

        ctx = engine._context_for_table("docs")
        op = MultiFieldSearchOperator(["title", "body"], "learning", weights=[2.0, 0.5])
        result = op.execute(ctx)
        assert len(result) > 0

    def test_cost_estimate(self) -> None:
        from uqa.operators.multi_field import MultiFieldSearchOperator

        op = MultiFieldSearchOperator(["title", "body"], "test")
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost == pytest.approx(200.0)


class TestMultiFieldSQL:
    """Tests for multi_field_match via SQL."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, body TEXT)")
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('machine learning', 'algorithms for ML')"
        )
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('cooking recipes', 'pasta and pizza')"
        )
        return e

    def test_multi_field_match_sql(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE multi_field_match(title, body, 'learning')"
        )
        assert result is not None

    def test_multi_field_match_with_weights(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT * FROM docs WHERE "
            "multi_field_match(title, body, 'learning', 2.0, 0.5)"
        )
        assert result is not None

    def test_multi_field_match_too_few_args(self, engine: Engine) -> None:
        with pytest.raises(ValueError):
            engine.sql("SELECT * FROM docs WHERE multi_field_match(title, 'learning')")


class TestMultiFieldQueryBuilder:
    """Tests for QueryBuilder.score_multi_field_bayesian."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, body TEXT)")
        e.sql(
            "INSERT INTO docs (title, body) VALUES "
            "('machine learning', 'algorithms for ML')"
        )
        return e

    def test_query_builder_multi_field(self, engine: Engine) -> None:
        result = (
            engine.query("docs")
            .score_multi_field_bayesian("learning", ["title", "body"])
            .execute()
        )
        assert len(result) > 0

    def test_query_builder_multi_field_with_weights(self, engine: Engine) -> None:
        result = (
            engine.query("docs")
            .score_multi_field_bayesian("learning", ["title", "body"], [2.0, 0.5])
            .execute()
        )
        assert len(result) > 0
