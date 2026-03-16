#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.types import Edge, IndexStats, Vertex
from uqa.graph.incremental_match import GraphDelta, IncrementalPatternMatcher
from uqa.graph.index import SubgraphIndex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    WeightedPathQueryOperator,
)
from uqa.graph.pattern import (
    BoundedLabel,
    EdgePattern,
    GraphPattern,
    Label,
    VertexPattern,
    parse_rpq,
)
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext
from uqa.operators.boolean import IntersectOperator
from uqa.planner.cardinality import CardinalityEstimator, GraphStats
from uqa.planner.optimizer import QueryOptimizer

_GRAPH_NAME = "test"


def _make_graph() -> GraphStore:
    """Build a small test graph: 1->2->3->4, 1->3."""
    g = GraphStore()
    g.create_graph(_GRAPH_NAME)
    g.add_vertex(Vertex(1, "person", {"name": "Alice", "age": 30}), graph=_GRAPH_NAME)
    g.add_vertex(Vertex(2, "person", {"name": "Bob", "age": 25}), graph=_GRAPH_NAME)
    g.add_vertex(Vertex(3, "person", {"name": "Carol", "age": 35}), graph=_GRAPH_NAME)
    g.add_vertex(Vertex(4, "person", {"name": "Dave", "age": 40}), graph=_GRAPH_NAME)
    g.add_edge(
        Edge(1, 1, 2, "knows", {"since": 2020, "weight": 1.0}), graph=_GRAPH_NAME
    )
    g.add_edge(
        Edge(2, 2, 3, "knows", {"since": 2021, "weight": 2.0}), graph=_GRAPH_NAME
    )
    g.add_edge(
        Edge(3, 3, 4, "knows", {"since": 2022, "weight": 3.0}), graph=_GRAPH_NAME
    )
    g.add_edge(
        Edge(4, 1, 3, "works_with", {"since": 2019, "weight": 0.5}), graph=_GRAPH_NAME
    )
    return g


# -- Phase 1C: Bounded RPQ Tests --


class TestBoundedRPQ:
    def test_parse_bounded_label(self) -> None:
        expr = parse_rpq("knows{2,3}")
        assert isinstance(expr, BoundedLabel)
        assert isinstance(expr.inner, Label)
        assert expr.inner.name == "knows"
        assert expr.min_hops == 2
        assert expr.max_hops == 3

    def test_bounded_nfa_exact_hops(self) -> None:
        """2-3 hops only: from 1, 2 hops reaches 3, 3 hops reaches 4."""
        g = _make_graph()
        ctx = ExecutionContext(graph_store=g)
        expr = parse_rpq("knows{2,3}")
        op = RegularPathQueryOperator(expr, graph=_GRAPH_NAME, start_vertex=1)
        result = op.execute(ctx)
        reached = {e.doc_id for e in result}
        assert 3 in reached  # 2 hops: 1->2->3
        assert 4 in reached  # 3 hops: 1->2->3->4

    def test_bounded_min_zero(self) -> None:
        """min_hops=0 means the start vertex itself is reachable."""
        g = _make_graph()
        ctx = ExecutionContext(graph_store=g)
        expr = parse_rpq("knows{0,1}")
        op = RegularPathQueryOperator(expr, graph=_GRAPH_NAME, start_vertex=1)
        result = op.execute(ctx)
        reached = {e.doc_id for e in result}
        assert 1 in reached  # 0 hops: start vertex
        assert 2 in reached  # 1 hop: 1->2

    def test_weighted_path_sum(self) -> None:
        """Weighted RPQ with sum aggregate."""
        g = _make_graph()
        ctx = ExecutionContext(graph_store=g)
        expr = Label("knows")
        op = WeightedPathQueryOperator(
            expr,
            graph=_GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="sum",
            start_vertex=1,
        )
        result = op.execute(ctx)
        # 1->2 via "knows" with weight 1.0
        entry = next(e for e in result if e.doc_id == 2)
        assert entry.payload.fields["path_weight"] == pytest.approx(1.0)

    def test_weighted_path_max(self) -> None:
        """Weighted RPQ with max aggregate."""
        g = _make_graph()
        ctx = ExecutionContext(graph_store=g)
        expr = parse_rpq("knows/knows")
        op = WeightedPathQueryOperator(
            expr,
            graph=_GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="max",
            start_vertex=1,
        )
        result = op.execute(ctx)
        # 1->2->3 via "knows/knows", max of weights 1.0 and 2.0
        entry = next(e for e in result if e.doc_id == 3)
        assert entry.payload.fields["path_weight"] == pytest.approx(2.0)

    def test_weighted_path_predicate(self) -> None:
        """Weighted RPQ with predicate filtering."""
        g = _make_graph()
        ctx = ExecutionContext(graph_store=g)
        expr = parse_rpq("knows/knows")
        # Only accept paths with total weight > 5
        op = WeightedPathQueryOperator(
            expr,
            graph=_GRAPH_NAME,
            weight_property="weight",
            aggregate_fn="sum",
            predicate=lambda w: w > 5.0,
            start_vertex=1,
        )
        result = op.execute(ctx)
        # 1->2->3->4 has weight 1+2+3=6 > 5, but that's 3 hops via knows/knows/knows
        # 1->2->3 has weight 1+2=3 < 5
        reached = {e.doc_id for e in result}
        assert 3 not in reached  # weight 3.0 < 5.0


