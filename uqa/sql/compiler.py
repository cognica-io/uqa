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
    CREATE VIEW name AS SELECT ...
    DROP VIEW [IF EXISTS] name
  DML:
    INSERT INTO name (col, ...) VALUES (val, ...), ...
    UPDATE name SET col = expr, ... [WHERE ...]
    DELETE FROM name [WHERE ...]
  DQL:
    WITH name AS (SELECT ...) [, ...]     -- common table expressions
    SELECT [DISTINCT] [* | col, ... | expr, ... | aggregates |
           window_func() OVER ([PARTITION BY ...] [ORDER BY ...])]
      FROM table
      [WHERE comparisons / boolean / IS [NOT] NULL /
             LIKE / NOT LIKE / ILIKE / NOT ILIKE /
             IN (SELECT ...) / EXISTS (SELECT ...) /
             text_match() / ...]
      [GROUP BY col [HAVING ...]]
      [ORDER BY col [ASC|DESC]]
      [LIMIT n [OFFSET m]]
  Transaction:
    BEGIN                               -- start explicit transaction
    COMMIT                              -- commit transaction
    ROLLBACK                            -- rollback transaction
    SAVEPOINT name                      -- create savepoint
    RELEASE SAVEPOINT name              -- release savepoint
    ROLLBACK TO SAVEPOINT name          -- rollback to savepoint
  Prepared Statements:
    PREPARE name [(type, ...)] AS query -- prepare a parameterized statement
    EXECUTE name [(val, ...)]           -- execute with parameter values
    DEALLOCATE name | ALL               -- deallocate prepared statement(s)
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
  traverse_match(start, 'label', k)  -- graph reachability as a scored signal

