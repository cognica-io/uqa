from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from uqa.core.types import Edge, Vertex


@dataclass
class VertexPattern:
    """A vertex pattern with variable name and optional constraints."""

    variable: str
    constraints: list[Callable[[Vertex], bool]] = field(default_factory=list)


@dataclass
class EdgePattern:
    """An edge pattern connecting two vertex variables."""

    source_var: str
    target_var: str
    label: str | None = None
    constraints: list[Callable[[Edge], bool]] = field(default_factory=list)


@dataclass
class GraphPattern:
    """Definition 5.2.1 (Paper 2): P = (V_P, E_P, C_V, C_E)"""

    vertex_patterns: list[VertexPattern]
    edge_patterns: list[EdgePattern]


class RegularPathExpr(ABC):
    """Abstract base class for regular path expressions."""

    @abstractmethod
    def __repr__(self) -> str: ...


@dataclass(frozen=True)
class Label(RegularPathExpr):
    """A single edge label."""

    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Concat(RegularPathExpr):
    """Concatenation of two path expressions (e1/e2)."""

    left: RegularPathExpr
    right: RegularPathExpr

    def __repr__(self) -> str:
        return f"({self.left!r}/{self.right!r})"


@dataclass(frozen=True)
class Alternation(RegularPathExpr):
    """Alternation of two path expressions (e1|e2)."""

    left: RegularPathExpr
    right: RegularPathExpr

    def __repr__(self) -> str:
        return f"({self.left!r}|{self.right!r})"


@dataclass(frozen=True)
class KleeneStar(RegularPathExpr):
    """Kleene star of a path expression (e*)."""

    inner: RegularPathExpr

    def __repr__(self) -> str:
        return f"{self.inner!r}*"


def parse_rpq(expr_str: str) -> RegularPathExpr:
    """Parse a regular path query expression string.

    Syntax:
        - "label" for a single label
        - "e1/e2" for concatenation
        - "e1|e2" for alternation
        - "e*" for Kleene star
        - Parentheses for grouping

    Precedence (lowest to highest): alternation, concatenation, Kleene star.
    """
    tokens = _tokenize(expr_str)
    pos = 0
    result, pos = _parse_alternation(tokens, pos)
    if pos != len(tokens):
        raise ValueError(
            f"Unexpected token at position {pos}: {tokens[pos]!r}"
        )
    return result


def _tokenize(expr_str: str) -> list[str]:
    """Tokenize an RPQ expression into labels, operators, and parens."""
    tokens: list[str] = []
    i = 0
    while i < len(expr_str):
        ch = expr_str[i]
        if ch in " \t":
            i += 1
            continue
        if ch in ("(", ")", "/", "|", "*"):
            tokens.append(ch)
            i += 1
        else:
            # Read a label (sequence of alphanumeric + underscore)
            start = i
            while i < len(expr_str) and expr_str[i] not in ("(", ")", "/", "|", "*", " ", "\t"):
                i += 1
            tokens.append(expr_str[start:i])
    return tokens


def _parse_alternation(tokens: list[str], pos: int) -> tuple[RegularPathExpr, int]:
    """Parse alternation (lowest precedence): expr '|' expr"""
    left, pos = _parse_concat(tokens, pos)
    while pos < len(tokens) and tokens[pos] == "|":
        pos += 1  # consume '|'
        right, pos = _parse_concat(tokens, pos)
        left = Alternation(left, right)
    return left, pos


def _parse_concat(tokens: list[str], pos: int) -> tuple[RegularPathExpr, int]:
    """Parse concatenation: expr '/' expr"""
    left, pos = _parse_star(tokens, pos)
    while pos < len(tokens) and tokens[pos] == "/":
        pos += 1  # consume '/'
        right, pos = _parse_star(tokens, pos)
        left = Concat(left, right)
    return left, pos


def _parse_star(tokens: list[str], pos: int) -> tuple[RegularPathExpr, int]:
    """Parse Kleene star (highest precedence): expr '*'"""
    expr, pos = _parse_atom(tokens, pos)
    while pos < len(tokens) and tokens[pos] == "*":
        pos += 1  # consume '*'
        expr = KleeneStar(expr)
    return expr, pos


def _parse_atom(tokens: list[str], pos: int) -> tuple[RegularPathExpr, int]:
    """Parse atom: label or parenthesized expression."""
    if pos >= len(tokens):
        raise ValueError("Unexpected end of expression")
    token = tokens[pos]
    if token == "(":
        pos += 1  # consume '('
        expr, pos = _parse_alternation(tokens, pos)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise ValueError("Missing closing parenthesis")
        pos += 1  # consume ')'
        return expr, pos
    if token in (")", "/", "|", "*"):
        raise ValueError(f"Unexpected token: {token!r}")
    # It's a label
    pos += 1
    return Label(token), pos
