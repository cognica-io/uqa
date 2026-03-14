#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQL-to-UQA compiler using pglast (PostgreSQL parser).

Supported statements:
  DDL:
    CREATE [TEMPORARY | TEMP] TABLE name (col type [constraints], ...)
    CREATE [TEMP] TABLE name AS SELECT ...
    DROP TABLE [IF EXISTS] name
    CREATE VIEW name AS SELECT ...
    DROP VIEW [IF EXISTS] name
    CREATE SEQUENCE name [START n] [INCREMENT n]
    ALTER SEQUENCE name [RESTART [WITH n]] [INCREMENT [BY] n] [START [WITH] n]
  Constraints:
    PRIMARY KEY, NOT NULL, DEFAULT val, UNIQUE, CHECK (expr)
    REFERENCES parent(col)           -- column-level FOREIGN KEY
    FOREIGN KEY (col) REFERENCES parent(col) -- table-level FOREIGN KEY
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
  bayesian_match_with_prior(field, 'query', prior_field, prior_mode)
                                     -- Bayesian BM25 with external prior
  knn_match(field, vector, k)        -- KNN vector search
  traverse_match(start, 'label', k)  -- graph reachability as a scored signal
  path_filter('path', value)         -- hierarchical path filter (equality)
  path_filter('path', 'op', value)   -- hierarchical path filter with operator
  vector_exclude(field, pos, neg, k, threshold) -- vector exclusion
  multi_field_match(field1, field2, ..., 'query' [, w1, w2, ...])
                                     -- multi-field Bayesian BM25 search

  Vector arguments accept ARRAY literals or $N parameter references:
    knn_match(embedding, ARRAY[0.1, 0.2, ...], 5)
    knn_match(embedding, $1, 5)  -- with params=[query_vec]

Fusion meta-functions (WHERE clause):
  fuse_log_odds(sig1, sig2, ...[, alpha]) -- log-odds conjunction (Paper 4)
  fuse_prob_and(sig1, sig2, ...)          -- probabilistic AND
  fuse_prob_or(sig1, sig2, ...)           -- probabilistic OR
  fuse_prob_not(signal)                   -- probabilistic NOT (complement)
  fuse_attention(sig1, sig2, ...)         -- attention-weighted fusion (Paper 4 S8)
  fuse_learned(sig1, sig2, ...)           -- learned-weight fusion (Paper 4 S8)
  sparse_threshold(signal, threshold)     -- ReLU thresholding (Paper 4 S6.5)

SELECT scalar functions:
  path_agg('path', 'func')          -- per-row nested array aggregation
  path_value('path')                 -- access nested field value

FROM-clause table functions:
  traverse(start_id, 'label', max_hops) -- graph traversal
  rpq('path_expr', start_id)            -- regular path query
  regexp_split_to_table(str, pattern [, flags]) -- split string by regex
