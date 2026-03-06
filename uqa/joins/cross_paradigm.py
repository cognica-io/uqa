#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from uqa.core.posting_list import GeneralizedPostingList
from uqa.core.types import GeneralizedPostingEntry, Payload, PostingEntry
from uqa.joins.base import JoinCondition, JoinOperator

if TYPE_CHECKING:
    from uqa.graph.store import GraphStore


class TextSimilarityJoinOperator:
    """Jaccard similarity join between tokenized text fields.

    Nested loop join: for each pair, compute Jaccard similarity
    of token sets and emit if above threshold.
    """

    def __init__(
        self,
        left: object,
        right: object,
        left_field: str,
        right_field: str,
        threshold: float = 0.5,
    ) -> None:
        self.left = left
        self.right = right
        self.left_field = left_field
        self.right_field = right_field
        self.threshold = threshold

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_text = left_entry.payload.fields.get(self.left_field, "")
            left_tokens = set(str(left_text).lower().split())
            if not left_tokens:
                continue

            for right_entry in right_entries:
                right_text = right_entry.payload.fields.get(self.right_field, "")
                right_tokens = set(str(right_text).lower().split())
                if not right_tokens:
                    continue

                intersection = left_tokens & right_tokens
                union = left_tokens | right_tokens
                jaccard = len(intersection) / len(union) if union else 0.0

                if jaccard >= self.threshold:
                    merged_fields = {
                        **left_entry.payload.fields,
                        **right_entry.payload.fields,
                    }
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(left_entry.doc_id, right_entry.doc_id),
                            payload=Payload(score=jaccard, fields=merged_fields),
                        )
                    )

        return GeneralizedPostingList(result)

    @staticmethod
    def _get_entries(source: object, context: object) -> list[PostingEntry]:
        if hasattr(source, "execute"):
            pl = source.execute(context)  # type: ignore[attr-defined]
            return list(pl)
        return list(source)  # type: ignore[arg-type]


