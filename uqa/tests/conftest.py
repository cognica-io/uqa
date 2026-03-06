#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.types import DocId, Edge, Payload, PostingEntry, Vertex
from uqa.core.posting_list import PostingList
from uqa.core.hierarchical import HierarchicalDocument


@pytest.fixture
def sample_entries() -> list[PostingEntry]:
    return [
        PostingEntry(1, Payload(positions=(0, 5), score=1.0)),
        PostingEntry(3, Payload(positions=(2,), score=0.8)),
        PostingEntry(5, Payload(positions=(1,), score=0.6)),
        PostingEntry(7, Payload(positions=(3,), score=0.4)),
        PostingEntry(9, Payload(positions=(0,), score=0.2)),
    ]


@pytest.fixture
def sample_posting_list(sample_entries: list[PostingEntry]) -> PostingList:
    return PostingList(sample_entries)


@pytest.fixture
def other_entries() -> list[PostingEntry]:
    return [
        PostingEntry(2, Payload(positions=(1,), score=0.9)),
        PostingEntry(3, Payload(positions=(4,), score=0.7)),
        PostingEntry(5, Payload(positions=(6,), score=0.5)),
        PostingEntry(8, Payload(positions=(2,), score=0.3)),
    ]


@pytest.fixture
def other_posting_list(other_entries: list[PostingEntry]) -> PostingList:
    return PostingList(other_entries)


@pytest.fixture
def universal_posting_list() -> PostingList:
    return PostingList([
        PostingEntry(i, Payload(score=0.0))
        for i in range(1, 11)
    ])


@pytest.fixture
def sample_documents() -> list[dict]:
    return [
        {
            "doc_id": 1,
            "title": "introduction to neural networks",
            "abstract": "neural networks are computational models",
            "year": 2023,
            "category": "machine learning",
        },
        {
            "doc_id": 2,
            "title": "deep learning transformers",
            "abstract": "transformers use attention mechanisms",
            "year": 2024,
            "category": "deep learning",
        },
        {
            "doc_id": 3,
            "title": "graph neural networks",
            "abstract": "graph neural networks extend neural networks to graph data",
            "year": 2024,
            "category": "machine learning",
        },
        {
            "doc_id": 4,
            "title": "bayesian optimization methods",
            "abstract": "bayesian methods for hyperparameter optimization",
            "year": 2025,
            "category": "optimization",
        },
        {
            "doc_id": 5,
            "title": "reinforcement learning agents",
            "abstract": "reinforcement learning for decision making",
            "year": 2025,
            "category": "reinforcement learning",
        },
    ]


@pytest.fixture
def sample_vectors() -> dict[int, np.ndarray]:
    rng = np.random.RandomState(42)
    return {i: rng.randn(64).astype(np.float32) for i in range(1, 6)}


@pytest.fixture
def sample_graph_vertices() -> list[Vertex]:
    return [
        Vertex(1, {"name": "Alice", "age": 30}),
        Vertex(2, {"name": "Bob", "age": 25}),
        Vertex(3, {"name": "Charlie", "age": 35}),
        Vertex(4, {"name": "Diana", "age": 28}),
        Vertex(5, {"name": "Eve", "age": 32}),
    ]


@pytest.fixture
def sample_graph_edges() -> list[Edge]:
    return [
        Edge(1, 1, 2, "knows", {"since": 2020}),
        Edge(2, 1, 3, "knows", {"since": 2019}),
        Edge(3, 2, 3, "knows", {"since": 2021}),
        Edge(4, 2, 4, "works_with", {"project": "alpha"}),
        Edge(5, 3, 4, "knows", {"since": 2022}),
        Edge(6, 3, 5, "works_with", {"project": "beta"}),
        Edge(7, 4, 5, "knows", {"since": 2023}),
    ]


@pytest.fixture
def hierarchical_doc() -> HierarchicalDocument:
    return HierarchicalDocument(1, {
        "title": "test document",
        "metadata": {
            "author": "Alice",
            "tags": ["python", "search", "algebra"],
        },
        "sections": [
            {"heading": "Introduction", "content": "This is the intro"},
            {"heading": "Methods", "content": "We use posting lists"},
        ],
    })
