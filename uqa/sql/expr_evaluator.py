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

# pyright: reportArgumentType=false, reportOperatorIssue=false

from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pglast.ast import (
    A_ArrayExpr,
    A_Const,
    A_Expr,
    BoolExpr,
    CaseExpr,
    CoalesceExpr,
    ColumnRef,
    FuncCall,
    MinMaxExpr,
    NullTest,
    RangeVar,
    SelectStmt,
    SQLValueFunction,
    SubLink,
    TypeCast,
)
from pglast.ast import (
    Boolean as PgBoolean,
)
from pglast.ast import (
    Float as PgFloat,
)
from pglast.ast import (
    Integer as PgInteger,
)
from pglast.ast import (
    String as PgString,
)
from pglast.enums.parsenodes import A_Expr_Kind
from pglast.enums.primnodes import (
    BoolExprType,
    MinMaxOp,
    NullTestType,
    SQLValueFunctionOp,
    SubLinkType,
)


class ExprEvaluator:
    """Evaluate a pglast AST expression node against a data row.

    Each ``evaluate()`` call takes an AST node and a ``dict`` row and
    returns the computed scalar value.  The evaluator is stateless and
    reusable across rows.

    *subquery_executor* is an optional callback ``(SelectStmt) -> SQLResult``
    used to evaluate scalar subqueries (``EXPR_SUBLINK``) and
    ``IN`` subqueries (``ANY_SUBLINK``).
    """

    _DISPATCH_NAMES: dict[type, str] = {
        ColumnRef: "_eval_column_ref",
        A_Const: "_eval_const",
        A_Expr: "_eval_a_expr",
        FuncCall: "_eval_func_call",
        NullTest: "_eval_null_test",
        BoolExpr: "_eval_bool_expr",
        CaseExpr: "_eval_case",
        TypeCast: "_eval_type_cast",
        CoalesceExpr: "_eval_coalesce",
        SubLink: "_eval_sublink",
        A_ArrayExpr: "_eval_a_array_expr",
        MinMaxExpr: "_eval_min_max",
        SQLValueFunction: "_eval_sql_value_function",
    }

    def __init__(
        self,
        subquery_executor: Any = None,
        sequences: dict | None = None,
        outer_row: dict[str, Any] | None = None,
    ) -> None:
        self._subquery_executor = subquery_executor
        self._sequences = sequences
        self._subquery_cache: dict[int, Any] = {}
        self._outer_row = outer_row

    def evaluate(self, node: Any, row: dict[str, Any]) -> Any:
        """Evaluate *node* against *row* and return the result."""
        method_name = self._DISPATCH_NAMES.get(type(node))
        if method_name is not None:
            return getattr(self, method_name)(node, row)

        # NamedArgExpr: func(name => value) -- evaluate the inner arg
        if type(node).__name__ == "NamedArgExpr":
            return self.evaluate(node.arg, row)

        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    def _eval_a_array_expr(self, node: A_ArrayExpr, row: dict[str, Any]) -> Any:
        """Evaluate an array expression."""
        if node.elements is None:
            return []
        return [self.evaluate(e, row) for e in node.elements]

    # -- Leaf nodes ----------------------------------------------------

    def _eval_column_ref(self, node: ColumnRef, row: dict[str, Any]) -> Any:
        fields = node.fields
        # Handle qualified references like excluded.col or table.col
        if len(fields) >= 2 and hasattr(fields[0], "sval"):
            qualified = f"{fields[0].sval}.{fields[-1].sval}"
            if qualified in row:
                return row[qualified]
            # Correlated reference: resolve from outer row
            if self._outer_row is not None and qualified in self._outer_row:
                return self._outer_row[qualified]
        col_name = fields[-1].sval
        return row.get(col_name)

    @staticmethod
    def _eval_const(node: A_Const, row: dict[str, Any] | None = None) -> Any:
        if node.isnull:
            return None
        val = node.val
        if isinstance(val, PgInteger):
            return val.ival
        if isinstance(val, PgFloat):
            return float(val.fval)
        if isinstance(val, PgString):
            return val.sval
        if isinstance(val, PgBoolean):
            return val.boolval
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

        if kind == A_Expr_Kind.AEXPR_NULLIF:
            a = self.evaluate(node.lexpr, row)
            b = self.evaluate(node.rexpr, row)
            return None if a == b else a

        raise ValueError(f"Unsupported A_Expr kind: {kind}")

    def _eval_operator(self, node: A_Expr, row: dict[str, Any]) -> Any:
        op = node.name[0].sval
        left = self.evaluate(node.lexpr, row)
        right = self.evaluate(node.rexpr, row)

        # JSON field access operators (Def 5.2.3 -- path evaluation)
        if op == "->":
            return _json_access(left, right, as_text=False)
        if op == "->>":
            return _json_access(left, right, as_text=True)
        if op in ("#>", "#>>"):
            return _json_path_access(left, right, as_text=(op == "#>>"))
        if op == "@>":
            return _json_contains(left, right)
        if op == "<@":
            return _json_contains(right, left)
        if op == "?":
            return _json_has_key(left, right)
        if op == "?|":
            return _json_has_any_key(left, right)
        if op == "?&":
            return _json_has_all_keys(left, right)

        if op == "overlaps":
            # (start1, end1) OVERLAPS (start2, end2) comes as special operator
            return _overlaps(left, right)

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
        # Array type cast (e.g. ARRAY[]::integer[])
        if node.typeName.arrayBounds is not None:
            if value is None:
                return None
            return value if isinstance(value, list) else [value]
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

    def _is_correlated(self, node: Any) -> bool:
        """Check if a subquery contains correlated references."""
        inner_tables: set[str] = set()
        if isinstance(node, SelectStmt) and node.fromClause:
            for from_item in node.fromClause:
                if isinstance(from_item, RangeVar):
                    if from_item.alias:
                        inner_tables.add(from_item.alias.aliasname)
                    inner_tables.add(from_item.relname)
        return self._has_correlated_ref(node, inner_tables)

    def _has_correlated_ref(self, node: Any, inner_tables: set[str]) -> bool:
        """Recursively check if an AST node contains correlated ColumnRefs."""
        if isinstance(node, ColumnRef):
            if len(node.fields) >= 2:
                qualifier = node.fields[0].sval
                if qualifier not in inner_tables:
                    return True
            return False
        if isinstance(node, (tuple, list)):
            return any(self._has_correlated_ref(item, inner_tables) for item in node)
        if hasattr(node, "__slots__") and isinstance(node.__slots__, dict):
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is not None and self._has_correlated_ref(val, inner_tables):
                    return True
        return False

    def _eval_sublink(self, node: SubLink, row: dict[str, Any]) -> Any:
        if self._subquery_executor is None:
            raise ValueError("Subquery in expression requires a subquery executor")

        # Check if the subquery is uncorrelated and can be cached.
        correlated = self._is_correlated(node.subselect)
        cache_key = id(node)

        if correlated:
            # Build qualified outer row context for correlated references.
            # The inner query's ExprEvaluator resolves qualified ColumnRefs
            # (e.g., "e1.dept") against this context, eliminating the need
            # to clone the entire AST per outer row.
            outer_context = self._build_correlated_context(node.subselect, row)
            subselect = node.subselect
            result = self._subquery_executor(subselect, outer_row=outer_context)
        else:
            subselect = node.subselect

        link_type = SubLinkType(node.subLinkType)

        if link_type == SubLinkType.EXPR_SUBLINK:
            # Scalar subquery: (SELECT COUNT(*) FROM ...)
            if not correlated:
                cached = self._subquery_cache.get(cache_key)
                if cached is not None:
                    return cached
                result = self._subquery_executor(subselect)
            if not result.rows:
                value = None
            else:
                first_col = result.columns[0]
                value = result.rows[0][first_col]
            if not correlated:
                self._subquery_cache[cache_key] = value
            return value

        if link_type == SubLinkType.ANY_SUBLINK:
            # IN subquery: col IN (SELECT ...)
            left = self.evaluate(node.testexpr, row)
            if left is None:
                return False
            # For uncorrelated ANY, cache the value set.
            if not correlated:
                cached_set = self._subquery_cache.get(cache_key)
                if isinstance(cached_set, set):
                    return left in cached_set
                result = self._subquery_executor(subselect)
            if not result.columns:
                return False
            sub_col = result.columns[0]
            value_set = {r[sub_col] for r in result.rows}
            if not correlated:
                self._subquery_cache[cache_key] = value_set
            return left in value_set

        if link_type == SubLinkType.EXISTS_SUBLINK:
            # EXISTS (SELECT ...)
            if not correlated:
                cached = self._subquery_cache.get(cache_key)
                if cached is not None:
                    return cached
                result = self._subquery_executor(subselect)
            value = len(result.rows) > 0
            if not correlated:
                self._subquery_cache[cache_key] = value
            return value

        raise ValueError(f"Unsupported subquery type: {link_type.name}")

    def _build_correlated_context(
        self, subselect: Any, outer_row: dict[str, Any]
    ) -> dict[str, Any]:
        """Build a qualified-key dict for correlated reference resolution.

        For a subquery ``SELECT ... FROM t2 WHERE t2.x = t1.y``, where
        ``t1`` is the outer table, produces ``{"t1.y": <value>}`` so the
        inner evaluator can resolve the correlated ColumnRef without AST
        cloning.
        """
        cache_key = id(subselect)
        cached = self._subquery_cache.get(("_corr_refs", cache_key))
        if cached is None:
            inner_tables: set[str] = set()
            if isinstance(subselect, SelectStmt) and subselect.fromClause:
                for from_item in subselect.fromClause:
                    if isinstance(from_item, RangeVar):
                        if from_item.alias:
                            inner_tables.add(from_item.alias.aliasname)
                        inner_tables.add(from_item.relname)
            refs = self._collect_correlated_refs(subselect, inner_tables)
            self._subquery_cache[("_corr_refs", cache_key)] = refs
            cached = refs

        context: dict[str, Any] = {}
        for qualifier, col_name in cached:
            qualified_key = f"{qualifier}.{col_name}"
            val = outer_row.get(qualified_key)
            if val is None:
                val = outer_row.get(col_name)
            context[qualified_key] = val
        return context

    def _collect_correlated_refs(
        self, node: Any, inner_tables: set[str]
    ) -> list[tuple[str, str]]:
        """Collect all (qualifier, col_name) pairs for correlated ColumnRefs."""
        refs: list[tuple[str, str]] = []
        self._walk_for_correlated(node, inner_tables, refs)
        return refs

    def _walk_for_correlated(
        self, node: Any, inner_tables: set[str], refs: list[tuple[str, str]]
    ) -> None:
        if isinstance(node, ColumnRef):
            if len(node.fields) >= 2 and hasattr(node.fields[0], "sval"):
                qualifier = node.fields[0].sval
                if qualifier not in inner_tables:
                    col_name = node.fields[-1].sval
                    refs.append((qualifier, col_name))
            return
        if isinstance(node, (tuple, list)):
            for item in node:
                self._walk_for_correlated(item, inner_tables, refs)
            return
        if hasattr(node, "__slots__") and isinstance(node.__slots__, dict):
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is not None:
                    self._walk_for_correlated(val, inner_tables, refs)

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

    # -- MinMaxExpr (GREATEST / LEAST) ---------------------------------

    def _eval_min_max(self, node: MinMaxExpr, row: dict[str, Any]) -> Any:
        values = [self.evaluate(a, row) for a in node.args]
        non_null = [v for v in values if v is not None]
        if not non_null:
            return None
        if MinMaxOp(node.op) == MinMaxOp.IS_GREATEST:
            return max(non_null)
        return min(non_null)

    # -- SQLValueFunction (CURRENT_DATE, CURRENT_TIMESTAMP) -----------

    @staticmethod
    def _eval_sql_value_function(
        node: SQLValueFunction, row: dict[str, Any] | None = None
    ) -> Any:
        op = SQLValueFunctionOp(node.op)
        now = datetime.now(UTC)
        if op == SQLValueFunctionOp.SVFOP_CURRENT_DATE:
            return now.strftime("%Y-%m-%d")
        if op in (
            SQLValueFunctionOp.SVFOP_CURRENT_TIMESTAMP,
            SQLValueFunctionOp.SVFOP_CURRENT_TIMESTAMP_N,
        ):
            return now.strftime("%Y-%m-%dT%H:%M:%S")
        if op in (
            SQLValueFunctionOp.SVFOP_CURRENT_TIME,
            SQLValueFunctionOp.SVFOP_CURRENT_TIME_N,
        ):
            return now.strftime("%H:%M:%S")
        if op in (
            SQLValueFunctionOp.SVFOP_LOCALTIMESTAMP,
            SQLValueFunctionOp.SVFOP_LOCALTIMESTAMP_N,
        ):
            local_now = datetime.now()
            return local_now.strftime("%Y-%m-%dT%H:%M:%S")
        if op in (
            SQLValueFunctionOp.SVFOP_LOCALTIME,
            SQLValueFunctionOp.SVFOP_LOCALTIME_N,
        ):
            local_now = datetime.now()
            return local_now.strftime("%H:%M:%S")
        raise ValueError(f"Unsupported SQLValueFunction: {op.name}")

    # -- FuncCall (scalar functions) -----------------------------------

    _AGG_FUNCS = frozenset(
        {
            "count",
            "sum",
            "avg",
            "min",
            "max",
            "string_agg",
            "array_agg",
            "bool_and",
            "bool_or",
            "stddev",
            "stddev_pop",
            "stddev_samp",
            "variance",
            "var_pop",
            "var_samp",
            "percentile_cont",
            "percentile_disc",
            "mode",
            "json_object_agg",
            "jsonb_object_agg",
            "corr",
            "covar_pop",
            "covar_samp",
            "regr_count",
            "regr_avgx",
            "regr_avgy",
            "regr_sxx",
            "regr_syy",
            "regr_sxy",
            "regr_slope",
            "regr_intercept",
            "regr_r2",
        }
    )

    def _eval_func_call(self, node: FuncCall, row: dict[str, Any]) -> Any:
        func_name = node.funcname[-1].sval.lower()

        # For aggregate functions (used in HAVING), look up the
        # pre-computed value from the aggregated row.
        if func_name in self._AGG_FUNCS:
            col = self._agg_column_name(func_name, node)
            if col in row:
                return row[col]

        # Sequence functions
        if func_name in ("nextval", "currval", "setval"):
            return self._eval_sequence_func(func_name, node, row)

        if func_name == "path_agg":
            return self._eval_path_agg(node, row)
        if func_name == "path_value":
            return self._eval_path_value(node, row)
        args = [self.evaluate(a, row) for a in (node.args or ())]
        return _call_scalar_function(func_name, args)

    def _agg_column_name(self, func_name: str, node: FuncCall) -> str:
        """Compute the natural column name for an aggregate function.

        Mirrors the naming convention in _extract_agg_specs:
        count(*) -> "count", sum(age) -> "sum_age".
        """
        if node.agg_star or not node.args:
            return func_name
        arg = node.args[0]
        if isinstance(arg, ColumnRef):
            return f"{func_name}_{arg.fields[-1].sval}"
        return func_name

    def _eval_sequence_func(
        self, func_name: str, node: FuncCall, row: dict[str, Any]
    ) -> Any:
        if self._sequences is None:
            raise ValueError("No sequence store available")
        args = [self.evaluate(a, row) for a in (node.args or ())]
        seq_name = str(args[0]) if args else ""
        seq = self._sequences.get(seq_name)
        if seq is None:
            raise ValueError(f"Sequence '{seq_name}' does not exist")

        if func_name == "nextval":
            seq["current"] += seq["increment"]
            return seq["current"]
        if func_name == "currval":
            return seq["current"]
        if func_name == "setval":
            if len(args) < 2:
                raise ValueError("setval() requires 2 arguments")
            seq["current"] = int(args[1])
            return seq["current"]
        raise ValueError(f"Unknown sequence function: {func_name}")

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


