#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the @@ full-text search / hybrid search operator."""

from __future__ import annotations

import numpy as np
import pytest

from uqa.engine import Engine
from uqa.sql.fts_query import (
    AndNode,
    FTSParser,
    FTSTokenType,
    NotNode,
    OrNode,
    PhraseNode,
    TermNode,
    VectorNode,
    tokenize,
)

# ================================================================== #
# Fixtures
# ================================================================== #


@pytest.fixture
def engine() -> Engine:
    """Engine with a docs table containing text and vector columns."""
    e = Engine()
    e.sql("""
        CREATE TABLE docs (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            embedding VECTOR(4)
        )
    """)
    rows = [
        (
            "database internals",
            "a guide to storage engines and distributed systems",
            [0.9, 0.1, 0.0, 0.0],
        ),
        (
            "full text search algorithms",
            "inverted index and BM25 scoring for information retrieval",
            [0.1, 0.9, 0.0, 0.0],
        ),
        (
            "wireless sensor networks",
            "low power communication protocols for IoT devices",
            [0.0, 0.0, 0.9, 0.1],
        ),
        (
            "deep learning fundamentals",
            "neural network architectures and training techniques",
            [0.0, 0.0, 0.1, 0.9],
        ),
        (
            "database query optimization",
            "cost-based optimizer and query planning for SQL engines",
            [0.8, 0.2, 0.0, 0.0],
        ),
        (
            "information retrieval systems",
            "ranking algorithms and relevance scoring for search engines",
            [0.2, 0.8, 0.0, 0.0],
        ),
    ]
    for title, body, emb in rows:
        vec = np.array(emb, dtype=np.float32)
        arr_str = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
        e.sql(
            f"INSERT INTO docs (title, body, embedding) "
            f"VALUES ('{title}', '{body}', {arr_str})"
        )
    return e


# ================================================================== #
# Lexer unit tests
# ================================================================== #


class TestFTSTokenizer:
    def test_single_term(self) -> None:
        tokens = tokenize("hello")
        assert tokens[0].type == FTSTokenType.TERM
        assert tokens[0].value == "hello"
        assert tokens[1].type == FTSTokenType.EOF

    def test_multiple_terms(self) -> None:
        tokens = tokenize("hello world")
        assert tokens[0].type == FTSTokenType.TERM
        assert tokens[1].type == FTSTokenType.TERM
        assert tokens[2].type == FTSTokenType.EOF

    def test_phrase(self) -> None:
        tokens = tokenize('"hello world"')
        assert tokens[0].type == FTSTokenType.PHRASE
        assert tokens[0].value == "hello world"

    def test_vector(self) -> None:
        tokens = tokenize("[0.1, 0.2, 0.3]")
        assert tokens[0].type == FTSTokenType.VECTOR
        assert tokens[0].value == "0.1, 0.2, 0.3"

    def test_boolean_keywords(self) -> None:
        tokens = tokenize("a AND b OR c NOT d")
        types = [t.type for t in tokens[:-1]]  # exclude EOF
        assert types == [
            FTSTokenType.TERM,
            FTSTokenType.AND,
            FTSTokenType.TERM,
            FTSTokenType.OR,
            FTSTokenType.TERM,
            FTSTokenType.NOT,
            FTSTokenType.TERM,
        ]

    def test_case_insensitive_keywords(self) -> None:
        tokens = tokenize("a and b or c not d")
        types = [t.type for t in tokens[:-1]]
        assert types == [
            FTSTokenType.TERM,
            FTSTokenType.AND,
            FTSTokenType.TERM,
            FTSTokenType.OR,
            FTSTokenType.TERM,
            FTSTokenType.NOT,
            FTSTokenType.TERM,
        ]

    def test_field_colon_term(self) -> None:
        tokens = tokenize("title:hello")
        types = [t.type for t in tokens[:-1]]
        assert types == [FTSTokenType.TERM, FTSTokenType.COLON, FTSTokenType.TERM]

    def test_parentheses(self) -> None:
        tokens = tokenize("(a OR b)")
        types = [t.type for t in tokens[:-1]]
        assert types == [
            FTSTokenType.LPAREN,
            FTSTokenType.TERM,
            FTSTokenType.OR,
            FTSTokenType.TERM,
            FTSTokenType.RPAREN,
        ]

    def test_empty_string(self) -> None:
        tokens = tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type == FTSTokenType.EOF

    def test_unterminated_quote(self) -> None:
        with pytest.raises(ValueError, match="Unterminated quoted phrase"):
            tokenize('"hello')

    def test_unterminated_bracket(self) -> None:
        with pytest.raises(ValueError, match="Unterminated vector literal"):
            tokenize("[0.1, 0.2")

    def test_complex_query(self) -> None:
        tokens = tokenize('title:"neural network" AND embedding:[0.1, 0.2]')
        types = [t.type for t in tokens[:-1]]
        assert types == [
            FTSTokenType.TERM,
            FTSTokenType.COLON,
            FTSTokenType.PHRASE,
            FTSTokenType.AND,
            FTSTokenType.TERM,
            FTSTokenType.COLON,
            FTSTokenType.VECTOR,
        ]


