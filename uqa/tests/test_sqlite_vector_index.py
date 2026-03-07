#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Section 3.2.3: Persistent HNSW Index (SQLiteVectorIndex).

Covers:
- Write-through persistence for vectors
- Loading from SQLite on construction
- Search correctness (KNN and threshold)
- Persistence across reconnection
- Delete support
- Engine integration
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.storage.catalog import Catalog
from uqa.storage.sqlite_vector_index import SQLiteVectorIndex


# -- Helpers ---------------------------------------------------------------


def _make_catalog(tmp_path) -> Catalog:
    db = str(tmp_path / "test.db")
    return Catalog(db)


def _random_vector(dim: int = 8, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randn(dim).astype(np.float32)


def _make_index(
    conn, dimensions: int = 8, max_elements: int = 100
) -> SQLiteVectorIndex:
    return SQLiteVectorIndex(
        conn, dimensions=dimensions, max_elements=max_elements
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
            "SELECT doc_id, dimensions FROM _vectors WHERE doc_id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == 8
        catalog.close()

    def test_add_multiple_vectors(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        for i in range(1, 6):
            idx.add(i, _random_vector(8, seed=i))

        count = catalog.conn.execute(
            "SELECT COUNT(*) FROM _vectors"
        ).fetchone()[0]
        assert count == 5
        assert idx.count() == 5
        catalog.close()

    def test_vector_blob_round_trip(self, tmp_path):
        catalog = _make_catalog(tmp_path)
        idx = _make_index(catalog.conn)

        vec = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
                       dtype=np.float32)
        idx.add(1, vec)

        row = catalog.conn.execute(
            "SELECT embedding FROM _vectors WHERE doc_id = 1"
        ).fetchone()
        restored = np.frombuffer(row[0], dtype=np.float32).copy()
        np.testing.assert_array_equal(restored, vec)
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
            "SELECT COUNT(*) FROM _vectors WHERE doc_id = 1"
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
# Engine Integration
# ======================================================================


class TestEngineIntegration:
    def test_engine_uses_sqlite_vector_index(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db, vector_dimensions=8) as engine:
            assert isinstance(engine.vector_index, SQLiteVectorIndex)

    def test_in_memory_engine_uses_plain_index(self):
        from uqa.engine import Engine
        from uqa.storage.vector_index import HNSWIndex

        engine = Engine(vector_dimensions=8)
        assert type(engine.vector_index) is HNSWIndex

    def test_vector_survives_engine_close_reopen(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)

        with Engine(db_path=db, vector_dimensions=8) as engine:
            engine.add_document(1, {"title": "test"}, embedding=vec)

        with Engine(db_path=db, vector_dimensions=8) as engine:
            query = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            result = engine.vector_index.search_knn(query, k=1)
            assert len(result.entries) == 1
            assert result.entries[0].doc_id == 1

    def test_delete_document_removes_vector(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        vec = np.array([1.0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)

        with Engine(db_path=db, vector_dimensions=8) as engine:
            engine.add_document(1, {"title": "test"}, embedding=vec)
            engine.delete_document(1)

        with Engine(db_path=db, vector_dimensions=8) as engine:
            assert engine.vector_index.count() == 0

    def test_multiple_vectors_persist(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db, vector_dimensions=4) as engine:
            for i in range(1, 6):
                vec = _random_vector(4, seed=i)
                engine.add_document(i, {"title": f"doc{i}"}, embedding=vec)

        with Engine(db_path=db, vector_dimensions=4) as engine:
            assert engine.vector_index.count() == 5
            query = _random_vector(4, seed=3)
            result = engine.vector_index.search_knn(query, k=1)
            assert result.entries[0].doc_id == 3