class VectorSimilarityJoinOperator:
    """Cosine similarity join between vector fields.

    Nested loop join: for each pair, compute cosine similarity
    and emit if above threshold.
    """

    def __init__(
        self,
        left: object,
        right: object,
        left_field: str,
        right_field: str,
        threshold: float = 0.5,
    ) -> None:
        self.left = left
        self.right = right
        self.left_field = left_field
        self.right_field = right_field
        self.threshold = threshold

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_vec = left_entry.payload.fields.get(self.left_field)
            if left_vec is None:
                continue
            left_arr = np.asarray(left_vec, dtype=np.float64)
            left_norm = np.linalg.norm(left_arr)
            if left_norm == 0.0:
                continue

            for right_entry in right_entries:
                right_vec = right_entry.payload.fields.get(self.right_field)
                if right_vec is None:
                    continue
                right_arr = np.asarray(right_vec, dtype=np.float64)
                right_norm = np.linalg.norm(right_arr)
                if right_norm == 0.0:
                    continue

                cosine_sim = float(
                    np.dot(left_arr, right_arr) / (left_norm * right_norm)
                )

                if cosine_sim >= self.threshold:
                    merged_fields = {
                        **left_entry.payload.fields,
                        **right_entry.payload.fields,
                    }
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(left_entry.doc_id, right_entry.doc_id),
                            payload=Payload(
                                score=cosine_sim, fields=merged_fields
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


class HybridJoinOperator:
    """Combines structured equijoin with vector similarity.

    First filters by structured field equality, then ranks
    by vector cosine similarity.
    """

    def __init__(
        self,
        left: object,
        right: object,
        structured_field: str,
        vector_field: str,
        threshold: float = 0.5,
    ) -> None:
        self.left = left
        self.right = right
        self.structured_field = structured_field
        self.vector_field = vector_field
        self.threshold = threshold

    def execute(self, context: object) -> GeneralizedPostingList:
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        # Build hash table on structured field for right side
        right_index: dict[object, list[PostingEntry]] = defaultdict(list)
        for entry in right_entries:
            key = entry.payload.fields.get(self.structured_field)
            if key is not None:
                right_index[key].append(entry)

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            left_key = left_entry.payload.fields.get(self.structured_field)
            if left_key is None:
                continue
            left_vec = left_entry.payload.fields.get(self.vector_field)
            if left_vec is None:
                continue
            left_arr = np.asarray(left_vec, dtype=np.float64)
            left_norm = np.linalg.norm(left_arr)
            if left_norm == 0.0:
                continue

            for right_entry in right_index.get(left_key, []):
                right_vec = right_entry.payload.fields.get(self.vector_field)
                if right_vec is None:
                    continue
                right_arr = np.asarray(right_vec, dtype=np.float64)
                right_norm = np.linalg.norm(right_arr)
                if right_norm == 0.0:
                    continue

                cosine_sim = float(
                    np.dot(left_arr, right_arr) / (left_norm * right_norm)
                )
                if cosine_sim >= self.threshold:
                    merged_fields = {
                        **left_entry.payload.fields,
                        **right_entry.payload.fields,
                    }
                    result.append(
                        GeneralizedPostingEntry(
                            doc_ids=(left_entry.doc_id, right_entry.doc_id),
                            payload=Payload(
                                score=cosine_sim, fields=merged_fields
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


class GraphJoinOperator:
    """Join two posting lists based on graph edge connectivity.

    For each (left_entry, right_entry) pair, checks whether a directed
    edge from left_entry.doc_id to right_entry.doc_id exists in the
    graph store (optionally filtered by label). Matched pairs are emitted.
    """

    def __init__(
        self,
        left: object,
        right: object,
        label: str | None = None,
    ) -> None:
        self.left = left
        self.right = right
        self.label = label

    def execute(self, context: object) -> GeneralizedPostingList:
        from uqa.graph.store import GraphStore

        graph: GraphStore = context.graph_store  # type: ignore[attr-defined]
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        right_set = {e.doc_id: e for e in right_entries}

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            neighbors = graph.neighbors(
                left_entry.doc_id, label=self.label, direction="out"
            )
            for neighbor_id in neighbors:
                right_entry = right_set.get(neighbor_id)
                if right_entry is None:
                    continue
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
        return list(source)  # type: ignore[arg-type]


class CrossParadigmJoinOperator:
    """Join graph vertices with document posting lists.

    Bridges the graph and relational paradigms: for each vertex in the
    left (graph) posting list, looks up the corresponding document in
    the right (document) posting list by matching vertex_field on the
    vertex properties against doc_field on the document payload.
    """

    def __init__(
        self,
        left: object,
        right: object,
        vertex_field: str,
        doc_field: str,
    ) -> None:
        self.left = left
        self.right = right
        self.vertex_field = vertex_field
        self.doc_field = doc_field

    def execute(self, context: object) -> GeneralizedPostingList:
        from uqa.graph.store import GraphStore

        graph: GraphStore = context.graph_store  # type: ignore[attr-defined]
        left_entries = self._get_entries(self.left, context)
        right_entries = self._get_entries(self.right, context)

        right_index: dict[object, list[PostingEntry]] = defaultdict(list)
        for entry in right_entries:
            key = entry.payload.fields.get(self.doc_field)
            if key is not None:
                right_index[key].append(entry)

        result: list[GeneralizedPostingEntry] = []
        for left_entry in left_entries:
            vertex = graph.get_vertex(left_entry.doc_id)
            if vertex is None:
                vertex_key = left_entry.payload.fields.get(self.vertex_field)
            else:
                vertex_key = vertex.properties.get(self.vertex_field)
            if vertex_key is None:
                continue
            for right_entry in right_index.get(vertex_key, []):
                merged_fields = {}
                if vertex is not None:
                    merged_fields.update(vertex.properties)
                merged_fields.update(left_entry.payload.fields)
                merged_fields.update(right_entry.payload.fields)
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
        return list(source)  # type: ignore[arg-type]
