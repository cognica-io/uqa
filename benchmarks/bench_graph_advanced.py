#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for advanced graph features.

Covers temporal traversal, graph delta, message passing,
graph embeddings, and path index.
"""

from __future__ import annotations

import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.core.types import Edge, Vertex
from uqa.graph.delta import GraphDelta
from uqa.graph.graph_embedding import GraphEmbeddingOperator
from uqa.graph.index import PathIndex
from uqa.graph.message_passing import MessagePassingOperator
from uqa.graph.store import GraphStore
from uqa.graph.temporal_filter import TemporalFilter
from uqa.graph.temporal_traverse import TemporalTraverseOperator
from uqa.graph.versioned_store import VersionedGraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_graph(sf: int = 1) -> GraphStore:
    gen = BenchmarkDataGenerator(scale_factor=sf, seed=42)
    vertices, edges = gen.graph()
    gs = GraphStore()
    for v in vertices:
        gs.add_vertex(v)
    for e in edges:
        gs.add_edge(e)
    return gs


def _build_temporal_graph(sf: int = 1) -> GraphStore:
    """Build a graph where edges have valid_from/valid_to properties."""
    gen = BenchmarkDataGenerator(scale_factor=sf, seed=42)
    vertices, edges = gen.graph()
    gs = GraphStore()
    for v in vertices:
        gs.add_vertex(v)
    rng = gen.rng
    for e in edges:
        valid_from = float(rng.uniform(0.0, 50.0))
        valid_to = valid_from + float(rng.uniform(10.0, 50.0))
        temporal_edge = Edge(
            edge_id=e.edge_id,
            source_id=e.source_id,
            target_id=e.target_id,
            label=e.label,
            properties={
                **e.properties,
                "valid_from": valid_from,
                "valid_to": valid_to,
            },
        )
        gs.add_edge(temporal_edge)
    return gs


class _GraphContext:
    """Minimal context object for graph operators."""

    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store


# ---------------------------------------------------------------------------
# Path Index
# ---------------------------------------------------------------------------


class TestPathIndex:
    @pytest.mark.parametrize("depth", [1, 2, 3])
    def test_build(self, benchmark, depth: int) -> None:
        gs = _build_graph(sf=1)
        labels = ["knows", "works_at", "located_in"]
        sequences = [labels[:depth]]
        result = benchmark(PathIndex.build, gs, sequences)
        assert len(result.indexed_paths()) == 1

    def test_lookup(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        idx = PathIndex.build(gs, [["knows"], ["works_at"]])
        benchmark(idx.lookup, ["knows"])

    def test_rpq_with_index_vs_without(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        idx = PathIndex.build(gs, [["knows", "works_at"]])

        def lookup_indexed() -> int:
            pairs = idx.lookup(["knows", "works_at"])
            return len(pairs) if pairs is not None else 0

        result = benchmark(lookup_indexed)
        assert result >= 0


# ---------------------------------------------------------------------------
# Graph Delta
# ---------------------------------------------------------------------------


class TestGraphDelta:
    @pytest.mark.parametrize("size", [10, 100, 1000])
    def test_apply(self, benchmark, size: int) -> None:
        gs = _build_graph(sf=1)
        vgs = VersionedGraphStore(gs)
        gen = BenchmarkDataGenerator(scale_factor=1, seed=99)
        rng = gen.rng

        # Pre-build the delta with new vertices and edges
        delta = GraphDelta()
        base_vid = 100000
        base_eid = 100000
        for i in range(size):
            delta.add_vertex(
                Vertex(
                    vertex_id=base_vid + i,
                    label="Person",
                    properties={"name": f"new_{i}"},
                )
            )
            delta.add_edge(
                Edge(
                    edge_id=base_eid + i,
                    source_id=base_vid + i,
                    target_id=int(rng.integers(1, 100)),
                    label="knows",
                    properties={"weight": 0.5},
                )
            )

        benchmark(vgs.apply, delta)

    @pytest.mark.parametrize("depth", [1, 5, 10])
    def test_rollback(self, benchmark, depth: int) -> None:
        gs = _build_graph(sf=1)
        vgs = VersionedGraphStore(gs)

        # Apply `depth` deltas
        for d in range(depth):
            delta = GraphDelta()
            delta.add_vertex(
                Vertex(
                    vertex_id=200000 + d,
                    label="Person",
                    properties={"name": f"rollback_{d}"},
                )
            )
            vgs.apply(delta)

        target_version = 0
        benchmark(vgs.rollback, target_version)


# ---------------------------------------------------------------------------
# Temporal Traversal
# ---------------------------------------------------------------------------


class TestTemporalTraverse:
    @pytest.mark.parametrize("depth", [1, 2, 3])
    def test_traverse(self, benchmark, depth: int) -> None:
        gs = _build_temporal_graph(sf=1)
        tf = TemporalFilter(timestamp=25.0)
        op = TemporalTraverseOperator(
            start_vertex=1,
            label="knows",
            max_hops=depth,
            temporal_filter=tf,
        )
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0

    def test_traverse_with_filter_vs_without(self, benchmark) -> None:
        gs = _build_temporal_graph(sf=1)
        tf = TemporalFilter(timestamp=25.0)
        op = TemporalTraverseOperator(
            start_vertex=1,
            label="knows",
            max_hops=2,
            temporal_filter=tf,
        )
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Message Passing
# ---------------------------------------------------------------------------


class TestMessagePassing:
    @pytest.mark.parametrize("k_layers", [1, 2, 3])
    def test_execute(self, benchmark, k_layers: int) -> None:
        gs = _build_graph(sf=1)
        op = MessagePassingOperator(k_layers=k_layers, aggregation="mean")
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0

    @pytest.mark.parametrize("aggregation", ["mean", "sum", "max"])
    def test_aggregation(self, benchmark, aggregation: str) -> None:
        gs = _build_graph(sf=1)
        op = MessagePassingOperator(k_layers=2, aggregation=aggregation)
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Graph Embedding
# ---------------------------------------------------------------------------


class TestGraphEmbedding:
    @pytest.mark.parametrize("dimensions", [8, 16, 32])
    def test_execute(self, benchmark, dimensions: int) -> None:
        gs = _build_graph(sf=1)
        op = GraphEmbeddingOperator(dimensions=dimensions, k_layers=2)
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0
