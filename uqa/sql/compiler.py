#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQL-to-UQA compiler using pglast (PostgreSQL parser).

Supported statements:
  DDL:
    CREATE TABLE name (col type [PRIMARY KEY] [NOT NULL] [DEFAULT val], ...)
    DROP TABLE [IF EXISTS] name
  DML:
    INSERT INTO name (col, ...) VALUES (val, ...), ...
  DQL:
    SELECT [* | col, ... | aggregates] FROM table
      [WHERE comparisons / boolean / text_match() / knn_match()]
      [GROUP BY col [HAVING ...]]
      [ORDER BY col [ASC|DESC]]
      [LIMIT n]
  Utility:
    EXPLAIN SELECT ...                  -- show optimized query plan
    ANALYZE [table]                     -- collect per-column statistics

All SELECT queries pass through the QueryOptimizer (filter pushdown,
vector threshold merge, intersect reordering) before execution via
PlanExecutor with timing stats.

Extended functions (WHERE clause):
  text_match(field, 'query')         -- full-text search with BM25 scoring
  bayesian_match(field, 'query')     -- Bayesian BM25 calibrated probability
  knn_match(k)                       -- KNN vector search (requires set_query_vector)

FROM-clause table functions:
  traverse(start_id, 'label', max_hops) -- graph traversal
  rpq('path_expr', start_id)            -- regular path query
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from pglast import parse_sql
from pglast.ast import (
    A_Const,
    A_Expr,
    A_Star,
    BoolExpr,
    ColumnRef,
    CreateStmt,
    DropStmt,
    ExplainStmt,
    Float as PgFloat,
    FuncCall,
    InsertStmt,
    Integer as PgInteger,
    JoinExpr,
    RangeFunction,
    RangeVar,
    SelectStmt,
    SortBy,
    String as PgString,
    VacuumStmt,
)
from pglast.enums.parsenodes import A_Expr_Kind, ConstrType, SortByDir
from pglast.enums.primnodes import BoolExprType
from pglast.enums.nodes import JoinType

from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Between,
    Equals,
    GreaterThan,
    GreaterThanOrEqual,
    InSet,
    LessThan,
    LessThanOrEqual,
    NotEquals,
    Payload,
    PostingEntry,
    Predicate,
)
from uqa.sql.table import ColumnDef, Table, resolve_type, _AUTO_INCREMENT_TYPES

if TYPE_CHECKING:
    from uqa.engine import Engine
    from uqa.operators.base import ExecutionContext


# ======================================================================
# Result type
# ======================================================================

@dataclass
class SQLResult:
    """Result of a SQL query: columns + rows."""

    columns: list[str]
    rows: list[dict[str, Any]]

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __repr__(self) -> str:
        return f"SQLResult(columns={self.columns}, {len(self.rows)} rows)"

    def __str__(self) -> str:
        if not self.rows:
            return "(0 rows)"
        col_widths: dict[str, int] = {}
        for col in self.columns:
            col_widths[col] = len(col)
        str_rows: list[dict[str, str]] = []
        for row in self.rows:
            sr = {}
            for col in self.columns:
                s = _format_value(row.get(col, ""))
                sr[col] = s
                col_widths[col] = max(col_widths[col], len(s))
            str_rows.append(sr)
        parts: list[str] = []
        header = " | ".join(col.ljust(col_widths[col]) for col in self.columns)
        parts.append(header)
        parts.append("-+-".join("-" * col_widths[col] for col in self.columns))
        for sr in str_rows:
            parts.append(
                " | ".join(sr[col].ljust(col_widths[col]) for col in self.columns)
            )
        parts.append(f"({len(self.rows)} rows)")
        return "\n".join(parts)


def _format_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


# ======================================================================
# Compiler
# ======================================================================

