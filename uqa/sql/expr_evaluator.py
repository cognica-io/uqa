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
    RangeVar,
    SelectStmt,
    String as PgString,
    SubLink,
    TypeCast,
)
from pglast.enums.parsenodes import A_Expr_Kind
from pglast.enums.primnodes import BoolExprType, NullTestType, SubLinkType


class ExprEvaluator:
    """Evaluate a pglast AST expression node against a data row.

    Each ``evaluate()`` call takes an AST node and a ``dict`` row and
    returns the computed scalar value.  The evaluator is stateless and
    reusable across rows.

    *subquery_executor* is an optional callback ``(SelectStmt) -> SQLResult``
    used to evaluate scalar subqueries (``EXPR_SUBLINK``) and
    ``IN`` subqueries (``ANY_SUBLINK``).
    """

    def __init__(
        self, subquery_executor: Any = None
    ) -> None:
        self._subquery_executor = subquery_executor

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

        if isinstance(node, SubLink):
            return self._eval_sublink(node, row)

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

        if kind == A_Expr_Kind.AEXPR_LIKE:
            val = self.evaluate(node.lexpr, row)
            if val is None:
                return False
            pattern = self.evaluate(node.rexpr, row)
            op_name = node.name[0].sval
            from uqa.core.types import _like_match
            matched = _like_match(str(val), pattern, case_sensitive=True)
            return not matched if op_name == "!~~" else matched

        if kind == A_Expr_Kind.AEXPR_ILIKE:
            val = self.evaluate(node.lexpr, row)
            if val is None:
                return False
            pattern = self.evaluate(node.rexpr, row)
            op_name = node.name[0].sval
            from uqa.core.types import _like_match
            matched = _like_match(str(val), pattern, case_sensitive=False)
            return not matched if op_name == "!~~*" else matched

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

    # -- SubLink (subquery) --------------------------------------------

    def _eval_sublink(self, node: SubLink, row: dict[str, Any]) -> Any:
        if self._subquery_executor is None:
            raise ValueError(
                "Subquery in expression requires a subquery executor"
            )

        # Substitute correlated column references from the outer row
        subselect = self._substitute_correlated_refs(
            node.subselect, row
        )

        link_type = SubLinkType(node.subLinkType)

        if link_type == SubLinkType.EXPR_SUBLINK:
            # Scalar subquery: (SELECT COUNT(*) FROM ...)
            result = self._subquery_executor(subselect)
            if not result.rows:
                return None
            first_col = result.columns[0]
            return result.rows[0][first_col]

        if link_type == SubLinkType.ANY_SUBLINK:
            # IN subquery: col IN (SELECT ...)
            left = self.evaluate(node.testexpr, row)
            if left is None:
                return False
            result = self._subquery_executor(subselect)
            if not result.columns:
                return False
            sub_col = result.columns[0]
            return left in {r[sub_col] for r in result.rows}

        if link_type == SubLinkType.EXISTS_SUBLINK:
            # EXISTS (SELECT ...)
            result = self._subquery_executor(subselect)
            return len(result.rows) > 0

        raise ValueError(f"Unsupported subquery type: {link_type.name}")

    def _substitute_correlated_refs(
        self, node: Any, outer_row: dict[str, Any]
    ) -> Any:
        """Replace correlated ColumnRef nodes with constants from the outer row.

        A correlated reference is a multi-part ColumnRef (e.g., ``e.dept``)
        whose qualifier (first part) does not match any table in the inner
        query's FROM clause.  Such references are replaced with ``A_Const``
        values from the outer row.
        """
        # Collect inner table names/aliases from the FROM clause
        inner_tables: set[str] = set()
        if isinstance(node, SelectStmt) and node.fromClause:
            for from_item in node.fromClause:
                if isinstance(from_item, RangeVar):
                    if from_item.alias:
                        inner_tables.add(from_item.alias.aliasname)
                    inner_tables.add(from_item.relname)

        return self._subst_correlated(node, outer_row, inner_tables)

    def _subst_correlated(
        self, node: Any, outer_row: dict[str, Any],
        inner_tables: set[str],
    ) -> Any:
        """Recursively walk AST, replacing correlated ColumnRefs."""
        if isinstance(node, ColumnRef):
            if len(node.fields) >= 2:
                qualifier = node.fields[0].sval
                col_name = node.fields[-1].sval
                if qualifier not in inner_tables:
                    # Correlated reference -- substitute with outer value
                    val = outer_row.get(col_name)
                    return self._value_to_const(val)
            return node

        if isinstance(node, tuple):
            return tuple(
                self._subst_correlated(item, outer_row, inner_tables)
                for item in node
            )
        if isinstance(node, list):
            return [
                self._subst_correlated(item, outer_row, inner_tables)
                for item in node
            ]

        if hasattr(node, '__slots__') and isinstance(node.__slots__, dict):
            kwargs = {}
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is None:
                    kwargs[slot] = None
                elif isinstance(val, (tuple, list)):
                    kwargs[slot] = type(val)(
                        self._subst_correlated(
                            item, outer_row, inner_tables
                        )
                        for item in val
                    )
                elif hasattr(val, '__slots__'):
                    kwargs[slot] = self._subst_correlated(
                        val, outer_row, inner_tables
                    )
                else:
                    kwargs[slot] = val
            try:
                return node.__class__(**kwargs)
            except TypeError:
                return node

        return node

    @staticmethod
    def _value_to_const(val: Any) -> A_Const:
        """Convert a Python value to an A_Const AST node."""
        if val is None:
            return A_Const(isnull=True, val=None)
        if isinstance(val, int):
            return A_Const(isnull=False, val=PgInteger(ival=val))
        if isinstance(val, float):
            return A_Const(isnull=False, val=PgFloat(fval=str(val)))
        return A_Const(isnull=False, val=PgString(sval=str(val)))

    # -- FuncCall (scalar functions) -----------------------------------

    def _eval_func_call(self, node: FuncCall, row: dict[str, Any]) -> Any:
        func_name = node.funcname[-1].sval.lower()
        if func_name == "path_agg":
            return self._eval_path_agg(node, row)
        if func_name == "path_value":
            return self._eval_path_value(node, row)
        args = [self.evaluate(a, row) for a in (node.args or ())]
        return _call_scalar_function(func_name, args)

    def _eval_path_agg(self, node: FuncCall, row: dict[str, Any]) -> Any:
        """Evaluate path_agg('path', 'func') -- aggregate nested array values.

        Navigates the row using the dot-path, collects array element values,
        and applies the named aggregation (sum, count, avg, min, max).
        """
        from uqa.core.hierarchical import HierarchicalDocument

        args = node.args or ()
        if len(args) < 2:
            raise ValueError("path_agg() requires 2 arguments: path, function")
        path_str = self.evaluate(args[0], row)
        agg_name = self.evaluate(args[1], row)

        path_expr: list[str | int] = []
        for component in str(path_str).split("."):
            if component.isdigit():
                path_expr.append(int(component))
            else:
                path_expr.append(component)

        hdoc = HierarchicalDocument(0, row)
        values = hdoc.eval_path(path_expr)

        if not isinstance(values, list):
            values = [values] if values is not None else []
        numeric = [v for v in values if isinstance(v, (int, float))]

        agg = str(agg_name).lower()
        if agg == "sum":
            return sum(numeric) if numeric else 0.0
        if agg == "count":
            return len(values)
        if agg == "avg":
            return sum(numeric) / len(numeric) if numeric else 0.0
        if agg == "min":
            return min(numeric) if numeric else None
        if agg == "max":
            return max(numeric) if numeric else None
        raise ValueError(f"Unknown aggregation function for path_agg: {agg}")

    def _eval_path_value(self, node: FuncCall, row: dict[str, Any]) -> Any:
        """Evaluate path_value('path') -- access nested field value.

        Navigates the row using the dot-path and returns the value found.
        """
        from uqa.core.hierarchical import HierarchicalDocument

        args = node.args or ()
        if len(args) < 1:
            raise ValueError("path_value() requires 1 argument: path")
        path_str = self.evaluate(args[0], row)

        path_expr: list[str | int] = []
        for component in str(path_str).split("."):
            if component.isdigit():
                path_expr.append(int(component))
            else:
                path_expr.append(component)

        hdoc = HierarchicalDocument(0, row)
        return hdoc.eval_path(path_expr)


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
