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

from typing import Any

import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.core.types import Edge, Vertex
from uqa.graph.delta import GraphDelta
from uqa.graph.graph_embedding import GraphEmbeddingOperator
from uqa.graph.index import PathIndex
from uqa.graph.message_passing import MessagePassingOperator
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.graph.temporal_filter import TemporalFilter
from uqa.graph.temporal_traverse import TemporalTraverseOperator
from uqa.graph.versioned_store import VersionedGraphStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


GRAPH_NAME = "bench"


def _build_graph(sf: int = 1) -> GraphStore:
    gen = BenchmarkDataGenerator(scale_factor=sf, seed=42)
    vertices, edges = gen.graph()
    gs = GraphStore()
    gs.create_graph(GRAPH_NAME)
    for v in vertices:
        gs.add_vertex(v, graph=GRAPH_NAME)
    for e in edges:
        gs.add_edge(e, graph=GRAPH_NAME)
    return gs


def _build_temporal_graph(sf: int = 1) -> GraphStore:
    """Build a graph where edges have valid_from/valid_to properties."""
    gen = BenchmarkDataGenerator(scale_factor=sf, seed=42)
    vertices, edges = gen.graph()
    gs = GraphStore()
    gs.create_graph(GRAPH_NAME)
    for v in vertices:
        gs.add_vertex(v, graph=GRAPH_NAME)
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
        gs.add_edge(temporal_edge, graph=GRAPH_NAME)
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
        result = benchmark(PathIndex.build, gs, sequences, graph_name=GRAPH_NAME)
        assert len(result.indexed_paths()) == 1

    def test_lookup(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        idx = PathIndex.build(gs, [["knows"], ["works_at"]], graph_name=GRAPH_NAME)
        benchmark(idx.lookup, ["knows"])

    def test_rpq_with_index_vs_without(self, benchmark) -> None:
        gs = _build_graph(sf=1)
        idx = PathIndex.build(gs, [["knows", "works_at"]], graph_name=GRAPH_NAME)

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
        vgs = VersionedGraphStore(gs, graph_name=GRAPH_NAME)
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
        vgs = VersionedGraphStore(gs, graph_name=GRAPH_NAME)

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
            graph=GRAPH_NAME,
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
            graph=GRAPH_NAME,
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
        op = MessagePassingOperator(
            k_layers=k_layers, aggregation="mean", graph=GRAPH_NAME
        )
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0

    @pytest.mark.parametrize("aggregation", ["mean", "sum", "max"])
    def test_aggregation(self, benchmark, aggregation: str) -> None:
        gs = _build_graph(sf=1)
        op = MessagePassingOperator(
            k_layers=2, aggregation=aggregation, graph=GRAPH_NAME
        )
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
        op = GraphEmbeddingOperator(dimensions=dimensions, k_layers=2, graph=GRAPH_NAME)
        ctx = _GraphContext(gs)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Named Graph Operations
# ---------------------------------------------------------------------------


def _engine_with_named_graph(name: str = "bench_ng") -> Any:
    """Create an Engine with a named graph via SQL create_graph()."""
    from uqa.engine import Engine

    e = Engine()
    e.sql(f"SELECT * FROM create_graph('{name}')")
    gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
    vertices, edges = gen.graph()
    graph = e.get_graph(name)
    for v in vertices:
        graph.add_vertex(v, graph=name)
    for edge in edges:
        graph.add_edge(edge, graph=name)
    return e


class TestNamedGraphTraverse:
    def test_traverse_named_graph(self, benchmark) -> None:
        e = _engine_with_named_graph("bench_ng")

        def run() -> object:
            return e.sql("SELECT * FROM traverse(1, 'knows', 2, 'graph:bench_ng')")

        result = benchmark(run)
        assert result is not None

    def test_temporal_traverse_named_graph(self, benchmark) -> None:
        e = _engine_with_named_graph("bench_tng")

        def run() -> object:
            return e.sql(
                "SELECT * FROM temporal_traverse(1, 'knows', 2, 0.5, 'graph:bench_tng')"
            )

        result = benchmark(run)
        assert result is not None

    def test_rpq_named_graph(self, benchmark) -> None:
        e = _engine_with_named_graph("bench_rpq")

        def run() -> object:
            return e.sql("SELECT * FROM rpq('knows/works_at', 1, 'graph:bench_rpq')")

        result = benchmark(run)
        assert result is not None