def _json_access(obj: Any, key: Any, *, as_text: bool) -> Any:
    """JSON field access (Paper 1, Def 5.2.3 -- path evaluation).

    ``->`` returns JSON, ``->>`` returns text.
    """

    if obj is None:
        return None
    if isinstance(obj, str):
        obj = json.loads(obj)
    if isinstance(obj, dict):
        result = obj.get(str(key) if not isinstance(key, str) else key)
    elif isinstance(obj, list) and isinstance(key, int):
        result = obj[key] if 0 <= key < len(obj) else None
    else:
        return None
    if result is None:
        return None
    if as_text:
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return str(result)
    return result


def _json_path_access(obj: Any, path_str: Any, *, as_text: bool) -> Any:
    """JSON path access via #> / #>> operators.

    Path is a PostgreSQL text array literal like '{a,b,c}'.
    Follows Def 5.2.3 recursive path evaluation.
    """

    if obj is None or path_str is None:
        return None
    if isinstance(obj, str):
        obj = json.loads(obj)

    # Parse PostgreSQL array literal '{a,b,c}' into keys
    path = str(path_str).strip("{}")
    keys = [k.strip() for k in path.split(",")]

    for key in keys:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None

    if obj is None:
        return None
    if as_text:
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, ensure_ascii=False)
        return str(obj)
    return obj


