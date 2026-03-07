#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed HNSW vector index with write-through persistence.

Inherits from :class:`HNSWIndex` so all operators (KNNOperator,
VectorSimilarityOperator) work unchanged.  Every ``add()`` writes the
vector to the catalog's ``_vectors`` table in addition to inserting it
into the hnswlib in-memory graph.

On construction all existing vectors are loaded from SQLite and
re-inserted into hnswlib, rebuilding the HNSW graph structure.
This is O(N log N) since hnswlib's Python API does not expose
neighbor-list-level reconstruction.
"""

from __future__ import annotations

import sqlite3

import numpy as np
from numpy.typing import NDArray

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, Payload, PostingEntry
from uqa.storage.vector_index import HNSWIndex


class SQLiteVectorIndex(HNSWIndex):
    """HNSWIndex backed by SQLite for durable vector storage."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        dimensions: int,
        max_elements: int,
        ef_construction: int = 200,
        m: int = 16,
    ) -> None:
        super().__init__(dimensions, max_elements, ef_construction, m)
        self._conn = conn
        self._load_from_sqlite()

    # -- Loading -------------------------------------------------------

    def _load_from_sqlite(self) -> None:
        """Load all vectors from the ``_vectors`` table into hnswlib."""
        row = self._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='_vectors'"
        ).fetchone()
        if row is None:
            return

        rows = self._conn.execute(
            "SELECT doc_id, dimensions, embedding FROM _vectors"
        ).fetchall()
        for doc_id, dims, blob in rows:
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            super().add(doc_id, vec)

    # -- Mutations (write-through) -------------------------------------

    def add(self, doc_id: DocId, vector: NDArray) -> None:
        super().add(doc_id, vector)
        blob = vector.astype(np.float32).tobytes()
        self._conn.execute(
            "INSERT OR REPLACE INTO _vectors "
            "(doc_id, dimensions, embedding) VALUES (?, ?, ?)",
            (doc_id, len(vector), blob),
        )
        self._conn.commit()

    def delete(self, doc_id: DocId) -> None:
        """Remove a vector from SQLite and mark deleted in hnswlib."""
        internal_id = self._doc_id_to_internal.get(doc_id)
        if internal_id is not None:
            self._index.mark_deleted(internal_id)
            del self._doc_id_to_internal[doc_id]
            del self._internal_to_doc_id[internal_id]

        self._conn.execute(
            "DELETE FROM _vectors WHERE doc_id = ?", (doc_id,)
        )
        self._conn.commit()

    # -- Search (override to account for deleted elements) ---------------

    def search_knn(self, query: NDArray, k: int) -> PostingList:
        live_count = len(self._doc_id_to_internal)
        if live_count == 0:
            return PostingList()
        actual_k = min(k, live_count)
        labels, distances = self._index.knn_query(
            np.array([query], dtype=np.float32), k=actual_k
        )
        entries: list[PostingEntry] = []
        for label, dist in zip(labels[0], distances[0]):
            doc_id = self._internal_to_doc_id.get(int(label))
            if doc_id is None:
                continue
            similarity = 1.0 - float(dist)
            entries.append(PostingEntry(doc_id, Payload(score=similarity)))
        return PostingList(entries)

    def search_threshold(self, query: NDArray, threshold: float) -> PostingList:
        live_count = len(self._doc_id_to_internal)
        if live_count == 0:
            return PostingList()
        labels, distances = self._index.knn_query(
            np.array([query], dtype=np.float32), k=live_count
        )
        entries: list[PostingEntry] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity >= threshold:
                doc_id = self._internal_to_doc_id.get(int(label))
                if doc_id is None:
                    continue
                entries.append(PostingEntry(doc_id, Payload(score=similarity)))
        return PostingList(entries)

    # -- Metadata ------------------------------------------------------

    def count(self) -> int:
        """Return the number of live vectors in the index."""
        return len(self._doc_id_to_internal)