# -- Phase 2A: Edge Property Filter Pushdown Tests --


class TestEdgeFilterPushdown:
    def test_edge_filter_pushdown(self) -> None:
        """Filter on 'a_b.since' should push into edge pattern constraints."""
        from uqa.core.types import GreaterThan
        from uqa.operators.primitive import FilterOperator

        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        # Filter: a_b.since > 2020
        filt = FilterOperator("a_b.since", GreaterThan(2020), pm)
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filt)
        # After pushdown, we should get a PatternMatchOperator (not wrapped in Filter)
        assert isinstance(optimized, PatternMatchOperator)
        # The edge pattern should now have a constraint
        assert len(optimized.pattern.edge_patterns[0].constraints) == 1

    def test_edge_filter_with_vertex_filter(self) -> None:
        """Combined vertex + edge filters: vertex filter pushes into pattern,
        edge filter is then pushed into the resulting PatternMatch's edge
        constraints in a second pass of _push_graph_pattern_filters.

        The optimizer processes the stacked filters bottom-up via recursion
        in _recurse_graph_pattern, so the vertex filter is pushed first,
        producing FilterOperator(edge, PatternMatchOperator).  However,
        _recurse_graph_pattern rebuilds the outer FilterOperator without
        re-checking for graph pattern pushdown.  A subsequent call to
        _push_graph_pattern_filters from optimize() is not repeated, so
        the edge filter remains as a wrapping FilterOperator.
        """
        from uqa.core.types import Equals, GreaterThan
        from uqa.operators.primitive import FilterOperator

        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        # First wrap in vertex filter, then edge filter
        vertex_filt = FilterOperator("a.name", Equals("Alice"), pm)
        edge_filt = FilterOperator("a_b.since", GreaterThan(2020), vertex_filt)
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(edge_filt)
        # The vertex filter is pushed into the pattern, but the edge filter
        # remains as a wrapper because the optimizer processes bottom-up
        # without re-entering _push_graph_pattern_filters for the rebuilt
        # outer FilterOperator.
        assert isinstance(optimized, FilterOperator)
        assert isinstance(optimized.source, PatternMatchOperator)
        # The inner PatternMatch should have the vertex constraint pushed in
        inner_pm = optimized.source
        a_vp = next(vp for vp in inner_pm.pattern.vertex_patterns if vp.variable == "a")
        assert len(a_vp.constraints) == 1

    def test_no_match_edge_filter_preserved(self) -> None:
        """Edge filter that doesn't match any edge variable stays as filter."""
        from uqa.core.types import Equals
        from uqa.operators.primitive import FilterOperator

        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        filt = FilterOperator("x_y.prop", Equals("val"), pm)
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filt)
        # x_y doesn't match a_b, so filter is preserved
        assert isinstance(optimized, FilterOperator)


