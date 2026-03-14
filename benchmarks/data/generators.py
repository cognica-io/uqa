#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Deterministic data generators for benchmarks.

All generators use a fixed seed for reproducibility. The ``scale_factor``
parameter controls data volume without changing distribution characteristics.
"""

from __future__ import annotations

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import Edge, Payload, PostingEntry, Vertex


class BenchmarkDataGenerator:
    """Deterministic data generator with configurable scale factors.

    Parameters
    ----------
    scale_factor:
        Multiplier for base data sizes. SF1 = 1000 documents.
    seed:
        Random seed for reproducibility.
    """

    def __init__(self, scale_factor: int = 10, seed: int = 42) -> None:
        self.sf = scale_factor
        self.rng = np.random.default_rng(seed)

    @property
    def num_documents(self) -> int:
        return self.sf * 1000

    @property
    def num_vectors(self) -> int:
        return self.sf * 1000

    @property
    def num_vertices(self) -> int:
        return self.sf * 500

    @property
    def num_edges(self) -> int:
        return self.sf * 2000

    # -- Posting Lists -----------------------------------------------------

    def posting_list(
        self, size: int, score_range: tuple[float, float] = (0.0, 1.0)
    ) -> PostingList:
        """Generate a PostingList with *size* entries and random scores."""
        doc_ids = sorted(self.rng.choice(size * 10, size=size, replace=False))
        entries = [
            PostingEntry(
                doc_id=int(did),
                payload=Payload(
                    positions=(0,),
                    score=float(self.rng.uniform(*score_range)),
                ),
            )
            for did in doc_ids
        ]
        pl = PostingList.__new__(PostingList)
        pl._entries = entries
        pl._doc_ids_cache = None
        return pl

    def posting_lists(
        self, size: int, overlap: float = 0.3
    ) -> tuple[PostingList, PostingList]:
        """Generate two PostingLists with controlled overlap ratio.

        Parameters
        ----------
        size:
            Number of entries in each list.
        overlap:
            Fraction of doc_ids shared between the two lists (0.0 to 1.0).
        """
        shared_count = int(size * overlap)
        unique_count = size - shared_count
        total_pool = size * 10

        all_ids = self.rng.choice(
            total_pool, size=shared_count + unique_count * 2, replace=False
        )
        shared_ids = all_ids[:shared_count]
        unique_a = all_ids[shared_count : shared_count + unique_count]
        unique_b = all_ids[shared_count + unique_count :]

        def make_pl(ids: np.ndarray) -> PostingList:
            sorted_ids = sorted(int(x) for x in ids)
            entries = [
                PostingEntry(
                    doc_id=did,
                    payload=Payload(positions=(0,), score=float(self.rng.random())),
                )
                for did in sorted_ids
            ]
            pl = PostingList.__new__(PostingList)
            pl._entries = entries
            pl._doc_ids_cache = None
            return pl

        ids_a = np.concatenate([shared_ids, unique_a])
        ids_b = np.concatenate([shared_ids, unique_b])
        return make_pl(ids_a), make_pl(ids_b)

    def posting_lists_multi(
        self, n: int, size: int, overlap: float = 0.3
    ) -> list[PostingList]:
        """Generate N PostingLists with pairwise overlap."""
        total_pool = size * 10 * n
        shared_count = int(size * overlap)
        shared_ids = self.rng.choice(total_pool, size=shared_count, replace=False)

        result: list[PostingList] = []
        for _ in range(n):
            unique_ids = self.rng.choice(
                total_pool, size=size - shared_count, replace=False
            )
            all_ids = np.concatenate([shared_ids, unique_ids])
            sorted_ids = sorted({int(x) for x in all_ids})[:size]
            entries = [
                PostingEntry(
                    doc_id=did,
                    payload=Payload(positions=(0,), score=float(self.rng.random())),
                )
                for did in sorted_ids
            ]
            pl = PostingList.__new__(PostingList)
            pl._entries = entries
            pl._doc_ids_cache = None
            result.append(pl)
        return result

    # -- Documents ---------------------------------------------------------

    def _zipf_terms(self, vocab_size: int, num_terms: int) -> list[str]:
        """Generate terms following a Zipf distribution."""
        vocab = [f"term_{i:06d}" for i in range(vocab_size)]
        indices = self.rng.zipf(1.5, size=num_terms) - 1
        indices = np.clip(indices, 0, vocab_size - 1)
        return [vocab[int(i)] for i in indices]

    def documents(self, terms_per_doc: int = 50) -> list[dict]:
        """Generate documents with Zipf-distributed terms."""
        vocab_size = max(1000, self.num_documents // 10)
        docs: list[dict] = []
        for i in range(self.num_documents):
            length = max(
                10, int(self.rng.lognormal(mean=np.log(terms_per_doc), sigma=0.5))
            )
            terms = self._zipf_terms(vocab_size, length)
            docs.append(
                {
                    "id": i + 1,
                    "title": f"Document {i + 1}",
                    "body": " ".join(terms),
                    "category": f"cat_{int(self.rng.integers(0, 10))}",
                    "price": round(float(self.rng.uniform(1.0, 1000.0)), 2),
                    "rating": round(float(self.rng.uniform(1.0, 5.0)), 1),
                }
            )
        return docs

    # -- Vectors -----------------------------------------------------------

    def vectors(self, dim: int = 128) -> np.ndarray:
        """Generate unit-normalized random vectors."""
        vecs = self.rng.standard_normal((self.num_vectors, dim)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def query_vector(self, dim: int = 128) -> np.ndarray:
        """Generate a single unit-normalized query vector."""
        vec = self.rng.standard_normal(dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # -- Graph -------------------------------------------------------------

    def graph(self) -> tuple[list[Vertex], list[Edge]]:
        """Generate a power-law graph.

        Vertex labels are drawn from a small set. Edge labels follow
        a Zipf distribution over a set of relation types.
        """
        vertex_labels = ["Person", "Organization", "Location", "Product", "Event"]
        edge_labels = ["knows", "works_at", "located_in", "created", "attended"]

        vertices: list[Vertex] = []
        for i in range(1, self.num_vertices + 1):
            label = vertex_labels[int(self.rng.integers(0, len(vertex_labels)))]
            vertices.append(
                Vertex(
                    vertex_id=i,
                    label=label,
                    properties={"name": f"{label}_{i}"},
                )
            )

        # Power-law degree distribution via preferential attachment
        edges: list[Edge] = []
        degree = np.ones(self.num_vertices + 1, dtype=np.float64)
        for eid in range(1, self.num_edges + 1):
            # Source: uniform random
            src = int(self.rng.integers(1, self.num_vertices + 1))
            # Target: preferential attachment (proportional to degree)
            probs = degree[1:] / degree[1:].sum()
            tgt = int(self.rng.choice(self.num_vertices, p=probs)) + 1
            if tgt == src:
                tgt = (tgt % self.num_vertices) + 1
            label = edge_labels[int(self.rng.integers(0, len(edge_labels)))]
            edges.append(
                Edge(
                    edge_id=eid,
                    source_id=src,
                    target_id=tgt,
                    label=label,
                    properties={"weight": round(float(self.rng.random()), 3)},
                )
            )
            degree[src] += 1
            degree[tgt] += 1

        return vertices, edges

    # -- Table rows --------------------------------------------------------

    def table_rows(
        self,
        num_rows: int | None = None,
        num_categories: int = 100,
    ) -> list[dict]:
        """Generate rows for a generic benchmark table.

        Schema: id (int), name (text), value (float), category (text),
                 quantity (int), active (bool).
        """
        n = num_rows or self.num_documents
        categories = [f"cat_{i}" for i in range(num_categories)]
        rows: list[dict] = []
        for i in range(1, n + 1):
            rows.append(
                {
                    "id": i,
                    "name": f"item_{i}",
                    "value": round(float(self.rng.uniform(0.01, 10000.0)), 2),
                    "category": categories[int(self.rng.integers(0, num_categories))],
                    "quantity": int(self.rng.integers(0, 1000)),
                    "active": bool(self.rng.random() > 0.2),
                }
            )
        return rows

    def join_tables(
        self, num_orders: int | None = None, num_customers: int | None = None
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Generate customers, products, and orders tables for join benchmarks.

        Returns (customers, products, orders).
        """
        n_customers = num_customers or max(100, self.num_documents // 10)
        n_products = max(50, self.num_documents // 20)
        n_orders = num_orders or self.num_documents

        customers = [
            {
                "id": i,
                "name": f"customer_{i}",
                "region": f"region_{int(self.rng.integers(0, 10))}",
            }
            for i in range(1, n_customers + 1)
        ]
        products = [
            {
                "id": i,
                "name": f"product_{i}",
                "price": round(float(self.rng.uniform(1.0, 500.0)), 2),
                "category": f"pcat_{int(self.rng.integers(0, 20))}",
            }
            for i in range(1, n_products + 1)
        ]
        orders = [
            {
                "id": i,
                "customer_id": int(self.rng.integers(1, n_customers + 1)),
                "product_id": int(self.rng.integers(1, n_products + 1)),
                "amount": round(float(self.rng.uniform(1.0, 1000.0)), 2),
                "status": ["pending", "shipped", "delivered"][
                    int(self.rng.integers(0, 3))
                ],
            }
            for i in range(1, n_orders + 1)
        ]
        return customers, products, orders

    # -- Terms for inverted index ------------------------------------------

    def term_documents(
        self, num_docs: int | None = None, terms_per_doc: int = 50
    ) -> list[tuple[int, dict[str, str]]]:
        """Generate (doc_id, {field: text}) pairs for inverted index benchmarks."""
        n = num_docs or self.num_documents
        vocab_size = max(500, n // 5)
        result: list[tuple[int, dict[str, str]]] = []
        for i in range(1, n + 1):
            terms = self._zipf_terms(vocab_size, terms_per_doc)
            result.append((i, {"body": " ".join(terms)}))
        return result
