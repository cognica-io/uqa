#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Parallel execution support for independent operator branches.

When enabled, operators with multiple independent children (Union,
Intersect, LogOddsFusion, ProbBoolFusion) execute those children
concurrently using a thread pool.  This provides real speedup for
I/O-bound operations (SQLite queries release the GIL) while
maintaining correctness for CPU-bound work (PostingList merges
happen after all children complete).

Thread safety: each child operator reads from shared SQLite
connections (SQLite supports concurrent reads in WAL mode) and
produces an independent PostingList.  No writes occur during
query execution.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList

if TYPE_CHECKING:
    from uqa.operators.base import ExecutionContext, Operator


# Default thread pool size; 0 disables parallel execution.
_DEFAULT_MAX_WORKERS = 4

# Minimum number of children to trigger parallel execution.
# Below this threshold, sequential execution has lower overhead.
_MIN_PARALLEL_BRANCHES = 2


class ParallelExecutor:
    """Executes independent operator branches concurrently.

    Usage::

        par = ParallelExecutor(max_workers=4)
        results = par.execute_branches(operators, context)
        # results is a list[PostingList] in the same order as operators
    """

    def __init__(self, max_workers: int = _DEFAULT_MAX_WORKERS) -> None:
        self._max_workers = max_workers

    @property
    def enabled(self) -> bool:
        return self._max_workers > 0

    def execute_branches(
        self,
        operators: list[Operator],
        context: ExecutionContext,
    ) -> list[PostingList]:
        """Execute a list of independent operators, possibly in parallel.

        Returns results in the same order as the input operators.
        Falls back to sequential execution when parallel execution is
        disabled or the number of branches is below the threshold.
        """
        if (
            not self.enabled
            or len(operators) < _MIN_PARALLEL_BRANCHES
        ):
            return [op.execute(context) for op in operators]

        workers = min(self._max_workers, len(operators))
        results: list[PostingList | None] = [None] * len(operators)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_idx = {
                pool.submit(op.execute, context): i
                for i, op in enumerate(operators)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()

        return results  # type: ignore[return-value]
