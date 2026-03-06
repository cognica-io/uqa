from __future__ import annotations

from collections import defaultdict

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry
from uqa.joins.base import JoinCondition, JoinOperator


class LeftOuterJoinOperator(JoinOperator):
    """Hash join preserving all left entries.

    All left entries appear in the result. Unmatched left entries
    get a None right doc_id and empty right-side fields.
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
                    merged_score = (
                        left_entry.payload.score + right_entry.payload.score
                    )
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(left_entry.doc_id, right_entry.doc_id),
                            payload=Payload(
                                score=merged_score, fields=merged_fields
                            ),
                        )
                    )
            else:
                # No match: preserve left entry with None right side
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(left_entry.doc_id,),
                        payload=Payload(
                            score=left_entry.payload.score,
                            fields=dict(left_entry.payload.fields),
                        ),
                    )
                )

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[PostingEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