"""

# pyright: reportArgumentType=false, reportAssignmentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportOperatorIssue=false, reportReturnType=false

from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pglast import parse_sql as _parse_sql_raw
from pglast.ast import (
    A_ArrayExpr,
    A_Const,
    A_Expr,
    A_Star,
    AlterSeqStmt,
    AlterTableStmt,
    BoolExpr,
    CaseExpr,
    CoalesceExpr,
    ColumnRef,
    CreateForeignServerStmt,
    CreateForeignTableStmt,
    CreateSeqStmt,
    CreateStmt,
    CreateTableAsStmt,
    DeallocateStmt,
    DeleteStmt,
    DropStmt,
    ExecuteStmt,
    ExplainStmt,
    FuncCall,
    IndexStmt,
    InsertStmt,
    JoinExpr,
    NullTest,
    ParamRef,
    PrepareStmt,
    RangeFunction,
    RangeSubselect,
    RangeVar,
    RenameStmt,
    SelectStmt,
    SubLink,
    TransactionStmt,
    TruncateStmt,
    TypeCast,
    UpdateStmt,
    VacuumStmt,
    ViewStmt,
)
from pglast.ast import (
    Boolean as PgBoolean,
)
from pglast.ast import (
    Constraint as PgConstraint,
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
from pglast.enums.nodes import JoinType, OnConflictAction
from pglast.enums.parsenodes import (
    A_Expr_Kind,
    AlterTableType,
    ConstrType,
    ObjectType,
    SetOperation,
    SortByDir,
    SortByNulls,
)
from pglast.enums.primnodes import BoolExprType, NullTestType, SubLinkType

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
from uqa.operators.base import Operator
from uqa.sql.table import (
    _AUTO_INCREMENT_TYPES,
    ColumnDef,
    ForeignKeyDef,
    Table,
    resolve_type,
)

if TYPE_CHECKING:
    import pyarrow as pa

    from uqa.engine import Engine
    from uqa.execution.relational import WindowSpec
    from uqa.operators.base import ExecutionContext


@lru_cache(maxsize=256)
def _parse_sql_cached(sql: str) -> tuple:
    return _parse_sql_raw(sql)


# ======================================================================
# Result type
# ======================================================================


class SQLResult:
    """Result of a SQL query: columns + rows.

    When constructed from the physical execution engine, the original
    Arrow RecordBatches are preserved so that ``to_arrow()`` returns a
    zero-copy ``pyarrow.Table`` without an intermediate dict round-trip.
    """

    __slots__ = ("_batches", "_rows", "columns")

    def __init__(
        self,
        columns: list[str],
        rows: list[dict[str, Any]],
        *,
        batches: list[Any] | None = None,
    ) -> None:
        self.columns = columns
        self._rows = rows
        self._batches = batches

    @property
    def rows(self) -> list[dict[str, Any]]:
        if self._rows is None:
            self._rows = _batches_to_rows(self._batches, self.columns)
        return self._rows

    def __len__(self) -> int:
        if self._rows is not None:
            return len(self._rows)
        if self._batches:
            return sum(b.num_rows for b in self._batches)
        return 0

    def __iter__(self):
        if self._rows is not None:
            return iter(self._rows)
        if self._batches:
            return _iter_batches(self._batches)
        return iter([])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SQLResult):
            return NotImplemented
        return self.columns == other.columns and self.rows == other.rows

    def __repr__(self) -> str:
        return f"SQLResult(columns={self.columns}, {len(self)} rows)"

    def __str__(self) -> str:
        rows = self.rows
        if not rows:
            return "(0 rows)"
        col_widths: dict[str, int] = {}
        for col in self.columns:
            col_widths[col] = len(col)
        str_rows: list[dict[str, str]] = []
        for row in rows:
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
        parts.append(f"({len(rows)} rows)")
        return "\n".join(parts)

    def to_arrow(self) -> pa.Table:
        """Convert this result to a ``pyarrow.Table``.

        When the result was produced by the physical execution engine,
        the original Arrow RecordBatches are concatenated directly
        without an intermediate Python-dict conversion.
        """
        import pyarrow as pa

        if self._batches:
            table = pa.Table.from_batches(self._batches)
            if list(table.column_names) != self.columns:
                table = table.select(self.columns)
            return table

        rows = self.rows
        if not rows:
            arrays = [pa.array([], type=pa.string()) for _ in self.columns]
            return pa.table({col: arr for col, arr in zip(self.columns, arrays)})

        col_values: dict[str, list[Any]] = {col: [] for col in self.columns}
        for row in rows:
            for col in self.columns:
                col_values[col].append(row.get(col))

        arrays: dict[str, pa.Array] = {}
        for col in self.columns:
            values = col_values[col]
            arrays[col] = pa.array(values, type=_infer_arrow_type(values))

        return pa.table(arrays)

    def to_parquet(self, path: str) -> None:
        """Write this result to a Parquet file at *path*."""
        import pyarrow.parquet as pq

        pq.write_table(self.to_arrow(), path)


def _iter_batches(batches: list[Any]):
    """Yield row dicts from Arrow RecordBatches without materializing all at once."""
    for rb in batches:
        pydict = rb.to_pydict()
        names = rb.schema.names
        for i in range(rb.num_rows):
            yield {name: pydict[name][i] for name in names}


def _batches_to_rows(
    batches: list[Any] | None, columns: list[str]
) -> list[dict[str, Any]]:
    """Convert Arrow RecordBatches to row dicts."""
    if not batches:
        return []
    return list(_iter_batches(batches))


def _format_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _infer_arrow_type(values: list[Any]) -> pa.DataType:
    """Infer a pyarrow type from a list of Python values."""
    import datetime

    import pyarrow as pa

    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            return pa.bool_()
        if isinstance(v, int):
            return pa.int64()
        if isinstance(v, float):
            return pa.float64()
        if isinstance(v, datetime.datetime):
            return pa.timestamp("us")
        if isinstance(v, datetime.date):
            return pa.date32()
        if isinstance(v, datetime.time):
            return pa.time64("us")
        if isinstance(v, datetime.timedelta):
            return pa.duration("us")
        if isinstance(v, bytes):
            return pa.binary()
        if isinstance(v, list):
            return pa.list_(_infer_arrow_type(v))
        return pa.string()
    return pa.string()


# ======================================================================
# Compiler
# ======================================================================

_AGG_FUNC_NAMES = frozenset(
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

# Two-argument statistical aggregates where extra carries the x column.
_TWO_ARG_STAT_AGGS = frozenset(
    {
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


class SQLCompiler:
    """Compiles SQL statements into UQA operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._params: list[Any] = []
        self._expanded_views: list[str] = []
        self._shadowed_tables: dict[str, Table] = {}
        self._inlined_ctes: dict[str, SelectStmt] = {}

    def execute(self, sql: str, params: list[Any] | None = None) -> SQLResult:
        """Parse and execute a SQL statement.

        *params* is an optional list of parameter values for ``$1``,
        ``$2``, ... placeholders.  Values can be any Python object
        (scalars, numpy arrays, etc.).
        """
        self._params = list(params) if params else []
        stmts = _parse_sql_cached(sql)
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
        if isinstance(stmt, AlterTableStmt):
            return self._compile_alter_table(stmt)
        if isinstance(stmt, RenameStmt):
            return self._compile_rename(stmt)
        if isinstance(stmt, TruncateStmt):
            return self._compile_truncate(stmt)
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
        if isinstance(stmt, CreateTableAsStmt):
            return self._compile_create_table_as(stmt)
        if isinstance(stmt, CreateSeqStmt):
            return self._compile_create_sequence(stmt)
        if isinstance(stmt, AlterSeqStmt):
            return self._compile_alter_sequence(stmt)
        if isinstance(stmt, CreateForeignServerStmt):
            return self._compile_create_foreign_server(stmt)
        if isinstance(stmt, CreateForeignTableStmt):
            return self._compile_create_foreign_table(stmt)
        raise ValueError(f"Unsupported statement: {type(stmt).__name__}")

    def _get_table(self, table_name: str) -> Table:
        """Look up a table by name, raising ValueError if not found."""
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table

    # ==================================================================
    # DDL: CREATE TABLE / DROP TABLE
    # ==================================================================

    def _compile_create_table(self, stmt: CreateStmt) -> SQLResult:
        table_name = stmt.relation.relname
        if table_name in self._engine._tables:
            if not stmt.if_not_exists:
                raise ValueError(f"Table '{table_name}' already exists")
            return SQLResult([], [])

        columns: list[ColumnDef] = []
        check_exprs: list[tuple[str, Any]] = []
        fk_defs: list[ForeignKeyDef] = []
        for elt in stmt.tableElts:
            # Table-level constraints (e.g., FOREIGN KEY (...) REFERENCES ...)
            if isinstance(elt, PgConstraint):
                ct = ConstrType(elt.contype)
                if ct == ConstrType.CONSTR_FOREIGN:
                    ref_table = elt.pktable.relname
                    fk_cols = (
                        [attr.sval for attr in elt.fk_attrs] if elt.fk_attrs else []
                    )
                    pk_cols = (
                        [attr.sval for attr in elt.pk_attrs] if elt.pk_attrs else []
                    )
                    for fk_col, pk_col in zip(fk_cols, pk_cols):
                        fk_defs.append(
                            ForeignKeyDef(
                                column=fk_col,
                                ref_table=ref_table,
                                ref_column=pk_col,
                            )
                        )
                continue

            col, check_expr, fk_def = self._parse_column_def(elt)
            columns.append(col)
            if check_expr is not None:
                check_exprs.append((col.name, check_expr))
            if fk_def is not None:
                fk_defs.append(fk_def)

        # Temporary tables always use in-memory storage, even when
        # the engine has a persistent catalog.
        is_temp = stmt.relation.relpersistence == "t"
        if is_temp:
            conn = None
        else:
            catalog = self._engine._catalog
            conn = catalog.conn if catalog is not None else None

        table = Table(table_name, columns, conn=conn)

        # Register CHECK constraints with ExprEvaluator closures
        if check_exprs:
            from uqa.sql.expr_evaluator import ExprEvaluator

            evaluator = ExprEvaluator()
            for name, expr in check_exprs:
                table.check_constraints.append(
                    (name, lambda row, e=expr, ev=evaluator: ev.evaluate(e, row))
                )

        # Register FOREIGN KEY constraints and validators
        if fk_defs:
            table.foreign_keys.extend(fk_defs)
            self._register_fk_validators(table, fk_defs)

        self._engine._tables[table_name] = table

        if is_temp:
            self._engine._temp_tables.add(table_name)
        elif self._engine._catalog is not None:
            self._engine._catalog.save_table_schema(
                table_name,
                [
                    {
                        "name": col.name,
                        "type_name": col.type_name,
                        "primary_key": col.primary_key,
                        "not_null": col.not_null,
                        "auto_increment": col.auto_increment,
                        "default": col.default,
                        "vector_dimensions": col.vector_dimensions,
                        "unique": col.unique,
                    }
                    for col in columns
                ],
            )

        return SQLResult([], [])

    def _compile_create_table_as(self, stmt: CreateTableAsStmt) -> SQLResult:
        """CREATE TABLE name AS SELECT ... / CREATE TEMP TABLE ..."""
        table_name = stmt.into.rel.relname
        if table_name in self._engine._tables:
            raise ValueError(f"Table '{table_name}' already exists")

        result = self._compile_select(stmt.query)

        # Infer column definitions from query result
        columns: list[ColumnDef] = []
        for col_name in result.columns:
            # Infer type from first row value
            py_type = str
            type_name = "text"
            if result.rows:
                sample = result.rows[0].get(col_name)
                if isinstance(sample, int):
                    py_type = int
                    type_name = "integer"
                elif isinstance(sample, float):
                    py_type = float
                    type_name = "real"
                elif isinstance(sample, bool):
                    py_type = bool
                    type_name = "boolean"
                elif isinstance(sample, list):
                    py_type = list
                    type_name = "text[]"
                elif isinstance(sample, dict):
                    py_type = object
                    type_name = "jsonb"
            columns.append(
                ColumnDef(
                    name=col_name,
                    type_name=type_name,
                    python_type=py_type,
                )
            )

        # Temporary tables always use in-memory storage
        is_temp = stmt.into.rel.relpersistence == "t"
        if is_temp:
            conn = None
        else:
            catalog = self._engine._catalog
            conn = catalog.conn if catalog is not None else None

        table = Table(table_name, columns, conn=conn)
        self._engine._tables[table_name] = table

        if is_temp:
            self._engine._temp_tables.add(table_name)
        elif self._engine._catalog is not None:
            self._engine._catalog.save_table_schema(
                table_name,
                [
                    {
                        "name": col.name,
                        "type_name": col.type_name,
                        "primary_key": col.primary_key,
                        "not_null": col.not_null,
                        "auto_increment": col.auto_increment,
                        "default": col.default,
                        "vector_dimensions": col.vector_dimensions,
                        "unique": col.unique,
                    }
                    for col in columns
                ],
            )

        # Insert result rows (use only declared columns)
        inserted = 0
        for row in result.rows:
            clean = {c: row.get(c) for c in result.columns}
            table.insert(clean)
            inserted += 1

        return SQLResult(["inserted"], [{"inserted": inserted}])

    def _compile_create_sequence(self, stmt: CreateSeqStmt) -> SQLResult:
        """CREATE SEQUENCE name [START n] [INCREMENT n] [MINVALUE n] [MAXVALUE n]."""
        seq_name = stmt.sequence.relname
        if seq_name in self._engine._sequences:
            if stmt.if_not_exists:
                return SQLResult([], [])
            raise ValueError(f"Sequence '{seq_name}' already exists")

        start = 1
        increment = 1
        if stmt.options:
            for opt in stmt.options:
                if opt.defname == "start":
                    start = opt.arg.ival
                elif opt.defname == "increment":
                    increment = opt.arg.ival

        self._engine._sequences[seq_name] = {
            "current": start - increment,
            "start": start,
            "increment": increment,
        }
        return SQLResult([], [])

    def _compile_alter_sequence(self, stmt: AlterSeqStmt) -> SQLResult:
        """ALTER SEQUENCE name [RESTART [WITH n]] [INCREMENT [BY] n] [START [WITH] n]."""
        seq_name = stmt.sequence.relname
        seq = self._engine._sequences.get(seq_name)
        if seq is None:
            raise ValueError(f"Sequence '{seq_name}' does not exist")

        if stmt.options:
            for opt in stmt.options:
                if opt.defname == "restart":
                    if opt.arg is not None:
                        restart_val = opt.arg.ival
                    else:
                        restart_val = seq["start"]
                    seq["current"] = restart_val - seq["increment"]
                elif opt.defname == "increment":
                    seq["increment"] = opt.arg.ival
                elif opt.defname == "start":
                    seq["start"] = opt.arg.ival

        return SQLResult([], [])

    def _parse_column_def(
        self,
        node: Any,
    ) -> tuple[ColumnDef, Any, ForeignKeyDef | None]:
        """Parse a ColumnDef node into (ColumnDef, check_expr, fk_def).

        Returns a triple of column definition, optional CHECK expression
        AST node, and optional FOREIGN KEY definition.
        """
        col_name: str = node.colname
        type_names = node.typeName.names
        raw_type, python_type = resolve_type(type_names, node.typeName.arrayBounds)

        # VECTOR(N) -- extract dimensions from type modifier
        vector_dimensions: int | None = None
        if raw_type == "vector":
            typmods = node.typeName.typmods
            if typmods and isinstance(typmods[0], A_Const):
                vector_dimensions = self._extract_int_value(typmods[0])
            else:
                raise ValueError(
                    f"VECTOR column '{col_name}' requires dimensions, e.g. VECTOR(128)"
                )

        primary_key = False
        not_null = False
        default = None
        unique = False
        check_expr = None
        fk_def: ForeignKeyDef | None = None

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
                elif ct == ConstrType.CONSTR_UNIQUE:
                    unique = True
                elif ct == ConstrType.CONSTR_CHECK:
                    check_expr = constraint.raw_expr
                elif ct == ConstrType.CONSTR_FOREIGN:
                    ref_table = constraint.pktable.relname
                    ref_col = (
                        constraint.pk_attrs[0].sval if constraint.pk_attrs else None
                    )
                    if ref_col is not None:
                        fk_def = ForeignKeyDef(
                            column=col_name,
                            ref_table=ref_table,
                            ref_column=ref_col,
                        )

        auto_increment = raw_type in _AUTO_INCREMENT_TYPES

        # NUMERIC(precision, scale) -- extract from type modifiers
        numeric_precision: int | None = None
        numeric_scale: int | None = None
        if raw_type in ("numeric", "decimal"):
            typmods = node.typeName.typmods
            if typmods and len(typmods) >= 2:
                numeric_precision = self._extract_int_value(typmods[0])
                numeric_scale = self._extract_int_value(typmods[1])
            elif typmods and len(typmods) == 1:
                numeric_precision = self._extract_int_value(typmods[0])
                numeric_scale = 0

        return (
            ColumnDef(
                name=col_name,
                type_name=raw_type,
                python_type=python_type,
                primary_key=primary_key,
                not_null=not_null,
                auto_increment=auto_increment,
                default=default,
                vector_dimensions=vector_dimensions,
                unique=unique,
                numeric_precision=numeric_precision,
                numeric_scale=numeric_scale,
            ),
            check_expr,
            fk_def,
        )

    def _register_fk_validators(
        self,
        table: Table,
        fk_defs: list[ForeignKeyDef],
    ) -> None:
        """Install insert/delete/update validator closures for FK constraints.

        Each closure captures the engine reference so it can look up the
        referenced (parent) table at validation time.
        """
        engine = self._engine

        for fk in fk_defs:
            fk_col = fk.column
            ref_table_name = fk.ref_table
            ref_col = fk.ref_column
            child_table_name = table.name

            # -- INSERT validator: new FK value must exist in parent ----
            def _validate_insert(
                row: dict[str, Any],
                _fk_col: str = fk_col,
                _ref_table: str = ref_table_name,
                _ref_col: str = ref_col,
                _child_table: str = child_table_name,
                _engine: Any = engine,
            ) -> None:
                value = row.get(_fk_col)
                if value is None:
                    return  # NULL FK is allowed
                parent = _engine._tables.get(_ref_table)
                if parent is None:
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"referenced table '{_ref_table}' does not exist"
                    )
                if not parent.document_store.has_value(_ref_col, value):
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"key ({_fk_col})=({value}) in table "
                        f"'{_child_table}' is not present in "
                        f"table '{_ref_table}'"
                    )

            table.fk_insert_validators.append(_validate_insert)

            # -- DELETE validator on parent: block if children exist ----
            def _validate_delete(
                doc_id: int,
                _fk_col: str = fk_col,
                _ref_table: str = ref_table_name,
                _ref_col: str = ref_col,
                _child_table: str = child_table_name,
                _engine: Any = engine,
            ) -> None:
                parent = _engine._tables.get(_ref_table)
                if parent is None:
                    return
                ref_value = parent.document_store.get_field(doc_id, _ref_col)
                if ref_value is None:
                    return
                child = _engine._tables.get(_child_table)
                if child is None:
                    return
                if child.document_store.has_value(_fk_col, ref_value):
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"key ({_ref_col})=({ref_value}) in table "
                        f"'{_ref_table}' is still referenced from "
                        f"table '{_child_table}'"
                    )

            # Register on the parent table (if it exists now).
            # Also defer: if the parent is created later, the
            # validator is registered when the parent is available.
            parent_table = engine._tables.get(ref_table_name)
            if parent_table is not None:
                parent_table.fk_delete_validators.append(_validate_delete)
            # Store the validator for deferred registration as well.
            table._pending_parent_delete_validators = getattr(
                table, "_pending_parent_delete_validators", []
            )
            table._pending_parent_delete_validators.append(
                (ref_table_name, _validate_delete)
            )

            # -- UPDATE validator: combined insert + parent checks -----
            def _validate_update(
                old_doc: dict[str, Any],
                new_doc: dict[str, Any],
                _fk_col: str = fk_col,
                _ref_table: str = ref_table_name,
                _ref_col: str = ref_col,
                _child_table: str = child_table_name,
                _engine: Any = engine,
            ) -> None:
                new_value = new_doc.get(_fk_col)
                old_value = old_doc.get(_fk_col)
                # If FK column did not change, nothing to validate
                if new_value == old_value:
                    return
                if new_value is None:
                    return  # Setting FK to NULL is allowed
                parent = _engine._tables.get(_ref_table)
                if parent is None:
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"referenced table '{_ref_table}' does not exist"
                    )
                parent_values = {
                    parent.document_store.get_field(did, _ref_col)
                    for did in parent.document_store.doc_ids
                }
                if new_value not in parent_values:
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"key ({_fk_col})=({new_value}) in table "
                        f"'{_child_table}' is not present in "
                        f"table '{_ref_table}'"
                    )

            table.fk_update_validators.append(_validate_update)

            # -- UPDATE validator on parent: block PK change if
            #    children reference old value -------------------------
            def _validate_parent_update(
                old_doc: dict[str, Any],
                new_doc: dict[str, Any],
                _fk_col: str = fk_col,
                _ref_table: str = ref_table_name,
                _ref_col: str = ref_col,
                _child_table: str = child_table_name,
                _engine: Any = engine,
            ) -> None:
                old_value = old_doc.get(_ref_col)
                new_value = new_doc.get(_ref_col)
                if old_value == new_value:
                    return
                if old_value is None:
                    return
                child = _engine._tables.get(_child_table)
                if child is None:
                    return
                child_fk_values = {
                    child.document_store.get_field(cid, _fk_col)
                    for cid in child.document_store.doc_ids
                }
                if old_value in child_fk_values:
                    raise ValueError(
                        f"FOREIGN KEY constraint violated: "
                        f"key ({_ref_col})=({old_value}) in table "
                        f"'{_ref_table}' is still referenced from "
                        f"table '{_child_table}'"
                    )

            if parent_table is not None:
                parent_table.fk_update_validators.append(_validate_parent_update)
            table._pending_parent_update_validators = getattr(
                table, "_pending_parent_update_validators", []
            )
            table._pending_parent_update_validators.append(
                (ref_table_name, _validate_parent_update)
            )

        # Attempt deferred registration of parent validators
        # for all FK defs that reference tables created after
        # the child table.
        self._resolve_pending_fk_validators()

    def _resolve_pending_fk_validators(self) -> None:
        """Register any pending parent-side FK validators.

        When a child table is created before its parent, the delete
        and update validators for the parent cannot be installed
        immediately.  This method iterates all tables and installs
        any pending validators whose parent tables now exist.
        """
        engine = self._engine
        for table in engine._tables.values():
            pending_del = getattr(table, "_pending_parent_delete_validators", [])
            remaining_del: list[tuple[str, Any]] = []
            for ref_table_name, validator in pending_del:
                parent = engine._tables.get(ref_table_name)
                if parent is not None:
                    if validator not in parent.fk_delete_validators:
                        parent.fk_delete_validators.append(validator)
                else:
                    remaining_del.append((ref_table_name, validator))
            table._pending_parent_delete_validators = remaining_del

            pending_upd = getattr(table, "_pending_parent_update_validators", [])
            remaining_upd: list[tuple[str, Any]] = []
            for ref_table_name, validator in pending_upd:
                parent = engine._tables.get(ref_table_name)
                if parent is not None:
                    if validator not in parent.fk_update_validators:
                        parent.fk_update_validators.append(validator)
                else:
                    remaining_upd.append((ref_table_name, validator))
            table._pending_parent_update_validators = remaining_upd

    def _compile_drop(self, stmt: DropStmt) -> SQLResult:
        """Dispatch DROP TABLE / DROP INDEX / DROP VIEW / DROP SERVER / DROP FOREIGN TABLE."""
        # removeType 41 = OBJECT_TABLE, 20 = OBJECT_INDEX, 51 = OBJECT_VIEW
        # removeType 17 = OBJECT_FOREIGN_SERVER, 18 = OBJECT_FOREIGN_TABLE
        if stmt.removeType == 20:
            return self._compile_drop_index(stmt)
        if stmt.removeType == 51:
            return self._compile_drop_view(stmt)
        if stmt.removeType == 17:
            return self._compile_drop_foreign_server(stmt)
        if stmt.removeType == 18:
            return self._compile_drop_foreign_table(stmt)
        return self._compile_drop_table(stmt)

    def _compile_drop_table(self, stmt: DropStmt) -> SQLResult:
        for obj in stmt.objects:
            table_name = obj[-1].sval
            if table_name in self._engine._tables:
                index_manager = getattr(self._engine, "_index_manager", None)
                if index_manager is not None:
                    index_manager.drop_indexes_for_table(table_name)
                del self._engine._tables[table_name]
                self._engine._temp_tables.discard(table_name)
                if self._engine._catalog is not None:
                    self._engine._catalog.drop_table_schema(table_name)
            elif not stmt.missing_ok:
                raise ValueError(f"Table '{table_name}' does not exist")
        return SQLResult([], [])

    def _compile_drop_index(self, stmt: DropStmt) -> SQLResult:
        index_manager = getattr(self._engine, "_index_manager", None)
        if index_manager is None:
            raise ValueError("Index operations require a persistent engine (db_path)")
        for obj in stmt.objects:
            index_name = obj[-1].sval
            if stmt.missing_ok:
                index_manager.drop_index_if_exists(index_name)
            else:
                index_manager.drop_index(index_name)
        return SQLResult([], [])

    # ==================================================================
    # DDL: FOREIGN DATA WRAPPERS
    # ==================================================================

    def _compile_create_foreign_server(
        self,
        stmt: CreateForeignServerStmt,
    ) -> SQLResult:
        from uqa.fdw.foreign_table import ForeignServer

        name = stmt.servername
        if name in self._engine._foreign_servers:
            if stmt.if_not_exists:
                return SQLResult([], [])
            raise ValueError(f"Foreign server '{name}' already exists")

        fdw_type = stmt.fdwname
        if fdw_type not in ("duckdb_fdw", "arrow_fdw"):
            raise ValueError(f"Unsupported FDW type: '{fdw_type}'")

        options: dict[str, str] = {}
        if stmt.options:
            for opt in stmt.options:
                options[opt.defname] = opt.arg.sval

        server = ForeignServer(name=name, fdw_type=fdw_type, options=options)
        self._engine._foreign_servers[name] = server

        if self._engine._catalog is not None:
            self._engine._catalog.save_foreign_server(
                name,
                fdw_type,
                options,
            )

        return SQLResult([], [])

    def _compile_create_foreign_table(
        self,
        stmt: CreateForeignTableStmt,
    ) -> SQLResult:
        from uqa.fdw.foreign_table import ForeignTable

        table_name = stmt.base.relation.relname
        if table_name in self._engine._foreign_tables:
            if stmt.base.if_not_exists:
                return SQLResult([], [])
            raise ValueError(f"Foreign table '{table_name}' already exists")
        if table_name in self._engine._tables:
            raise ValueError(f"Table '{table_name}' already exists")

        server_name = stmt.servername
        if server_name not in self._engine._foreign_servers:
            raise ValueError(f"Foreign server '{server_name}' does not exist")

        columns = OrderedDict()
        for elt in stmt.base.tableElts:
            col, _check, _fk = self._parse_column_def(elt)
            columns[col.name] = col

        options: dict[str, str] = {}
        if stmt.options:
            for opt in stmt.options:
                options[opt.defname] = opt.arg.sval

        ft = ForeignTable(
            name=table_name,
            server_name=server_name,
            columns=columns,
            options=options,
        )
        self._engine._foreign_tables[table_name] = ft

        if self._engine._catalog is not None:
            self._engine._catalog.save_foreign_table(
                table_name,
                server_name,
                [
                    {
                        "name": col.name,
                        "type_name": col.type_name,
                        "primary_key": col.primary_key,
                        "not_null": col.not_null,
                    }
                    for col in columns.values()
                ],
                options,
            )

        return SQLResult([], [])

    def _compile_drop_foreign_server(self, stmt: DropStmt) -> SQLResult:
        # DROP SERVER objects is a flat tuple of PgString
        for obj in stmt.objects:
            name = obj.sval
            if name in self._engine._foreign_servers:
                # Validate no foreign tables reference this server
                for ft in self._engine._foreign_tables.values():
                    if ft.server_name == name:
                        raise ValueError(
                            f"Cannot drop server '{name}': "
                            f"foreign table '{ft.name}' depends on it"
                        )
                # Close cached handler if present
                handler = self._engine._fdw_handlers.pop(name, None)
                if handler is not None:
                    handler.close()
                del self._engine._foreign_servers[name]
                if self._engine._catalog is not None:
                    self._engine._catalog.drop_foreign_server(name)
            elif not stmt.missing_ok:
                raise ValueError(f"Foreign server '{name}' does not exist")
        return SQLResult([], [])

    def _compile_drop_foreign_table(self, stmt: DropStmt) -> SQLResult:
        # DROP FOREIGN TABLE objects is a tuple of tuples of PgString
        for obj in stmt.objects:
            table_name = obj[-1].sval
            if table_name in self._engine._foreign_tables:
                del self._engine._foreign_tables[table_name]
                if self._engine._catalog is not None:
                    self._engine._catalog.drop_foreign_table(table_name)
            elif not stmt.missing_ok:
                raise ValueError(f"Foreign table '{table_name}' does not exist")
        return SQLResult([], [])

    # ==================================================================
    # DDL: ALTER TABLE / RENAME / TRUNCATE
    # ==================================================================

    def _compile_alter_table(self, stmt: AlterTableStmt) -> SQLResult:
        table_name = stmt.relation.relname
        table = self._get_table(table_name)

        for cmd in stmt.cmds:
            at = AlterTableType(cmd.subtype)

            if at == AlterTableType.AT_AddColumn:
                col_def, check_expr, fk_def = self._parse_column_def(cmd.def_)
                if col_def.name in table.columns:
                    raise ValueError(
                        f"Column '{col_def.name}' already exists "
                        f"in table '{table_name}'"
                    )
                table.columns[col_def.name] = col_def
                if check_expr is not None:
                    from uqa.sql.expr_evaluator import ExprEvaluator

                    ev = ExprEvaluator()
                    table.check_constraints.append(
                        (
                            col_def.name,
                            lambda row, e=check_expr, v=ev: v.evaluate(e, row),
                        )
                    )
                if fk_def is not None:
                    table.foreign_keys.append(fk_def)
                    self._register_fk_validators(table, [fk_def])

            elif at == AlterTableType.AT_DropColumn:
                col_name = cmd.name
                if col_name not in table.columns:
                    if cmd.missing_ok:
                        continue
                    raise ValueError(
                        f"Column '{col_name}' does not exist in table '{table_name}'"
                    )
                del table.columns[col_name]
                if table.primary_key == col_name:
                    table.primary_key = None
                # Remove field from all documents
                for doc_id in list(table.document_store.doc_ids):
                    doc = table.document_store.get(doc_id)
                    if doc and col_name in doc:
                        del doc[col_name]
                        table.document_store.put(doc_id, doc)

            elif at == AlterTableType.AT_ColumnDefault:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist in table '{table_name}'"
                    )
                if cmd.def_ is not None:
                    table.columns[col_name].default = self._extract_const_value(
                        cmd.def_
                    )
                else:
                    table.columns[col_name].default = None

            elif at == AlterTableType.AT_SetNotNull:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist in table '{table_name}'"
                    )
                # Validate existing data
                for doc_id in table.document_store.doc_ids:
                    val = table.document_store.get_field(doc_id, col_name)
                    if val is None:
                        raise ValueError(
                            f"Column '{col_name}' contains NULL values; "
                            f"cannot set NOT NULL"
                        )
                table.columns[col_name].not_null = True

            elif at == AlterTableType.AT_DropNotNull:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist in table '{table_name}'"
                    )
                table.columns[col_name].not_null = False

            elif at == AlterTableType.AT_AlterColumnType:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist in table '{table_name}'"
                    )
                new_type_names = cmd.def_.typeName.names
                new_type, new_python_type = resolve_type(
                    new_type_names, cmd.def_.typeName.arrayBounds
                )
                col_def = table.columns[col_name]
                col_def.type_name = new_type
                col_def.python_type = new_python_type
                # Coerce existing data to the new type
                for doc_id in list(table.document_store.doc_ids):
                    val = table.document_store.get_field(doc_id, col_name)
                    if val is not None:
                        try:
                            coerced = new_python_type(val)
                        except (ValueError, TypeError):
                            coerced = val
                        doc = table.document_store.get(doc_id)
                        if doc is not None:
                            doc[col_name] = coerced
                            table.document_store.put(doc_id, doc)

            else:
                raise ValueError(f"Unsupported ALTER TABLE subcommand: {at.name}")

        return SQLResult([], [])

    def _compile_rename(self, stmt: RenameStmt) -> SQLResult:
        rt = ObjectType(stmt.renameType)

        if rt == ObjectType.OBJECT_TABLE:
            old_name = stmt.relation.relname
            new_name = stmt.newname
            table = self._get_table(old_name)
            if new_name in self._engine._tables:
                raise ValueError(f"Table '{new_name}' already exists")
            del self._engine._tables[old_name]
            table.name = new_name
            self._engine._tables[new_name] = table
            return SQLResult([], [])

        if rt == ObjectType.OBJECT_COLUMN:
            table_name = stmt.relation.relname
            table = self._get_table(table_name)
            old_col = stmt.subname
            new_col = stmt.newname
            if old_col not in table.columns:
                raise ValueError(
                    f"Column '{old_col}' does not exist in table '{table_name}'"
                )
            if new_col in table.columns:
                raise ValueError(
                    f"Column '{new_col}' already exists in table '{table_name}'"
                )
            # Rebuild OrderedDict preserving order
            new_columns: OrderedDict[str, ColumnDef] = OrderedDict()
            for name, col_def in table.columns.items():
                if name == old_col:
                    col_def.name = new_col
                    new_columns[new_col] = col_def
                else:
                    new_columns[name] = col_def
            table.columns = new_columns
            if table.primary_key == old_col:
                table.primary_key = new_col
            # Rename field in all documents
            for doc_id in list(table.document_store.doc_ids):
                doc = table.document_store.get(doc_id)
                if doc and old_col in doc:
                    doc[new_col] = doc.pop(old_col)
                    table.document_store.put(doc_id, doc)
            return SQLResult([], [])

        raise ValueError(f"Unsupported RENAME type: {rt.name}")

    def _compile_truncate(self, stmt: TruncateStmt) -> SQLResult:
        for rel in stmt.relations:
            table_name = rel.relname
            table = self._get_table(table_name)
            table.document_store.clear()
            table.inverted_index.clear()
            for vi in table.vector_indexes.values():
                vi.clear()
            for si in table.spatial_indexes.values():
                si.clear()
            table.graph_store.clear()
            table._next_id = 1
            for uidx in table._unique_indexes.values():
                uidx.clear()
        return SQLResult([], [])

    # ==================================================================
    # DDL: CREATE VIEW / DROP VIEW
    # ==================================================================

    def _compile_create_view(self, stmt: ViewStmt) -> SQLResult:
        view_name = stmt.view.relname
        if view_name in self._engine._views:
            raise ValueError(f"View '{view_name}' already exists")
        if view_name in self._engine._tables:
            raise ValueError(f"'{view_name}' already exists as a table")
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
                    f"Column '{col_name}' does not exist in table '{table_name}'"
                )
            columns.append(col_name)

        access_method = (stmt.accessMethod or "btree").lower()

        if access_method in ("hnsw", "ivf"):
            # IVF vector index: CREATE INDEX ... USING hnsw|ivf
            # "hnsw" is accepted for backward compatibility and maps to IVF.
            if len(columns) != 1:
                raise ValueError("Vector index must be created on exactly one column")
            col_name = columns[0]
            col_def = table.columns[col_name]
            if col_def.vector_dimensions is None:
                raise ValueError(f"Column '{col_name}' is not a VECTOR column")

            # Parse WITH parameters: nlist, nprobe
            # (ef_construction, m are silently ignored for backward compat)
            params: dict[str, int] = {}
            if stmt.options:
                from pglast.ast import DefElem

                for opt in stmt.options:
                    if isinstance(opt, DefElem):
                        key = opt.defname.lower()
                        if key in ("nlist", "nprobe"):
                            val = opt.arg
                            if hasattr(val, "ival"):
                                params[key] = val.ival
                            elif hasattr(val, "sval"):
                                params[key] = int(val.sval)

            from uqa.storage.ivf_index import IVFIndex

            catalog_conn = getattr(
                getattr(self._engine, "_catalog", None), "conn", None
            )
            if catalog_conn is None:
                raise ValueError(
                    "IVF vector index requires a persistent engine (db_path)"
                )

            ivf_kwargs: dict[str, Any] = {
                "conn": catalog_conn,
                "table_name": table_name,
                "field_name": col_name,
                "dimensions": col_def.vector_dimensions,
            }
            if "nlist" in params:
                ivf_kwargs["nlist"] = params["nlist"]
            if "nprobe" in params:
                ivf_kwargs["nprobe"] = params["nprobe"]

            ivf = IVFIndex(**ivf_kwargs)

            # Re-index existing vectors from the document store
            for doc_id in table.document_store.doc_ids:
                doc = table.document_store.get(doc_id)
                if doc is not None and col_name in doc:
                    import numpy as np

                    vec = np.asarray(doc[col_name], dtype=np.float32)
                    ivf.add(doc_id, vec)

            table.vector_indexes[col_name] = ivf

            # Persist index definition if catalog is available
            index_manager = getattr(self._engine, "_index_manager", None)
            if index_manager is not None:
                index_def = IndexDef(
                    name=index_name,
                    index_type=IndexType.IVF,
                    table_name=table_name,
                    columns=tuple(columns),
                    parameters=params,
                )
                self._engine._catalog.save_index(index_def)

            return SQLResult([], [])

        if access_method == "rtree":
            # R*Tree spatial index: CREATE INDEX ... USING rtree
            if len(columns) != 1:
                raise ValueError("R*Tree index must be created on exactly one column")
            col_name = columns[0]
            col_def = table.columns[col_name]
            if col_def.type_name != "point":
                raise ValueError(f"Column '{col_name}' is not a POINT column")

            from uqa.storage.spatial_index import SpatialIndex

            catalog_conn = getattr(
                getattr(self._engine, "_catalog", None), "conn", None
            )
            sp_idx = SpatialIndex(table_name, col_name, conn=catalog_conn)

            # Re-index existing points from the document store
            for doc_id in table.document_store.doc_ids:
                doc = table.document_store.get(doc_id)
                if doc is not None and col_name in doc:
                    pt = doc[col_name]
                    if isinstance(pt, list | tuple) and len(pt) == 2:
                        sp_idx.add(doc_id, float(pt[0]), float(pt[1]))

            table.spatial_indexes[col_name] = sp_idx

            # Persist index definition if catalog is available
            index_manager = getattr(self._engine, "_index_manager", None)
            if index_manager is not None:
                index_def = IndexDef(
                    name=index_name,
                    index_type=IndexType.RTREE,
                    table_name=table_name,
                    columns=tuple(columns),
                )
                self._engine._catalog.save_index(index_def)

            return SQLResult([], [])

        # BTREE index (default)
        index_manager = getattr(self._engine, "_index_manager", None)
        if index_manager is None:
            raise ValueError("Index operations require a persistent engine (db_path)")

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
        if table_name in self._engine._foreign_tables:
            raise ValueError(f"Cannot INSERT into foreign table '{table_name}'")
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Column names
        if stmt.cols:
            col_names = [c.name for c in stmt.cols]
        else:
            col_names = table.column_names

        # VALUES or SELECT source
        values_stmt = stmt.selectStmt
        if values_stmt is None:
            raise ValueError("INSERT requires VALUES or SELECT clause")

        # Collect source rows
        source_rows: list[dict[str, Any]] = []

        if values_stmt.valuesLists is None:
            # INSERT INTO ... SELECT ...
            result = self._compile_select(values_stmt)
            for row in result.rows:
                mapped_row: dict[str, Any] = {}
                for i, col in enumerate(col_names):
                    if i < len(result.columns):
                        mapped_row[col] = row.get(result.columns[i])
                source_rows.append(mapped_row)
        else:
            # INSERT INTO ... VALUES ...
            for row_values in values_stmt.valuesLists:
                if len(row_values) != len(col_names):
                    raise ValueError(
                        f"VALUES has {len(row_values)} columns "
                        f"but {len(col_names)} were specified"
                    )
                row: dict[str, Any] = {}
                for i, val_node in enumerate(row_values):
                    row[col_names[i]] = self._extract_insert_value(val_node)
                source_rows.append(row)

        # ON CONFLICT handling
        on_conflict = stmt.onConflictClause
        conflict_cols: list[str] = []
        if on_conflict is not None and on_conflict.infer is not None:
            conflict_cols = [elem.name for elem in on_conflict.infer.indexElems]

        # Build hash index for O(1) conflict lookups
        conflict_index: dict[tuple, int] = {}
        if on_conflict is not None and conflict_cols:
            for doc_id in table.document_store.doc_ids:
                doc = table.document_store.get(doc_id)
                if doc is not None:
                    key = tuple(doc.get(c) for c in conflict_cols)
                    conflict_index[key] = doc_id

        # Insert rows with ON CONFLICT and RETURNING support
        returning_rows: list[dict[str, Any]] = []
        inserted = 0
        for src_row in source_rows:
            if on_conflict is not None and conflict_cols:
                key = tuple(src_row.get(c) for c in conflict_cols)
                existing_id = conflict_index.get(key)
                if existing_id is not None:
                    action = OnConflictAction(on_conflict.action)
                    if action == OnConflictAction.ONCONFLICT_NOTHING:
                        continue
                    # DO UPDATE SET ...
                    self._do_conflict_update(
                        table,
                        existing_id,
                        src_row,
                        on_conflict.targetList,
                    )
                    # Update index if conflict columns changed
                    updated_doc = table.document_store.get(existing_id)
                    if updated_doc is not None:
                        new_key = tuple(updated_doc.get(c) for c in conflict_cols)
                        if new_key != key:
                            conflict_index.pop(key, None)
                            conflict_index[new_key] = existing_id
                    if stmt.returningList:
                        doc = updated_doc
                        if doc:
                            returning_rows.append(
                                self._project_returning(doc, stmt.returningList, table)
                            )
                    inserted += 1
                    continue

            doc_id, _ = table.insert(src_row)
            inserted += 1
            # Update conflict index for subsequent rows in the batch
            if on_conflict is not None and conflict_cols:
                new_key = tuple(src_row.get(c) for c in conflict_cols)
                conflict_index[new_key] = doc_id
            if stmt.returningList:
                doc = table.document_store.get(doc_id)
                if doc:
                    returning_rows.append(
                        self._project_returning(doc, stmt.returningList, table)
                    )

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)

        return SQLResult(["inserted"], [{"inserted": inserted}])

    def _find_conflict(
        self,
        table: Table,
        conflict_cols: list[str],
        row: dict[str, Any],
    ) -> int | None:
        """Find an existing doc_id that conflicts on the given columns."""
        for doc_id in table.document_store.doc_ids:
            doc = table.document_store.get(doc_id)
            if doc is None:
                continue
            if all(doc.get(c) == row.get(c) for c in conflict_cols):
                return doc_id
        return None

    def _do_conflict_update(
        self,
        table: Table,
        doc_id: int,
        excluded_row: dict[str, Any],
        target_list: tuple,
    ) -> None:
        """Execute DO UPDATE SET assignments for an ON CONFLICT clause."""
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator(
            subquery_executor=self._compile_select,
            outer_row=getattr(self, "_correlated_outer_row", None),
        )

        old_doc = table.document_store.get(doc_id)
        if old_doc is None:
            return
        new_doc = dict(old_doc)

        # Merge excluded.* into the row for expression evaluation
        eval_row = dict(old_doc)
        for k, v in excluded_row.items():
            eval_row[f"excluded.{k}"] = v

        for target in target_list:
            col_name = target.name
            new_value = evaluator.evaluate(target.val, eval_row)
            col_def = table.columns.get(col_name)
            if new_value is not None and col_def is not None:
                new_doc[col_name] = col_def.python_type(new_value)
            elif new_value is None:
                new_doc.pop(col_name, None)

        table.inverted_index.remove_document(doc_id)
        table.remove_from_unique_indexes(doc_id)
        table.document_store.put(doc_id, new_doc)
        for col_name_u, uidx in table._unique_indexes.items():
            val_u = new_doc.get(col_name_u)
            if val_u is not None:
                uidx[val_u] = doc_id
        text_fields = {k: v for k, v in new_doc.items() if isinstance(v, str)}
        if text_fields:
            table.inverted_index.add_document(doc_id, text_fields)

    def _project_returning(
        self,
        doc: dict[str, Any],
        returning_list: tuple,
        table: Table,
    ) -> dict[str, Any]:
        """Project a document through a RETURNING clause."""
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator(
            subquery_executor=self._compile_select,
            outer_row=getattr(self, "_correlated_outer_row", None),
        )
        result: dict[str, Any] = {}
        for target in returning_list:
            if isinstance(target.val, ColumnRef):
                if isinstance(target.val.fields[0], A_Star):
                    # RETURNING * -- include all table columns
                    for col_name in table.columns:
                        result[col_name] = doc.get(col_name)
                    continue
                col_name = self._extract_column_name(target.val)
                alias = target.name or col_name
                result[alias] = doc.get(col_name)
            else:
                alias = target.name or "?column?"
                result[alias] = evaluator.evaluate(target.val, doc)
        return result

    def _returning_columns(self, returning_list: tuple, table: Table) -> list[str]:
        """Extract column names from a RETURNING clause."""
        cols: list[str] = []
        for target in returning_list:
            if isinstance(target.val, ColumnRef):
                if isinstance(target.val.fields[0], A_Star):
                    cols.extend(table.column_names)
                    continue
                col_name = self._extract_column_name(target.val)
                cols.append(target.name or col_name)
            else:
                cols.append(target.name or "?column?")
        return cols

    # ==================================================================
    # DML: UPDATE
    # ==================================================================

    def _compile_update(self, stmt: UpdateStmt) -> SQLResult:
        table_name = stmt.relation.relname
        if table_name in self._engine._foreign_tables:
            raise ValueError(f"Cannot UPDATE foreign table '{table_name}'")
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Multi-table UPDATE: UPDATE t1 SET ... FROM t2 WHERE ...
        if stmt.fromClause is not None:
            return self._compile_update_from(stmt, table)

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
            if stmt.returningList:
                cols = self._returning_columns(stmt.returningList, table)
                return SQLResult(cols, [])
            return SQLResult(["updated"], [{"updated": 0}])

        # Parse SET clause into (column_name, ast_node) pairs
        set_targets: list[tuple[str, Any]] = []
        for target in stmt.targetList:
            col_name = target.name
            if col_name not in table.columns:
                raise ValueError(
                    f"Unknown column '{col_name}' for table '{table_name}'"
                )
            set_targets.append((col_name, target.val))

        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator(
            subquery_executor=self._compile_select,
            outer_row=getattr(self, "_correlated_outer_row", None),
        )

        returning_rows: list[dict[str, Any]] = []
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

            # Validate FOREIGN KEY constraints for the update
            for fk_validator in table.fk_update_validators:
                fk_validator(old_doc, new_doc)

            # Remove old inverted index entries
            table.inverted_index.remove_document(doc_id)

            # Update unique indexes: remove old, add new
            table.remove_from_unique_indexes(doc_id)

            # Write updated document
            table.document_store.put(doc_id, new_doc)

            # Update unique indexes with new values
            for col_name, uidx in table._unique_indexes.items():
                val = new_doc.get(col_name)
                if val is not None:
                    uidx[val] = doc_id

            # Re-index text fields
            text_fields = {k: v for k, v in new_doc.items() if isinstance(v, str)}
            if text_fields:
                table.inverted_index.add_document(doc_id, text_fields)

            # Update spatial indexes for changed POINT columns
            for col_name, sp_idx in table.spatial_indexes.items():
                pt = new_doc.get(col_name)
                if pt is not None and isinstance(pt, list | tuple) and len(pt) == 2:
                    sp_idx.add(doc_id, float(pt[0]), float(pt[1]))
                else:
                    sp_idx.delete(doc_id)

            if stmt.returningList:
                returning_rows.append(
                    self._project_returning(new_doc, stmt.returningList, table)
                )
            updated += 1

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
        return SQLResult(["updated"], [{"updated": updated}])

    def _compile_update_from(self, stmt: UpdateStmt, table: Table) -> SQLResult:
        """UPDATE t1 SET col = expr FROM t2 [, t3, ...] WHERE condition."""
        import itertools

        from uqa.sql.expr_evaluator import ExprEvaluator

        table_name = stmt.relation.relname
        table_alias = (
            stmt.relation.alias.aliasname
            if stmt.relation.alias is not None
            else table_name
        )

        # Resolve FROM tables
        from_tables: list[tuple[Table, str]] = []
        for from_node in stmt.fromClause:
            ft, _op, fa = self._resolve_from_single(from_node)
            if ft is None:
                raise ValueError("UPDATE FROM requires table references")
            from_tables.append((ft, fa or ft.name))

        evaluator = ExprEvaluator(
            subquery_executor=self._compile_select,
            outer_row=getattr(self, "_correlated_outer_row", None),
        )

        # Parse SET clause
        set_targets: list[tuple[str, Any]] = []
        for target in stmt.targetList:
            col_name = target.name
            if col_name not in table.columns:
                raise ValueError(
                    f"Unknown column '{col_name}' for table '{table_name}'"
                )
            set_targets.append((col_name, target.val))

        returning_rows: list[dict[str, Any]] = []
        updated = 0

        # Nested-loop join: for each target row, check against FROM rows
        for doc_id in list(table.document_store.doc_ids):
            target_doc = table.document_store.get(doc_id)
            if target_doc is None:
                continue

            # Build qualified row for the target table
            target_row = dict(target_doc)
            for k, v in list(target_doc.items()):
                target_row[f"{table_alias}.{k}"] = v

            # Try all combinations of FROM rows
            from_row_lists: list[list[dict[str, Any]]] = []
            for ft, fa in from_tables:
                ft_rows: list[dict[str, Any]] = []
                for fid in ft.document_store.doc_ids:
                    fdoc = ft.document_store.get(fid)
                    if fdoc is not None:
                        qualified: dict[str, Any] = dict(fdoc)
                        for k, v in list(fdoc.items()):
                            qualified[f"{fa}.{k}"] = v
                        ft_rows.append(qualified)
                from_row_lists.append(ft_rows)

            # Cartesian product of FROM rows (usually just 1 FROM table)
            from_combos = (
                list(itertools.product(*from_row_lists)) if from_row_lists else [()]
            )

            for combo in from_combos:
                merged = dict(target_row)
                for from_row in combo:
                    merged.update(from_row)

                if stmt.whereClause is not None and not evaluator.evaluate(
                    stmt.whereClause, merged
                ):
                    continue

                # Apply SET expressions
                new_doc = dict(target_doc)
                for col_name, val_node in set_targets:
                    new_value = evaluator.evaluate(val_node, merged)
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

                table.inverted_index.remove_document(doc_id)
                table.remove_from_unique_indexes(doc_id)
                table.document_store.put(doc_id, new_doc)
                for col_name_u, uidx in table._unique_indexes.items():
                    val_u = new_doc.get(col_name_u)
                    if val_u is not None:
                        uidx[val_u] = doc_id
                text_fields = {k: v for k, v in new_doc.items() if isinstance(v, str)}
                if text_fields:
                    table.inverted_index.add_document(doc_id, text_fields)

                if stmt.returningList:
                    returning_rows.append(
                        self._project_returning(new_doc, stmt.returningList, table)
                    )
                updated += 1
                break  # Only update once per target row

        # Clean up expanded FROM tables
        for name in list(self._expanded_views):
            if name in self._shadowed_tables:
                self._engine._tables[name] = self._shadowed_tables.pop(name)
            else:
                self._engine._tables.pop(name, None)
        self._expanded_views.clear()

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
        return SQLResult(["updated"], [{"updated": updated}])

    # ==================================================================
    # DML: DELETE
    # ==================================================================

    def _compile_delete(self, stmt: DeleteStmt) -> SQLResult:
        table_name = stmt.relation.relname
        if table_name in self._engine._foreign_tables:
            raise ValueError(f"Cannot DELETE from foreign table '{table_name}'")
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Multi-table DELETE: DELETE FROM t1 USING t2 WHERE ...
        if stmt.usingClause is not None:
            return self._compile_delete_using(stmt, table)

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
            if stmt.returningList:
                cols = self._returning_columns(stmt.returningList, table)
                return SQLResult(cols, [])
            return SQLResult(["deleted"], [{"deleted": 0}])

        # Validate FOREIGN KEY constraints before deletion
        for doc_id in matching_ids:
            for fk_validator in table.fk_delete_validators:
                fk_validator(doc_id)

        returning_rows: list[dict[str, Any]] = []
        deleted = 0
        for doc_id in matching_ids:
            # Fetch row BEFORE deletion for RETURNING
            if stmt.returningList:
                doc = table.document_store.get(doc_id)
                if doc:
                    returning_rows.append(
                        self._project_returning(doc, stmt.returningList, table)
                    )
            table.inverted_index.remove_document(doc_id)
            for si in table.spatial_indexes.values():
                si.delete(doc_id)
            table.remove_from_unique_indexes(doc_id)
            table.document_store.delete(doc_id)
            deleted += 1

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
        return SQLResult(["deleted"], [{"deleted": deleted}])

    def _compile_delete_using(self, stmt: DeleteStmt, table: Table) -> SQLResult:
        """DELETE FROM t1 USING t2 [, t3, ...] WHERE condition."""
        import itertools

        from uqa.sql.expr_evaluator import ExprEvaluator

        table_name = stmt.relation.relname
        table_alias = (
            stmt.relation.alias.aliasname
            if stmt.relation.alias is not None
            else table_name
        )

        # Resolve USING tables
        using_tables: list[tuple[Table, str]] = []
        for using_node in stmt.usingClause:
            ut, _op, ua = self._resolve_from_single(using_node)
            if ut is None:
                raise ValueError("DELETE USING requires table references")
            using_tables.append((ut, ua or ut.name))

        evaluator = ExprEvaluator(
            subquery_executor=self._compile_select,
            outer_row=getattr(self, "_correlated_outer_row", None),
        )

        returning_rows: list[dict[str, Any]] = []
        to_delete: list[int] = []

        for doc_id in list(table.document_store.doc_ids):
            target_doc = table.document_store.get(doc_id)
            if target_doc is None:
                continue

            target_row = dict(target_doc)
            for k, v in list(target_doc.items()):
                target_row[f"{table_alias}.{k}"] = v

            using_row_lists: list[list[dict[str, Any]]] = []
            for ut, ua in using_tables:
                ut_rows: list[dict[str, Any]] = []
                for uid in ut.document_store.doc_ids:
                    udoc = ut.document_store.get(uid)
                    if udoc is not None:
                        qualified: dict[str, Any] = dict(udoc)
                        for k, v in list(udoc.items()):
                            qualified[f"{ua}.{k}"] = v
                        ut_rows.append(qualified)
                using_row_lists.append(ut_rows)

            using_combos = (
                list(itertools.product(*using_row_lists)) if using_row_lists else [()]
            )

            for combo in using_combos:
                merged = dict(target_row)
                for using_row in combo:
                    merged.update(using_row)

                if stmt.whereClause is not None and not evaluator.evaluate(
                    stmt.whereClause, merged
                ):
                    continue

                if stmt.returningList:
                    returning_rows.append(
                        self._project_returning(target_doc, stmt.returningList, table)
                    )
                to_delete.append(doc_id)
                break  # Only delete once per row

        deleted = 0
        for doc_id in to_delete:
            table.inverted_index.remove_document(doc_id)
            for si in table.spatial_indexes.values():
                si.delete(doc_id)
            table.remove_from_unique_indexes(doc_id)
            table.document_store.delete(doc_id)
            deleted += 1

        # Clean up expanded USING tables
        for name in list(self._expanded_views):
            if name in self._shadowed_tables:
                self._engine._tables[name] = self._shadowed_tables.pop(name)
            else:
                self._engine._tables.pop(name, None)
        self._expanded_views.clear()

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
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
                raise ValueError("SAVEPOINT requires an active transaction")
            txn.savepoint(stmt.savepoint_name)
            return SQLResult([], [])
        if kind == 5:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError("RELEASE SAVEPOINT requires an active transaction")
            txn.release_savepoint(stmt.savepoint_name)
            return SQLResult([], [])
        if kind == 6:
            txn = self._engine._transaction
            if txn is None or not txn.active:
                raise ValueError("ROLLBACK TO SAVEPOINT requires an active transaction")
            txn.rollback_to(stmt.savepoint_name)
            return SQLResult([], [])
        raise ValueError(f"Unsupported transaction statement kind: {kind}")

    # ==================================================================
    # Prepared Statements: PREPARE / EXECUTE / DEALLOCATE
    # ==================================================================

    def _compile_prepare(self, stmt: PrepareStmt) -> SQLResult:
        name = stmt.name
        if name in self._engine._prepared:
            raise ValueError(f"Prepared statement '{name}' already exists")
        self._engine._prepared[name] = stmt
        return SQLResult([], [])

    def _compile_execute(self, stmt: ExecuteStmt) -> SQLResult:
        name = stmt.name
        prep = self._engine._prepared.get(name)
        if prep is None:
            raise ValueError(f"Prepared statement '{name}' does not exist")

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
        raise ValueError(f"Unsupported prepared query type: {type(query).__name__}")

    def _compile_deallocate(self, stmt: DeallocateStmt) -> SQLResult:
        if stmt.name is None:
            # DEALLOCATE ALL
            self._engine._prepared.clear()
        else:
            if stmt.name not in self._engine._prepared:
                raise ValueError(f"Prepared statement '{stmt.name}' does not exist")
            del self._engine._prepared[stmt.name]
        return SQLResult([], [])

    def _substitute_params(self, node: Any, params: dict[int, A_Const]) -> Any:
        """Recursively replace ParamRef nodes with A_Const values."""
        if isinstance(node, ParamRef):
            if node.number not in params:
                raise ValueError(f"No value supplied for parameter ${node.number}")
            return params[node.number]

        # Recurse into plain tuples/lists (e.g. valuesLists rows)
        if isinstance(node, tuple):
            return tuple(self._substitute_params(item, params) for item in node)
        if isinstance(node, list):
            return [self._substitute_params(item, params) for item in node]

        # pglast AST nodes use __slots__; clone with substituted children
        if hasattr(node, "__slots__") and isinstance(node.__slots__, dict):
            kwargs = {}
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is None:
                    kwargs[slot] = None
                elif isinstance(val, tuple | list):
                    kwargs[slot] = type(val)(
                        self._substitute_params(item, params) for item in val
                    )
                elif hasattr(val, "__slots__"):
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
                        table.name,
                        col_name,
                        cs.distinct_count,
                        cs.null_count,
                        cs.min_value,
                        cs.max_value,
                        cs.row_count,
                        cs.histogram,
                        cs.mcv_values,
                        cs.mcv_frequencies,
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

        if ctx.inverted_index is None:
            return op
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
        from uqa.planner.cost_model import CostModel
        from uqa.planner.executor import PlanExecutor

        executor = PlanExecutor(ctx)
        plan_text = executor.explain(op)

        lines = plan_text.split("\n")
        rows = [{"plan": line} for line in lines]

        if ctx.inverted_index is not None:
            stats = ctx.inverted_index.stats
            cost_model = CostModel()
            estimated_cost = cost_model.estimate(op, stats)
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
        deferred_where: Any = None,
        join_source: bool = False,
    ) -> SQLResult:
        """Execute relational operations via physical operators.

        Builds a Volcano-model operator tree for GROUP BY, PROJECT,
        DISTINCT, ORDER BY, and LIMIT, then executes it to produce
        the final result.

        When *join_source* is True, qualified column references (e.g.
        ``e.name``) are available in the row data, and projection is
        routed through ExprProjectOp for correct qualified lookup.
        """
        from uqa.execution.batch import _SQL_TO_DTYPE, DataType
        from uqa.execution.relational import (
            DistinctOp,
            ExprProjectOp,
            HashAggOp,
            LimitOp,
            ProjectOp,
            SortOp,
            WindowOp,
        )
        from uqa.execution.scan import PostingListScanOp

        # Build table schema for typed ColumnVectors
        schema: dict[str, DataType] = {}
        if table is not None:
            for name, col in table.columns.items():
                schema[name] = _SQL_TO_DTYPE.get(col.type_name, DataType.TEXT)

        physical: Any = PostingListScanOp(
            pl,
            ctx.document_store,
            schema,
            graph_store=ctx.graph_store,
        )

        # Apply deferred WHERE filters (for graph-sourced queries)
        if deferred_where is not None:
            physical = self._apply_deferred_where(physical, deferred_where)

        is_grouped = stmt.groupClause is not None
        is_agg_only = not is_grouped and self._has_aggregates(stmt.targetList)
        has_window = self._has_window_functions(stmt.targetList)
        expected_cols: list[str] | None = None
        defer_proj = False

        if has_window:
            # Window functions: compute window values, then project
            win_specs = self._extract_window_specs(stmt.targetList, stmt.windowClause)
            physical = WindowOp(
                physical,
                win_specs,
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
                    expected_cols.append(target.name or self._extract_column_name(val))
                else:
                    expected_cols.append(target.name or self._infer_target_name(target))

            # Project to expected columns
            physical = ProjectOp(physical, expected_cols)

        elif is_grouped:
            group_cols = self._resolve_group_by_cols(stmt.groupClause, stmt.targetList)
            agg_specs = self._extract_agg_specs(stmt.targetList)

            # Ensure aggregates referenced in HAVING are also computed
            # (e.g., HAVING COUNT(*) > 1 when COUNT is not in SELECT).
            if stmt.havingClause is not None:
                self._ensure_having_aggs(stmt.havingClause, agg_specs)

            # When GROUP BY has computed expressions or aggregates
            # have expression args, pre-compute them via ExprProjectOp
            # so HashAggOp can group/aggregate by named columns.
            pre_targets = self._build_pre_agg_targets(
                stmt.groupClause, group_cols, agg_specs, table
            )
            if pre_targets:
                physical = ExprProjectOp(
                    physical,
                    pre_targets,
                    subquery_executor=self._compile_select,
                )

            group_aliases = self._build_group_aliases(group_cols, stmt.targetList)
            physical = HashAggOp(
                physical,
                group_cols,
                agg_specs,
                spill_threshold=self._engine.spill_threshold,
                group_aliases=group_aliases,
            )

            if stmt.havingClause is not None:
                from uqa.execution.relational import ExprFilterOp

                physical = ExprFilterOp(
                    physical,
                    stmt.havingClause,
                    subquery_executor=self._compile_select,
                )

            # Non-aggregate computed expressions in SELECT (e.g.,
            # POSITION('o' IN rep) with GROUP BY rep) need evaluation
            # after HashAggOp.  Build ExprProjectOp targets for the
            # full SELECT list when such expressions are present.
            post_group_targets = self._build_post_group_targets(
                stmt.targetList, group_cols, agg_specs
            )
            if post_group_targets:
                physical = ExprProjectOp(
                    physical,
                    post_group_targets,
                    subquery_executor=self._compile_select,
                )
                expected_cols = [name for name, _ in post_group_targets]
            else:
                # expected_cols: use SELECT aliases for group cols
                expected_cols = self._resolve_select_column_names(
                    stmt.targetList, group_cols, agg_specs
                )

        elif is_agg_only:
            agg_specs = self._extract_agg_specs(stmt.targetList)
            physical = HashAggOp(
                physical,
                [],
                agg_specs,
                spill_threshold=self._engine.spill_threshold,
            )
            # Check if SELECT list has wrapper expressions around aggregates
            # (e.g., ROUND(STDDEV(salary), 2)). If so, add ExprProjectOp.
            has_wrappers = any(
                not (
                    isinstance(t.val, FuncCall)
                    and t.val.funcname[-1].sval.lower() in _AGG_FUNC_NAMES
                    and t.val.over is None
                )
                for t in stmt.targetList
            )
            if has_wrappers:
                targets = self._build_expr_targets(stmt.targetList)
                physical = ExprProjectOp(
                    physical,
                    targets,
                    subquery_executor=self._compile_select,
                )
                expected_cols = [name for name, _ in targets]
            else:
                expected_cols = [a for a, *_ in agg_specs]

        else:
            is_star = self._is_select_star(stmt.targetList)
            if is_star and join_source:
                # SELECT * on a join: expand to explicit columns matching
                # PostgreSQL behavior (table columns in FROM order, no
                # internal fields like _doc_id/_score, no qualified
                # duplicates).
                join_tables = self._collect_join_tables(stmt.fromClause)
                star_targets: list[tuple[str, Any]] = []
                for alias, cols in join_tables:
                    for col in cols:
                        star_targets.append(
                            (
                                col,
                                ColumnRef(
                                    fields=(
                                        PgString(sval=alias),
                                        PgString(sval=col),
                                    )
                                ),
                            )
                        )
                if star_targets:
                    physical = ExprProjectOp(
                        physical,
                        star_targets,
                        subquery_executor=self._compile_select,
                        sequences=self._engine._sequences,
                    )
                    expected_cols = [name for name, _ in star_targets]
            elif not is_star:
                # Check whether ORDER BY references columns outside
                # the SELECT list.  If so, defer projection until
                # after the sort so the sort keys are still available.
                defer_proj = False
                if stmt.sortClause is not None:
                    sort_keys_pre = self._build_sort_keys(
                        stmt.sortClause,
                        stmt.targetList,
                    )
                    defer_proj = self._sort_needs_extra_cols(
                        sort_keys_pre,
                        stmt.targetList,
                    )

                use_expr = join_source or self._has_computed_expressions(
                    stmt.targetList
                )
                if not defer_proj:
                    if use_expr:
                        targets = self._build_expr_targets(stmt.targetList)
                        physical = ExprProjectOp(
                            physical,
                            targets,
                            subquery_executor=self._compile_select,
                            sequences=self._engine._sequences,
                        )
                        expected_cols = [name for name, _ in targets]
                    else:
                        proj_cols, proj_aliases = self._resolve_projection_cols(
                            stmt.targetList
                        )
                        physical = ProjectOp(physical, proj_cols, proj_aliases)
                        expected_cols = [proj_aliases.get(c, c) for c in proj_cols]

        # DISTINCT
        if stmt.distinctClause is not None:
            distinct_cols = expected_cols
            if distinct_cols is None:
                distinct_cols = list(table.columns.keys()) if table is not None else []
            physical = DistinctOp(
                physical,
                distinct_cols,
                spill_threshold=self._engine.spill_threshold,
            )

        # ORDER BY
        if stmt.sortClause is not None:
            sort_keys = self._build_sort_keys(stmt.sortClause, stmt.targetList)
            physical = SortOp(
                physical,
                sort_keys,
                spill_threshold=self._engine.spill_threshold,
            )

        # Deferred projection: apply after ORDER BY so sort keys
        # that reference non-projected columns are available.
        if defer_proj:
            if use_expr:
                targets = self._build_expr_targets(stmt.targetList)
                physical = ExprProjectOp(
                    physical,
                    targets,
                    subquery_executor=self._compile_select,
                    sequences=self._engine._sequences,
                )
                expected_cols = [name for name, _ in targets]
            else:
                proj_cols, proj_aliases = self._resolve_projection_cols(stmt.targetList)
                physical = ProjectOp(physical, proj_cols, proj_aliases)
                expected_cols = [proj_aliases.get(c, c) for c in proj_cols]

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
        batches: list[Any] = []
        while True:
            batch = physical.next()
            if batch is None:
                break
            rb = (
                batch.compact().record_batch
                if batch.selection is not None
                else batch.record_batch
            )
            batches.append(rb)
        physical.close()

        # Determine column names
        if expected_cols is not None:
            columns = expected_cols
        elif batches:
            columns = list(batches[0].schema.names)
        elif table is not None:
            columns = list(table.columns.keys())
        else:
            columns = []

        return SQLResult(columns, None, batches=batches)

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
                if fn in _AGG_FUNC_NAMES:
                    continue
                alias = target.name or fn
                if "_score" not in proj_cols:
                    proj_cols.append("_score")
                proj_aliases["_score"] = alias
        return proj_cols, proj_aliases

    @staticmethod
    def _has_computed_expressions(target_list: tuple | None) -> bool:
        """Check if any target is a computed expression (not a simple column)."""
        from pglast.ast import MinMaxExpr, SQLValueFunction

        if target_list is None:
            return False
        for target in target_list:
            val = target.val
            if isinstance(val, ColumnRef):
                continue
            if isinstance(val, FuncCall):
                fn = val.funcname[-1].sval.lower()
                if fn in _AGG_FUNC_NAMES:
                    continue
                # Non-aggregate functions like UPPER(), LOWER() are computed
                if fn in (
                    "text_match",
                    "bayesian_match",
                    "bayesian_match_with_prior",
                    "knn_match",
                    "traverse_match",
                    "spatial_within",
                ):
                    continue
                return True
            if isinstance(
                val,
                A_Const
                | A_ArrayExpr
                | A_Expr
                | CaseExpr
                | TypeCast
                | CoalesceExpr
                | NullTest
                | SubLink
                | MinMaxExpr
                | SQLValueFunction,
            ):
                return True
        return False

    def _build_expr_targets(self, target_list: tuple) -> list[tuple[str, Any]]:
        """Build (output_name, ast_node) pairs for ExprProjectOp.

        For text_match/bayesian_match function calls, wraps the node
        so the ExprEvaluator reads ``_score`` from the row instead.

        Output column names follow PostgreSQL convention: the unqualified
        column name is always used, even when multiple columns share the
        same name (e.g. ``SELECT a.id, b.id`` produces two ``id`` columns).
        Use explicit aliases (``AS``) to disambiguate when needed.
        """
        targets: list[tuple[str, Any]] = []
        for target in target_list:
            output_name = self._infer_target_name(target)
            val = target.val
            # text_match/bayesian_match -> read _score column
            if isinstance(val, FuncCall):
                fn = val.funcname[-1].sval.lower()
                if fn in ("text_match", "bayesian_match", "bayesian_match_with_prior"):
                    val = ColumnRef(fields=(PgString(sval="_score"),))
            targets.append((output_name, val))
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
            if fn in _AGG_FUNC_NAMES:
                arg_col = (
                    None if val.agg_star else (self._extract_column_name(val.args[0]))
                )
                return fn if arg_col is None else f"{fn}_{arg_col}"
            if fn in ("text_match", "bayesian_match", "bayesian_match_with_prior"):
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

    def _build_sort_keys(
        self,
        sort_clause: tuple,
        target_list: tuple | None,
    ) -> list[tuple[str, bool, bool]]:
        """Build sort keys from ORDER BY clause with alias/ordinal resolution.

        Returns list of (column_name, is_desc, nulls_first) tuples.
        Supports:
          - Column names: ORDER BY name
          - Column aliases: ORDER BY alias_name
          - Ordinal references: ORDER BY 1, 2
          - NULLS FIRST / NULLS LAST modifiers
        """
        # Build mappings from SELECT list for alias/ordinal resolution
        # original_to_alias: maps original column to its alias name
        # alias_names: set of all alias names
        original_to_alias: dict[str, str] = {}
        alias_names: set[str] = set()
        ordinal_map: dict[int, str] = {}
        if target_list:
            for idx, target in enumerate(target_list):
                # Skip SELECT * -- it expands to all columns and
                # does not contribute to ordinal/alias mappings.
                if isinstance(target.val, A_Star):
                    continue
                if isinstance(target.val, ColumnRef) and isinstance(
                    target.val.fields[-1], A_Star
                ):
                    continue
                col_name = self._infer_target_name(target)
                ordinal_map[idx + 1] = col_name
                if target.name:
                    alias_names.add(target.name)
                    if isinstance(target.val, ColumnRef):
                        real_col = self._extract_column_name(target.val)
                        original_to_alias[real_col] = target.name

        sort_keys: list[tuple[str, bool, bool]] = []
        for s in sort_clause:
            is_desc = s.sortby_dir == SortByDir.SORTBY_DESC
            if s.sortby_nulls == SortByNulls.SORTBY_NULLS_FIRST:
                nulls_first = True
            elif s.sortby_nulls == SortByNulls.SORTBY_NULLS_LAST:
                nulls_first = False
            else:
                # PostgreSQL default: NULLS FIRST for DESC, NULLS LAST for ASC
                nulls_first = is_desc

            # Ordinal reference: ORDER BY 1, 2, ...
            if isinstance(s.node, A_Const) and isinstance(s.node.val, PgInteger):
                ordinal = s.node.val.ival
                col = ordinal_map.get(ordinal)
                if col is None:
                    raise ValueError(
                        f"ORDER BY position {ordinal} is not in select list"
                    )
            else:
                col = self._extract_column_name(s.node)
                # If col is already an alias, use as-is.
                # If col is an original column that was aliased, use alias.
                if col not in alias_names and col in original_to_alias:
                    col = original_to_alias[col]

            sort_keys.append((col, is_desc, nulls_first))
        return sort_keys

    @staticmethod
    def _sort_needs_extra_cols(
        sort_keys: list[tuple[str, bool, bool]],
        target_list: tuple | None,
    ) -> bool:
        """Return True if ORDER BY references columns not in SELECT."""
        if target_list is None:
            return False
        projected: set[str] = set()
        for target in target_list:
            if isinstance(target.val, A_Star):
                return False
            if isinstance(target.val, ColumnRef):
                fields = target.val.fields
                if isinstance(fields[-1], A_Star):
                    return False
                col = (
                    fields[-1].sval if hasattr(fields[-1], "sval") else str(fields[-1])
                )
                projected.add(col)
                if target.name:
                    projected.add(target.name)
            elif target.name:
                projected.add(target.name)
        return any(col_name not in projected for col_name, _, _ in sort_keys)

    def _build_group_aliases(
        self,
        group_cols: list[str],
        target_list: tuple | None,
    ) -> dict[str, str]:
        """Build column_name -> alias mapping for group columns."""
        aliases: dict[str, str] = {}
        if not target_list:
            return aliases
        for target in target_list:
            if isinstance(target.val, ColumnRef) and target.name:
                col = self._extract_column_name(target.val)
                if col in group_cols:
                    aliases[col] = target.name
        return aliases

    def _build_post_group_targets(
        self,
        target_list: tuple | None,
        group_cols: list[str],
        agg_specs: list[tuple],
    ) -> list[tuple[str, Any]] | None:
        """Build ExprProjectOp targets for non-aggregate computed
        expressions in a GROUP BY SELECT list.

        Returns ``None`` when all SELECT targets are plain columns or
        aggregates (no post-group computation needed).
        """
        if not target_list:
            return None

        agg_aliases = {spec[0] for spec in agg_specs}
        has_computed = False
        for target in target_list:
            if isinstance(target.val, FuncCall):
                fn = target.val.funcname[-1].sval.lower()
                if fn not in _AGG_FUNC_NAMES or target.val.over is not None:
                    has_computed = True
                    break
            elif not isinstance(target.val, ColumnRef):
                name = target.name or "?column?"
                if name not in agg_aliases:
                    has_computed = True
                    break

        if not has_computed:
            return None

        # Build targets for the full SELECT list.  Group columns and
        # aggregate results are referenced by their output names from
        # HashAggOp; computed expressions are evaluated from those.
        group_set = set(group_cols)
        targets: list[tuple[str, Any]] = []
        for target in target_list:
            name = target.name or self._infer_target_name(target)
            if name in agg_aliases or name in group_set:
                # Aggregate or group column: pass through by name
                ref = ColumnRef(fields=[PgString(sval=name)])
                targets.append((name, ref))
            elif isinstance(target.val, ColumnRef):
                col = self._extract_column_name(target.val)
                ref = ColumnRef(fields=[PgString(sval=col)])
                targets.append((name, ref))
            else:
                # Computed expression: evaluate from HashAggOp output
                targets.append((name, target.val))
        return targets

    def _resolve_select_column_names(
        self,
        target_list: tuple | None,
        group_cols: list[str],
        agg_specs: list[tuple],
    ) -> list[str]:
        """Build expected column names from SELECT targets.

        For GROUP BY queries, maps group columns to their SELECT aliases
        and appends aggregate column aliases.
        """
        cols: list[str] = []
        if target_list:
            for target in target_list:
                if isinstance(target.val, ColumnRef):
                    col = self._extract_column_name(target.val)
                    # Use alias if present, otherwise raw column name
                    cols.append(target.name or col)
                elif isinstance(target.val, FuncCall):
                    func = target.val
                    fn = func.funcname[-1].sval.lower()
                    if func.agg_star:
                        natural = fn
                    elif func.args:
                        col_arg = None
                        for a in func.args:
                            if isinstance(a, ColumnRef):
                                col_arg = self._extract_column_name(a)
                        natural = f"{fn}_{col_arg}" if col_arg else fn
                    else:
                        natural = fn
                    cols.append(target.name or natural)
                else:
                    cols.append(target.name or self._infer_target_name(target))
        if not cols:
            cols = group_cols + [a for a, *_ in agg_specs]
        return cols

    def _build_pre_agg_targets(
        self,
        group_clause: tuple,
        group_cols: list[str],
        agg_specs: list[tuple],
        table: Any,
    ) -> list[tuple[str, Any]] | None:
        """Build ExprProjectOp targets to pre-compute expressions
        before HashAggOp.

        Covers two cases:
        - GROUP BY with FuncCall (e.g., DATE_TRUNC)
        - Aggregate args that are expressions (e.g., SUM(CASE ...))

        Returns ``None`` when no pre-computation is needed.
        """
        expr_targets: list[tuple[str, Any]] = []

        # GROUP BY computed expressions
        for idx, g in enumerate(group_clause):
            if isinstance(g, FuncCall):
                expr_targets.append((group_cols[idx], g))

        # Aggregate expression args (8th element of spec tuple)
        for spec in agg_specs:
            if len(spec) > 7 and spec[7] is not None:
                expr_targets.append((spec[2], spec[7]))

        if not expr_targets:
            return None

        # Pass through all raw table columns, then append
        # the computed expression columns.
        targets: list[tuple[str, Any]] = []
        col_names = list(table.columns.keys()) if table else []
        for col_name in col_names:
            ref = ColumnRef(fields=[PgString(sval=col_name)])
            targets.append((col_name, ref))
        for alias, node in expr_targets:
            targets.append((alias, node))
        return targets

    def _resolve_group_by_cols(
        self,
        group_clause: tuple,
        target_list: tuple | None,
    ) -> list[str]:
        """Resolve GROUP BY items: column names, aliases, or ordinals."""
        # Build alias map from SELECT list
        alias_map: dict[str, str] = {}
        select_cols: list[str] = []
        if target_list:
            for target in target_list:
                if isinstance(target.val, ColumnRef):
                    col = self._extract_column_name(target.val)
                    select_cols.append(target.name or col)
                    if target.name:
                        alias_map[target.name] = col
                elif isinstance(target.val, FuncCall):
                    fn = target.val.funcname[-1].sval.lower()
                    if target.val.agg_star:
                        name = fn
                    elif target.val.args:
                        # First arg may not be a ColumnRef (e.g.,
                        # DATE_TRUNC('month', col)).  Fall back to the
                        # last ColumnRef arg, then to just the func name.
                        col_arg = None
                        for a in target.val.args:
                            if isinstance(a, ColumnRef):
                                col_arg = self._extract_column_name(a)
                        name = f"{fn}_{col_arg}" if col_arg else fn
                    else:
                        name = fn
                    select_cols.append(target.name or name)
                else:
                    select_cols.append(target.name or "?column?")

        result: list[str] = []
        for g in group_clause:
            # Ordinal reference: GROUP BY 1, 2
            if isinstance(g, A_Const):
                val = g.val
                if isinstance(val, PgInteger):
                    idx = val.ival - 1  # 1-based
                    if 0 <= idx < len(select_cols):
                        result.append(select_cols[idx])
                        continue
                    raise ValueError(
                        f"GROUP BY position {val.ival} is not in select list"
                    )

            # Column reference
            if isinstance(g, ColumnRef):
                col = self._extract_column_name(g)
                # Check alias map
                result.append(alias_map.get(col, col))
                continue

            # FuncCall in GROUP BY: match against SELECT targets by
            # function name and use the SELECT alias.
            if isinstance(g, FuncCall):
                g_fn = g.funcname[-1].sval.lower()
                matched = None
                if target_list:
                    for target in target_list:
                        if (
                            isinstance(target.val, FuncCall)
                            and target.val.funcname[-1].sval.lower() == g_fn
                            and target.name
                        ):
                            matched = target.name
                            break
                if matched:
                    result.append(matched)
                else:
                    # Generate name from func + last ColumnRef arg
                    col_arg = None
                    if g.args:
                        for a in g.args:
                            if isinstance(a, ColumnRef):
                                col_arg = self._extract_column_name(a)
                    name = f"{g_fn}_{col_arg}" if col_arg else g_fn
                    result.append(name)
                continue

            # Fallback: try extracting column name
            result.append(self._extract_column_name(g))
        return result

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

        if isinstance(having_node, A_Expr) and isinstance(having_node.lexpr, FuncCall):
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

        raise ValueError(f"Unsupported HAVING clause: {type(having_node).__name__}")

    # ==================================================================
    # DQL: SELECT
    # ==================================================================

    def _compile_select(
        self,
        stmt: SelectStmt,
        *,
        explain: bool = False,
        outer_row: dict[str, Any] | None = None,
    ) -> SQLResult:
        # 0. Materialize CTEs as temporary in-memory tables
        cte_names: list[str] = []
        if stmt.withClause is not None:
            cte_names = self._materialize_ctes(
                stmt.withClause.ctes,
                recursive=bool(stmt.withClause.recursive),
                main_query=stmt,
            )

        # Save and set correlated outer row context for this subquery.
        prev_outer_row = getattr(self, "_correlated_outer_row", None)
        self._correlated_outer_row = outer_row

        prev_inlined = dict(self._inlined_ctes)

        try:
            return self._compile_select_body(stmt, explain=explain)
        finally:
            self._correlated_outer_row = prev_outer_row
            # Clean up inlined CTEs that were consumed during resolution
            for name in cte_names:
                self._inlined_ctes.pop(name, None)
            # Restore previous inlined CTEs state
            self._inlined_ctes = prev_inlined
            # Clean up CTE temporary tables
            for name in cte_names:
                self._engine._tables.pop(name, None)
            # Clean up materialized view / derived tables
            for name in self._expanded_views:
                if name in self._shadowed_tables:
                    self._engine._tables[name] = self._shadowed_tables.pop(name)
                else:
                    self._engine._tables.pop(name, None)
            self._expanded_views.clear()

    def _extract_pushdown_predicates(
        self,
        where_node: Any,
    ) -> tuple[list, Any | None]:
        """Split a WHERE clause into pushable and non-pushable parts.

        Walks the AST and extracts simple ``column op constant``
        comparisons that can be forwarded to the FDW handler for
        server-side evaluation (e.g. Hive partition pruning).

        Returns ``(pushable, remaining)`` where *pushable* is a list
        of :class:`FDWPredicate` instances and *remaining* is the AST
        subtree that must still be evaluated post-scan (or ``None`` if
        the entire WHERE was pushed down).
        """
        from uqa.fdw.foreign_table import FDWPredicate

        if isinstance(where_node, BoolExpr):
            if where_node.boolop == BoolExprType.AND_EXPR:
                pushable: list[FDWPredicate] = []
                remaining: list = []
                for arg in where_node.args:
                    sub_push, sub_remain = self._extract_pushdown_predicates(arg)
                    pushable.extend(sub_push)
                    if sub_remain is not None:
                        remaining.append(sub_remain)
                if not remaining:
                    return pushable, None
                if len(remaining) == 1:
                    return pushable, remaining[0]
                return pushable, BoolExpr(
                    boolop=BoolExprType.AND_EXPR,
                    args=tuple(remaining),
                )
            # OR / NOT -- not pushable
            return [], where_node

        if isinstance(where_node, A_Expr):
            kind = where_node.kind
            rhs_is_const = isinstance(
                where_node.rexpr, A_Const | PgInteger | PgFloat | PgString
            )
            if rhs_is_const and kind == A_Expr_Kind.AEXPR_OP:
                op_name = where_node.name[-1].sval
                if op_name in ("=", "!=", "<>", "<", "<=", ">", ">="):
                    try:
                        col_name = self._extract_column_name(where_node.lexpr)
                    except ValueError:
                        return [], where_node
                    value = self._extract_const_value(where_node.rexpr)
                    return [FDWPredicate(col_name, op_name, value)], None

            # BETWEEN: split into >= and <= predicates
            if kind == A_Expr_Kind.AEXPR_BETWEEN:
                try:
                    col_name = self._extract_column_name(where_node.lexpr)
                except ValueError:
                    return [], where_node
                bounds = where_node.rexpr
                if (
                    len(bounds) == 2
                    and isinstance(bounds[0], A_Const)
                    and isinstance(bounds[1], A_Const)
                ):
                    lo = self._extract_const_value(bounds[0])
                    hi = self._extract_const_value(bounds[1])
                    return [
                        FDWPredicate(col_name, ">=", lo),
                        FDWPredicate(col_name, "<=", hi),
                    ], None

            # IN: pushable when all RHS elements are constants
            if kind == A_Expr_Kind.AEXPR_IN:
                try:
                    col_name = self._extract_column_name(where_node.lexpr)
                except ValueError:
                    return [], where_node
                elements = where_node.rexpr
                if isinstance(elements, list | tuple) and all(
                    isinstance(e, A_Const) for e in elements
                ):
                    values = tuple(self._extract_const_value(e) for e in elements)
                    return [FDWPredicate(col_name, "IN", values)], None

            # LIKE / NOT LIKE
            if kind == A_Expr_Kind.AEXPR_LIKE:
                try:
                    col_name = self._extract_column_name(where_node.lexpr)
                except ValueError:
                    return [], where_node
                if isinstance(where_node.rexpr, A_Const):
                    pattern = self._extract_const_value(where_node.rexpr)
                    op_name = where_node.name[0].sval
                    if op_name == "!~~":
                        return [
                            FDWPredicate(col_name, "NOT LIKE", pattern),
                        ], None
                    return [
                        FDWPredicate(col_name, "LIKE", pattern),
                    ], None

            # ILIKE / NOT ILIKE
            if kind == A_Expr_Kind.AEXPR_ILIKE:
                try:
                    col_name = self._extract_column_name(where_node.lexpr)
                except ValueError:
                    return [], where_node
                if isinstance(where_node.rexpr, A_Const):
                    pattern = self._extract_const_value(where_node.rexpr)
                    op_name = where_node.name[0].sval
                    if op_name == "!~~*":
                        return [
                            FDWPredicate(col_name, "NOT ILIKE", pattern),
                        ], None
                    return [
                        FDWPredicate(col_name, "ILIKE", pattern),
                    ], None

        # Everything else: not pushable
        return [], where_node

    # -- Join predicate pushdown -------------------------------------------

    def _partition_where_for_joins(
        self, where_clause: Any, source_op: Any
    ) -> tuple[dict[str, list], Any]:
        """Partition WHERE conjuncts into per-alias pushable and remaining.

        Decomposes AND conjuncts and classifies each by the table aliases
        it references.  Single-alias conjuncts whose alias has a reachable
        _TableScanOperator below an inner join are pushable.  Everything
        else stays as deferred WHERE.

        Returns (pushable_per_alias, remaining_where_node).
        """
        conjuncts = self._extract_and_conjuncts(where_clause)
        scan_aliases = self._collect_inner_join_scan_aliases(source_op)

        pushable: dict[str, list] = {}
        remaining: list = []

        for conj in conjuncts:
            aliases = self._collect_conjunct_aliases(conj)
            if len(aliases) == 1:
                alias = next(iter(aliases))
                if alias in scan_aliases:
                    pushable.setdefault(alias, []).append(conj)
                    continue
            remaining.append(conj)

        remaining_node = self._reconstruct_and(remaining)
        return pushable, remaining_node

    @staticmethod
    def _extract_and_conjuncts(node: Any) -> list:
        """Flatten nested AND expressions into a list of conjuncts."""
        if isinstance(node, BoolExpr) and node.boolop == BoolExprType.AND_EXPR:
            result: list = []
            for arg in node.args:
                result.extend(SQLCompiler._extract_and_conjuncts(arg))
            return result
        return [node]

    @staticmethod
    def _collect_conjunct_aliases(node: Any) -> set[str]:
        """Collect table alias prefixes from ColumnRef nodes in an AST subtree."""
        aliases: set[str] = set()
        SQLCompiler._walk_for_column_aliases(node, aliases)
        return aliases

    @staticmethod
    def _walk_for_column_aliases(node: Any, aliases: set[str]) -> None:
        """Recursively walk AST, extracting alias prefixes from ColumnRef."""
        if isinstance(node, ColumnRef):
            if node.fields and len(node.fields) >= 2:
                first = node.fields[0]
                alias = first.sval if hasattr(first, "sval") else str(first)
                aliases.add(alias)
            return

        # Recurse into common AST node attributes
        for attr in ("lexpr", "rexpr", "args", "arg", "xpr", "val"):
            child = getattr(node, attr, None)
            if child is None:
                continue
            if isinstance(child, list | tuple):
                for c in child:
                    if c is not None:
                        SQLCompiler._walk_for_column_aliases(c, aliases)
            else:
                SQLCompiler._walk_for_column_aliases(child, aliases)

    @staticmethod
    def _collect_inner_join_scan_aliases(op: Any) -> set[str]:
        """Collect aliases from _TableScanOperator leaves reachable via inner joins.

        Only scans behind INNER/INDEX/CROSS joins are safe for predicate
        pushdown.  Scans behind outer joins are excluded to preserve
        correct NULL-extension semantics.
        """
        from uqa.joins.cross import CrossJoinOperator
        from uqa.joins.index import IndexJoinOperator
        from uqa.joins.inner import InnerJoinOperator

        aliases: set[str] = set()
        if isinstance(op, _TableScanOperator) and op._alias:
            aliases.add(op._alias)
        elif isinstance(op, InnerJoinOperator | IndexJoinOperator | CrossJoinOperator):
            aliases |= SQLCompiler._collect_inner_join_scan_aliases(op.left)
            aliases |= SQLCompiler._collect_inner_join_scan_aliases(op.right)
        return aliases

    @staticmethod
    def _reconstruct_and(conjuncts: list) -> Any:
        """Rebuild a BoolExpr AND node from a list of conjuncts."""
        if not conjuncts:
            return None
        if len(conjuncts) == 1:
            return conjuncts[0]
        return BoolExpr(boolop=BoolExprType.AND_EXPR, args=tuple(conjuncts))

    def _inject_join_filters(self, join_op: Any, pushable: dict[str, list]) -> Any:
        """Walk join operator tree and wrap matching table scans with filters."""
        from uqa.joins.cross import CrossJoinOperator
        from uqa.joins.index import IndexJoinOperator
        from uqa.joins.inner import InnerJoinOperator

        if isinstance(
            join_op, InnerJoinOperator | IndexJoinOperator | CrossJoinOperator
        ):
            new_left = self._inject_scan_filter(join_op.left, pushable)
            new_right = self._inject_scan_filter(join_op.right, pushable)
            if new_left is not join_op.left or new_right is not join_op.right:
                if isinstance(join_op, CrossJoinOperator):
                    return CrossJoinOperator(new_left, new_right)
                return type(join_op)(new_left, new_right, join_op.condition)
        return join_op

    def _inject_scan_filter(self, scan: Any, pushable: dict[str, list]) -> Any:
        """Wrap a scan with a filter if pushable predicates match its alias."""
        from uqa.joins.cross import CrossJoinOperator
        from uqa.joins.index import IndexJoinOperator
        from uqa.joins.inner import InnerJoinOperator

        if isinstance(scan, InnerJoinOperator | IndexJoinOperator | CrossJoinOperator):
            return self._inject_join_filters(scan, pushable)

        if isinstance(scan, _TableScanOperator):
            alias = scan._alias
            if alias and alias in pushable:
                where_node = self._reconstruct_and(pushable[alias])
                return _FilteredScanOperator(scan, where_node, self._compile_select)
        return scan

    def _apply_deferred_where(self, physical: Any, where_node: Any) -> Any:
        """Apply WHERE predicates as physical filter on joined/graph rows.

        For simple column-to-constant comparisons, uses typed PhysFilterOp.
        For cross-table or complex expressions (e.g., a.id = b.user_id),
        falls back to ExprFilterOp using ExprEvaluator.
        """
        from uqa.core.types import (
            Equals,
            GreaterThan,
            GreaterThanOrEqual,
            LessThan,
            LessThanOrEqual,
            NotEquals,
        )
        from uqa.execution.relational import (
            ExprFilterOp,
        )
        from uqa.execution.relational import (
            FilterOp as PhysFilterOp,
        )

        if (
            isinstance(where_node, BoolExpr)
            and where_node.boolop == BoolExprType.AND_EXPR
        ):
            for arg in where_node.args:
                physical = self._apply_deferred_where(physical, arg)
            return physical

        if isinstance(where_node, A_Expr):
            kind = where_node.kind

            # Check if RHS is a constant (column-to-constant comparison)
            rhs_is_const = isinstance(
                where_node.rexpr, A_Const | PgInteger | PgFloat | PgString
            )

            if rhs_is_const and kind == A_Expr_Kind.AEXPR_OP:
                col_name = self._extract_column_name(where_node.lexpr)
                rhs = self._extract_const_value(where_node.rexpr)
                op_name = where_node.name[-1].sval
                predicate_map = {
                    "=": Equals,
                    "!=": NotEquals,
                    "<>": NotEquals,
                    "<": LessThan,
                    "<=": LessThanOrEqual,
                    ">": GreaterThan,
                    ">=": GreaterThanOrEqual,
                }
                pred_cls = predicate_map.get(op_name)
                if pred_cls is not None:
                    return PhysFilterOp(physical, col_name, pred_cls(rhs))

            if rhs_is_const and kind == A_Expr_Kind.AEXPR_BETWEEN:
                col_name = self._extract_column_name(where_node.lexpr)
                lo = self._extract_const_value(where_node.rexpr[0])
                hi = self._extract_const_value(where_node.rexpr[1])
                physical = PhysFilterOp(physical, col_name, GreaterThanOrEqual(lo))
                return PhysFilterOp(physical, col_name, LessThanOrEqual(hi))

        # Fallback: use ExprEvaluator for complex expressions
        # (e.g., cross-table column comparisons like a.id = b.user_id)
        return ExprFilterOp(
            physical,
            where_node,
            subquery_executor=self._compile_select,
        )

    def _compile_select_body(
        self, stmt: SelectStmt, *, explain: bool = False
    ) -> SQLResult:
        # Handle standalone VALUES
        if stmt.valuesLists is not None:
            return self._compile_values(stmt)

        # 0. Handle set operations (UNION / INTERSECT / EXCEPT)
        if stmt.op is not None and stmt.op != SetOperation.SETOP_NONE:
            return self._compile_set_operation(stmt)

        # 1. Predicate pushdown into views/derived tables.
        #    If FROM is a single view or derived table, push safe WHERE
        #    predicates into the subquery before materialization.
        stmt = self._try_predicate_pushdown(stmt)

        # 2. Resolve FROM clause -> (table | None, source_op | None)
        table, source_op = self._resolve_from(
            stmt.fromClause, where_clause=stmt.whereClause
        )

        # 3. Build execution context from resolved table
        ctx = self._context_for_table(table)

        # 4. Check if FROM is a graph source (traverse/rpq) or join.
        #    Graph/join-sourced queries defer relational WHERE to the
        #    physical layer because their entries are not single-table
        #    doc_ids from the document store.
        graph_source = self._is_graph_operator(source_op)
        join_source = self._is_join_operator(source_op)
        foreign_source = isinstance(source_op, _ForeignTableScanOperator)
        deferred_where = None

        # 5. Constant folding: evaluate compile-time constant expressions
        if stmt.whereClause is not None:
            stmt = self._fold_stmt_where(stmt)

        # 6. WHERE clause
        if stmt.whereClause is not None:
            if foreign_source:
                # Extract pushable predicates for the FDW handler and
                # keep the rest as deferred WHERE for post-scan filtering.
                pushable, remaining = self._extract_pushdown_predicates(
                    stmt.whereClause,
                )
                if pushable:
                    source_op.pushdown_predicates = pushable
                deferred_where = remaining
            elif join_source:
                # Push single-table predicates below the join for
                # early filtering; keep cross-table predicates deferred.
                pushable, remaining = self._partition_where_for_joins(
                    stmt.whereClause, source_op
                )
                if pushable:
                    source_op = self._inject_join_filters(source_op, pushable)
                deferred_where = remaining
            elif graph_source:
                # Defer WHERE to physical ExprFilterOp layer
                deferred_where = stmt.whereClause
            else:
                where_op = self._compile_where(stmt.whereClause, ctx)
                if source_op is not None:
                    where_op = self._chain_on_source(where_op, source_op)
                source_op = where_op

        # 7. Optimize and execute operator tree
        if source_op is not None:
            source_op = self._optimize(source_op, ctx, table)
            if explain:
                return self._explain_plan(source_op, ctx)
            pl = self._execute_plan(source_op, ctx)
        else:
            if explain:
                return SQLResult(["plan"], [{"plan": "Seq Scan (full table)"}])
            # LIMIT pushdown: when there's no WHERE/ORDER BY/GROUP BY/
            # HAVING/DISTINCT/window, we can limit the scan early.
            scan_limit = None
            if (
                stmt.whereClause is None
                and stmt.sortClause is None
                and stmt.groupClause is None
                and not stmt.distinctClause
                and stmt.havingClause is None
                and stmt.windowClause is None
                and stmt.limitCount is not None
            ):
                scan_offset = 0
                if stmt.limitOffset is not None:
                    scan_offset = self._extract_int_value(stmt.limitOffset)
                scan_limit = self._extract_int_value(stmt.limitCount) + scan_offset
            pl = self._scan_all(ctx, limit=scan_limit)

        # 8. Execute relational operations via physical operators
        return self._execute_relational(
            stmt,
            pl,
            ctx,
            table,
            deferred_where=deferred_where,
            join_source=join_source or foreign_source,
        )

    def _compile_values(self, stmt: SelectStmt) -> SQLResult:
        """Handle standalone VALUES (1, 'a'), (2, 'b') queries."""
        rows: list[dict[str, Any]] = []
        num_cols = len(stmt.valuesLists[0]) if stmt.valuesLists else 0
        columns = [f"column{i + 1}" for i in range(num_cols)]

        for row_values in stmt.valuesLists:
            row: dict[str, Any] = {}
            for i, val_node in enumerate(row_values):
                row[columns[i]] = self._extract_insert_value(val_node)
            rows.append(row)

        # Apply ORDER BY if present
        if stmt.sortClause is not None:
            from uqa.execution.relational import SortOp

            sort_keys: list[tuple[str, bool, bool]] = []
            for s in stmt.sortClause:
                is_desc = s.sortby_dir == SortByDir.SORTBY_DESC
                if s.sortby_nulls == SortByNulls.SORTBY_NULLS_FIRST:
                    nulls_first = True
                elif s.sortby_nulls == SortByNulls.SORTBY_NULLS_LAST:
                    nulls_first = False
                else:
                    nulls_first = is_desc
                if isinstance(s.node, A_Const) and isinstance(s.node.val, PgInteger):
                    ordinal = s.node.val.ival
                    if 1 <= ordinal <= num_cols:
                        col = columns[ordinal - 1]
                    else:
                        raise ValueError(
                            f"ORDER BY position {ordinal} is not in select list"
                        )
                else:
                    col = self._extract_column_name(s.node)
                sort_keys.append((col, is_desc, nulls_first))
            SortOp._sort_rows(rows, sort_keys)

        # Apply LIMIT/OFFSET
        if stmt.limitCount is not None:
            offset = 0
            if stmt.limitOffset is not None:
                offset = self._extract_int_value(stmt.limitOffset)
            limit = self._extract_int_value(stmt.limitCount)
            rows = rows[offset : offset + limit]

        return SQLResult(columns, rows)

    # -- Set operations (UNION / INTERSECT / EXCEPT) -------------------

    def _compile_set_operation(self, stmt: SelectStmt) -> SQLResult:
        """Handle UNION / INTERSECT / EXCEPT set operations."""
        from uqa.execution.relational import SortOp

        left = self._compile_select(stmt.larg)
        right = self._compile_select(stmt.rarg)

        if len(left.columns) != len(right.columns):
            raise ValueError(
                f"Set operation column count mismatch: "
                f"{len(left.columns)} vs {len(right.columns)}"
            )

        # Normalize right result columns to match left column names
        right_rows = [
            {
                left.columns[i]: row.get(right.columns[i])
                for i in range(len(left.columns))
            }
            for row in right.rows
        ]
        columns = left.columns
        is_all = bool(stmt.all)
        op = SetOperation(stmt.op)

        if op == SetOperation.SETOP_UNION:
            rows = self._set_union(left.rows, right_rows, columns, is_all)
        elif op == SetOperation.SETOP_INTERSECT:
            rows = self._set_intersect(left.rows, right_rows, columns, is_all)
        elif op == SetOperation.SETOP_EXCEPT:
            rows = self._set_except(left.rows, right_rows, columns, is_all)
        else:
            raise ValueError(f"Unsupported set operation: {op}")

        # Apply ORDER BY / LIMIT on the combined result
        if stmt.sortClause is not None:
            sort_keys = self._build_sort_keys(stmt.sortClause, stmt.larg.targetList)
            SortOp._sort_rows(rows, sort_keys)

        if stmt.limitCount is not None:
            offset = 0
            if stmt.limitOffset is not None:
                offset = self._extract_int_value(stmt.limitOffset)
            limit = self._extract_int_value(stmt.limitCount)
            rows = rows[offset : offset + limit]

        return SQLResult(columns, rows)

    @staticmethod
    def _set_union(
        left_rows: list[dict],
        right_rows: list[dict],
        columns: list[str],
        is_all: bool,
    ) -> list[dict]:
        if is_all:
            return list(left_rows) + right_rows
        seen: set[tuple] = set()
        rows: list[dict] = []
        for row in list(left_rows) + right_rows:
            key = tuple(row.get(c) for c in columns)
            if key not in seen:
                seen.add(key)
                rows.append(row)
        return rows

    @staticmethod
    def _set_intersect(
        left_rows: list[dict],
        right_rows: list[dict],
        columns: list[str],
        is_all: bool,
    ) -> list[dict]:
        from collections import Counter

        if is_all:
            right_counter: Counter[tuple] = Counter(
                tuple(r.get(c) for c in columns) for r in right_rows
            )
            rows: list[dict] = []
            for row in left_rows:
                key = tuple(row.get(c) for c in columns)
                if right_counter[key] > 0:
                    rows.append(row)
                    right_counter[key] -= 1
            return rows

        right_keys = {tuple(r.get(c) for c in columns) for r in right_rows}
        seen: set[tuple] = set()
        rows = []
        for row in left_rows:
            key = tuple(row.get(c) for c in columns)
            if key in right_keys and key not in seen:
                seen.add(key)
                rows.append(row)
        return rows

    @staticmethod
    def _set_except(
        left_rows: list[dict],
        right_rows: list[dict],
        columns: list[str],
        is_all: bool,
    ) -> list[dict]:
        from collections import Counter

        if is_all:
            right_counter: Counter[tuple] = Counter(
                tuple(r.get(c) for c in columns) for r in right_rows
            )
            rows: list[dict] = []
            for row in left_rows:
                key = tuple(row.get(c) for c in columns)
                if right_counter[key] > 0:
                    right_counter[key] -= 1
                else:
                    rows.append(row)
            return rows

        right_keys = {tuple(r.get(c) for c in columns) for r in right_rows}
        seen: set[tuple] = set()
        rows = []
        for row in left_rows:
            key = tuple(row.get(c) for c in columns)
            if key not in right_keys and key not in seen:
                seen.add(key)
                rows.append(row)
        return rows

    # -- CTE materialization -------------------------------------------

    _MAX_RECURSIVE_DEPTH = 1000

    def _count_cte_refs(self, name: str, node: Any) -> int:
        """Count references to a CTE name in an AST tree."""
        if isinstance(node, RangeVar):
            return 1 if node.relname == name else 0
        count = 0
        if isinstance(node, tuple | list):
            for item in node:
                count += self._count_cte_refs(name, item)
            return count
        if hasattr(node, "__slots__") and isinstance(node.__slots__, dict):
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is not None:
                    count += self._count_cte_refs(name, val)
        return count

    def _materialize_ctes(
        self,
        ctes: tuple,
        *,
        recursive: bool = False,
        main_query: SelectStmt | None = None,
    ) -> list[str]:
        """Execute CTE queries and register results as temporary tables.

        When *recursive* is True (WITH RECURSIVE), CTEs whose query
        is a UNION/UNION ALL are executed via iterative fixpoint.

        Single-reference non-recursive CTEs are inlined as derived
        tables when the FROM clause is resolved, avoiding materialization.

        Returns the list of CTE names for cleanup after the main query.
        """
        cte_names: list[str] = []
        for cte in ctes:
            name = cte.ctename
            query = cte.ctequery

            is_recursive = (
                recursive
                and query.op is not None
                and query.op != SetOperation.SETOP_NONE
            )

            if is_recursive:
                self._materialize_recursive_cte(cte)
            else:
                # Inline single-reference non-recursive CTEs as derived
                # tables instead of materializing them.
                if (
                    main_query is not None
                    and self._count_cte_refs(name, main_query) == 1
                ):
                    self._inlined_ctes[name] = query
                else:
                    result = self._compile_select(query)
                    table = self._result_to_table(name, result)
                    self._engine._tables[name] = table
            cte_names.append(name)

        return cte_names

    def _materialize_recursive_cte(self, cte: Any) -> None:
        """Iterative fixpoint computation for recursive CTEs.

        1. Execute base case (larg) to seed the working table.
        2. Loop: execute recursive case (rarg) referencing the CTE,
           collect new rows.
        3. If UNION (not ALL): deduplicate against accumulated rows.
        4. Terminate when no new rows or depth limit reached.
        """
        name = cte.ctename
        query = cte.ctequery
        is_union_all = bool(query.all)

        # Column name mapping from alias
        alias_cols = [s.sval for s in cte.aliascolnames] if cte.aliascolnames else None

        # 1. Execute base case
        base_result = self._compile_select(query.larg)
        base_columns = base_result.columns

        # Remap columns if alias names are provided
        if alias_cols:
            all_rows = []
            for row in base_result.rows:
                remapped = {}
                for i, acol in enumerate(alias_cols):
                    if i < len(base_columns):
                        remapped[acol] = row.get(base_columns[i])
                all_rows.append(remapped)
            columns = alias_cols
        else:
            all_rows = list(base_result.rows)
            columns = base_columns

        # Track seen tuples for UNION deduplication
        seen: set[tuple] | None = None
        if not is_union_all:
            seen = set()
            deduped = []
            for row in all_rows:
                key = tuple(row.get(c) for c in columns)
                if key not in seen:
                    seen.add(key)
                    deduped.append(row)
            all_rows = deduped

        # Register working table
        working_rows = list(all_rows)

        for _depth in range(self._MAX_RECURSIVE_DEPTH):
            # Build temporary table from working rows
            result = SQLResult(columns, working_rows)
            table = self._result_to_table(name, result)
            self._engine._tables[name] = table

            # Execute recursive case
            rec_result = self._compile_select(query.rarg)

            # Remap recursive result columns to match base case columns.
            # alias_cols takes priority; otherwise remap positionally
            # to the base case column names (handles cases like
            # ``t.depth + 1`` producing ``?column?`` instead of ``depth``).
            target_cols = alias_cols or columns
            new_rows = []
            for row in rec_result.rows:
                remapped = {}
                for i, tcol in enumerate(target_cols):
                    if i < len(rec_result.columns):
                        remapped[tcol] = row.get(rec_result.columns[i])
                new_rows.append(remapped)

            if not new_rows:
                break

            # Deduplicate for UNION (not ALL)
            if seen is not None:
                filtered = []
                for row in new_rows:
                    key = tuple(row.get(c) for c in columns)
                    if key not in seen:
                        seen.add(key)
                        filtered.append(row)
                new_rows = filtered
                if not new_rows:
                    break

            all_rows.extend(new_rows)
            working_rows = new_rows

        # Final table with all accumulated rows
        result = SQLResult(columns, all_rows)
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table

    # -- View expansion ------------------------------------------------

    def _expand_view(
        self,
        view_name: str,
        query: SelectStmt,
        pushed_where: Any = None,
    ) -> tuple[Table, None]:
        """Materialize a view's stored query into a temporary table.

        The temporary table is registered in ``_engine._tables`` and
        tracked in ``_expanded_views`` for cleanup after the enclosing
        query completes.

        When *pushed_where* is provided, it is AND-merged into the
        subquery's WHERE clause before compilation (predicate pushdown).
        """
        if pushed_where is not None:
            query = self._inject_where(query, pushed_where)
        result = self._compile_select(query)
        table = self._result_to_table(view_name, result)
        self._engine._tables[view_name] = table
        self._expanded_views.append(view_name)
        return table, None

    # -- Derived table (subquery in FROM) ------------------------------

    def _materialize_derived_table(
        self, node: RangeSubselect, pushed_where: Any = None
    ) -> tuple[Table, None]:
        """Materialize a subquery in FROM as a temporary table."""
        alias = node.alias.aliasname if node.alias else "_derived"
        subquery = node.subquery
        if pushed_where is not None:
            subquery = self._inject_where(subquery, pushed_where)
        result = self._compile_select(subquery)
        table = self._result_to_table(alias, result)
        # Save the original table entry if the alias shadows a real table,
        # so it can be restored during cleanup.
        if alias in self._engine._tables:
            self._shadowed_tables[alias] = self._engine._tables[alias]
        self._engine._tables[alias] = table
        self._expanded_views.append(alias)
        return table, None

    def _try_predicate_pushdown(self, stmt: SelectStmt) -> SelectStmt:
        """Push safe WHERE predicates into a view or derived table subquery.

        Only applies when FROM is a single view or derived table and
        WHERE contains predicates that reference only the subquery's
        output columns (no aggregates, window functions, or subqueries).

        Returns the (possibly modified) statement with pushed predicates
        removed from the outer WHERE.
        """
        if stmt.whereClause is None or stmt.fromClause is None:
            return stmt
        if len(stmt.fromClause) != 1:
            return stmt

        from_node = stmt.fromClause[0]

        # Identify the subquery and its output columns.
        subquery: SelectStmt | None = None
        if isinstance(from_node, RangeVar):
            table_name = from_node.relname
            # Check if it's a view
            view_query = self._engine._views.get(table_name)
            if view_query is not None:
                subquery = view_query
            # Check if it's an inlined CTE
            elif table_name in self._inlined_ctes:
                subquery = self._inlined_ctes[table_name]
        elif isinstance(from_node, RangeSubselect):
            subquery = from_node.subquery

        if subquery is None:
            return stmt

        # Do not push predicates into subqueries that have aggregates,
        # window functions, GROUP BY, DISTINCT, or LIMIT -- pushing
        # changes the semantics of those operations.
        if subquery.groupClause is not None:
            return stmt
        if subquery.distinctClause:
            return stmt
        if subquery.limitCount is not None:
            return stmt
        if subquery.targetList and any(
            isinstance(t.val, FuncCall) and t.val.over is not None
            for t in subquery.targetList
        ):
            return stmt
        if subquery.targetList and self._has_aggregates(subquery.targetList):
            return stmt

        # Collect output column names from the subquery's target list.
        subquery_columns: set[str] = set()
        if subquery.targetList:
            for target in subquery.targetList:
                if target.name:
                    subquery_columns.add(target.name)
                elif isinstance(target.val, ColumnRef):
                    subquery_columns.add(
                        target.val.fields[-1].sval
                        if hasattr(target.val.fields[-1], "sval")
                        else str(target.val.fields[-1])
                    )
        if not subquery_columns:
            return stmt

        # Split WHERE into pushable and remaining predicates.
        pushable, remaining = self._split_pushable(stmt.whereClause, subquery_columns)
        if not pushable:
            return stmt

        # Inject pushable predicates into the subquery.
        pushed_pred = (
            pushable[0]
            if len(pushable) == 1
            else BoolExpr(boolop=BoolExprType.AND_EXPR, args=tuple(pushable))
        )

        if isinstance(from_node, RangeVar):
            view_query = self._engine._views.get(from_node.relname)
            if view_query is not None:
                self._engine._views[from_node.relname] = self._inject_where(
                    view_query, pushed_pred
                )
            elif from_node.relname in self._inlined_ctes:
                self._inlined_ctes[from_node.relname] = self._inject_where(
                    self._inlined_ctes[from_node.relname], pushed_pred
                )
        elif isinstance(from_node, RangeSubselect):
            new_subquery = self._inject_where(subquery, pushed_pred)
            # Reconstruct the RangeSubselect with the modified subquery
            kwargs = {}
            for slot in from_node.__slots__:
                kwargs[slot] = getattr(from_node, slot, None)
            kwargs["subquery"] = new_subquery
            new_from_node = RangeSubselect(**kwargs)
            # Reconstruct stmt with modified FROM and reduced WHERE
            stmt_kwargs = {}
            for slot in stmt.__slots__:
                stmt_kwargs[slot] = getattr(stmt, slot, None)
            stmt_kwargs["fromClause"] = (new_from_node,)
            stmt_kwargs["whereClause"] = remaining
            return SelectStmt(**stmt_kwargs)

        # Reconstruct stmt with reduced WHERE
        stmt_kwargs = {}
        for slot in stmt.__slots__:
            stmt_kwargs[slot] = getattr(stmt, slot, None)
        stmt_kwargs["whereClause"] = remaining
        return SelectStmt(**stmt_kwargs)

    def _split_pushable(
        self, where_node: Any, subquery_columns: set[str]
    ) -> tuple[list[Any], Any]:
        """Split a WHERE clause into pushable and remaining predicates.

        Returns (pushable_list, remaining_node) where remaining_node
        is None if all predicates were pushed.
        """
        if (
            isinstance(where_node, BoolExpr)
            and where_node.boolop == BoolExprType.AND_EXPR
        ):
            pushable: list[Any] = []
            remaining: list[Any] = []
            for arg in where_node.args:
                if self._is_pushable_predicate(arg, subquery_columns):
                    pushable.append(arg)
                else:
                    remaining.append(arg)
            remaining_node: Any = None
            if len(remaining) == 1:
                remaining_node = remaining[0]
            elif len(remaining) > 1:
                remaining_node = BoolExpr(
                    boolop=BoolExprType.AND_EXPR, args=tuple(remaining)
                )
            return pushable, remaining_node

        # Single predicate (not AND)
        if self._is_pushable_predicate(where_node, subquery_columns):
            return [where_node], None
        return [], where_node

    @staticmethod
    def _inject_where(query: SelectStmt, predicate: Any) -> SelectStmt:
        """Return a copy of *query* with *predicate* AND-merged into WHERE."""
        if query.whereClause is None:
            new_where = predicate
        else:
            new_where = BoolExpr(
                boolop=BoolExprType.AND_EXPR,
                args=(query.whereClause, predicate),
            )
        kwargs = {}
        for slot in query.__slots__:
            kwargs[slot] = getattr(query, slot, None)
        kwargs["whereClause"] = new_where
        return SelectStmt(**kwargs)

    @staticmethod
    def _is_pushable_predicate(node: Any, subquery_columns: set[str]) -> bool:
        """Check if a WHERE predicate is safe to push into a subquery.

        A predicate is pushable if it only references columns that exist
        in the subquery output and contains no aggregates, window functions,
        or subqueries.
        """
        if isinstance(node, ColumnRef):
            col = node.fields[-1].sval if hasattr(node.fields[-1], "sval") else None
            return col is not None and col in subquery_columns
        if isinstance(node, A_Const):
            return True
        if isinstance(node, FuncCall | SubLink):
            return False
        if isinstance(node, A_Expr):
            left_ok = SQLCompiler._is_pushable_predicate(node.lexpr, subquery_columns)
            right_ok = node.rexpr is None or SQLCompiler._is_pushable_predicate(
                node.rexpr, subquery_columns
            )
            return left_ok and right_ok
        if isinstance(node, BoolExpr):
            return all(
                SQLCompiler._is_pushable_predicate(arg, subquery_columns)
                for arg in node.args
            )
        if isinstance(node, NullTest):
            return SQLCompiler._is_pushable_predicate(node.arg, subquery_columns)
        return False

    def _result_to_table(self, name: str, result: SQLResult) -> Table:
        """Convert a SQLResult into a temporary in-memory Table.

        Transient tables (CTEs, views, derived tables, catalog views)
        are never text-searched, so inverted index building is skipped
        to avoid unnecessary overhead during query execution.
        """
        _type_map = {int: "integer", float: "real", str: "text"}
        col_defs: list[ColumnDef] = []
        for col_name in result.columns:
            py_type: type = str
            for row in result.rows:
                sample = row.get(col_name)
                if sample is not None:
                    if isinstance(sample, bool):
                        py_type = str  # bool before int (bool is subclass)
                    elif isinstance(sample, int):
                        py_type = int
                    elif isinstance(sample, float):
                        py_type = float
                    break
            col_defs.append(
                ColumnDef(
                    name=col_name,
                    type_name=_type_map.get(py_type, "text"),
                    python_type=py_type,
                )
            )

        table = Table(name=name, columns=col_defs)
        for i, row in enumerate(result.rows):
            doc_id = i + 1
            doc = {"_id": doc_id}
            doc.update(row)
            table.document_store.put(doc_id, doc)

        return table

    # -- information_schema virtual tables -----------------------------

    def _build_information_schema_table(
        self,
        view_name: str,
    ) -> tuple[Table, None]:
        """Build virtual information_schema tables from engine metadata."""
        if view_name == "tables":
            return self._build_info_schema_tables()
        if view_name == "columns":
            return self._build_info_schema_columns()
        raise ValueError(f"Unknown information_schema view: '{view_name}'")

    def _build_info_schema_tables(self) -> tuple[Table, None]:
        """Build information_schema.tables from engine state."""
        columns = [
            "table_catalog",
            "table_schema",
            "table_name",
            "table_type",
        ]
        rows: list[dict[str, Any]] = []
        for tname in sorted(self._engine._tables):
            rows.append(
                {
                    "table_catalog": "",
                    "table_schema": "public",
                    "table_name": tname,
                    "table_type": "BASE TABLE",
                }
            )
        for ftname in sorted(self._engine._foreign_tables):
            rows.append(
                {
                    "table_catalog": "",
                    "table_schema": "public",
                    "table_name": ftname,
                    "table_type": "FOREIGN TABLE",
                }
            )
        for vname in sorted(self._engine._views):
            rows.append(
                {
                    "table_catalog": "",
                    "table_schema": "public",
                    "table_name": vname,
                    "table_type": "VIEW",
                }
            )
        result = SQLResult(columns, rows)
        name = "_info_schema_tables"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    _INFO_TYPE_DISPLAY: dict[str, str] = {
        "int2": "smallint",
        "int4": "integer",
        "int8": "bigint",
        "float4": "real",
        "float8": "double precision",
        "bool": "boolean",
    }

    def _build_info_schema_columns(self) -> tuple[Table, None]:
        """Build information_schema.columns from engine state."""
        columns = [
            "table_catalog",
            "table_schema",
            "table_name",
            "column_name",
            "ordinal_position",
            "data_type",
            "is_nullable",
        ]
        rows: list[dict[str, Any]] = []
        for tname in sorted(self._engine._tables):
            tbl = self._engine._tables[tname]
            for pos, (cname, cdef) in enumerate(tbl.columns.items(), start=1):
                display_type = self._INFO_TYPE_DISPLAY.get(
                    cdef.type_name, cdef.type_name
                )
                rows.append(
                    {
                        "table_catalog": "",
                        "table_schema": "public",
                        "table_name": tname,
                        "column_name": cname,
                        "ordinal_position": pos,
                        "data_type": display_type,
                        "is_nullable": "NO" if cdef.not_null else "YES",
                    }
                )
        result = SQLResult(columns, rows)
        name = "_info_schema_columns"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    # -- pg_catalog virtual tables --------------------------------------

    def _build_pg_catalog_table(
        self,
        view_name: str,
    ) -> tuple[Table, None]:
        """Build virtual pg_catalog tables from engine metadata."""
        if view_name == "pg_tables":
            return self._build_pg_tables()
        if view_name == "pg_views":
            return self._build_pg_views()
        if view_name == "pg_indexes":
            return self._build_pg_indexes()
        if view_name == "pg_type":
            return self._build_pg_type()
        raise ValueError(f"Unknown pg_catalog view: '{view_name}'")

    def _build_pg_tables(self) -> tuple[Table, None]:
        """Build pg_catalog.pg_tables from engine state."""
        columns = ["schemaname", "tablename", "tableowner", "tablespace"]
        rows: list[dict[str, Any]] = []
        for tname in sorted(self._engine._tables):
            rows.append(
                {
                    "schemaname": "public",
                    "tablename": tname,
                    "tableowner": "",
                    "tablespace": "",
                }
            )
        result = SQLResult(columns, rows)
        name = "_pg_tables"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    def _build_pg_views(self) -> tuple[Table, None]:
        """Build pg_catalog.pg_views from engine state."""
        columns = ["schemaname", "viewname", "viewowner", "definition"]
        rows: list[dict[str, Any]] = []
        for vname in sorted(self._engine._views):
            rows.append(
                {
                    "schemaname": "public",
                    "viewname": vname,
                    "viewowner": "",
                    "definition": "",
                }
            )
        result = SQLResult(columns, rows)
        name = "_pg_views"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    def _build_pg_indexes(self) -> tuple[Table, None]:
        """Build pg_catalog.pg_indexes from engine state."""
        columns = ["schemaname", "tablename", "indexname", "tablespace", "indexdef"]
        rows: list[dict[str, Any]] = []
        index_manager = getattr(self._engine, "_index_manager", None)
        if index_manager is not None:
            for idx in index_manager._indexes.values():
                idx_def = idx.index_def
                rows.append(
                    {
                        "schemaname": "public",
                        "tablename": idx_def.table_name,
                        "indexname": idx_def.name,
                        "tablespace": "",
                        "indexdef": (
                            f"CREATE INDEX {idx_def.name} ON "
                            f"{idx_def.table_name} "
                            f"({', '.join(idx_def.columns)})"
                        ),
                    }
                )
        result = SQLResult(columns, rows)
        name = "_pg_indexes"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    def _build_pg_type(self) -> tuple[Table, None]:
        """Build pg_catalog.pg_type with UQA-supported types."""
        columns = [
            "oid",
            "typname",
            "typnamespace",
            "typlen",
            "typtype",
            "typcategory",
        ]
        # PostgreSQL-compatible OIDs for supported types
        type_entries = [
            (16, "boolean", 11, 1, "b", "B"),
            (17, "bytea", 11, -1, "b", "U"),
            (20, "bigint", 11, 8, "b", "N"),
            (21, "smallint", 11, 2, "b", "N"),
            (23, "integer", 11, 4, "b", "N"),
            (25, "text", 11, -1, "b", "S"),
            (114, "json", 11, -1, "b", "U"),
            (142, "xml", 11, -1, "b", "U"),
            (700, "real", 11, 4, "b", "N"),
            (701, "float8", 11, 8, "b", "N"),
            (1043, "varchar", 11, -1, "b", "S"),
            (1082, "date", 11, 4, "b", "D"),
            (1083, "time", 11, 8, "b", "D"),
            (1114, "timestamp", 11, 8, "b", "D"),
            (1184, "timestamptz", 11, 8, "b", "D"),
            (1186, "interval", 11, 16, "b", "T"),
            (1700, "numeric", 11, -1, "b", "N"),
            (2950, "uuid", 11, 16, "b", "U"),
            (3802, "jsonb", 11, -1, "b", "U"),
            (16385, "vector", 11, -1, "b", "U"),
        ]
        rows: list[dict[str, Any]] = []
        for oid, typname, ns, typlen, typtype, typcat in type_entries:
            rows.append(
                {
                    "oid": oid,
                    "typname": typname,
                    "typnamespace": ns,
                    "typlen": typlen,
                    "typtype": typtype,
                    "typcategory": typcat,
                }
            )
        result = SQLResult(columns, rows)
        name = "_pg_type"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    # -- FROM clause ---------------------------------------------------

    def _resolve_from(
        self,
        from_clause: tuple | None,
        where_clause: Any = None,
    ) -> tuple[Table | None, Any]:
        """Resolve FROM clause to (table, source_operator).

        Returns (table, None) for ``FROM table_name`` and
        (None, operator) for ``FROM func(...)``.

        Multiple FROM sources (``FROM a, b, c``) are treated as
        implicit CROSS JOINs.  When equijoin predicates are available
        in *where_clause*, the join order is optimized using DPccp.
        """
        if from_clause is None:
            return None, None

        if len(from_clause) == 1:
            table, op, _alias = self._resolve_from_single(from_clause[0])
            return table, op

        # Multiple FROM sources: try DPccp join reordering when there
        # are 3+ base relations and equijoin predicates in WHERE.
        has_lateral = any(
            isinstance(node, RangeSubselect) and node.lateral for node in from_clause
        )
        if not has_lateral and len(from_clause) >= 3 and where_clause is not None:
            result = self._try_implicit_join_reorder(from_clause, where_clause)
            if result is not None:
                return result

        # Fallback: left-deep cross join chain
        from uqa.joins.cross import CrossJoinOperator

        table, op, alias = self._resolve_from_single(from_clause[0])
        if op is None:
            op = _TableScanOperator(table, alias=alias)

        for node in from_clause[1:]:
            # LATERAL subquery: re-evaluate per left row
            if isinstance(node, RangeSubselect) and node.lateral:
                lateral_alias = node.alias.aliasname if node.alias else "_lateral"
                op = _LateralJoinOperator(op, node.subquery, lateral_alias, self)
                continue

            right_table, right_op, right_alias = self._resolve_from_single(node)
            if right_op is None:
                right_op = _TableScanOperator(right_table, alias=right_alias)
            op = CrossJoinOperator(op, right_op)
            # Keep first resolved table as context source
            if table is None:
                table = right_table

        return table, op

    def _try_implicit_join_reorder(
        self,
        from_clause: tuple,
        where_clause: Any,
    ) -> tuple[Table | None, Any] | None:
        """Attempt DPccp join reordering for implicit cross joins.

        Extracts equijoin predicates from the WHERE clause and uses
        DPccp to find an optimal join order.  Returns None if there
        are no equijoin predicates (pure cross join).
        """
        # Resolve each FROM item to get relations metadata.
        relations: list[dict[str, Any]] = []
        for node in from_clause:
            table, op, alias = self._resolve_from_single(node)
            if op is None and table is not None:
                op = _TableScanOperator(table, alias=alias)
            elif op is None:
                op = _ScanOperator()

            cardinality = 1000.0
            column_stats: dict[str, Any] = {}
            if table is not None:
                cardinality = float(len(table.document_store.doc_ids)) or 1.0
                column_stats = dict(table._stats)

            relations.append(
                {
                    "alias": alias,
                    "operator": op,
                    "table": table,
                    "cardinality": cardinality,
                    "column_stats": column_stats,
                }
            )

        # Extract equijoin predicates from the WHERE clause.
        alias_set = {r["alias"] for r in relations}
        predicates = self._extract_implicit_equijoin_predicates(
            where_clause, alias_set, relations
        )
        if not predicates:
            return None

        from uqa.planner.join_order import JoinOrderOptimizer

        optimizer = JoinOrderOptimizer()
        operator, table = optimizer.optimize(relations, predicates)
        return table, operator

    def _extract_implicit_equijoin_predicates(
        self,
        where_node: Any,
        alias_set: set[str],
        relations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract equijoin predicates from WHERE for implicit cross joins."""
        predicates: list[dict[str, Any]] = []
        conjuncts = (
            list(where_node.args)
            if isinstance(where_node, BoolExpr)
            and where_node.boolop == BoolExprType.AND_EXPR
            else [where_node]
        )

        for node in conjuncts:
            if not isinstance(node, A_Expr):
                continue
            if A_Expr_Kind(node.kind) != A_Expr_Kind.AEXPR_OP:
                continue
            op_name = node.name[0].sval if node.name else None
            if op_name != "=":
                continue
            if not isinstance(node.lexpr, ColumnRef) or not isinstance(
                node.rexpr, ColumnRef
            ):
                continue

            left_fields = node.lexpr.fields
            right_fields = node.rexpr.fields

            # Both sides must be qualified (table.column)
            if (
                len(left_fields) < 2
                or len(right_fields) < 2
                or not hasattr(left_fields[0], "sval")
                or not hasattr(right_fields[0], "sval")
            ):
                continue

            left_alias = left_fields[0].sval
            left_col = left_fields[-1].sval
            right_alias = right_fields[0].sval
            right_col = right_fields[-1].sval

            if left_alias not in alias_set or right_alias not in alias_set:
                continue

            predicates.append(
                {
                    "left_alias": left_alias,
                    "right_alias": right_alias,
                    "left_field": left_col,
                    "right_field": right_col,
                }
            )

        return predicates

    def _resolve_from_single(self, node: Any) -> tuple[Table | None, Any, str | None]:
        """Resolve a single FROM clause item.

        Returns ``(table, operator, alias)`` where *alias* is the
        table alias (e.g. ``e`` in ``FROM employees e``) or the table
        name itself when no alias is specified.
        """
        if isinstance(node, RangeVar):
            alias = node.alias.aliasname if node.alias is not None else node.relname
            # Virtual schema tables
            if node.schemaname == "information_schema":
                tbl, op = self._build_information_schema_table(node.relname)
                return tbl, op, alias
            if node.schemaname == "pg_catalog":
                tbl, op = self._build_pg_catalog_table(node.relname)
                return tbl, op, alias
            table_name = node.relname
            table = self._engine._tables.get(table_name)
            if table is None:
                # Inline CTE: compile on demand instead of materializing
                inlined_query = self._inlined_ctes.pop(table_name, None)
                if inlined_query is not None:
                    result = self._compile_select(inlined_query)
                    table = self._result_to_table(table_name, result)
                    self._engine._tables[table_name] = table
                    self._expanded_views.append(table_name)
                    return table, None, alias
                # Check foreign tables
                ft = self._engine._foreign_tables.get(table_name)
                if ft is not None:
                    op = _ForeignTableScanOperator(
                        ft,
                        self._engine,
                        alias=alias,
                    )
                    proxy_table = Table(
                        table_name,
                        list(ft.columns.values()),
                    )
                    return proxy_table, op, alias
                view_query = self._engine._views.get(table_name)
                if view_query is not None:
                    tbl, op = self._expand_view(table_name, view_query)
                    return tbl, op, alias
                raise ValueError(f"Table '{table_name}' does not exist")
            return table, None, alias

        if isinstance(node, RangeFunction):
            tbl, op = self._compile_from_function(node)
            return tbl, op, None

        if isinstance(node, JoinExpr):
            tbl, op = self._resolve_join(node)
            return tbl, op, None

        if isinstance(node, RangeSubselect):
            tbl, op = self._materialize_derived_table(node)
            alias = node.alias.aliasname if node.alias else None
            return tbl, op, alias

        raise ValueError(f"Unsupported FROM clause: {type(node).__name__}")

    def _context_for_table(self, table: Table | None) -> ExecutionContext:
        """Build an ExecutionContext scoped to a specific table.

        When *table* is ``None`` (e.g. ``SELECT 1`` with no FROM clause)
        a minimal context with no storage is returned.
        """
        from uqa.operators.base import ExecutionContext

        index_manager = getattr(self._engine, "_index_manager", None)
        parallel_executor = getattr(self._engine, "_parallel_executor", None)

        if table is None:
            return ExecutionContext(
                index_manager=index_manager,
                parallel_executor=parallel_executor,
            )

        return ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
            vector_indexes=table.vector_indexes,
            spatial_indexes=table.spatial_indexes,
            graph_store=table.graph_store,
            block_max_index=table.block_max_index,
            index_manager=index_manager,
            parallel_executor=parallel_executor,
        )

    def _compile_from_function(self, node: RangeFunction) -> tuple[Table | None, Any]:
        """Return (table_or_none, operator) for a FROM-clause function."""
        func_call = node.functions[0][0]
        if not isinstance(func_call, FuncCall):
            raise ValueError(f"Expected FuncCall in FROM, got {type(func_call)}")
        name = func_call.funcname[-1].sval.lower()
        args = func_call.args or ()

        if name == "cypher":
            return self._build_cypher_from(node, args)
        if name == "create_graph":
            return self._build_create_graph(args)
        if name == "drop_graph":
            return self._build_drop_graph(args)
        if name == "traverse":
            return self._build_traverse_from(args)
        if name == "temporal_traverse":
            return self._build_temporal_traverse_from(args)
        if name == "rpq":
            return self._build_rpq_from(args)
        if name == "pagerank":
            return self._build_centrality_from(args, "pagerank")
        if name == "hits":
            return self._build_centrality_from(args, "hits")
        if name == "betweenness":
            return self._build_centrality_from(args, "betweenness")
        if name == "text_search":
            return self._build_text_search_from(args)
        if name == "generate_series":
            return self._build_generate_series(node, args)
        if name == "unnest":
            return self._build_unnest(node, args)
        if name in ("json_each", "jsonb_each", "json_each_text", "jsonb_each_text"):
            return self._build_json_each(node, args, as_text=name.endswith("_text"))
        if name in (
            "json_array_elements",
            "jsonb_array_elements",
            "json_array_elements_text",
            "jsonb_array_elements_text",
        ):
            return self._build_json_array_elements(
                node, args, as_text=name.endswith("_text")
            )
        if name == "regexp_split_to_table":
            return self._build_regexp_split_to_table(node, args)
        if name == "create_analyzer":
            return self._build_create_analyzer(args)
        if name == "drop_analyzer":
            return self._build_drop_analyzer(args)
        if name == "list_analyzers":
            return self._build_list_analyzers()
        if name == "set_table_analyzer":
            return self._build_set_table_analyzer(args)
        if name == "graph_add_vertex":
            return self._build_graph_add_vertex(args)
        if name == "graph_add_edge":
            return self._build_graph_add_edge(args)
        raise ValueError(f"Unknown table function: {name}")

    @staticmethod
    def _is_graph_operator(op: Any) -> bool:
        """Return True if op is a graph traversal, RPQ, centrality, or Cypher operator."""
        if op is None:
            return False
        from uqa.graph.centrality import (
            BetweennessCentralityOperator,
            HITSOperator,
            PageRankOperator,
        )
        from uqa.graph.operators import (
            CypherQueryOperator,
            RegularPathQueryOperator,
            TraverseOperator,
            WeightedPathQueryOperator,
        )
        from uqa.graph.temporal_traverse import TemporalTraverseOperator

        return isinstance(
            op,
            TraverseOperator
            | RegularPathQueryOperator
            | CypherQueryOperator
            | TemporalTraverseOperator
            | PageRankOperator
            | HITSOperator
            | BetweennessCentralityOperator
            | WeightedPathQueryOperator,
        )

    @staticmethod
    def _is_join_operator(op: Any) -> bool:
        """Return True if op is a join operator (cross, inner, outer, expr)."""
        if op is None:
            return False
        from uqa.joins.base import JoinOperator
        from uqa.joins.cross import CrossJoinOperator

        return isinstance(
            op,
            JoinOperator | CrossJoinOperator | _ExprJoinOperator | _LateralJoinOperator,
        )

    def _collect_join_tables(
        self, from_clause: tuple | None
    ) -> list[tuple[str, list[str]]]:
        """Collect (alias, column_names) for all tables in a FROM clause.

        Walks JoinExpr/RangeVar nodes in left-to-right order, matching
        PostgreSQL's ``SELECT *`` column expansion order.
        """
        if from_clause is None:
            return []
        result: list[tuple[str, list[str]]] = []
        for node in from_clause:
            self._walk_from_for_tables(node, result)
        return result

    def _walk_from_for_tables(
        self, node: Any, out: list[tuple[str, list[str]]]
    ) -> None:
        """Recursively collect tables from a FROM clause node."""
        if isinstance(node, RangeVar):
            alias = node.alias.aliasname if node.alias is not None else node.relname
            table = self._engine._tables.get(node.relname)
            if table is not None and table.columns:
                cols = list(table.columns.keys())
            else:
                cols = []
            out.append((alias, cols))
        elif isinstance(node, JoinExpr):
            self._walk_from_for_tables(node.larg, out)
            self._walk_from_for_tables(node.rarg, out)
        elif isinstance(node, RangeSubselect):
            alias = node.alias.aliasname if node.alias else "_subquery"
            out.append((alias, []))

    def _build_traverse_from(self, args: tuple) -> tuple[Table | None, Any]:
        """Build traverse() FROM-clause.

        Per-table graph:
            traverse(start, 'label', hops[, 'table'])
        Named graph:
            traverse(start, 'label', hops, 'graph:name')
        """
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        op = TraverseOperator(start, label, max_hops)

        if len(args) > 3:
            source_name = self._extract_string_value(args[3])
            if source_name.startswith("graph:"):
                graph_store = self._engine.get_graph(source_name[6:])
                return None, _NamedGraphOperatorWrapper(op, graph_store)
            table = self._engine._tables.get(source_name)
            if table is None:
                raise ValueError(f"Table '{source_name}' does not exist")
            return table, op

        if not self._engine._tables:
            raise ValueError("traverse() requires a table or graph argument")
        table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table, op

    def _build_temporal_traverse_from(self, args: tuple) -> tuple[Table | None, Any]:
        """Build temporal_traverse() FROM-clause.

        Per-table graph:
            temporal_traverse(start, 'label', hops, timestamp[, 'table'])
            temporal_traverse(start, 'label', hops, from_ts, to_ts[, 'table'])

        Named graph:
            temporal_traverse(start, 'label', hops, timestamp, 'graph:name')
            temporal_traverse(start, 'label', hops, from_ts, to_ts, 'graph:name')
        """
        from uqa.graph.temporal_filter import TemporalFilter
        from uqa.graph.temporal_traverse import TemporalTraverseOperator

        if len(args) < 4:
            raise ValueError(
                "temporal_traverse() requires at least 4 arguments: "
                "temporal_traverse(start, label, hops, timestamp)"
            )
        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1

        # Determine temporal filter and optional table/graph name.
        source_name: str | None = None
        tf: TemporalFilter

        if len(args) == 4:
            ts = float(self._extract_const_value(args[3]))
            tf = TemporalFilter(timestamp=ts)
        elif len(args) == 5:
            arg4 = args[4]
            if self._is_string_const(arg4):
                ts = float(self._extract_const_value(args[3]))
                tf = TemporalFilter(timestamp=ts)
                source_name = self._extract_string_value(arg4)
            else:
                from_ts = float(self._extract_const_value(args[3]))
                to_ts = float(self._extract_const_value(args[4]))
                tf = TemporalFilter(time_range=(from_ts, to_ts))
        elif len(args) >= 6:
            from_ts = float(self._extract_const_value(args[3]))
            to_ts = float(self._extract_const_value(args[4]))
            tf = TemporalFilter(time_range=(from_ts, to_ts))
            source_name = self._extract_string_value(args[5])
        else:
            tf = TemporalFilter()

        op = TemporalTraverseOperator(start, label, max_hops, tf)

        # Named graph: "graph:name" prefix
        if source_name is not None and source_name.startswith("graph:"):
            graph_name = source_name[6:]
            graph_store = self._engine.get_graph(graph_name)
            return None, _NamedGraphOperatorWrapper(op, graph_store)

        # Per-table graph
        table_name = source_name
        if table_name is None:
            if not self._engine._tables:
                raise ValueError(
                    "temporal_traverse() requires a table or graph argument"
                )
            table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table, op

    @staticmethod
    def _is_string_const(node: Any) -> bool:
        """Return True if node is a string constant (A_Const with PgString)."""
        return isinstance(node, A_Const) and isinstance(node.val, PgString)

    def _build_rpq_from(self, args: tuple) -> tuple[Table | None, Any]:
        """Build rpq() FROM-clause.

        Per-table graph:
            rpq('expr', start[, 'table'])
        Named graph:
            rpq('expr', start, 'graph:name')
        """
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import parse_rpq

        expr = self._extract_string_value(args[0])
        start = self._extract_int_value(args[1]) if len(args) > 1 else None
        op = RegularPathQueryOperator(parse_rpq(expr), start_vertex=start)

        if len(args) > 2:
            source_name = self._extract_string_value(args[2])
            if source_name.startswith("graph:"):
                graph_store = self._engine.get_graph(source_name[6:])
                return None, _NamedGraphOperatorWrapper(op, graph_store)
            table = self._engine._tables.get(source_name)
            if table is None:
                raise ValueError(f"Table '{source_name}' does not exist")
            return table, op

        if not self._engine._tables:
            raise ValueError("rpq() requires a table or graph argument")
        table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table, op

    def _build_centrality_from(
        self, args: tuple, kind: str
    ) -> tuple[Table | None, Any]:
        """Build centrality FROM-clause: pagerank(), hits(), betweenness().

        pagerank([damping[, max_iter[, tol[, 'table']]]])
        hits([max_iter[, tol[, 'table']]])
        betweenness(['table'])
        """
        from uqa.graph.centrality import (
            BetweennessCentralityOperator,
            HITSOperator,
            PageRankOperator,
        )

        table_name_arg = None

        # Check if the last (or only) arg is a string table/graph source
        def _is_source_arg(a: object) -> bool:
            try:
                val = self._extract_const_value(a)
                return isinstance(val, str)
            except (ValueError, TypeError, AttributeError):
                return False

        if kind == "pagerank":
            # pagerank([damping[, max_iter[, tol]]][, 'source'])
            numeric_args = [a for a in args if not _is_source_arg(a)]
            source_args = [a for a in args if _is_source_arg(a)]
            damping = float(self._extract_const_value(numeric_args[0])) if len(numeric_args) > 0 else 0.85
            max_iter = self._extract_int_value(numeric_args[1]) if len(numeric_args) > 1 else 100
            tol = float(self._extract_const_value(numeric_args[2])) if len(numeric_args) > 2 else 1e-6
            if source_args:
                table_name_arg = self._extract_string_value(source_args[0])
            op = PageRankOperator(damping=damping, max_iterations=max_iter, tolerance=tol)
        elif kind == "hits":
            # hits([max_iter[, tol]][, 'source'])
            numeric_args = [a for a in args if not _is_source_arg(a)]
            source_args = [a for a in args if _is_source_arg(a)]
            max_iter = self._extract_int_value(numeric_args[0]) if len(numeric_args) > 0 else 100
            tol = float(self._extract_const_value(numeric_args[1])) if len(numeric_args) > 1 else 1e-6
            if source_args:
                table_name_arg = self._extract_string_value(source_args[0])
            op = HITSOperator(max_iterations=max_iter, tolerance=tol)
        else:
            # betweenness(['source'])
            if len(args) > 0:
                table_name_arg = self._extract_string_value(args[0])
            op = BetweennessCentralityOperator()

        if table_name_arg is not None:
            if table_name_arg.startswith("graph:"):
                graph_store = self._engine.get_graph(table_name_arg[6:])
                return None, _NamedGraphOperatorWrapper(op, graph_store)
            table = self._engine._tables.get(table_name_arg)
            if table is None:
                raise ValueError(f"Table '{table_name_arg}' does not exist")
            return table, op

        if not self._engine._tables:
            raise ValueError(f"{kind}() requires a table argument")
        first_table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(first_table_name)
        if table is None:
            raise ValueError(f"Table '{first_table_name}' does not exist")
        return table, op

    def _build_create_graph(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM create_graph('name')``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("create_graph() requires a graph name argument")
        name = self._extract_string_value(args[0])
        self._engine.create_graph(name)
        # Return a single-row result like AGE
        table = Table(
            "_create_graph",
            [
                SQLColumnDef(name="create_graph", type_name="text", python_type=str),
            ],
        )
        table.insert({"create_graph": f"graph '{name}' created"})
        self._engine._tables["_create_graph"] = table
        self._expanded_views.append("_create_graph")
        return table, None

    def _build_drop_graph(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM drop_graph('name')`` or ``drop_graph('name', true)``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("drop_graph() requires a graph name argument")
        name = self._extract_string_value(args[0])
        self._engine.drop_graph(name)
        table = Table(
            "_drop_graph",
            [
                SQLColumnDef(name="drop_graph", type_name="text", python_type=str),
            ],
        )
        table.insert({"drop_graph": f"graph '{name}' dropped"})
        self._engine._tables["_drop_graph"] = table
        self._expanded_views.append("_drop_graph")
        return table, None

    def _build_create_analyzer(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM create_analyzer('name', 'config_json')``.

        ``config_json`` is a JSON string with keys: tokenizer,
        token_filters, char_filters -- matching ``Analyzer.to_dict()``.
        """
        import json as json_mod

        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 2:
            raise ValueError("create_analyzer() requires (name, config_json)")
        name = self._extract_string_value(args[0])
        config_str = self._extract_string_value(args[1])
        config = json_mod.loads(config_str)
        self._engine.create_analyzer(name, config)
        table = Table(
            "_create_analyzer",
            [
                SQLColumnDef(name="create_analyzer", type_name="text", python_type=str),
            ],
        )
        table.insert({"create_analyzer": f"analyzer '{name}' created"})
        self._engine._tables["_create_analyzer"] = table
        self._expanded_views.append("_create_analyzer")
        return table, None

    def _build_drop_analyzer(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM drop_analyzer('name')``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("drop_analyzer() requires a name argument")
        name = self._extract_string_value(args[0])
        self._engine.drop_analyzer(name)
        table = Table(
            "_drop_analyzer",
            [
                SQLColumnDef(name="drop_analyzer", type_name="text", python_type=str),
            ],
        )
        table.insert({"drop_analyzer": f"analyzer '{name}' dropped"})
        self._engine._tables["_drop_analyzer"] = table
        self._expanded_views.append("_drop_analyzer")
        return table, None

    def _build_list_analyzers(self) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM list_analyzers()``."""
        from uqa.analysis.analyzer import list_analyzers
        from uqa.sql.table import ColumnDef as SQLColumnDef

        names = list_analyzers()
        table = Table(
            "_list_analyzers",
            [
                SQLColumnDef(name="analyzer_name", type_name="text", python_type=str),
            ],
        )
        for n in names:
            table.insert({"analyzer_name": n})
        self._engine._tables["_list_analyzers"] = table
        self._expanded_views.append("_list_analyzers")
        return table, None

    def _build_set_table_analyzer(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM set_table_analyzer('table', 'field', 'name'[, 'phase'])``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 3:
            raise ValueError(
                "set_table_analyzer() requires (table, field, analyzer_name[, phase])"
            )
        table_name = self._extract_string_value(args[0])
        field = self._extract_string_value(args[1])
        analyzer_name = self._extract_string_value(args[2])
        phase = self._extract_string_value(args[3]) if len(args) > 3 else "both"
        self._engine.set_table_analyzer(table_name, field, analyzer_name, phase=phase)
        table = Table(
            "_set_table_analyzer",
            [
                SQLColumnDef(
                    name="set_table_analyzer",
                    type_name="text",
                    python_type=str,
                ),
            ],
        )
        msg = f"analyzer '{analyzer_name}' assigned to {table_name}.{field}"
        if phase != "both":
            msg += f" (phase={phase})"
        table.insert({"set_table_analyzer": msg})
        self._engine._tables["_set_table_analyzer"] = table
        self._expanded_views.append("_set_table_analyzer")
        return table, None

    def _build_graph_add_vertex(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM graph_add_vertex(id, 'label', 'table'[, 'key=val,...'])``.

        Adds a graph vertex to a table's graph store via SQL.
        """
        from uqa.core.types import Vertex
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 3:
            raise ValueError(
                "graph_add_vertex(id, 'label', 'table'[, 'key=val,...'])"
            )
        vid = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1])
        table_name = self._extract_string_value(args[2])

        props: dict[str, object] = {}
        if len(args) > 3:
            props_str = self._extract_string_value(args[3])
            for pair in props_str.split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        props[k] = int(v)
                    except ValueError:
                        try:
                            props[k] = float(v)
                        except ValueError:
                            props[k] = v

        self._engine.add_graph_vertex(Vertex(vid, label, props), table=table_name)

        result_table = Table(
            "_graph_add_vertex",
            [SQLColumnDef(name="result", type_name="text", python_type=str)],
        )
        result_table.insert({"result": f"vertex {vid} added to {table_name}"})
        self._engine._tables["_graph_add_vertex"] = result_table
        self._expanded_views.append("_graph_add_vertex")
        return result_table, None

    def _build_graph_add_edge(self, args: tuple) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM graph_add_edge(eid, src, tgt, 'label', 'table'[, 'key=val,...'])``.

        Adds a graph edge to a table's graph store via SQL.
        """
        from uqa.core.types import Edge
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 5:
            raise ValueError(
                "graph_add_edge(eid, src, tgt, 'label', 'table'[, 'key=val,...'])"
            )
        eid = self._extract_int_value(args[0])
        src = self._extract_int_value(args[1])
        tgt = self._extract_int_value(args[2])
        label = self._extract_string_value(args[3])
        table_name = self._extract_string_value(args[4])

        props: dict[str, object] = {}
        if len(args) > 5:
            props_str = self._extract_string_value(args[5])
            for pair in props_str.split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        props[k] = int(v)
                    except ValueError:
                        try:
                            props[k] = float(v)
                        except ValueError:
                            props[k] = v

        self._engine.add_graph_edge(
            Edge(eid, src, tgt, label, props), table=table_name
        )

        result_table = Table(
            "_graph_add_edge",
            [SQLColumnDef(name="result", type_name="text", python_type=str)],
        )
        result_table.insert(
            {"result": f"edge {eid} ({src}->{tgt} '{label}') added to {table_name}"}
        )
        self._engine._tables["_graph_add_edge"] = result_table
        self._expanded_views.append("_graph_add_edge")
        return result_table, None

    def _build_cypher_from(
        self, node: RangeFunction, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build cypher() FROM-clause (Apache AGE compatible).

        Usage::

            SELECT * FROM cypher('graph_name', $$
                MATCH (n:Person) RETURN n.name, n.age
            $$) AS (name agtype, age agtype)

        Returns a CypherQueryOperator that integrates into the operator
        tree.  The operator produces a GraphPostingList with projected
        fields, which PostingListScanOp reads via payload.fields.
        """
        from uqa.graph.cypher.parser import parse_cypher
        from uqa.graph.operators import CypherQueryOperator

        if len(args) < 2:
            raise ValueError(
                "cypher() requires 2 arguments: cypher('graph_name', $$ query $$)"
            )
        graph_name = self._extract_string_value(args[0])
        cypher_source = self._extract_string_value(args[1])

        graph = self._engine.get_graph(graph_name)
        ast = parse_cypher(cypher_source)

        # Determine column names from AS clause.
        # pglast puts ``AS t(name agtype, age agtype)`` column defs in
        # ``node.coldeflist`` (ColumnDef.colname), not alias.colnames.
        col_names: list[str] | None = None
        if node.coldeflist:
            col_names = [cd.colname for cd in node.coldeflist]
        elif node.alias is not None and node.alias.colnames:
            col_names = [c.sval for c in node.alias.colnames]

        op = CypherQueryOperator(
            graph,
            ast,
            params=self._cypher_params(),
            col_names=col_names,
        )
        return None, op

    def _cypher_params(self) -> dict[str, Any]:
        """Convert SQL positional params ($1, $2) to Cypher named params."""
        result: dict[str, Any] = {}
        for i, val in enumerate(self._params, 1):
            result[str(i)] = val
        return result

    def _build_text_search_from(self, args: tuple) -> tuple[Table | None, Any]:
        """Build a text_search FROM-clause: text_search('query', 'field'[, 'table'])."""
        from uqa.operators.boolean import UnionOperator
        from uqa.operators.primitive import ScoreOperator, TermOperator
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
        analyzer = (
            ctx.inverted_index.get_search_analyzer(field_name)
            if field_name
            else ctx.inverted_index.analyzer
        )
        terms = analyzer.analyze(query)
        term_ops = [TermOperator(t, field_name) for t in terms]
        retrieval = term_ops[0] if len(term_ops) == 1 else UnionOperator(term_ops)
        scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        op = ScoreOperator(scorer, retrieval, terms, field=field_name)
        return table, op

    def _build_generate_series(
        self, node: RangeFunction, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build generate_series(start, stop [, step]) as a table function."""
        if len(args) < 2:
            raise ValueError("generate_series requires at least 2 arguments")
        start = self._extract_const_value(args[0])
        stop = self._extract_const_value(args[1])
        step = self._extract_const_value(args[2]) if len(args) > 2 else 1

        if not isinstance(start, int | float):
            raise ValueError("generate_series currently supports numeric ranges")
        if step == 0:
            raise ValueError("generate_series step cannot be zero")

        values: list[int | float] = []
        current = start
        if step > 0:
            while current <= stop:
                values.append(current)
                current += step
        else:
            while current >= stop:
                values.append(current)
                current += step

        # Determine column name from alias (AS t(n)) or default
        col_name = "generate_series"
        if node.alias is not None:
            if node.alias.colnames:
                col_name = node.alias.colnames[0].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "generate_series"

        from uqa.sql.table import ColumnDef as SQLColumnDef

        col_type = "integer" if all(isinstance(v, int) for v in values) else "real"
        python_type = int if col_type == "integer" else float
        col = SQLColumnDef(
            name=col_name,
            type_name=col_type,
            python_type=python_type,
        )
        table = Table(alias_name, [col])
        for _i, val in enumerate(values, 1):
            table.insert({col_name: val})

        self._engine._tables[alias_name] = table
        self._expanded_views.append(alias_name)
        return table, None

    def _build_unnest(
        self, node: RangeFunction, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build unnest(array) as a table function."""
        from uqa.sql.expr_evaluator import ExprEvaluator
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("unnest requires at least 1 argument")

        evaluator = ExprEvaluator()
        arr = evaluator.evaluate(args[0], {})
        if not isinstance(arr, list):
            arr = [arr]

        # Determine column name from alias
        col_name = "unnest"
        if node.alias is not None:
            if node.alias.colnames:
                col_name = node.alias.colnames[0].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "unnest"

        col_type = "text"
        python_type: type = str
        if arr and isinstance(arr[0], int):
            col_type = "integer"
            python_type = int
        elif arr and isinstance(arr[0], float):
            col_type = "real"
            python_type = float

        col = SQLColumnDef(
            name=col_name,
            type_name=col_type,
            python_type=python_type,
        )
        table = Table(alias_name, [col])
        for val in arr:
            table.insert({col_name: val})

        self._engine._tables[alias_name] = table
        self._expanded_views.append(alias_name)
        return table, None

    def _build_regexp_split_to_table(
        self, node: RangeFunction, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build regexp_split_to_table(string, pattern [, flags]) as a table function."""
        import re as re_mod

        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 2:
            raise ValueError("regexp_split_to_table requires at least 2 arguments")

        string_val = self._extract_const_value(args[0])
        pattern_val = self._extract_const_value(args[1])
        if not isinstance(string_val, str):
            string_val = str(string_val)
        if not isinstance(pattern_val, str):
            pattern_val = str(pattern_val)

        flags = 0
        if len(args) > 2:
            flag_str = self._extract_const_value(args[2])
            if isinstance(flag_str, str):
                for ch in flag_str:
                    if ch == "i":
                        flags |= re_mod.IGNORECASE
                    elif ch == "g":
                        pass  # global is default for split
                    elif ch == "m":
                        flags |= re_mod.MULTILINE
                    elif ch == "s":
                        flags |= re_mod.DOTALL
                    elif ch == "x":
                        flags |= re_mod.VERBOSE

        parts = re_mod.split(pattern_val, string_val, flags=flags)

        # Determine column name from alias
        col_name = "regexp_split_to_table"
        if node.alias is not None:
            if node.alias.colnames:
                col_name = node.alias.colnames[0].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "regexp_split_to_table"

        col = SQLColumnDef(
            name=col_name,
            type_name="text",
            python_type=str,
        )
        table = Table(alias_name, [col])
        for val in parts:
            table.insert({col_name: val})

        self._engine._tables[alias_name] = table
        self._expanded_views.append(alias_name)
        return table, None

    def _build_json_each(
        self, node: RangeFunction, args: tuple, *, as_text: bool = False
    ) -> tuple[Table | None, Any]:
        """Build json_each(json) / json_each_text(json) as a table function."""
        from uqa.sql.expr_evaluator import ExprEvaluator
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("json_each requires 1 argument")

        evaluator = ExprEvaluator()
        obj = evaluator.evaluate(args[0], {})
        if isinstance(obj, str):
            import json as json_mod

            obj = json_mod.loads(obj)
        if not isinstance(obj, dict):
            raise ValueError("json_each argument must be a JSON object")

        # Determine column names from alias
        key_col = "key"
        val_col = "value"
        if node.alias is not None:
            if node.alias.colnames and len(node.alias.colnames) >= 2:
                key_col = node.alias.colnames[0].sval
                val_col = node.alias.colnames[1].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "json_each"

        import json as json_mod_inner

        cols = [
            SQLColumnDef(name=key_col, type_name="text", python_type=str),
            SQLColumnDef(name=val_col, type_name="text", python_type=str),
        ]
        table = Table(alias_name, cols)
        for k, v in obj.items():
            if as_text:
                val = str(v)
            elif isinstance(v, str):
                val = v
            else:
                val = json_mod_inner.dumps(v)
            table.insert({key_col: k, val_col: val})

        self._engine._tables[alias_name] = table
        self._expanded_views.append(alias_name)
        return table, None

    def _build_json_array_elements(
        self, node: RangeFunction, args: tuple, *, as_text: bool = False
    ) -> tuple[Table | None, Any]:
        """Build json_array_elements(json) as a table function."""
        from uqa.sql.expr_evaluator import ExprEvaluator
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("json_array_elements requires 1 argument")

        evaluator = ExprEvaluator()
        arr = evaluator.evaluate(args[0], {})
        if isinstance(arr, str):
            import json as json_mod

            arr = json_mod.loads(arr)
        if not isinstance(arr, list):
            raise ValueError("json_array_elements argument must be a JSON array")

        col_name = "value"
        if node.alias is not None:
            if node.alias.colnames:
                col_name = node.alias.colnames[0].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "json_array_elements"

        import json as json_mod_inner

        col = SQLColumnDef(name=col_name, type_name="text", python_type=str)
        table = Table(alias_name, [col])
        for val in arr:
            if as_text:
                actual = str(val)
            elif isinstance(val, str):
                actual = val
            else:
                actual = json_mod_inner.dumps(val)
            table.insert({col_name: actual})

        self._engine._tables[alias_name] = table
        self._expanded_views.append(alias_name)
        return table, None

    # -- JOIN ----------------------------------------------------------

    def _resolve_join(self, node: JoinExpr) -> tuple[Table | None, Any]:
        # Try DPccp optimization for chains of 3+ INNER JOINs
        result = self._try_dpccp_optimize(node)
        if result is not None:
            return result

        return self._resolve_join_pair(node)

    def _resolve_join_pair(self, node: JoinExpr) -> tuple[Table | None, Any]:
        """Resolve a single two-way JOIN expression."""
        from uqa.joins.base import JoinCondition
        from uqa.joins.cross import CrossJoinOperator
        from uqa.joins.inner import InnerJoinOperator
        from uqa.joins.outer import (
            FullOuterJoinOperator,
            LeftOuterJoinOperator,
            RightOuterJoinOperator,
        )

        left_table, left_op, left_alias = self._resolve_from_single(node.larg)

        # LATERAL subquery on the right side of a JOIN
        if isinstance(node.rarg, RangeSubselect) and node.rarg.lateral:
            if left_op is None and left_table is not None:
                left_op = _TableScanOperator(left_table, alias=left_alias)
            elif left_op is None:
                left_op = _ScanOperator()
            lateral_alias = node.rarg.alias.aliasname if node.rarg.alias else "_lateral"
            lateral_op = _LateralJoinOperator(
                left_op, node.rarg.subquery, lateral_alias, self
            )
            return left_table, lateral_op

        right_table, right_op, right_alias = self._resolve_from_single(node.rarg)

        table = left_table or right_table

        if left_op is None and left_table is not None:
            left_op = _TableScanOperator(left_table, alias=left_alias)
        elif left_op is None:
            left_op = _ScanOperator()
        if right_op is None and right_table is not None:
            right_op = _TableScanOperator(right_table, alias=right_alias)
        elif right_op is None:
            right_op = _ScanOperator()

        jt = node.jointype
        quals = node.quals

        # CROSS JOIN: JOIN_INNER with no quals
        if jt == JoinType.JOIN_INNER and quals is None:
            return table, CrossJoinOperator(left_op, right_op)

        # Simple equality ON: use efficient hash join
        if isinstance(quals, A_Expr):
            op_name = quals.name[-1].sval if quals.name else None
            if op_name == "=":
                left_field, right_field = self._resolve_join_on_fields(
                    quals.lexpr,
                    quals.rexpr,
                    left_alias,
                    right_alias,
                )
                condition = JoinCondition(left_field, right_field)

                if jt == JoinType.JOIN_INNER:
                    return table, InnerJoinOperator(left_op, right_op, condition)
                if jt == JoinType.JOIN_LEFT:
                    return table, LeftOuterJoinOperator(left_op, right_op, condition)
                if jt == JoinType.JOIN_RIGHT:
                    return table, RightOuterJoinOperator(left_op, right_op, condition)
                if jt == JoinType.JOIN_FULL:
                    return table, FullOuterJoinOperator(left_op, right_op, condition)

        # Complex ON (compound conditions, non-equality):
        # use nested-loop join with expression evaluation
        if quals is None:
            raise ValueError("Non-CROSS JOIN requires ON clause")
        return table, _ExprJoinOperator(left_op, right_op, quals, jt)

    # -- DPccp join order optimization ------------------------------------

    def _try_dpccp_optimize(self, node: JoinExpr) -> tuple[Table | None, Any] | None:
        """Attempt DPccp optimization on a chain of INNER JOINs.

        Returns None if the join tree is not eligible for DPccp
        (e.g. contains outer joins, LATERAL, non-equality predicates,
        or fewer than 3 relations).
        """
        relations: list[dict[str, Any]] = []
        predicates: list[dict[str, Any]] = []

        if not self._flatten_inner_joins(node, relations, predicates):
            return None

        # DPccp is worthwhile for 2+ relations (determines build side)
        if len(relations) < 2:
            return None

        from uqa.planner.join_order import JoinOrderOptimizer

        optimizer = JoinOrderOptimizer()
        operator, table = optimizer.optimize(relations, predicates)
        return table, operator

    def _flatten_inner_joins(
        self,
        node: Any,
        relations: list[dict[str, Any]],
        predicates: list[dict[str, Any]],
    ) -> bool:
        """Recursively flatten a tree of INNER JOINs.

        Collects base relations and equijoin predicates.  Returns
        False if any node is not eligible for reordering (outer join,
        LATERAL, non-equality predicate, subquery).
        """
        if not isinstance(node, JoinExpr):
            # Base relation
            table, op, alias = self._resolve_from_single(node)
            if op is None and table is not None:
                op = _TableScanOperator(table, alias=alias)
            elif op is None:
                op = _ScanOperator()

            cardinality = 1000.0  # default
            column_stats: dict[str, Any] = {}
            if table is not None:
                cardinality = float(len(table.document_store.doc_ids)) or 1.0
                column_stats = dict(table._stats)

            relations.append(
                {
                    "alias": alias,
                    "operator": op,
                    "table": table,
                    "cardinality": cardinality,
                    "column_stats": column_stats,
                }
            )
            return True

        # Only INNER JOINs can be freely reordered
        if node.jointype != JoinType.JOIN_INNER:
            return False

        # LATERAL subqueries cannot be reordered
        if isinstance(node.rarg, RangeSubselect) and node.rarg.lateral:
            return False

        # CROSS JOIN (no quals) is OK but has no predicate
        quals = node.quals

        # Recursively flatten left and right subtrees
        left_start = len(relations)
        if not self._flatten_inner_joins(node.larg, relations, predicates):
            return False

        right_start = len(relations)
        if not self._flatten_inner_joins(node.rarg, relations, predicates):
            return False

        # Extract equijoin predicate if present
        if quals is not None:
            pred = self._extract_equijoin_predicate(
                quals,
                relations,
                left_start,
                right_start,
            )
            if pred is None:
                # Non-equality or compound predicate; bail out
                return False
            predicates.append(pred)

        return True

    def _extract_equijoin_predicate(
        self,
        quals: Any,
        relations: list[dict[str, Any]],
        left_start: int,
        right_start: int,
    ) -> dict[str, Any] | None:
        """Extract a simple equijoin predicate from an ON clause.

        Returns a predicate dict or None if the quals are not a simple
        equality comparison on column references.
        """
        if not isinstance(quals, A_Expr):
            return None
        op_name = quals.name[-1].sval if quals.name else None
        if op_name != "=":
            return None
        if not isinstance(quals.lexpr, ColumnRef):
            return None
        if not isinstance(quals.rexpr, ColumnRef):
            return None

        l_fields = quals.lexpr.fields
        r_fields = quals.rexpr.fields

        l_col = l_fields[-1].sval
        r_col = r_fields[-1].sval
        l_qual = l_fields[0].sval if len(l_fields) >= 2 else None
        r_qual = r_fields[0].sval if len(r_fields) >= 2 else None

        # Match qualifiers to relation aliases to determine which
        # relation each side belongs to
        left_alias = self._find_relation_alias(
            l_qual, relations, left_start, right_start
        )
        right_alias = self._find_relation_alias(
            r_qual, relations, left_start, right_start
        )

        if left_alias is None or right_alias is None:
            return None
        if left_alias == right_alias:
            return None

        return {
            "left_alias": left_alias,
            "right_alias": right_alias,
            "left_field": l_col,
            "right_field": r_col,
        }

    @staticmethod
    def _find_relation_alias(
        qualifier: str | None,
        relations: list[dict[str, Any]],
        range_start: int,
        range_end: int,
    ) -> str | None:
        """Find the alias of a relation matching a column qualifier.

        Searches all relations (not just the given range) since a
        predicate like ``ON a.id = c.id`` may reference relations
        from any position in the flattened tree.
        """
        if qualifier is None:
            # Unqualified column; if there is exactly one relation
            # in the right range, assume it belongs there
            if range_end < len(relations) and range_end - range_start == 0:
                return relations[range_end]["alias"]
            return None

        for rel in relations:
            if rel["alias"] == qualifier:
                return qualifier
        return None

    @staticmethod
    def _resolve_join_on_fields(
        lexpr: Any,
        rexpr: Any,
        left_alias: str | None,
        right_alias: str | None,
    ) -> tuple[str, str]:
        """Map ON clause operands to (left_field, right_field).

        PostgreSQL treats ``ON p.x = e.y`` the same as ``ON e.y = p.x``.
        This method checks the table qualifiers to ensure the returned
        fields match the FROM clause order (left table, right table),
        regardless of the operand order in the ON expression.
        """
        l_col = lexpr.fields[-1].sval if isinstance(lexpr, ColumnRef) else str(lexpr)
        r_col = rexpr.fields[-1].sval if isinstance(rexpr, ColumnRef) else str(rexpr)

        l_qual = (
            lexpr.fields[0].sval
            if isinstance(lexpr, ColumnRef) and len(lexpr.fields) >= 2
            else None
        )
        r_qual = (
            rexpr.fields[0].sval
            if isinstance(rexpr, ColumnRef) and len(rexpr.fields) >= 2
            else None
        )

        # Match qualifiers to table aliases to determine correct order
        if l_qual == right_alias and r_qual == left_alias:
            # ON clause operands are swapped relative to FROM order
            return r_col, l_col
        # Default: assume ON clause order matches FROM order
        return l_col, r_col

    # -- WHERE clause --------------------------------------------------

    def _compile_where(self, node: Any, ctx: ExecutionContext) -> Any:
        if isinstance(node, BoolExpr):
            return self._compile_bool_expr(node, ctx)
        if isinstance(node, A_Expr):
            return self._compile_comparison(node, ctx)
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
            base = (
                scored[0]
                if len(scored) == 1
                else (
                    __import__(
                        "uqa.operators.boolean", fromlist=["IntersectOperator"]
                    ).IntersectOperator(scored)
                )
            )
        elif filters:
            base = filters.pop(0)
        else:
            return _ScanOperator()

        for f in filters:
            base = FilterOperator(f.field, f.predicate, source=base)
        return base

    def _compile_comparison(
        self, node: A_Expr, ctx: ExecutionContext | None = None
    ) -> Any:
        from uqa.operators.primitive import FilterOperator

        kind = A_Expr_Kind(node.kind)

        if kind == A_Expr_Kind.AEXPR_OP:
            op_name = node.name[0].sval

            if op_name == "@@":
                from uqa.sql.fts_query import compile_fts_match

                field_name = self._extract_column_name(node.lexpr)
                query_string = self._extract_string_value(node.rexpr)
                effective_field = None if field_name == "_all" else field_name
                if ctx is None:
                    raise ValueError("@@  operator requires an execution context")
                return compile_fts_match(query_string, effective_field, ctx, self)

            # Simple case: column op constant (basic comparison only)
            if (
                isinstance(node.lexpr, ColumnRef)
                and isinstance(node.rexpr, A_Const)
                and op_name in ("=", "!=", "<>", ">", ">=", "<", "<=")
            ):
                field_name = self._extract_column_name(node.lexpr)
                value = self._extract_const_value(node.rexpr)
                return FilterOperator(
                    field_name,
                    _op_to_predicate(op_name, value),
                )
            # Expression-based comparison (JSON ops, complex expressions, etc.)
            return _ExprFilterOperator(
                node, subquery_executor=self._compile_select, compiler=self
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
        from uqa.core.types import IsNotNull, IsNull
        from uqa.operators.primitive import FilterOperator

        field_name = self._extract_column_name(node.arg)
        if NullTestType(node.nulltesttype) == NullTestType.IS_NULL:
            return FilterOperator(field_name, IsNull())
        return FilterOperator(field_name, IsNotNull())

    def _compile_sublink_in_where(self, node: SubLink, ctx: ExecutionContext) -> Any:
        """Compile a SubLink (subquery) in WHERE position.

        Supports:
        - ANY_SUBLINK: ``WHERE col IN (SELECT ...)``
        - EXISTS_SUBLINK: ``WHERE EXISTS (SELECT ...)``

        Correlated subqueries (inner query references outer table) are
        routed to per-row evaluation via ``_ExprFilterOperator``.
        """
        # Detect correlated subqueries.  Try semi-join decorrelation
        # for EXISTS before falling back to per-row evaluation.
        if self._is_correlated(node.subselect):
            link_type_check = SubLinkType(node.subLinkType)
            if link_type_check == SubLinkType.EXISTS_SUBLINK:
                semi = self._try_exists_decorrelation(node.subselect, ctx)
                if semi is not None:
                    return semi
            return _ExprFilterOperator(
                node, subquery_executor=self._compile_select, compiler=self
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
                row[sub_col]
                for row in inner_result.rows
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

        raise ValueError(f"Unsupported subquery type: {link_type.name}")

    def _try_exists_decorrelation(
        self, subselect: SelectStmt, ctx: ExecutionContext
    ) -> Any:
        """Decorrelate a correlated EXISTS into a semi-join FilterOperator.

        Handles the common pattern:
            WHERE EXISTS (SELECT 1 FROM inner WHERE inner.fk = outer.pk AND ...)

        Extracts the equijoin predicate (inner.fk = outer.pk), executes the
        inner query with the non-correlated predicates only, collects the
        distinct values of the join column, and returns a FilterOperator
        using InSet on the outer column.  Falls back to None if the pattern
        is not recognized.
        """
        from uqa.operators.primitive import FilterOperator

        if subselect.whereClause is None:
            return None

        # Collect inner table names for correlated reference detection.
        inner_tables: set[str] = set()
        if subselect.fromClause:
            for from_item in subselect.fromClause:
                if isinstance(from_item, RangeVar):
                    if from_item.alias:
                        inner_tables.add(from_item.alias.aliasname)
                    inner_tables.add(from_item.relname)

        # Split WHERE into equijoin predicates and residual predicates.
        # Equijoin: inner_col = outer_col (one side correlated, one inner).
        equi_preds: list[
            tuple[str, str, str]
        ] = []  # (outer_qual_col, inner_col, inner_table)
        residual_nodes: list[Any] = []

        where = subselect.whereClause
        conjuncts = self._flatten_bool_and(where)

        for conj in conjuncts:
            parsed = self._parse_equijoin_predicate(conj, inner_tables)
            if parsed is not None:
                equi_preds.append(parsed)
            else:
                residual_nodes.append(conj)

        if not equi_preds:
            return None

        # Use the first equijoin predicate for the semi-join.
        outer_qual, inner_col, _inner_tbl = equi_preds[0]

        # outer_qual is "alias.column" -- extract the bare column name.
        outer_col = outer_qual.split(".")[-1] if "." in outer_qual else outer_qual

        # Build residual WHERE for the inner query (non-correlated predicates
        # plus any remaining equijoin predicates beyond the first).
        remaining_equi = equi_preds[1:]
        all_residual = residual_nodes + [
            self._rebuild_equijoin_node(ep) for ep in remaining_equi
        ]

        # Rebuild the inner SELECT projecting the join column so we can
        # collect its distinct values for the InSet filter.
        from pglast.ast import ResTarget

        join_target = ResTarget(
            val=ColumnRef(fields=(PgString(sval=_inner_tbl), PgString(sval=inner_col))),
            name=inner_col,
        )
        residual_where = self._rebuild_and(all_residual) if all_residual else None
        modified = SelectStmt(
            targetList=(join_target,),
            fromClause=subselect.fromClause,
            whereClause=residual_where,
            groupClause=None,
            havingClause=None,
            sortClause=None,
            limitCount=None,
            limitOffset=None,
            distinctClause=None,
            op=SetOperation.SETOP_NONE,
        )

        inner_result = self._compile_select(modified)
        if not inner_result.rows:
            from uqa.operators.boolean import ComplementOperator

            return ComplementOperator(_ScanOperator())

        # Collect distinct values of the inner join column.
        values = frozenset(
            row.get(inner_col)
            for row in inner_result.rows
            if row.get(inner_col) is not None
        )
        return FilterOperator(outer_col, InSet(values))

    @staticmethod
    def _flatten_bool_and(node: Any) -> list[Any]:
        """Flatten a tree of BoolExpr(AND, ...) into a list of conjuncts."""
        if (
            isinstance(node, BoolExpr)
            and BoolExprType(node.boolop) == BoolExprType.AND_EXPR
        ):
            result: list[Any] = []
            for arg in node.args:
                result.extend(SQLCompiler._flatten_bool_and(arg))
            return result
        return [node]

    def _parse_equijoin_predicate(
        self, node: Any, inner_tables: set[str]
    ) -> tuple[str, str, str] | None:
        """Parse an equijoin predicate: inner.col = outer.col.

        Returns (outer_qualified_col, inner_col_name, inner_table) or None.
        """
        if not isinstance(node, A_Expr):
            return None
        if not (hasattr(node, "name") and node.name and len(node.name) == 1):
            return None
        op = node.name[0]
        if not (hasattr(op, "sval") and op.sval == "="):
            return None
        if not isinstance(node.lexpr, ColumnRef) or not isinstance(
            node.rexpr, ColumnRef
        ):
            return None

        left_fields = node.lexpr.fields
        right_fields = node.rexpr.fields

        if len(left_fields) < 2 or len(right_fields) < 2:
            return None

        left_qual = left_fields[0].sval
        left_col = left_fields[-1].sval
        right_qual = right_fields[0].sval
        right_col = right_fields[-1].sval

        left_is_inner = left_qual in inner_tables
        right_is_inner = right_qual in inner_tables

        if left_is_inner and not right_is_inner:
            return (f"{right_qual}.{right_col}", left_col, left_qual)
        if right_is_inner and not left_is_inner:
            return (f"{left_qual}.{left_col}", right_col, right_qual)
        return None

    @staticmethod
    def _rebuild_and(nodes: list[Any]) -> Any:
        """Rebuild a list of conjuncts into a BoolExpr AND tree."""
        if len(nodes) == 1:
            return nodes[0]
        return BoolExpr(boolop=BoolExprType.AND_EXPR, args=tuple(nodes))

    @staticmethod
    def _rebuild_equijoin_node(ep: tuple[str, str, str]) -> Any:
        """Rebuild an equijoin predicate as an A_Expr node (unused in current path)."""
        outer_qual, inner_col, inner_tbl = ep
        parts = outer_qual.split(".")
        return A_Expr(
            kind=0,
            name=(PgString(sval="="),),
            lexpr=ColumnRef(
                fields=(PgString(sval=inner_tbl), PgString(sval=inner_col))
            ),
            rexpr=ColumnRef(fields=tuple(PgString(sval=p) for p in parts)),
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

        if isinstance(node, tuple | list):
            return any(self._has_outer_refs(item, inner_tables) for item in node)

        if hasattr(node, "__slots__") and isinstance(node.__slots__, dict):
            for slot in node.__slots__:
                val = getattr(node, slot, None)
                if val is not None and self._has_outer_refs(val, inner_tables):
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
        if name == "bayesian_match_with_prior":
            return self._make_bayesian_with_prior_op(args, ctx)
        if name == "knn_match":
            return self._make_knn_op(args)
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        if name == "temporal_traverse":
            return self._make_temporal_traverse_op(args)
        if name == "path_filter":
            return self._make_path_filter_op(args)
        if name == "vector_exclude":
            return self._make_vector_exclude_op(args)
        if name == "spatial_within":
            return self._make_spatial_within_op(args)
        if name == "fuse_log_odds":
            return self._make_fusion_op(args, ctx, mode="log_odds")
        if name == "fuse_prob_and":
            return self._make_fusion_op(args, ctx, mode="prob_and")
        if name == "fuse_prob_or":
            return self._make_fusion_op(args, ctx, mode="prob_or")
        if name == "fuse_prob_not":
            return self._make_prob_not_op(args, ctx)
        if name == "fuse_attention":
            return self._make_attention_fusion_op(args, ctx)
        if name == "fuse_learned":
            return self._make_learned_fusion_op(args, ctx)
        if name == "sparse_threshold":
            return self._make_sparse_threshold_op(args, ctx)
        if name == "multi_field_match":
            return self._make_multi_field_match_op(args)
        if name == "message_passing":
            return self._make_message_passing_op(args)
        if name == "graph_embedding":
            return self._make_graph_embedding_op(args)
        if name == "staged_retrieval":
            return self._make_staged_retrieval_op(args, ctx)
        if name == "pagerank":
            return self._make_pagerank_op(args)
        if name == "hits":
            return self._make_hits_op(args)
        if name == "betweenness":
            return self._make_betweenness_op(args)
        if name == "weighted_rpq":
            return self._make_weighted_rpq_op(args)
        if name == "progressive_fusion":
            return self._make_progressive_fusion_op(args, ctx)
        # Fall back to expression-based filter for scalar functions
        # used in WHERE (e.g., ST_DWithin, ST_Within).
        return _ExprFilterOperator(node, subquery_executor=self._compile_select)

    def _make_text_search_op(
        self,
        field_name: str | None,
        query: str,
        ctx: ExecutionContext,
        *,
        bayesian: bool,
    ) -> Any:
        from uqa.operators.primitive import ScoreOperator, TermOperator

        idx = ctx.inverted_index
        analyzer = idx.get_search_analyzer(field_name) if field_name else idx.analyzer
        terms = analyzer.analyze(query)
        if not terms:
            return TermOperator(query, field_name)
        # Pass the raw query to a single TermOperator so it analyzes
        # once internally.  Pre-analyzing and feeding stemmed tokens to
        # TermOperator caused double-stemming (e.g. database -> databas
        # -> databa) for terms where stemming is not idempotent.
        retrieval = TermOperator(query, field_name)

        if bayesian:
            from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

            scorer = BayesianBM25Scorer(BayesianBM25Params(), ctx.inverted_index.stats)
        else:
            from uqa.scoring.bm25 import BM25Params, BM25Scorer

            scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        return ScoreOperator(scorer, retrieval, terms, field=field_name)

    def _make_multi_field_match_op(self, args: tuple) -> Any:
        """multi_field_match(field1, field2, ..., query [, weight1, weight2, ...])

        The last string argument is the query string.  All preceding ColumnRef
        arguments are field names.  Optional trailing numeric arguments after
        the query are per-field weights.
        """
        from uqa.operators.multi_field import MultiFieldSearchOperator

        if len(args) < 3:
            raise ValueError(
                "multi_field_match() requires at least 3 arguments: "
                "multi_field_match(field1, field2, ..., query)"
            )

        # Parse: fields..., query_string [, weight1, weight2, ...]
        fields: list[str] = []
        query: str | None = None
        weights: list[float] = []

        for i, arg in enumerate(args):
            if isinstance(arg, ColumnRef):
                fields.append(self._extract_column_name(arg))
            elif isinstance(arg, A_Const):
                val = self._extract_const_value(arg)
                if isinstance(val, str) and query is None:
                    query = val
                elif isinstance(val, int | float):
                    weights.append(float(val))
                elif isinstance(val, str):
                    raise ValueError(f"Unexpected string argument at position {i}")

        if query is None or len(fields) < 2:
            raise ValueError(
                "multi_field_match() requires at least 2 field names and a query string"
            )

        if weights and len(weights) != len(fields):
            raise ValueError(
                f"Number of weights ({len(weights)}) must match "
                f"number of fields ({len(fields)})"
            )

        return MultiFieldSearchOperator(
            fields, query, weights=weights if weights else None
        )

    def _make_message_passing_op(self, args: tuple) -> Any:
        """message_passing(k_layers, aggregation, property_name)"""
        from uqa.graph.message_passing import MessagePassingOperator

        k = self._extract_int_value(args[0]) if len(args) > 0 else 2
        agg = self._extract_string_value(args[1]) if len(args) > 1 else "mean"
        prop = self._extract_string_value(args[2]) if len(args) > 2 else None
        return MessagePassingOperator(k, agg, prop)

    def _make_graph_embedding_op(self, args: tuple) -> Any:
        """graph_embedding(dimensions, k_layers)"""
        from uqa.graph.graph_embedding import GraphEmbeddingOperator

        dims = self._extract_int_value(args[0]) if len(args) > 0 else 32
        k = self._extract_int_value(args[1]) if len(args) > 1 else 2
        return GraphEmbeddingOperator(dims, k)

    def _make_bayesian_with_prior_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """bayesian_match_with_prior(field, query, prior_field, prior_mode)

        Bayesian BM25 with external prior.
        prior_mode: 'recency' or 'authority'.
        """
        from uqa.operators.primitive import TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params
        from uqa.scoring.external_prior import (
            ExternalPriorScorer,
            authority_prior,
            recency_prior,
        )

        if len(args) < 4:
            raise ValueError(
                "bayesian_match_with_prior() requires 4 arguments: "
                "bayesian_match_with_prior(field, query, prior_field, prior_mode)"
            )
        field_name = self._extract_column_name(args[0])
        query = self._extract_string_value(args[1])
        prior_field = self._extract_string_value(args[2])
        prior_mode = self._extract_string_value(args[3])

        if prior_mode == "recency":
            prior_fn = recency_prior(prior_field)
        elif prior_mode == "authority":
            prior_fn = authority_prior(prior_field)
        else:
            raise ValueError(
                f"Unknown prior mode: {prior_mode}. Use 'recency' or 'authority'."
            )

        idx = ctx.inverted_index
        scorer = ExternalPriorScorer(BayesianBM25Params(), idx.stats, prior_fn)

        analyzer = idx.get_search_analyzer(field_name) if field_name else idx.analyzer
        terms = analyzer.analyze(query)
        retrieval = TermOperator(query, field_name)

        return _ExternalPriorSearchOperator(
            retrieval, scorer, terms, field_name, ctx.document_store
        )

    def _make_knn_op(self, args: tuple) -> Any:
        """knn_match(field, vector, k)

        *field* is a column name (ColumnRef).
        *vector* is an ARRAY literal or $N parameter reference.
        *k* is an integer constant.
        """
        from uqa.operators.primitive import KNNOperator

        if len(args) != 3:
            raise ValueError(
                "knn_match() requires 3 arguments: knn_match(field, vector, k)"
            )
        field_name = self._extract_column_name(args[0])
        query_vector = self._extract_vector_arg(args[1])
        k = self._extract_int_value(args[2])
        return KNNOperator(query_vector, k, field=field_name)

    def _make_spatial_within_op(self, args: tuple) -> Any:
        """spatial_within(field, POINT(x, y), distance_meters)

        *field* is a column name (ColumnRef).
        *POINT(x, y)* is a POINT constructor (FuncCall) or $N parameter.
        *distance_meters* is a numeric constant or $N parameter.
        """
        from uqa.operators.primitive import SpatialWithinOperator

        if len(args) != 3:
            raise ValueError(
                "spatial_within() requires 3 arguments: "
                "spatial_within(field, POINT(x, y), distance)"
            )
        field_name = self._extract_column_name(args[0])
        cx, cy = self._extract_point_arg(args[1])
        distance = self._extract_numeric_value(args[2])
        return SpatialWithinOperator(field_name, cx, cy, distance)

    def _extract_point_arg(self, node: Any) -> tuple[float, float]:
        """Extract (x, y) from POINT(x, y) FuncCall or $N parameter."""
        if isinstance(node, FuncCall):
            name = node.funcname[-1].sval.lower()
            if name != "point":
                raise ValueError(f"Expected POINT(x, y), got {name}()")
            pt_args = node.args or ()
            if len(pt_args) != 2:
                raise ValueError("POINT() requires exactly 2 arguments")
            x = self._extract_numeric_value(pt_args[0])
            y = self._extract_numeric_value(pt_args[1])
            return (x, y)
        if isinstance(node, ParamRef):
            idx = node.number - 1
            if idx < 0 or idx >= len(self._params):
                raise ValueError(f"No value supplied for parameter ${node.number}")
            val = self._params[idx]
            if isinstance(val, list | tuple) and len(val) == 2:
                return (float(val[0]), float(val[1]))
            raise ValueError(
                f"Parameter ${node.number} must be a [x, y] list for POINT"
            )
        raise ValueError(
            f"Expected POINT(x, y) or $N parameter, got {type(node).__name__}"
        )

    def _extract_numeric_value(self, node: Any) -> float:
        """Extract a numeric value from A_Const or $N parameter."""
        if isinstance(node, A_Const):
            val = node.val
            if isinstance(val, PgInteger):
                return float(val.ival)
            if isinstance(val, PgFloat):
                return float(val.fval)
        if isinstance(node, ParamRef):
            idx = node.number - 1
            if idx < 0 or idx >= len(self._params):
                raise ValueError(f"No value supplied for parameter ${node.number}")
            return float(self._params[idx])
        raise ValueError(
            f"Expected numeric constant or $N parameter, got {type(node).__name__}"
        )

    def _make_traverse_match_op(self, args: tuple) -> Any:
        """traverse_match(start_id, 'label', max_hops) as a WHERE signal.

        Returns a posting list of reachable vertices with score = 0.9.
        """
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        return TraverseOperator(start, label, max_hops)

    def _make_temporal_traverse_op(self, args: tuple) -> Any:
        """temporal_traverse(start, label, hops, timestamp) or
        temporal_traverse(start, label, hops, from_ts, to_ts)

        Returns a posting list of temporally reachable vertices.
        """
        from uqa.graph.temporal_filter import TemporalFilter
        from uqa.graph.temporal_traverse import TemporalTraverseOperator

        if len(args) < 4:
            raise ValueError(
                "temporal_traverse() requires at least 4 arguments: "
                "temporal_traverse(start, label, hops, timestamp)"
            )
        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1

        if len(args) == 4:
            ts = float(self._extract_const_value(args[3]))
            tf = TemporalFilter(timestamp=ts)
        elif len(args) >= 5:
            from_ts = float(self._extract_const_value(args[3]))
            to_ts = float(self._extract_const_value(args[4]))
            tf = TemporalFilter(time_range=(from_ts, to_ts))
        else:
            tf = TemporalFilter()

        return TemporalTraverseOperator(start, label, max_hops, tf)

    def _make_path_filter_op(self, args: tuple) -> Any:
        """path_filter('path', value) or path_filter('path', 'op', value).

        2-arg form: equality filter on nested path.
        3-arg form: comparison filter with explicit operator (=, !=, <, >, <=, >=).
        """
        from uqa.operators.hierarchical import PathFilterOperator

        if len(args) < 2:
            raise ValueError(
                "path_filter() requires at least 2 arguments: "
                "path_filter('path', value) or path_filter('path', 'op', value)"
            )

        path_str = self._extract_string_value(args[0])
        path_expr: list[str | int] = []
        for component in path_str.split("."):
            if component.isdigit():
                path_expr.append(int(component))
            else:
                path_expr.append(component)

        if len(args) == 2:
            value = self._extract_const_value(args[1])
            return PathFilterOperator(path_expr, Equals(value))

        op_str = self._extract_string_value(args[1])
        value = self._extract_const_value(args[2])
        return PathFilterOperator(path_expr, _op_to_predicate(op_str, value))

    def _make_vector_exclude_op(self, args: tuple) -> Any:
        """vector_exclude(field, positive_vector, negative_vector, k, threshold)

        *field* is a column name (ColumnRef).
        *positive_vector* is an ARRAY literal or $N parameter.
        *negative_vector* is an ARRAY literal or $N parameter.
        *k* is an integer constant.
        *threshold* is a numeric constant.
        """
        from uqa.operators.hybrid import VectorExclusionOperator
        from uqa.operators.primitive import KNNOperator

        if len(args) != 5:
            raise ValueError(
                "vector_exclude() requires 5 arguments: "
                "vector_exclude(field, positive_vector, negative_vector, "
                "k, threshold)"
            )

        field_name = self._extract_column_name(args[0])
        positive_vector = self._extract_vector_arg(args[1])
        negative_vector = self._extract_vector_arg(args[2])
        k = self._extract_int_value(args[3])
        threshold = float(self._extract_const_value(args[4]))

        positive = KNNOperator(positive_vector, k, field=field_name)
        return VectorExclusionOperator(
            positive, negative_vector, threshold, field=field_name
        )

    def _compile_calibrated_signal(self, node: FuncCall, ctx: ExecutionContext) -> Any:
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
            return self._make_calibrated_knn_op(args)
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        if name == "spatial_within":
            return self._make_spatial_within_op(args)
        if name == "pagerank":
            return self._make_pagerank_op(args)
        if name == "hits":
            return self._make_hits_op(args)
        if name == "betweenness":
            return self._make_betweenness_op(args)
        if name == "weighted_rpq":
            return self._make_weighted_rpq_op(args)
        if name == "message_passing":
            return self._make_message_passing_op(args)
        raise ValueError(
            f"Unknown signal function for fusion: {name}. "
            f"Use text_match, bayesian_match, knn_match, traverse_match, "
            f"spatial_within, pagerank, hits, betweenness, or weighted_rpq."
        )

    def _make_calibrated_knn_op(self, args: tuple) -> Any:
        """KNN search with scores calibrated to probabilities via
        P_vector = (1 + cosine_similarity) / 2 (Definition 7.1.2, Paper 3).

        knn_match(field, vector, k) -- same signature as _make_knn_op.
        """
        if len(args) != 3:
            raise ValueError(
                "knn_match() requires 3 arguments: knn_match(field, vector, k)"
            )
        field_name = self._extract_column_name(args[0])
        query_vector = self._extract_vector_arg(args[1])
        k = self._extract_int_value(args[2])
        return _CalibratedKNNOperator(query_vector, k, field=field_name)

    def _make_prob_not_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """fuse_prob_not(signal) -- probabilistic complement of a single signal."""
        from uqa.operators.hybrid import ProbNotOperator

        if len(args) != 1 or not isinstance(args[0], FuncCall):
            raise ValueError(
                "fuse_prob_not() requires exactly 1 signal function argument"
            )
        signal = self._compile_calibrated_signal(args[0], ctx)
        return ProbNotOperator(signal)

    def _make_sparse_threshold_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """sparse_threshold(signal, threshold)

        Apply ReLU thresholding: max(0, score - threshold).
        """
        from uqa.operators.sparse import SparseThresholdOperator

        if len(args) != 2:
            raise ValueError(
                "sparse_threshold() requires 2 arguments: "
                "sparse_threshold(signal, threshold)"
            )
        if not isinstance(args[0], FuncCall):
            raise ValueError(
                "sparse_threshold() first argument must be a signal function"
            )
        signal = self._compile_calibrated_signal(args[0], ctx)
        threshold = float(self._extract_const_value(args[1]))
        return SparseThresholdOperator(signal, threshold)

    def _make_fusion_op(self, args: tuple, ctx: ExecutionContext, *, mode: str) -> Any:
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
        gating: str | None = None

        for arg in args:
            if isinstance(arg, FuncCall):
                signals.append(self._compile_calibrated_signal(arg, ctx))
            elif isinstance(arg, A_Const) and mode == "log_odds":
                val = self._extract_const_value(arg)
                if isinstance(val, str):
                    gating = val
                else:
                    alpha = float(val)
            else:
                raise ValueError(
                    f"Fusion function arguments must be signal functions "
                    f"(text_match, knn_match, etc.), got {type(arg).__name__}"
                )

        if len(signals) < 2:
            raise ValueError("Fusion requires at least 2 signal functions")

        if mode == "log_odds":
            return LogOddsFusionOperator(signals, alpha=alpha, gating=gating)
        if mode == "prob_and":
            return ProbBoolFusionOperator(signals, mode="and")
        return ProbBoolFusionOperator(signals, mode="or")

    def _make_staged_retrieval_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """staged_retrieval(signal1, k1, signal2, k2, ...)

        Each pair of arguments is a (signal_function, cutoff) pair.
        Cutoff can be int (top-k) or float (threshold).
        """
        from uqa.operators.multi_stage import MultiStageOperator

        stages = []
        i = 0
        while i < len(args) - 1:
            if not isinstance(args[i], FuncCall):
                raise ValueError(
                    f"staged_retrieval: argument {i} must be a signal function"
                )
            signal = self._compile_calibrated_signal(args[i], ctx)
            cutoff_val = self._extract_const_value(args[i + 1])
            if isinstance(cutoff_val, float) and cutoff_val == int(cutoff_val):
                cutoff_val = int(cutoff_val)
            stages.append((signal, cutoff_val))
            i += 2

        if not stages:
            raise ValueError(
                "staged_retrieval requires at least one (signal, cutoff) pair"
            )

        return MultiStageOperator(stages)

    def _make_pagerank_op(self, args: tuple) -> Any:
        """pagerank([damping[, max_iterations[, tolerance]]])

        Graph centrality scoring via power iteration.
        """
        from uqa.graph.centrality import PageRankOperator

        damping = float(self._extract_const_value(args[0])) if len(args) > 0 else 0.85
        max_iter = self._extract_int_value(args[1]) if len(args) > 1 else 100
        tol = float(self._extract_const_value(args[2])) if len(args) > 2 else 1e-6
        return PageRankOperator(damping=damping, max_iterations=max_iter, tolerance=tol)

    def _make_hits_op(self, args: tuple) -> Any:
        """hits([max_iterations[, tolerance]])

        HITS hub/authority scoring.
        """
        from uqa.graph.centrality import HITSOperator

        max_iter = self._extract_int_value(args[0]) if len(args) > 0 else 100
        tol = float(self._extract_const_value(args[1])) if len(args) > 1 else 1e-6
        return HITSOperator(max_iterations=max_iter, tolerance=tol)

    def _make_betweenness_op(self, _args: tuple) -> Any:
        """betweenness()

        Betweenness centrality via Brandes algorithm.
        """
        from uqa.graph.centrality import BetweennessCentralityOperator

        return BetweennessCentralityOperator()

    def _make_weighted_rpq_op(self, args: tuple) -> Any:
        """weighted_rpq('path_expr', start, 'weight_prop'[, 'agg_fn'[, threshold]])

        Weighted regular path query with cumulative edge weight tracking.
        """
        from uqa.graph.operators import WeightedPathQueryOperator
        from uqa.graph.pattern import parse_rpq

        if len(args) < 3:
            raise ValueError(
                "weighted_rpq() requires at least 3 arguments: "
                "weighted_rpq('path_expr', start, 'weight_property'"
                "[, 'agg_fn'[, threshold]])"
            )
        expr_str = self._extract_string_value(args[0])
        start = self._extract_int_value(args[1])
        weight_prop = self._extract_string_value(args[2])
        agg_fn = self._extract_string_value(args[3]) if len(args) > 3 else "sum"
        predicate = None
        if len(args) > 4:
            threshold = float(self._extract_const_value(args[4]))
            predicate = lambda w, t=threshold: w > t
        return WeightedPathQueryOperator(
            path_expr=parse_rpq(expr_str),
            weight_property=weight_prop,
            aggregate_fn=agg_fn,
            predicate=predicate,
            start_vertex=start,
        )

    def _make_progressive_fusion_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """progressive_fusion(signal1, signal2, k1, signal3, k2[, alpha[, 'gating']])

        Progressive multi-stage fusion with WAND pruning.
        First stage signals come before the first k, subsequent stages
        alternate between signal and k.
        Format: progressive_fusion(sig1, sig2, k1, sig3, k2[, alpha][, 'gating'])
        """
        from uqa.operators.progressive_fusion import ProgressiveFusionOperator

        # Parse stage signals and cutoffs
        signals: list[Any] = []
        stages: list[tuple[list[Any], int]] = []
        alpha = 0.5
        gating = None

        for arg in args:
            if isinstance(arg, FuncCall):
                signals.append(self._compile_calibrated_signal(arg, ctx))
            elif isinstance(arg, A_Const):
                val = self._extract_const_value(arg)
                if isinstance(val, str):
                    gating = val
                elif isinstance(val, float) and not val == int(val):
                    alpha = val
                else:
                    # Integer: this is a k cutoff
                    k = int(val)
                    if not signals:
                        raise ValueError(
                            "progressive_fusion: k must follow signal functions"
                        )
                    stages.append((list(signals), k))
                    signals = []
            else:
                raise ValueError(
                    f"progressive_fusion: unexpected argument type {type(arg).__name__}"
                )

        if signals:
            raise ValueError(
                "progressive_fusion: trailing signals without k cutoff"
            )
        if not stages:
            raise ValueError(
                "progressive_fusion requires at least one (signals, k) stage"
            )

        return ProgressiveFusionOperator(stages=stages, alpha=alpha, gating=gating)

    def _make_attention_fusion_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """fuse_attention(signal1, signal2, ...)"""
        from uqa.fusion.attention import AttentionFusion
        from uqa.fusion.query_features import QueryFeatureExtractor
        from uqa.operators.attention import AttentionFusionOperator

        signals: list[Any] = []
        for arg in args:
            if isinstance(arg, FuncCall):
                signals.append(self._compile_calibrated_signal(arg, ctx))

        if len(signals) < 2:
            raise ValueError("fuse_attention requires at least 2 signals")

        n_signals = len(signals)
        attention = AttentionFusion(n_signals=n_signals, n_query_features=6)

        # Extract query features from the first text signal
        import numpy as np

        query_features = np.zeros(6, dtype=np.float64)
        if ctx.inverted_index is not None:
            extractor = QueryFeatureExtractor(ctx.inverted_index)
            # Try to extract terms from the first text signal
            for arg in args:
                if isinstance(arg, FuncCall):
                    fn_name = arg.funcname[-1].sval.lower()
                    if (
                        fn_name in ("text_match", "bayesian_match")
                        and arg.args
                        and len(arg.args) >= 2
                    ):
                        query_str = self._extract_string_value(arg.args[1])
                        analyzer = ctx.inverted_index.analyzer
                        terms = analyzer.analyze(query_str)
                        query_features = extractor.extract(terms)
                        break

        return AttentionFusionOperator(signals, attention, query_features)

    def _make_learned_fusion_op(self, args: tuple, ctx: ExecutionContext) -> Any:
        """fuse_learned(signal1, signal2, ...)"""
        from uqa.fusion.learned import LearnedFusion
        from uqa.operators.learned_fusion import LearnedFusionOperator

        signals: list[Any] = []
        for arg in args:
            if isinstance(arg, FuncCall):
                signals.append(self._compile_calibrated_signal(arg, ctx))

        if len(signals) < 2:
            raise ValueError("fuse_learned requires at least 2 signals")

        learned = LearnedFusion(n_signals=len(signals))
        return LearnedFusionOperator(signals, learned)

    # -- Aggregation ---------------------------------------------------

    def _has_aggregates(self, target_list: tuple | None) -> bool:
        if target_list is None:
            return False
        for t in target_list:
            for func in self._collect_agg_funcs(t.val):
                fn = func.funcname[-1].sval.lower()
                if fn in _AGG_FUNC_NAMES and func.over is None:
                    return True
        return False

    def _extract_agg_specs(self, target_list: tuple) -> list[tuple]:
        """Extract aggregate specifications as 8-tuples.

        Returns (alias, func_name, arg_col, distinct, extra, filter_node,
        order_keys, agg_expr_node).  filter_node is the AST node for
        FILTER (WHERE ...), order_keys is a list of (col_name, descending)
        for ORDER BY within aggregate.

        Also discovers aggregates nested inside scalar functions
        (e.g., ROUND(STDDEV(salary), 2)) and adds them with their
        natural column names so HashAggOp computes them.
        """
        from pglast.enums.parsenodes import SortByDir

        specs: list[tuple] = []
        for target in target_list:
            # Find the top-level aggregate (if any)
            func: FuncCall | None = None
            if isinstance(target.val, FuncCall):
                fn = target.val.funcname[-1].sval.lower()
                if fn in _AGG_FUNC_NAMES and target.val.over is None:
                    func = target.val

            if func is None:
                # Not a top-level aggregate -- check for nested aggregates
                # (e.g., ROUND(STDDEV(salary), 2))
                nested = self._collect_agg_funcs(target.val)
                nested = [
                    f
                    for f in nested
                    if f.funcname[-1].sval.lower() in _AGG_FUNC_NAMES and f.over is None
                ]
                existing = {(s[1], s[2]) for s in specs}
                for nf in nested:
                    nfn = nf.funcname[-1].sval.lower()
                    if nf.agg_star or not nf.args:
                        ac = None
                    elif isinstance(nf.args[0], ColumnRef):
                        ac = self._extract_column_name(nf.args[0])
                    else:
                        ac = None
                    extra = None
                    if (
                        nfn in _TWO_ARG_STAT_AGGS
                        and len(nf.args or ()) >= 2
                        and isinstance(nf.args[1], ColumnRef)
                    ):
                        extra = self._extract_column_name(nf.args[1])
                    if (nfn, ac) not in existing:
                        alias = nfn if ac is None else f"{nfn}_{ac}"
                        specs.append(
                            (
                                alias,
                                nfn,
                                ac,
                                False,
                                extra,
                                None,
                                None,
                                None,
                            )
                        )
                        existing.add((nfn, ac))
                continue
            func_name = func.funcname[-1].sval.lower()
            distinct = bool(func.agg_distinct)
            extra: Any = None
            agg_expr_node: Any = None

            # Ordered-set aggregates: arg_col from WITHIN GROUP (ORDER BY)
            if func_name in ("percentile_cont", "percentile_disc"):
                extra = self._extract_const_value(func.args[0])
                arg_col = self._extract_column_name(func.agg_order[0].node)
            elif func_name == "mode":
                arg_col = self._extract_column_name(func.agg_order[0].node)
            elif func_name in ("json_object_agg", "jsonb_object_agg"):
                arg_col = self._extract_column_name(func.args[0])
                extra = self._extract_column_name(func.args[1])
            elif func_name in _TWO_ARG_STAT_AGGS:
                # Two-argument statistical aggregates: (y, x)
                arg_col = self._extract_column_name(func.args[0])
                extra = self._extract_column_name(func.args[1])
            else:
                if func.agg_star:
                    arg_col = None
                elif isinstance(func.args[0], ColumnRef):
                    arg_col = self._extract_column_name(func.args[0])
                else:
                    # Expression arg (CaseExpr, A_Expr, etc.)
                    # Generate a synthetic column name; the expression
                    # will be pre-computed via ExprProjectOp.
                    arg_col = f"__agg_expr_{len(specs)}"
                    agg_expr_node = func.args[0]
                if func_name == "string_agg" and func.args and len(func.args) > 1:
                    extra = self._extract_const_value(func.args[1])

            alias = target.name or (
                func_name if arg_col is None else f"{func_name}_{arg_col}"
            )

            filter_node = func.agg_filter
            order_keys = None
            if func.agg_order:
                order_keys = [
                    (
                        self._extract_column_name(sb.node),
                        sb.sortby_dir == SortByDir.SORTBY_DESC,
                    )
                    for sb in func.agg_order
                ]

            specs.append(
                (
                    alias,
                    func_name,
                    arg_col,
                    distinct,
                    extra,
                    filter_node,
                    order_keys,
                    agg_expr_node,
                )
            )
        return specs

    def _ensure_having_aggs(self, having_node: Any, agg_specs: list[tuple]) -> None:
        """Walk the HAVING AST and add any aggregate calls missing from *agg_specs*.

        This ensures that aggregates referenced only in HAVING (not in SELECT)
        are still computed by HashAggOp.
        """
        existing = {(s[1], s[2]) for s in agg_specs}  # (func_name, arg_col)
        for func in self._collect_agg_funcs(having_node):
            func_name = func.funcname[-1].sval.lower()
            if func_name not in _AGG_FUNC_NAMES:
                continue
            if func.agg_star or not func.args:
                arg_col = None
            elif isinstance(func.args[0], ColumnRef):
                arg_col = self._extract_column_name(func.args[0])
            else:
                arg_col = None
            if (func_name, arg_col) in existing:
                continue
            alias = func_name if arg_col is None else f"{func_name}_{arg_col}"
            agg_specs.append(
                (
                    alias,
                    func_name,
                    arg_col,
                    False,
                    None,
                    None,
                    None,
                    None,
                )
            )
            existing.add((func_name, arg_col))

    @staticmethod
    def _collect_agg_funcs(node: Any) -> list[FuncCall]:
        """Recursively collect all FuncCall nodes from an AST subtree."""
        result: list[FuncCall] = []
        if isinstance(node, FuncCall):
            result.append(node)
        for attr in ("lexpr", "rexpr", "args", "arg"):
            child = getattr(node, attr, None)
            if child is None:
                continue
            if isinstance(child, list | tuple):
                for item in child:
                    result.extend(SQLCompiler._collect_agg_funcs(item))
            else:
                result.extend(SQLCompiler._collect_agg_funcs(child))
        return result

    # -- Window functions -----------------------------------------------

    @staticmethod
    def _has_window_functions(target_list: tuple | None) -> bool:
        if target_list is None:
            return False
        return any(
            isinstance(t.val, FuncCall) and t.val.over is not None for t in target_list
        )

    def _extract_window_specs(
        self, target_list: tuple, window_clause: tuple | None = None
    ) -> list[WindowSpec]:
        """Extract window function specs from the target list."""
        from uqa.execution.relational import WindowSpec
        from uqa.sql.expr_evaluator import ExprEvaluator

        # Build named window lookup from WINDOW clause
        named_windows: dict[str, Any] = {}
        if window_clause:
            for wdef in window_clause:
                named_windows[wdef.name] = wdef

        specs: list[WindowSpec] = []
        for target in target_list:
            val = target.val
            if not isinstance(val, FuncCall) or val.over is None:
                continue

            func_name = val.funcname[-1].sval.lower()
            alias = target.name or func_name
            win = val.over

            # Resolve named window reference (OVER (w))
            if win.refname and win.refname in named_windows:
                base = named_windows[win.refname]
                # Merge: the inline OVER can add partition/order to the base
                if not win.partitionClause and base.partitionClause:
                    win = win.__class__(
                        partitionClause=base.partitionClause,
                        orderClause=win.orderClause or base.orderClause,
                        frameOptions=win.frameOptions
                        if (win.frameOptions or 0) & 1
                        else base.frameOptions,
                        startOffset=win.startOffset or base.startOffset,
                        endOffset=win.endOffset or base.endOffset,
                    )
                elif not win.orderClause and base.orderClause:
                    win = win.__class__(
                        partitionClause=win.partitionClause or base.partitionClause,
                        orderClause=base.orderClause,
                        frameOptions=win.frameOptions
                        if (win.frameOptions or 0) & 1
                        else base.frameOptions,
                        startOffset=win.startOffset or base.startOffset,
                        endOffset=win.endOffset or base.endOffset,
                    )
            elif (
                win.name
                and win.name in named_windows
                and not win.partitionClause
                and not win.orderClause
            ):
                # OVER w (bare name, already resolved by pglast in some cases)
                base = named_windows[win.name]
                win = base

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
                        default_value = evaluator.evaluate(val.args[2], {})
            elif func_name == "ntile":
                evaluator = ExprEvaluator()
                if val.args:
                    ntile_buckets = int(evaluator.evaluate(val.args[0], {}))
            elif func_name == "nth_value":
                evaluator = ExprEvaluator()
                if val.args:
                    arg_col = self._extract_column_name(val.args[0])
                    if len(val.args) > 1:
                        ntile_buckets = int(evaluator.evaluate(val.args[1], {}))
            elif func_name not in (
                "row_number",
                "rank",
                "dense_rank",
                "percent_rank",
                "cume_dist",
            ):
                # Aggregate window functions (SUM, COUNT, AVG, MIN, MAX)
                if not val.agg_star and val.args:
                    arg_col = self._extract_column_name(val.args[0])

            # Parse window frame
            frame_start, frame_end = None, None
            frame_start_offset, frame_end_offset = 0, 0
            frame_type = "rows"
            fo = win.frameOptions or 0
            if fo & 1:  # NONDEFAULT
                if fo & 2:  # RANGE
                    frame_type = "range"
                frame_start, frame_start_offset = self._parse_frame_bound(
                    fo, "start", win.startOffset
                )
                frame_end, frame_end_offset = self._parse_frame_bound(
                    fo, "end", win.endOffset
                )

            specs.append(
                WindowSpec(
                    alias=alias,
                    func_name=func_name,
                    partition_cols=part_cols,
                    order_keys=order_keys,
                    arg_col=arg_col,
                    offset=offset,
                    default_value=default_value,
                    ntile_buckets=ntile_buckets,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    frame_start_offset=frame_start_offset,
                    frame_end_offset=frame_end_offset,
                    frame_type=frame_type,
                    filter_node=val.agg_filter,
                )
            )

        return specs

    @staticmethod
    def _parse_frame_bound(
        frame_options: int, side: str, offset_node: Any
    ) -> tuple[str, int]:
        """Parse a window frame bound from the bitmask.

        side is "start" or "end".  Returns (bound_type, offset).
        """
        # Constants from pglast.enums.parsenodes
        if side == "start":
            if frame_options & 32:  # START_UNBOUNDED_PRECEDING
                return "unbounded_preceding", 0
            if frame_options & 512:  # START_CURRENT_ROW
                return "current_row", 0
            if frame_options & 2048:  # START_OFFSET_PRECEDING
                off = 0
                if offset_node is not None:
                    off = offset_node.val.ival
                return "offset_preceding", off
            if frame_options & 8192:  # START_OFFSET_FOLLOWING
                off = 0
                if offset_node is not None:
                    off = offset_node.val.ival
                return "offset_following", off
        else:
            if frame_options & 256:  # END_UNBOUNDED_FOLLOWING
                return "unbounded_following", 0
            if frame_options & 1024:  # END_CURRENT_ROW
                return "current_row", 0
            if frame_options & 4096:  # END_OFFSET_PRECEDING
                off = 0
                if offset_node is not None:
                    off = offset_node.val.ival
                return "offset_preceding", off
            if frame_options & 16384:  # END_OFFSET_FOLLOWING
                off = 0
                if offset_node is not None:
                    off = offset_node.val.ival
                return "offset_following", off
        return "current_row", 0

    # -- Result conversion ---------------------------------------------

    def _scan_all(self, ctx: ExecutionContext, limit: int | None = None) -> PostingList:
        if ctx.document_store is None:
            # No FROM clause (e.g. SELECT 1 AS val): produce a single
            # dummy row so that expression projection yields one result.
            return PostingList([PostingEntry(0, Payload(score=0.0))])
        all_ids = sorted(ctx.document_store.doc_ids)
        if limit is not None and limit < len(all_ids):
            all_ids = all_ids[:limit]
        return PostingList([PostingEntry(d, Payload(score=0.0)) for d in all_ids])

    # -- Helpers -------------------------------------------------------

    def _chain_on_source(self, where_op: Any, source_op: Any) -> Any:
        from uqa.operators.primitive import FilterOperator

        if isinstance(where_op, FilterOperator) and where_op.source is None:
            return FilterOperator(where_op.field, where_op.predicate, source=source_op)
        from uqa.operators.boolean import IntersectOperator

        return IntersectOperator([source_op, where_op])

    # -- Constant folding --------------------------------------------------

    # Side-effecting functions that must not be folded at compile time.
    _NO_FOLD_FUNCS = frozenset(
        {
            "random",
            "nextval",
            "currval",
            "now",
            "current_timestamp",
            "clock_timestamp",
            "statement_timestamp",
            "timeofday",
        }
    )

    def _fold_stmt_where(self, stmt: SelectStmt) -> SelectStmt:
        """Return a new SelectStmt with the WHERE clause constant-folded."""
        folded = self._fold_constants(stmt.whereClause)
        if folded is stmt.whereClause:
            return stmt
        # pglast AST nodes are dataclass-like; shallow-copy with new where
        import copy

        new_stmt = copy.copy(stmt)
        new_stmt.whereClause = folded
        return new_stmt

    def _fold_constants(self, node: Any) -> Any:
        """Bottom-up constant folding for AST expressions.

        Evaluates constant sub-expressions at compile time.  Conservative
        scope: only folds A_Expr with A_Const operands and BoolExpr with
        fully constant args.  Skips ColumnRef, side-effecting functions,
        and SubLink nodes.
        """
        if node is None:
            return None

        if isinstance(node, A_Const):
            return node

        if isinstance(node, ColumnRef):
            return node

        if isinstance(node, A_Expr):
            return self._fold_a_expr(node)

        if isinstance(node, BoolExpr):
            return self._fold_bool_expr(node)

        # FuncCall: fold only if all args are constant and function is pure
        if isinstance(node, FuncCall):
            return self._fold_func_call(node)

        return node

    def _fold_a_expr(self, node: A_Expr) -> Any:
        """Try to fold an A_Expr with constant operands."""
        new_lexpr = self._fold_constants(node.lexpr)
        new_rexpr = self._fold_constants(node.rexpr)

        if isinstance(new_lexpr, A_Const) and isinstance(new_rexpr, A_Const):
            try:
                from uqa.sql.expr_evaluator import ExprEvaluator

                evaluator = ExprEvaluator()
                folded = A_Expr(
                    kind=node.kind,
                    name=node.name,
                    lexpr=new_lexpr,
                    rexpr=new_rexpr,
                )
                result = evaluator.evaluate(folded, {})
                return self._value_to_a_const(result)
            except Exception:
                pass

        if new_lexpr is not node.lexpr or new_rexpr is not node.rexpr:
            return A_Expr(
                kind=node.kind,
                name=node.name,
                lexpr=new_lexpr,
                rexpr=new_rexpr,
            )
        return node

    def _fold_bool_expr(self, node: BoolExpr) -> Any:
        """Try to fold a BoolExpr, including partial evaluation.

        AND: remove True constants; if any False -> False.
        OR:  remove False constants; if any True -> True.
        NOT: fold if operand is constant.
        """
        new_args = tuple(self._fold_constants(arg) for arg in node.args)

        # Full fold: all args are constants
        if all(isinstance(a, A_Const) for a in new_args):
            try:
                from uqa.sql.expr_evaluator import ExprEvaluator

                evaluator = ExprEvaluator()
                folded = BoolExpr(boolop=node.boolop, args=new_args)
                result = evaluator.evaluate(folded, {})
                return self._value_to_a_const(result)
            except Exception:
                pass

        # Partial fold for AND/OR with some constant args
        if node.boolop == BoolExprType.AND_EXPR:
            surviving: list = []
            for arg in new_args:
                if isinstance(arg, A_Const) and not arg.isnull:
                    val = self._const_to_bool(arg)
                    if val is False:
                        return A_Const(val=PgBoolean(boolval=False))
                    # True -> skip (identity element for AND)
                    continue
                surviving.append(arg)
            if not surviving:
                return A_Const(val=PgBoolean(boolval=True))
            if len(surviving) == 1:
                return surviving[0]
            return BoolExpr(boolop=BoolExprType.AND_EXPR, args=tuple(surviving))

        if node.boolop == BoolExprType.OR_EXPR:
            surviving = []
            for arg in new_args:
                if isinstance(arg, A_Const) and not arg.isnull:
                    val = self._const_to_bool(arg)
                    if val is True:
                        return A_Const(val=PgBoolean(boolval=True))
                    # False -> skip (identity element for OR)
                    continue
                surviving.append(arg)
            if not surviving:
                return A_Const(val=PgBoolean(boolval=False))
            if len(surviving) == 1:
                return surviving[0]
            return BoolExpr(boolop=BoolExprType.OR_EXPR, args=tuple(surviving))

        if new_args != tuple(node.args):
            return BoolExpr(boolop=node.boolop, args=new_args)
        return node

    @staticmethod
    def _const_to_bool(node: A_Const) -> bool | None:
        """Extract boolean truth value from an A_Const."""
        if node.isnull:
            return None
        val = node.val
        if isinstance(val, PgBoolean):
            return val.boolval
        if isinstance(val, PgInteger):
            return val.ival != 0
        if isinstance(val, PgFloat):
            return float(val.fval) != 0.0
        if isinstance(val, PgString):
            return len(val.sval) > 0
        return None

    def _fold_func_call(self, node: FuncCall) -> Any:
        """Fold a FuncCall if all args are constant and function is pure."""
        func_name = node.funcname[-1].sval.lower() if node.funcname else ""
        if func_name in self._NO_FOLD_FUNCS:
            return node

        if node.args is None:
            return node

        new_args = tuple(self._fold_constants(arg) for arg in node.args)
        if new_args != tuple(node.args):
            return FuncCall(
                funcname=node.funcname,
                args=new_args,
                agg_star=node.agg_star,
                agg_distinct=node.agg_distinct,
                func_variadic=node.func_variadic,
                funcformat=node.funcformat,
                over=node.over,
            )
        return node

    @staticmethod
    def _value_to_a_const(value: Any) -> A_Const:
        """Convert a Python value to an A_Const AST node."""
        if value is None:
            return A_Const(isnull=True)
        if isinstance(value, bool):
            return A_Const(val=PgBoolean(boolval=value))
        if isinstance(value, int):
            return A_Const(val=PgInteger(ival=value))
        if isinstance(value, float):
            return A_Const(val=PgFloat(fval=str(value)))
        if isinstance(value, str):
            return A_Const(val=PgString(sval=value))
        raise ValueError(f"Cannot convert {type(value).__name__} to A_Const")

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
            if isinstance(val, PgBoolean):
                return val.boolval
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

    def _extract_vector_arg(self, node: Any) -> Any:
        """Extract a vector from an ARRAY literal or a $N parameter.

        Returns a numpy float32 array.
        """
        import numpy as np

        if isinstance(node, A_ArrayExpr):
            values = [self._extract_const_value(elem) for elem in node.elements]
            return np.array(values, dtype=np.float32)
        if isinstance(node, ParamRef):
            idx = node.number - 1  # $1 -> index 0
            if idx < 0 or idx >= len(self._params):
                raise ValueError(f"No value supplied for parameter ${node.number}")
            return np.asarray(self._params[idx], dtype=np.float32)
        raise ValueError(
            f"Expected ARRAY literal or $N parameter for vector, "
            f"got {type(node).__name__}"
        )

    def _extract_insert_value(self, node: Any) -> Any:
        """Extract a value from an INSERT VALUES clause.

        Handles A_Const (scalars), A_ArrayExpr (vector/array literals),
        FuncCall for POINT(x, y), and TypeCast (e.g. '...'::jsonb).
        """
        if isinstance(node, FuncCall):
            name = node.funcname[-1].sval.lower()
            if name == "point":
                pt_args = node.args or ()
                if len(pt_args) != 2:
                    raise ValueError("POINT() requires exactly 2 arguments")
                x = float(self._extract_const_value(pt_args[0]))
                y = float(self._extract_const_value(pt_args[1]))
                return [x, y]
            # Other function calls in INSERT VALUES: evaluate as scalar.
            return self._extract_const_value(node)
        if isinstance(node, A_ArrayExpr):
            if node.elements is None:
                return []
            return [self._extract_const_value(elem) for elem in node.elements]
        if isinstance(node, TypeCast):
            from uqa.sql.expr_evaluator import _cast_value

            value = self._extract_insert_value(node.arg)
            type_name = node.typeName.names[-1].sval.lower()
            if node.typeName.arrayBounds is not None:
                return value if isinstance(value, list) else [value]
            return _cast_value(value, type_name)
        return self._extract_const_value(node)


class _NamedGraphOperatorWrapper:
    """Wraps a graph operator to execute against a named graph store.

    Injects the named graph into the execution context so that graph
    operators (TemporalTraverseOperator, etc.) that read ctx.graph_store
    see the named graph instead of the per-table graph.
    """

    def __init__(self, inner: Any, graph_store: Any) -> None:
        self.inner = inner
        self.graph_store = graph_store

    def execute(self, context: Any) -> PostingList:
        from dataclasses import replace

        from uqa.operators.base import ExecutionContext

        if isinstance(context, ExecutionContext):
            ctx = replace(context, graph_store=self.graph_store)
        else:
            ctx = ExecutionContext(graph_store=self.graph_store)
        return self.inner.execute(ctx)

    def cost_estimate(self, stats: Any) -> float:
        return getattr(self.inner, "cost_estimate", lambda _: 100.0)(stats)


class _ScanOperator:
    """Scans all documents in the store."""

    def execute(self, context: Any) -> PostingList:
        all_ids = sorted(context.document_store.doc_ids)
        return PostingList.from_sorted(
            [PostingEntry(d, Payload(score=0.0)) for d in all_ids]
        )

    def cost_estimate(self, stats: Any) -> float:
        return float(stats.total_docs)


class _TableScanOperator:
    """Scans a specific table, eagerly loading document fields.

    Unlike _ScanOperator (which leaves payload.fields empty),
    this operator populates fields from the document store so that
    join operators can match on field values.

    When *alias* is provided (e.g. ``"e"`` from ``FROM employees e``),
    fields are dual-keyed: both qualified (``e.name``) and unqualified
    (``name``) keys are stored.  This allows downstream join operators
    to merge fields without collision on qualified keys, while
    ExprEvaluator resolves ``e.name`` via qualified lookup.
    """

    def __init__(self, table: Table, alias: str | None = None) -> None:
        self._table = table
        self._alias = alias

    def execute(self, context: Any) -> PostingList:
        entries: list[PostingEntry] = []
        alias = self._alias
        # Pre-fetch column names so NULL columns are explicitly present.
        # The document store may omit NULL values; for JOIN semantics
        # we need them to prevent unqualified fallback to the wrong table.
        col_names = list(self._table.columns.keys()) if self._table.columns else []
        for doc_id in sorted(self._table.document_store.doc_ids):
            doc = self._table.document_store.get(doc_id)
            fields = dict(doc) if doc else {}
            for col_name in col_names:
                if col_name not in fields:
                    fields[col_name] = None
            if alias:
                qualified = {f"{alias}.{k}": v for k, v in fields.items()}
                fields = {**qualified, **fields}
            entries.append(PostingEntry(doc_id, Payload(score=0.0, fields=fields)))
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: Any) -> float:
        return float(len(self._table.document_store.doc_ids))


class _FilteredScanOperator:
    """Wraps a scan operator and filters its output using a WHERE predicate.

    Used to push single-table WHERE predicates below join operators,
    reducing the number of rows that enter the join.  The predicate is
    an AST node evaluated via ExprEvaluator against each entry's fields.
    """

    def __init__(
        self,
        scan: _TableScanOperator,
        where_node: Any,
        subquery_executor: Any,
    ) -> None:
        self._scan = scan
        self._where_node = where_node
        self._subquery_executor = subquery_executor

    def execute(self, context: Any) -> PostingList:
        from uqa.sql.expr_evaluator import ExprEvaluator

        pl = self._scan.execute(context)
        evaluator = ExprEvaluator(subquery_executor=self._subquery_executor)
        filtered: list[PostingEntry] = []
        for entry in pl:
            if evaluator.evaluate(self._where_node, entry.payload.fields):
                filtered.append(entry)
        return PostingList.from_sorted(filtered)

    def cost_estimate(self, stats: Any) -> float:
        base = self._scan.cost_estimate(stats)
        return base * 0.5


class _ForeignTableScanOperator:
    """Scans a foreign table by delegating to the appropriate FDW handler.

    The handler returns a ``pyarrow.Table`` which is converted into a
    :class:`PostingList` for seamless integration with UQA's query
    pipeline (joins, WHERE, GROUP BY, ORDER BY, etc.).

    When :attr:`pushdown_predicates` is set, the predicates are forwarded
    to the handler's ``scan()`` so the data source can filter rows
    server-side (e.g. Hive partition pruning).
    """

    def __init__(
        self,
        foreign_table: Any,
        engine: Any,
        alias: str | None = None,
    ) -> None:
        self._foreign_table = foreign_table
        self._engine = engine
        self._alias = alias
        self.pushdown_predicates: list | None = None

    def _get_handler(self) -> Any:
        """Lazily obtain or create the FDW handler for this table's server."""
        from uqa.fdw.arrow_handler import ArrowFlightSQLFDWHandler
        from uqa.fdw.duckdb_handler import DuckDBFDWHandler

        server_name = self._foreign_table.server_name
        handler = self._engine._fdw_handlers.get(server_name)
        if handler is not None:
            return handler

        server = self._engine._foreign_servers[server_name]
        if server.fdw_type == "duckdb_fdw":
            handler = DuckDBFDWHandler(server)
        elif server.fdw_type == "arrow_fdw":
            handler = ArrowFlightSQLFDWHandler(server)
        else:
            raise ValueError(f"Unsupported FDW type: '{server.fdw_type}'")
        self._engine._fdw_handlers[server_name] = handler
        return handler

    def execute(self, context: Any) -> PostingList:
        handler = self._get_handler()
        arrow_table = handler.scan(
            self._foreign_table,
            predicates=self.pushdown_predicates,
        )

        col_names = list(self._foreign_table.columns.keys())
        alias = self._alias

        entries: list[PostingEntry] = []
        for i in range(arrow_table.num_rows):
            doc_id = i + 1
            fields: dict[str, Any] = {}
            for col in col_names:
                fields[col] = arrow_table.column(col)[i].as_py()
            if alias:
                qualified = {f"{alias}.{k}": v for k, v in fields.items()}
                fields = {**qualified, **fields}
            entries.append(PostingEntry(doc_id, Payload(score=0.0, fields=fields)))
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: Any) -> float:
        return 10000.0


def _entry_doc_id(entry: object) -> int:
    """Extract doc_id from either PostingEntry or GeneralizedPostingEntry."""
    if hasattr(entry, "doc_ids"):
        return entry.doc_ids[0]
    return entry.doc_id


def _get_join_entries(source: object, context: object) -> list:
    """Execute a source operator and return its entries as a list."""
    if hasattr(source, "execute"):
        pl = source.execute(context)
        return list(pl)
    return list(source)


class _ExprJoinOperator:
    """Nested-loop join with arbitrary ON expression evaluation.

    Used for non-equality join conditions (e.g. ``ON a.x >= b.y``)
    and compound conditions (e.g. ``ON a.x >= b.y AND a.x <= b.z``).
    Falls back to O(N*M) nested loop since hash join requires equality.
    """

    def __init__(
        self,
        left: object,
        right: object,
        quals: Any,
        join_type: int,
    ) -> None:
        self._left = left
        self._right = right
        self._quals = quals
        self._join_type = join_type

    def execute(self, context: object) -> Any:
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator()
        left_entries = _get_join_entries(self._left, context)
        right_entries = _get_join_entries(self._right, context)

        jt = self._join_type
        quals = self._quals

        if jt == JoinType.JOIN_INNER:
            return self._inner(evaluator, quals, left_entries, right_entries)
        if jt == JoinType.JOIN_LEFT:
            return self._left_outer(evaluator, quals, left_entries, right_entries)
        if jt == JoinType.JOIN_RIGHT:
            return self._right_outer(evaluator, quals, left_entries, right_entries)
        if jt == JoinType.JOIN_FULL:
            return self._full_outer(evaluator, quals, left_entries, right_entries)
        raise ValueError(f"Unsupported join type for expression join: {jt}")

    @staticmethod
    def _inner(
        evaluator: Any,
        quals: Any,
        left_entries: list,
        right_entries: list,
    ) -> Any:
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload

        result: list = []
        for left in left_entries:
            for right in right_entries:
                merged = {
                    **left.payload.fields,
                    **right.payload.fields,
                }
                if evaluator.evaluate(quals, merged):
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(
                                _entry_doc_id(left),
                                _entry_doc_id(right),
                            ),
                            payload=Payload(
                                score=(left.payload.score + right.payload.score),
                                fields=merged,
                            ),
                        )
                    )
        return GeneralizedPostingList(result)

    @staticmethod
    def _left_outer(
        evaluator: Any,
        quals: Any,
        left_entries: list,
        right_entries: list,
    ) -> Any:
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload

        result: list = []
        for left in left_entries:
            matched = False
            for right in right_entries:
                merged = {
                    **left.payload.fields,
                    **right.payload.fields,
                }
                if evaluator.evaluate(quals, merged):
                    matched = True
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(
                                _entry_doc_id(left),
                                _entry_doc_id(right),
                            ),
                            payload=Payload(
                                score=(left.payload.score + right.payload.score),
                                fields=merged,
                            ),
                        )
                    )
            if not matched:
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(left),),
                        payload=Payload(
                            score=left.payload.score,
                            fields=dict(left.payload.fields),
                        ),
                    )
                )
        return GeneralizedPostingList(result)

    @staticmethod
    def _right_outer(
        evaluator: Any,
        quals: Any,
        left_entries: list,
        right_entries: list,
    ) -> Any:
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload

        result: list = []
        matched_right: set = set()
        for left in left_entries:
            for right in right_entries:
                merged = {
                    **left.payload.fields,
                    **right.payload.fields,
                }
                if evaluator.evaluate(quals, merged):
                    matched_right.add(_entry_doc_id(right))
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(
                                _entry_doc_id(left),
                                _entry_doc_id(right),
                            ),
                            payload=Payload(
                                score=(left.payload.score + right.payload.score),
                                fields=merged,
                            ),
                        )
                    )
        for right in right_entries:
            if _entry_doc_id(right) not in matched_right:
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(right),),
                        payload=Payload(
                            score=right.payload.score,
                            fields=dict(right.payload.fields),
                        ),
                    )
                )
        return GeneralizedPostingList(result)

    @staticmethod
    def _full_outer(
        evaluator: Any,
        quals: Any,
        left_entries: list,
        right_entries: list,
    ) -> Any:
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload

        result: list = []
        matched_right: set = set()
        for left in left_entries:
            matched = False
            for right in right_entries:
                merged = {
                    **left.payload.fields,
                    **right.payload.fields,
                }
                if evaluator.evaluate(quals, merged):
                    matched = True
                    matched_right.add(_entry_doc_id(right))
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(
                                _entry_doc_id(left),
                                _entry_doc_id(right),
                            ),
                            payload=Payload(
                                score=(left.payload.score + right.payload.score),
                                fields=merged,
                            ),
                        )
                    )
            if not matched:
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(left),),
                        payload=Payload(
                            score=left.payload.score,
                            fields=dict(left.payload.fields),
                        ),
                    )
                )
        for right in right_entries:
            if _entry_doc_id(right) not in matched_right:
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(right),),
                        payload=Payload(
                            score=right.payload.score,
                            fields=dict(right.payload.fields),
                        ),
                    )
                )
        return GeneralizedPostingList(result)