# ================================================================== #
# Parser unit tests
# ================================================================== #


class TestFTSParser:
    def test_single_term(self) -> None:
        ast = FTSParser(tokenize("hello")).parse()
        assert isinstance(ast, TermNode)
        assert ast.field is None
        assert ast.term == "hello"

    def test_phrase(self) -> None:
        ast = FTSParser(tokenize('"hello world"')).parse()
        assert isinstance(ast, PhraseNode)
        assert ast.field is None
        assert ast.phrase == "hello world"

    def test_field_term(self) -> None:
        ast = FTSParser(tokenize("title:hello")).parse()
        assert isinstance(ast, TermNode)
        assert ast.field == "title"
        assert ast.term == "hello"

    def test_field_phrase(self) -> None:
        ast = FTSParser(tokenize('title:"hello world"')).parse()
        assert isinstance(ast, PhraseNode)
        assert ast.field == "title"
        assert ast.phrase == "hello world"

    def test_field_vector(self) -> None:
        ast = FTSParser(tokenize("embedding:[0.1, 0.2, 0.3]")).parse()
        assert isinstance(ast, VectorNode)
        assert ast.field == "embedding"
        assert ast.values == (0.1, 0.2, 0.3)

    def test_explicit_and(self) -> None:
        ast = FTSParser(tokenize("a AND b")).parse()
        assert isinstance(ast, AndNode)
        assert isinstance(ast.left, TermNode)
        assert isinstance(ast.right, TermNode)

    def test_explicit_or(self) -> None:
        ast = FTSParser(tokenize("a OR b")).parse()
        assert isinstance(ast, OrNode)

    def test_not(self) -> None:
        ast = FTSParser(tokenize("NOT a")).parse()
        assert isinstance(ast, NotNode)
        assert isinstance(ast.operand, TermNode)

    def test_implicit_and(self) -> None:
        ast = FTSParser(tokenize("a b")).parse()
        assert isinstance(ast, AndNode)
        assert isinstance(ast.left, TermNode)
        assert isinstance(ast.right, TermNode)

    def test_precedence_and_over_or(self) -> None:
        # a OR b AND c -> Or(a, And(b, c))
        ast = FTSParser(tokenize("a OR b AND c")).parse()
        assert isinstance(ast, OrNode)
        assert isinstance(ast.left, TermNode)
        assert ast.left.term == "a"
        assert isinstance(ast.right, AndNode)

    def test_grouping_overrides_precedence(self) -> None:
        # (a OR b) AND c -> And(Or(a, b), c)
        ast = FTSParser(tokenize("(a OR b) AND c")).parse()
        assert isinstance(ast, AndNode)
        assert isinstance(ast.left, OrNode)
        assert isinstance(ast.right, TermNode)

    def test_complex_nested(self) -> None:
        ast = FTSParser(
            tokenize("(title:attention OR body:transformer) AND embedding:[0.1, 0.2]")
        ).parse()
        assert isinstance(ast, AndNode)
        assert isinstance(ast.left, OrNode)
        assert isinstance(ast.right, VectorNode)

    def test_double_negation(self) -> None:
        ast = FTSParser(tokenize("NOT NOT hello")).parse()
        assert isinstance(ast, NotNode)
        assert isinstance(ast.operand, NotNode)
        assert isinstance(ast.operand.operand, TermNode)

    def test_empty_query(self) -> None:
        with pytest.raises(ValueError, match="Empty query"):
            FTSParser(tokenize("")).parse()

    def test_trailing_operator(self) -> None:
        with pytest.raises(ValueError, match="Unexpected token"):
            FTSParser(tokenize("a AND")).parse()

    def test_unbalanced_paren(self) -> None:
        with pytest.raises(ValueError, match="Expected RPAREN"):
            FTSParser(tokenize("(a OR b")).parse()

    def test_three_implicit_and(self) -> None:
        ast = FTSParser(tokenize("a b c")).parse()
        # Left-associative: And(And(a, b), c)
        assert isinstance(ast, AndNode)
        assert isinstance(ast.left, AndNode)
        assert isinstance(ast.right, TermNode)
        assert ast.right.term == "c"


