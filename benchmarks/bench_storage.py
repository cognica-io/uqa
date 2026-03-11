#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for the SQLite-backed storage layer.

Covers SQLiteDocumentStore, SQLiteInvertedIndex, SQLiteVectorIndex,
and SQLiteGraphStore throughput.
"""

from __future__ import annotations

import sqlite3
import tempfile

import numpy as np
import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from benchmarks.data.schemas import BENCH_TABLE_COLUMNS
from uqa.core.types import Edge, Vertex
from uqa.storage.sqlite_document_store import SQLiteDocumentStore
from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex
from uqa.storage.sqlite_vector_index import SQLiteVectorIndex
from uqa.graph.store import GraphStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc_store(conn: sqlite3.Connection) -> SQLiteDocumentStore:
    return SQLiteDocumentStore(conn, "bench", BENCH_TABLE_COLUMNS)


def _make_inverted_index(conn: sqlite3.Connection) -> SQLiteInvertedIndex:
    return SQLiteInvertedIndex(conn, "bench")


# ---------------------------------------------------------------------------
# Document Store
# ---------------------------------------------------------------------------

class TestDocumentStore:
    def test_put_single(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        conn = sqlite3.connect(":memory:")
        store = _make_doc_store(conn)
        idx = [0]

        def put_one() -> None:
            i = idx[0] % len(rows)
            store.put(i + 1, rows[i])
            idx[0] += 1

        benchmark(put_one)
        conn.close()

    @pytest.mark.parametrize("batch_size", [10, 100])
    def test_put_batch(self, benchmark, batch_size: int) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        conn = sqlite3.connect(":memory:")
        store = _make_doc_store(conn)

        def put_batch() -> None:
            for i in range(batch_size):
                store.put(i + 1, rows[i % len(rows)])

        benchmark(put_batch)
        conn.close()

    def test_get_random(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        conn = sqlite3.connect(":memory:")
        store = _make_doc_store(conn)
        for i, row in enumerate(rows):
            store.put(i + 1, row)

        rng = np.random.default_rng(99)
        ids = rng.integers(1, len(rows) + 1, size=1000)
        idx = [0]

        def get_one() -> None:
            doc_id = int(ids[idx[0] % len(ids)])
            store.get(doc_id)
            idx[0] += 1

        benchmark(get_one)
        conn.close()

    def test_scan_all(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        conn = sqlite3.connect(":memory:")
        store = _make_doc_store(conn)
        for i, row in enumerate(rows):
            store.put(i + 1, row)

        def scan() -> int:
            return len(store.doc_ids)

        count = benchmark(scan)
        assert count == 1000
        conn.close()


# ---------------------------------------------------------------------------
# Inverted Index
# ---------------------------------------------------------------------------

class TestInvertedIndex:
    def test_add_document(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        term_docs = gen.term_documents(num_docs=100, terms_per_doc=50)
        conn = sqlite3.connect(":memory:")
        idx = _make_inverted_index(conn)
        counter = [0]

        def add_one() -> None:
            i = counter[0] % len(term_docs)
            doc_id, fields = term_docs[i]
            # Use a unique doc_id each time to avoid replace overhead
            idx.add_document(counter[0] + 10000, fields)
            counter[0] += 1

        benchmark(add_one)
        conn.close()

    def test_get_posting_list(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        term_docs = gen.term_documents(num_docs=500, terms_per_doc=50)
        conn = sqlite3.connect(":memory:")
        idx = _make_inverted_index(conn)
        for doc_id, fields in term_docs:
            idx.add_document(doc_id, fields)

        # Pick a frequent term
        pl = idx.get_posting_list("body", "term_000000")
        if len(pl) == 0:
            # Fallback: use any term that exists
            stats = idx.stats
            term = next(
                (t for (f, t), c in stats._doc_freqs.items() if c > 10),
                "term_000001",
            )
        else:
            term = "term_000000"

        def lookup() -> int:
            return len(idx.get_posting_list("body", term))

        benchmark(lookup)
        conn.close()

    def test_doc_freq(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        term_docs = gen.term_documents(num_docs=500, terms_per_doc=50)
        conn = sqlite3.connect(":memory:")
        idx = _make_inverted_index(conn)
        for doc_id, fields in term_docs:
            idx.add_document(doc_id, fields)

        benchmark(idx.doc_freq, "body", "term_000001")
        conn.close()


# ---------------------------------------------------------------------------
# Vector Index
# ---------------------------------------------------------------------------

class TestVectorIndex:
    def test_build_index(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vecs = gen.vectors(dim=128)
        n = min(500, len(vecs))

        def build() -> int:
            conn = sqlite3.connect(":memory:")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _vectors "
                "(doc_id INTEGER PRIMARY KEY, dimensions INTEGER, embedding BLOB)"
            )
            vi = SQLiteVectorIndex(conn, dimensions=128, max_elements=n + 100)
            for i in range(n):
                vi.add(i + 1, vecs[i])
            count = vi.count()
            conn.close()
            return count

        count = benchmark(build)
        assert count == n

    @pytest.mark.parametrize("k", [10, 50])
    def test_knn_search(self, benchmark, k: int) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vecs = gen.vectors(dim=128)
        n = min(500, len(vecs))
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _vectors "
            "(doc_id INTEGER PRIMARY KEY, dimensions INTEGER, embedding BLOB)"
        )
        vi = SQLiteVectorIndex(conn, dimensions=128, max_elements=n + 100)
        for i in range(n):
            vi.add(i + 1, vecs[i])

        query = gen.query_vector(dim=128)

        def search() -> int:
            return len(vi.search_knn(query, k))

        count = benchmark(search)
        assert count == k
        conn.close()


# ---------------------------------------------------------------------------
# Graph Store
# ---------------------------------------------------------------------------

class TestGraphStore:
    def test_add_vertices(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vertices, _ = gen.graph()
        vertices = vertices[:500]

        def build() -> int:
            gs = GraphStore()
            for v in vertices:
                gs.add_vertex(v)
            return len(gs.vertices)

        count = benchmark(build)
        assert count == len(vertices)

    def test_add_edges(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vertices, edges = gen.graph()
        gs = GraphStore()
        for v in vertices:
            gs.add_vertex(v)
        edges = edges[:1000]

        def add_edges() -> int:
            for e in edges:
                gs.add_edge(e)
            return len(gs.edges)

        benchmark(add_edges)

    def test_neighbors(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vertices, edges = gen.graph()
        gs = GraphStore()
        for v in vertices:
            gs.add_vertex(v)
        for e in edges:
            gs.add_edge(e)

        # Pick a vertex with high degree
        vertex_id = edges[0].source_id

        def get_neighbors() -> int:
            return len(gs.neighbors(vertex_id))

        benchmark(get_neighbors)

    def test_neighbors_with_label(self, benchmark) -> None:
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vertices, edges = gen.graph()
        gs = GraphStore()
        for v in vertices:
            gs.add_vertex(v)
        for e in edges:
            gs.add_edge(e)

        vertex_id = edges[0].source_id

        def get_neighbors_labeled() -> int:
            return len(gs.neighbors(vertex_id, label="knows"))

        benchmark(get_neighbors_labeled)
