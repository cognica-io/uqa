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

from dataclasses import dataclass, field
from typing import Any

from uqa.execution.batch import Batch, DEFAULT_BATCH_SIZE
from uqa.execution.physical import PhysicalOperator


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Specification for a single window function evaluation.

    Attributes:
        alias: Output column name.
        func_name: Window function name (row_number, rank, lag, sum, ...).
        partition_cols: Columns for PARTITION BY.
        order_keys: List of (column, descending) pairs for ORDER BY.
        arg_col: Column argument for aggregate/navigation functions.
        offset: Row offset for LAG/LEAD (default 1).
        default_value: Default value for LAG/LEAD when out of bounds.
        ntile_buckets: Number of buckets for NTILE.
    """

    alias: str
    func_name: str
    partition_cols: list[str] = field(default_factory=list)
    order_keys: list[tuple[str, bool]] = field(default_factory=list)
    arg_col: str | None = None
    offset: int = 1
    default_value: Any = None
    ntile_buckets: int = 1


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

            col = batch.get_column(self._column)
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

            return batch.with_selection(active)

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

        return batch.compact().select_columns(self._columns, self._aliases)

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

    When *spill_threshold* > 0 and the input exceeds that many rows,
    sorted runs are spilled to disk as Arrow IPC files and merged via
    a k-way merge (external merge sort).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        sort_keys: list[tuple[str, bool]],
        batch_size: int = DEFAULT_BATCH_SIZE,
        spill_threshold: int = 0,
    ) -> None:
        self._child = child
        self._sort_keys = sort_keys
        self._batch_size = batch_size
        self._spill_threshold = spill_threshold
        self._sorted_rows: list[dict[str, Any]] | None = None
        self._merge_iter: Any = None
        self._spill_mgr: Any = None
        self._offset = 0

    @staticmethod
    def _sort_rows(
        rows: list[dict[str, Any]],
        sort_keys: list[tuple[str, bool]],
    ) -> None:
        for col_name, desc in reversed(sort_keys):
            rows.sort(
                key=lambda r, c=col_name: (r.get(c) is None, r.get(c)),
                reverse=desc,
            )

    def open(self) -> None:
        self._child.open()

        if self._spill_threshold <= 0:
            all_rows: list[dict[str, Any]] = []
            while True:
                batch = self._child.next()
                if batch is None:
                    break
                all_rows.extend(batch.to_rows())
            self._child.close()
            self._sort_rows(all_rows, self._sort_keys)
            self._sorted_rows = all_rows
            self._offset = 0
            return

        # External merge sort with disk spilling.
        from uqa.execution.spill import (
            SpillManager,
            SpillWriter,
            merge_sorted_runs,
            read_rows_from_ipc,
        )

        spill_mgr = SpillManager()
        self._spill_mgr = spill_mgr
        buffer: list[dict[str, Any]] = []
        run_paths: list[str] = []

        while True:
            batch = self._child.next()
            if batch is None:
                break
            buffer.extend(batch.to_rows())
            if len(buffer) >= self._spill_threshold:
                self._sort_rows(buffer, self._sort_keys)
                path = spill_mgr.new_path()
                writer = SpillWriter(path)
                writer.write_rows(buffer)
                writer.close()
                run_paths.append(path)
                buffer.clear()
        self._child.close()

        if not run_paths:
            # Everything fit in memory.
            self._sort_rows(buffer, self._sort_keys)
            self._sorted_rows = buffer
            self._offset = 0
            return

        runs: list[Any] = [read_rows_from_ipc(p) for p in run_paths]
        if buffer:
            self._sort_rows(buffer, self._sort_keys)
            runs.append(iter(buffer))
        self._merge_iter = merge_sorted_runs(runs, self._sort_keys)

    def next(self) -> Batch | None:
        if self._merge_iter is not None:
            rows: list[dict[str, Any]] = []
            for row in self._merge_iter:
                rows.append(row)
                if len(rows) >= self._batch_size:
                    break
            if not rows:
                return None
            return Batch.from_rows(rows)

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
        self._merge_iter = None
        self._offset = 0
        if self._spill_mgr is not None:
            self._spill_mgr.cleanup()
            self._spill_mgr = None


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
                batch = batch.slice(
                    need_to_skip, batch.size - need_to_skip
                )
                self._skipped = self._offset

            # Apply LIMIT
            remaining = self._limit - self._emitted
            if batch.size <= remaining:
                self._emitted += batch.size
                return batch

            self._emitted += remaining
            return batch.slice(0, remaining)

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

    When *spill_threshold* > 0 and the input exceeds that many rows,
    rows are hash-partitioned into 16 on-disk partitions (Grace hash)
    and each partition is aggregated independently.
    """

    _NUM_PARTITIONS = 16

    def __init__(
        self,
        child: PhysicalOperator,
        group_columns: list[str],
        agg_specs: list[tuple[str, str, str | None]],
        batch_size: int = DEFAULT_BATCH_SIZE,
        spill_threshold: int = 0,
    ) -> None:
        self._child = child
        self._group_columns = group_columns
        self._agg_specs = agg_specs
        self._batch_size = batch_size
        self._spill_threshold = spill_threshold
        self._result_rows: list[dict[str, Any]] | None = None
        self._result_iter: Any = None
        self._spill_mgr: Any = None
        self._offset = 0

    def _aggregate_rows(
        self, rows_iter: Any
    ) -> list[dict[str, Any]]:
        groups: dict[tuple, list[dict[str, Any]]] = {}
        for row in rows_iter:
            key = tuple(row.get(c) for c in self._group_columns)
            groups.setdefault(key, []).append(row)
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
        return result

    def open(self) -> None:
        self._child.open()

        if self._spill_threshold <= 0:
            self._result_rows = self._aggregate_rows(
                self._drain_child()
            )
            self._offset = 0
            return

        # Try in-memory first.
        buffer: list[dict[str, Any]] = []
        exceeded = False
        while True:
            batch = self._child.next()
            if batch is None:
                break
            buffer.extend(batch.to_rows())
            if len(buffer) >= self._spill_threshold:
                exceeded = True
                break

        if not exceeded:
            self._child.close()
            self._result_rows = self._aggregate_rows(iter(buffer))
            self._offset = 0
            return

        # Grace hash partitioning.
        from uqa.execution.spill import (
            SpillManager,
            SpillWriter,
            read_rows_from_ipc,
        )

        spill_mgr = SpillManager()
        self._spill_mgr = spill_mgr
        num_parts = self._NUM_PARTITIONS
        flush_size = max(1024, self._spill_threshold // num_parts)
        partition_paths = [spill_mgr.new_path() for _ in range(num_parts)]
        writers = [SpillWriter(p) for p in partition_paths]
        part_buffers: list[list[dict[str, Any]]] = [
            [] for _ in range(num_parts)
        ]
        group_cols = self._group_columns

        def _partition_row(row: dict[str, Any]) -> None:
            key = tuple(row.get(c) for c in group_cols)
            h = hash(key) % num_parts
            part_buffers[h].append(row)
            if len(part_buffers[h]) >= flush_size:
                writers[h].write_rows(part_buffers[h])
                part_buffers[h].clear()

        for row in buffer:
            _partition_row(row)
        buffer.clear()

        while True:
            batch = self._child.next()
            if batch is None:
                break
            for row in batch.to_rows():
                _partition_row(row)
        self._child.close()

        active_paths: list[str] = []
        for h in range(num_parts):
            if part_buffers[h]:
                writers[h].write_rows(part_buffers[h])
                part_buffers[h].clear()
            writers[h].close()
            if writers[h].row_count > 0:
                active_paths.append(partition_paths[h])

        if not active_paths and not self._group_columns:
            self._result_rows = self._aggregate_rows(iter([]))
            self._offset = 0
            return

        agg_specs = self._agg_specs

        def _process_partitions():
            for path in active_paths:
                yield from self._aggregate_rows(
                    read_rows_from_ipc(path)
                )

        self._result_iter = _process_partitions()

    def _drain_child(self) -> Any:
        while True:
            batch = self._child.next()
            if batch is None:
                break
            yield from batch.to_rows()
        self._child.close()

    def next(self) -> Batch | None:
        if self._result_iter is not None:
            rows: list[dict[str, Any]] = []
            for row in self._result_iter:
                rows.append(row)
                if len(rows) >= self._batch_size:
                    break
            if not rows:
                return None
            return Batch.from_rows(rows)

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
        self._result_iter = None
        self._offset = 0
        if self._spill_mgr is not None:
            self._spill_mgr.cleanup()
            self._spill_mgr = None


class DistinctOp(PhysicalOperator):
    """Remove duplicate rows based on specified columns.

    Blocking operator: materializes all input to perform deduplication.

    When *spill_threshold* > 0 and the input exceeds that many rows,
    rows are hash-partitioned to disk and deduplicated per partition.
    """

    _NUM_PARTITIONS = 16

    def __init__(
        self,
        child: PhysicalOperator,
        columns: list[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
        spill_threshold: int = 0,
    ) -> None:
        self._child = child
        self._columns = columns
        self._batch_size = batch_size
        self._spill_threshold = spill_threshold
        self._unique_rows: list[dict[str, Any]] | None = None
        self._result_iter: Any = None
        self._spill_mgr: Any = None
        self._offset = 0

    @staticmethod
    def _dedup(
        rows_iter: Any,
        columns: list[str],
    ) -> list[dict[str, Any]]:
        seen: set[tuple] = set()
        unique: list[dict[str, Any]] = []
        for row in rows_iter:
            key = tuple(row.get(c) for c in columns)
            if key not in seen:
                seen.add(key)
                unique.append(row)
        return unique

    def open(self) -> None:
        self._child.open()

        if self._spill_threshold <= 0:
            all_rows: list[dict[str, Any]] = []
            while True:
                batch = self._child.next()
                if batch is None:
                    break
                all_rows.extend(batch.to_rows())
            self._child.close()
            self._unique_rows = self._dedup(all_rows, self._columns)
            self._offset = 0
            return

        # Try in-memory first.
        buffer: list[dict[str, Any]] = []
        exceeded = False
        while True:
            batch = self._child.next()
            if batch is None:
                break
            buffer.extend(batch.to_rows())
            if len(buffer) >= self._spill_threshold:
                exceeded = True
                break

        if not exceeded:
            self._child.close()
            self._unique_rows = self._dedup(buffer, self._columns)
            self._offset = 0
            return

        # Hash partition dedup.
        from uqa.execution.spill import (
            SpillManager,
            SpillWriter,
            read_rows_from_ipc,
        )

        spill_mgr = SpillManager()
        self._spill_mgr = spill_mgr
        num_parts = self._NUM_PARTITIONS
        flush_size = max(1024, self._spill_threshold // num_parts)
        partition_paths = [spill_mgr.new_path() for _ in range(num_parts)]
        writers = [SpillWriter(p) for p in partition_paths]
        part_buffers: list[list[dict[str, Any]]] = [
            [] for _ in range(num_parts)
        ]
        columns = self._columns

        def _partition_row(row: dict[str, Any]) -> None:
            key = tuple(row.get(c) for c in columns)
            h = hash(key) % num_parts
            part_buffers[h].append(row)
            if len(part_buffers[h]) >= flush_size:
                writers[h].write_rows(part_buffers[h])
                part_buffers[h].clear()

        for row in buffer:
            _partition_row(row)
        buffer.clear()

        while True:
            batch = self._child.next()
            if batch is None:
                break
            for row in batch.to_rows():
                _partition_row(row)
        self._child.close()

        active_paths: list[str] = []
        for h in range(num_parts):
            if part_buffers[h]:
                writers[h].write_rows(part_buffers[h])
                part_buffers[h].clear()
            writers[h].close()
            if writers[h].row_count > 0:
                active_paths.append(partition_paths[h])

        def _dedup_partitions():
            for path in active_paths:
                yield from self._dedup(
                    read_rows_from_ipc(path), columns
                )

        self._result_iter = _dedup_partitions()

    def next(self) -> Batch | None:
        if self._result_iter is not None:
            rows: list[dict[str, Any]] = []
            for row in self._result_iter:
                rows.append(row)
                if len(rows) >= self._batch_size:
                    break
            if not rows:
                return None
            return Batch.from_rows(rows)

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
        self._result_iter = None
        self._offset = 0
        if self._spill_mgr is not None:
            self._spill_mgr.cleanup()
            self._spill_mgr = None


class WindowOp(PhysicalOperator):
    """Evaluate window functions over partitioned, ordered rows.

    Blocking operator: materializes all input, partitions by the
    specified columns, sorts each partition by the order keys, then
    evaluates window functions (ROW_NUMBER, RANK, DENSE_RANK, NTILE,
    LAG, LEAD, FIRST_VALUE, LAST_VALUE, SUM/COUNT/AVG/MIN/MAX OVER).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        window_specs: list[WindowSpec],
        batch_size: int = DEFAULT_BATCH_SIZE,
        spill_threshold: int = 0,
    ) -> None:
        self._child = child
        self._window_specs = window_specs
        self._batch_size = batch_size
        self._spill_threshold = spill_threshold
        self._result_rows: list[dict[str, Any]] | None = None
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

        for spec in self._window_specs:
            # Sort by partition keys + order keys
            sorted_rows = list(all_rows)
            for col, desc in reversed(spec.order_keys):
                sorted_rows.sort(
                    key=lambda r, c=col: (r.get(c) is None, r.get(c)),
                    reverse=desc,
                )
            if spec.partition_cols:
                sorted_rows.sort(
                    key=lambda r: tuple(
                        r.get(c) for c in spec.partition_cols
                    )
                )

            # Build a mapping from original row identity to sorted index
            # We use id() to track row objects
            row_id_to_sorted_idx: dict[int, int] = {}
            for idx, row in enumerate(sorted_rows):
                row_id_to_sorted_idx[id(row)] = idx

            # Partition the sorted rows
            partitions: list[list[int]] = []
            current_key: tuple | None = None
            for idx, row in enumerate(sorted_rows):
                key = tuple(
                    row.get(c) for c in spec.partition_cols
                )
                if key != current_key:
                    partitions.append([])
                    current_key = key
                partitions[-1].append(idx)

            # Compute window values for sorted rows
            win_values: dict[int, Any] = {}
            for part_indices in partitions:
                part_rows = [sorted_rows[i] for i in part_indices]
                values = _compute_window_function(spec, part_rows)
                for i, idx in enumerate(part_indices):
                    win_values[idx] = values[i]

            # Apply computed values back to original rows
            for row in all_rows:
                sorted_idx = row_id_to_sorted_idx[id(row)]
                row[spec.alias] = win_values[sorted_idx]

        self._result_rows = all_rows
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


def _compute_window_function(
    spec: WindowSpec,
    partition_rows: list[dict[str, Any]],
) -> list[Any]:
    """Compute a window function over an ordered partition.

    Returns a list of values, one per row in the partition.
    """
    func_name = spec.func_name
    n = len(partition_rows)

    if func_name == "row_number":
        return list(range(1, n + 1))

    if func_name == "rank":
        order_cols = [c for c, _ in spec.order_keys]
        ranks: list[int] = []
        for i in range(n):
            if i == 0:
                ranks.append(1)
            else:
                prev = partition_rows[i - 1]
                cur = partition_rows[i]
                if _rows_equal_on_columns(prev, cur, order_cols):
                    ranks.append(ranks[-1])
                else:
                    ranks.append(i + 1)
        return ranks

    if func_name == "dense_rank":
        order_cols = [c for c, _ in spec.order_keys]
        ranks = []
        current_rank = 0
        for i in range(n):
            if i == 0:
                current_rank = 1
            else:
                prev = partition_rows[i - 1]
                cur = partition_rows[i]
                if not _rows_equal_on_columns(prev, cur, order_cols):
                    current_rank += 1
            ranks.append(current_rank)
        return ranks

    if func_name == "ntile":
        result: list[int] = []
        for i in range(n):
            bucket = (i * spec.ntile_buckets) // n + 1
            result.append(bucket)
        return result

    if func_name == "lag":
        result = []
        for i in range(n):
            if i - spec.offset >= 0:
                result.append(
                    partition_rows[i - spec.offset].get(spec.arg_col)
                )
            else:
                result.append(spec.default_value)
        return result

    if func_name == "lead":
        result = []
        for i in range(n):
            if i + spec.offset < n:
                result.append(
                    partition_rows[i + spec.offset].get(spec.arg_col)
                )
            else:
                result.append(spec.default_value)
        return result

    if func_name == "first_value":
        if n == 0:
            return []
        val = partition_rows[0].get(spec.arg_col)
        return [val] * n

    if func_name == "last_value":
        if n == 0:
            return []
        val = partition_rows[-1].get(spec.arg_col)
        return [val] * n

    # Aggregate window functions (SUM, COUNT, AVG, MIN, MAX OVER)
    if func_name in ("sum", "count", "avg", "min", "max"):
        agg_val = _compute_aggregate(
            func_name, spec.arg_col, partition_rows
        )
        return [agg_val] * n

    raise ValueError(f"Unknown window function: {func_name}")


def _rows_equal_on_columns(
    a: dict[str, Any],
    b: dict[str, Any],
    columns: list[str],
) -> bool:
    """Check if two rows have equal values on the given columns."""
    return all(a.get(c) == b.get(c) for c in columns)


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
