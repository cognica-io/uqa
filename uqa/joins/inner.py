from __future__ import annotations

from collections import defaultdict

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry
from uqa.joins.base import JoinCondition, JoinOperator


class InnerJoinOperator(JoinOperator):
    """Hash join implementation for inner join.

    Build hash table on right side, probe from left side.
    Only matching pairs appear in the result.
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
        right_index: dict[object, list[PostingEntry]] = defaultdict(list)
        for entry in right_entries:
            key = entry.payload.fields.get(self.condition.right_field)
            if key is not None:
                right_index[key].append(entry)

        # Probe from left side
        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_key = left_entry.payload.fields.get(self.condition.left_field)
            if left_key is None:
                continue
            for right_entry in right_index.get(left_key, []):
                merged_fields = {
                    **left_entry.payload.fields,
                    **right_entry.payload.fields,
                }
                merged_score = left_entry.payload.score + right_entry.payload.score
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(left_entry.doc_id, right_entry.doc_id),
                        payload=Payload(score=merged_score, fields=merged_fields),
                    )
                )

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[PostingEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        # Assume it's already iterable of PostingEntry
        return list(source)  # type: ignore[arg-type]