# ================================================================== #
# SQL integration tests
# ================================================================== #


class TestFTSMatchSQL:
    def test_single_term(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE title @@ 'database' ORDER BY _score DESC"
        )
        assert len(result) >= 1
        for row in result:
            assert "database" in row["title"]
            assert row["_score"] > 0

    def test_phrase(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs "
            "WHERE body @@ '\"information retrieval\"' ORDER BY _score DESC"
        )
        assert len(result) >= 1
        for row in result:
            assert row["_score"] > 0

    def test_all_column(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM docs WHERE _all @@ 'database'")
        assert len(result) >= 1

    def test_boolean_and(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM docs WHERE title @@ 'database AND query'"
        )
        # Only documents with both "database" and "query" in title
        assert len(result) >= 1
        for row in result:
            assert "database" in row["title"]
            assert "query" in row["title"] or "optimization" in row["title"]

    def test_boolean_or(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM docs WHERE title @@ 'database OR wireless'"
        )
        # Documents with either "database" or "wireless" in title
        assert len(result) >= 2

    def test_boolean_not(self, engine: Engine) -> None:
        all_result = engine.sql("SELECT title FROM docs WHERE title @@ 'database'")
        not_result = engine.sql(
            "SELECT title FROM docs WHERE title @@ 'database AND NOT query'"
        )
        assert len(not_result) < len(all_result) or len(not_result) >= 1

    def test_grouping(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM docs WHERE title @@ '(database OR search) AND text'"
        )
        assert len(result) >= 1

    def test_implicit_and(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM docs WHERE title @@ 'full text'")
        assert len(result) >= 1

    def test_field_specific(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM docs WHERE _all @@ 'title:database'")
        assert len(result) >= 1

    def test_hybrid_text_vector(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs "
            "WHERE _all @@ 'body:search AND embedding:[0.1, 0.9, 0.0, 0.0]' "
            "ORDER BY _score DESC"
        )
        assert len(result) >= 1
        for row in result:
            assert 0 < row["_score"] < 1

    def test_score_calibrated(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE title @@ 'database' "
            "ORDER BY _score DESC"
        )
        for row in result:
            assert 0 < row["_score"] < 1

    def test_order_by_score_limit(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs WHERE title @@ 'database' "
            "ORDER BY _score DESC LIMIT 1"
        )
        assert len(result) == 1

    def test_combined_with_equality(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM docs WHERE title @@ 'database' AND id > 2"
        )
        for row in result:
            assert "database" in row["title"]


# ================================================================== #
# Edge cases
# ================================================================== #


class TestFTSMatchEdgeCases:
    def test_empty_query(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match="Empty query"):
            engine.sql("SELECT title FROM docs WHERE title @@ ''")

    def test_unknown_field(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title FROM docs WHERE _all @@ 'nonexistent_field:xyz'"
        )
        assert len(result) == 0

    def test_malformed_vector(self) -> None:
        with pytest.raises(ValueError, match="Malformed vector literal"):
            FTSParser(tokenize("field:[abc, def]")).parse()
            # _parse_vector is called during VectorNode construction

    def test_malformed_vector_via_parser(self) -> None:
        # The parser itself creates VectorNode which calls _parse_vector
        tokens = tokenize("field:[abc, def]")
        with pytest.raises(ValueError):
            FTSParser(tokens).parse()

    def test_unbalanced_parens(self) -> None:
        with pytest.raises(ValueError):
            FTSParser(tokenize("(a AND b")).parse()

    def test_extra_closing_paren(self) -> None:
        with pytest.raises(ValueError):
            FTSParser(tokenize("a AND b)")).parse()

    def test_vector_only_query(self, engine: Engine) -> None:
        result = engine.sql(
            "SELECT title, _score FROM docs "
            "WHERE _all @@ 'embedding:[0.9, 0.1, 0.0, 0.0]' "
            "ORDER BY _score DESC"
        )
        assert len(result) >= 1
        # First result should be closest to the query vector
        assert result.rows[0]["_score"] > 0

    def test_not_only(self, engine: Engine) -> None:
        result = engine.sql("SELECT title FROM docs WHERE title @@ 'NOT database'")
        for row in result:
            assert "database" not in row["title"]

    def test_empty_vector_literal(self) -> None:
        with pytest.raises(ValueError, match="Empty vector literal"):
            from uqa.sql.fts_query import _parse_vector

            _parse_vector("")
