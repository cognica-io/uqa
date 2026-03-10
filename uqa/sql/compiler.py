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
  knn_match(field, vector, k)        -- KNN vector search
  traverse_match(start, 'label', k)  -- graph reachability as a scored signal
  path_filter('path', value)         -- hierarchical path filter (equality)
  path_filter('path', 'op', value)   -- hierarchical path filter with operator
  vector_exclude(field, pos, neg, k, threshold) -- vector exclusion

  Vector arguments accept ARRAY literals or $N parameter references:
    knn_match(embedding, ARRAY[0.1, 0.2, ...], 5)
    knn_match(embedding, $1, 5)  -- with params=[query_vec]

Fusion meta-functions (WHERE clause):
  fuse_log_odds(sig1, sig2, ...[, alpha]) -- log-odds conjunction (Paper 4)
  fuse_prob_and(sig1, sig2, ...)          -- probabilistic AND
  fuse_prob_or(sig1, sig2, ...)           -- probabilistic OR
  fuse_prob_not(signal)                   -- probabilistic NOT (complement)

SELECT scalar functions:
  path_agg('path', 'func')          -- per-row nested array aggregation
  path_value('path')                 -- access nested field value

FROM-clause table functions:
  traverse(start_id, 'label', max_hops) -- graph traversal
  rpq('path_expr', start_id)            -- regular path query
  regexp_split_to_table(str, pattern [, flags]) -- split string by regex
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from pglast import parse_sql
from pglast.ast import (
    A_ArrayExpr,
    A_Const,
    A_Expr,
    A_Star,
    AlterSeqStmt,
    AlterTableStmt,
    BoolExpr,
    Boolean as PgBoolean,
    CaseExpr,
    CoalesceExpr,
    ColumnDef as PgColumnDef,
    ColumnRef,
    Constraint as PgConstraint,
    CreateSeqStmt,
    CreateStmt,
    CreateTableAsStmt,
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
    RangeSubselect,
    RangeVar,
    RenameStmt,
    SelectStmt,
    SortBy,
    String as PgString,
    SubLink,
    TransactionStmt,
    TruncateStmt,
    TypeCast,
    UpdateStmt,
    VacuumStmt,
    ViewStmt,
    PrepareStmt,
    ExecuteStmt,
    DeallocateStmt,
    ParamRef,
)
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
from pglast.enums.nodes import JoinType, OnConflictAction

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
from uqa.sql.table import (
    ColumnDef,
    ForeignKeyDef,
    Table,
    resolve_type,
    _AUTO_INCREMENT_TYPES,
)

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

_AGG_FUNC_NAMES = frozenset({
    "count", "sum", "avg", "min", "max", "string_agg",
    "array_agg", "bool_and", "bool_or",
    "stddev", "stddev_pop", "stddev_samp",
    "variance", "var_pop", "var_samp",
    "percentile_cont", "percentile_disc", "mode",
    "json_object_agg", "jsonb_object_agg",
    "corr", "covar_pop", "covar_samp",
    "regr_count", "regr_avgx", "regr_avgy",
    "regr_sxx", "regr_syy", "regr_sxy",
    "regr_slope", "regr_intercept", "regr_r2",
})

# Two-argument statistical aggregates where extra carries the x column.
_TWO_ARG_STAT_AGGS = frozenset({
    "corr", "covar_pop", "covar_samp",
    "regr_count", "regr_avgx", "regr_avgy",
    "regr_sxx", "regr_syy", "regr_sxy",
    "regr_slope", "regr_intercept", "regr_r2",
})


