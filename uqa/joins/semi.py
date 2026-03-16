#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.operators.base import Operator

if TYPE_CHECKING:
    from collections.abc import Callable

    from uqa.core.types import IndexStats, PostingEntry
    from uqa.operators.base import ExecutionContext


class SemiJoinOperator(Operator):
    """Semi-join: returns PostingList of left entries that have a match in right.

    Hash join pattern -- build hash set from right, probe with left.
    Only checks existence, does not produce combined payloads.
    """

    def __init__(
        self,
        left: Operator,
        right: Operator,
        condition: Callable[[PostingEntry, PostingEntry], bool] | None = None,
    ) -> None:
        self._left = left
        self._right = right
        self._condition = condition

    def execute(self, context: ExecutionContext) -> PostingList:
        left_pl = self._left.execute(context)
        right_pl = self._right.execute(context)

        if self._condition is None:
            # Fast path: join on doc_id equality using a hash set.
            right_ids = right_pl.doc_ids
            result = [e for e in left_pl.entries if e.doc_id in right_ids]
        else:
            # General path: build a dict keyed by doc_id for right entries,
            # then probe each left entry against all right entries using the
            # condition callable.  A dict-of-lists is used so that the
            # condition can inspect any field, not just doc_id.
            right_by_id: dict[int, list[PostingEntry]] = {}
            for r in right_pl.entries:
                right_by_id.setdefault(r.doc_id, []).append(r)

            right_entries = right_pl.entries
            result: list[PostingEntry] = []
            for left_entry in left_pl.entries:
                # Check against entries sharing the same doc_id first, then
                # fall back to a full scan if no id-based bucket exists.
                # Because the condition is arbitrary, we must scan all right
                # entries to guarantee correctness.
                matched = False
                for right_entry in right_entries:
                    if self._condition(left_entry, right_entry):
                        matched = True
                        break
                if matched:
                    result.append(left_entry)

        return PostingList.from_sorted(result)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self._left.cost_estimate(stats) + self._right.cost_estimate(stats)


class AntiJoinOperator(Operator):
    """Anti-join: returns PostingList of left entries that have NO match in right.

    Hash join pattern -- build hash set from right, probe with left.
    Only checks existence, does not produce combined payloads.
    """

    def __init__(
        self,
        left: Operator,
        right: Operator,
        condition: Callable[[PostingEntry, PostingEntry], bool] | None = None,
    ) -> None:
        self._left = left
        self._right = right
        self._condition = condition

    def execute(self, context: ExecutionContext) -> PostingList:
        left_pl = self._left.execute(context)
        right_pl = self._right.execute(context)

        if self._condition is None:
            # Fast path: join on doc_id equality using a hash set.
            right_ids = right_pl.doc_ids
            result = [e for e in left_pl.entries if e.doc_id not in right_ids]
        else:
            # General path: keep left entries that have NO match in right.
            right_entries = right_pl.entries
            result: list[PostingEntry] = []
            for left_entry in left_pl.entries:
                matched = False
                for right_entry in right_entries:
                    if self._condition(left_entry, right_entry):
                        matched = True
                        break
                if not matched:
                    result.append(left_entry)

        return PostingList.from_sorted(result)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self._left.cost_estimate(stats) + self._right.cost_estimate(stats)
