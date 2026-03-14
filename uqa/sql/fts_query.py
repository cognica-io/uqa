#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Full-text search query string parser and compiler for the @@ operator.

Grammar
-------
::

    query      = or_expr
    or_expr    = and_expr ( 'OR' and_expr )*
    and_expr   = unary ( ('AND' | <implicit>) unary )*
    unary      = 'NOT' unary | primary
    primary    = '(' or_expr ')'
               | TERM ':' PHRASE          -- field:"phrase"
               | TERM ':' VECTOR          -- field:[0.1, 0.2]
               | TERM ':' TERM            -- field:term
               | PHRASE                   -- "phrase"
               | TERM                     -- bare term

Operators AND / OR / NOT are case-insensitive keywords.
Adjacent terms without an explicit operator are treated as implicit AND.
Precedence: NOT > AND > OR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.operators.base import ExecutionContext, Operator
    from uqa.sql.compiler import SQLCompiler


# ------------------------------------------------------------------ #
# Lexer
# ------------------------------------------------------------------ #


class FTSTokenType(Enum):
    TERM = auto()
    PHRASE = auto()
    VECTOR = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class FTSToken:
    type: FTSTokenType
    value: str
    pos: int


_KEYWORDS = {
    "and": FTSTokenType.AND,
    "or": FTSTokenType.OR,
    "not": FTSTokenType.NOT,
}