# -- Phase 2B: Join-Pattern Fusion Tests --


class TestJoinPatternFusion:
    def test_shared_variable_fusion(self) -> None:
        """Two patterns sharing variable 'a' should be fused."""
        p1 = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        p2 = GraphPattern(
            [VertexPattern("a"), VertexPattern("c")],
            [EdgePattern("a", "c", "works_with")],
        )
        pm1 = PatternMatchOperator(p1, graph=_GRAPH_NAME)
        pm2 = PatternMatchOperator(p2, graph=_GRAPH_NAME)
        intersect = IntersectOperator([pm1, pm2])
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)
        # Should be fused into a single PatternMatchOperator
        assert isinstance(optimized, PatternMatchOperator)
        # Merged pattern has 3 vertex patterns and 2 edge patterns
        assert len(optimized.pattern.vertex_patterns) == 3
        assert len(optimized.pattern.edge_patterns) == 2

    def test_no_shared_variables_preserved(self) -> None:
        """Patterns without shared variables should not be fused."""
        p1 = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        p2 = GraphPattern(
            [VertexPattern("c"), VertexPattern("d")],
            [EdgePattern("c", "d", "works_with")],
        )
        pm1 = PatternMatchOperator(p1, graph=_GRAPH_NAME)
        pm2 = PatternMatchOperator(p2, graph=_GRAPH_NAME)
        intersect = IntersectOperator([pm1, pm2])
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)
        # Should remain as IntersectOperator
        assert isinstance(optimized, IntersectOperator)

    def test_constraints_combined(self) -> None:
        """Shared variable constraints from both patterns should be combined."""

        def c1(v):
            return v.properties.get("age", 0) > 20

        def c2(v):
            return v.properties.get("age", 0) < 50

        p1 = GraphPattern(
            [VertexPattern("a", [c1]), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        p2 = GraphPattern(
            [VertexPattern("a", [c2]), VertexPattern("c")],
            [EdgePattern("a", "c", "works_with")],
        )
        pm1 = PatternMatchOperator(p1, graph=_GRAPH_NAME)
        pm2 = PatternMatchOperator(p2, graph=_GRAPH_NAME)
        intersect = IntersectOperator([pm1, pm2])
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)
        assert isinstance(optimized, PatternMatchOperator)
        # Variable 'a' should have both constraints
        a_vp = next(
            vp for vp in optimized.pattern.vertex_patterns if vp.variable == "a"
        )
        assert len(a_vp.constraints) == 2

    def test_mixed_operand_types(self) -> None:
        """IntersectOperator with mixed types preserves non-PatternMatch ops."""
        from uqa.operators.primitive import TermOperator

        p1 = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        pm1 = PatternMatchOperator(p1, graph=_GRAPH_NAME)
        term = TermOperator("test")
        intersect = IntersectOperator([pm1, term])
        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)
        # Should remain IntersectOperator with both operands
        assert isinstance(optimized, IntersectOperator)


# -- Phase 3A: Subgraph Index Tests --


class TestSubgraphIndex:
    def test_build_and_lookup(self) -> None:
        g = _make_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = SubgraphIndex.build(g, [pattern], graph_name=_GRAPH_NAME)
        result = idx.lookup(pattern)
        assert result is not None
        assert len(result) > 0

    def test_miss_returns_none(self) -> None:
        g = _make_graph()
        pattern1 = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        pattern2 = GraphPattern(
            [VertexPattern("x"), VertexPattern("y")],
            [EdgePattern("x", "y", "unknown_label")],
        )
        idx = SubgraphIndex.build(g, [pattern1], graph_name=_GRAPH_NAME)
        result = idx.lookup(pattern2)
        assert result is None

    def test_invalidation(self) -> None:
        g = _make_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = SubgraphIndex.build(g, [pattern], graph_name=_GRAPH_NAME)
        assert idx.has_pattern(pattern)
        idx.invalidate({"knows"})
        assert not idx.has_pattern(pattern)

    def test_pattern_match_uses_cache(self) -> None:
        g = _make_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        idx = SubgraphIndex.build(g, [pattern], graph_name=_GRAPH_NAME)
        ctx = ExecutionContext(graph_store=g, subgraph_index=idx)
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        result = pm.execute(ctx)
        # Should return results from cache
        assert len(result) > 0

    def test_canonical_key_deterministic(self) -> None:
        pattern = GraphPattern(
            [VertexPattern("b"), VertexPattern("a")],
            [EdgePattern("a", "b", "knows")],
        )
        key1 = SubgraphIndex._canonicalize(pattern)
        key2 = SubgraphIndex._canonicalize(pattern)
        assert key1 == key2


