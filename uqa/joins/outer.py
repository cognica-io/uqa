#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload
from uqa.joins.base import JoinCondition, JoinOperator


def _entry_doc_id(entry: object) -> int:
    """Extract doc_id from either PostingEntry or GeneralizedPostingEntry."""
    if hasattr(entry, "doc_ids"):
        return entry.doc_ids[0]  # type: ignore[union-attr]
    return entry.doc_id  # type: ignore[union-attr]


class LeftOuterJoinOperator(JoinOperator):
    """Hash join preserving all left entries.

    All left entries appear in the result. Unmatched left entries
    get a single-element doc_ids tuple and empty right-side fields.
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

        # Build hash table on right side
        right_index: dict[object, list] = defaultdict(list)
        for entry in right_entries:
            key = entry.payload.fields.get(self.condition.right_field)
            if key is not None:
                right_index[key].append(entry)

        # Probe from left side, preserving all left entries
        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_key = left_entry.payload.fields.get(self.condition.left_field)
            matches = right_index.get(left_key, []) if left_key is not None else []

            if matches:
                for right_entry in matches:
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
                            payload=Payload(score=merged_score, fields=merged_fields),
                        )
                    )
            else:
                # No match: preserve left entry with None right side
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(left_entry),),
                        payload=Payload(
                            score=left_entry.payload.score,
                            fields=dict(left_entry.payload.fields),
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


class RightOuterJoinOperator(JoinOperator):
    """Hash join preserving all right entries.

    Implemented via commutativity (Theorem 4.3.1): swap operands,
    run as LEFT JOIN, swap join condition fields.
    """

    def __init__(
        self,
        left: object,
        right: object,
        condition: JoinCondition,
    ) -> None:
        # Swap: run LEFT JOIN with right as left, left as right
        swapped_condition = JoinCondition(
            left_field=condition.right_field,
            right_field=condition.left_field,
        )
        super().__init__(left, right, swapped_condition)
        self._inner = LeftOuterJoinOperator(right, left, swapped_condition)

    def execute(self, context: object) -> GeneralizedPostingList:
        return self._inner.execute(context)


class FullOuterJoinOperator(JoinOperator):
    """Full outer join preserving all entries from both sides.

    FullJoin(L, R) = LeftJoin(L, R) UNION unmatched-right-rows.
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

        # Build hash table on right side
        right_index: dict[object, list] = defaultdict(list)
        for entry in right_entries:
            key = entry.payload.fields.get(self.condition.right_field)
            if key is not None:
                right_index[key].append(entry)

        # LEFT JOIN pass: all left entries, matched rights tracked
        matched_right_ids: set[int] = set()
        result: list[GeneralizedPostingEntry] = []

        for left_entry in left_entries:
            left_key = left_entry.payload.fields.get(self.condition.left_field)
            matches = right_index.get(left_key, []) if left_key is not None else []

            if matches:
                for right_entry in matches:
                    matched_right_ids.add(_entry_doc_id(right_entry))
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
                                score=merged_score,
                                fields=merged_fields,
                            ),
                        )
                    )
            else:
                # Unmatched left entry
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(left_entry),),
                        payload=Payload(
                            score=left_entry.payload.score,
                            fields=dict(left_entry.payload.fields),
                        ),
                    )
                )

        # Unmatched right entries
        for right_entry in right_entries:
            if _entry_doc_id(right_entry) not in matched_right_ids:
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(_entry_doc_id(right_entry),),
                        payload=Payload(
                            score=right_entry.payload.score,
                            fields=dict(right_entry.payload.fields),
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