class _LateralJoinOperator:
    """LATERAL subquery join operator.

    For each row from the left source, executes the subquery with that
    row's columns available as correlated references, then produces
    the cross product of left rows with their corresponding subquery
    results.
    """

    def __init__(
        self,
        left: object,
        subquery: Any,
        alias: str,
        compiler: SQLCompiler,
    ) -> None:
        self._left = left
        self._subquery = subquery
        self._alias = alias
        self._compiler = compiler

    def execute(self, context: object) -> Any:
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload

        left_entries = _get_join_entries(self._left, context)
        result: list = []
        alias = self._alias

        for left_entry in left_entries:
            left_fields = left_entry.payload.fields

            # Inject left row columns into a temporary table so the
            # subquery WHERE clause can reference them via ExprEvaluator.
            # We create a temporary table with a single row that holds
            # the left side columns, then execute the subquery.
            sub_result = self._execute_lateral_subquery(left_fields)

            for row in sub_result.rows:
                # Build qualified right-side fields
                right_fields: dict[str, Any] = {}
                for k, v in row.items():
                    right_fields[k] = v
                    right_fields[f"{alias}.{k}"] = v

                merged = {**left_fields, **right_fields}
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(left_entry),),
                        payload=Payload(
                            score=left_entry.payload.score,
                            fields=merged,
                        ),
                    )
                )

        return GeneralizedPostingList(result)

    def _execute_lateral_subquery(self, left_fields: dict[str, Any]) -> SQLResult:
        """Execute the lateral subquery with left-row columns injected.

        Passes the left-row values as outer_row context to the subquery
        compiler, which threads them through to ExprEvaluator for
        correlated reference resolution -- no AST cloning needed.
        """
        # Build outer_row with both qualified and unqualified keys
        # so correlated ColumnRefs resolve correctly.
        outer_row: dict[str, Any] = dict(left_fields)

        return self._compiler._compile_select(self._subquery, outer_row=outer_row)

    def cost_estimate(self, stats: Any) -> float:
        return 1000.0