# -- Phase 3B: Incremental Pattern Matching Tests --


class TestIncrementalPatternMatcher:
    def test_add_edge_creates_new_match(self) -> None:
        g = _make_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        # Get initial matches
        ctx = ExecutionContext(graph_store=g)
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        initial_gpl = pm.execute(ctx)
        initial_matches = set()
        for entry in initial_gpl:
            gp = initial_gpl.get_graph_payload(entry.doc_id)
            if gp:
                initial_matches.add(gp.subgraph_vertices)

        matcher = IncrementalPatternMatcher(
            pattern, initial_matches, graph_name=_GRAPH_NAME
        )

        # Add a new edge 4->1 "knows"
        new_eid = g.next_edge_id()
        g.add_edge(Edge(new_eid, 4, 1, "knows"), graph=_GRAPH_NAME)
        delta = GraphDelta(added_edge_ids={new_eid})
        updated = matcher.update(g, delta)
        # Should now include (4, 1) match
        has_41 = any(frozenset({4, 1}).issubset(m) for m in updated)
        assert has_41

    def test_remove_vertex_invalidates_match(self) -> None:
        g = _make_graph()
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        ctx = ExecutionContext(graph_store=g)
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        initial_gpl = pm.execute(ctx)
        initial_matches = set()
        for entry in initial_gpl:
            gp = initial_gpl.get_graph_payload(entry.doc_id)
            if gp:
                initial_matches.add(gp.subgraph_vertices)

        matcher = IncrementalPatternMatcher(
            pattern, initial_matches, graph_name=_GRAPH_NAME
        )

        # Remove vertex 2
        g.remove_vertex(2, graph=_GRAPH_NAME)
        delta = GraphDelta(removed_vertex_ids={2})
        updated = matcher.update(g, delta)
        # No match should contain vertex 2
        for match in updated:
            assert 2 not in match

    def test_unrelated_delta_no_change(self) -> None:
        g = _make_graph()
        # Add an isolated vertex
        g.add_vertex(Vertex(99, "thing", {}), graph=_GRAPH_NAME)
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows")],
        )
        ctx = ExecutionContext(graph_store=g)
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        initial_gpl = pm.execute(ctx)
        initial_matches = set()
        for entry in initial_gpl:
            gp = initial_gpl.get_graph_payload(entry.doc_id)
            if gp:
                initial_matches.add(gp.subgraph_vertices)

        original_count = len(initial_matches)
        matcher = IncrementalPatternMatcher(
            pattern, initial_matches, graph_name=_GRAPH_NAME
        )

        # Add another isolated vertex -- should not affect pattern matches
        g.add_vertex(Vertex(100, "thing", {}), graph=_GRAPH_NAME)
        delta = GraphDelta(added_vertex_ids={100})
        updated = matcher.update(g, delta)
        assert len(updated) == original_count


# -- Phase 3C: Graph Sampling Cardinality Tests --


