#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Disk spilling infrastructure for blocking operators.

When a blocking operator (sort, hash-aggregate, distinct) accumulates
more rows than ``spill_threshold``, it writes intermediate data to
temporary Arrow IPC stream files and processes them incrementally to
bound memory usage.

Arrow IPC stream format preserves full schema and type information,
enabling zero-conversion round-trips between in-memory RecordBatches
and on-disk files.
"""

from __future__ import annotations

import heapq
import os
import tempfile
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.ipc as ipc

from uqa.execution.batch import Batch


class SpillManager:
    """Manages temporary Arrow IPC files for a single operator."""

    def __init__(self) -> None:
        self._temp_dir: str | None = None
        self._paths: list[str] = []

    def _ensure_dir(self) -> str:
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="uqa_spill_")
        return self._temp_dir

    def new_path(self) -> str:
        d = self._ensure_dir()
        idx = len(self._paths)
        path = os.path.join(d, f"spill_{idx}.arrow")
        self._paths.append(path)
        return path

    def cleanup(self) -> None:
        for path in self._paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        self._paths.clear()
        if self._temp_dir is not None:
            try:
                os.rmdir(self._temp_dir)
            except OSError:
                pass
            self._temp_dir = None


class SpillWriter:
    """Appends row batches to an Arrow IPC stream file.

    The schema is captured from the first ``write_rows`` call and
    reused for all subsequent writes to guarantee type consistency.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.row_count = 0
        self._sink: pa.OSFile | None = None
        self._writer: ipc.RecordBatchStreamWriter | None = None
        self._schema: pa.Schema | None = None

    def write_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        if self._writer is None:
            batch = Batch.from_rows(rows)
            rb = batch.record_batch
            self._schema = rb.schema
            self._sink = pa.OSFile(self.path, "wb")
            self._writer = ipc.new_stream(self._sink, self._schema)
        else:
            rb = pa.RecordBatch.from_pylist(rows, schema=self._schema)
        self._writer.write_batch(rb)
        self.row_count += len(rows)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
        if self._sink is not None:
            self._sink.close()


def read_rows_from_ipc(path: str) -> Iterator[dict[str, Any]]:
    """Yield row dicts from an Arrow IPC stream file."""
    source = pa.OSFile(path, "rb")
    try:
        reader = ipc.open_stream(source)
        for rb in reader:
            pydict = rb.to_pydict()
            names = rb.schema.names
            for i in range(rb.num_rows):
                yield {name: pydict[name][i] for name in names}
    finally:
        source.close()


# -- External merge sort utilities -----------------------------------------


class _SortKey:
    """Comparable wrapper for k-way merge heap ordering.

    Handles multi-column sort with per-column ascending/descending
    and NULL-last (ASC) / NULL-first (DESC) semantics matching the
    in-memory SortOp behavior.
    """

    __slots__ = ("row", "_parts")

    def __init__(
        self, row: dict[str, Any], sort_keys: list[tuple[str, bool]]
    ) -> None:
        self.row = row
        self._parts: list[tuple[bool, Any, bool]] = [
            (row.get(col) is None, row.get(col), desc)
            for col, desc in sort_keys
        ]

    def __lt__(self, other: _SortKey) -> bool:
        for (na, va, desc), (nb, vb, _) in zip(self._parts, other._parts):
            if na != nb:
                # ASC: non-NULL < NULL (NULL-last)
                # DESC: NULL < non-NULL (NULL-first)
                return na if desc else nb
            if na:
                continue
            if va == vb:
                continue
            return va > vb if desc else va < vb
        return False


def merge_sorted_runs(
    runs: list[Iterator[dict[str, Any]]],
    sort_keys: list[tuple[str, bool]],
) -> Iterator[dict[str, Any]]:
    """K-way merge of pre-sorted row iterators using a min-heap."""
    heap: list[tuple[_SortKey, int, int]] = []
    counter = 0

    for run_idx, run in enumerate(runs):
        row = next(run, None)
        if row is not None:
            heapq.heappush(heap, (_SortKey(row, sort_keys), counter, run_idx))
            counter += 1

    while heap:
        key, _, run_idx = heapq.heappop(heap)
        yield key.row
        row = next(runs[run_idx], None)
        if row is not None:
            heapq.heappush(
                heap, (_SortKey(row, sort_keys), counter, run_idx)
            )
            counter += 1