class _ExternalPriorSearchOperator:
    """Internal operator for Bayesian BM25 with external prior."""

    def __init__(
        self,
        source: Any,
        scorer: Any,
        terms: list[str],
        field: str | None,
        document_store: Any,
    ) -> None:
        self.source = source
        self.scorer = scorer
        self.terms = terms
        self.field = field
        self.document_store = document_store

    def execute(self, context: Any) -> PostingList:
        from uqa.core.posting_list import PostingList as PL

        source_pl = self.source.execute(context)
        doc_store = self.document_store or context.document_store
        idx = context.inverted_index
        entries: list[PostingEntry] = []

        for entry in source_pl:
            doc_id = entry.doc_id
            doc_fields = doc_store.get(doc_id) if doc_store else {}
            if doc_fields is None:
                doc_fields = {}
            tf = len(entry.payload.positions) if entry.payload.positions else 1
            field_key = self.field or "_default"
            doc_length = idx.get_doc_length(doc_id, field_key) if idx else tf
            doc_freq = len(source_pl)

            score = self.scorer.score_with_prior(tf, doc_length, doc_freq, doc_fields)
            entries.append(PostingEntry(doc_id, Payload(score=score)))

        return PL.from_sorted(entries)

    def cost_estimate(self, stats: Any) -> float:
        return getattr(self.source, "cost_estimate", lambda _: 100.0)(stats) * 1.1