class SQLCompiler:
    """Compiles SQL statements into UQA operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._query_vector: Any = None

    def set_query_vector(self, vector: Any) -> None:
        """Register a query vector for knn_match() calls."""
        self._query_vector = vector

    def execute(self, sql: str) -> SQLResult:
        """Parse and execute a SQL statement."""
        stmts = parse_sql(sql)
        if not stmts:
            raise ValueError("Empty SQL statement")
        stmt = stmts[0].stmt
        if isinstance(stmt, SelectStmt):
            return self._compile_select(stmt)
        if isinstance(stmt, CreateStmt):
            return self._compile_create_table(stmt)
        if isinstance(stmt, InsertStmt):
            return self._compile_insert(stmt)
        if isinstance(stmt, DropStmt):
            return self._compile_drop_table(stmt)
        if isinstance(stmt, ExplainStmt):
            return self._compile_explain(stmt)
        if isinstance(stmt, VacuumStmt):
            return self._compile_analyze(stmt)
        raise ValueError(f"Unsupported statement: {type(stmt).__name__}")

    # ==================================================================
    # DDL: CREATE TABLE / DROP TABLE
    # ==================================================================

    def _compile_create_table(self, stmt: CreateStmt) -> SQLResult:
        table_name = stmt.relation.relname
        if table_name in self._engine._tables:
            raise ValueError(f"Table '{table_name}' already exists")

        columns: list[ColumnDef] = []
        for elt in stmt.tableElts:
            col = self._parse_column_def(elt)
            columns.append(col)

        table = Table(table_name, columns)
        self._engine._tables[table_name] = table
        return SQLResult([], [])

    def _parse_column_def(self, node: Any) -> ColumnDef:
        col_name: str = node.colname
        type_names = node.typeName.names
        raw_type, python_type = resolve_type(type_names)

        primary_key = False
        not_null = False
        default = None

        if node.constraints:
            for constraint in node.constraints:
                ct = ConstrType(constraint.contype)
                if ct == ConstrType.CONSTR_PRIMARY:
                    primary_key = True
                    not_null = True
                elif ct == ConstrType.CONSTR_NOTNULL:
                    not_null = True
                elif ct == ConstrType.CONSTR_DEFAULT:
                    default = self._extract_const_value(constraint.raw_expr)

        auto_increment = raw_type in _AUTO_INCREMENT_TYPES

        return ColumnDef(
            name=col_name,
            type_name=raw_type,
            python_type=python_type,
            primary_key=primary_key,
            not_null=not_null,
            auto_increment=auto_increment,
            default=default,
        )

    def _compile_drop_table(self, stmt: DropStmt) -> SQLResult:
        for obj in stmt.objects:
            table_name = obj[-1].sval
            if table_name in self._engine._tables:
                del self._engine._tables[table_name]
            elif not stmt.missing_ok:
                raise ValueError(f"Table '{table_name}' does not exist")
        return SQLResult([], [])

    # ==================================================================
    # DML: INSERT INTO
    # ==================================================================

    def _compile_insert(self, stmt: InsertStmt) -> SQLResult:
        table_name = stmt.relation.relname
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Column names
        if stmt.cols:
            col_names = [c.name for c in stmt.cols]
        else:
            col_names = table.column_names

        # VALUES rows
        values_stmt = stmt.selectStmt
        if values_stmt is None or values_stmt.valuesLists is None:
            raise ValueError("INSERT requires VALUES clause")

        inserted = 0
        for row_values in values_stmt.valuesLists:
            if len(row_values) != len(col_names):
                raise ValueError(
                    f"VALUES has {len(row_values)} columns "
                    f"but {len(col_names)} were specified"
                )
            row: dict[str, Any] = {}
            for i, val_node in enumerate(row_values):
                row[col_names[i]] = self._extract_const_value(val_node)
            table.insert(row)
            inserted += 1

        return SQLResult(["inserted"], [{"inserted": inserted}])

    # ==================================================================
    # EXPLAIN / ANALYZE
    # ==================================================================

    def _compile_explain(self, stmt: ExplainStmt) -> SQLResult:
        """EXPLAIN SELECT ... -- show the optimized query plan."""
        inner = stmt.query
        if not isinstance(inner, SelectStmt):
            raise ValueError("EXPLAIN only supports SELECT statements")
        return self._compile_select(inner, explain=True)

    def _compile_analyze(self, stmt: VacuumStmt) -> SQLResult:
        """ANALYZE [table] -- collect per-column statistics."""
        if stmt.rels:
            for rel in stmt.rels:
                table_name = rel.relation.relname
                table = self._engine._tables.get(table_name)
                if table is None:
                    raise ValueError(f"Table '{table_name}' does not exist")
                table.analyze()
        else:
            for table in self._engine._tables.values():
                table.analyze()
        return SQLResult([], [])

    # ==================================================================
    # Query optimizer + plan executor
    # ==================================================================

    def _optimize(
        self, op: Any, ctx: ExecutionContext, table: Table | None = None
    ) -> Any:
        """Run the operator tree through the QueryOptimizer."""
        from uqa.planner.optimizer import QueryOptimizer

        stats = ctx.inverted_index.stats
        column_stats = table._stats if table is not None else None
        optimizer = QueryOptimizer(stats, column_stats)
        return optimizer.optimize(op)

    def _execute_plan(self, op: Any, ctx: ExecutionContext) -> PostingList:
        """Execute an operator tree via PlanExecutor with timing stats."""
        from uqa.planner.executor import PlanExecutor

        executor = PlanExecutor(ctx)
        return executor.execute(op)

    def _explain_plan(self, op: Any, ctx: ExecutionContext) -> SQLResult:
        """Format the optimized query plan as an EXPLAIN result."""
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.cost_model import CostModel

        executor = PlanExecutor(ctx)
        plan_text = executor.explain(op)

        stats = ctx.inverted_index.stats
        cost_model = CostModel()
        estimated_cost = cost_model.estimate(op, stats)

        lines = plan_text.split("\n")
        rows = [{"plan": line} for line in lines]
        rows.append({"plan": f"  (estimated cost: {estimated_cost:.1f})"})
        return SQLResult(["plan"], rows)

    # ==================================================================
    # DQL: SELECT
    # ==================================================================

    def _compile_select(
        self, stmt: SelectStmt, *, explain: bool = False
    ) -> SQLResult:
        # 1. Resolve FROM clause -> (table | None, source_op | None)
        table, source_op = self._resolve_from(stmt.fromClause)

        # 2. Build execution context from resolved table
        ctx = self._context_for_table(table)

        # 3. WHERE clause
        if stmt.whereClause is not None:
            where_op = self._compile_where(stmt.whereClause, ctx)
            if source_op is not None:
                where_op = self._chain_on_source(where_op, source_op)
            source_op = where_op

        # 4. Optimize and execute operator tree
        if source_op is not None:
            source_op = self._optimize(source_op, ctx, table)
            if explain:
                return self._explain_plan(source_op, ctx)
            pl = self._execute_plan(source_op, ctx)
        else:
            if explain:
                return SQLResult(["plan"], [{"plan": "Seq Scan (full table)"}])
            pl = self._scan_all(ctx)

        # 5. GROUP BY + aggregates
        if stmt.groupClause is not None:
            return self._handle_group_by(stmt, pl, ctx)

        # 6. Aggregate-only query (no GROUP BY)
        if self._has_aggregates(stmt.targetList):
            return self._handle_aggregates(stmt.targetList, pl, ctx)

        # 7. Convert to rows
        rows = self._to_rows(pl, ctx)

        # 8. Project
        columns, rows = self._project(stmt.targetList, rows)

        # 9. ORDER BY
        if stmt.sortClause is not None:
            rows = self._apply_order_by(rows, stmt.sortClause)

        # 10. LIMIT
        if stmt.limitCount is not None:
            rows = rows[: self._extract_int_value(stmt.limitCount)]

        return SQLResult(columns, rows)

    # -- FROM clause ---------------------------------------------------

    def _resolve_from(
        self, from_clause: tuple | None
    ) -> tuple[Table | None, Any]:
        """Resolve FROM clause to (table, source_operator).

        Returns (table, None) for ``FROM table_name`` and
        (None, operator) for ``FROM func(...)``.
        """
        if from_clause is None:
            return None, None

        if len(from_clause) != 1:
            raise ValueError("Multiple FROM sources not supported; use JOIN")

        node = from_clause[0]

        if isinstance(node, RangeVar):
            table_name = node.relname
            table = self._engine._tables.get(table_name)
            if table is None:
                raise ValueError(f"Table '{table_name}' does not exist")
            return table, None

        if isinstance(node, RangeFunction):
            return self._compile_from_function(node)

        if isinstance(node, JoinExpr):
            return self._resolve_join(node)

        raise ValueError(f"Unsupported FROM clause: {type(node).__name__}")

    def _context_for_table(self, table: Table | None) -> ExecutionContext:
        """Build an ExecutionContext scoped to a specific table."""
        from uqa.operators.base import ExecutionContext

        if table is None:
            return self._engine._build_context()

        return ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
            vector_index=self._engine.vector_index,
            graph_store=self._engine.graph_store,
            block_max_index=self._engine.block_max_index,
        )

    def _compile_from_function(
        self, node: RangeFunction
    ) -> tuple[Table | None, Any]:
        """Return (table_or_none, operator) for a FROM-clause function."""
        func_call = node.functions[0][0]
        if not isinstance(func_call, FuncCall):
            raise ValueError(f"Expected FuncCall in FROM, got {type(func_call)}")
        name = func_call.funcname[-1].sval.lower()
        args = func_call.args or ()

        if name == "traverse":
            return None, self._build_traverse(args)
        if name == "rpq":
            return None, self._build_rpq(args)
        if name == "text_search":
            return self._build_text_search_from(args)
        raise ValueError(f"Unknown table function: {name}")

    def _build_traverse(self, args: tuple) -> Any:
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        return TraverseOperator(start, label, max_hops)

    def _build_rpq(self, args: tuple) -> Any:
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import parse_rpq

        expr = self._extract_string_value(args[0])
        start = self._extract_int_value(args[1]) if len(args) > 1 else None
        return RegularPathQueryOperator(parse_rpq(expr), start_vertex=start)

    def _build_text_search_from(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build a text_search FROM-clause: text_search('query', 'field'[, 'table'])."""
        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.operators.boolean import UnionOperator
        from uqa.scoring.bm25 import BM25Params, BM25Scorer

        query = self._extract_string_value(args[0])
        field_name = self._extract_string_value(args[1]) if len(args) > 1 else None
        table: Table | None = None
        if len(args) > 2:
            table_name = self._extract_string_value(args[2])
            table = self._engine._tables.get(table_name)
            if table is None:
                raise ValueError(f"Table '{table_name}' does not exist")
        ctx = self._context_for_table(table)
        terms = query.lower().split()
        term_ops = [TermOperator(t, field_name) for t in terms]
        retrieval = term_ops[0] if len(term_ops) == 1 else UnionOperator(term_ops)
        scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        op = ScoreOperator(scorer, retrieval, terms, field=field_name)
        return table, op

    # -- JOIN ----------------------------------------------------------

    def _resolve_join(
        self, node: JoinExpr
    ) -> tuple[Table | None, Any]:
        from uqa.joins.base import JoinCondition
        from uqa.joins.inner import InnerJoinOperator
        from uqa.joins.outer import LeftOuterJoinOperator

        left_table, left_op = self._resolve_from_node(node.larg)
        right_table, right_op = self._resolve_from_node(node.rarg)

        # Both sides must be the same table or both None (engine default)
        table = left_table or right_table

        if left_op is None:
            left_op = _ScanOperator()
        if right_op is None:
            right_op = _ScanOperator()

        quals = node.quals
        if not isinstance(quals, A_Expr):
            raise ValueError("JOIN ON must be a simple column equality")
        left_field = self._extract_column_name(quals.lexpr)
        right_field = self._extract_column_name(quals.rexpr)
        condition = JoinCondition(left_field, right_field)

        jt = node.jointype
        if jt == JoinType.JOIN_INNER:
            return table, InnerJoinOperator(left_op, right_op, condition)
        if jt == JoinType.JOIN_LEFT:
            return table, LeftOuterJoinOperator(left_op, right_op, condition)
        raise ValueError(f"Unsupported join type: {jt}")

    def _resolve_from_node(self, node: Any) -> tuple[Table | None, Any]:
        if isinstance(node, RangeVar):
            table_name = node.relname
            table = self._engine._tables.get(table_name)
            if table is None:
                raise ValueError(f"Table '{table_name}' does not exist")
            return table, None
        if isinstance(node, RangeFunction):
            return self._compile_from_function(node)
        raise ValueError(f"Unsupported FROM node: {type(node).__name__}")

    # -- WHERE clause --------------------------------------------------

    def _compile_where(self, node: Any, ctx: ExecutionContext) -> Any:
        if isinstance(node, BoolExpr):
            return self._compile_bool_expr(node, ctx)
        if isinstance(node, A_Expr):
            return self._compile_comparison(node)
        if isinstance(node, FuncCall):
            return self._compile_func_in_where(node, ctx)
        raise ValueError(f"Unsupported WHERE node: {type(node).__name__}")

    def _compile_bool_expr(self, node: BoolExpr, ctx: ExecutionContext) -> Any:
        if node.boolop == BoolExprType.AND_EXPR:
            return self._compile_and(node.args, ctx)
        if node.boolop == BoolExprType.OR_EXPR:
            from uqa.operators.boolean import UnionOperator
            return UnionOperator([self._compile_where(a, ctx) for a in node.args])
        if node.boolop == BoolExprType.NOT_EXPR:
            from uqa.operators.boolean import ComplementOperator
            return ComplementOperator(self._compile_where(node.args[0], ctx))
        raise ValueError(f"Unsupported BoolExpr type: {node.boolop}")

    def _compile_and(self, args: tuple, ctx: ExecutionContext) -> Any:
        """Compile AND: chain filters on top of scored retrievals."""
        from uqa.operators.primitive import FilterOperator

        scored: list[Any] = []
        filters: list[Any] = []

        for arg in args:
            compiled = self._compile_where(arg, ctx)
            if isinstance(compiled, FilterOperator) and compiled.source is None:
                filters.append(compiled)
            else:
                scored.append(compiled)

        if scored:
            base = scored[0] if len(scored) == 1 else (
                __import__("uqa.operators.boolean", fromlist=["IntersectOperator"])
                .IntersectOperator(scored)
            )
        elif filters:
            base = filters.pop(0)
        else:
            return _ScanOperator()

        for f in filters:
            base = FilterOperator(f.field, f.predicate, source=base)
        return base

    def _compile_comparison(self, node: A_Expr) -> Any:
        from uqa.operators.primitive import FilterOperator

        kind = A_Expr_Kind(node.kind)

        if kind == A_Expr_Kind.AEXPR_OP:
            field_name = self._extract_column_name(node.lexpr)
            value = self._extract_const_value(node.rexpr)
            return FilterOperator(field_name, _op_to_predicate(node.name[0].sval, value))

        if kind == A_Expr_Kind.AEXPR_IN:
            field_name = self._extract_column_name(node.lexpr)
            values = frozenset(self._extract_const_value(v) for v in node.rexpr)
            return FilterOperator(field_name, InSet(values))

        if kind == A_Expr_Kind.AEXPR_BETWEEN:
            field_name = self._extract_column_name(node.lexpr)
            low = self._extract_const_value(node.rexpr[0])
            high = self._extract_const_value(node.rexpr[1])
            return FilterOperator(field_name, Between(low, high))

        if kind == A_Expr_Kind.AEXPR_NOT_BETWEEN:
            from uqa.operators.boolean import ComplementOperator
            from uqa.operators.primitive import FilterOperator as FO
            field_name = self._extract_column_name(node.lexpr)
            low = self._extract_const_value(node.rexpr[0])
            high = self._extract_const_value(node.rexpr[1])
            return ComplementOperator(FO(field_name, Between(low, high)))

        if kind == A_Expr_Kind.AEXPR_LIKE:
            raise ValueError("LIKE not supported; use text_match() for full-text search")

        raise ValueError(f"Unsupported expression kind: {kind}")

    def _compile_func_in_where(self, node: FuncCall, ctx: ExecutionContext) -> Any:
        name = node.funcname[-1].sval.lower()
        args = node.args or ()

        if name == "text_match":
            field_name = self._extract_column_name(args[0])
            query = self._extract_string_value(args[1])
            return self._make_text_search_op(field_name, query, ctx, bayesian=False)
        if name == "bayesian_match":
            field_name = self._extract_column_name(args[0])
            query = self._extract_string_value(args[1])
            return self._make_text_search_op(field_name, query, ctx, bayesian=True)
        if name == "knn_match":
            return self._make_knn_op(self._extract_int_value(args[0]))
        raise ValueError(f"Unknown function: {name}")

    def _make_text_search_op(
        self, field_name: str, query: str, ctx: ExecutionContext, *, bayesian: bool
    ) -> Any:
        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.operators.boolean import UnionOperator

        terms = query.lower().split()
        term_ops = [TermOperator(t, field_name) for t in terms]
        retrieval = term_ops[0] if len(term_ops) == 1 else UnionOperator(term_ops)

        if bayesian:
            from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer
            scorer = BayesianBM25Scorer(BayesianBM25Params(), ctx.inverted_index.stats)
        else:
            from uqa.scoring.bm25 import BM25Params, BM25Scorer
            scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        return ScoreOperator(scorer, retrieval, terms, field=field_name)

    def _make_knn_op(self, k: int) -> Any:
        from uqa.operators.primitive import KNNOperator
        if self._query_vector is None:
            raise ValueError(
                "No query vector registered. "
                "Call set_query_vector() before using knn_match()."
            )
        return KNNOperator(self._query_vector, k)

    # -- Aggregation ---------------------------------------------------

    def _has_aggregates(self, target_list: tuple | None) -> bool:
        if target_list is None:
            return False
        return any(
            isinstance(t.val, FuncCall)
            and t.val.funcname[-1].sval.lower() in ("count", "sum", "avg", "min", "max")
            for t in target_list
        )

    def _handle_group_by(
        self, stmt: SelectStmt, pl: PostingList, ctx: ExecutionContext
    ) -> SQLResult:
        group_cols = [self._extract_column_name(g) for g in stmt.groupClause]
        doc_store = ctx.document_store

        groups: dict[tuple, list[int]] = {}
        for entry in pl:
            key = tuple(doc_store.get_field(entry.doc_id, c) for c in group_cols)
            groups.setdefault(key, []).append(entry.doc_id)

        agg_specs = self._extract_agg_specs(stmt.targetList)
        rows: list[dict[str, Any]] = []
        for key, doc_ids in groups.items():
            row: dict[str, Any] = dict(zip(group_cols, key))
            for alias, func_name, arg_col in agg_specs:
                row[alias] = self._compute_aggregate(func_name, arg_col, doc_ids, doc_store)
            rows.append(row)

        if stmt.havingClause is not None:
            rows = self._apply_having(rows, stmt.havingClause, stmt.targetList)
        if stmt.sortClause is not None:
            rows = self._apply_order_by(rows, stmt.sortClause)
        if stmt.limitCount is not None:
            rows = rows[: self._extract_int_value(stmt.limitCount)]

        columns = list(rows[0].keys()) if rows else group_cols
        return SQLResult(columns, rows)

    def _handle_aggregates(
        self, target_list: tuple, pl: PostingList, ctx: ExecutionContext
    ) -> SQLResult:
        doc_ids = [e.doc_id for e in pl]
        agg_specs = self._extract_agg_specs(target_list)
        row: dict[str, Any] = {}
        for alias, func_name, arg_col in agg_specs:
            row[alias] = self._compute_aggregate(
                func_name, arg_col, doc_ids, ctx.document_store
            )
        return SQLResult(list(row.keys()), [row])

    def _extract_agg_specs(
        self, target_list: tuple
    ) -> list[tuple[str, str, str | None]]:
        specs: list[tuple[str, str, str | None]] = []
        for target in target_list:
            if not isinstance(target.val, FuncCall):
                continue
            func = target.val
            func_name = func.funcname[-1].sval.lower()
            if func_name not in ("count", "sum", "avg", "min", "max"):
                continue
            arg_col = None if func.agg_star else self._extract_column_name(func.args[0])
            alias = target.name or (func_name if arg_col is None else f"{func_name}_{arg_col}")
            specs.append((alias, func_name, arg_col))
        return specs

    def _compute_aggregate(
        self, func_name: str, arg_col: str | None,
        doc_ids: list[int], doc_store: Any
    ) -> Any:
        if func_name == "count":
            if arg_col is None:
                return len(doc_ids)
            return sum(1 for d in doc_ids if doc_store.get_field(d, arg_col) is not None)
        values = [
            doc_store.get_field(d, arg_col) for d in doc_ids
            if isinstance(doc_store.get_field(d, arg_col), (int, float))
        ]
        if not values:
            return None
        if func_name == "sum":
            return sum(values)
        if func_name == "avg":
            return sum(values) / len(values)
        if func_name == "min":
            return min(values)
        if func_name == "max":
            return max(values)
        raise ValueError(f"Unknown aggregate: {func_name}")

    def _apply_having(
        self, rows: list[dict], having_node: Any, target_list: tuple
    ) -> list[dict]:
        alias_map: dict[str, str] = {}
        for target in target_list:
            if isinstance(target.val, FuncCall):
                func = target.val
                fn = func.funcname[-1].sval.lower()
                natural = fn if func.agg_star else f"{fn}_{self._extract_column_name(func.args[0])}"
                alias_map[natural] = target.name or natural

        if isinstance(having_node, A_Expr) and isinstance(having_node.lexpr, FuncCall):
            func = having_node.lexpr
            fn = func.funcname[-1].sval.lower()
            natural = fn if func.agg_star else f"{fn}_{self._extract_column_name(func.args[0])}"
            col_name = alias_map.get(natural, natural)
            pred = _op_to_predicate(having_node.name[0].sval, self._extract_const_value(having_node.rexpr))
            return [r for r in rows if pred.evaluate(r.get(col_name))]
        raise ValueError(f"Unsupported HAVING clause: {type(having_node).__name__}")

    # -- Result conversion ---------------------------------------------

    def _scan_all(self, ctx: ExecutionContext) -> PostingList:
        all_ids = sorted(ctx.document_store.doc_ids)
        return PostingList([PostingEntry(d, Payload(score=0.0)) for d in all_ids])

    def _to_rows(self, pl: PostingList, ctx: ExecutionContext) -> list[dict[str, Any]]:
        doc_store = ctx.document_store
        graph_store = ctx.graph_store
        rows: list[dict[str, Any]] = []
        for entry in pl:
            row: dict[str, Any] = {"_doc_id": entry.doc_id, "_score": entry.payload.score}
            doc = doc_store.get(entry.doc_id) if doc_store else None
            if doc is not None:
                row.update(doc)
            elif graph_store is not None:
                vertex = graph_store.get_vertex(entry.doc_id)
                if vertex is not None:
                    row.update(vertex.properties)
            if entry.payload.fields:
                row.update(entry.payload.fields)
            rows.append(row)
        return rows

    def _project(
        self, target_list: tuple | None, rows: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if target_list is None or len(target_list) == 0:
            columns = list(rows[0].keys()) if rows else []
            return columns, rows

        # SELECT *
        for target in target_list:
            if isinstance(target.val, A_Star):
                return (list(rows[0].keys()) if rows else []), rows
            if isinstance(target.val, ColumnRef):
                for field in target.val.fields:
                    if isinstance(field, A_Star):
                        return (list(rows[0].keys()) if rows else []), rows

        # Explicit columns
        columns: list[str] = []
        for target in target_list:
            if isinstance(target.val, ColumnRef):
                columns.append(target.name or self._extract_column_name(target.val))
            elif isinstance(target.val, FuncCall):
                func = target.val
                fn = func.funcname[-1].sval.lower()
                arg = None if func.agg_star else self._extract_column_name(func.args[0])
                columns.append(target.name or (fn if arg is None else f"{fn}_{arg}"))

        projected: list[dict[str, Any]] = []
        for row in rows:
            p_row: dict[str, Any] = {}
            for target in target_list:
                if isinstance(target.val, ColumnRef):
                    col = self._extract_column_name(target.val)
                    p_row[target.name or col] = row.get(col)
                elif isinstance(target.val, FuncCall):
                    func = target.val
                    fn = func.funcname[-1].sval.lower()
                    arg = None if func.agg_star else self._extract_column_name(func.args[0])
                    alias = target.name or (fn if arg is None else f"{fn}_{arg}")
                    p_row[alias] = row.get(alias, row.get("_score"))
            projected.append(p_row)
        return columns, projected

    # -- ORDER BY ------------------------------------------------------

    def _apply_order_by(
        self, rows: list[dict[str, Any]], sort_clause: tuple
    ) -> list[dict[str, Any]]:
        for sort_by in reversed(sort_clause):
            col_name = self._extract_column_name(sort_by.node)
            desc = sort_by.sortby_dir == SortByDir.SORTBY_DESC
            rows = sorted(
                rows,
                key=lambda r, c=col_name: (r.get(c) is None, r.get(c)),
                reverse=desc,
            )
        return rows

    # -- Helpers -------------------------------------------------------

    def _chain_on_source(self, where_op: Any, source_op: Any) -> Any:
        from uqa.operators.primitive import FilterOperator
        if isinstance(where_op, FilterOperator) and where_op.source is None:
            return FilterOperator(where_op.field, where_op.predicate, source=source_op)
        from uqa.operators.boolean import IntersectOperator
        return IntersectOperator([source_op, where_op])

    @staticmethod
    def _extract_column_name(node: Any) -> str:
        if isinstance(node, ColumnRef):
            return node.fields[-1].sval
        raise ValueError(f"Expected ColumnRef, got {type(node).__name__}")

    @staticmethod
    def _extract_const_value(node: Any) -> Any:
        if isinstance(node, A_Const):
            if node.isnull:
                return None
            val = node.val
            if isinstance(val, PgInteger):
                return val.ival
            if isinstance(val, PgFloat):
                return float(val.fval)
            if isinstance(val, PgString):
                return val.sval
        raise ValueError(f"Expected A_Const, got {type(node).__name__}: {node}")

    @staticmethod
    def _extract_string_value(node: Any) -> str:
        if isinstance(node, A_Const) and isinstance(node.val, PgString):
            return node.val.sval
        if isinstance(node, ColumnRef):
            return node.fields[-1].sval
        raise ValueError(f"Expected string constant, got {type(node).__name__}")

    @staticmethod
    def _extract_int_value(node: Any) -> int:
        if isinstance(node, A_Const) and isinstance(node.val, PgInteger):
            return node.val.ival
        raise ValueError(f"Expected integer constant, got {type(node).__name__}")


class _ScanOperator:
    """Scans all documents in the store."""

    def execute(self, context: Any) -> PostingList:
        all_ids = sorted(context.document_store.doc_ids)
        return PostingList([PostingEntry(d, Payload(score=0.0)) for d in all_ids])

    def cost_estimate(self, stats: Any) -> float:
        return float(stats.total_docs)


def _op_to_predicate(op_name: str, value: Any) -> Predicate:
    mapping: dict[str, type[Predicate]] = {
        "=": Equals, "!=": NotEquals, "<>": NotEquals,
        ">": GreaterThan, ">=": GreaterThanOrEqual,
        "<": LessThan, "<=": LessThanOrEqual,
    }
    cls = mapping.get(op_name)
    if cls is None:
        raise ValueError(f"Unsupported operator: {op_name}")
    return cls(value)
