#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

import hnswlib
import numpy as np

from uqa.core.posting_list import PostingList

if TYPE_CHECKING:
    from numpy.typing import NDArray
from uqa.core.types import DocId, Payload, PostingEntry

_INITIAL_CAPACITY = 1024


class HNSWIndex:
    """Hierarchical Navigable Small World graph for ANN search.

    Cost: O(d * log|D|) per query (Definition 6.2.1, Paper 1).
    Capacity grows automatically on insert.
    """

    def __init__(
        self,
        dimensions: int,
        ef_construction: int = 200,
        m: int = 16,
    ) -> None:
        self.dimensions = dimensions
        self._ef_construction = ef_construction
        self._m = m
        self._capacity = _INITIAL_CAPACITY
        self._index = hnswlib.Index(space="cosine", dim=dimensions)
        self._index.init_index(
            max_elements=self._capacity,
            ef_construction=ef_construction,
            M=m,
        )
        self._index.set_ef(50)
        self._doc_id_to_internal: dict[DocId, int] = {}
        self._internal_to_doc_id: dict[int, DocId] = {}
        self._next_internal: int = 0

    def add(self, doc_id: DocId, vector: NDArray) -> None:
        if self._next_internal >= self._capacity:
            self._capacity *= 2
            self._index.resize_index(self._capacity)
        internal_id = self._next_internal
        self._next_internal += 1
        self._doc_id_to_internal[doc_id] = internal_id
        self._internal_to_doc_id[internal_id] = doc_id
        self._index.add_items(
            np.array([vector], dtype=np.float32), np.array([internal_id])
        )

    def clear(self) -> None:
        """Reset the index by re-initializing the hnswlib graph."""
        self._capacity = _INITIAL_CAPACITY
        self._index = hnswlib.Index(space="cosine", dim=self.dimensions)
        self._index.init_index(
            max_elements=self._capacity,
            ef_construction=self._ef_construction,
            M=self._m,
        )
        self._index.set_ef(50)
        self._doc_id_to_internal.clear()
        self._internal_to_doc_id.clear()
        self._next_internal = 0

    def search_knn(self, query: NDArray, k: int) -> PostingList:
        """KNN_k operator (Definition 3.1.3)."""
        if self._next_internal == 0:
            return PostingList()
        actual_k = min(k, self._next_internal)
        labels, distances = self._index.knn_query(
            np.array([query], dtype=np.float32), k=actual_k
        )
        entries: list[PostingEntry] = []
        for label, dist in zip(labels[0], distances[0]):
            doc_id = self._internal_to_doc_id[int(label)]
            # hnswlib cosine distance = 1 - cosine_similarity
            similarity = 1.0 - float(dist)
            entries.append(PostingEntry(doc_id, Payload(score=similarity)))
        return PostingList(entries)

    def search_threshold(self, query: NDArray, threshold: float) -> PostingList:
        """V_theta operator (Definition 3.1.2).

        Uses progressive k-expansion: starts with a small k and doubles
        until the last result is below threshold or the index is exhausted.
        This preserves HNSW's O(d log N) advantage instead of always
        scanning the entire index.
        """
        total = self._next_internal
        if total == 0:
            return PostingList()

        query_arr = np.array([query], dtype=np.float32)
        k = min(100, total)
        entries: list[PostingEntry] = []

        while k <= total:
            labels, distances = self._index.knn_query(query_arr, k=k)
            entries.clear()
            all_above = True
            for label, dist in zip(labels[0], distances[0]):
                similarity = 1.0 - float(dist)
                if similarity >= threshold:
                    doc_id = self._internal_to_doc_id[int(label)]
                    entries.append(PostingEntry(doc_id, Payload(score=similarity)))
                else:
                    all_above = False
                    break

            if not all_above or k >= total:
                break
            # All results satisfied threshold -- expand k
            k = min(k * 2, total)

        return PostingList(entries)