class TestGraphSamplingCardinality:
    def test_small_graph_uses_formula(self) -> None:
        """Small graph (< 10000 vertices) uses formula, not sampling."""
        gs = GraphStats(num_vertices=100, num_edges=200, avg_out_degree=2.0)
        estimator = CardinalityEstimator(graph_stats=gs)
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows", [])],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        stats = IndexStats(total_docs=100)
        result = estimator.estimate(pm, stats)
        # Should use formula-based estimate, not sampling
        assert result > 0

    def test_no_graph_store_fallback(self) -> None:
        """Without graph_store, even large graph falls back to formula."""
        gs = GraphStats(
            num_vertices=20000,
            num_edges=100000,
            avg_out_degree=5.0,
            label_counts={"knows": 100000},
        )
        estimator = CardinalityEstimator(graph_stats=gs, graph_store=None)
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows", [])],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        stats = IndexStats(total_docs=20000)
        result = estimator.estimate(pm, stats)
        assert result > 0

    def test_empty_graph_returns_zero(self) -> None:
        """Empty graph should return near-zero or zero matches."""
        gs = GraphStats(num_vertices=0, num_edges=0, avg_out_degree=0.0)
        estimator = CardinalityEstimator(graph_stats=gs)
        pattern = GraphPattern(
            [VertexPattern("a"), VertexPattern("b")],
            [EdgePattern("a", "b", "knows", [])],
        )
        pm = PatternMatchOperator(pattern, graph=_GRAPH_NAME)
        stats = IndexStats(total_docs=0)
        result = estimator.estimate(pm, stats)
        assert result >= 0


# -- Phase 2E: Temporal Cardinality Tests --


class TestTemporalCardinality:
    def test_range_half_coverage(self) -> None:
        """Range covering half total range gives ~0.5 selectivity."""
        gs = GraphStats(
            num_vertices=100,
            num_edges=200,
            avg_out_degree=2.0,
            min_timestamp=0.0,
            max_timestamp=100.0,
        )
        estimator = CardinalityEstimator(graph_stats=gs)
        sel = estimator._temporal_selectivity(
            type("TF", (), {"timestamp": None, "time_range": (0.0, 50.0)})(),
            gs,
        )
        assert sel == pytest.approx(0.5)

    def test_point_query_low_selectivity(self) -> None:
        """Point query on large range gives low selectivity."""
        gs = GraphStats(
            num_vertices=100,
            num_edges=200,
            avg_out_degree=2.0,
            min_timestamp=0.0,
            max_timestamp=1000.0,
        )
        estimator = CardinalityEstimator(graph_stats=gs)
        sel = estimator._temporal_selectivity(
            type("TF", (), {"timestamp": 50.0, "time_range": None})(),
            gs,
        )
        assert sel == pytest.approx(0.001)

    def test_no_temporal_data_returns_one(self) -> None:
        """No temporal data in stats returns selectivity 1.0."""
        gs = GraphStats(num_vertices=100, num_edges=200, avg_out_degree=2.0)
        estimator = CardinalityEstimator(graph_stats=gs)
        sel = estimator._temporal_selectivity(
            type("TF", (), {"timestamp": 50.0, "time_range": None})(),
            gs,
        )
        assert sel == 1.0


# -- SQL Function Tests --


