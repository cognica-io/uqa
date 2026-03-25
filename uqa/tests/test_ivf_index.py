#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for IVF (Inverted File Index) vector index.

Covers:
- Write-through persistence
- Search correctness (KNN and threshold)
- Delete support
- Persistence across reconnection
- k-means convergence and auto-train
- Centroid persistence
- Retrain on stale state
- Engine integration
"""

from __future__ import annotations

import numpy as np

from uqa.storage.catalog import Catalog
from uqa.storage.ivf_index import IVFIndex

# -- Helpers ---------------------------------------------------------------


def _make_catalog(tmp_path) -> Catalog:
    db = str(tmp_path / "test.db")
    return Catalog(db)


def _random_vector(dim: int = 8, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v


def _make_index(
    conn,
    table_name: str = "test",
    field_name: str = "emb",
    dimensions: int = 8,
    nlist: int = 4,
    nprobe: int = 4,
) -> IVFIndex:
    return IVFIndex(
        conn,
        table_name=table_name,
        field_name=field_name,
        dimensions=dimensions,
        nlist=nlist,
        nprobe=nprobe,
    )


# ======================================================================
# Write-Through Persistence
# ======================================================================


class TestWriteThrough:
    def test_add_vector_persisted_to_sqlite(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)
        vec = _random_vector(8, seed=1)
        idx.add(1, vec)

        row = catalog.conn.execute(
            'SELECT doc_id FROM "_ivf_lists_test_emb" WHERE doc_id = 1'
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        catalog.close()

    def test_add_multiple_vectors(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        for i in range(1, 6):
            idx.add(i, _random_vector(8, seed=i))

        count = catalog.conn.execute(
            'SELECT COUNT(*) FROM "_ivf_lists_test_emb"'
        ).fetchone()[0]
        assert count == 5
        assert idx.count() == 5
        catalog.close()

    def test_vector_blob_round_trip(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        vec = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], dtype=np.float32)
        idx.add(1, vec)

        row = catalog.conn.execute(
            'SELECT embedding FROM "_ivf_lists_test_emb" WHERE doc_id = 1'
        ).fetchone()
        restored = np.frombuffer(row[0], dtype=np.float32).copy()
        # Vectors are normalized on add, so compare normalized versions.
        expected = vec / np.linalg.norm(vec)
        np.testing.assert_allclose(restored, expected, atol=1e-6)
        catalog.close()


# ======================================================================
# Search Correctness
# ======================================================================


class TestSearchCorrectness:
    def test_knn_search(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        # Insert vectors: v1 close to query, v2 far
        v1 = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        v2 = np.array([0, 0, 0, 0, 0, 0, 0, 1.0], dtype=np.float32)
        idx.add(1, v1)
        idx.add(2, v2)

        query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        result = idx.search_knn(query, k=1)
        assert len(result.entries) == 1
        assert result.entries[0].doc_id == 1
        catalog.close()

    def test_threshold_search(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        v1 = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        v2 = np.array([0, 0, 0, 0, 0, 0, 0, 1.0], dtype=np.float32)
        idx.add(1, v1)
        idx.add(2, v2)

        query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        result = idx.search_threshold(query, threshold=0.9)
        doc_ids = {e.doc_id for e in result.entries}
        assert 1 in doc_ids
        assert 2 not in doc_ids
        catalog.close()

    def test_knn_empty_index(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)
        query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        result = idx.search_knn(query, k=5)
        assert len(result.entries) == 0
        catalog.close()


# ======================================================================
# Delete
# ======================================================================


class TestDelete:
    def test_delete_removes_from_sqlite(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        idx.add(1, _random_vector(8, seed=1))
        idx.add(2, _random_vector(8, seed=2))
        idx.delete(1)

        row = catalog.conn.execute(
            'SELECT COUNT(*) FROM "_ivf_lists_test_emb" WHERE doc_id = 1'
        ).fetchone()
        assert row[0] == 0
        assert idx.count() == 1
        catalog.close()

    def test_delete_nonexistent_is_safe(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        # Should not raise
        idx.delete(999)
        assert idx.count() == 0
        catalog.close()

    def test_knn_after_delete(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        v1 = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        v2 = np.array([0, 1.0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        idx.add(1, v1)
        idx.add(2, v2)
        idx.delete(1)

        query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        result = idx.search_knn(query, k=2)
        doc_ids = {e.doc_id for e in result.entries}
        assert 1 not in doc_ids
        assert 2 in doc_ids
        catalog.close()


# ======================================================================
# Persistence Across Reconnection
# ======================================================================


class TestPersistence:
    def test_vectors_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        idx1 = _make_index(cat1.conn)
        v1 = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        v2 = np.array([0, 1.0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        idx1.add(1, v1)
        idx1.add(2, v2)
        cat1.close()

        cat2 = Catalog(db)
        idx2 = _make_index(cat2.conn)
        assert idx2.count() == 2

        query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        result = idx2.search_knn(query, k=1)
        assert len(result.entries) == 1
        assert result.entries[0].doc_id == 1
        cat2.close()

    def test_delete_persists_across_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        idx1 = _make_index(cat1.conn)
        idx1.add(1, _random_vector(8, seed=1))
        idx1.add(2, _random_vector(8, seed=2))
        idx1.delete(1)
        cat1.close()

        cat2 = Catalog(db)
        idx2 = _make_index(cat2.conn)
        assert idx2.count() == 1
        cat2.close()

    def test_search_accuracy_after_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        idx1 = _make_index(cat1.conn)
        for i in range(1, 11):
            idx1.add(i, _random_vector(8, seed=i))
        cat1.close()

        cat2 = Catalog(db)
        idx2 = _make_index(cat2.conn)
        assert idx2.count() == 10

        query = _random_vector(8, seed=5)
        result = idx2.search_knn(query, k=1)
        assert len(result.entries) == 1
        # The closest vector should be doc_id 5 (same seed)
        assert result.entries[0].doc_id == 5
        cat2.close()


# ======================================================================
# k-means and Auto-Train
# ======================================================================


class TestAutoTrain:
    def test_cold_start_brute_force(self, tmp_path):
        """With few vectors, index stays in UNTRAINED state and uses brute force."""
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn, nlist=4)

        # Add fewer vectors than train_threshold
        for i in range(1, 6):
            idx.add(i, _random_vector(8, seed=i))

        from uqa.storage.ivf_index import _State

        assert idx._state == _State.UNTRAINED

        # Search still works via brute force
        query = _random_vector(8, seed=3)
        result = idx.search_knn(query, k=1)
        assert result.entries[0].doc_id == 3
        catalog.close()

    def test_auto_train_triggers(self, tmp_path):
        """When enough vectors accumulate, training triggers automatically."""
        catalog = _make_catalog(tmp_path)
        # nlist=4 -> train_threshold = max(8, 256) = 256
        # Use small nlist so threshold is just 256.
        idx = _make_index(catalog.conn, nlist=4)

        from uqa.storage.ivf_index import _State

        for i in range(1, 257):
            idx.add(i, _random_vector(8, seed=i))

        assert idx._state == _State.TRAINED
        assert idx._centroids is not None
        assert len(idx._centroids) == 4

        # Verify centroids are persisted in SQLite (exclude sentinel rows)
        row = catalog.conn.execute(
            'SELECT COUNT(*) FROM "_ivf_centroids_test_emb" WHERE centroid_id >= 0'
        ).fetchone()
        assert row[0] == 4
        catalog.close()

    def test_centroid_persistence(self, tmp_path):
        """Centroids survive reconnection."""
        db = str(tmp_path / "persist.db")

        cat1 = Catalog(db)
        idx1 = _make_index(cat1.conn, nlist=4)
        for i in range(1, 257):
            idx1.add(i, _random_vector(8, seed=i))

        from uqa.storage.ivf_index import _State

        assert idx1._state == _State.TRAINED
        old_centroids = idx1._centroids.copy()
        cat1.close()

        cat2 = Catalog(db)
        idx2 = _make_index(cat2.conn, nlist=4)
        assert idx2._state == _State.TRAINED
        np.testing.assert_array_equal(idx2._centroids, old_centroids)
        cat2.close()

    def test_stale_triggers_retrain(self, tmp_path):
        """Deleting >20% of vectors marks state as STALE, and next search retrains."""
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn, nlist=4)

        # Insert enough to train
        for i in range(1, 257):
            idx.add(i, _random_vector(8, seed=i))

        from uqa.storage.ivf_index import _State

        assert idx._state == _State.TRAINED

        # Delete >20% of vectors (delete 60 out of 256)
        for i in range(1, 61):
            idx.delete(i)

        assert idx._state == _State.STALE

        # Next search triggers retrain
        query = _random_vector(8, seed=100)
        idx.search_knn(query, k=1)
        assert idx._state == _State.TRAINED
        catalog.close()

    def test_clear_resets_state(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn, nlist=4)

        for i in range(1, 257):
            idx.add(i, _random_vector(8, seed=i))

        from uqa.storage.ivf_index import _State

        assert idx._state == _State.TRAINED
        idx.clear()
        assert idx._state == _State.UNTRAINED
        assert idx.count() == 0
        catalog.close()


# ======================================================================
# Engine Integration
# ======================================================================


class TestEngineIntegration:
    def test_create_index_using_hnsw(self, tmp_path):
        """'USING hnsw' maps to IVF for backward compatibility."""
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (  id SERIAL PRIMARY KEY,  emb VECTOR(8))")
            assert engine._tables["docs"].vector_indexes == {}

            engine.sql("CREATE INDEX idx_emb ON docs USING hnsw (emb)")
            assert "emb" in engine._tables["docs"].vector_indexes
            assert isinstance(engine._tables["docs"].vector_indexes["emb"], IVFIndex)

    def test_create_index_using_ivf(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (  id SERIAL PRIMARY KEY,  emb VECTOR(8))")
            engine.sql("CREATE INDEX idx_emb ON docs USING ivf (emb)")
            assert "emb" in engine._tables["docs"].vector_indexes
            assert isinstance(engine._tables["docs"].vector_indexes["emb"], IVFIndex)

    def test_vector_stored_in_document_store(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (  id SERIAL PRIMARY KEY,  emb VECTOR(4))")
            engine.sql("INSERT INTO docs (emb) VALUES (ARRAY[1.0, 0, 0, 0])")
            doc = engine._tables["docs"].document_store.get(1)
            assert doc is not None
            assert doc["emb"] == [1.0, 0.0, 0.0, 0.0]

    def test_sql_insert_with_ivf_index(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(8)"
                ")"
            )
            engine.sql("CREATE INDEX idx_emb ON docs USING hnsw (emb)")

            vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
            engine.sql(f"INSERT INTO docs (title, emb) VALUES ('test', {arr})")

            vec_idx = engine._tables["docs"].vector_indexes["emb"]
            assert vec_idx.count() == 1

            query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            result = vec_idx.search_knn(query, k=1)
            assert len(result.entries) == 1
            assert result.entries[0].doc_id == 1

    def test_brute_force_knn_without_index(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(8)"
                ")"
            )
            vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
            engine.sql(f"INSERT INTO docs (title, emb) VALUES ('test', {arr})")

            # No vector index -- knn_match falls back to brute-force
            result = engine.sql(
                "SELECT title FROM docs WHERE knn_match(emb, $1, 1)",
                params=[vec],
            )
            assert len(result.rows) == 1
            assert result.rows[0]["title"] == "test"

    def test_add_document_stores_vector(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)

        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(8)"
                ")"
            )
            engine.add_document(1, {"title": "test"}, table="docs", embedding=vec)

            doc = engine._tables["docs"].document_store.get(1)
            assert doc is not None
            assert doc["emb"] == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def test_sql_data_persists_across_engine_restart(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(8)"
                ")"
            )
            vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
            engine.sql(f"INSERT INTO docs (title, emb) VALUES ('test', {arr})")

        # Both scalar and vector data persist across restart
        with Engine(db_path=db) as engine:
            result = engine.sql("SELECT title, emb FROM docs")
            assert len(result.rows) == 1
            assert result.rows[0]["title"] == "test"
            assert result.rows[0]["emb"] == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def test_delete_document_removes_from_store(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(8)"
                ")"
            )
            vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            engine.add_document(1, {"title": "test"}, table="docs", embedding=vec)
            engine.delete_document(1, table="docs")
            assert engine._tables["docs"].document_store.get(1) is None

    def test_create_index_on_existing_data(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql(
                "CREATE TABLE docs ("
                "  id SERIAL PRIMARY KEY,"
                "  title TEXT,"
                "  emb VECTOR(4)"
                ")"
            )
            for i in range(1, 6):
                vec = _random_vector(4, seed=i)
                engine.add_document(
                    i, {"title": f"doc{i}"}, table="docs", embedding=vec
                )

            # No index yet -- verify brute-force works
            query = _random_vector(4, seed=3)
            result = engine.sql(
                "SELECT id FROM docs WHERE knn_match(emb, $1, 1)",
                params=[query],
            )
            assert result.rows[0]["id"] == 3

            # Create index on existing data
            engine.sql("CREATE INDEX idx_emb ON docs USING hnsw (emb)")
            vec_idx = engine._tables["docs"].vector_indexes["emb"]
            assert vec_idx.count() == 5

            result2 = vec_idx.search_knn(query, k=1)
            assert result2.entries[0].doc_id == 3

    def test_ivf_index_persists_across_restart(self, tmp_path):
        """IVF index and its vectors are fully restored on engine restart."""
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (  id SERIAL PRIMARY KEY,  emb VECTOR(8))")
            engine.sql("CREATE INDEX idx_emb ON docs USING hnsw (emb)")

            for i in range(1, 11):
                vec = _random_vector(8, seed=i)
                arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
                engine.sql(f"INSERT INTO docs (emb) VALUES ({arr})")

        with Engine(db_path=db) as engine:
            vec_idx = engine._tables["docs"].vector_indexes.get("emb")
            assert vec_idx is not None
            assert isinstance(vec_idx, IVFIndex)
            assert vec_idx.count() == 10

            query = _random_vector(8, seed=5)
            result = vec_idx.search_knn(query, k=1)
            assert result.entries[0].doc_id == 5

    def test_ivf_with_custom_params(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, emb VECTOR(8))")
            engine.sql(
                "CREATE INDEX idx_emb ON docs "
                "USING ivf (emb) WITH (nlist = 8, nprobe = 4)"
            )
            vec_idx = engine._tables["docs"].vector_indexes["emb"]
            assert isinstance(vec_idx, IVFIndex)
            assert vec_idx._nlist == 8
            assert vec_idx._nprobe == 4

    def test_ivf_train_persists_across_restart(self, tmp_path):
        """IVF trained state (centroids + background stats) survives close/reopen."""
        from uqa.engine import Engine
        from uqa.storage.ivf_index import _State

        db = str(tmp_path / "train_persist.db")
        n_vectors = 300  # exceeds train_threshold (256)
        dims = 16

        with Engine(db_path=db) as engine:
            engine.sql(f"CREATE TABLE docs (id SERIAL PRIMARY KEY, emb VECTOR({dims}))")
            engine.sql("CREATE INDEX idx_emb ON docs USING ivf (emb) WITH (nlist = 4)")

            for i in range(1, n_vectors + 1):
                vec = _random_vector(dims, seed=i)
                arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
                engine.sql(f"INSERT INTO docs (emb) VALUES ({arr})")

            vec_idx = engine._tables["docs"].vector_indexes["emb"]
            assert isinstance(vec_idx, IVFIndex)
            assert vec_idx._state == _State.TRAINED
            assert vec_idx.background_stats is not None

        # Reopen and verify trained state is fully restored.
        with Engine(db_path=db) as engine:
            vec_idx = engine._tables["docs"].vector_indexes["emb"]
            assert isinstance(vec_idx, IVFIndex)
            assert vec_idx.count() == n_vectors
            assert vec_idx._state == _State.TRAINED
            assert vec_idx._centroids is not None
            assert vec_idx.background_stats is not None

            # KNN search must work with trained centroids.
            query = _random_vector(dims, seed=42)
            result = vec_idx.search_knn(query, k=5)
            assert len(result.entries) == 5

            # probed_distances must not raise.
            dists = vec_idx.probed_distances(query)
            assert len(dists) > 0