class _CalibratedKNNOperator(Operator):
    """KNN search with scores calibrated to probabilities.

    P_vector = (1 + cosine_similarity) / 2  (Definition 7.1.2, Paper 3)

    Maps cosine similarity [-1, 1] to probability [0, 1]:
    - similarity = 1.0  ->  P = 1.0  (identical)
    - similarity = 0.0  ->  P = 0.5  (orthogonal, neutral)
    - similarity = -1.0 ->  P = 0.0  (opposite)
    """

    def __init__(self, query_vector: Any, k: int, field: str = "embedding") -> None:
        self.query_vector = query_vector
        self.k = k
        self.field = field

    def execute(self, context: Any) -> PostingList:
        from uqa.operators.primitive import _brute_force_knn

        vec_idx = context.vector_indexes.get(self.field)
        if vec_idx is not None:
            raw_pl = vec_idx.search_knn(self.query_vector, self.k)
        else:
            raw_pl = _brute_force_knn(context, self.field, self.query_vector, self.k)
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
        self,
        expr_node: Any,
        subquery_executor: Any = None,
        compiler: Any = None,
    ) -> None:
        self.expr_node = expr_node
        self._subquery_executor = subquery_executor
        self._compiler = compiler

    def execute(self, context: Any) -> PostingList:
        from uqa.sql.expr_evaluator import ExprEvaluator

        outer_row = (
            getattr(self._compiler, "_correlated_outer_row", None)
            if self._compiler is not None
            else None
        )
        evaluator = ExprEvaluator(
            subquery_executor=self._subquery_executor,
            outer_row=outer_row,
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
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: Any) -> float:
        return float(stats.total_docs)


def _op_to_predicate(op_name: str, value: Any) -> Predicate:
    mapping: dict[str, type[Predicate]] = {
        "=": Equals,
        "!=": NotEquals,
        "<>": NotEquals,
        ">": GreaterThan,
        ">=": GreaterThanOrEqual,
        "<": LessThan,
        "<=": LessThanOrEqual,
    }
    cls = mapping.get(op_name)
    if cls is None:
        raise ValueError(f"Unsupported operator: {op_name}")
    return cls(value)
