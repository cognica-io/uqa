#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""AST node definitions for the openCypher subset supported by UQA.

The AST mirrors Apache AGE's supported Cypher clauses:

    MATCH / OPTIONAL MATCH / CREATE / MERGE / SET / DELETE / DETACH DELETE
    RETURN / WITH / WHERE / ORDER BY / SKIP / LIMIT / UNWIND
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# -- Expressions -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PropertyAccess:
    """``n.name`` or ``n.address.city``."""

    variable: str
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Parameter:
    """``$param`` -- a named parameter reference."""

    name: str


@dataclass(frozen=True, slots=True)
class Literal:
    """A literal value: integer, float, string, boolean, NULL, list, map."""

    value: Any


@dataclass(frozen=True, slots=True)
class Variable:
    """A bound variable reference (``n``, ``r``)."""

    name: str


@dataclass(frozen=True, slots=True)
class FunctionCall:
    """``func(arg1, arg2, ...)`` -- built-in or aggregation."""

    name: str
    args: tuple[CypherExpr, ...]
    distinct: bool = False


@dataclass(frozen=True, slots=True)
class BinaryOp:
    """``left op right`` -- comparison, arithmetic, logic."""

    op: str
    left: CypherExpr
    right: CypherExpr


@dataclass(frozen=True, slots=True)
class UnaryOp:
    """``NOT expr`` or ``-expr``."""

    op: str
    operand: CypherExpr


@dataclass(frozen=True, slots=True)
class ListIndex:
    """``expr[index]``."""

    expr: CypherExpr
    index: CypherExpr


@dataclass(frozen=True, slots=True)
class InList:
    """``expr IN list_expr``."""

    expr: CypherExpr
    list_expr: CypherExpr


@dataclass(frozen=True, slots=True)
class IsNull:
    """``expr IS NULL``."""

    expr: CypherExpr


@dataclass(frozen=True, slots=True)
class IsNotNull:
    """``expr IS NOT NULL``."""

    expr: CypherExpr


@dataclass(frozen=True, slots=True)
class CaseExpr:
    """``CASE expr WHEN ... THEN ... ELSE ... END``."""

    operand: CypherExpr | None
    whens: tuple[tuple[CypherExpr, CypherExpr], ...]
    else_expr: CypherExpr | None


@dataclass(frozen=True, slots=True)
class ListLiteral:
    """``[expr, expr, ...]``."""

    elements: tuple[CypherExpr, ...]


@dataclass(frozen=True, slots=True)
class MapLiteral:
    """``{key: expr, key: expr, ...}``."""

    pairs: tuple[tuple[str, CypherExpr], ...]


CypherExpr = (
    PropertyAccess
    | Parameter
    | Literal
    | Variable
    | FunctionCall
    | BinaryOp
    | UnaryOp
    | ListIndex
    | InList
    | IsNull
    | IsNotNull
    | CaseExpr
    | ListLiteral
    | MapLiteral
)


# -- Pattern elements -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class NodePattern:
    """``(variable:Label {key: value, ...})``."""

    variable: str | None
    labels: tuple[str, ...]
    properties: dict[str, CypherExpr] | None


@dataclass(frozen=True, slots=True)
class RelPattern:
    """``-[variable:TYPE*min..max {props}]->``."""

    variable: str | None
    types: tuple[str, ...]
    properties: dict[str, CypherExpr] | None
    direction: str  # "right", "left", "both", "none"
    min_hops: int | None  # None = exactly 1
    max_hops: int | None  # None = exactly 1


@dataclass(frozen=True, slots=True)
class PathPattern:
    """A chain of alternating node and relationship patterns.

    ``elements`` alternates NodePattern and RelPattern:
    ``(a)-[r]->(b)`` -> [NodePattern, RelPattern, NodePattern]
    """

    elements: tuple[NodePattern | RelPattern, ...]


# -- Clauses ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MatchClause:
    """``MATCH pattern WHERE condition``."""

    patterns: tuple[PathPattern, ...]
    where: CypherExpr | None
    optional: bool


@dataclass(frozen=True, slots=True)
class CreateClause:
    """``CREATE pattern``."""

    patterns: tuple[PathPattern, ...]


@dataclass(frozen=True, slots=True)
class MergeClause:
    """``MERGE pattern ON CREATE SET ... ON MATCH SET ...``."""

    pattern: PathPattern
    on_create_set: tuple[SetItem, ...] | None
    on_match_set: tuple[SetItem, ...] | None


@dataclass(frozen=True, slots=True)
class SetItem:
    """``variable.property = expr`` or ``variable = expr`` or ``variable += expr``."""

    target: CypherExpr
    value: CypherExpr
    operator: str  # "=", "+="


@dataclass(frozen=True, slots=True)
class SetClause:
    """``SET item, item, ...``."""

    items: tuple[SetItem, ...]


@dataclass(frozen=True, slots=True)
class DeleteClause:
    """``DELETE expr, expr, ...`` or ``DETACH DELETE expr, expr, ...``."""

    expressions: tuple[CypherExpr, ...]
    detach: bool


@dataclass(frozen=True, slots=True)
class ReturnItem:
    """A single item in RETURN or WITH: ``expr AS alias``."""

    expr: CypherExpr
    alias: str | None


@dataclass(frozen=True, slots=True)
class OrderByItem:
    """``expr ASC|DESC``."""

    expr: CypherExpr
    ascending: bool


@dataclass(frozen=True, slots=True)
class ReturnClause:
    """``RETURN [DISTINCT] items ORDER BY ... SKIP n LIMIT m``."""

    items: tuple[ReturnItem, ...]
    distinct: bool
    order_by: tuple[OrderByItem, ...] | None
    skip: CypherExpr | None
    limit: CypherExpr | None


@dataclass(frozen=True, slots=True)
class WithClause:
    """``WITH [DISTINCT] items WHERE condition``."""

    items: tuple[ReturnItem, ...]
    distinct: bool
    order_by: tuple[OrderByItem, ...] | None
    skip: CypherExpr | None
    limit: CypherExpr | None
    where: CypherExpr | None


@dataclass(frozen=True, slots=True)
class UnwindClause:
    """``UNWIND expr AS variable``."""

    expr: CypherExpr
    variable: str


CypherClause = (
    MatchClause
    | CreateClause
    | MergeClause
    | SetClause
    | DeleteClause
    | ReturnClause
    | WithClause
    | UnwindClause
)


# -- Top-level statement ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class CypherQuery:
    """A complete Cypher query: a sequence of clauses."""

    clauses: tuple[CypherClause, ...]
