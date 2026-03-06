from __future__ import annotations

import hnswlib
import numpy as np
from numpy.typing import NDArray

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, Payload, PostingEntry


class HNSWIndex:
    """Hierarchical Navigable Small World graph for ANN search.

    Cost: O(d * log|D|) per query (Definition 6.2.1, Paper 1).
    """

    def __init__(
        self,
        dimensions: int,
        max_elements: int,
        ef_construction: int = 200,
        m: int = 16,
    ) -> None:
        self.dimensions = dimensions
        self._max_elements = max_elements
        self._index = hnswlib.Index(space="cosine", dim=dimensions)
        self._index.init_index(
            max_elements=max_elements,
            ef_construction=ef_construction,
            M=m,
        )
        self._index.set_ef(50)
        self._doc_id_to_internal: dict[DocId, int] = {}
        self._internal_to_doc_id: dict[int, DocId] = {}
        self._next_internal: int = 0

    def add(self, doc_id: DocId, vector: NDArray) -> None:
        internal_id = self._next_internal
        self._next_internal += 1
        self._doc_id_to_internal[doc_id] = internal_id
        self._internal_to_doc_id[internal_id] = doc_id
        self._index.add_items(
            np.array([vector], dtype=np.float32), np.array([internal_id])
        )

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
        """V_theta operator (Definition 3.1.2)."""
        if self._next_internal == 0:
            return PostingList()
        # Search with a large k, then filter by threshold
        k = self._next_internal
        labels, distances = self._index.knn_query(
            np.array([query], dtype=np.float32), k=k
        )
        entries: list[PostingEntry] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity >= threshold:
                doc_id = self._internal_to_doc_id[int(label)]
                entries.append(PostingEntry(doc_id, Payload(score=similarity)))
        return PostingList(entries)