def _json_contains(container: Any, contained: Any) -> bool:
    """JSON containment test (@> operator).

    Returns True if *container* contains *contained* at every level.
    """

    if container is None or contained is None:
        return False
    if isinstance(container, str):
        # Only parse if it looks like a JSON object/array, not a
        # plain scalar string (which would fail json.loads).
        stripped = container.strip()
        if stripped and stripped[0] in ("{", "["):
            container = json.loads(container)
    if isinstance(contained, str):
        stripped = contained.strip()
        if stripped and stripped[0] in ("{", "["):
            contained = json.loads(contained)

    if isinstance(contained, dict):
        if not isinstance(container, dict):
            return False
        for key, val in contained.items():
            if key not in container:
                return False
            if not _json_contains(container[key], val):
                return False
        return True
    if isinstance(contained, list):
        if not isinstance(container, list):
            return False
        for item in contained:
            if not any(_json_contains(c, item) for c in container):
                return False
        return True
    return container == contained


def _json_has_key(obj: Any, key: Any) -> bool:
    """JSONB ? operator: does the object contain the key?"""
    if obj is None:
        return False
    if isinstance(obj, str):
        obj = json.loads(obj)
    if isinstance(obj, dict):
        return str(key) in obj
    if isinstance(obj, list):
        return key in obj
    return False


def _parse_pg_array_literal(value: Any) -> list[str]:
    """Parse a PostgreSQL array literal like '{a,b,c}' into a list."""
    if isinstance(value, list):
        return [str(k) for k in value]
    s = str(value).strip()
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1]
        if not inner:
            return []
        return [part.strip() for part in inner.split(",")]
    return [s]


def _json_has_any_key(obj: Any, keys: Any) -> bool:
    """JSONB ?| operator: does the object contain any of the keys?"""
    if obj is None or keys is None:
        return False
    if isinstance(obj, str):
        obj = json.loads(obj)
    keys = _parse_pg_array_literal(keys)
    if isinstance(obj, dict):
        return any(k in obj for k in keys)
    return False


def _json_has_all_keys(obj: Any, keys: Any) -> bool:
    """JSONB ?& operator: does the object contain all of the keys?"""
    if obj is None or keys is None:
        return False
    if isinstance(obj, str):
        obj = json.loads(obj)
    keys = _parse_pg_array_literal(keys)
    if isinstance(obj, dict):
        return all(k in obj for k in keys)
    return False


