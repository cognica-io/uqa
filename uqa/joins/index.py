#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import bisect

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry
from uqa.joins.base import JoinCondition, JoinOperator

# Union of both entry types that flow through join operators.
JoinEntry = PostingEntry | GeneralizedPostingEntry


def _entry_doc_id(entry: JoinEntry) -> int:
    """Extract doc_id from either PostingEntry or GeneralizedPostingEntry."""
    if hasattr(entry, "doc_ids"):
        return entry.doc_ids[0]  # type: ignore[union-attr]
    return entry.doc_id  # type: ignore[union-attr]


class IndexJoinOperator(JoinOperator):
    """Index join using binary search on the right side (Section 6.3, Paper 1).

    Builds a sorted index on the right join key, then for each left
    entry performs a binary search to find matches.
    Complexity: O(|L1| * log|L2|).
    """

    def __init__(
        self,
        left: object,
        right: object,
        condition: JoinCondition,
    ) -> None:
        super().__init__(left, right, condition)

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        # Build sorted index on right join key: (key, entry) pairs sorted by key
        keyed_right: list[tuple[object, JoinEntry]] = []
        for entry in right_entries:
            key = entry.payload.fields.get(self.condition.right_field)
            if key is not None:
                keyed_right.append((key, entry))
        keyed_right.sort(key=lambda x: x[0])

        right_keys = [kr[0] for kr in keyed_right]

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_key = left_entry.payload.fields.get(self.condition.left_field)
            if left_key is None:
                continue

            # Binary search for left_key in right_keys
            lo = bisect.bisect_left(right_keys, left_key)
            while lo < len(right_keys) and right_keys[lo] == left_key:
                right_entry = keyed_right[lo][1]
                merged_fields = {
                    **left_entry.payload.fields,
                    **right_entry.payload.fields,
                }
                merged_score = left_entry.payload.score + right_entry.payload.score
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(
                            _entry_doc_id(left_entry),
                            _entry_doc_id(right_entry),
                        ),
                        payload=Payload(
                            score=merged_score, fields=merged_fields
                        ),
                    )
                )
                lo += 1

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[JoinEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
