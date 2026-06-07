#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload

if TYPE_CHECKING:
    from uqa.cancel import CancellationToken


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

    cancel_token: CancellationToken | None = None

    def __init__(self, left: object, right: object) -> None:
        self.left = left
        self.right = right

    def check_cancelled(self) -> None:
        """Raise :class:`~uqa.cancel.QueryCancelled` if cancelled."""
        if self.cancel_token is not None:
            self.cancel_token.check()

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)
        left_items = [
            (_entry_doc_id(entry), entry.payload.fields, entry.payload.score)
            for entry in left_entries
        ]
        right_items = [
            (_entry_doc_id(entry), entry.payload.fields, entry.payload.score)
            for entry in right_entries
        ]

        result: list[GeneralizedPostingEntry] = []
        for left_id, left_fields, left_score in left_items:
            self.check_cancelled()
            for right_id, right_fields, right_score in right_items:
                if not left_fields:
                    merged_fields = dict(right_fields)
                elif not right_fields:
                    merged_fields = dict(left_fields)
                else:
                    merged_fields = dict(left_fields)
                    merged_fields.update(right_fields)
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(
                            left_id,
                            right_id,
                        ),
                        payload=Payload(
                            score=left_score + right_score,
                            fields=merged_fields,
                        ),
                    )
                )

        return GeneralizedPostingList.from_sorted(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
