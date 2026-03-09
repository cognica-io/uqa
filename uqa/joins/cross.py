#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload


def _entry_doc_id(entry: object) -> int:
    """Extract doc_id from either PostingEntry or GeneralizedPostingEntry."""
    if hasattr(entry, "doc_ids"):
        return entry.doc_ids[0]  # type: ignore[union-attr]
    return entry.doc_id  # type: ignore[union-attr]


class CrossJoinOperator:
    """Cartesian product join (CROSS JOIN).

    Produces all (left, right) pairs with no join condition.
    Bounded by Theorem 4.4.1: |result| <= |L| * |R|.
    """

    def __init__(self, left: object, right: object) -> None:
        self.left = left
        self.right = right

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            for right_entry in right_entries:
                merged_fields = {
                    **left_entry.payload.fields,
                    **right_entry.payload.fields,
                }
                merged_score = (
                    left_entry.payload.score + right_entry.payload.score
                )
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

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
