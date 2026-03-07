#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Relational physical operators for the Volcano execution engine.

These operators implement the standard relational algebra over batches:
filter, project, sort, limit, hash-aggregate, and distinct.  Each
follows the ``open / next / close`` iterator protocol.

Sort, hash-aggregate, and distinct are *blocking* operators -- they
materialize all input before producing output.  Filter, project, and
limit are *streaming* operators that process one batch at a time.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from uqa.execution.batch import Batch, DEFAULT_BATCH_SIZE
from uqa.execution.physical import PhysicalOperator


class FilterOp(PhysicalOperator):
    """Evaluate a predicate on a column, setting the selection vector.

    Streaming operator: processes one batch at a time.  Batches with
    no matching rows are skipped (pulls the next batch from the child).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        column: str,
        predicate: Any,
    ) -> None:
        self._child = child
        self._column = column
        self._predicate = predicate
        from uqa.core.types import is_null_predicate
        self._null_aware = is_null_predicate(predicate)

    def open(self) -> None:
        self._child.open()

    def next(self) -> Batch | None:
        while True:
            batch = self._child.next()
            if batch is None:
                return None

            col = batch.columns.get(self._column)
            if col is None:
                continue

            if batch.selection is not None:
                indices = batch.selection
            else:
                indices = range(batch.size)

            active: list[int] = []
            null_aware = self._null_aware
            for i in indices:
                val = col[i]
                if null_aware:
                    matched = self._predicate.evaluate(val)
                else:
                    matched = val is not None and self._predicate.evaluate(val)
                if matched:
                    active.append(i)

            if not active:
                continue

            return Batch(
                columns=batch.columns,
                selection=np.array(active, dtype=np.intp),
                size=batch.size,
            )

    def close(self) -> None:
        self._child.close()


class ProjectOp(PhysicalOperator):
    """Select specific columns from the input.

    Streaming operator: compacts and projects each batch individually.
    Column renaming is supported via the *aliases* dict.
    """

    def __init__(
        self,
        child: PhysicalOperator,
        columns: list[str],
        aliases: dict[str, str] | None = None,
    ) -> None:
        self._child = child
        self._columns = columns
        self._aliases = aliases or {}

    def open(self) -> None:
        self._child.open()

    def next(self) -> Batch | None:
        batch = self._child.next()
        if batch is None:
            return None

        batch = batch.compact()
        projected = {}
        for col in self._columns:
            alias = self._aliases.get(col, col)
            if col in batch.columns:
                projected[alias] = batch.columns[col]

        return Batch(columns=projected, size=batch.size)

    def close(self) -> None:
        self._child.close()


class ExprProjectOp(PhysicalOperator):
    """Evaluate SQL expression AST nodes to produce computed columns.

    Streaming operator: evaluates each expression against every row in
    the batch.  Unlike :class:`ProjectOp`, this operator handles arbitrary
    expressions (arithmetic, CASE, CAST, function calls, etc.) via the
    :class:`~uqa.sql.expr_evaluator.ExprEvaluator`.

    *targets* is a list of ``(output_name, ast_node)`` pairs.
    """

    def __init__(
        self,
        child: PhysicalOperator,
        targets: list[tuple[str, Any]],
        subquery_executor: Any = None,
    ) -> None:
        self._child = child
        self._targets = targets
        self._subquery_executor = subquery_executor

    def open(self) -> None:
        self._child.open()

    def next(self) -> Batch | None:
        from uqa.sql.expr_evaluator import ExprEvaluator

        batch = self._child.next()
        if batch is None:
            return None

        batch = batch.compact()
        input_rows = batch.to_rows()

        evaluator = ExprEvaluator(
            subquery_executor=self._subquery_executor
        )
        output_rows: list[dict[str, Any]] = []
        for row in input_rows:
            out: dict[str, Any] = {}
            for col_name, node in self._targets:
                out[col_name] = evaluator.evaluate(node, row)
            output_rows.append(out)

        if not output_rows:
            return None
        return Batch.from_rows(output_rows)

    def close(self) -> None:
        self._child.close()


class SortOp(PhysicalOperator):
    """Sort all input rows by the specified keys.

    Blocking operator: materializes all input before producing sorted
    output in batches.  Sort stability is guaranteed (Python's
    ``list.sort`` is stable).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        sort_keys: list[tuple[str, bool]],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._child = child
        self._sort_keys = sort_keys
        self._batch_size = batch_size
        self._sorted_rows: list[dict[str, Any]] | None = None
        self._offset = 0

    def open(self) -> None:
        self._child.open()

        all_rows: list[dict[str, Any]] = []
        while True:
            batch = self._child.next()
            if batch is None:
                break
            all_rows.extend(batch.to_rows())
        self._child.close()

        for col_name, desc in reversed(self._sort_keys):
            all_rows.sort(
                key=lambda r, c=col_name: (r.get(c) is None, r.get(c)),
                reverse=desc,
            )

        self._sorted_rows = all_rows
        self._offset = 0

    def next(self) -> Batch | None:
        if self._sorted_rows is None:
            return None
        if self._offset >= len(self._sorted_rows):
            return None

        end = min(
            self._offset + self._batch_size, len(self._sorted_rows)
        )
        batch_rows = self._sorted_rows[self._offset : end]
        self._offset = end
        return Batch.from_rows(batch_rows)

    def close(self) -> None:
        self._sorted_rows = None
        self._offset = 0