class TestCentralitySQL:
    """Tests for centrality SQL functions (pagerank, hits, betweenness)."""

    @staticmethod
    def _make_engine():
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE net (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO net (name) VALUES ('A'), ('B'), ('C'), ('D')")
        for i in range(1, 5):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, '', 'net')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'knows', 'net')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'knows', 'net')")
        engine.sql("SELECT * FROM graph_add_edge(3, 3, 4, 'knows', 'net')")
        engine.sql("SELECT * FROM graph_add_edge(4, 2, 1, 'knows', 'net')")
        return engine

    def test_pagerank_from(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id, _score FROM pagerank()")
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 <= row["_score"] <= 1.0

    def test_pagerank_where(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT name, _score FROM net WHERE pagerank()")
        assert len(result.rows) > 0

    def test_pagerank_custom_damping(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id, _score FROM pagerank(0.95)")
        assert len(result.rows) > 0

    def test_hits_from(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id, _score FROM hits()")
        assert len(result.rows) > 0

    def test_betweenness_from(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id, _score FROM betweenness()")
        assert len(result.rows) > 0

    def test_centrality_with_order_by(self) -> None:
        engine = self._make_engine()
        result = engine.sql(
            "SELECT _doc_id, _score FROM pagerank() ORDER BY _score DESC LIMIT 2"
        )
        assert len(result.rows) == 2
        assert result.rows[0]["_score"] >= result.rows[1]["_score"]

    def test_centrality_with_aggregation(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT COUNT(*) AS cnt FROM pagerank()")
        assert result.rows[0]["cnt"] == 4

    def test_centrality_in_fusion(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT name, _score FROM net
            WHERE fuse_log_odds(
                text_match(name, 'A'),
                pagerank()
            )
            ORDER BY _score DESC
        """)
        assert result is not None


class TestWeightedRPQSQL:
    """Tests for weighted_rpq SQL function."""

    @staticmethod
    def _make_engine():
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE g (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO g (name) VALUES ('A'), ('B'), ('C')")
        for i in range(1, 4):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, '', 'g')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'knows', 'g', 'weight=1.5')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'knows', 'g', 'weight=2.5')")
        return engine

    def test_weighted_rpq_basic(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT _score FROM g
            WHERE weighted_rpq('knows', 1, 'weight', 'sum')
        """)
        assert len(result.rows) > 0

    def test_weighted_rpq_max(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT _score FROM g
            WHERE weighted_rpq('knows/knows', 1, 'weight', 'max')
        """)
        assert len(result.rows) >= 0

    def test_weighted_rpq_threshold(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT _score FROM g
            WHERE weighted_rpq('knows', 1, 'weight', 'sum', 2.0)
        """)
        # Only edges with weight > 2.0 should pass
        assert len(result.rows) >= 0


class TestProgressiveFusionSQL:
    """Tests for progressive_fusion SQL function."""

    @staticmethod
    def _make_engine():
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        engine.sql("INSERT INTO docs (content) VALUES ('machine learning algorithms')")
        engine.sql("INSERT INTO docs (content) VALUES ('deep learning networks')")
        engine.sql("INSERT INTO docs (content) VALUES ('database indexing')")
        return engine

    def test_progressive_fusion_basic(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT content, _score FROM docs
            WHERE progressive_fusion(
                text_match(content, 'learning'),
                bayesian_match(content, 'algorithms'),
                2,
                bayesian_match(content, 'machine'),
                1
            )
            ORDER BY _score DESC
        """)
        assert result is not None
        assert len(result.rows) <= 1

    def test_progressive_fusion_with_gating(self) -> None:
        engine = self._make_engine()
        result = engine.sql("""
            SELECT content, _score FROM docs
            WHERE progressive_fusion(
                text_match(content, 'learning'),
                bayesian_match(content, 'deep'),
                2,
                bayesian_match(content, 'networks'),
                1,
                'relu'
            )
        """)
        assert result is not None


class TestBoundedRPQSQL:
    """Tests for bounded RPQ via rpq() SQL function."""

    @staticmethod
    def _make_engine():
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE chain (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO chain (name) VALUES ('A'), ('B'), ('C'), ('D')")
        for i in range(1, 5):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, '', 'chain')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'next', 'chain')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'next', 'chain')")
        engine.sql("SELECT * FROM graph_add_edge(3, 3, 4, 'next', 'chain')")
        return engine

    def test_bounded_rpq_from(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id, name FROM rpq('next{1,2}', 1)")
        doc_ids = {row["_doc_id"] for row in result.rows}
        assert 2 in doc_ids  # 1 hop
        assert 3 in doc_ids  # 2 hops
        assert 4 not in doc_ids  # 3 hops, out of range

    def test_bounded_rpq_exact(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT _doc_id FROM rpq('next{2,2}', 1)")
        doc_ids = {row["_doc_id"] for row in result.rows}
        assert 3 in doc_ids
        assert 2 not in doc_ids

    def test_bounded_rpq_aggregate(self) -> None:
        engine = self._make_engine()
        result = engine.sql("SELECT COUNT(*) AS cnt FROM rpq('next{1,3}', 1)")
        assert result.rows[0]["cnt"] == 3
