#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict

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

        # Build hash table on smaller side for better memory/cache behavior
        if len(left_entries) <= len(right_entries):
            build_entries, probe_entries = left_entries, right_entries
            build_field = self.condition.left_field
            probe_field = self.condition.right_field
            build_is_left = True
        else:
            build_entries, probe_entries = right_entries, left_entries
            build_field = self.condition.right_field
            probe_field = self.condition.left_field
            build_is_left = False

        build_index: dict[object, list[JoinEntry]] = defaultdict(list)
        for entry in build_entries:
            key = entry.payload.fields.get(build_field)
            if key is not None:
                build_index[key].append(entry)

        # Probe from larger side
        result: list[GeneralizedPostingEntry] = []
        for probe_entry in probe_entries:
            probe_key = probe_entry.payload.fields.get(probe_field)
            if probe_key is None:
                continue
            for build_entry in build_index.get(probe_key, []):
                # Preserve left/right ordering in output
                left_e = build_entry if build_is_left else probe_entry
                right_e = probe_entry if build_is_left else build_entry
                merged_fields = {
                    **left_e.payload.fields,
                    **right_e.payload.fields,
                }
                merged_score = left_e.payload.score + right_e.payload.score
                result.append(
                    GeneralizedPostingEntry(
                        doc_ids=(
                            _entry_doc_id(left_e),
                            _entry_doc_id(right_e),
                        ),
                        payload=Payload(score=merged_score, fields=merged_fields),
                    )
                )

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[JoinEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]
