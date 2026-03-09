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
    A_ArrayExpr,
    A_Const,
    A_Expr,
    BoolExpr,
    Boolean as PgBoolean,
    CaseExpr,
    CoalesceExpr,
    ColumnRef,
    Float as PgFloat,
    FuncCall,
    Integer as PgInteger,
    MinMaxExpr,
    NullTest,
    RangeVar,
    SQLValueFunction,
    SelectStmt,
    String as PgString,
    SubLink,
    TypeCast,
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

    def __init__(
        self,
        subquery_executor: Any = None,
        sequences: dict | None = None,
    ) -> None:
        self._subquery_executor = subquery_executor
        self._sequences = sequences

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

        if isinstance(node, A_ArrayExpr):
            if node.elements is None:
                return []
            return [self.evaluate(e, row) for e in node.elements]

        if isinstance(node, MinMaxExpr):
            return self._eval_min_max(node, row)

        if isinstance(node, SQLValueFunction):
            return self._eval_sql_value_function(node)

        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    # -- Leaf nodes ----------------------------------------------------

    @staticmethod
    def _eval_column_ref(node: ColumnRef, row: dict[str, Any]) -> Any:
        fields = node.fields
        # Handle qualified references like excluded.col or table.col
        if len(fields) >= 2 and hasattr(fields[0], "sval"):
            qualified = f"{fields[0].sval}.{fields[-1].sval}"
            if qualified in row:
                return row[qualified]
        col_name = fields[-1].sval
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
    def _eval_sql_value_function(node: SQLValueFunction) -> Any:
        from datetime import datetime, timezone

        op = SQLValueFunctionOp(node.op)
        now = datetime.now(timezone.utc)
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

    _AGG_FUNCS = frozenset({
        "count", "sum", "avg", "min", "max", "string_agg",
        "array_agg", "bool_and", "bool_or",
        "stddev", "stddev_pop", "stddev_samp",
        "variance", "var_pop", "var_samp",
        "percentile_cont", "percentile_disc", "mode",
        "json_object_agg", "jsonb_object_agg",
    })

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
    import json as json_mod

    if obj is None:
        return None
    if isinstance(obj, str):
        obj = json_mod.loads(obj)
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
            return json_mod.dumps(result, ensure_ascii=False)
        return str(result)
    return result


def _json_path_access(obj: Any, path_str: Any, *, as_text: bool) -> Any:
    """JSON path access via #> / #>> operators.

    Path is a PostgreSQL text array literal like '{a,b,c}'.
    Follows Def 5.2.3 recursive path evaluation.
    """
    import json as json_mod

    if obj is None or path_str is None:
        return None
    if isinstance(obj, str):
        obj = json_mod.loads(obj)

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
            return json_mod.dumps(obj, ensure_ascii=False)
        return str(obj)
    return obj


def _json_contains(container: Any, contained: Any) -> bool:
    """JSON containment test (@> operator).

    Returns True if *container* contains *contained* at every level.
    """
    import json as json_mod

    if container is None or contained is None:
        return False
    if isinstance(container, str):
        # Only parse if it looks like a JSON object/array, not a
        # plain scalar string (which would fail json.loads).
        stripped = container.strip()
        if stripped and stripped[0] in ('{', '['):
            container = json_mod.loads(container)
    if isinstance(contained, str):
        stripped = contained.strip()
        if stripped and stripped[0] in ('{', '['):
            contained = json_mod.loads(contained)

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
        import json as json_mod
        obj = json_mod.loads(obj)
    if isinstance(obj, dict):
        return str(key) in obj
    if isinstance(obj, list):
        return key in obj
    return False


def _json_has_any_key(obj: Any, keys: Any) -> bool:
    """JSONB ?| operator: does the object contain any of the keys?"""
    if obj is None or keys is None:
        return False
    if isinstance(obj, str):
        import json as json_mod
        obj = json_mod.loads(obj)
    if not isinstance(keys, list):
        keys = [keys]
    if isinstance(obj, dict):
        return any(str(k) in obj for k in keys)
    return False


