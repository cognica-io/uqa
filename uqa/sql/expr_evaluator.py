#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQL expression evaluator for computed columns and expression-based filters.

Evaluates pglast AST expression nodes against data rows to produce
scalar values.  Used by the SQL compiler for:

- Computed columns in SELECT (``SELECT price * quantity AS total``)
- Expression-based WHERE clauses (``WHERE price * 2 > 100``)
- IS NULL / IS NOT NULL tests
- CASE / WHEN expressions
- CAST type conversions
- COALESCE and string functions (UPPER, LOWER, LENGTH, SUBSTRING, etc.)
"""

from __future__ import annotations

from typing import Any

from pglast.ast import (
    A_Const,
    A_Expr,
    BoolExpr,
    CaseExpr,
    CoalesceExpr,
    ColumnRef,
    Float as PgFloat,
    FuncCall,
    Integer as PgInteger,
    NullTest,
    String as PgString,
    TypeCast,
)
from pglast.enums.parsenodes import A_Expr_Kind
from pglast.enums.primnodes import BoolExprType, NullTestType


class ExprEvaluator:
    """Evaluate a pglast AST expression node against a data row.

    Each ``evaluate()`` call takes an AST node and a ``dict`` row and
    returns the computed scalar value.  The evaluator is stateless and
    reusable across rows.
    """

    def evaluate(self, node: Any, row: dict[str, Any]) -> Any:
        """Evaluate *node* against *row* and return the result."""
        if isinstance(node, ColumnRef):
            return self._eval_column_ref(node, row)

        if isinstance(node, A_Const):
            return self._eval_const(node)

        if isinstance(node, A_Expr):
            return self._eval_a_expr(node, row)

        if isinstance(node, FuncCall):
            return self._eval_func_call(node, row)

        if isinstance(node, NullTest):
            return self._eval_null_test(node, row)

        if isinstance(node, BoolExpr):
            return self._eval_bool_expr(node, row)

        if isinstance(node, CaseExpr):
            return self._eval_case(node, row)

        if isinstance(node, TypeCast):
            return self._eval_type_cast(node, row)

        if isinstance(node, CoalesceExpr):
            return self._eval_coalesce(node, row)

        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    # -- Leaf nodes ----------------------------------------------------

    @staticmethod
    def _eval_column_ref(node: ColumnRef, row: dict[str, Any]) -> Any:
        col_name = node.fields[-1].sval
        return row.get(col_name)

    @staticmethod
    def _eval_const(node: A_Const) -> Any:
        if node.isnull:
            return None
        val = node.val
        if isinstance(val, PgInteger):
            return val.ival
        if isinstance(val, PgFloat):
            return float(val.fval)
        if isinstance(val, PgString):
            return val.sval
        raise ValueError(f"Unknown A_Const value type: {type(val).__name__}")

    # -- A_Expr (arithmetic, comparison, concatenation) ----------------

    def _eval_a_expr(self, node: A_Expr, row: dict[str, Any]) -> Any:
        kind = A_Expr_Kind(node.kind)

        if kind == A_Expr_Kind.AEXPR_OP:
            return self._eval_operator(node, row)

        if kind == A_Expr_Kind.AEXPR_IN:
            left = self.evaluate(node.lexpr, row)
            if left is None:
                return False
            values = [self.evaluate(v, row) for v in node.rexpr]
            return left in values

        if kind == A_Expr_Kind.AEXPR_BETWEEN:
            val = self.evaluate(node.lexpr, row)
            if val is None:
                return False
            low = self.evaluate(node.rexpr[0], row)
            high = self.evaluate(node.rexpr[1], row)
            return low <= val <= high

        if kind == A_Expr_Kind.AEXPR_NOT_BETWEEN:
            val = self.evaluate(node.lexpr, row)
            if val is None:
                return True
            low = self.evaluate(node.rexpr[0], row)
            high = self.evaluate(node.rexpr[1], row)
            return not (low <= val <= high)

        raise ValueError(f"Unsupported A_Expr kind: {kind}")

    def _eval_operator(self, node: A_Expr, row: dict[str, Any]) -> Any:
        op = node.name[0].sval
        left = self.evaluate(node.lexpr, row)
        right = self.evaluate(node.rexpr, row)

        # String concatenation
        if op == "||":
            if left is None or right is None:
                return None
            return str(left) + str(right)

        # Arithmetic (return None if either operand is None)
        if op in ("+", "-", "*", "/", "%"):
            if left is None or right is None:
                return None
            return _arithmetic(op, left, right)

        # Comparison (return False if either operand is None)
        if op in ("=", "!=", "<>", "<", ">", "<=", ">="):
            if left is None or right is None:
                return False
            return _compare(op, left, right)

        raise ValueError(f"Unsupported operator: {op}")

    # -- NullTest ------------------------------------------------------

    def _eval_null_test(self, node: NullTest, row: dict[str, Any]) -> bool:
        value = self.evaluate(node.arg, row)
        if NullTestType(node.nulltesttype) == NullTestType.IS_NULL:
            return value is None
        return value is not None

    # -- BoolExpr (AND, OR, NOT) ---------------------------------------

    def _eval_bool_expr(self, node: BoolExpr, row: dict[str, Any]) -> bool:
        if node.boolop == BoolExprType.AND_EXPR:
            return all(self.evaluate(a, row) for a in node.args)
        if node.boolop == BoolExprType.OR_EXPR:
            return any(self.evaluate(a, row) for a in node.args)
        if node.boolop == BoolExprType.NOT_EXPR:
            return not self.evaluate(node.args[0], row)
        raise ValueError(f"Unsupported BoolExpr type: {node.boolop}")

    # -- CASE / WHEN --------------------------------------------------

    def _eval_case(self, node: CaseExpr, row: dict[str, Any]) -> Any:
        for when_node in node.args:
            condition = self.evaluate(when_node.expr, row)
            if condition:
                return self.evaluate(when_node.result, row)
        if node.defresult is not None:
            return self.evaluate(node.defresult, row)
        return None

    # -- TypeCast (CAST) -----------------------------------------------

    def _eval_type_cast(self, node: TypeCast, row: dict[str, Any]) -> Any:
        value = self.evaluate(node.arg, row)
        if value is None:
            return None
        type_name = node.typeName.names[-1].sval.lower()
        return _cast_value(value, type_name)

    # -- COALESCE ------------------------------------------------------

    def _eval_coalesce(self, node: CoalesceExpr, row: dict[str, Any]) -> Any:
        for arg in node.args:
            value = self.evaluate(arg, row)
            if value is not None:
                return value
        return None

    # -- FuncCall (scalar functions) -----------------------------------

    def _eval_func_call(self, node: FuncCall, row: dict[str, Any]) -> Any:
        func_name = node.funcname[-1].sval.lower()
        args = [self.evaluate(a, row) for a in (node.args or ())]
        return _call_scalar_function(func_name, args)


# -- Module-level helpers ------------------------------------------------


def _arithmetic(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            return None
        if isinstance(left, int) and isinstance(right, int):
            return left // right
        return left / right
    if op == "%":
        if right == 0:
            return None
        return left % right
    raise ValueError(f"Unknown arithmetic operator: {op}")


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "=":
        return left == right
    if op in ("!=", "<>"):
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    raise ValueError(f"Unknown comparison operator: {op}")


_CAST_MAP: dict[str, type] = {
    "integer": int,
    "int": int,
    "int4": int,
    "bigint": int,
    "int8": int,
    "smallint": int,
    "int2": int,
    "float": float,
    "float4": float,
    "float8": float,
    "double": float,
    "real": float,
    "numeric": float,
    "text": str,
    "varchar": str,
    "char": str,
    "boolean": bool,
    "bool": bool,
}


def _cast_value(value: Any, type_name: str) -> Any:
    cast_type = _CAST_MAP.get(type_name)
    if cast_type is None:
        raise ValueError(f"Unsupported CAST target type: {type_name}")
    if cast_type is bool:
        if isinstance(value, str):
            return value.lower() in ("true", "t", "1", "yes")
        return bool(value)
    return cast_type(value)


_SCALAR_FUNCTIONS: dict[str, Any] = {}


def _call_scalar_function(name: str, args: list[Any]) -> Any:
    # String functions
    if name == "upper":
        return str(args[0]).upper() if args[0] is not None else None
    if name == "lower":
        return str(args[0]).lower() if args[0] is not None else None
    if name == "length":
        return len(str(args[0])) if args[0] is not None else None
    if name in ("trim", "btrim"):
        return str(args[0]).strip() if args[0] is not None else None
    if name == "ltrim":
        return str(args[0]).lstrip() if args[0] is not None else None
    if name == "rtrim":
        return str(args[0]).rstrip() if args[0] is not None else None
    if name == "replace":
        if any(a is None for a in args[:3]):
            return None
        return str(args[0]).replace(str(args[1]), str(args[2]))
    if name == "substring" or name == "substr":
        if args[0] is None:
            return None
        s = str(args[0])
        start = int(args[1]) - 1 if len(args) > 1 else 0
        length = int(args[2]) if len(args) > 2 else len(s) - start
        return s[start : start + length]
    if name == "concat":
        return "".join(str(a) if a is not None else "" for a in args)
    if name == "left":
        if args[0] is None:
            return None
        return str(args[0])[: int(args[1])]
    if name == "right":
        if args[0] is None:
            return None
        n = int(args[1])
        return str(args[0])[-n:] if n > 0 else ""

    # Math functions
    if name == "abs":
        return abs(args[0]) if args[0] is not None else None
    if name == "round":
        if args[0] is None:
            return None
        ndigits = int(args[1]) if len(args) > 1 else 0
        return round(args[0], ndigits)
    if name == "ceil" or name == "ceiling":
        if args[0] is None:
            return None
        import math
        return math.ceil(args[0])
    if name == "floor":
        if args[0] is None:
            return None
        import math
        return math.floor(args[0])

    # Type checking
    if name == "typeof":
        if args[0] is None:
            return "null"
        if isinstance(args[0], int):
            return "integer"
        if isinstance(args[0], float):
            return "real"
        if isinstance(args[0], str):
            return "text"
        if isinstance(args[0], bool):
            return "boolean"
        return "unknown"

    raise ValueError(f"Unknown scalar function: {name}")