class SQLCompiler:
    """Compiles SQL statements into UQA operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._params: list[Any] = []
        self._expanded_views: list[str] = []
        self._shadowed_tables: dict[str, Table] = {}

    def execute(self, sql: str, params: list[Any] | None = None) -> SQLResult:
        """Parse and execute a SQL statement.

        *params* is an optional list of parameter values for ``$1``,
        ``$2``, ... placeholders.  Values can be any Python object
        (scalars, numpy arrays, etc.).
        """
        self._params = list(params) if params else []
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
                        [attr.sval for attr in elt.fk_attrs]
                        if elt.fk_attrs else []
                    )
                    pk_cols = (
                        [attr.sval for attr in elt.pk_attrs]
                        if elt.pk_attrs else []
                    )
                    for fk_col, pk_col in zip(fk_cols, pk_cols):
                        fk_defs.append(ForeignKeyDef(
                            column=fk_col,
                            ref_table=ref_table,
                            ref_column=pk_col,
                        ))
                continue

            col, check_expr, fk_def = self._parse_column_def(elt)
            columns.append(col)
            if check_expr is not None:
                check_exprs.append((col.name, check_expr))
            if fk_def is not None:
                fk_defs.append(fk_def)

        # Temporary tables always use in-memory storage, even when
        # the engine has a persistent catalog.
        is_temp = stmt.relation.relpersistence == 't'
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
            columns.append(ColumnDef(
                name=col_name,
                type_name=type_name,
                python_type=py_type,
            ))

        # Temporary tables always use in-memory storage
        is_temp = stmt.into.rel.relpersistence == 't'
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
        self, node: Any,
    ) -> tuple[ColumnDef, Any, ForeignKeyDef | None]:
        """Parse a ColumnDef node into (ColumnDef, check_expr, fk_def).

        Returns a triple of column definition, optional CHECK expression
        AST node, and optional FOREIGN KEY definition.
        """
        col_name: str = node.colname
        type_names = node.typeName.names
        raw_type, python_type = resolve_type(
            type_names, node.typeName.arrayBounds
        )

        # VECTOR(N) -- extract dimensions from type modifier
        vector_dimensions: int | None = None
        if raw_type == "vector":
            typmods = node.typeName.typmods
            if typmods and isinstance(typmods[0], A_Const):
                vector_dimensions = self._extract_int_value(typmods[0])
            else:
                raise ValueError(
                    f"VECTOR column '{col_name}' requires dimensions, "
                    f"e.g. VECTOR(128)"
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
                        constraint.pk_attrs[0].sval
                        if constraint.pk_attrs
                        else None
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

        return ColumnDef(
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
        ), check_expr, fk_def

    def _register_fk_validators(
        self, table: Table, fk_defs: list[ForeignKeyDef],
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
                for doc_id in parent.document_store.doc_ids:
                    if parent.document_store.get_field(doc_id, _ref_col) == value:
                        return
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
                for child_id in child.document_store.doc_ids:
                    child_val = child.document_store.get_field(
                        child_id, _fk_col
                    )
                    if child_val == ref_value:
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
                for doc_id in parent.document_store.doc_ids:
                    if parent.document_store.get_field(doc_id, _ref_col) == new_value:
                        return
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
                for child_id in child.document_store.doc_ids:
                    child_val = child.document_store.get_field(
                        child_id, _fk_col
                    )
                    if child_val == old_value:
                        raise ValueError(
                            f"FOREIGN KEY constraint violated: "
                            f"key ({_ref_col})=({old_value}) in table "
                            f"'{_ref_table}' is still referenced from "
                            f"table '{_child_table}'"
                        )

            if parent_table is not None:
                parent_table.fk_update_validators.append(
                    _validate_parent_update
                )
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
            pending_del = getattr(
                table, "_pending_parent_delete_validators", []
            )
            remaining_del: list[tuple[str, Any]] = []
            for ref_table_name, validator in pending_del:
                parent = engine._tables.get(ref_table_name)
                if parent is not None:
                    if validator not in parent.fk_delete_validators:
                        parent.fk_delete_validators.append(validator)
                else:
                    remaining_del.append((ref_table_name, validator))
            table._pending_parent_delete_validators = remaining_del

            pending_upd = getattr(
                table, "_pending_parent_update_validators", []
            )
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
                self._engine._temp_tables.discard(table_name)
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
    # DDL: ALTER TABLE / RENAME / TRUNCATE
    # ==================================================================

    def _compile_alter_table(self, stmt: AlterTableStmt) -> SQLResult:
        table_name = stmt.relation.relname
        table = self._get_table(table_name)

        for cmd in stmt.cmds:
            at = AlterTableType(cmd.subtype)

            if at == AlterTableType.AT_AddColumn:
                col_def, check_expr, fk_def = self._parse_column_def(
                    cmd.def_
                )
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
                        (col_def.name,
                         lambda row, e=check_expr, v=ev: v.evaluate(e, row))
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
                        f"Column '{col_name}' does not exist "
                        f"in table '{table_name}'"
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
                        f"Column '{col_name}' does not exist "
                        f"in table '{table_name}'"
                    )
                if cmd.def_ is not None:
                    table.columns[col_name].default = (
                        self._extract_const_value(cmd.def_)
                    )
                else:
                    table.columns[col_name].default = None

            elif at == AlterTableType.AT_SetNotNull:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist "
                        f"in table '{table_name}'"
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
                        f"Column '{col_name}' does not exist "
                        f"in table '{table_name}'"
                    )
                table.columns[col_name].not_null = False

            elif at == AlterTableType.AT_AlterColumnType:
                col_name = cmd.name
                if col_name not in table.columns:
                    raise ValueError(
                        f"Column '{col_name}' does not exist "
                        f"in table '{table_name}'"
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
                raise ValueError(
                    f"Unsupported ALTER TABLE subcommand: {at.name}"
                )

        return SQLResult([], [])

    def _compile_rename(self, stmt: RenameStmt) -> SQLResult:
        rt = ObjectType(stmt.renameType)

        if rt == ObjectType.OBJECT_TABLE:
            old_name = stmt.relation.relname
            new_name = stmt.newname
            table = self._get_table(old_name)
            if new_name in self._engine._tables:
                raise ValueError(
                    f"Table '{new_name}' already exists"
                )
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
                    f"Column '{old_col}' does not exist "
                    f"in table '{table_name}'"
                )
            if new_col in table.columns:
                raise ValueError(
                    f"Column '{new_col}' already exists "
                    f"in table '{table_name}'"
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
            table.graph_store.clear()
            table._next_id = 1
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
            conflict_cols = [
                elem.name for elem in on_conflict.infer.indexElems
            ]

        # Insert rows with ON CONFLICT and RETURNING support
        returning_rows: list[dict[str, Any]] = []
        inserted = 0
        for src_row in source_rows:
            if on_conflict is not None and conflict_cols:
                existing_id = self._find_conflict(
                    table, conflict_cols, src_row
                )
                if existing_id is not None:
                    action = OnConflictAction(on_conflict.action)
                    if action == OnConflictAction.ONCONFLICT_NOTHING:
                        continue
                    # DO UPDATE SET ...
                    self._do_conflict_update(
                        table, existing_id, src_row,
                        on_conflict.targetList,
                    )
                    if stmt.returningList:
                        doc = table.document_store.get(existing_id)
                        if doc:
                            returning_rows.append(
                                self._project_returning(
                                    doc, stmt.returningList, table
                                )
                            )
                    inserted += 1
                    continue

            doc_id, _ = table.insert(src_row)
            inserted += 1
            if stmt.returningList:
                doc = table.document_store.get(doc_id)
                if doc:
                    returning_rows.append(
                        self._project_returning(
                            doc, stmt.returningList, table
                        )
                    )

        if stmt.returningList:
            cols = self._returning_columns(
                stmt.returningList, table
            )
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
        evaluator = ExprEvaluator(subquery_executor=self._compile_select)

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
        table.document_store.put(doc_id, new_doc)
        text_fields = {
            k: v for k, v in new_doc.items() if isinstance(v, str)
        }
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
        evaluator = ExprEvaluator(subquery_executor=self._compile_select)
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

    def _returning_columns(
        self, returning_list: tuple, table: Table
    ) -> list[str]:
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
                    f"Unknown column '{col_name}' "
                    f"for table '{table_name}'"
                )
            set_targets.append((col_name, target.val))

        from uqa.sql.expr_evaluator import ExprEvaluator
        evaluator = ExprEvaluator(subquery_executor=self._compile_select)

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

            # Write updated document
            table.document_store.put(doc_id, new_doc)

            # Re-index text fields
            text_fields = {
                k: v for k, v in new_doc.items()
                if isinstance(v, str)
            }
            if text_fields:
                table.inverted_index.add_document(doc_id, text_fields)

            if stmt.returningList:
                returning_rows.append(
                    self._project_returning(
                        new_doc, stmt.returningList, table
                    )
                )
            updated += 1

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
        return SQLResult(["updated"], [{"updated": updated}])

    def _compile_update_from(
        self, stmt: UpdateStmt, table: Table
    ) -> SQLResult:
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

        evaluator = ExprEvaluator(subquery_executor=self._compile_select)

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
                list(itertools.product(*from_row_lists))
                if from_row_lists
                else [()]
            )

            for combo in from_combos:
                merged = dict(target_row)
                for from_row in combo:
                    merged.update(from_row)

                if stmt.whereClause is not None:
                    if not evaluator.evaluate(stmt.whereClause, merged):
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
                table.document_store.put(doc_id, new_doc)
                text_fields = {
                    k: v for k, v in new_doc.items()
                    if isinstance(v, str)
                }
                if text_fields:
                    table.inverted_index.add_document(doc_id, text_fields)

                if stmt.returningList:
                    returning_rows.append(
                        self._project_returning(
                            new_doc, stmt.returningList, table
                        )
                    )
                updated += 1
                break  # Only update once per target row

        # Clean up expanded FROM tables
        for name in list(self._expanded_views):
            if name in self._shadowed_tables:
                self._engine._tables[name] = (
                    self._shadowed_tables.pop(name)
                )
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
                        self._project_returning(
                            doc, stmt.returningList, table
                        )
                    )
            table.inverted_index.remove_document(doc_id)
            table.document_store.delete(doc_id)
            deleted += 1

        if stmt.returningList:
            cols = self._returning_columns(stmt.returningList, table)
            return SQLResult(cols, returning_rows)
        return SQLResult(["deleted"], [{"deleted": deleted}])

    def _compile_delete_using(
        self, stmt: DeleteStmt, table: Table
    ) -> SQLResult:
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

        evaluator = ExprEvaluator(subquery_executor=self._compile_select)

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
                list(itertools.product(*using_row_lists))
                if using_row_lists
                else [()]
            )

            for combo in using_combos:
                merged = dict(target_row)
                for using_row in combo:
                    merged.update(using_row)

                if stmt.whereClause is not None:
                    if not evaluator.evaluate(stmt.whereClause, merged):
                        continue

                if stmt.returningList:
                    returning_rows.append(
                        self._project_returning(
                            target_doc, stmt.returningList, table
                        )
                    )
                to_delete.append(doc_id)
                break  # Only delete once per row

        deleted = 0
        for doc_id in to_delete:
            table.inverted_index.remove_document(doc_id)
            table.document_store.delete(doc_id)
            deleted += 1

        # Clean up expanded USING tables
        for name in list(self._expanded_views):
            if name in self._shadowed_tables:
                self._engine._tables[name] = (
                    self._shadowed_tables.pop(name)
                )
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
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.cost_model import CostModel

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

        # Apply deferred WHERE filters (for graph-sourced queries)
        if deferred_where is not None:
            physical = self._apply_deferred_where(physical, deferred_where)

        is_grouped = stmt.groupClause is not None
        is_agg_only = not is_grouped and self._has_aggregates(
            stmt.targetList
        )
        has_window = self._has_window_functions(stmt.targetList)
        expected_cols: list[str] | None = None

        if has_window:
            # Window functions: compute window values, then project
            win_specs = self._extract_window_specs(
                stmt.targetList, stmt.windowClause
            )
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
            group_cols = self._resolve_group_by_cols(
                stmt.groupClause, stmt.targetList
            )
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
                    physical, pre_targets,
                    subquery_executor=self._compile_select,
                )

            group_aliases = self._build_group_aliases(
                group_cols, stmt.targetList
            )
            physical = HashAggOp(
                physical, group_cols, agg_specs,
                spill_threshold=self._engine.spill_threshold,
                group_aliases=group_aliases,
            )

            if stmt.havingClause is not None:
                from uqa.execution.relational import ExprFilterOp
                physical = ExprFilterOp(
                    physical, stmt.havingClause,
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
                    physical, post_group_targets,
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
                physical, [], agg_specs,
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
                    physical, targets,
                    subquery_executor=self._compile_select,
                )
                expected_cols = [name for name, _ in targets]
            else:
                expected_cols = [a for a, *_ in agg_specs]

        else:
            is_star = self._is_select_star(stmt.targetList)
            if not is_star:
                use_expr = (
                    join_source
                    or self._has_computed_expressions(stmt.targetList)
                )
                if use_expr:
                    targets = self._build_expr_targets(stmt.targetList)
                    physical = ExprProjectOp(
                        physical, targets,
                        subquery_executor=self._compile_select,
                        sequences=self._engine._sequences,
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
            sort_keys = self._build_sort_keys(
                stmt.sortClause, stmt.targetList
            )
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
                if fn in ("text_match", "bayesian_match", "knn_match",
                          "traverse_match"):
                    continue
                return True
            if isinstance(val, (A_Const, A_ArrayExpr, A_Expr, CaseExpr,
                                TypeCast, CoalesceExpr, NullTest, SubLink,
                                MinMaxExpr, SQLValueFunction)):
                return True
        return False

    def _build_expr_targets(
        self, target_list: tuple
    ) -> list[tuple[str, Any]]:
        """Build (output_name, ast_node) pairs for ExprProjectOp.

        For text_match/bayesian_match function calls, wraps the node
        so the ExprEvaluator reads ``_score`` from the row instead.

        When multiple columns share the same unqualified name (e.g.
        ``e.name`` and ``d.name`` in a JOIN), the output names are
        disambiguated using qualified forms to avoid dict key collisions.
        """
        # First pass: collect inferred names and detect duplicates
        raw: list[tuple[str, str | None, Any]] = []
        name_counts: dict[str, int] = {}
        for target in target_list:
            name = self._infer_target_name(target)
            # Qualified name for ColumnRef with table alias
            qual_name: str | None = None
            val = target.val
            if (
                target.name is None
                and isinstance(val, ColumnRef)
                and len(val.fields) >= 2
                and hasattr(val.fields[0], "sval")
            ):
                qual_name = (
                    f"{val.fields[0].sval}.{val.fields[-1].sval}"
                )
            raw.append((name, qual_name, val))
            name_counts[name] = name_counts.get(name, 0) + 1

        # Second pass: build targets with disambiguation
        targets: list[tuple[str, Any]] = []
        for name, qual_name, val in raw:
            output_name = name
            if name_counts[name] > 1 and qual_name is not None:
                output_name = qual_name
            # text_match/bayesian_match -> read _score column
            if isinstance(val, FuncCall):
                fn = val.funcname[-1].sval.lower()
                if fn in ("text_match", "bayesian_match"):
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
                if (
                    isinstance(target.val, ColumnRef)
                    and isinstance(target.val.fields[-1], A_Star)
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
            if isinstance(s.node, A_Const) and isinstance(
                s.node.val, PgInteger
            ):
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
                        natural = (
                            f"{fn}_{col_arg}" if col_arg else fn
                        )
                    else:
                        natural = fn
                    cols.append(target.name or natural)
                else:
                    cols.append(
                        target.name or self._infer_target_name(target)
                    )
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
        self, group_clause: tuple, target_list: tuple | None,
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
            cte_names = self._materialize_ctes(
                stmt.withClause.ctes,
                recursive=bool(stmt.withClause.recursive),
            )

        try:
            return self._compile_select_body(
                stmt, explain=explain
            )
        finally:
            # Clean up CTE temporary tables
            for name in cte_names:
                self._engine._tables.pop(name, None)
            # Clean up materialized view / derived tables
            for name in self._expanded_views:
                if name in self._shadowed_tables:
                    self._engine._tables[name] = (
                        self._shadowed_tables.pop(name)
                    )
                else:
                    self._engine._tables.pop(name, None)
            self._expanded_views.clear()

    def _apply_deferred_where(self, physical: Any, where_node: Any) -> Any:
        """Apply WHERE predicates as physical filter on joined/graph rows.

        For simple column-to-constant comparisons, uses typed PhysFilterOp.
        For cross-table or complex expressions (e.g., a.id = b.user_id),
        falls back to ExprFilterOp using ExprEvaluator.
        """
        from uqa.execution.relational import (
            ExprFilterOp,
            FilterOp as PhysFilterOp,
        )
        from uqa.core.types import (
            Equals,
            NotEquals,
            GreaterThan,
            GreaterThanOrEqual,
            LessThan,
            LessThanOrEqual,
        )

        if isinstance(where_node, BoolExpr):
            if where_node.boolop == BoolExprType.AND_EXPR:
                for arg in where_node.args:
                    physical = self._apply_deferred_where(physical, arg)
                return physical

        if isinstance(where_node, A_Expr):
            kind = where_node.kind

            # Check if RHS is a constant (column-to-constant comparison)
            rhs_is_const = isinstance(
                where_node.rexpr, (A_Const, PgInteger, PgFloat, PgString)
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
                physical = PhysFilterOp(
                    physical, col_name, GreaterThanOrEqual(lo)
                )
                return PhysFilterOp(
                    physical, col_name, LessThanOrEqual(hi)
                )

        # Fallback: use ExprEvaluator for complex expressions
        # (e.g., cross-table column comparisons like a.id = b.user_id)
        return ExprFilterOp(
            physical, where_node,
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

        # 1. Resolve FROM clause -> (table | None, source_op | None)
        table, source_op = self._resolve_from(stmt.fromClause)

        # 2. Build execution context from resolved table
        ctx = self._context_for_table(table)

        # 3. Check if FROM is a graph source (traverse/rpq) or join.
        #    Graph/join-sourced queries defer relational WHERE to the
        #    physical layer because their entries are not single-table
        #    doc_ids from the document store.
        graph_source = self._is_graph_operator(source_op)
        join_source = self._is_join_operator(source_op)
        deferred_where = None

        # 4. WHERE clause
        if stmt.whereClause is not None:
            if graph_source or join_source:
                # Defer WHERE to physical ExprFilterOp layer
                deferred_where = stmt.whereClause
            else:
                where_op = self._compile_where(stmt.whereClause, ctx)
                if source_op is not None:
                    where_op = self._chain_on_source(where_op, source_op)
                source_op = where_op

        # 5. Optimize and execute operator tree
        if source_op is not None:
            source_op = self._optimize(source_op, ctx, table)
            if explain:
                return self._explain_plan(source_op, ctx)
            pl = self._execute_plan(source_op, ctx)
        else:
            if explain:
                return SQLResult(["plan"], [{"plan": "Seq Scan (full table)"}])
            pl = self._scan_all(ctx)

        # 6-12. Execute relational operations via physical operators
        return self._execute_relational(
            stmt, pl, ctx, table,
            deferred_where=deferred_where,
            join_source=join_source,
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
                if (isinstance(s.node, A_Const)
                        and isinstance(s.node.val, PgInteger)):
                    ordinal = s.node.val.ival
                    if 1 <= ordinal <= num_cols:
                        col = columns[ordinal - 1]
                    else:
                        raise ValueError(
                            f"ORDER BY position {ordinal} is not in "
                            f"select list"
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
            rows = rows[offset:offset + limit]

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
            rows = self._set_union(
                left.rows, right_rows, columns, is_all
            )
        elif op == SetOperation.SETOP_INTERSECT:
            rows = self._set_intersect(
                left.rows, right_rows, columns, is_all
            )
        elif op == SetOperation.SETOP_EXCEPT:
            rows = self._set_except(
                left.rows, right_rows, columns, is_all
            )
        else:
            raise ValueError(f"Unsupported set operation: {op}")

        # Apply ORDER BY / LIMIT on the combined result
        if stmt.sortClause is not None:
            sort_keys = self._build_sort_keys(
                stmt.sortClause, stmt.larg.targetList
            )
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

        right_keys = {
            tuple(r.get(c) for c in columns) for r in right_rows
        }
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

        right_keys = {
            tuple(r.get(c) for c in columns) for r in right_rows
        }
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

    def _materialize_ctes(
        self, ctes: tuple, *, recursive: bool = False
    ) -> list[str]:
        """Execute CTE queries and register results as temporary tables.

        When *recursive* is True (WITH RECURSIVE), CTEs whose query
        is a UNION/UNION ALL are executed via iterative fixpoint.

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
        alias_cols = (
            [s.sval for s in cte.aliascolnames]
            if cte.aliascolnames
            else None
        )

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

        for depth in range(self._MAX_RECURSIVE_DEPTH):
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
        self, view_name: str, query: SelectStmt
    ) -> tuple[Table, None]:
        """Materialize a view's stored query into a temporary table.

        The temporary table is registered in ``_engine._tables`` and
        tracked in ``_expanded_views`` for cleanup after the enclosing
        query completes.
        """
        result = self._compile_select(query)
        table = self._result_to_table(view_name, result)
        self._engine._tables[view_name] = table
        self._expanded_views.append(view_name)
        return table, None

    # -- Derived table (subquery in FROM) ------------------------------

    def _materialize_derived_table(
        self, node: RangeSubselect
    ) -> tuple[Table, None]:
        """Materialize a subquery in FROM as a temporary table."""
        alias = node.alias.aliasname if node.alias else "_derived"
        result = self._compile_select(node.subquery)
        table = self._result_to_table(alias, result)
        # Save the original table entry if the alias shadows a real table,
        # so it can be restored during cleanup.
        if alias in self._engine._tables:
            self._shadowed_tables[alias] = self._engine._tables[alias]
        self._engine._tables[alias] = table
        self._expanded_views.append(alias)
        return table, None

    def _result_to_table(self, name: str, result: SQLResult) -> Table:
        """Convert a SQLResult into a temporary in-memory Table."""
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
            col_defs.append(ColumnDef(
                name=col_name,
                type_name=_type_map.get(py_type, "text"),
                python_type=py_type,
            ))

        table = Table(name=name, columns=col_defs)
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

        return table

    # -- information_schema virtual tables -----------------------------

    def _build_information_schema_table(
        self, view_name: str,
    ) -> tuple[Table, None]:
        """Build virtual information_schema tables from engine metadata."""
        if view_name == "tables":
            return self._build_info_schema_tables()
        if view_name == "columns":
            return self._build_info_schema_columns()
        raise ValueError(
            f"Unknown information_schema view: '{view_name}'"
        )

    def _build_info_schema_tables(self) -> tuple[Table, None]:
        """Build information_schema.tables from engine state."""
        columns = [
            "table_catalog", "table_schema", "table_name", "table_type",
        ]
        rows: list[dict[str, Any]] = []
        for tname in sorted(self._engine._tables):
            rows.append({
                "table_catalog": "",
                "table_schema": "public",
                "table_name": tname,
                "table_type": "BASE TABLE",
            })
        for vname in sorted(self._engine._views):
            rows.append({
                "table_catalog": "",
                "table_schema": "public",
                "table_name": vname,
                "table_type": "VIEW",
            })
        result = SQLResult(columns, rows)
        name = "_info_schema_tables"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    _INFO_TYPE_DISPLAY: dict[str, str] = {
        "int2": "smallint", "int4": "integer", "int8": "bigint",
        "float4": "real", "float8": "double precision",
        "bool": "boolean",
    }

    def _build_info_schema_columns(self) -> tuple[Table, None]:
        """Build information_schema.columns from engine state."""
        columns = [
            "table_catalog", "table_schema", "table_name",
            "column_name", "ordinal_position", "data_type",
            "is_nullable",
        ]
        rows: list[dict[str, Any]] = []
        for tname in sorted(self._engine._tables):
            tbl = self._engine._tables[tname]
            for pos, (cname, cdef) in enumerate(
                tbl.columns.items(), start=1
            ):
                display_type = self._INFO_TYPE_DISPLAY.get(
                    cdef.type_name, cdef.type_name
                )
                rows.append({
                    "table_catalog": "",
                    "table_schema": "public",
                    "table_name": tname,
                    "column_name": cname,
                    "ordinal_position": pos,
                    "data_type": display_type,
                    "is_nullable": "NO" if cdef.not_null else "YES",
                })
        result = SQLResult(columns, rows)
        name = "_info_schema_columns"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    # -- pg_catalog virtual tables --------------------------------------

    def _build_pg_catalog_table(
        self, view_name: str,
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
            rows.append({
                "schemaname": "public",
                "tablename": tname,
                "tableowner": "",
                "tablespace": "",
            })
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
            rows.append({
                "schemaname": "public",
                "viewname": vname,
                "viewowner": "",
                "definition": "",
            })
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
                rows.append({
                    "schemaname": "public",
                    "tablename": idx_def.table_name,
                    "indexname": idx_def.name,
                    "tablespace": "",
                    "indexdef": (
                        f"CREATE INDEX {idx_def.name} ON "
                        f"{idx_def.table_name} "
                        f"({', '.join(idx_def.columns)})"
                    ),
                })
        result = SQLResult(columns, rows)
        name = "_pg_indexes"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    def _build_pg_type(self) -> tuple[Table, None]:
        """Build pg_catalog.pg_type with UQA-supported types."""
        columns = [
            "oid", "typname", "typnamespace", "typlen",
            "typtype", "typcategory",
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
            rows.append({
                "oid": oid,
                "typname": typname,
                "typnamespace": ns,
                "typlen": typlen,
                "typtype": typtype,
                "typcategory": typcat,
            })
        result = SQLResult(columns, rows)
        name = "_pg_type"
        table = self._result_to_table(name, result)
        self._engine._tables[name] = table
        self._expanded_views.append(name)
        return table, None

    # -- FROM clause ---------------------------------------------------

    def _resolve_from(
        self, from_clause: tuple | None
    ) -> tuple[Table | None, Any]:
        """Resolve FROM clause to (table, source_operator).

        Returns (table, None) for ``FROM table_name`` and
        (None, operator) for ``FROM func(...)``.

        Multiple FROM sources (``FROM a, b, c``) are treated as
        implicit CROSS JOINs built into a left-deep join tree.
        """
        if from_clause is None:
            return None, None

        if len(from_clause) == 1:
            table, op, _alias = self._resolve_from_single(from_clause[0])
            return table, op

        # Multiple FROM sources -> implicit CROSS JOIN chain
        from uqa.joins.cross import CrossJoinOperator

        table, op, alias = self._resolve_from_single(from_clause[0])
        if op is None:
            op = _TableScanOperator(table, alias=alias)

        for node in from_clause[1:]:
            # LATERAL subquery: re-evaluate per left row
            if isinstance(node, RangeSubselect) and node.lateral:
                lateral_alias = (
                    node.alias.aliasname if node.alias else "_lateral"
                )
                op = _LateralJoinOperator(
                    op, node.subquery, lateral_alias, self
                )
                continue

            right_table, right_op, right_alias = (
                self._resolve_from_single(node)
            )
            if right_op is None:
                right_op = _TableScanOperator(
                    right_table, alias=right_alias
                )
            op = CrossJoinOperator(op, right_op)
            # Keep first resolved table as context source
            if table is None:
                table = right_table

        return table, op

    def _resolve_from_single(
        self, node: Any
    ) -> tuple[Table | None, Any, str | None]:
        """Resolve a single FROM clause item.

        Returns ``(table, operator, alias)`` where *alias* is the
        table alias (e.g. ``e`` in ``FROM employees e``) or the table
        name itself when no alias is specified.
        """
        if isinstance(node, RangeVar):
            alias = (
                node.alias.aliasname
                if node.alias is not None
                else node.relname
            )
            # Virtual schema tables
            if node.schemaname == "information_schema":
                tbl, op = self._build_information_schema_table(
                    node.relname
                )
                return tbl, op, alias
            if node.schemaname == "pg_catalog":
                tbl, op = self._build_pg_catalog_table(node.relname)
                return tbl, op, alias
            table_name = node.relname
            table = self._engine._tables.get(table_name)
            if table is None:
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
            alias = (
                node.alias.aliasname if node.alias else None
            )
            return tbl, op, alias

        raise ValueError(f"Unsupported FROM clause: {type(node).__name__}")

    def _context_for_table(self, table: Table | None) -> ExecutionContext:
        """Build an ExecutionContext scoped to a specific table.

        When *table* is ``None`` (e.g. ``SELECT 1`` with no FROM clause)
        a minimal context with no storage is returned.
        """
        from uqa.operators.base import ExecutionContext

        index_manager = getattr(self._engine, "_index_manager", None)
        parallel_executor = getattr(
            self._engine, "_parallel_executor", None
        )

        if table is None:
            return ExecutionContext(
                index_manager=index_manager,
                parallel_executor=parallel_executor,
            )

        return ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
            vector_indexes=table.vector_indexes,
            graph_store=table.graph_store,
            block_max_index=table.block_max_index,
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

        if name == "cypher":
            return self._build_cypher_from(node, args)
        if name == "create_graph":
            return self._build_create_graph(args)
        if name == "drop_graph":
            return self._build_drop_graph(args)
        if name == "traverse":
            return self._build_traverse_from(args)
        if name == "rpq":
            return self._build_rpq_from(args)
        if name == "text_search":
            return self._build_text_search_from(args)
        if name == "generate_series":
            return self._build_generate_series(node, args)
        if name == "unnest":
            return self._build_unnest(node, args)
        if name in ("json_each", "jsonb_each", "json_each_text", "jsonb_each_text"):
            return self._build_json_each(node, args, as_text=name.endswith("_text"))
        if name in ("json_array_elements", "jsonb_array_elements",
                     "json_array_elements_text", "jsonb_array_elements_text"):
            return self._build_json_array_elements(node, args, as_text=name.endswith("_text"))
        if name == "regexp_split_to_table":
            return self._build_regexp_split_to_table(node, args)
        if name == "create_analyzer":
            return self._build_create_analyzer(args)
        if name == "drop_analyzer":
            return self._build_drop_analyzer(args)
        if name == "list_analyzers":
            return self._build_list_analyzers()
        raise ValueError(f"Unknown table function: {name}")

    @staticmethod
    def _is_graph_operator(op: Any) -> bool:
        """Return True if op is a graph traversal, RPQ, or Cypher operator."""
        if op is None:
            return False
        from uqa.graph.operators import (
            CypherQueryOperator,
            TraverseOperator,
            RegularPathQueryOperator,
        )
        return isinstance(
            op, (TraverseOperator, RegularPathQueryOperator, CypherQueryOperator)
        )

    @staticmethod
    def _is_join_operator(op: Any) -> bool:
        """Return True if op is a join operator (cross, inner, outer, expr)."""
        if op is None:
            return False
        from uqa.joins.base import JoinOperator
        from uqa.joins.cross import CrossJoinOperator
        return isinstance(
            op, (
                JoinOperator, CrossJoinOperator,
                _ExprJoinOperator, _LateralJoinOperator,
            )
        )

    def _build_traverse_from(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build traverse() FROM-clause.

        traverse(start, 'label', hops, 'table')   -- per-table graph
        traverse(start, 'label', hops)             -- requires table
        """
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        if len(args) > 3:
            table_name = self._extract_string_value(args[3])
        else:
            # Use the first available table's graph store
            if not self._engine._tables:
                raise ValueError(
                    "traverse() requires a table argument or "
                    "at least one table to exist"
                )
            table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table, TraverseOperator(start, label, max_hops)

    def _build_rpq_from(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Build rpq() FROM-clause.

        rpq('expr', start, 'table')     -- per-table graph
        rpq('expr', start)              -- requires table
        """
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import parse_rpq

        expr = self._extract_string_value(args[0])
        start = self._extract_int_value(args[1]) if len(args) > 1 else None
        if len(args) > 2:
            table_name = self._extract_string_value(args[2])
        else:
            if not self._engine._tables:
                raise ValueError(
                    "rpq() requires a table argument or "
                    "at least one table to exist"
                )
            table_name = next(iter(self._engine._tables))
        table = self._engine._tables.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return table, RegularPathQueryOperator(parse_rpq(expr), start_vertex=start)

    def _build_create_graph(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM create_graph('name')``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("create_graph() requires a graph name argument")
        name = self._extract_string_value(args[0])
        self._engine.create_graph(name)
        # Return a single-row result like AGE
        table = Table("_create_graph", [
            SQLColumnDef(name="create_graph", type_name="text", python_type=str),
        ])
        table.insert({"create_graph": f"graph '{name}' created"})
        self._engine._tables["_create_graph"] = table
        self._expanded_views.append("_create_graph")
        return table, None

    def _build_drop_graph(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM drop_graph('name')`` or ``drop_graph('name', true)``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("drop_graph() requires a graph name argument")
        name = self._extract_string_value(args[0])
        self._engine.drop_graph(name)
        table = Table("_drop_graph", [
            SQLColumnDef(name="drop_graph", type_name="text", python_type=str),
        ])
        table.insert({"drop_graph": f"graph '{name}' dropped"})
        self._engine._tables["_drop_graph"] = table
        self._expanded_views.append("_drop_graph")
        return table, None

    def _build_create_analyzer(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM create_analyzer('name', 'config_json')``.

        ``config_json`` is a JSON string with keys: tokenizer,
        token_filters, char_filters -- matching ``Analyzer.to_dict()``.
        """
        import json as json_mod
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if len(args) < 2:
            raise ValueError(
                "create_analyzer() requires (name, config_json)"
            )
        name = self._extract_string_value(args[0])
        config_str = self._extract_string_value(args[1])
        config = json_mod.loads(config_str)
        self._engine.create_analyzer(name, config)
        table = Table("_create_analyzer", [
            SQLColumnDef(name="create_analyzer", type_name="text", python_type=str),
        ])
        table.insert({"create_analyzer": f"analyzer '{name}' created"})
        self._engine._tables["_create_analyzer"] = table
        self._expanded_views.append("_create_analyzer")
        return table, None

    def _build_drop_analyzer(
        self, args: tuple
    ) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM drop_analyzer('name')``."""
        from uqa.sql.table import ColumnDef as SQLColumnDef

        if not args:
            raise ValueError("drop_analyzer() requires a name argument")
        name = self._extract_string_value(args[0])
        self._engine.drop_analyzer(name)
        table = Table("_drop_analyzer", [
            SQLColumnDef(name="drop_analyzer", type_name="text", python_type=str),
        ])
        table.insert({"drop_analyzer": f"analyzer '{name}' dropped"})
        self._engine._tables["_drop_analyzer"] = table
        self._expanded_views.append("_drop_analyzer")
        return table, None

    def _build_list_analyzers(self) -> tuple[Table | None, Any]:
        """Handle ``SELECT * FROM list_analyzers()``."""
        from uqa.analysis.analyzer import list_analyzers
        from uqa.sql.table import ColumnDef as SQLColumnDef

        names = list_analyzers()
        table = Table("_list_analyzers", [
            SQLColumnDef(name="analyzer_name", type_name="text", python_type=str),
        ])
        for n in names:
            table.insert({"analyzer_name": n})
        self._engine._tables["_list_analyzers"] = table
        self._expanded_views.append("_list_analyzers")
        return table, None

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
                "cypher() requires 2 arguments: "
                "cypher('graph_name', $$ query $$)"
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
            graph, ast,
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
        analyzer = ctx.inverted_index.get_field_analyzer(field_name) if field_name else ctx.inverted_index.analyzer
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
            raise ValueError(
                "generate_series requires at least 2 arguments"
            )
        start = self._extract_const_value(args[0])
        stop = self._extract_const_value(args[1])
        step = self._extract_const_value(args[2]) if len(args) > 2 else 1

        if not isinstance(start, (int, float)):
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
        for i, val in enumerate(values, 1):
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
            raise ValueError(
                "regexp_split_to_table requires at least 2 arguments"
            )

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
            SQLColumnDef(
                name=key_col, type_name="text", python_type=str
            ),
            SQLColumnDef(
                name=val_col, type_name="text", python_type=str
            ),
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
            raise ValueError(
                "json_array_elements argument must be a JSON array"
            )

        col_name = "value"
        if node.alias is not None:
            if node.alias.colnames:
                col_name = node.alias.colnames[0].sval
            alias_name = node.alias.aliasname
        else:
            alias_name = "json_array_elements"

        import json as json_mod_inner

        col = SQLColumnDef(
            name=col_name, type_name="text", python_type=str
        )
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

    def _resolve_join(
        self, node: JoinExpr
    ) -> tuple[Table | None, Any]:
        from uqa.joins.base import JoinCondition
        from uqa.joins.cross import CrossJoinOperator
        from uqa.joins.inner import InnerJoinOperator
        from uqa.joins.outer import (
            FullOuterJoinOperator,
            LeftOuterJoinOperator,
            RightOuterJoinOperator,
        )

        left_table, left_op, left_alias = self._resolve_from_single(
            node.larg
        )

        # LATERAL subquery on the right side of a JOIN
        if isinstance(node.rarg, RangeSubselect) and node.rarg.lateral:
            if left_op is None and left_table is not None:
                left_op = _TableScanOperator(left_table, alias=left_alias)
            elif left_op is None:
                left_op = _ScanOperator()
            lateral_alias = (
                node.rarg.alias.aliasname
                if node.rarg.alias else "_lateral"
            )
            lateral_op = _LateralJoinOperator(
                left_op, node.rarg.subquery, lateral_alias, self
            )
            return left_table, lateral_op

        right_table, right_op, right_alias = self._resolve_from_single(
            node.rarg
        )

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
                    quals.lexpr, quals.rexpr,
                    left_alias, right_alias,
                )
                condition = JoinCondition(left_field, right_field)

                if jt == JoinType.JOIN_INNER:
                    return table, InnerJoinOperator(
                        left_op, right_op, condition
                    )
                if jt == JoinType.JOIN_LEFT:
                    return table, LeftOuterJoinOperator(
                        left_op, right_op, condition
                    )
                if jt == JoinType.JOIN_RIGHT:
                    return table, RightOuterJoinOperator(
                        left_op, right_op, condition
                    )
                if jt == JoinType.JOIN_FULL:
                    return table, FullOuterJoinOperator(
                        left_op, right_op, condition
                    )

        # Complex ON (compound conditions, non-equality):
        # use nested-loop join with expression evaluation
        if quals is None:
            raise ValueError("Non-CROSS JOIN requires ON clause")
        return table, _ExprJoinOperator(left_op, right_op, quals, jt)

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
            op_name = node.name[0].sval
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
            return self._make_knn_op(args)
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        if name == "path_filter":
            return self._make_path_filter_op(args)
        if name == "vector_exclude":
            return self._make_vector_exclude_op(args)
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

        analyzer = ctx.inverted_index.get_field_analyzer(field_name)
        terms = analyzer.analyze(query)
        term_ops = [TermOperator(t, field_name) for t in terms]
        retrieval = term_ops[0] if len(term_ops) == 1 else UnionOperator(term_ops)

        if bayesian:
            from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer
            scorer = BayesianBM25Scorer(BayesianBM25Params(), ctx.inverted_index.stats)
        else:
            from uqa.scoring.bm25 import BM25Params, BM25Scorer
            scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        return ScoreOperator(scorer, retrieval, terms, field=field_name)

    def _make_knn_op(self, args: tuple) -> Any:
        """knn_match(field, vector, k)

        *field* is a column name (ColumnRef).
        *vector* is an ARRAY literal or $N parameter reference.
        *k* is an integer constant.
        """
        from uqa.operators.primitive import KNNOperator

        if len(args) != 3:
            raise ValueError(
                "knn_match() requires 3 arguments: "
                "knn_match(field, vector, k)"
            )
        field_name = self._extract_column_name(args[0])
        query_vector = self._extract_vector_arg(args[1])
        k = self._extract_int_value(args[2])
        return KNNOperator(query_vector, k, field=field_name)

    def _make_traverse_match_op(self, args: tuple) -> Any:
        """traverse_match(start_id, 'label', max_hops) as a WHERE signal.

        Returns a posting list of reachable vertices with score = 0.9.
        """
        from uqa.graph.operators import TraverseOperator

        start = self._extract_int_value(args[0])
        label = self._extract_string_value(args[1]) if len(args) > 1 else None
        max_hops = self._extract_int_value(args[2]) if len(args) > 2 else 1
        return TraverseOperator(start, label, max_hops)

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
            return self._make_calibrated_knn_op(args)
        if name == "traverse_match":
            return self._make_traverse_match_op(args)
        raise ValueError(
            f"Unknown signal function for fusion: {name}. "
            f"Use text_match, bayesian_match, knn_match, or traverse_match."
        )

    def _make_calibrated_knn_op(self, args: tuple) -> Any:
        """KNN search with scores calibrated to probabilities via
        P_vector = (1 + cosine_similarity) / 2 (Definition 7.1.2, Paper 3).

        knn_match(field, vector, k) -- same signature as _make_knn_op.
        """
        if len(args) != 3:
            raise ValueError(
                "knn_match() requires 3 arguments: "
                "knn_match(field, vector, k)"
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
        for t in target_list:
            for func in self._collect_agg_funcs(t.val):
                fn = func.funcname[-1].sval.lower()
                if fn in _AGG_FUNC_NAMES and func.over is None:
                    return True
        return False

    def _extract_agg_specs(
        self, target_list: tuple
    ) -> list[tuple]:
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
                    f for f in nested
                    if f.funcname[-1].sval.lower() in _AGG_FUNC_NAMES
                    and f.over is None
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
                    if nfn in _TWO_ARG_STAT_AGGS and len(nf.args or ()) >= 2:
                        if isinstance(nf.args[1], ColumnRef):
                            extra = self._extract_column_name(nf.args[1])
                    if (nfn, ac) not in existing:
                        alias = nfn if ac is None else f"{nfn}_{ac}"
                        specs.append((
                            alias, nfn, ac, False, extra,
                            None, None, None,
                        ))
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

            specs.append((
                alias, func_name, arg_col, distinct, extra,
                filter_node, order_keys, agg_expr_node,
            ))
        return specs

    def _ensure_having_aggs(
        self, having_node: Any, agg_specs: list[tuple]
    ) -> None:
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
            agg_specs.append((
                alias, func_name, arg_col, False, None, None, None, None,
            ))
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
            if isinstance(child, (list, tuple)):
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
            isinstance(t.val, FuncCall) and t.val.over is not None
            for t in target_list
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
                        frameOptions=win.frameOptions if (win.frameOptions or 0) & 1 else base.frameOptions,
                        startOffset=win.startOffset or base.startOffset,
                        endOffset=win.endOffset or base.endOffset,
                    )
                elif not win.orderClause and base.orderClause:
                    win = win.__class__(
                        partitionClause=win.partitionClause or base.partitionClause,
                        orderClause=base.orderClause,
                        frameOptions=win.frameOptions if (win.frameOptions or 0) & 1 else base.frameOptions,
                        startOffset=win.startOffset or base.startOffset,
                        endOffset=win.endOffset or base.endOffset,
                    )
            elif win.name and win.name in named_windows and not win.partitionClause and not win.orderClause:
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
                        default_value = evaluator.evaluate(
                            val.args[2], {}
                        )
            elif func_name == "ntile":
                evaluator = ExprEvaluator()
                if val.args:
                    ntile_buckets = int(
                        evaluator.evaluate(val.args[0], {})
                    )
            elif func_name == "nth_value":
                evaluator = ExprEvaluator()
                if val.args:
                    arg_col = self._extract_column_name(val.args[0])
                    if len(val.args) > 1:
                        ntile_buckets = int(
                            evaluator.evaluate(val.args[1], {})
                        )
            elif func_name not in (
                "row_number", "rank", "dense_rank",
                "percent_rank", "cume_dist",
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
                frame_start, frame_start_offset = (
                    self._parse_frame_bound(fo, "start", win.startOffset)
                )
                frame_end, frame_end_offset = (
                    self._parse_frame_bound(fo, "end", win.endOffset)
                )

            specs.append(WindowSpec(
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
            ))

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
            if frame_options & 32:   # START_UNBOUNDED_PRECEDING
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
            if frame_options & 256:   # END_UNBOUNDED_FOLLOWING
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
        return None, 0

    # -- Result conversion ---------------------------------------------

    def _scan_all(self, ctx: ExecutionContext) -> PostingList:
        if ctx.document_store is None:
            # No FROM clause (e.g. SELECT 1 AS val): produce a single
            # dummy row so that expression projection yields one result.
            return PostingList([PostingEntry(0, Payload(score=0.0))])
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
            values = [
                self._extract_const_value(elem) for elem in node.elements
            ]
            return np.array(values, dtype=np.float32)
        if isinstance(node, ParamRef):
            idx = node.number - 1  # $1 -> index 0
            if idx < 0 or idx >= len(self._params):
                raise ValueError(
                    f"No value supplied for parameter ${node.number}"
                )
            return np.asarray(self._params[idx], dtype=np.float32)
        raise ValueError(
            f"Expected ARRAY literal or $N parameter for vector, "
            f"got {type(node).__name__}"
        )

    def _extract_insert_value(self, node: Any) -> Any:
        """Extract a value from an INSERT VALUES clause.

        Handles A_Const (scalars), A_ArrayExpr (vector/array literals),
        and TypeCast (e.g. '...'::jsonb).
        """
        if isinstance(node, A_ArrayExpr):
            if node.elements is None:
                return []
            return [self._extract_const_value(elem) for elem in node.elements]
        if isinstance(node, TypeCast):
            from uqa.sql.expr_evaluator import ExprEvaluator, _cast_value
            value = self._extract_insert_value(node.arg)
            type_name = node.typeName.names[-1].sval.lower()
            if node.typeName.arrayBounds is not None:
                return value if isinstance(value, list) else [value]
            return _cast_value(value, type_name)
        return self._extract_const_value(node)


class _ScanOperator:
    """Scans all documents in the store."""

    def execute(self, context: Any) -> PostingList:
        all_ids = sorted(context.document_store.doc_ids)
        return PostingList([PostingEntry(d, Payload(score=0.0)) for d in all_ids])

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

    def __init__(
        self, table: Table, alias: str | None = None
    ) -> None:
        self._table = table
        self._alias = alias

    def execute(self, context: Any) -> PostingList:
        entries: list[PostingEntry] = []
        alias = self._alias
        # Pre-fetch column names so NULL columns are explicitly present.
        # The document store may omit NULL values; for JOIN semantics
        # we need them to prevent unqualified fallback to the wrong table.
        col_names = (
            list(self._table.columns.keys())
            if self._table.columns
            else []
        )
        for doc_id in sorted(self._table.document_store.doc_ids):
            doc = self._table.document_store.get(doc_id)
            fields = dict(doc) if doc else {}
            for col_name in col_names:
                if col_name not in fields:
                    fields[col_name] = None
            if alias:
                qualified = {
                    f"{alias}.{k}": v for k, v in fields.items()
                }
                fields = {**qualified, **fields}
            entries.append(
                PostingEntry(doc_id, Payload(score=0.0, fields=fields))
            )
        return PostingList(entries)

    def cost_estimate(self, stats: Any) -> float:
        return float(len(self._table.document_store.doc_ids))


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
        from uqa.core.posting_list import GeneralizedPostingList
        from uqa.core.types import GeneralizedPostingEntry, Payload
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator()
        left_entries = _get_join_entries(self._left, context)
        right_entries = _get_join_entries(self._right, context)

        jt = self._join_type
        quals = self._quals

        if jt == JoinType.JOIN_INNER:
            return self._inner(
                evaluator, quals, left_entries, right_entries
            )
        if jt == JoinType.JOIN_LEFT:
            return self._left_outer(
                evaluator, quals, left_entries, right_entries
            )
        if jt == JoinType.JOIN_RIGHT:
            return self._right_outer(
                evaluator, quals, left_entries, right_entries
            )
        if jt == JoinType.JOIN_FULL:
            return self._full_outer(
                evaluator, quals, left_entries, right_entries
            )
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
                                score=(
                                    left.payload.score
                                    + right.payload.score
                                ),
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
                                score=(
                                    left.payload.score
                                    + right.payload.score
                                ),
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
                                score=(
                                    left.payload.score
                                    + right.payload.score
                                ),
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
                                score=(
                                    left.payload.score
                                    + right.payload.score
                                ),
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

    def _execute_lateral_subquery(
        self, left_fields: dict[str, Any]
    ) -> SQLResult:
        """Execute the lateral subquery with left-row columns injected.

        Rewrites the subquery AST by replacing outer ColumnRef nodes
        (references to columns from the left-side tables) with
        A_Const nodes containing the actual values from the current
        left row.  This is the same approach used for correlated
        subqueries.
        """
        import copy
        from uqa.sql.expr_evaluator import ExprEvaluator

        evaluator = ExprEvaluator()

        # Build outer_row dict for substitution (unqualified keys)
        outer_row: dict[str, Any] = {}
        for k, v in left_fields.items():
            if "." not in k:
                outer_row[k] = v

        # Deep-copy the subquery AST and substitute outer references
        subquery_copy = copy.deepcopy(self._subquery)
        rewritten = evaluator._substitute_correlated_refs(
            subquery_copy, outer_row
        )

        return self._compiler._compile_select(rewritten)

    def cost_estimate(self, stats: Any) -> float:
        return 1000.0


class _CalibratedKNNOperator:
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
        vec_idx = context.vector_indexes.get(self.field)
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