def _overlaps(range1: Any, range2: Any) -> bool:
    """Test whether two date/time ranges overlap (OVERLAPS operator)."""

    if range1 is None or range2 is None:
        return False
    if isinstance(range1, (list, tuple)) and isinstance(range2, (list, tuple)):
        s1 = datetime.fromisoformat(str(range1[0]))
        e1 = datetime.fromisoformat(str(range1[1]))
        s2 = datetime.fromisoformat(str(range2[0]))
        e2 = datetime.fromisoformat(str(range2[1]))
        if s1 > e1:
            s1, e1 = e1, s1
        if s2 > e2:
            s2, e2 = e2, s2
        return s1 < e2 and s2 < e1
    return False


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
    "date": str,
    "timestamp": str,
    "timestamptz": str,
    "json": object,
    "jsonb": object,
    "uuid": str,
    "bytea": bytes,
}


def _cast_value(value: Any, type_name: str) -> Any:
    if type_name in ("json", "jsonb"):
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value
    if type_name == "uuid":
        return str(value)
    if type_name == "bytea":
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")
    if type_name == "interval":
        return str(value)
    cast_type = _CAST_MAP.get(type_name)
    if cast_type is None:
        raise ValueError(f"Unsupported CAST target type: {type_name}")
    if cast_type is bool:
        if isinstance(value, str):
            return value.lower() in ("true", "t", "1", "yes")
        return bool(value)
    return cast_type(value)


def _call_scalar_function(name: str, args: list[Any]) -> Any:
    fn = _SCALAR_FUNCTIONS.get(name)
    if fn is None:
        raise ValueError(f"Unknown scalar function: {name}")
    return fn(args)


# -- Scalar function helpers ------------------------------------------------
#
# Each helper takes ``(args: list[Any]) -> Any`` and implements one
# (or a small family of) SQL scalar function(s).  They are collected
# in ``_SCALAR_FUNCTIONS`` for O(1) dispatch by ``_call_scalar_function``.
#

# -- String helpers --


def _sf_upper(args: list[Any]) -> Any:
    return str(args[0]).upper() if args[0] is not None else None


def _sf_lower(args: list[Any]) -> Any:
    return str(args[0]).lower() if args[0] is not None else None


def _sf_length(args: list[Any]) -> Any:
    return len(str(args[0])) if args[0] is not None else None