def tokenize(source: str) -> list[FTSToken]:
    """Tokenize an FTS query string into a list of tokens."""
    tokens: list[FTSToken] = []
    i = 0
    n = len(source)

    while i < n:
        ch = source[i]

        # Skip whitespace
        if ch in (" ", "\t", "\n", "\r"):
            i += 1
            continue

        # Single-character tokens
        if ch == "(":
            tokens.append(FTSToken(FTSTokenType.LPAREN, "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(FTSToken(FTSTokenType.RPAREN, ")", i))
            i += 1
            continue
        if ch == ":":
            tokens.append(FTSToken(FTSTokenType.COLON, ":", i))
            i += 1
            continue

        # Quoted phrase
        if ch == '"':
            start = i
            i += 1
            while i < n and source[i] != '"':
                i += 1
            if i >= n:
                raise ValueError(
                    f"Unterminated quoted phrase starting at position {start}"
                )
            phrase = source[start + 1 : i]
            tokens.append(FTSToken(FTSTokenType.PHRASE, phrase, start))
            i += 1  # skip closing quote
            continue

        # Vector literal [...]
        if ch == "[":
            start = i
            i += 1
            while i < n and source[i] != "]":
                i += 1
            if i >= n:
                raise ValueError(
                    f"Unterminated vector literal starting at position {start}"
                )
            content = source[start + 1 : i]
            tokens.append(FTSToken(FTSTokenType.VECTOR, content, start))
            i += 1  # skip closing bracket
            continue

        # Bare word (term or keyword)
        if _is_word_char(ch):
            start = i
            while i < n and _is_word_char(source[i]):
                i += 1
            word = source[start:i]
            kw = _KEYWORDS.get(word.lower())
            if kw is not None:
                tokens.append(FTSToken(kw, word, start))
            else:
                tokens.append(FTSToken(FTSTokenType.TERM, word, start))
            continue

        raise ValueError(f"Unexpected character {ch!r} at position {i}")

    tokens.append(FTSToken(FTSTokenType.EOF, "", n))
    return tokens


def _is_word_char(ch: str) -> bool:
    """Return True if *ch* is a valid word character (not delimiter)."""
    return ch not in (" ", "\t", "\n", "\r", "(", ")", ":", '"', "[", "]")


# ------------------------------------------------------------------ #
# AST Nodes
# ------------------------------------------------------------------ #


@dataclass(frozen=True, slots=True)
class TermNode:
    field: str | None
    term: str


@dataclass(frozen=True, slots=True)
class PhraseNode:
    field: str | None
    phrase: str


@dataclass(frozen=True, slots=True)
class VectorNode:
    field: str | None
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class AndNode:
    left: FTSNode
    right: FTSNode


@dataclass(frozen=True, slots=True)
class OrNode:
    left: FTSNode
    right: FTSNode


@dataclass(frozen=True, slots=True)
class NotNode:
    operand: FTSNode


FTSNode = TermNode | PhraseNode | VectorNode | AndNode | OrNode | NotNode


# ------------------------------------------------------------------ #
# Recursive Descent Parser
# ------------------------------------------------------------------ #


class FTSParser:
    """Parse an FTS query string into an AST."""

    def __init__(self, tokens: list[FTSToken]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> FTSNode:
        if self._peek().type == FTSTokenType.EOF:
            raise ValueError("Empty query")
        node = self._or_expr()
        if self._peek().type != FTSTokenType.EOF:
            tok = self._peek()
            raise ValueError(f"Unexpected token {tok.value!r} at position {tok.pos}")
        return node

    def _peek(self) -> FTSToken:
        return self._tokens[self._pos]

    def _advance(self) -> FTSToken:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: FTSTokenType) -> FTSToken:
        tok = self._advance()
        if tok.type != tt:
            raise ValueError(
                f"Expected {tt.name}, got {tok.type.name} ({tok.value!r}) "
                f"at position {tok.pos}"
            )
        return tok

    def _or_expr(self) -> FTSNode:
        left = self._and_expr()
        while self._peek().type == FTSTokenType.OR:
            self._advance()  # consume OR
            right = self._and_expr()
            left = OrNode(left, right)
        return left

    def _and_expr(self) -> FTSNode:
        left = self._unary()
        while True:
            tok = self._peek()
            if tok.type == FTSTokenType.AND:
                self._advance()  # consume AND
                right = self._unary()
                left = AndNode(left, right)
            elif tok.type in (
                FTSTokenType.TERM,
                FTSTokenType.PHRASE,
                FTSTokenType.VECTOR,
                FTSTokenType.LPAREN,
                FTSTokenType.NOT,
            ):
                # Implicit AND
                right = self._unary()
                left = AndNode(left, right)
            else:
                break
        return left

    def _unary(self) -> FTSNode:
        if self._peek().type == FTSTokenType.NOT:
            self._advance()  # consume NOT
            operand = self._unary()
            return NotNode(operand)
        return self._primary()

    def _primary(self) -> FTSNode:
        tok = self._peek()

        if tok.type == FTSTokenType.LPAREN:
            self._advance()  # consume (
            node = self._or_expr()
            self._expect(FTSTokenType.RPAREN)
            return node

        if tok.type == FTSTokenType.PHRASE:
            self._advance()
            return PhraseNode(field=None, phrase=tok.value)

        if tok.type == FTSTokenType.VECTOR:
            self._advance()
            return VectorNode(field=None, values=_parse_vector(tok.value))

        if tok.type == FTSTokenType.TERM:
            self._advance()
            # Lookahead for field:value
            if self._peek().type == FTSTokenType.COLON:
                self._advance()  # consume :
                next_tok = self._peek()
                if next_tok.type == FTSTokenType.PHRASE:
                    self._advance()
                    return PhraseNode(field=tok.value, phrase=next_tok.value)
                if next_tok.type == FTSTokenType.VECTOR:
                    self._advance()
                    return VectorNode(
                        field=tok.value, values=_parse_vector(next_tok.value)
                    )
                if next_tok.type == FTSTokenType.TERM:
                    self._advance()
                    return TermNode(field=tok.value, term=next_tok.value)
                raise ValueError(
                    f"Expected term, phrase, or vector after ':', "
                    f"got {next_tok.type.name} at position {next_tok.pos}"
                )
            return TermNode(field=None, term=tok.value)

        raise ValueError(
            f"Unexpected token {tok.type.name} ({tok.value!r}) at position {tok.pos}"
        )


def _parse_vector(content: str) -> tuple[float, ...]:
    """Parse comma-separated floats from vector literal content."""
    content = content.strip()
    if not content:
        raise ValueError("Empty vector literal")
    try:
        return tuple(float(v.strip()) for v in content.split(","))
    except ValueError as exc:
        raise ValueError(f"Malformed vector literal: {exc}") from exc


# ------------------------------------------------------------------ #
# AST-to-Operator Compiler
# ------------------------------------------------------------------ #


def compile_fts_match(
    query_string: str,
    default_field: str | None,
    ctx: ExecutionContext,
    compiler: SQLCompiler,
) -> Operator:
    """Compile a full-text search query string into a UQA operator tree.

    Parameters
    ----------
    query_string:
        The query string from the right-hand side of ``@@``.
    default_field:
        Column name from the left-hand side.  ``None`` means search all
        text fields (``_all`` column was specified).
    ctx:
        The current execution context with document store and inverted index.
    compiler:
        The SQL compiler instance (used for ``_make_text_search_op``).
    """
    tokens = tokenize(query_string)
    ast = FTSParser(tokens).parse()
    return _compile_node(ast, default_field, ctx, compiler)


def _compile_node(
    node: FTSNode,
    default_field: str | None,
    ctx: ExecutionContext,
    compiler: SQLCompiler,
) -> Operator:
    """Recursively compile an FTS AST node into a UQA operator."""
    if isinstance(node, TermNode):
        field = _resolve_field(node.field, default_field)
        return compiler._make_text_search_op(field, node.term, ctx, bayesian=True)

    if isinstance(node, PhraseNode):
        return _compile_phrase(node, default_field, ctx)

    if isinstance(node, VectorNode):
        return _compile_vector(node, default_field)

    if isinstance(node, AndNode):
        return _compile_and(node, default_field, ctx, compiler)

    if isinstance(node, OrNode):
        from uqa.operators.boolean import UnionOperator

        left = _compile_node(node.left, default_field, ctx, compiler)
        right = _compile_node(node.right, default_field, ctx, compiler)
        return UnionOperator([left, right])

    if isinstance(node, NotNode):
        from uqa.operators.boolean import ComplementOperator

        operand = _compile_node(node.operand, default_field, ctx, compiler)
        return ComplementOperator(operand)

    raise TypeError(f"Unknown FTS node type: {type(node).__name__}")


def _compile_phrase(
    node: PhraseNode,
    default_field: str | None,
    ctx: ExecutionContext,
) -> Operator:
    """Compile a phrase query into intersected term operators with BM25 scoring.

    A phrase is tokenized into individual terms.  Each term becomes a
    TermOperator, and they are intersected so only documents containing
    ALL terms are returned.  The result is then scored with BayesianBM25.
    """
    from uqa.operators.boolean import IntersectOperator
    from uqa.operators.primitive import ScoreOperator, TermOperator

    field = _resolve_field(node.field, default_field)
    idx = ctx.inverted_index
    if idx is None:
        from uqa.core.posting_list import PostingList
        from uqa.operators.base import Operator as _Op

        class _Empty(_Op):
            def execute(self, context: ExecutionContext) -> PostingList:
                return PostingList()

            def cost_estimate(self, stats: object) -> float:
                return 0.0

        return _Empty()

    analyzer = idx.get_search_analyzer(field) if field else idx.analyzer
    terms = analyzer.analyze(node.phrase)
    if not terms:
        from uqa.core.posting_list import PostingList
        from uqa.operators.base import Operator as _Op

        class _Empty2(_Op):
            def execute(self, context: ExecutionContext) -> PostingList:
                return PostingList()

            def cost_estimate(self, stats: object) -> float:
                return 0.0

        return _Empty2()

    term_ops = [TermOperator(t, field) for t in terms]
    retrieval = term_ops[0] if len(term_ops) == 1 else IntersectOperator(term_ops)

    from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

    scorer = BayesianBM25Scorer(BayesianBM25Params(), idx.stats)
    return ScoreOperator(scorer, retrieval, terms, field=field)


def _compile_vector(
    node: VectorNode,
    default_field: str | None,
) -> Operator:
    """Compile a vector query into a calibrated KNN operator."""
    import numpy as np

    field = node.field or default_field or "embedding"
    query_vec = np.array(node.values, dtype=np.float32)

    # Import here to avoid circular imports at module level
    from uqa.sql.compiler import _CalibratedKNNOperator

    return _CalibratedKNNOperator(query_vec, k=10000, field=field)


def _compile_and(
    node: AndNode,
    default_field: str | None,
    ctx: ExecutionContext,
    compiler: SQLCompiler,
) -> Operator:
    """Compile AND -- use LogOddsFusion when mixing text and vector signals."""
    left_op = _compile_node(node.left, default_field, ctx, compiler)
    right_op = _compile_node(node.right, default_field, ctx, compiler)

    if _has_vector_signal(node.left) != _has_vector_signal(node.right):
        # Mixed text + vector: use log-odds fusion for calibrated combination
        from uqa.operators.hybrid import LogOddsFusionOperator

        return LogOddsFusionOperator([left_op, right_op])

    # Same-kind AND: use intersection
    from uqa.operators.boolean import IntersectOperator

    return IntersectOperator([left_op, right_op])


def _has_vector_signal(node: FTSNode) -> bool:
    """Return True if the AST subtree contains a VectorNode."""
    if isinstance(node, VectorNode):
        return True
    if isinstance(node, (TermNode, PhraseNode)):
        return False
    if isinstance(node, AndNode):
        return _has_vector_signal(node.left) or _has_vector_signal(node.right)
    if isinstance(node, OrNode):
        return _has_vector_signal(node.left) or _has_vector_signal(node.right)
    if isinstance(node, NotNode):
        return _has_vector_signal(node.operand)
    return False


def _resolve_field(node_field: str | None, default_field: str | None) -> str | None:
    """Resolve the effective field name.

    If the node specifies a field, use it.  Otherwise fall back to the
    default_field from the left-hand side of ``@@``.  The special value
    ``_all`` is mapped to ``None`` (all-field search).
    """
    field = node_field if node_field is not None else default_field
    if field == "_all":
        return None
    return field