Fusion meta-functions (WHERE clause):
  fuse_log_odds(sig1, sig2, ...[, alpha]) -- log-odds conjunction (Paper 4)
  fuse_prob_and(sig1, sig2, ...)          -- probabilistic AND
  fuse_prob_or(sig1, sig2, ...)           -- probabilistic OR
  fuse_prob_not(signal)                   -- probabilistic NOT (complement)

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
    CaseExpr,
    CoalesceExpr,
    ColumnRef,
    CreateStmt,
    DeleteStmt,
    DropStmt,
    ExplainStmt,
    Float as PgFloat,
    FuncCall,
    IndexStmt,
    InsertStmt,
    Integer as PgInteger,
    JoinExpr,
    NullTest,
    RangeFunction,
    RangeVar,
    SelectStmt,
    SortBy,
    String as PgString,
    SubLink,
    TransactionStmt,
    TypeCast,
    UpdateStmt,
    VacuumStmt,
    ViewStmt,
    PrepareStmt,
    ExecuteStmt,
    DeallocateStmt,
    ParamRef,
)
from pglast.enums.parsenodes import A_Expr_Kind, ConstrType, SortByDir
from pglast.enums.primnodes import BoolExprType, NullTestType, SubLinkType
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
        self._expanded_views: list[str] = []

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
        if isinstance(stmt, UpdateStmt):
            return self._compile_update(stmt)
        if isinstance(stmt, DeleteStmt):
            return self._compile_delete(stmt)
        if isinstance(stmt, DropStmt):
            return self._compile_drop(stmt)
        if isinstance(stmt, ViewStmt):
            return self._compile_create_view(stmt)
        if isinstance(stmt, IndexStmt):
            return self._compile_create_index(stmt)
        if isinstance(stmt, ExplainStmt):
            return self._compile_explain(stmt)
        if isinstance(stmt, VacuumStmt):
            return self._compile_analyze(stmt)
        if isinstance(stmt, TransactionStmt):
            return self._compile_transaction(stmt)
        if isinstance(stmt, PrepareStmt):
            return self._compile_prepare(stmt)
        if isinstance(stmt, ExecuteStmt):
            return self._compile_execute(stmt)
        if isinstance(stmt, DeallocateStmt):
            return self._compile_deallocate(stmt)
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

        catalog = self._engine._catalog
        conn = catalog.conn if catalog is not None else None
        table = Table(table_name, columns, conn=conn)
        self._engine._tables[table_name] = table

        if catalog is not None:
            catalog.save_table_schema(
                table_name,
                [
                    {
                        "name": col.name,
                        "type_name": col.type_name,
                        "primary_key": col.primary_key,
                        "not_null": col.not_null,
                        "auto_increment": col.auto_increment,
                        "default": col.default,
                    }
                    for col in columns
                ],
            )

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

    def _compile_drop(self, stmt: DropStmt) -> SQLResult:
        """Dispatch DROP TABLE / DROP INDEX / DROP VIEW based on removeType."""
        # removeType 41 = OBJECT_TABLE, 20 = OBJECT_INDEX, 51 = OBJECT_VIEW
        if stmt.removeType == 20:
            return self._compile_drop_index(stmt)
        if stmt.removeType == 51:
            return self._compile_drop_view(stmt)
        return self._compile_drop_table(stmt)

    def _compile_drop_table(self, stmt: DropStmt) -> SQLResult:
        for obj in stmt.objects:
            table_name = obj[-1].sval
            if table_name in self._engine._tables:
                index_manager = getattr(self._engine, "_index_manager", None)
                if index_manager is not None:
                    index_manager.drop_indexes_for_table(table_name)
                del self._engine._tables[table_name]
                if self._engine._catalog is not None:
                    self._engine._catalog.drop_table_schema(table_name)
            elif not stmt.missing_ok:
                raise ValueError(f"Table '{table_name}' does not exist")
        return SQLResult([], [])

    def _compile_drop_index(self, stmt: DropStmt) -> SQLResult:
        index_manager = getattr(self._engine, "_index_manager", None)
        if index_manager is None:
            raise ValueError(
                "Index operations require a persistent engine (db_path)"
            )
        for obj in stmt.objects:
            index_name = obj[-1].sval
            if stmt.missing_ok:
                index_manager.drop_index_if_exists(index_name)
            else:
                index_manager.drop_index(index_name)
        return SQLResult([], [])

    # ==================================================================
    # DDL: CREATE VIEW / DROP VIEW
    # ==================================================================

    def _compile_create_view(self, stmt: ViewStmt) -> SQLResult:
        view_name = stmt.view.relname
        if view_name in self._engine._views:
            raise ValueError(f"View '{view_name}' already exists")
        if view_name in self._engine._tables:
            raise ValueError(
                f"'{view_name}' already exists as a table"
            )
        self._engine._views[view_name] = stmt.query
        return SQLResult([], [])

    def _compile_drop_view(self, stmt: DropStmt) -> SQLResult:
        for obj in stmt.objects:
            view_name = obj[-1].sval
            if view_name in self._engine._views:
                del self._engine._views[view_name]
            elif not stmt.missing_ok:
                raise ValueError(f"View '{view_name}' does not exist")
        return SQLResult([], [])

    # ==================================================================
    # DDL: CREATE INDEX / DROP INDEX
    # ==================================================================

    def _compile_create_index(self, stmt: IndexStmt) -> SQLResult:
        from uqa.storage.index_types import IndexDef, IndexType

        index_manager = getattr(self._engine, "_index_manager", None)
        if index_manager is None:
            raise ValueError(
                "Index operations require a persistent engine (db_path)"
            )

        index_name = stmt.idxname
        table_name = stmt.relation.relname

        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        columns: list[str] = []
        for param in stmt.indexParams:
            col_name = param.name
            if col_name not in table.columns:
                raise ValueError(
                    f"Column '{col_name}' does not exist "
                    f"in table '{table_name}'"
                )
            columns.append(col_name)

        index_def = IndexDef(
            name=index_name,
            index_type=IndexType.BTREE,
            table_name=table_name,
            columns=tuple(columns),
        )
        index_manager.create_index(index_def)
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

        # SQLite-backed stores auto-persist on each put/add_document,
        # so no separate catalog persistence is needed.
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
    # DML: UPDATE
    # ==================================================================

    def _compile_update(self, stmt: UpdateStmt) -> SQLResult:
        table_name = stmt.relation.relname
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Find matching doc_ids via WHERE clause
        ctx = self._context_for_table(table)
        if stmt.whereClause is not None:
            where_op = self._compile_where(stmt.whereClause, ctx)
            where_op = self._optimize(where_op, ctx, table)
            pl = self._execute_plan(where_op, ctx)
        else:
            pl = self._scan_all(ctx)

        matching_ids = [entry.doc_id for entry in pl.entries]
        if not matching_ids:
            return SQLResult(["updated"], [{"updated": 0}])

        # Parse SET clause into (column_name, ast_node) pairs
        set_targets: list[tuple[str, Any]] = []
        for target in stmt.targetList:
            col_name = target.name
            if col_name not in table.columns:
                raise ValueError(
                    f"Unknown column '{col_name}' "
                    f"for table '{table_name}'"
                )
            set_targets.append((col_name, target.val))

        from uqa.sql.expr_evaluator import ExprEvaluator
        evaluator = ExprEvaluator(subquery_executor=self._compile_select)

        updated = 0
        for doc_id in matching_ids:
            old_doc = table.document_store.get(doc_id)
            if old_doc is None:
                continue

            # Evaluate SET expressions against the current row
            new_doc = dict(old_doc)
            for col_name, val_node in set_targets:
                new_value = evaluator.evaluate(val_node, old_doc)
                col_def = table.columns[col_name]
                if new_value is not None:
                    new_doc[col_name] = col_def.python_type(new_value)
                elif col_def.not_null:
                    raise ValueError(
                        f"NOT NULL constraint violated: "
                        f"column '{col_name}' in table '{table_name}'"
                    )
                else:
                    new_doc.pop(col_name, None)

            # Remove old inverted index entries
            table.inverted_index.remove_document(doc_id)

            # Write updated document
            table.document_store.put(doc_id, new_doc)

            # Re-index text fields
            text_fields = {
                k: v for k, v in new_doc.items()
                if isinstance(v, str)
            }
            if text_fields:
                table.inverted_index.add_document(doc_id, text_fields)

            updated += 1

        return SQLResult(["updated"], [{"updated": updated}])

    # ==================================================================
    # DML: DELETE
    # ==================================================================

    def _compile_delete(self, stmt: DeleteStmt) -> SQLResult:
        table_name = stmt.relation.relname
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Find matching doc_ids via WHERE clause
        ctx = self._context_for_table(table)
        if stmt.whereClause is not None:
            where_op = self._compile_where(stmt.whereClause, ctx)
            where_op = self._optimize(where_op, ctx, table)
            pl = self._execute_plan(where_op, ctx)
        else:
            pl = self._scan_all(ctx)

        matching_ids = [entry.doc_id for entry in pl.entries]
        if not matching_ids:
            return SQLResult(["deleted"], [{"deleted": 0}])

        deleted = 0
        for doc_id in matching_ids:
            table.inverted_index.remove_document(doc_id)
            table.document_store.delete(doc_id)
            deleted += 1

        return SQLResult(["deleted"], [{"deleted": deleted}])

    # ==================================================================
    # Transaction: BEGIN / COMMIT / ROLLBACK / SAVEPOINT
    # ==================================================================

    def _compile_transaction(self, stmt: TransactionStmt) -> SQLResult:
        kind = stmt.kind.value
        # 0 = BEGIN, 2 = COMMIT, 3 = ROLLBACK
        # 4 = SAVEPOINT, 5 = RELEASE SAVEPOINT, 6 = ROLLBACK TO SAVEPOINT
        if kind == 0:
            self._engine.begin()
            return SQLResult([], [])
        if kind == 2:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError("No active transaction to commit")
            txn.commit()
            self._engine._transaction = None
            return SQLResult([], [])
        if kind == 3:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError("No active transaction to rollback")
            txn.rollback()
            self._engine._transaction = None
            return SQLResult([], [])
        if kind == 4:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError(
                    "SAVEPOINT requires an active transaction"
                )
            txn.savepoint(stmt.savepoint_name)
            return SQLResult([], [])
        if kind == 5:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError(
                    "RELEASE SAVEPOINT requires an active transaction"
                )
            txn.release_savepoint(stmt.savepoint_name)
            return SQLResult([], [])
        if kind == 6:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError(
                    "ROLLBACK TO SAVEPOINT requires an active transaction"
                )
            txn.rollback_to(stmt.savepoint_name)
            return SQLResult([], [])
        raise ValueError(f"Unsupported transaction statement kind: {kind}")

    # ==================================================================
    # Prepared Statements: PREPARE / EXECUTE / DEALLOCATE
    # ==================================================================

    def _compile_prepare(self, stmt: PrepareStmt) -> SQLResult:
        name = stmt.name
        if name in self._engine._prepared:
            raise ValueError(
                f"Prepared statement '{name}' already exists"
            )
        self._engine._prepared[name] = stmt
        return SQLResult([], [])

    def _compile_execute(self, stmt: ExecuteStmt) -> SQLResult:
        name = stmt.name
        prep = self._engine._prepared.get(name)
        if prep is None:
            raise ValueError(
                f"Prepared statement '{name}' does not exist"
            )

        # Collect parameter values from EXECUTE
        params: dict[int, A_Const] = {}
        if stmt.params:
            for i, param in enumerate(stmt.params):
                params[i + 1] = param  # 1-based

        # Substitute ParamRef nodes in the stored query AST
        query = self._substitute_params(prep.query, params)

        # Dispatch to the appropriate compiler method
        if isinstance(query, SelectStmt):
            return self._compile_select(query)
        if isinstance(query, InsertStmt):
            return self._compile_insert(query)
        if isinstance(query, UpdateStmt):
            return self._compile_update(query)
        if isinstance(query, DeleteStmt):
            return self._compile_delete(query)
        raise ValueError(
            f"Unsupported prepared query type: {type(query).__name__}"
        )

    def _compile_deallocate(self, stmt: DeallocateStmt) -> SQLResult:
        if stmt.name is None:
            # DEALLOCATE ALL
            self._engine._prepared.clear()
        else:
            if stmt.name not in self._engine._prepared:
                raise ValueError(
                    f"Prepared statement '{stmt.name}' does not exist"
                )
            del self._engine._prepared[stmt.name]
        return SQLResult([], [])

    def _substitute_params(
        self, node: Any, params: dict[int, A_Const]
    ) -> Any:
        """Recursively replace ParamRef nodes with A_Const values."""
        if isinstance(node, ParamRef):
            if node.number not in params:
                raise ValueError(
                    f"No value supplied for parameter ${node.number}"
                )
            return params[node.number]

        # Recurse into plain tuples/lists (e.g. valuesLists rows)
        if isinstance(node, tuple):
            return tuple(
                self._substitute_params(item, params) for item in node
            )
        if isinstance(node, list):
            return [
                self._substitute_params(item, params) for item in node
            ]

        # pglast AST nodes use __slots__; clone with substituted children
        if hasattr(node, '__slots__') and isinstance(node.__slots__, dict):
            kwargs = {}
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is None:
                    kwargs[slot] = None
                elif isinstance(val, (tuple, list)):
                    kwargs[slot] = type(val)(
                        self._substitute_params(item, params)
                        for item in val
                    )
                elif hasattr(val, '__slots__'):
                    kwargs[slot] = self._substitute_params(val, params)
                else:
                    kwargs[slot] = val
            try:
                return node.__class__(**kwargs)
            except TypeError:
                return node

        return node

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
        tables_to_analyze: list[Any] = []
        if stmt.rels:
            for rel in stmt.rels:
                table_name = rel.relation.relname
                table = self._engine._tables.get(table_name)
                if table is None:
                    raise ValueError(f"Table '{table_name}' does not exist")
                tables_to_analyze.append(table)
        else:
            tables_to_analyze = list(self._engine._tables.values())

        catalog = self._engine._catalog
        for table in tables_to_analyze:
            stats = table.analyze()
            if catalog is not None:
                for col_name, cs in stats.items():
                    catalog.save_column_stats(
                        table.name, col_name,
                        cs.distinct_count, cs.null_count,
                        cs.min_value, cs.max_value, cs.row_count,
                        cs.histogram, cs.mcv_values, cs.mcv_frequencies,
                    )
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
        table_name = table.name if table is not None else None
        optimizer = QueryOptimizer(
            stats,
            column_stats,
            index_manager=ctx.index_manager,
            table_name=table_name,
        )
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
    # Physical execution (Volcano iterator model)
    # ==================================================================

    def _execute_relational(
        self,
        stmt: SelectStmt,
        pl: PostingList,
        ctx: ExecutionContext,
        table: Table | None,
    ) -> SQLResult:
        """Execute relational operations via physical operators.

        Builds a Volcano-model operator tree for GROUP BY, PROJECT,
        DISTINCT, ORDER BY, and LIMIT, then executes it to produce
        the final result.
        """
        from uqa.execution.batch import DataType, _SQL_TO_DTYPE
        from uqa.execution.scan import PostingListScanOp
        from uqa.execution.relational import (
            DistinctOp,
            ExprProjectOp,
            FilterOp as PhysFilterOp,
            HashAggOp,
            LimitOp,
            ProjectOp,
            SortOp,
            WindowOp,
        )

        # Build table schema for typed ColumnVectors
        schema: dict[str, DataType] = {}
        if table is not None:
            for name, col in table.columns.items():
                schema[name] = _SQL_TO_DTYPE.get(
                    col.type_name, DataType.TEXT
                )

        physical: Any = PostingListScanOp(
            pl,
            ctx.document_store,
            schema,
            graph_store=ctx.graph_store,
        )

        is_grouped = stmt.groupClause is not None
        is_agg_only = not is_grouped and self._has_aggregates(
            stmt.targetList
        )
        has_window = self._has_window_functions(stmt.targetList)
        expected_cols: list[str] | None = None

        if has_window:
            # Window functions: compute window values, then project
            win_specs = self._extract_window_specs(stmt.targetList)
            physical = WindowOp(
                physical, win_specs,
                spill_threshold=self._engine.spill_threshold,
            )

            # Build expected columns: non-window columns + window aliases
            expected_cols = []
            for target in stmt.targetList:
                val = target.val
                if isinstance(val, FuncCall) and val.over is not None:
                    alias = target.name or val.funcname[-1].sval.lower()
                    expected_cols.append(alias)
                elif isinstance(val, ColumnRef):
                    expected_cols.append(
                        target.name or self._extract_column_name(val)
                    )
                else:
                    expected_cols.append(
                        target.name or self._infer_target_name(target)
                    )

            # Project to expected columns
            physical = ProjectOp(physical, expected_cols)

        elif is_grouped:
            group_cols = [
                self._extract_column_name(g) for g in stmt.groupClause
            ]
            agg_specs = self._extract_agg_specs(stmt.targetList)
            physical = HashAggOp(
                physical, group_cols, agg_specs,
                spill_threshold=self._engine.spill_threshold,
            )

            if stmt.havingClause is not None:
                col, pred = self._resolve_having_predicate(
                    stmt.havingClause, stmt.targetList
                )
                physical = PhysFilterOp(physical, col, pred)

            expected_cols = group_cols + [a for a, _, _ in agg_specs]

        elif is_agg_only:
            agg_specs = self._extract_agg_specs(stmt.targetList)
            physical = HashAggOp(
                physical, [], agg_specs,
                spill_threshold=self._engine.spill_threshold,
            )
            expected_cols = [a for a, _, _ in agg_specs]

        else:
            is_star = self._is_select_star(stmt.targetList)
            if not is_star:
                if self._has_computed_expressions(stmt.targetList):
                    targets = self._build_expr_targets(stmt.targetList)
                    physical = ExprProjectOp(
                        physical, targets,
                        subquery_executor=self._compile_select,
                    )
                    expected_cols = [name for name, _ in targets]
                else:
                    proj_cols, proj_aliases = (
                        self._resolve_projection_cols(stmt.targetList)
                    )
                    physical = ProjectOp(
                        physical, proj_cols, proj_aliases
                    )
                    expected_cols = [
                        proj_aliases.get(c, c) for c in proj_cols
                    ]

        # DISTINCT
        if stmt.distinctClause is not None:
            distinct_cols = expected_cols
            if distinct_cols is None:
                distinct_cols = (
                    list(table.columns.keys())
                    if table is not None
                    else []
                )
            physical = DistinctOp(
                physical, distinct_cols,
                spill_threshold=self._engine.spill_threshold,
            )

        # ORDER BY
        if stmt.sortClause is not None:
            sort_keys = [
                (
                    self._extract_column_name(s.node),
                    s.sortby_dir == SortByDir.SORTBY_DESC,
                )
                for s in stmt.sortClause
            ]
            physical = SortOp(
                physical, sort_keys,
                spill_threshold=self._engine.spill_threshold,
            )

        # LIMIT / OFFSET
        if stmt.limitCount is not None:
            offset = 0
            if stmt.limitOffset is not None:
                offset = self._extract_int_value(stmt.limitOffset)
            physical = LimitOp(
                physical, self._extract_int_value(stmt.limitCount), offset
            )

        # Execute physical plan
        physical.open()
        rows: list[dict[str, Any]] = []
        while True:
            batch = physical.next()
            if batch is None:
                break
            rows.extend(batch.to_rows())
        physical.close()

        # Determine column names
        if expected_cols is not None:
            columns = expected_cols
        elif rows:
            columns = list(rows[0].keys())
        elif table is not None:
            columns = list(table.columns.keys())
        else:
            columns = []

        return SQLResult(columns, rows)

    @staticmethod
    def _is_select_star(target_list: tuple | None) -> bool:
        """Check if the target list is SELECT * or equivalent."""
        if target_list is None or len(target_list) == 0:
            return True
        for target in target_list:
            if isinstance(target.val, A_Star):
                return True
            if isinstance(target.val, ColumnRef):
                for field_node in target.val.fields:
                    if isinstance(field_node, A_Star):
                        return True
        return False

    def _resolve_projection_cols(
        self, target_list: tuple
    ) -> tuple[list[str], dict[str, str]]:
        """Resolve target list columns and aliases for ProjectOp."""
        proj_cols: list[str] = []
        proj_aliases: dict[str, str] = {}
        for target in target_list:
            if isinstance(target.val, ColumnRef):
                col = self._extract_column_name(target.val)
                proj_cols.append(col)
                if target.name and target.name != col:
                    proj_aliases[col] = target.name
            elif isinstance(target.val, FuncCall):
                func = target.val
                fn = func.funcname[-1].sval.lower()
                if fn in ("count", "sum", "avg", "min", "max"):
                    continue
                alias = target.name or fn
                if "_score" not in proj_cols:
                    proj_cols.append("_score")
                proj_aliases["_score"] = alias
        return proj_cols, proj_aliases

    @staticmethod
    def _has_computed_expressions(target_list: tuple | None) -> bool:
        """Check if any target is a computed expression (not a simple column)."""
        if target_list is None:
            return False
        for target in target_list:
            val = target.val
            if isinstance(val, ColumnRef):
                continue
            if isinstance(val, FuncCall):
                fn = val.funcname[-1].sval.lower()
                if fn in ("count", "sum", "avg", "min", "max"):
                    continue
                # Non-aggregate functions like UPPER(), LOWER() are computed
                if fn in ("text_match", "bayesian_match", "knn_match",
                          "traverse_match"):
                    continue
                return True
            if isinstance(val, (A_Const, A_Expr, CaseExpr, TypeCast,
                                CoalesceExpr, NullTest, SubLink)):
                return True
        return False

    def _build_expr_targets(
        self, target_list: tuple
    ) -> list[tuple[str, Any]]:
        """Build (output_name, ast_node) pairs for ExprProjectOp.

        For text_match/bayesian_match function calls, wraps the node
        so the ExprEvaluator reads ``_score`` from the row instead.
        """
        targets: list[tuple[str, Any]] = []
        for target in target_list:
            name = self._infer_target_name(target)
            val = target.val
            # text_match/bayesian_match -> read _score column
            if isinstance(val, FuncCall):
                fn = val.funcname[-1].sval.lower()
                if fn in ("text_match", "bayesian_match"):
                    from pglast.ast import ColumnRef, String as PgStr
                    val = ColumnRef(fields=(PgStr(sval="_score"),))
            targets.append((name, val))
        return targets

    def _infer_target_name(self, target: Any) -> str:
        """Infer the output column name for a single SELECT target."""
        if target.name:
            return target.name
        val = target.val
        if isinstance(val, ColumnRef):
            return self._extract_column_name(val)
        if isinstance(val, FuncCall):
            fn = val.funcname[-1].sval.lower()
            if fn in ("count", "sum", "avg", "min", "max"):
                arg_col = None if val.agg_star else (
                    self._extract_column_name(val.args[0])
                )
                return fn if arg_col is None else f"{fn}_{arg_col}"
            if fn in ("text_match", "bayesian_match"):
                return "_score"
            return fn
        if isinstance(val, TypeCast):
            if isinstance(val.arg, ColumnRef):
                return self._extract_column_name(val.arg)
            return val.typeName.names[-1].sval.lower()
        if isinstance(val, SubLink):
            # Scalar subquery without alias
            return "?column?"
        return "?column?"

    def _resolve_having_predicate(
        self, having_node: Any, target_list: tuple
    ) -> tuple[str, Predicate]:
        """Resolve HAVING clause into (column_name, predicate)."""
        alias_map: dict[str, str] = {}
        for target in target_list:
            if isinstance(target.val, FuncCall):
                func = target.val
                fn = func.funcname[-1].sval.lower()
                natural = (
                    fn
                    if func.agg_star
                    else f"{fn}_{self._extract_column_name(func.args[0])}"
                )
                alias_map[natural] = target.name or natural

        if isinstance(having_node, A_Expr) and isinstance(
            having_node.lexpr, FuncCall
        ):
            func = having_node.lexpr
            fn = func.funcname[-1].sval.lower()
            natural = (
                fn
                if func.agg_star
                else f"{fn}_{self._extract_column_name(func.args[0])}"
            )
            col_name = alias_map.get(natural, natural)
            pred = _op_to_predicate(
                having_node.name[0].sval,
                self._extract_const_value(having_node.rexpr),
            )
            return col_name, pred

        raise ValueError(
            f"Unsupported HAVING clause: {type(having_node).__name__}"
        )

    # ==================================================================
    # DQL: SELECT
    # ==================================================================

    def _compile_select(
        self, stmt: SelectStmt, *, explain: bool = False
    ) -> SQLResult:
        # 0. Materialize CTEs as temporary in-memory tables
        cte_names: list[str] = []
        if stmt.withClause is not None:
            cte_names = self._materialize_ctes(stmt.withClause.ctes)

        try:
            return self._compile_select_body(
                stmt, explain=explain
            )
        finally:
            # Clean up CTE temporary tables
            for name in cte_names:
                self._engine._tables.pop(name, None)
            # Clean up materialized view tables
            for name in self._expanded_views:
                self._engine._tables.pop(name, None)
            self._expanded_views.clear()

    def _compile_select_body(
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

        # 5-11. Execute relational operations via physical operators
        return self._execute_relational(stmt, pl, ctx, table)

    # -- CTE materialization -------------------------------------------

    def _materialize_ctes(self, ctes: tuple) -> list[str]:
        """Execute CTE queries and register results as temporary tables.

        Returns the list of CTE names for cleanup after the main query.
        """
        _type_map = {int: "integer", float: "real", str: "text"}
        cte_names: list[str] = []
        for cte in ctes:
            name = cte.ctename
            result = self._compile_select(cte.ctequery)

            # Infer column types from the first row
            col_defs: list[ColumnDef] = []
            for col_name in result.columns:
                py_type: type = str
                if result.rows:
                    sample = result.rows[0].get(col_name)
                    if isinstance(sample, int):
                        py_type = int
                    elif isinstance(sample, float):
                        py_type = float
                col_defs.append(ColumnDef(
                    name=col_name,
                    type_name=_type_map.get(py_type, "TEXT"),
                    python_type=py_type,
                ))

            table = Table(name=name, columns=col_defs)
            # Populate the table with CTE results
            for i, row in enumerate(result.rows):
                doc_id = i + 1
                doc = {"_id": doc_id}
                doc.update(row)
                table.document_store.put(doc_id, doc)
                # Index text fields for text_match support
                text_fields = {
                    col_def.name: str(row[col_def.name])
                    for col_def in col_defs
                    if row.get(col_def.name) is not None
                    and isinstance(row[col_def.name], str)
                }
                if text_fields:
                    table.inverted_index.add_document(doc_id, text_fields)

            self._engine._tables[name] = table
            cte_names.append(name)

        return cte_names

    # -- View expansion ------------------------------------------------

    def _expand_view(
        self, view_name: str, query: SelectStmt
    ) -> tuple[Table, None]:
        """Materialize a view's stored query into a temporary table.

        The temporary table is registered in ``_engine._tables`` and
        tracked in ``_expanded_views`` for cleanup after the enclosing
        query completes.
        """
        result = self._compile_select(query)

        _type_map = {int: "integer", float: "real", str: "text"}
        col_defs: list[ColumnDef] = []
        for col_name in result.columns:
            py_type: type = str
            if result.rows:
                sample = result.rows[0].get(col_name)
                if isinstance(sample, int):
                    py_type = int
                elif isinstance(sample, float):
                    py_type = float
            col_defs.append(ColumnDef(
                name=col_name,
                type_name=_type_map.get(py_type, "TEXT"),
                python_type=py_type,
            ))

        table = Table(name=view_name, columns=col_defs)
        for i, row in enumerate(result.rows):
            doc_id = i + 1
            doc = {"_id": doc_id}
            doc.update(row)
            table.document_store.put(doc_id, doc)
            text_fields = {
                cd.name: str(row[cd.name])
                for cd in col_defs
                if row.get(cd.name) is not None
                and isinstance(row[cd.name], str)
            }
            if text_fields:
                table.inverted_index.add_document(doc_id, text_fields)

        self._engine._tables[view_name] = table
        self._expanded_views.append(view_name)
        return table, None

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
                # Check if it is a view -- expand by materializing the
                # stored query into a temporary table.
                view_query = self._engine._views.get(table_name)
                if view_query is not None:
                    return self._expand_view(table_name, view_query)
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

        index_manager = getattr(self._engine, "_index_manager", None)

        if table is None:
            return self._engine._build_context()

        parallel_executor = getattr(
            self._engine, "_parallel_executor", None
        )

        return ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
            vector_index=self._engine.vector_index,
            graph_store=self._engine.graph_store,
            block_max_index=self._engine.block_max_index,
            index_manager=index_manager,
            parallel_executor=parallel_executor,
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
                view_query = self._engine._views.get(table_name)
                if view_query is not None:
                    return self._expand_view(table_name, view_query)
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
        if isinstance(node, NullTest):
            return self._compile_null_test(node)
        if isinstance(node, SubLink):
            return self._compile_sublink_in_where(node, ctx)
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
            # Simple case: column op constant
            if isinstance(node.lexpr, ColumnRef) and isinstance(
                node.rexpr, A_Const
            ):
                field_name = self._extract_column_name(node.lexpr)
                value = self._extract_const_value(node.rexpr)
                return FilterOperator(
                    field_name,
                    _op_to_predicate(node.name[0].sval, value),
                )
            # Expression-based comparison (e.g., price * 2 > 100)
            return _ExprFilterOperator(
                node, subquery_executor=self._compile_select
            )

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
            from uqa.core.types import Like, NotLike
            field_name = self._extract_column_name(node.lexpr)
            pattern = self._extract_string_value(node.rexpr)
            op_name = node.name[0].sval
            if op_name == "!~~":
                return FilterOperator(field_name, NotLike(pattern))
            return FilterOperator(field_name, Like(pattern))

        if kind == A_Expr_Kind.AEXPR_ILIKE:
            from uqa.core.types import ILike, NotILike
            field_name = self._extract_column_name(node.lexpr)
            pattern = self._extract_string_value(node.rexpr)
            op_name = node.name[0].sval
            if op_name == "!~~*":
                return FilterOperator(field_name, NotILike(pattern))
            return FilterOperator(field_name, ILike(pattern))

        raise ValueError(f"Unsupported expression kind: {kind}")

    def _compile_null_test(self, node: NullTest) -> Any:
        from uqa.core.types import IsNull, IsNotNull
        from uqa.operators.primitive import FilterOperator

        field_name = self._extract_column_name(node.arg)
        if NullTestType(node.nulltesttype) == NullTestType.IS_NULL:
            return FilterOperator(field_name, IsNull())
        return FilterOperator(field_name, IsNotNull())

    def _compile_sublink_in_where(
        self, node: SubLink, ctx: ExecutionContext
    ) -> Any:
        """Compile a SubLink (subquery) in WHERE position.

        Supports:
        - ANY_SUBLINK: ``WHERE col IN (SELECT ...)``
        - EXISTS_SUBLINK: ``WHERE EXISTS (SELECT ...)``

        Correlated subqueries (inner query references outer table) are
        routed to per-row evaluation via ``_ExprFilterOperator``.
        """
        # Detect correlated subqueries -- route to per-row evaluation
        if self._is_correlated(node.subselect):
            return _ExprFilterOperator(
                node, subquery_executor=self._compile_select
            )

        from uqa.operators.primitive import FilterOperator

        link_type = SubLinkType(node.subLinkType)

        if link_type == SubLinkType.ANY_SUBLINK:
            # IN (SELECT ...) -- execute subquery, collect values, use InSet
            inner_result = self._compile_select(node.subselect)
            if not inner_result.columns:
                raise ValueError("Subquery must return at least one column")
            sub_col = inner_result.columns[0]
            values = frozenset(
                row[sub_col] for row in inner_result.rows
                if row.get(sub_col) is not None
            )
            field_name = self._extract_column_name(node.testexpr)
            return FilterOperator(field_name, InSet(values))

        if link_type == SubLinkType.EXISTS_SUBLINK:
            # EXISTS (SELECT ...) -- execute subquery
            inner_result = self._compile_select(node.subselect)
            if inner_result.rows:
                return _ScanOperator()
            # No rows => empty result -- return an operator that yields nothing
            from uqa.operators.boolean import ComplementOperator
            scan = _ScanOperator()
            return ComplementOperator(scan)

        raise ValueError(
            f"Unsupported subquery type: {link_type.name}"
        )

    def _is_correlated(self, subselect: Any) -> bool:
        """Check if a subquery contains correlated column references.

        A correlated reference is a multi-part ColumnRef (e.g., ``e.dept``)
        whose qualifier does not match any table in the inner FROM clause.
        """
        inner_tables: set[str] = set()
        if subselect.fromClause:
            for from_item in subselect.fromClause:
                if isinstance(from_item, RangeVar):
                    if from_item.alias:
                        inner_tables.add(from_item.alias.aliasname)
                    inner_tables.add(from_item.relname)

        return self._has_outer_refs(subselect, inner_tables)

    def _has_outer_refs(self, node: Any, inner_tables: set[str]) -> bool:
        """Recursively check for outer column references."""
        if isinstance(node, ColumnRef):
            if len(node.fields) >= 2:
                qualifier = node.fields[0].sval
                return qualifier not in inner_tables
            return False

        if isinstance(node, (tuple, list)):
            return any(
                self._has_outer_refs(item, inner_tables)
                for item in node
            )

        if hasattr(node, '__slots__') and isinstance(node.__slots__, dict):
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is not None and self._has_outer_refs(
                    val, inner_tables
                ):
                    return True

        return False

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
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        if name == "fuse_log_odds":
            return self._make_fusion_op(args, ctx, mode="log_odds")
        if name == "fuse_prob_and":
            return self._make_fusion_op(args, ctx, mode="prob_and")
        if name == "fuse_prob_or":
            return self._make_fusion_op(args, ctx, mode="prob_or")
        if name == "fuse_prob_not":
            return self._make_prob_not_op(args, ctx)
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

    def _make_traverse_match_op(self, args: tuple) -> Any:
        """traverse_match(start_id, 'label', max_hops) as a WHERE signal.

        Returns a posting list of reachable vertices with score = 0.9.
        """
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        return TraverseOperator(start, label, max_hops)

    def _compile_calibrated_signal(
        self, node: FuncCall, ctx: ExecutionContext
    ) -> Any:
        """Compile a signal function into an operator that produces
        calibrated probabilities in (0, 1).

        - text_match -> Bayesian BM25 (not raw BM25)
        - bayesian_match -> Bayesian BM25 (already calibrated)
        - knn_match -> cosine similarity mapped via P = (1 + sim) / 2
        - traverse_match -> graph reachability score 0.9 (already calibrated)
        """
        name = node.funcname[-1].sval.lower()
        args = node.args or ()

        if name == "text_match":
            field_name = self._extract_column_name(args[0])
            query = self._extract_string_value(args[1])
            return self._make_text_search_op(field_name, query, ctx, bayesian=True)
        if name == "bayesian_match":
            field_name = self._extract_column_name(args[0])
            query = self._extract_string_value(args[1])
            return self._make_text_search_op(field_name, query, ctx, bayesian=True)
        if name == "knn_match":
            return self._make_calibrated_knn_op(self._extract_int_value(args[0]))
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        raise ValueError(
            f"Unknown signal function for fusion: {name}. "
            f"Use text_match, bayesian_match, knn_match, or traverse_match."
        )

    def _make_calibrated_knn_op(self, k: int) -> Any:
        """KNN search with scores calibrated to probabilities via
        P_vector = (1 + cosine_similarity) / 2 (Definition 7.1.2, Paper 3).
        """
        from uqa.operators.primitive import KNNOperator

        if self._query_vector is None:
            raise ValueError(
                "No query vector registered. "
                "Call set_query_vector() before using knn_match()."
            )
        return _CalibratedKNNOperator(self._query_vector, k)

    def _make_prob_not_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """fuse_prob_not(signal) -- probabilistic complement of a single signal."""
        from uqa.operators.hybrid import ProbNotOperator

        if len(args) != 1 or not isinstance(args[0], FuncCall):
            raise ValueError(
                "fuse_prob_not() requires exactly 1 signal function argument"
            )
        signal = self._compile_calibrated_signal(args[0], ctx)
        return ProbNotOperator(signal)

    def _make_fusion_op(
        self, args: tuple, ctx: ExecutionContext, *, mode: str
    ) -> Any:
        """Build a fusion operator from nested function calls.

        fuse_log_odds(signal1, signal2, ...[, alpha])
        fuse_prob_and(signal1, signal2, ...)
        fuse_prob_or(signal1, signal2, ...)

        Each signal argument must be a FuncCall (text_match, bayesian_match,
        knn_match, traverse_match). For fuse_log_odds, the last argument may
        be a numeric literal specifying the confidence alpha.

        Signal scores are calibrated to probabilities in (0, 1):
        - text_match is compiled as bayesian_match (Bayesian BM25)
        - knn_match applies P_vector = (1 + cosine_sim) / 2
        - traverse_match and bayesian_match are already calibrated
        """
        from uqa.operators.hybrid import LogOddsFusionOperator, ProbBoolFusionOperator

        signals: list[Any] = []
        alpha = 0.5

        for arg in args:
            if isinstance(arg, FuncCall):
                signals.append(self._compile_calibrated_signal(arg, ctx))
            elif isinstance(arg, A_Const) and mode == "log_odds":
                # Trailing numeric argument = alpha
                alpha = float(self._extract_const_value(arg))
            else:
                raise ValueError(
                    f"Fusion function arguments must be signal functions "
                    f"(text_match, knn_match, etc.), got {type(arg).__name__}"
                )

        if len(signals) < 2:
            raise ValueError("Fusion requires at least 2 signal functions")

        if mode == "log_odds":
            return LogOddsFusionOperator(signals, alpha=alpha)
        if mode == "prob_and":
            return ProbBoolFusionOperator(signals, mode="and")
        return ProbBoolFusionOperator(signals, mode="or")

    # -- Aggregation ---------------------------------------------------

    def _has_aggregates(self, target_list: tuple | None) -> bool:
        if target_list is None:
            return False
        return any(
            isinstance(t.val, FuncCall)
            and t.val.funcname[-1].sval.lower() in ("count", "sum", "avg", "min", "max")
            and (t.val.over is None)
            for t in target_list
        )

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

    # -- Window functions -----------------------------------------------

    @staticmethod
    def _has_window_functions(target_list: tuple | None) -> bool:
        if target_list is None:
            return False
        return any(
            isinstance(t.val, FuncCall) and t.val.over is not None
            for t in target_list
        )

    def _extract_window_specs(
        self, target_list: tuple
    ) -> list[WindowSpec]:
        """Extract window function specs from the target list."""
        from uqa.execution.relational import WindowSpec
        from uqa.sql.expr_evaluator import ExprEvaluator

        specs: list[WindowSpec] = []
        for target in target_list:
            val = target.val
            if not isinstance(val, FuncCall) or val.over is None:
                continue

            func_name = val.funcname[-1].sval.lower()
            alias = target.name or func_name
            win = val.over

            # Partition columns
            part_cols: list[str] = []
            if win.partitionClause:
                for p in win.partitionClause:
                    part_cols.append(self._extract_column_name(p))

            # Order keys
            order_keys: list[tuple[str, bool]] = []
            if win.orderClause:
                for s in win.orderClause:
                    col = self._extract_column_name(s.node)
                    desc = s.sortby_dir == SortByDir.SORTBY_DESC
                    order_keys.append((col, desc))

            # Build WindowSpec with typed fields
            arg_col: str | None = None
            offset = 1
            default_value: Any = None
            ntile_buckets = 1

            if func_name in ("lag", "lead"):
                evaluator = ExprEvaluator()
                if val.args:
                    arg_col = self._extract_column_name(val.args[0])
                    if len(val.args) > 1:
                        offset = int(evaluator.evaluate(val.args[1], {}))
                    if len(val.args) > 2:
                        default_value = evaluator.evaluate(
                            val.args[2], {}
                        )
            elif func_name == "ntile":
                evaluator = ExprEvaluator()
                if val.args:
                    ntile_buckets = int(
                        evaluator.evaluate(val.args[0], {})
                    )
            elif func_name not in ("row_number", "rank", "dense_rank"):
                # Aggregate window functions (SUM, COUNT, AVG, MIN, MAX)
                if not val.agg_star and val.args:
                    arg_col = self._extract_column_name(val.args[0])

            specs.append(WindowSpec(
                alias=alias,
                func_name=func_name,
                partition_cols=part_cols,
                order_keys=order_keys,
                arg_col=arg_col,
                offset=offset,
                default_value=default_value,
                ntile_buckets=ntile_buckets,
            ))

        return specs

    # -- Result conversion ---------------------------------------------

    def _scan_all(self, ctx: ExecutionContext) -> PostingList:
        all_ids = sorted(ctx.document_store.doc_ids)
        return PostingList([PostingEntry(d, Payload(score=0.0)) for d in all_ids])

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


class _CalibratedKNNOperator:
    """KNN search with scores calibrated to probabilities.

    P_vector = (1 + cosine_similarity) / 2  (Definition 7.1.2, Paper 3)

    Maps cosine similarity [-1, 1] to probability [0, 1]:
    - similarity = 1.0  ->  P = 1.0  (identical)
    - similarity = 0.0  ->  P = 0.5  (orthogonal, neutral)
    - similarity = -1.0 ->  P = 0.0  (opposite)
    """

    def __init__(self, query_vector: Any, k: int) -> None:
        self.query_vector = query_vector
        self.k = k

    def execute(self, context: Any) -> PostingList:
        vec_idx = context.vector_index
        if vec_idx is None:
            return PostingList()
        raw_pl = vec_idx.search_knn(self.query_vector, self.k)
        entries = [
            PostingEntry(
                e.doc_id,
                Payload(score=(1.0 + e.payload.score) / 2.0),
            )
            for e in raw_pl
        ]
        return PostingList(entries)

    def cost_estimate(self, stats: Any) -> float:
        import math
        return float(stats.dimensions) * math.log2(stats.total_docs + 1)


class _ExprFilterOperator:
    """Filter rows using an arbitrary expression via ExprEvaluator.

    Used for WHERE clauses that cannot be reduced to a simple
    ``FilterOperator(field, predicate)`` -- e.g. ``WHERE price * 2 > 100``.
    """

    def __init__(
        self, expr_node: Any, subquery_executor: Any = None
    ) -> None:
        self.expr_node = expr_node
        self._subquery_executor = subquery_executor

    def execute(self, context: Any) -> PostingList:
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator(
            subquery_executor=self._subquery_executor
        )
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        entries: list[PostingEntry] = []
        for doc_id in sorted(doc_store.doc_ids):
            doc = doc_store.get(doc_id)
            if doc is None:
                continue
            result = evaluator.evaluate(self.expr_node, doc)
            if result:
                entries.append(PostingEntry(doc_id, Payload(score=0.0)))
        return PostingList(entries)

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
