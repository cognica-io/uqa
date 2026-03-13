#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""IVF (Inverted File Index) backed by SQLite.

IVF partitions the vector space into Voronoi cells around learned
centroids.  Each centroid owns a posting list of vectors.  At query
time only the ``nprobe`` nearest centroids are scanned, giving
sub-linear search.

SQLite tables (per table/field):
    "_ivf_centroids_{table}_{field}"  -- centroid blobs
    "_ivf_lists_{table}_{field}"      -- (centroid_id, doc_id, embedding)

Three states:
    UNTRAINED  -- fewer than ``train_threshold`` vectors; brute-force scan
    TRAINED    -- centroids are valid; IVF search
    STALE      -- >20%% deletes since last train; retrain on next search
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, Payload, PostingEntry
from uqa.storage.vector_index import VectorIndex

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.storage.managed_connection import SQLiteConnection

_UNTRAINED_CENTROID_ID = -1


class _State(enum.Enum):
    UNTRAINED = "untrained"
    TRAINED = "trained"
    STALE = "stale"


class IVFIndex(VectorIndex):
    """Inverted File Index with SQLite-backed persistence.

    Centroids are held in memory (small); posting lists live in SQLite.
    Vectors are L2-normalized on add so cosine similarity = dot product.
    """

    def __init__(
        self,
        conn: SQLiteConnection,
        table_name: str,
        field_name: str,
        dimensions: int,
        nlist: int = 100,
        nprobe: int = 10,
    ) -> None:
        self.dimensions = dimensions
        self._conn = conn
        self._table_name = table_name
        self._field_name = field_name
        self._nlist = nlist
        self._nprobe = nprobe

        self._centroids_table = f"_ivf_centroids_{table_name}_{field_name}"
        self._lists_table = f"_ivf_lists_{table_name}_{field_name}"

        self._create_tables()

        # In-memory centroid matrix (nlist x dimensions), loaded from SQLite.
        self._centroids: NDArray | None = None
        self._state = _State.UNTRAINED
        self._total_vectors = 0
        self._deletes_since_train = 0

        self._load_state()

    @property
    def train_threshold(self) -> int:
        """Minimum vector count before training triggers."""
        return max(2 * self._nlist, 256)

    # ------------------------------------------------------------------
    # SQLite DDL
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        ct = self._centroids_table
        lt = self._lists_table
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{ct}" ('
            f"    centroid_id INTEGER PRIMARY KEY,"
            f"    centroid   BLOB NOT NULL"
            f")"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{lt}" ('
            f"    centroid_id INTEGER NOT NULL,"
            f"    doc_id     INTEGER NOT NULL,"
            f"    embedding  BLOB NOT NULL,"
            f"    PRIMARY KEY (centroid_id, doc_id)"
            f")"
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{lt}_cid" '
            f'ON "{lt}" (centroid_id)'
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # State restoration from SQLite
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Restore centroids and counts from SQLite."""
        # Count total live vectors.
        row = self._conn.execute(
            f'SELECT COUNT(*) FROM "{self._lists_table}"'
        ).fetchone()
        self._total_vectors = row[0]

        # Load centroids.
        rows = self._conn.execute(
            f'SELECT centroid_id, centroid FROM "{self._centroids_table}" '
            f"WHERE centroid_id >= 0 ORDER BY centroid_id"
        ).fetchall()
        if rows:
            n = len(rows)
            self._centroids = np.empty((n, self.dimensions), dtype=np.float32)
            for i, (_cid, blob) in enumerate(rows):
                self._centroids[i] = np.frombuffer(blob, dtype=np.float32)
            self._state = _State.TRAINED
        else:
            self._state = _State.UNTRAINED

    # ------------------------------------------------------------------
    # VectorIndex interface
    # ------------------------------------------------------------------

    def add(self, doc_id: DocId, vector: NDArray) -> None:
        vec = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        blob = vec.tobytes()

        if self._state == _State.TRAINED:
            centroid_id = int(self._assign_centroid(vec))
        else:
            centroid_id = _UNTRAINED_CENTROID_ID

        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._lists_table}" '
            f"(centroid_id, doc_id, embedding) VALUES (?, ?, ?)",
            (centroid_id, doc_id, blob),
        )
        self._conn.commit()
        self._total_vectors += 1

        # Auto-train when enough vectors accumulate.
        if (
            self._state == _State.UNTRAINED
            and self._total_vectors >= self.train_threshold
        ):
            self._train()

    def delete(self, doc_id: DocId) -> None:
        row = self._conn.execute(
            f'SELECT centroid_id FROM "{self._lists_table}" WHERE doc_id = ?',
            (doc_id,),
        ).fetchone()
        if row is None:
            return

        self._conn.execute(
            f'DELETE FROM "{self._lists_table}" WHERE doc_id = ?',
            (doc_id,),
        )
        self._conn.commit()
        self._total_vectors -= 1
        self._deletes_since_train += 1

        # Mark stale if >20% deletes since last train.
        if (
            self._state == _State.TRAINED
            and self._total_vectors > 0
            and self._deletes_since_train > self._total_vectors * 0.2
        ):
            self._state = _State.STALE

    def clear(self) -> None:
        self._conn.execute(f'DELETE FROM "{self._lists_table}"')
        self._conn.execute(f'DELETE FROM "{self._centroids_table}"')
        self._conn.commit()
        self._centroids = None
        self._state = _State.UNTRAINED
        self._total_vectors = 0
        self._deletes_since_train = 0

    def search_knn(self, query: NDArray, k: int) -> PostingList:
        if self._total_vectors == 0:
            return PostingList()

        if self._state == _State.STALE:
            self._train()

        q = np.asarray(query, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        if self._state == _State.UNTRAINED:
            return self._brute_force_knn(q, k)

        return self._ivf_knn(q, k)

    def search_threshold(self, query: NDArray, threshold: float) -> PostingList:
        if self._total_vectors == 0:
            return PostingList()

        if self._state == _State.STALE:
            self._train()

        q = np.asarray(query, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        if self._state == _State.UNTRAINED:
            return self._brute_force_threshold(q, threshold)

        return self._ivf_threshold(q, threshold)

    def count(self) -> int:
        return self._total_vectors

    # ------------------------------------------------------------------
    # Centroid assignment
    # ------------------------------------------------------------------

    def _assign_centroid(self, normalized_vec: NDArray) -> int:
        """Return the index of the nearest centroid."""
        assert self._centroids is not None
        dots = self._centroids @ normalized_vec
        return int(np.argmax(dots))

    def _nearest_centroids(self, normalized_query: NDArray, nprobe: int) -> list[int]:
        """Return indices of the ``nprobe`` nearest centroids."""
        assert self._centroids is not None
        n = len(self._centroids)
        actual_nprobe = min(nprobe, n)
        dots = self._centroids @ normalized_query
        # argpartition is O(n) vs O(n log n) for full sort.
        if actual_nprobe >= n:
            return list(range(n))
        indices = np.argpartition(dots, -actual_nprobe)[-actual_nprobe:]
        return [int(i) for i in indices]

    # ------------------------------------------------------------------
    # Brute-force search (UNTRAINED state)
    # ------------------------------------------------------------------

    def _brute_force_knn(self, q: NDArray, k: int) -> PostingList:
        rows = self._conn.execute(
            f'SELECT doc_id, embedding FROM "{self._lists_table}"'
        ).fetchall()
        if not rows:
            return PostingList()

        scored: list[tuple[int, float]] = []
        for doc_id, blob in rows:
            vec = np.frombuffer(blob, dtype=np.float32)
            sim = float(np.dot(q, vec))
            scored.append((doc_id, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        actual_k = min(k, len(scored))
        entries = [
            PostingEntry(did, Payload(score=sim))
            for did, sim in scored[:actual_k]
        ]
        return PostingList(entries)

    def _brute_force_threshold(self, q: NDArray, threshold: float) -> PostingList:
        rows = self._conn.execute(
            f'SELECT doc_id, embedding FROM "{self._lists_table}"'
        ).fetchall()
        entries: list[PostingEntry] = []
        for doc_id, blob in rows:
            vec = np.frombuffer(blob, dtype=np.float32)
            sim = float(np.dot(q, vec))
            if sim >= threshold:
                entries.append(PostingEntry(doc_id, Payload(score=sim)))
        return PostingList(entries)

    # ------------------------------------------------------------------
    # IVF search (TRAINED state)
    # ------------------------------------------------------------------

    def _ivf_knn(self, q: NDArray, k: int) -> PostingList:
        centroid_ids = self._nearest_centroids(q, self._nprobe)

        # Also scan the untrained bucket (-1) for vectors added since
        # the last train.
        centroid_ids_with_untrained = centroid_ids + [_UNTRAINED_CENTROID_ID]

        scored: list[tuple[int, float]] = []
        for cid in centroid_ids_with_untrained:
            rows = self._conn.execute(
                f'SELECT doc_id, embedding FROM "{self._lists_table}" '
                f"WHERE centroid_id = ?",
                (cid,),
            ).fetchall()
            for doc_id, blob in rows:
                vec = np.frombuffer(blob, dtype=np.float32)
                sim = float(np.dot(q, vec))
                scored.append((doc_id, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        actual_k = min(k, len(scored))
        entries = [
            PostingEntry(did, Payload(score=sim))
            for did, sim in scored[:actual_k]
        ]
        return PostingList(entries)

    def _ivf_threshold(self, q: NDArray, threshold: float) -> PostingList:
        centroid_ids = self._nearest_centroids(q, self._nprobe)
        centroid_ids_with_untrained = centroid_ids + [_UNTRAINED_CENTROID_ID]

        entries: list[PostingEntry] = []
        for cid in centroid_ids_with_untrained:
            rows = self._conn.execute(
                f'SELECT doc_id, embedding FROM "{self._lists_table}" '
                f"WHERE centroid_id = ?",
                (cid,),
            ).fetchall()
            for doc_id, blob in rows:
                vec = np.frombuffer(blob, dtype=np.float32)
                sim = float(np.dot(q, vec))
                if sim >= threshold:
                    entries.append(PostingEntry(doc_id, Payload(score=sim)))
        return PostingList(entries)

    # ------------------------------------------------------------------
    # k-means training
    # ------------------------------------------------------------------

    def _train(self) -> None:
        """Run k-means on all vectors and reassign posting lists."""
        rows = self._conn.execute(
            f'SELECT doc_id, embedding FROM "{self._lists_table}"'
        ).fetchall()
        if not rows:
            return

        n = len(rows)
        doc_ids = [r[0] for r in rows]
        data = np.empty((n, self.dimensions), dtype=np.float32)
        for i, (_did, blob) in enumerate(rows):
            data[i] = np.frombuffer(blob, dtype=np.float32)

        actual_nlist = min(self._nlist, n)
        if actual_nlist < 1:
            return

        centroids = self._kmeans(data, actual_nlist)
        self._centroids = centroids

        # Persist centroids.
        self._conn.execute(f'DELETE FROM "{self._centroids_table}"')
        for i, c in enumerate(centroids):
            self._conn.execute(
                f'INSERT INTO "{self._centroids_table}" '
                f"(centroid_id, centroid) VALUES (?, ?)",
                (i, c.tobytes()),
            )

        # Reassign all vectors to their nearest centroid.
        assignments = data @ centroids.T  # (n, nlist)
        best = np.argmax(assignments, axis=1)

        for j, doc_id in enumerate(doc_ids):
            cid = int(best[j])
            self._conn.execute(
                f'UPDATE "{self._lists_table}" '
                f"SET centroid_id = ? WHERE doc_id = ?",
                (cid, doc_id),
            )

        self._conn.commit()
        self._state = _State.TRAINED
        self._deletes_since_train = 0

    def _kmeans(
        self,
        data: NDArray,
        k: int,
        max_iter: int = 25,
        tol: float = 1e-4,
    ) -> NDArray:
        """k-means++ initialization followed by Lloyd's iterations.

        All vectors are assumed to be L2-normalized (unit sphere).
        Returns centroids as an (k, dimensions) array, each row normalized.
        """
        n = len(data)
        rng = np.random.RandomState(42)

        # -- k-means++ initialization --
        centroids = np.empty((k, self.dimensions), dtype=np.float32)
        idx = rng.randint(n)
        centroids[0] = data[idx]

        for i in range(1, k):
            # Dot product similarity; distance = 1 - similarity.
            sims = data @ centroids[:i].T  # (n, i)
            max_sims = sims.max(axis=1)  # (n,)
            dists = 1.0 - max_sims
            dists = np.maximum(dists, 0.0)
            total = dists.sum()
            if total == 0:
                idx = rng.randint(n)
            else:
                probs = dists / total
                idx = rng.choice(n, p=probs)
            centroids[i] = data[idx]

        # -- Lloyd's iterations --
        for _ in range(max_iter):
            # Assign each vector to nearest centroid.
            sims = data @ centroids.T  # (n, k)
            labels = np.argmax(sims, axis=1)

            # Update centroids.
            new_centroids = np.zeros_like(centroids)
            counts = np.zeros(k, dtype=np.int64)
            for j in range(n):
                c = labels[j]
                new_centroids[c] += data[j]
                counts[c] += 1

            for c in range(k):
                if counts[c] > 0:
                    new_centroids[c] /= counts[c]
                    norm = np.linalg.norm(new_centroids[c])
                    if norm > 0:
                        new_centroids[c] /= norm
                else:
                    # Empty cluster: reinitialize from a random point.
                    new_centroids[c] = data[rng.randint(n)]

            # Check convergence.
            shift = np.linalg.norm(new_centroids - centroids)
            centroids = new_centroids
            if shift < tol:
                break

        return centroids