def _sf_trim(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    chars = str(args[1]) if len(args) > 1 else None
    return str(args[0]).strip(chars)


def _sf_ltrim(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    chars = str(args[1]) if len(args) > 1 else None
    return str(args[0]).lstrip(chars)


def _sf_rtrim(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    chars = str(args[1]) if len(args) > 1 else None
    return str(args[0]).rstrip(chars)


def _sf_replace(args: list[Any]) -> Any:
    if any(a is None for a in args[:3]):
        return None
    return str(args[0]).replace(str(args[1]), str(args[2]))


def _sf_substring(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    s = str(args[0])
    start = int(args[1]) - 1 if len(args) > 1 else 0
    length = int(args[2]) if len(args) > 2 else len(s) - start
    return s[start : start + length]


def _sf_concat(args: list[Any]) -> Any:
    return "".join(str(a) if a is not None else "" for a in args)


def _sf_concat_ws(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    sep = str(args[0])
    return sep.join(str(a) for a in args[1:] if a is not None)


def _sf_left(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return str(args[0])[: int(args[1])]


def _sf_right(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    n = int(args[1])
    return str(args[0])[-n:] if n > 0 else ""


def _sf_initcap(args: list[Any]) -> Any:
    return str(args[0]).title() if args[0] is not None else None


# -- Math helpers --


def _sf_abs(args: list[Any]) -> Any:
    return abs(args[0]) if args[0] is not None else None


def _sf_round(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    ndigits = int(args[1]) if len(args) > 1 else 0
    return round(args[0], ndigits)


def _sf_ceil(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.ceil(args[0])


def _sf_floor(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.floor(args[0])


# -- Additional string helpers --


def _sf_translate(args: list[Any]) -> Any:
    if any(a is None for a in args[:3]):
        return None
    s, from_chars, to_chars = str(args[0]), str(args[1]), str(args[2])
    table = str.maketrans(
        from_chars,
        to_chars[: len(from_chars)].ljust(len(from_chars)),
        from_chars[len(to_chars) :] if len(to_chars) < len(from_chars) else "",
    )
    return s.translate(table)


def _sf_ascii(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    s = str(args[0])
    return ord(s[0]) if s else 0


def _sf_chr(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return chr(int(args[0]))


def _sf_starts_with(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return str(args[0]).startswith(str(args[1]))


def _sf_position(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    # pglast: POSITION(sub IN str) -> position(str, sub)
    idx = str(args[0]).find(str(args[1]))
    return idx + 1 if idx >= 0 else 0


def _sf_strpos(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    idx = str(args[0]).find(str(args[1]))
    return idx + 1 if idx >= 0 else 0


def _sf_octet_length(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return len(str(args[0]).encode("utf-8"))


def _sf_md5(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return hashlib.md5(str(args[0]).encode("utf-8")).hexdigest()


def _sf_format(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    fmt = str(args[0])
    fmt = fmt.replace("%I", "%s").replace("%L", "'%s'")
    return fmt % tuple(args[1:])


def _sf_regexp_match(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    m = re.search(str(args[1]), str(args[0]))
    if m is None:
        return None
    groups = m.groups()
    return list(groups) if groups else [m.group()]


def _sf_regexp_matches(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    flags_str = str(args[2]) if len(args) > 2 and args[2] is not None else ""
    flags = re.DOTALL if "s" in flags_str else 0
    if "i" in flags_str:
        flags |= re.IGNORECASE
    if "g" in flags_str:
        return [
            list(m) if isinstance(m, tuple) else [m]
            for m in re.findall(str(args[1]), str(args[0]), flags)
        ]
    m = re.search(str(args[1]), str(args[0]), flags)
    if m is None:
        return None
    groups = m.groups()
    return [list(groups)] if groups else [[m.group()]]


def _sf_regexp_replace(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    replacement = str(args[2]) if len(args) > 2 and args[2] is not None else ""
    flags_str = str(args[3]) if len(args) > 3 and args[3] is not None else ""
    count = 0 if "g" in flags_str else 1
    flags = 0
    if "i" in flags_str:
        flags |= re.IGNORECASE
    return re.sub(str(args[1]), replacement, str(args[0]), count=count, flags=flags)


def _sf_overlay(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None or args[2] is None:
        return None
    s = str(args[0])
    repl = str(args[1])
    pos = int(args[2]) - 1  # 1-based to 0-based
    length = int(args[3]) if len(args) > 3 and args[3] is not None else len(repl)
    return s[:pos] + repl + s[pos + length :]


def _sf_lpad(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    s, length = str(args[0]), int(args[1])
    fill = str(args[2]) if len(args) > 2 and args[2] is not None else " "
    if len(s) >= length:
        return s[:length]
    pad_len = length - len(s)
    pad = (fill * (pad_len // len(fill) + 1))[:pad_len]
    return pad + s


def _sf_rpad(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    s, length = str(args[0]), int(args[1])
    fill = str(args[2]) if len(args) > 2 and args[2] is not None else " "
    if len(s) >= length:
        return s[:length]
    pad_len = length - len(s)
    pad = (fill * (pad_len // len(fill) + 1))[:pad_len]
    return s + pad


def _sf_repeat(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return str(args[0]) * int(args[1])


def _sf_reverse(args: list[Any]) -> Any:
    return str(args[0])[::-1] if args[0] is not None else None


def _sf_split_part(args: list[Any]) -> Any:
    if any(a is None for a in args[:3]):
        return None
    parts = str(args[0]).split(str(args[1]))
    n = int(args[2])
    return parts[n - 1] if 1 <= n <= len(parts) else ""


def _sf_encode(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    data = args[0]
    if isinstance(data, str):
        data = data.encode("utf-8")
    fmt = str(args[1]).lower()
    if fmt == "base64":
        return base64.b64encode(data).decode("ascii")
    if fmt == "hex":
        return data.hex()
    if fmt == "escape":
        parts = []
        for b in data:
            if 32 <= b < 127 and b != 92:
                parts.append(chr(b))
            else:
                parts.append(f"\\{b:03o}")
        return "".join(parts)
    raise ValueError(f"Unsupported encode format: {fmt}")


def _sf_decode(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    text = str(args[0])
    fmt = str(args[1]).lower()
    if fmt == "base64":
        return base64.b64decode(text)
    if fmt == "hex":
        return bytes.fromhex(text)
    if fmt == "escape":
        result = bytearray()
        i = 0
        while i < len(text):
            if (
                text[i] == "\\"
                and i + 3 < len(text)
                and re.match(r"[0-7]{3}", text[i + 1 : i + 4])
            ):
                result.append(int(text[i + 1 : i + 4], 8))
                i += 4
            else:
                result.append(ord(text[i]))
                i += 1
        return bytes(result)
    raise ValueError(f"Unsupported decode format: {fmt}")


def _sf_regexp_split_to_array(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    text = str(args[0])
    pattern = str(args[1])
    flags = 0
    if len(args) > 2 and args[2] is not None:
        flags_str = str(args[2])
        if "i" in flags_str:
            flags |= re.IGNORECASE
    return re.split(pattern, text, flags=flags)


def _sf_power(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return args[0] ** args[1]


def _sf_sqrt(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.sqrt(args[0])


def _sf_log(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    if len(args) > 1 and args[1] is not None:
        return math.log(args[1]) / math.log(args[0])
    return math.log10(args[0])


def _sf_ln(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.log(args[0])


def _sf_exp(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.exp(args[0])


def _sf_mod(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return args[0] % args[1] if args[1] != 0 else None


def _sf_trunc(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    if len(args) > 1 and args[1] is not None:
        factor = 10 ** int(args[1])
        return math.trunc(args[0] * factor) / factor
    return math.trunc(args[0])


def _sf_sign(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return (args[0] > 0) - (args[0] < 0)


def _sf_pi(args: list[Any]) -> Any:
    return math.pi


def _sf_random(args: list[Any]) -> Any:
    return random.random()


def _sf_cbrt(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    v = args[0]
    return -((-v) ** (1.0 / 3.0)) if v < 0 else v ** (1.0 / 3.0)


def _sf_degrees(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.degrees(args[0])


def _sf_radians(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.radians(args[0])


def _sf_sin(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.sin(args[0])


def _sf_cos(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.cos(args[0])


def _sf_tan(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.tan(args[0])


def _sf_asin(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.asin(args[0])


def _sf_acos(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.acos(args[0])


def _sf_atan(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return math.atan(args[0])


def _sf_atan2(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return math.atan2(args[0], args[1])


def _sf_div(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    if args[1] == 0:
        return None
    return int(args[0] // args[1])


def _sf_gcd(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return math.gcd(int(args[0]), int(args[1]))


def _sf_lcm(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    a, b = int(args[0]), int(args[1])
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def _sf_width_bucket(args: list[Any]) -> Any:
    if any(a is None for a in args[:4]):
        return None
    val, lo, hi, n = args[0], args[1], args[2], int(args[3])
    if hi == lo or n <= 0:
        return None
    if val < lo:
        return 0
    if val >= hi:
        return n + 1
    return int((val - lo) / ((hi - lo) / n)) + 1


def _sf_min_scale(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    d = Decimal(str(args[0])).normalize()
    exp = d.as_tuple().exponent
    return -exp if exp < 0 else 0


def _sf_trim_scale(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    d = Decimal(str(args[0])).normalize()
    if d == d.to_integral_value():
        return int(d)
    return float(d)


# -- Date/time scalar helpers --


def _sf_now(args: list[Any]) -> Any:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def _sf_extract(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return _extract_datetime_field(str(args[0]).lower(), str(args[1]))


def _sf_date_trunc(args: list[Any]) -> Any:
    if args[0] is None or args[1] is None:
        return None
    return _date_trunc(str(args[0]).lower(), str(args[1]))


def _sf_make_timestamp(args: list[Any]) -> Any:
    if any(a is None for a in args[:6]):
        return None
    y, mo, d = int(args[0]), int(args[1]), int(args[2])
    h, mi, s = int(args[3]), int(args[4]), float(args[5])
    sec = int(s)
    usec = int((s - sec) * 1_000_000)
    dt = datetime(y, mo, d, h, mi, sec, usec)
    return dt.isoformat()


def _sf_make_interval(args: list[Any]) -> Any:
    years = int(args[0]) if len(args) > 0 and args[0] is not None else 0
    months = int(args[1]) if len(args) > 1 and args[1] is not None else 0
    weeks = int(args[2]) if len(args) > 2 and args[2] is not None else 0
    days = int(args[3]) if len(args) > 3 and args[3] is not None else 0
    hours = int(args[4]) if len(args) > 4 and args[4] is not None else 0
    mins = int(args[5]) if len(args) > 5 and args[5] is not None else 0
    secs = float(args[6]) if len(args) > 6 and args[6] is not None else 0
    total_days = years * 365 + months * 30 + weeks * 7 + days
    td = timedelta(days=total_days, hours=hours, minutes=mins, seconds=secs)
    total_seconds = int(td.total_seconds())
    h_part = total_seconds // 3600
    m_part = (total_seconds % 3600) // 60
    s_part = total_seconds % 60
    return f"{h_part:02d}:{m_part:02d}:{s_part:02d}"


def _sf_make_date(args: list[Any]) -> Any:
    if any(a is None for a in args[:3]):
        return None
    return date(int(args[0]), int(args[1]), int(args[2])).isoformat()


def _sf_to_char(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return _to_char(str(args[0]), str(args[1]) if len(args) > 1 else "")


def _sf_to_date(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return _to_date(str(args[0]), str(args[1]) if len(args) > 1 else "")


def _sf_to_timestamp(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    return _to_timestamp(str(args[0]), str(args[1]) if len(args) > 1 else "")


def _sf_age(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    return _age(args)


def _sf_to_number(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    s = str(args[0])
    cleaned = re.sub(r"[^\d.\-]", "", s)
    if not cleaned or cleaned == "-":
        return 0
    return float(cleaned)


def _sf_overlaps(args: list[Any]) -> Any:
    if len(args) < 4 or any(a is None for a in args[:4]):
        return None
    s1 = datetime.fromisoformat(str(args[0]))
    e1 = datetime.fromisoformat(str(args[1]))
    s2 = datetime.fromisoformat(str(args[2]))
    e2 = datetime.fromisoformat(str(args[3]))
    if s1 > e1:
        s1, e1 = e1, s1
    if s2 > e2:
        s2, e2 = e2, s2
    return s1 < e2 and s2 < e1


def _sf_isfinite(args: list[Any]) -> Any:
    if args[0] is None:
        return None
    val = str(args[0]).strip().lower()
    return val not in ("infinity", "-infinity")


def _sf_clock_timestamp(args: list[Any]) -> Any:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def _sf_timeofday(args: list[Any]) -> Any:
    now = datetime.now(UTC)
    weekday = now.strftime("%a")
    month = now.strftime("%b")
    day = now.strftime("%d")
    time_part = now.strftime("%H:%M:%S.%f")
    year = now.strftime("%Y")
    return f"{weekday} {month} {day} {time_part} {year} UTC"


# -- Type checking helpers --


def _sf_typeof(args: list[Any]) -> Any:
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


# -- JSON scalar helpers --


def _sf_json_build_object(args: list[Any]) -> Any:
    return _json_build_object(args)


def _sf_json_build_array(args: list[Any]) -> Any:
    return list(args)


def _sf_json_typeof(args: list[Any]) -> Any:
    return _json_typeof(args[0] if args else None)


def _sf_json_array_length(args: list[Any]) -> Any:
    return _json_array_length(args[0] if args else None)


def _sf_json_extract_path(args: list[Any]) -> Any:
    return _json_extract_path(args, as_text=False)


def _sf_json_extract_path_text(args: list[Any]) -> Any:
    return _json_extract_path(args, as_text=True)


def _sf_to_json(args: list[Any]) -> Any:
    return args[0] if args else None


def _sf_jsonb_set(args: list[Any]) -> Any:
    return _jsonb_set(args)


def _sf_json_each(args: list[Any]) -> Any:
    return _json_each(args, as_text=False)


def _sf_json_each_text(args: list[Any]) -> Any:
    return _json_each(args, as_text=True)


def _sf_json_array_elements(args: list[Any]) -> Any:
    return _json_array_elements(args, as_text=False)


def _sf_json_array_elements_text(args: list[Any]) -> Any:
    return _json_array_elements(args, as_text=True)


def _sf_json_object_keys(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    obj = args[0]
    if isinstance(obj, str):
        obj = json.loads(obj)
    if isinstance(obj, dict):
        return list(obj.keys())
    return None


def _sf_jsonb_strip_nulls(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    obj = args[0]
    if isinstance(obj, str):
        obj = json.loads(obj)

    def _strip_nulls(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: _strip_nulls(val) for k, val in v.items() if val is not None}
        return v

    return _strip_nulls(obj)


# -- UUID helpers --


def _sf_gen_random_uuid(args: list[Any]) -> Any:
    return str(uuid.uuid4())


# -- Array helpers --


def _sf_array_length(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0]
    if isinstance(arr, str):
        arr = json.loads(arr)
    if not isinstance(arr, list):
        return None
    return len(arr)


def _sf_array_upper(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0]
    if isinstance(arr, str):
        arr = json.loads(arr)
    if not isinstance(arr, list) or not arr:
        return None
    return len(arr)


def _sf_array_lower(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0]
    if isinstance(arr, str):
        arr = json.loads(arr)
    if not isinstance(arr, list) or not arr:
        return None
    return 1


def _sf_array_cat(args: list[Any]) -> Any:
    if len(args) < 2:
        return None
    a = args[0] if isinstance(args[0], list) else []
    b = args[1] if isinstance(args[1], list) else []
    return a + b


def _sf_array_append(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0] if isinstance(args[0], list) else [args[0]]
    return [*arr, args[1]] if len(args) > 1 else arr


def _sf_array_remove(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0] if isinstance(args[0], list) else []
    val = args[1] if len(args) > 1 else None
    return [x for x in arr if x != val]


def _sf_cardinality(args: list[Any]) -> Any:
    if not args or args[0] is None:
        return None
    arr = args[0]
    if isinstance(arr, str):
        arr = json.loads(arr)
    if not isinstance(arr, list):
        return None
    return len(arr)


# -- Spatial functions -----------------------------------------------------


def _sf_point(args: list[Any]) -> list[float]:
    """POINT(x, y) -> [x, y]."""
    if len(args) != 2:
        raise ValueError("POINT() requires exactly 2 arguments")
    return [float(args[0]), float(args[1])]


def _sf_st_distance(args: list[Any]) -> float | None:
    """ST_Distance(point1, point2) -> distance in meters (Haversine)."""
    from uqa.storage.spatial_index import haversine_distance

    if len(args) != 2:
        raise ValueError("ST_Distance() requires 2 arguments")
    p1, p2 = args[0], args[1]
    if p1 is None or p2 is None:
        return None
    if isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)):
        return haversine_distance(
            float(p1[1]), float(p1[0]), float(p2[1]), float(p2[0])
        )
    raise ValueError("ST_Distance() arguments must be POINT values ([x, y])")


def _sf_st_within(args: list[Any]) -> bool | None:
    """ST_Within(point1, point2, distance_meters) -> boolean."""
    from uqa.storage.spatial_index import haversine_distance

    if len(args) != 3:
        raise ValueError("ST_Within() requires 3 arguments")
    p1, p2 = args[0], args[1]
    if p1 is None or p2 is None:
        return None
    dist_limit = float(args[2])
    if isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)):
        dist = haversine_distance(
            float(p1[1]), float(p1[0]), float(p2[1]), float(p2[0])
        )
        return dist <= dist_limit
    raise ValueError("ST_Within() first two arguments must be POINT values ([x, y])")


def _sf_st_dwithin(args: list[Any]) -> bool | None:
    """ST_DWithin(point1, point2, distance_meters) -> boolean.

    Alias for ST_Within.
    """
    return _sf_st_within(args)


# -- Dispatch table --------------------------------------------------------

_SCALAR_FUNCTIONS: dict[str, Any] = {
    "upper": _sf_upper,
    "lower": _sf_lower,
    "length": _sf_length,
    "trim": _sf_trim,
    "btrim": _sf_trim,
    "ltrim": _sf_ltrim,
    "rtrim": _sf_rtrim,
    "replace": _sf_replace,
    "substring": _sf_substring,
    "substr": _sf_substring,
    "concat": _sf_concat,
    "concat_ws": _sf_concat_ws,
    "left": _sf_left,
    "right": _sf_right,
    "initcap": _sf_initcap,
    "translate": _sf_translate,
    "ascii": _sf_ascii,
    "chr": _sf_chr,
    "starts_with": _sf_starts_with,
    "char_length": _sf_length,
    "character_length": _sf_length,
    "position": _sf_position,
    "strpos": _sf_strpos,
    "octet_length": _sf_octet_length,
    "md5": _sf_md5,
    "format": _sf_format,
    "regexp_match": _sf_regexp_match,
    "regexp_matches": _sf_regexp_matches,
    "regexp_replace": _sf_regexp_replace,
    "overlay": _sf_overlay,
    "lpad": _sf_lpad,
    "rpad": _sf_rpad,
    "repeat": _sf_repeat,
    "reverse": _sf_reverse,
    "split_part": _sf_split_part,
    "encode": _sf_encode,
    "decode": _sf_decode,
    "regexp_split_to_array": _sf_regexp_split_to_array,
    "abs": _sf_abs,
    "round": _sf_round,
    "ceil": _sf_ceil,
    "ceiling": _sf_ceil,
    "floor": _sf_floor,
    "power": _sf_power,
    "pow": _sf_power,
    "sqrt": _sf_sqrt,
    "log": _sf_log,
    "log10": _sf_log,
    "ln": _sf_ln,
    "exp": _sf_exp,
    "mod": _sf_mod,
    "trunc": _sf_trunc,
    "sign": _sf_sign,
    "pi": _sf_pi,
    "random": _sf_random,
    "cbrt": _sf_cbrt,
    "degrees": _sf_degrees,
    "radians": _sf_radians,
    "sin": _sf_sin,
    "cos": _sf_cos,
    "tan": _sf_tan,
    "asin": _sf_asin,
    "acos": _sf_acos,
    "atan": _sf_atan,
    "atan2": _sf_atan2,
    "div": _sf_div,
    "gcd": _sf_gcd,
    "lcm": _sf_lcm,
    "width_bucket": _sf_width_bucket,
    "min_scale": _sf_min_scale,
    "trim_scale": _sf_trim_scale,
    "now": _sf_now,
    "extract": _sf_extract,
    "date_part": _sf_extract,
    "date_trunc": _sf_date_trunc,
    "make_timestamp": _sf_make_timestamp,
    "make_interval": _sf_make_interval,
    "make_date": _sf_make_date,
    "to_char": _sf_to_char,
    "to_date": _sf_to_date,
    "to_timestamp": _sf_to_timestamp,
    "age": _sf_age,
    "to_number": _sf_to_number,
    "overlaps": _sf_overlaps,
    "isfinite": _sf_isfinite,
    "clock_timestamp": _sf_clock_timestamp,
    "timeofday": _sf_timeofday,
    "typeof": _sf_typeof,
    "json_build_object": _sf_json_build_object,
    "jsonb_build_object": _sf_json_build_object,
    "json_build_array": _sf_json_build_array,
    "jsonb_build_array": _sf_json_build_array,
    "json_typeof": _sf_json_typeof,
    "jsonb_typeof": _sf_json_typeof,
    "json_array_length": _sf_json_array_length,
    "jsonb_array_length": _sf_json_array_length,
    "json_extract_path": _sf_json_extract_path,
    "json_extract_path_text": _sf_json_extract_path_text,
    "jsonb_extract_path": _sf_json_extract_path,
    "jsonb_extract_path_text": _sf_json_extract_path_text,
    "to_json": _sf_to_json,
    "to_jsonb": _sf_to_json,
    "row_to_json": _sf_to_json,
    "jsonb_set": _sf_jsonb_set,
    "jsonb_insert": _sf_jsonb_set,
    "json_each": _sf_json_each,
    "jsonb_each": _sf_json_each,
    "json_each_text": _sf_json_each_text,
    "jsonb_each_text": _sf_json_each_text,
    "json_array_elements": _sf_json_array_elements,
    "jsonb_array_elements": _sf_json_array_elements,
    "json_array_elements_text": _sf_json_array_elements_text,
    "jsonb_array_elements_text": _sf_json_array_elements_text,
    "json_object_keys": _sf_json_object_keys,
    "jsonb_object_keys": _sf_json_object_keys,
    "jsonb_strip_nulls": _sf_jsonb_strip_nulls,
    "json_strip_nulls": _sf_jsonb_strip_nulls,
    "gen_random_uuid": _sf_gen_random_uuid,
    "array_length": _sf_array_length,
    "array_upper": _sf_array_upper,
    "array_lower": _sf_array_lower,
    "array_cat": _sf_array_cat,
    "array_append": _sf_array_append,
    "array_remove": _sf_array_remove,
    "cardinality": _sf_cardinality,
    "point": _sf_point,
    "st_distance": _sf_st_distance,
    "st_within": _sf_st_within,
    "st_dwithin": _sf_st_dwithin,
}


def _extract_datetime_field(field: str, timestamp_str: str) -> Any:
    """Extract a field from a timestamp/date string (EXTRACT / DATE_PART)."""

    dt = datetime.fromisoformat(timestamp_str)
    if field == "year":
        return dt.year
    if field == "month":
        return dt.month
    if field == "day":
        return dt.day
    if field == "hour":
        return dt.hour
    if field == "minute":
        return dt.minute
    if field == "second":
        return dt.second
    if field == "dow":
        # PostgreSQL: Sunday=0, Monday=1, ..., Saturday=6
        return dt.isoweekday() % 7
    if field == "doy":
        return dt.timetuple().tm_yday
    if field == "epoch":
        return dt.timestamp()
    if field == "quarter":
        return (dt.month - 1) // 3 + 1
    if field == "week":
        return dt.isocalendar()[1]
    raise ValueError(f"Unknown EXTRACT field: {field}")


def _date_trunc(precision: str, timestamp_str: str) -> str:
    """Truncate a timestamp to the given precision (DATE_TRUNC)."""

    dt = datetime.fromisoformat(timestamp_str)
    if precision == "year":
        dt = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif precision == "month":
        dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif precision == "day":
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif precision == "hour":
        dt = dt.replace(minute=0, second=0, microsecond=0)
    elif precision == "minute":
        dt = dt.replace(second=0, microsecond=0)
    elif precision == "second":
        dt = dt.replace(microsecond=0)
    else:
        raise ValueError(f"Unknown DATE_TRUNC precision: {precision}")
    return dt.isoformat()


# -- JSON helpers (Paper 1, Section 5.2-5.3) ----------------------------


def _json_build_object(args: list[Any]) -> dict:
    """Build a JSON object from alternating key-value pairs."""
    if len(args) % 2 != 0:
        raise ValueError("json_build_object requires an even number of arguments")
    result: dict = {}
    for i in range(0, len(args), 2):
        key = str(args[i]) if args[i] is not None else "null"
        result[key] = args[i + 1]
    return result


def _json_typeof(value: Any) -> str | None:
    """Return the JSON type name of a value."""
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


def _json_array_length(value: Any) -> int | None:
    """Return the number of elements in a JSON array."""

    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, list):
        return len(value)
    return None


def _json_extract_path(args: list[Any], *, as_text: bool) -> Any:
    """Extract a value from a JSON document by path keys.

    Implements Paper 1, Definition 5.2.3 (recursive path evaluation):
    ``eval(h, [k1, k2, ...])``
    """

    if not args or args[0] is None:
        return None
    obj = args[0]
    if isinstance(obj, str):
        obj = json.loads(obj)
    for key in args[1:]:
        if key is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(str(key))
        elif isinstance(obj, list):
            idx = int(key)
            obj = obj[idx] if 0 <= idx < len(obj) else None
        else:
            return None
        if obj is None:
            return None
    if as_text:
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, ensure_ascii=False)
        return str(obj)
    return obj


def _jsonb_set(args: list[Any]) -> Any:
    """Implement JSONB_SET(target, path, new_value [, create_if_missing]).

    Sets a value in a JSON document at the given path.
    """

    if len(args) < 3 or args[0] is None:
        return None
    target = args[0]
    if isinstance(target, str):
        target = json.loads(target)

    path_str = str(args[1]).strip("{}")
    keys = [k.strip() for k in path_str.split(",")]
    new_value = args[2]
    create = bool(args[3]) if len(args) > 3 else True

    import copy

    result = copy.deepcopy(target)
    obj = result
    for _i, key in enumerate(keys[:-1]):
        if isinstance(obj, dict):
            if key not in obj:
                if not create:
                    return result
                obj[key] = {}
            obj = obj[key]
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (ValueError, IndexError):
                return result
        else:
            return result

    last_key = keys[-1]
    if isinstance(obj, dict):
        if last_key in obj or create:
            obj[last_key] = new_value
    elif isinstance(obj, list):
        try:
            obj[int(last_key)] = new_value
        except (ValueError, IndexError):
            pass
    return result


def _json_each(args: list[Any], *, as_text: bool) -> list[dict]:
    """Expand a JSON object into key-value rows."""

    if not args or args[0] is None:
        return []
    obj = args[0]
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict):
        return []
    rows = []
    for k, v in obj.items():
        if as_text:
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            else:
                v = str(v) if v is not None else None
        rows.append({"key": k, "value": v})
    return rows


def _json_array_elements(args: list[Any], *, as_text: bool) -> list[Any]:
    """Expand a JSON array into individual elements."""

    if not args or args[0] is None:
        return []
    arr = args[0]
    if isinstance(arr, str):
        arr = json.loads(arr)
    if not isinstance(arr, list):
        return []
    if as_text:
        result_list = []
        for v in arr:
            if isinstance(v, (dict, list)):
                result_list.append(json.dumps(v, ensure_ascii=False))
            else:
                result_list.append(str(v) if v is not None else None)
        return result_list
    return arr


# -- Date/time formatting helpers ----------------------------------------

_PG_TO_STRFTIME: list[tuple[str, str]] = [
    ("YYYY", "%Y"),
    ("YY", "%y"),
    ("MM", "%m"),
    ("DD", "%d"),
    ("HH24", "%H"),
    ("HH12", "%I"),
    ("HH", "%H"),
    ("MI", "%M"),
    ("SS", "%S"),
    ("US", "%f"),
    ("AM", "%p"),
    ("PM", "%p"),
    ("Month", "%B"),
    ("Mon", "%b"),
    ("Day", "%A"),
    ("Dy", "%a"),
    ("TZ", "%Z"),
]


def _pg_format_to_strftime(fmt: str) -> str:
    """Convert a PostgreSQL date format string to Python strftime format."""
    result = fmt
    for pg, py in _PG_TO_STRFTIME:
        result = result.replace(pg, py)
    return result


def _to_char(value: str, fmt: str) -> str:
    """TO_CHAR(timestamp, format)"""

    try:
        dt = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return str(value)
    py_fmt = _pg_format_to_strftime(fmt)
    return dt.strftime(py_fmt)


def _to_date(text: str, fmt: str) -> str:
    """TO_DATE(text, format) -- returns ISO date string."""

    py_fmt = _pg_format_to_strftime(fmt)
    try:
        dt = datetime.strptime(text, py_fmt)
    except (ValueError, TypeError):
        return text
    return dt.date().isoformat()


def _to_timestamp(text: str, fmt: str) -> str:
    """TO_TIMESTAMP(text, format) -- returns ISO timestamp string."""

    py_fmt = _pg_format_to_strftime(fmt)
    try:
        dt = datetime.strptime(text, py_fmt)
    except (ValueError, TypeError):
        return text
    return dt.isoformat()


def _age(args: list[Any]) -> str:
    """AGE(timestamp1 [, timestamp2]) -- returns interval-like string."""

    try:
        dt1 = datetime.fromisoformat(str(args[0]))
        dt2 = (
            datetime.fromisoformat(str(args[1]))
            if len(args) > 1 and args[1] is not None
            else datetime.now()
        )
    except (ValueError, TypeError):
        return ""
    delta = dt1 - dt2
    total_days = abs(delta.days)
    years = total_days // 365
    months = (total_days % 365) // 30
    days = (total_days % 365) % 30
    parts: list[str] = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} mon{'s' if months != 1 else ''}")
    if days or not parts:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    return " ".join(parts)
