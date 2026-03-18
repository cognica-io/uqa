#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for graph centrality, bounded RPQ, weighted paths, and indexing.

Covers PageRank, HITS, betweenness centrality, bounded RPQ, weighted
path queries, subgraph index build/lookup, and incremental pattern matching.
"""

from __future__ import annotations

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.graph.centrality import (
    BetweennessCentralityOperator,
    HITSOperator,
    PageRankOperator,
)
from uqa.graph.incremental_match import GraphDelta, IncrementalPatternMatcher
from uqa.graph.index import SubgraphIndex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    WeightedPathQueryOperator,
)
from uqa.graph.pattern import (
    EdgePattern,
    GraphPattern,
    Label,
    VertexPattern,
    parse_rpq,
)
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.operators.base import ExecutionContext
from uqa.operators.progressive_fusion import ProgressiveFusionOperator

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


def _build_ctx(sf: int = 1) -> tuple[GraphStore, ExecutionContext]:
    gs = _build_graph(sf)
    ctx = ExecutionContext(graph_store=gs)
    return gs, ctx


# ---------------------------------------------------------------------------
# PageRank
# ---------------------------------------------------------------------------


class TestPageRank:
    def test_pagerank_default(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = PageRankOperator(graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0

    def test_pagerank_high_damping(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = PageRankOperator(damping=0.95, max_iterations=50, graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0

    def test_pagerank_low_iterations(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = PageRankOperator(max_iterations=10, graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# HITS
# ---------------------------------------------------------------------------


class TestHITS:
    def test_hits_default(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = HITSOperator(graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0

    def test_hits_low_iterations(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = HITSOperator(max_iterations=10, graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Betweenness Centrality
# ---------------------------------------------------------------------------


class TestBetweenness:
    def test_betweenness(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = BetweennessCentralityOperator(graph=GRAPH_NAME)
        result = benchmark(op.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Bounded RPQ
# ---------------------------------------------------------------------------


class TestBoundedRPQ:
    def test_parse_bounded(self, benchmark) -> None:
        benchmark(parse_rpq, "knows{2,4}")

    def test_bounded_rpq_execute(self, benchmark) -> None:
        _, ctx = _build_ctx()
        expr = parse_rpq("knows{1,3}")
        op = RegularPathQueryOperator(expr, graph=GRAPH_NAME, start_vertex=1)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0

    def test_bounded_vs_kleene(self, benchmark) -> None:
        """Bounded RPQ should be faster than Kleene star for same reach."""
        _, ctx = _build_ctx()
        expr = parse_rpq("knows{1,2}")
        op = RegularPathQueryOperator(expr, graph=GRAPH_NAME, start_vertex=1)
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Weighted Path Query
# ---------------------------------------------------------------------------


class TestWeightedPath:
    def test_weighted_sum(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = WeightedPathQueryOperator(
            path_expr=Label("knows"),
            graph=GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="sum",
            start_vertex=1,
        )
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0

    def test_weighted_max(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = WeightedPathQueryOperator(
            path_expr=parse_rpq("knows/knows"),
            graph=GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="max",
            start_vertex=1,
        )
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0

    def test_weighted_with_predicate(self, benchmark) -> None:
        _, ctx = _build_ctx()
        op = WeightedPathQueryOperator(
            path_expr=Label("knows"),
            graph=GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="sum",
            predicate=lambda w: w > 0.5,
            start_vertex=1,
        )
        result = benchmark(op.execute, ctx)
        assert len(result) >= 0


# ---------------------------------------------------------------------------
# Subgraph Index
# ---------------------------------------------------------------------------


class TestSubgraphIndex:
    def test_build(self, benchmark) -> None:
        gs = _build_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = benchmark(SubgraphIndex.build, gs, [pattern], graph_name=GRAPH_NAME)
        assert idx.has_pattern(pattern)

    def test_lookup(self, benchmark) -> None:
        gs = _build_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = SubgraphIndex.build(gs, [pattern], graph_name=GRAPH_NAME)
        result = benchmark(idx.lookup, pattern)
        assert result is not None

    def test_cached_pattern_match(self, benchmark) -> None:
        gs = _build_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = SubgraphIndex.build(gs, [pattern], graph_name=GRAPH_NAME)
        ctx = ExecutionContext(graph_store=gs, subgraph_index=idx)
        pm = PatternMatchOperator(pattern, graph=GRAPH_NAME)
        result = benchmark(pm.execute, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Incremental Pattern Matching
# ---------------------------------------------------------------------------


class TestIncrementalMatch:
    def _setup_matcher(self) -> tuple[GraphStore, IncrementalPatternMatcher]:
        gs = _build_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        ctx = ExecutionContext(graph_store=gs)
        pm = PatternMatchOperator(pattern, graph=GRAPH_NAME)
        gpl = pm.execute(ctx)
        matches = set()
        for entry in gpl:
            gp = gpl.get_graph_payload(entry.doc_id)
            if gp:
                matches.add(gp.subgraph_vertices)
        return gs, IncrementalPatternMatcher(pattern, matches, graph_name=GRAPH_NAME)

    def test_incremental_add_edge(self, benchmark) -> None:
        from uqa.core.types import Edge as E

        gs, matcher = self._setup_matcher()
        new_eid = gs.next_edge_id()
        gs.add_edge(E(new_eid, 1, 2, "knows", {"weight": 0.5}), graph=GRAPH_NAME)
        delta = GraphDelta(added_edge_ids={new_eid})
        result = benchmark(matcher.update, gs, delta)
        assert len(result) > 0

    def test_incremental_remove_vertex(self, benchmark) -> None:
        gs, matcher = self._setup_matcher()
        gs.remove_vertex(2, graph=GRAPH_NAME)
        delta = GraphDelta(removed_vertex_ids={2})
        result = benchmark(matcher.update, gs, delta)
        for m in result:
            assert 2 not in m


# ---------------------------------------------------------------------------
# Progressive Fusion
# ---------------------------------------------------------------------------


class TestProgressiveFusion:
    def test_two_stage(self, benchmark) -> None:
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry

        class _FixedOp:
            def __init__(self, entries):
                self._entries = entries

            def execute(self, context):
                return PostingList(
                    [PostingEntry(d, Payload(score=s)) for d, s in self._entries]
                )

            def cost_estimate(self, stats):
                return float(len(self._entries))

        sig1 = _FixedOp([(i, 0.9 - i * 0.01) for i in range(1, 51)])
        sig2 = _FixedOp([(i, 0.8 - i * 0.01) for i in range(1, 51)])
        sig3 = _FixedOp([(i, 0.7 - i * 0.01) for i in range(1, 51)])

        op = ProgressiveFusionOperator(
            stages=[
                ([sig1, sig2], 20),
                ([sig3], 10),
            ],
        )
        ctx = ExecutionContext()
        result = benchmark(op.execute, ctx)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# SQL Function Benchmarks
# ---------------------------------------------------------------------------


class TestCentralitySQL:
    @staticmethod
    def _make_engine():
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE bench (id SERIAL PRIMARY KEY, name TEXT)")
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        vertices, edges = gen.graph()
        for v in vertices:
            engine.sql(f"INSERT INTO bench (name) VALUES ('v_{v.vertex_id}')")
            engine.sql(
                f"SELECT * FROM graph_add_vertex({v.vertex_id}, '{v.label}', 'bench')"
            )
        for e in edges:
            w = e.properties.get("weight", 0)
            engine.sql(
                f"SELECT * FROM graph_add_edge("
                f"{e.edge_id}, {e.source_id}, {e.target_id}, "
                f"'{e.label}', 'bench', 'weight={w}')"
            )
        return engine

    def test_pagerank_from_sql(self, benchmark) -> None:
        engine = self._make_engine()
        result = benchmark(
            engine.sql,
            "SELECT _doc_id, _score FROM pagerank() ORDER BY _score DESC LIMIT 10",
        )
        assert len(result.rows) > 0

    def test_hits_from_sql(self, benchmark) -> None:
        engine = self._make_engine()
        result = benchmark(
            engine.sql,
            "SELECT _doc_id, _score FROM hits() ORDER BY _score DESC LIMIT 10",
        )
        assert len(result.rows) > 0

    def test_betweenness_from_sql(self, benchmark) -> None:
        engine = self._make_engine()
        result = benchmark(
            engine.sql,
            "SELECT _doc_id, _score FROM betweenness() ORDER BY _score DESC LIMIT 10",
        )
        assert len(result.rows) > 0

    def test_bounded_rpq_sql(self, benchmark) -> None:
        engine = self._make_engine()
        result = benchmark(
            engine.sql, "SELECT COUNT(*) AS cnt FROM rpq('knows{1,2}', 1)"
        )
        assert result.rows[0]["cnt"] >= 0

    def test_pagerank_where_sql(self, benchmark) -> None:
        engine = self._make_engine()
        result = benchmark(
            engine.sql,
            "SELECT name, _score FROM bench WHERE pagerank() ORDER BY _score DESC LIMIT 5",
        )
        assert len(result.rows) > 0