class LimitOp(PhysicalOperator):
    """Limit output to at most *limit* rows, optionally skipping *offset*.

    Streaming operator: skips the first *offset* rows, then passes
    through up to *limit* rows from the child.  Truncates the last
    batch if needed and stops pulling once the limit is reached.
    """

    def __init__(
        self, child: PhysicalOperator, limit: int, offset: int = 0
    ) -> None:
        self._child = child
        self._limit = limit
        self._offset = offset
        self._skipped = 0
        self._emitted = 0

    def open(self) -> None:
        self._child.open()
        self._skipped = 0
        self._emitted = 0

    def next(self) -> Batch | None:
        if self._emitted >= self._limit:
            return None

        while True:
            batch = self._child.next()
            if batch is None:
                return None

            batch = batch.compact()

            # Skip rows for OFFSET
            if self._skipped < self._offset:
                need_to_skip = self._offset - self._skipped
                if batch.size <= need_to_skip:
                    self._skipped += batch.size
                    continue
                # Partial skip: drop first need_to_skip rows
                indices = np.arange(
                    need_to_skip, batch.size, dtype=np.intp
                )
                batch = Batch(
                    columns={
                        name: col.select(indices)
                        for name, col in batch.columns.items()
                    },
                    size=batch.size - need_to_skip,
                )
                self._skipped = self._offset

            # Apply LIMIT
            remaining = self._limit - self._emitted
            if batch.size <= remaining:
                self._emitted += batch.size
                return batch

            indices = np.arange(remaining, dtype=np.intp)
            truncated = {
                name: col.select(indices)
                for name, col in batch.columns.items()
            }
            self._emitted += remaining
            return Batch(columns=truncated, size=remaining)

    def close(self) -> None:
        self._child.close()
        self._skipped = 0
        self._emitted = 0


class HashAggOp(PhysicalOperator):
    """Hash-based GROUP BY with aggregate functions.

    Blocking operator: materializes all input, groups by the specified
    columns, computes aggregates per group, and yields the result in
    batches.

    When *group_columns* is empty, the entire input is treated as a
    single group (aggregate-only query like ``SELECT COUNT(*) FROM t``).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        group_columns: list[str],
        agg_specs: list[tuple[str, str, str | None]],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._child = child
        self._group_columns = group_columns
        self._agg_specs = agg_specs
        self._batch_size = batch_size
        self._result_rows: list[dict[str, Any]] | None = None
        self._offset = 0

    def open(self) -> None:
        self._child.open()

        groups: dict[tuple, list[dict[str, Any]]] = {}
        while True:
            batch = self._child.next()
            if batch is None:
                break
            for row in batch.to_rows():
                key = tuple(row.get(c) for c in self._group_columns)
                groups.setdefault(key, []).append(row)
        self._child.close()

        if not groups and not self._group_columns:
            groups[()] = []

        result: list[dict[str, Any]] = []
        for key, rows in groups.items():
            row_out: dict[str, Any] = dict(
                zip(self._group_columns, key)
            )
            for alias, func_name, arg_col in self._agg_specs:
                row_out[alias] = _compute_aggregate(
                    func_name, arg_col, rows
                )
            result.append(row_out)

        self._result_rows = result
        self._offset = 0

    def next(self) -> Batch | None:
        if self._result_rows is None:
            return None
        if self._offset >= len(self._result_rows):
            return None

        end = min(
            self._offset + self._batch_size, len(self._result_rows)
        )
        batch_rows = self._result_rows[self._offset : end]
        self._offset = end
        return Batch.from_rows(batch_rows)

    def close(self) -> None:
        self._result_rows = None
        self._offset = 0


class DistinctOp(PhysicalOperator):
    """Remove duplicate rows based on specified columns.

    Blocking operator: materializes all input to perform deduplication.
    """

    def __init__(
        self,
        child: PhysicalOperator,
        columns: list[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._child = child
        self._columns = columns
        self._batch_size = batch_size
        self._unique_rows: list[dict[str, Any]] | None = None
        self._offset = 0

    def open(self) -> None:
        self._child.open()

        seen: set[tuple] = set()
        unique: list[dict[str, Any]] = []
        while True:
            batch = self._child.next()
            if batch is None:
                break
            for row in batch.to_rows():
                key = tuple(row.get(c) for c in self._columns)
                if key not in seen:
                    seen.add(key)
                    unique.append(row)
        self._child.close()

        self._unique_rows = unique
        self._offset = 0

    def next(self) -> Batch | None:
        if self._unique_rows is None:
            return None
        if self._offset >= len(self._unique_rows):
            return None

        end = min(
            self._offset + self._batch_size, len(self._unique_rows)
        )
        batch_rows = self._unique_rows[self._offset : end]
        self._offset = end
        return Batch.from_rows(batch_rows)

    def close(self) -> None:
        self._unique_rows = None
        self._offset = 0


def _compute_aggregate(
    func_name: str, arg_col: str | None, rows: list[dict[str, Any]]
) -> Any:
    """Compute a single aggregate value over a group of rows."""
    if func_name == "count":
        if arg_col is None:
            return len(rows)
        return sum(1 for r in rows if r.get(arg_col) is not None)

    values = [
        r.get(arg_col)
        for r in rows
        if isinstance(r.get(arg_col), (int, float))
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