def _json_has_all_keys(obj: Any, keys: Any) -> bool:
    """JSONB ?& operator: does the object contain all of the keys?"""
    if obj is None or keys is None:
        return False
    if isinstance(obj, str):
        import json as json_mod
        obj = json_mod.loads(obj)
    if not isinstance(keys, list):
        keys = [keys]
    if isinstance(obj, dict):
        return all(str(k) in obj for k in keys)
    return False


def _overlaps(range1: Any, range2: Any) -> bool:
    """Test whether two date/time ranges overlap (OVERLAPS operator)."""
    from datetime import datetime
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
    import json as json_mod

    if type_name in ("json", "jsonb"):
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json_mod.loads(value)
        return value
    if type_name == "uuid":
        return str(value)
    if type_name == "bytea":
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")
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

    # Additional string functions
    if name == "initcap":
        return str(args[0]).title() if args[0] is not None else None
    if name == "translate":
        if any(a is None for a in args[:3]):
            return None
        s, from_chars, to_chars = str(args[0]), str(args[1]), str(args[2])
        table = str.maketrans(
            from_chars,
            to_chars[:len(from_chars)].ljust(len(from_chars)),
            from_chars[len(to_chars):] if len(to_chars) < len(from_chars) else "",
        )
        return s.translate(table)
    if name == "ascii":
        if args[0] is None:
            return None
        s = str(args[0])
        return ord(s[0]) if s else 0
    if name == "chr":
        if args[0] is None:
            return None
        return chr(int(args[0]))
    if name == "starts_with":
        if args[0] is None or args[1] is None:
            return None
        return str(args[0]).startswith(str(args[1]))
    if name in ("char_length", "character_length"):
        return len(str(args[0])) if args[0] is not None else None
    if name == "position":
        if args[0] is None or args[1] is None:
            return None
        # pglast: POSITION(sub IN str) -> position(str, sub)
        idx = str(args[0]).find(str(args[1]))
        return idx + 1 if idx >= 0 else 0
    if name == "strpos":
        if args[0] is None or args[1] is None:
            return None
        idx = str(args[0]).find(str(args[1]))
        return idx + 1 if idx >= 0 else 0
    if name == "octet_length":
        if args[0] is None:
            return None
        return len(str(args[0]).encode("utf-8"))
    if name == "md5":
        if args[0] is None:
            return None
        import hashlib
        return hashlib.md5(str(args[0]).encode("utf-8")).hexdigest()
    if name == "format":
        if args[0] is None:
            return None
        fmt = str(args[0])
        # PostgreSQL uses %s for strings, %I for identifiers, %L for literals
        # Map to Python format: replace %s with %s, %I and %L with %s
        fmt = fmt.replace("%I", "%s").replace("%L", "'%s'")
        return fmt % tuple(args[1:])
    if name == "regexp_match":
        if args[0] is None or args[1] is None:
            return None
        import re
        m = re.search(str(args[1]), str(args[0]))
        if m is None:
            return None
        groups = m.groups()
        return list(groups) if groups else [m.group()]
    if name == "regexp_matches":
        if args[0] is None or args[1] is None:
            return None
        import re
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
    if name == "regexp_replace":
        if args[0] is None or args[1] is None:
            return None
        import re
        replacement = str(args[2]) if len(args) > 2 and args[2] is not None else ""
        flags_str = str(args[3]) if len(args) > 3 and args[3] is not None else ""
        count = 0 if "g" in flags_str else 1
        flags = 0
        if "i" in flags_str:
            flags |= re.IGNORECASE
        return re.sub(str(args[1]), replacement, str(args[0]), count=count, flags=flags)
    if name == "overlay":
        if args[0] is None or args[1] is None or args[2] is None:
            return None
        s = str(args[0])
        repl = str(args[1])
        pos = int(args[2]) - 1  # 1-based to 0-based
        length = int(args[3]) if len(args) > 3 and args[3] is not None else len(repl)
        return s[:pos] + repl + s[pos + length:]
    if name == "lpad":
        if args[0] is None:
            return None
        s, length = str(args[0]), int(args[1])
        fill = str(args[2]) if len(args) > 2 and args[2] is not None else " "
        if len(s) >= length:
            return s[:length]
        pad_len = length - len(s)
        pad = (fill * (pad_len // len(fill) + 1))[:pad_len]
        return pad + s
    if name == "rpad":
        if args[0] is None:
            return None
        s, length = str(args[0]), int(args[1])
        fill = str(args[2]) if len(args) > 2 and args[2] is not None else " "
        if len(s) >= length:
            return s[:length]
        pad_len = length - len(s)
        pad = (fill * (pad_len // len(fill) + 1))[:pad_len]
        return s + pad
    if name == "repeat":
        if args[0] is None:
            return None
        return str(args[0]) * int(args[1])
    if name == "reverse":
        return str(args[0])[::-1] if args[0] is not None else None
    if name == "split_part":
        if any(a is None for a in args[:3]):
            return None
        parts = str(args[0]).split(str(args[1]))
        n = int(args[2])
        return parts[n - 1] if 1 <= n <= len(parts) else ""

    # Additional math functions
    if name in ("power", "pow"):
        if args[0] is None or args[1] is None:
            return None
        return args[0] ** args[1]
    if name == "sqrt":
        if args[0] is None:
            return None
        import math
        return math.sqrt(args[0])
    if name in ("log", "log10"):
        if args[0] is None:
            return None
        import math
        if len(args) > 1 and args[1] is not None:
            # LOG(b, x) = log base b of x
            return math.log(args[1]) / math.log(args[0])
        return math.log10(args[0])
    if name == "ln":
        if args[0] is None:
            return None
        import math
        return math.log(args[0])
    if name == "exp":
        if args[0] is None:
            return None
        import math
        return math.exp(args[0])
    if name == "mod":
        if args[0] is None or args[1] is None:
            return None
        return args[0] % args[1] if args[1] != 0 else None
    if name == "trunc":
        if args[0] is None:
            return None
        import math
        if len(args) > 1 and args[1] is not None:
            factor = 10 ** int(args[1])
            return math.trunc(args[0] * factor) / factor
        return math.trunc(args[0])
    if name == "sign":
        if args[0] is None:
            return None
        return (args[0] > 0) - (args[0] < 0)
    if name == "pi":
        import math
        return math.pi
    if name == "random":
        import random
        return random.random()
    if name == "cbrt":
        if args[0] is None:
            return None
        v = args[0]
        return -((-v) ** (1.0 / 3.0)) if v < 0 else v ** (1.0 / 3.0)
    if name == "degrees":
        if args[0] is None:
            return None
        import math
        return math.degrees(args[0])
    if name == "radians":
        if args[0] is None:
            return None
        import math
        return math.radians(args[0])
    if name == "sin":
        if args[0] is None:
            return None
        import math
        return math.sin(args[0])
    if name == "cos":
        if args[0] is None:
            return None
        import math
        return math.cos(args[0])
    if name == "tan":
        if args[0] is None:
            return None
        import math
        return math.tan(args[0])
    if name == "asin":
        if args[0] is None:
            return None
        import math
        return math.asin(args[0])
    if name == "acos":
        if args[0] is None:
            return None
        import math
        return math.acos(args[0])
    if name == "atan":
        if args[0] is None:
            return None
        import math
        return math.atan(args[0])
    if name == "atan2":
        if args[0] is None or args[1] is None:
            return None
        import math
        return math.atan2(args[0], args[1])
    if name == "div":
        if args[0] is None or args[1] is None:
            return None
        if args[1] == 0:
            return None
        return int(args[0] // args[1])
    if name == "gcd":
        if args[0] is None or args[1] is None:
            return None
        import math
        return math.gcd(int(args[0]), int(args[1]))
    if name == "lcm":
        if args[0] is None or args[1] is None:
            return None
        import math
        a, b = int(args[0]), int(args[1])
        return abs(a * b) // math.gcd(a, b) if a and b else 0
    if name == "width_bucket":
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

    # Date/time functions
    if name == "now":
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if name in ("extract", "date_part"):
        if args[0] is None or args[1] is None:
            return None
        return _extract_datetime_field(str(args[0]).lower(), str(args[1]))
    if name == "date_trunc":
        if args[0] is None or args[1] is None:
            return None
        return _date_trunc(str(args[0]).lower(), str(args[1]))

    if name == "make_timestamp":
        if any(a is None for a in args[:6]):
            return None
        y, m, d = int(args[0]), int(args[1]), int(args[2])
        h, mi, s = int(args[3]), int(args[4]), float(args[5])
        sec = int(s)
        usec = int((s - sec) * 1_000_000)
        from datetime import datetime
        dt = datetime(y, m, d, h, mi, sec, usec)
        return dt.isoformat()

    if name == "make_interval":
        # make_interval(years, months, weeks, days, hours, mins, secs)
        from datetime import timedelta
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

    if name == "to_number":
        if args[0] is None:
            return None
        import re
        s = str(args[0])
        # Strip non-numeric characters except digits, dots, minus
        cleaned = re.sub(r"[^\d.\-]", "", s)
        if not cleaned or cleaned == "-":
            return 0
        return float(cleaned)

    if name == "overlaps":
        if len(args) < 4 or any(a is None for a in args[:4]):
            return None
        from datetime import datetime
        s1 = datetime.fromisoformat(str(args[0]))
        e1 = datetime.fromisoformat(str(args[1]))
        s2 = datetime.fromisoformat(str(args[2]))
        e2 = datetime.fromisoformat(str(args[3]))
        # Ensure start <= end for each range
        if s1 > e1:
            s1, e1 = e1, s1
        if s2 > e2:
            s2, e2 = e2, s2
        return s1 < e2 and s2 < e1

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

    # JSON functions (Paper 1, Section 5.2-5.3)
    if name == "json_build_object":
        return _json_build_object(args)
    if name == "jsonb_build_object":
        return _json_build_object(args)
    if name == "json_build_array":
        return list(args)
    if name == "jsonb_build_array":
        return list(args)
    if name == "json_typeof" or name == "jsonb_typeof":
        return _json_typeof(args[0] if args else None)
    if name == "json_array_length" or name == "jsonb_array_length":
        return _json_array_length(args[0] if args else None)
    if name in ("json_extract_path", "json_extract_path_text",
                 "jsonb_extract_path", "jsonb_extract_path_text"):
        as_text = name.endswith("_text")
        return _json_extract_path(args, as_text=as_text)
    if name in ("to_json", "to_jsonb", "row_to_json"):
        return args[0] if args else None
    if name in ("jsonb_set", "jsonb_insert"):
        return _jsonb_set(args)
    if name in ("json_each", "jsonb_each", "json_each_text", "jsonb_each_text"):
        return _json_each(args, as_text=name.endswith("_text"))
    if name in ("json_array_elements", "jsonb_array_elements",
                "json_array_elements_text", "jsonb_array_elements_text"):
        return _json_array_elements(args, as_text=name.endswith("_text"))
    if name in ("json_object_keys", "jsonb_object_keys"):
        if not args or args[0] is None:
            return None
        obj = args[0]
        if isinstance(obj, str):
            import json as json_mod
            obj = json_mod.loads(obj)
        if isinstance(obj, dict):
            return list(obj.keys())
        return None

    # UUID functions
    if name == "gen_random_uuid":
        import uuid
        return str(uuid.uuid4())

    # Array functions
    if name == "array_length":
        if not args or args[0] is None:
            return None
        arr = args[0]
        if isinstance(arr, str):
            import json as json_mod
            arr = json_mod.loads(arr)
        if not isinstance(arr, list):
            return None
        return len(arr)
    if name == "array_upper":
        if not args or args[0] is None:
            return None
        arr = args[0]
        if isinstance(arr, str):
            import json as json_mod
            arr = json_mod.loads(arr)
        if not isinstance(arr, list) or not arr:
            return None
        return len(arr)
    if name == "array_lower":
        if not args or args[0] is None:
            return None
        arr = args[0]
        if isinstance(arr, str):
            import json as json_mod
            arr = json_mod.loads(arr)
        if not isinstance(arr, list) or not arr:
            return None
        return 1
    if name == "array_cat":
        if len(args) < 2:
            return None
        a = args[0] if isinstance(args[0], list) else []
        b = args[1] if isinstance(args[1], list) else []
        return a + b
    if name == "array_append":
        if not args or args[0] is None:
            return None
        arr = args[0] if isinstance(args[0], list) else [args[0]]
        return arr + [args[1]] if len(args) > 1 else arr
    if name == "array_remove":
        if not args or args[0] is None:
            return None
        arr = args[0] if isinstance(args[0], list) else []
        val = args[1] if len(args) > 1 else None
        return [x for x in arr if x != val]
    if name == "cardinality":
        if not args or args[0] is None:
            return None
        arr = args[0]
        if isinstance(arr, str):
            import json as json_mod
            arr = json_mod.loads(arr)
        if not isinstance(arr, list):
            return None
        return len(arr)

    raise ValueError(f"Unknown scalar function: {name}")


def _extract_datetime_field(field: str, timestamp_str: str) -> Any:
    """Extract a field from a timestamp/date string (EXTRACT / DATE_PART)."""
    from datetime import datetime

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
    from datetime import datetime

    dt = datetime.fromisoformat(timestamp_str)
    if precision == "year":
        dt = dt.replace(month=1, day=1, hour=0, minute=0, second=0,
                         microsecond=0)
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
        raise ValueError(
            "json_build_object requires an even number of arguments"
        )
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
        import json as json_mod
        value = json_mod.loads(value)
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
    import json as json_mod

    if value is None:
        return None
    if isinstance(value, str):
        value = json_mod.loads(value)
    if isinstance(value, list):
        return len(value)
    return None


def _json_extract_path(args: list[Any], *, as_text: bool) -> Any:
    """Extract a value from a JSON document by path keys.

    Implements Paper 1, Definition 5.2.3 (recursive path evaluation):
    ``eval(h, [k1, k2, ...])``
    """
    import json as json_mod

    if not args or args[0] is None:
        return None
    obj = args[0]
    if isinstance(obj, str):
        obj = json_mod.loads(obj)
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
            return json_mod.dumps(obj, ensure_ascii=False)
        return str(obj)
    return obj


def _jsonb_set(args: list[Any]) -> Any:
    """Implement JSONB_SET(target, path, new_value [, create_if_missing]).

    Sets a value in a JSON document at the given path.
    """
    import json as json_mod

    if len(args) < 3 or args[0] is None:
        return None
    target = args[0]
    if isinstance(target, str):
        target = json_mod.loads(target)

    path_str = str(args[1]).strip("{}")
    keys = [k.strip() for k in path_str.split(",")]
    new_value = args[2]
    create = bool(args[3]) if len(args) > 3 else True

    import copy
    result = copy.deepcopy(target)
    obj = result
    for i, key in enumerate(keys[:-1]):
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
    import json as json_mod

    if not args or args[0] is None:
        return []
    obj = args[0]
    if isinstance(obj, str):
        obj = json_mod.loads(obj)
    if not isinstance(obj, dict):
        return []
    rows = []
    for k, v in obj.items():
        if as_text:
            if isinstance(v, (dict, list)):
                v = json_mod.dumps(v, ensure_ascii=False)
            else:
                v = str(v) if v is not None else None
        rows.append({"key": k, "value": v})
    return rows


def _json_array_elements(args: list[Any], *, as_text: bool) -> list[Any]:
    """Expand a JSON array into individual elements."""
    import json as json_mod

    if not args or args[0] is None:
        return []
    arr = args[0]
    if isinstance(arr, str):
        arr = json_mod.loads(arr)
    if not isinstance(arr, list):
        return []
    if as_text:
        result_list = []
        for v in arr:
            if isinstance(v, (dict, list)):
                result_list.append(json_mod.dumps(v, ensure_ascii=False))
            else:
                result_list.append(str(v) if v is not None else None)
        return result_list
    return arr
