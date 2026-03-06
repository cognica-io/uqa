#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry
from uqa.joins.base import JoinCondition, JoinOperator


class SortMergeJoinOperator(JoinOperator):
    """Sort-merge join for pre-sorted inputs (Section 6.3, Paper 1).

    Exploits the posting list invariant (entries sorted by doc_id) to
    avoid hash table construction. When both inputs are sorted on the
    join key, merge in O(|L1| + |L2|).

    Falls back to sorting by join key if entries are not already ordered
    on that field.
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

        left_sorted = sorted(
            left_entries,
            key=lambda e: e.payload.fields.get(self.condition.left_field),
        )
        right_sorted = sorted(
            right_entries,
            key=lambda e: e.payload.fields.get(self.condition.right_field),
        )

        result: list[GeneralizedPostingEntry] = []
        i, j = 0, 0
        while i < len(left_sorted) and j < len(right_sorted):
            left_key = left_sorted[i].payload.fields.get(self.condition.left_field)
            right_key = right_sorted[j].payload.fields.get(self.condition.right_field)

            if left_key is None:
                i += 1
                continue
            if right_key is None:
                j += 1
                continue

            if left_key == right_key:
                # Collect all right entries with the same key
                right_start = j
                while (
                    j < len(right_sorted)
                    and right_sorted[j].payload.fields.get(self.condition.right_field)
                    == right_key
                ):
                    j += 1
                right_end = j

                # Collect all left entries with the same key
                left_start = i
                while (
                    i < len(left_sorted)
                    and left_sorted[i].payload.fields.get(self.condition.left_field)
                    == left_key
                ):
                    i += 1

                # Cross-product of matching groups
                for li in range(left_start, i):
                    for ri in range(right_start, right_end):
                        le = left_sorted[li]
                        re = right_sorted[ri]
                        merged_fields = {
                            **le.payload.fields,
                            **re.payload.fields,
                        }
                        merged_score = le.payload.score + re.payload.score
                        result.append(
                            GeneralizedPostingEntry(
                                doc_ids=(le.doc_id, re.doc_id),
                                payload=Payload(
                                    score=merged_score, fields=merged_fields
                                ),
                            )
                        )
            elif left_key < right_key:
                i += 1
            else:
                j += 1

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[PostingEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
