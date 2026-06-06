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
    "_vectors"          -- canonical persistent vector rows
    "_ivf_indexes"      -- IVF metadata per table/field
    "_ivf_centroids"    -- centroid blobs per table/field
    "_ivf_assignments"  -- vector-to-centroid assignments

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
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from uqa.storage.managed_connection import SQLiteConnection

_UNTRAINED_CENTROID_ID = -1
_BACKGROUND_STATS_ID = -2


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
        self._has_reader = hasattr(conn, "read_fetchall")

        self._create_tables()

        # In-memory centroid matrix (nlist x dimensions), loaded from SQLite.
        self._centroids: NDArray | None = None
        self._state = _State.UNTRAINED
        self._total_vectors = 0
        self._deletes_since_train = 0
        self._background_mu: float | None = None
        self._background_sigma: float | None = None

        self._load_state()

    def _read_fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        if self._has_reader:
            return self._conn.read_fetchall(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchall()

    def _read_fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        if self._has_reader:
            return self._conn.read_fetchone(sql, params)  # type: ignore[union-attr]
        return self._conn.execute(sql, params).fetchone()

    @property
    def train_threshold(self) -> int:
        """Minimum vector count before training triggers."""
        return max(2 * self._nlist, 256)

    @property
    def nlist(self) -> int:
        """Number of IVF cells (centroids)."""
        return self._nlist

    @property
    def total_vectors(self) -> int:
        """Number of live vectors in the index."""
        return self._total_vectors

    @property
    def background_stats(self) -> tuple[float, float] | None:
        """Background distance distribution parameters (mu_G, sigma_G).

        Computed at train time from random query top-K distances
        (Definition 4.5.1).  Returns None if the index has not been
        trained or if no statistics are available.
        """
        if self._background_mu is not None and self._background_sigma is not None:
            return (self._background_mu, self._background_sigma)
        return None

    @property
    def background_samples(self) -> NDArray | None:
        """Raw distance samples underlying the background distribution.

        These are top-K distances from random queries, used to build
        a KDE for f_G (Definition 4.5.1).
        """
        return self._background_samples

    # ------------------------------------------------------------------
    # SQLite DDL
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        ct = self._centroids_table
        lt = self._lists_table
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _vectors ("
            "    table_name TEXT NOT NULL,"
            "    field TEXT NOT NULL,"
            "    doc_id INTEGER NOT NULL,"
            "    vector_ordinal INTEGER NOT NULL DEFAULT 0,"
            "    vector BLOB NOT NULL,"
            "    PRIMARY KEY (table_name, field, doc_id, vector_ordinal)"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _ivf_indexes ("
            "    table_name TEXT NOT NULL,"
            "    field TEXT NOT NULL,"
            "    dimensions INTEGER NOT NULL,"
            "    nlist INTEGER NOT NULL,"
            "    nprobe INTEGER NOT NULL,"
            "    train_threshold INTEGER NOT NULL,"
            "    state TEXT NOT NULL,"
            "    trained_size INTEGER NOT NULL,"
            "    deletes_since_train INTEGER NOT NULL,"
            "    vector_count INTEGER NOT NULL,"
            "    PRIMARY KEY (table_name, field)"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _ivf_centroids ("
            "    table_name TEXT NOT NULL,"
            "    field TEXT NOT NULL,"
            "    centroid_id INTEGER NOT NULL,"
            "    vector BLOB NOT NULL,"
            "    PRIMARY KEY (table_name, field, centroid_id)"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _ivf_assignments ("
            "    table_name TEXT NOT NULL,"
            "    field TEXT NOT NULL,"
            "    doc_id INTEGER NOT NULL,"
            "    vector_ordinal INTEGER NOT NULL DEFAULT 0,"
            "    centroid_id INTEGER NOT NULL,"
            "    PRIMARY KEY (table_name, field, doc_id, vector_ordinal)"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS _ivf_assignments_centroid_idx "
            "ON _ivf_assignments (table_name, field, centroid_id, doc_id, vector_ordinal)"
        )
        # Legacy Python mirror tables are kept for old tests and for
        # background calibration samples that canonical IVF metadata does
        # not persist.
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
            f'CREATE INDEX IF NOT EXISTS "{lt}_cid" ON "{lt}" (centroid_id)'
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # State restoration from SQLite
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Restore centroids, background stats, and counts from SQLite."""
        self._migrate_legacy_rows()

        # Count total live vectors.
        row = self._conn.execute(
            "SELECT COUNT(*) FROM _vectors WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        ).fetchone()
        self._total_vectors = int(row[0]) if row else 0

        # Load centroids.
        rows = self._conn.execute(
            "SELECT centroid_id, vector FROM _ivf_centroids "
            "WHERE table_name = ? AND field = ? AND centroid_id >= 0 "
            "ORDER BY centroid_id",
            (self._table_name, self._field_name),
        ).fetchall()
        if not rows:
            rows = self._conn.execute(
                f'SELECT centroid_id, centroid FROM "{self._centroids_table}" '
                f"WHERE centroid_id >= 0 ORDER BY centroid_id"
            ).fetchall()
        if rows:
            n = len(rows)
            self._centroids = np.empty((n, self.dimensions), dtype=np.float32)
            for i, (_, blob) in enumerate(rows):
                self._centroids[i] = np.frombuffer(blob, dtype=np.float32)
            self._state = _State.TRAINED
        else:
            self._state = _State.UNTRAINED

        meta_row = self._conn.execute(
            "SELECT state, deletes_since_train, vector_count FROM _ivf_indexes "
            "WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        ).fetchone()
        if meta_row is not None:
            try:
                self._state = _State(str(meta_row[0]))
            except ValueError:
                pass
            self._deletes_since_train = int(meta_row[1])
            self._total_vectors = self._count_vectors()
        if self._state != _State.UNTRAINED and self._centroids is None:
            self._state = _State.UNTRAINED

        # Load background distance distribution stats and samples.
        self._background_samples: np.ndarray | None = None
        bg_row = self._conn.execute(
            f'SELECT centroid FROM "{self._centroids_table}" WHERE centroid_id = ?',
            (_BACKGROUND_STATS_ID,),
        ).fetchone()
        if bg_row is not None:
            blob = np.frombuffer(bg_row[0], dtype=np.float64)
            self._background_mu = float(blob[0])
            self._background_sigma = float(blob[1])
            if len(blob) > 2:
                self._background_samples = blob[2:].copy()

    def _migrate_legacy_rows(self) -> None:
        """Copy old per-field IVF rows into the shared canonical tables."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM _vectors WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        ).fetchone()
        if row is not None and int(row[0]) > 0:
            return

        legacy_rows = self._conn.execute(
            f'SELECT centroid_id, doc_id, embedding FROM "{self._lists_table}"'
        ).fetchall()
        if not legacy_rows:
            return

        self._conn.executemany(
            "INSERT OR IGNORE INTO _vectors "
            "(table_name, field, doc_id, vector_ordinal, vector) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (self._table_name, self._field_name, int(doc_id), 0, bytes(blob))
                for _centroid_id, doc_id, blob in legacy_rows
            ],
        )
        assignments = [
            (
                self._table_name,
                self._field_name,
                int(doc_id),
                0,
                int(centroid_id),
            )
            for centroid_id, doc_id, _blob in legacy_rows
            if int(centroid_id) >= 0
        ]
        if assignments:
            self._conn.executemany(
                "INSERT OR IGNORE INTO _ivf_assignments "
                "(table_name, field, doc_id, vector_ordinal, centroid_id) "
                "VALUES (?, ?, ?, ?, ?)",
                assignments,
            )

        centroid_count = self._conn.execute(
            "SELECT COUNT(*) FROM _ivf_centroids WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        ).fetchone()
        if centroid_count is None or int(centroid_count[0]) == 0:
            centroid_rows = self._conn.execute(
                f'SELECT centroid_id, centroid FROM "{self._centroids_table}" '
                "WHERE centroid_id >= 0"
            ).fetchall()
            if centroid_rows:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO _ivf_centroids "
                    "(table_name, field, centroid_id, vector) VALUES (?, ?, ?, ?)",
                    [
                        (
                            self._table_name,
                            self._field_name,
                            int(centroid_id),
                            bytes(blob),
                        )
                        for centroid_id, blob in centroid_rows
                    ],
                )
        self._conn.commit()

    # ------------------------------------------------------------------
    # VectorIndex interface
    # ------------------------------------------------------------------

    def add(self, doc_id: DocId, vector: NDArray) -> None:
        raw_vectors = _coerce_vector_rows(vector, self.dimensions, self._field_name)
        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ? AND field = ? AND doc_id = ?",
            (self._table_name, self._field_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments "
            "WHERE table_name = ? AND field = ? AND doc_id = ?",
            (self._table_name, self._field_name, doc_id),
        )
        self._conn.execute(
            f'DELETE FROM "{self._lists_table}" WHERE doc_id = ?',
            (doc_id,),
        )

        if not raw_vectors:
            self._conn.commit()
            self._total_vectors = self._count_vectors()
            self._save_meta(self._state)
            return

        normalized_vectors = [_normalize(raw_vec) for raw_vec in raw_vectors]

        if self._state == _State.TRAINED:
            centroid_ids = [
                int(self._assign_centroid(vec)) for vec in normalized_vectors
            ]
        else:
            centroid_ids = [_UNTRAINED_CENTROID_ID] * len(normalized_vectors)

        self._conn.executemany(
            "INSERT OR REPLACE INTO _vectors "
            "(table_name, field, doc_id, vector_ordinal, vector) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    self._table_name,
                    self._field_name,
                    doc_id,
                    ordinal,
                    raw_vec.tobytes(),
                )
                for ordinal, raw_vec in enumerate(raw_vectors)
            ],
        )
        assignments = [
            (
                self._table_name,
                self._field_name,
                doc_id,
                ordinal,
                centroid_id,
            )
            for ordinal, centroid_id in enumerate(centroid_ids)
            if centroid_id >= 0
        ]
        if assignments:
            self._conn.executemany(
                "INSERT OR REPLACE INTO _ivf_assignments "
                "(table_name, field, doc_id, vector_ordinal, centroid_id) "
                "VALUES (?, ?, ?, ?, ?)",
                assignments,
            )
        # Legacy mirror tables have one row per document, so keep the
        # first vector as a compatibility representative.
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._lists_table}" '
            f"(centroid_id, doc_id, embedding) VALUES (?, ?, ?)",
            (centroid_ids[0], doc_id, normalized_vectors[0].tobytes()),
        )
        self._conn.commit()
        self._total_vectors = self._count_vectors()
        self._save_meta(self._state)

        # Auto-train when enough vectors accumulate.
        if (
            self._state == _State.UNTRAINED
            and self._total_vectors >= self.train_threshold
        ):
            self._train()

    def delete(self, doc_id: DocId) -> None:
        row = self._conn.execute(
            "SELECT 1 FROM _vectors "
            "WHERE table_name = ? AND field = ? AND doc_id = ? LIMIT 1",
            (self._table_name, self._field_name, doc_id),
        ).fetchone()
        if row is None:
            return

        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ? AND field = ? AND doc_id = ?",
            (self._table_name, self._field_name, doc_id),
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments "
            "WHERE table_name = ? AND field = ? AND doc_id = ?",
            (self._table_name, self._field_name, doc_id),
        )
        self._conn.execute(
            f'DELETE FROM "{self._lists_table}" WHERE doc_id = ?', (doc_id,)
        )
        self._conn.commit()
        self._total_vectors = max(self._count_vectors(), 0)
        self._deletes_since_train += 1

        # Mark stale if >20% deletes since last train.
        if (
            self._state == _State.TRAINED
            and self._total_vectors > 0
            and self._deletes_since_train > self._total_vectors * 0.2
        ):
            self._state = _State.STALE
        self._save_meta(self._state)

    def clear(self) -> None:
        self._conn.execute(
            "DELETE FROM _vectors WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.execute(
            "DELETE FROM _ivf_indexes WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.execute(
            "DELETE FROM _ivf_centroids WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.execute(
            "DELETE FROM _ivf_assignments WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.execute(f'DELETE FROM "{self._lists_table}"')
        self._conn.execute(f'DELETE FROM "{self._centroids_table}"')
        self._conn.commit()
        self._centroids = None
        self._state = _State.UNTRAINED
        self._total_vectors = 0
        self._deletes_since_train = 0
        self._background_mu = None
        self._background_sigma = None
        self._background_samples = None

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
        self._total_vectors = self._count_vectors()
        return self._total_vectors

    def _count_vectors(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM _vectors WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        ).fetchone()
        return int(row[0]) if row else 0

    def _load_vectors(self) -> list[tuple[int, int, NDArray, NDArray]]:
        rows = self._read_fetchall(
            "SELECT doc_id, vector_ordinal, vector FROM _vectors "
            "WHERE table_name = ? AND field = ? ORDER BY doc_id, vector_ordinal",
            (self._table_name, self._field_name),
        )
        out: list[tuple[int, int, NDArray, NDArray]] = []
        for doc_id, ordinal, blob in rows:
            raw = np.frombuffer(blob, dtype=np.float32).copy()
            out.append((int(doc_id), int(ordinal), raw, _normalize(raw)))
        return out

    def _save_meta(self, state: _State, trained_size: int | None = None) -> None:
        if trained_size is None:
            trained_size = self._total_vectors if state == _State.TRAINED else 0
        self._conn.execute(
            "INSERT OR REPLACE INTO _ivf_indexes "
            "(table_name, field, dimensions, nlist, nprobe, train_threshold, "
            "state, trained_size, deletes_since_train, vector_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self._table_name,
                self._field_name,
                self.dimensions,
                self._nlist,
                self._nprobe,
                self.train_threshold,
                state.value,
                trained_size,
                self._deletes_since_train,
                self._total_vectors,
            ),
        )
        self._conn.commit()

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
        rows = [(None, doc_id, vec) for doc_id, _ord, _raw, vec in self._load_vectors()]
        return self._rows_to_posting_list(rows, q, limit=k)

    def _brute_force_threshold(self, q: NDArray, threshold: float) -> PostingList:
        rows = [(None, doc_id, vec) for doc_id, _ord, _raw, vec in self._load_vectors()]
        return self._rows_to_posting_list(rows, q, threshold=threshold)

    # ------------------------------------------------------------------
    # IVF search (TRAINED state)
    # ------------------------------------------------------------------

    def probed_distances(self, query: NDArray) -> NDArray:
        """Return cosine distances to ALL vectors in the probed cells.

        This is the background distance distribution f_G for a specific
        query (Section 6.2b) -- the distances that the IVF search
        already computes but normally discards beyond the top-K.
        """
        q = np.asarray(query, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        if self._state != _State.TRAINED or self._centroids is None:
            # Brute-force: scan all vectors.
            vectors = [vec for _doc_id, _ord, _raw, vec in self._load_vectors()]
            if not vectors:
                return np.empty(0, dtype=np.float32)
            data = np.vstack(vectors)
            return 1.0 - (data @ q)

        centroid_ids = self._nearest_centroids(q, self._nprobe)
        centroid_ids_with_untrained = [*centroid_ids, _UNTRAINED_CENTROID_ID]
        rows = self._load_vectors_for_centroids(centroid_ids_with_untrained)
        if not rows:
            return np.empty(0, dtype=np.float32)
        data = np.vstack([vec for _centroid_id, _doc_id, vec in rows])
        return 1.0 - (data @ q)

    def _ivf_knn(self, q: NDArray, k: int) -> PostingList:
        centroid_ids = self._nearest_centroids(q, self._nprobe)

        # Also scan the untrained bucket (-1) for vectors added since
        # the last train.
        centroid_ids_with_untrained = [*centroid_ids, _UNTRAINED_CENTROID_ID]
        rows = self._load_vectors_for_centroids(centroid_ids_with_untrained)
        return self._rows_to_posting_list(rows, q, limit=k)

    def _ivf_threshold(self, q: NDArray, threshold: float) -> PostingList:
        centroid_ids = self._nearest_centroids(q, self._nprobe)
        centroid_ids_with_untrained = [*centroid_ids, _UNTRAINED_CENTROID_ID]
        rows = self._load_vectors_for_centroids(centroid_ids_with_untrained)
        return self._rows_to_posting_list(rows, q, threshold=threshold)

    def _load_vectors_for_centroids(
        self, centroid_ids: list[int]
    ) -> list[tuple[int | None, int, NDArray]]:
        if not centroid_ids:
            return []

        placeholders = ",".join("?" * len(centroid_ids))
        params = (self._table_name, self._field_name, *centroid_ids)
        rows = self._read_fetchall(
            "SELECT a.centroid_id, v.doc_id, v.vector "
            "FROM _ivf_assignments a "
            "JOIN _vectors v "
            "  ON v.table_name = a.table_name "
            " AND v.field = a.field "
            " AND v.doc_id = a.doc_id "
            " AND v.vector_ordinal = a.vector_ordinal "
            f"WHERE a.table_name = ? AND a.field = ? AND a.centroid_id IN ({placeholders})",
            params,
        )
        if rows:
            return [
                (
                    int(centroid_id),
                    int(doc_id),
                    _normalize(np.frombuffer(blob, dtype=np.float32)),
                )
                for centroid_id, doc_id, blob in rows
            ]

        # Legacy fallback for databases created before the shared tables.
        legacy_rows = self._read_fetchall(
            f'SELECT centroid_id, doc_id, embedding FROM "{self._lists_table}" '
            f"WHERE centroid_id IN ({placeholders})",
            tuple(centroid_ids),
        )
        return [
            (
                int(centroid_id),
                int(doc_id),
                np.frombuffer(blob, dtype=np.float32).copy(),
            )
            for centroid_id, doc_id, blob in legacy_rows
        ]

    def _rows_to_posting_list(
        self,
        rows: Sequence[tuple[int | None, int, NDArray]],
        q: NDArray,
        *,
        limit: int | None = None,
        threshold: float | None = None,
    ) -> PostingList:
        if not rows:
            return PostingList()

        best: dict[int, tuple[float, int | None]] = {}
        for centroid_id, doc_id, vec in rows:
            score = float(vec @ q)
            if threshold is not None and score < threshold:
                continue
            prev = best.get(doc_id)
            if prev is None or score > prev[0]:
                best[doc_id] = (score, centroid_id)

        ranked = sorted(best.items(), key=lambda item: item[1][0], reverse=True)
        if limit is not None:
            ranked = ranked[:limit]

        entries = []
        for doc_id, (score, centroid_id) in ranked:
            fields = {}
            if centroid_id is not None:
                fields["_centroid_id"] = centroid_id
            entries.append(PostingEntry(doc_id, Payload(score=score, fields=fields)))
        return PostingList(entries)

    # ------------------------------------------------------------------
    # k-means training
    # ------------------------------------------------------------------

    def cell_populations(self) -> dict[int, int]:
        """Return the number of vectors in each IVF cell.

        Returns a mapping from centroid_id to population count.
        Only includes cells with centroid_id >= 0 (trained cells).
        """
        rows = self._conn.execute(
            "SELECT centroid_id, COUNT(*) FROM _ivf_assignments "
            "WHERE table_name = ? AND field = ? AND centroid_id >= 0 "
            "GROUP BY centroid_id",
            (self._table_name, self._field_name),
        ).fetchall()
        return dict(rows)

    def _train(self) -> None:
        """Run k-means on all vectors and reassign posting lists."""
        rows = self._load_vectors()
        if not rows:
            return

        n = len(rows)
        doc_keys = [(doc_id, ordinal) for doc_id, ordinal, _raw, _vec in rows]
        data = np.vstack([vec for _doc_id, _ordinal, _raw, vec in rows])

        actual_nlist = min(self._nlist, n)
        if actual_nlist < 1:
            return

        centroids = self._kmeans(data, actual_nlist)
        self._centroids = centroids

        # Persist centroids (atomic: delete old + insert new).
        self._conn.execute(f'DELETE FROM "{self._centroids_table}"')
        self._conn.execute(
            "DELETE FROM _ivf_centroids WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.executemany(
            f'INSERT INTO "{self._centroids_table}" '
            f"(centroid_id, centroid) VALUES (?, ?)",
            [(i, c.tobytes()) for i, c in enumerate(centroids)],
        )
        self._conn.executemany(
            "INSERT INTO _ivf_centroids "
            "(table_name, field, centroid_id, vector) VALUES (?, ?, ?, ?)",
            [
                (self._table_name, self._field_name, i, c.tobytes())
                for i, c in enumerate(centroids)
            ],
        )
        self._conn.commit()

        # Reassign all vectors to their nearest centroid.
        assignments = data @ centroids.T  # (n, nlist)
        best = np.argmax(assignments, axis=1)

        self._conn.execute(
            "DELETE FROM _ivf_assignments WHERE table_name = ? AND field = ?",
            (self._table_name, self._field_name),
        )
        self._conn.executemany(
            "INSERT INTO _ivf_assignments "
            "(table_name, field, doc_id, vector_ordinal, centroid_id) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (self._table_name, self._field_name, doc_id, ordinal, int(best[j]))
                for j, (doc_id, ordinal) in enumerate(doc_keys)
            ],
        )
        self._conn.executemany(
            f'UPDATE "{self._lists_table}" SET centroid_id = ? WHERE doc_id = ?',
            [
                (int(best[j]), doc_id)
                for j, (doc_id, ordinal) in enumerate(doc_keys)
                if ordinal == 0
            ],
        )
        self._conn.commit()

        # Estimate background distance distribution f_G from random
        # query top-K distances (Definition 4.5.1).  We simulate random
        # queries, find their nearest neighbours in the corpus, and
        # collect the resulting distances.  This captures "what top-K
        # distances look like for a typical query" -- the correct
        # domain for the likelihood ratio denominator.
        data_seed = int(np.abs(data[:8].sum() * 1e6)) % (2**31)
        bg_rng = np.random.RandomState(data_seed)
        n_random_queries = 100
        k_per_query = min(50, n)
        random_queries = bg_rng.randn(n_random_queries, self.dimensions).astype(
            np.float32
        )
        norms = np.linalg.norm(random_queries, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-30)
        random_queries /= norms

        # Compute similarities for each random query and take the
        # top-k distances.
        all_bg_dists: list[float] = []
        for rq in random_queries:
            sims_rq = data @ rq  # (n,)
            if k_per_query >= n:
                top_sims = sims_rq
            else:
                top_idx = np.argpartition(sims_rq, -k_per_query)[-k_per_query:]
                top_sims = sims_rq[top_idx]
            all_bg_dists.extend((1.0 - top_sims).tolist())

        bg_samples = np.array(all_bg_dists, dtype=np.float64)
        self._background_mu = float(np.mean(bg_samples))
        self._background_sigma = max(float(np.std(bg_samples)), 1e-10)
        self._background_samples = bg_samples

        # Persist: mu, sigma, and the raw samples for KDE evaluation.
        bg_blob = np.concatenate(
            [
                np.array(
                    [self._background_mu, self._background_sigma], dtype=np.float64
                ),
                bg_samples,
            ]
        ).tobytes()
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._centroids_table}" '
            f"(centroid_id, centroid) VALUES (?, ?)",
            (_BACKGROUND_STATS_ID, bg_blob),
        )

        self._conn.commit()
        self._state = _State.TRAINED
        self._deletes_since_train = 0
        self._total_vectors = self._count_vectors()
        self._save_meta(self._state, trained_size=self._total_vectors)

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

            # Update centroids using vectorized scatter-add.
            new_centroids = np.zeros_like(centroids)
            np.add.at(new_centroids, labels, data)
            counts = np.bincount(labels, minlength=k)

            nonempty = counts > 0
            new_centroids[nonempty] /= counts[nonempty, np.newaxis]
            norms = np.linalg.norm(new_centroids[nonempty], axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-30)
            new_centroids[nonempty] /= norms

            empty = ~nonempty
            n_empty = empty.sum()
            if n_empty > 0:
                new_centroids[empty] = data[rng.choice(n, size=n_empty)]

            # Check convergence.
            shift = np.linalg.norm(new_centroids - centroids)
            centroids = new_centroids
            if shift < tol:
                break

        return centroids


def _normalize(vec: NDArray) -> NDArray:
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        return (arr / norm).astype(np.float32)
    return arr


def _coerce_vector_rows(
    value: NDArray, dimensions: int, field_name: str
) -> list[NDArray]:
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 1:
        rows = [arr]
    elif arr.ndim == 2:
        rows = [arr[i] for i in range(arr.shape[0])]
    else:
        raise ValueError(
            f"Vector field '{field_name}' requires a 1-D vector or 2-D tensor, "
            f"got {arr.ndim}-D value"
        )

    for row in rows:
        if row.shape[0] != dimensions:
            raise ValueError(
                f"Vector field '{field_name}' requires {dimensions} dimensions, "
                f"got {row.shape[0]}"
            )
    return [row.copy() for row in rows]
