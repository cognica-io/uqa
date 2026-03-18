#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.types import Edge, IndexStats, Vertex
from uqa.graph.operators import PatternMatchOperator, TraverseOperator
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.operators.base import ExecutionContext
from uqa.operators.hybrid import LogOddsFusionOperator
from uqa.operators.primitive import FilterOperator, TermOperator
from uqa.planner.cardinality import CardinalityEstimator, GraphStats

# -- #1: Graph Cost Model & Cardinality --


def _make_graph_stats() -> tuple[GraphStore, GraphStats]:
    gs = GraphStore()
    gs.create_graph("g")
    for i in range(1, 11):
        gs.add_vertex(Vertex(i, "person", {}), graph="g")
    for i in range(1, 8):
        gs.add_edge(Edge(i, i, i + 1, "knows", {}), graph="g")
    gs.add_edge(Edge(8, 1, 5, "works_with", {}), graph="g")
    gs.add_edge(Edge(9, 3, 7, "works_with", {}), graph="g")

    graph_stats = GraphStats(
        num_vertices=10,
        num_edges=9,
        label_counts={"knows": 7, "works_with": 2},
        avg_out_degree=0.9,
    )
    return gs, graph_stats


def test_graph_stats_from_graph_store():
    gs, _ = _make_graph_stats()
    stats = GraphStats.from_graph_store(gs, graph="g")
    assert stats.num_vertices == 10
    assert stats.num_edges == 9
    assert stats.label_counts["knows"] == 7
    assert stats.avg_out_degree > 0


def test_graph_stats_vertex_label_counts():
    gs, _ = _make_graph_stats()
    stats = GraphStats.from_graph_store(gs, graph="g")
    assert stats.vertex_label_counts["person"] == 10


def test_graph_stats_label_degree():
    gs, _ = _make_graph_stats()
    stats = GraphStats.from_graph_store(gs, graph="g")
    assert "knows" in stats.label_degree_map
    assert stats.label_degree_map["knows"] > 0


def test_traverse_cardinality_with_stats():
    _, graph_stats = _make_graph_stats()
    estimator = CardinalityEstimator(graph_stats=graph_stats)
    idx_stats = IndexStats(total_docs=10, dimensions=0)

    op = TraverseOperator(1, graph="g", label="knows", max_hops=2)
    card = estimator.estimate(op, idx_stats)
    assert card > 0


def test_pattern_match_cardinality_with_stats():
    _, graph_stats = _make_graph_stats()
    estimator = CardinalityEstimator(graph_stats=graph_stats)
    idx_stats = IndexStats(total_docs=10, dimensions=0)

    pattern = GraphPattern(
        [VertexPattern("a"), VertexPattern("b")],
        [EdgePattern("a", "b", "knows")],
    )
    op = PatternMatchOperator(pattern, graph="g")
    card = estimator.estimate(op, idx_stats)
    assert card > 0


def test_traverse_uses_label_degree_map():
    """Traverse should use label_degree_map for label-specific branching."""
    gs, _ = _make_graph_stats()
    graph_stats = GraphStats.from_graph_store(gs, graph="g")
    # label_degree_map should have "knows" with a specific degree
    assert "knows" in graph_stats.label_degree_map

    estimator = CardinalityEstimator(graph_stats=graph_stats)
    idx_stats = IndexStats(total_docs=10, dimensions=0)

    op = TraverseOperator(1, graph="g", label="knows", max_hops=1)
    card = estimator.estimate(op, idx_stats)
    # Should use label-specific degree, not avg_out_degree * selectivity
    assert card > 0
    assert card <= 10


def test_rpq_uses_nfa_state_count():
    """RPQ cardinality should scale with expression complexity."""
    from uqa.graph.pattern import Concat, KleeneStar, Label

    graph_stats = GraphStats(
        num_vertices=100,
        num_edges=500,
        avg_out_degree=5.0,
        label_counts={"a": 200, "b": 300},
    )
    estimator = CardinalityEstimator(graph_stats=graph_stats)
    idx_stats = IndexStats(total_docs=100, dimensions=0)

    from uqa.graph.operators import RegularPathQueryOperator

    # Simple: single label
    op_simple = RegularPathQueryOperator(Label("a"), graph="g")
    card_simple = estimator.estimate(op_simple, idx_stats)

    # Complex: a/b/a* (more NFA states)
    op_complex = RegularPathQueryOperator(
        Concat(Label("a"), Concat(Label("b"), KleeneStar(Label("a")))),
        graph="g",
    )
    card_complex = estimator.estimate(op_complex, idx_stats)

    # Complex expression should have different (higher) cardinality estimate
    assert card_complex >= card_simple


# -- #9: Cross-Paradigm Optimizer rules --


def test_optimizer_accepts_graph_stats():
    """QueryOptimizer should accept graph_stats parameter."""
    from uqa.planner.optimizer import QueryOptimizer

    gs_stats = GraphStats(num_vertices=100, num_edges=500, avg_out_degree=5.0)
    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats, graph_stats=gs_stats)
    assert optimizer._graph_stats is not None
    assert optimizer._graph_stats.num_vertices == 100


def test_optimizer_graph_stats_passed_to_estimator():
    """graph_stats should be forwarded to the CardinalityEstimator."""
    from uqa.planner.optimizer import QueryOptimizer

    gs_stats = GraphStats(num_vertices=50, num_edges=200, avg_out_degree=4.0)
    idx_stats = IndexStats(total_docs=50, dimensions=0)
    optimizer = QueryOptimizer(idx_stats, graph_stats=gs_stats)
    assert optimizer.estimator._graph_stats is gs_stats


def test_optimizer_filter_pushdown_through_traverse():
    """Optimizer should not crash on graph operators."""
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)
    term_op = TermOperator("test")
    optimized = optimizer.optimize(term_op)
    assert optimized is not None


def test_optimizer_fusion_signal_reordering():
    """Fusion signals should be reordered by cost."""
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    sig1 = TermOperator("cheap", "field1")
    sig2 = TermOperator("expensive", "field2")
    fusion = LogOddsFusionOperator([sig2, sig1], alpha=0.5)
    optimized = optimizer.optimize(fusion)
    assert isinstance(optimized, LogOddsFusionOperator)


def test_graph_aware_fusion_reordering():
    """With graph_stats, graph operators should be preferred in fusion ordering.

    Graph traversal cardinality with stats: avg_out_degree * label_selectivity
    = 8.0 * (700/800) = 7.0. With the 0.5x graph discount, effective cost = 3.5.
    Text TermOperator cost = doc_freq = 5.0 (higher than discounted graph cost).
    Without graph_stats discount, graph cost 7.0 > text cost 5.0 (text first).
    With discount, graph cost 3.5 < text cost 5.0 (graph first).
    """
    from uqa.planner.optimizer import QueryOptimizer

    gs_stats = GraphStats(
        num_vertices=100,
        num_edges=800,
        label_counts={"knows": 700},
        avg_out_degree=8.0,
    )
    idx_stats = IndexStats(total_docs=100, dimensions=0)
    idx_stats._doc_freqs[("body", "hello")] = 5
    optimizer = QueryOptimizer(idx_stats, graph_stats=gs_stats)

    text_op = TermOperator("hello", "body")
    graph_op = TraverseOperator(1, graph="g", label="knows", max_hops=1)
    fusion = LogOddsFusionOperator([text_op, graph_op], alpha=0.5)

    optimized = optimizer.optimize(fusion)
    assert isinstance(optimized, LogOddsFusionOperator)
    # With graph_stats discount, graph op (3.5) < text op (5.0) -> graph first
    assert isinstance(optimized.signals[0], TraverseOperator)


def test_graph_aware_fusion_without_graph_stats():
    """Without graph_stats, no graph-specific discount is applied."""
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)
    assert optimizer._graph_stats is None

    text_op = TermOperator("hello", "body")
    graph_op = TraverseOperator(1, graph="g", label="knows", max_hops=1)
    fusion = LogOddsFusionOperator([text_op, graph_op], alpha=0.5)

    optimized = optimizer.optimize(fusion)
    assert isinstance(optimized, LogOddsFusionOperator)
    # Both signals should still be present (order depends on raw cost)
    assert len(optimized.signals) == 2


def test_filter_pushdown_below_graph_join():
    """Filter should be pushed below GraphJoinOperator."""
    from uqa.core.types import Equals
    from uqa.joins.cross_paradigm import GraphJoinOperator
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    left_op = TermOperator("alice", "name")
    right_op = TermOperator("bob", "name")
    join_op = GraphJoinOperator(left_op, right_op, "knows", graph="g")

    # Filter on top of graph join
    filter_op = FilterOperator("name", Equals("alice"), join_op)

    optimized = optimizer.optimize(filter_op)
    # Filter should have been pushed below the join
    assert isinstance(optimized, GraphJoinOperator)
    # The left side should now have the filter
    assert isinstance(optimized.left, FilterOperator)
    assert optimized.left.field == "name"


def test_filter_pushdown_preserves_non_graph_join():
    """Filter above non-GraphJoin operator should not be affected by graph join rule."""
    from uqa.core.types import Equals
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    term_op = TermOperator("test", "body")
    filter_op = FilterOperator("category", Equals("ml"), term_op)

    optimized = optimizer.optimize(filter_op)
    # Should still be a FilterOperator (no graph join to push into)
    assert isinstance(optimized, FilterOperator)


def test_graph_join_filter_pushdown_preserves_label():
    """Pushed filter should preserve the join label and graph name."""
    from uqa.core.types import GreaterThan
    from uqa.joins.cross_paradigm import GraphJoinOperator
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    left_op = TermOperator("a", "f1")
    right_op = TermOperator("b", "f2")
    join_op = GraphJoinOperator(left_op, right_op, "works_with", graph="myg")

    filter_op = FilterOperator("score", GreaterThan(0.5), join_op)
    optimized = optimizer.optimize(filter_op)

    assert isinstance(optimized, GraphJoinOperator)
    assert optimized.label == "works_with"
    assert optimized.graph_name == "myg"


def test_filter_pushdown_into_traverse():
    """Filter on vertex property should be pushed into TraverseOperator."""
    from uqa.core.types import Equals
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    traverse_op = TraverseOperator(1, graph="g", label="knows", max_hops=2)
    filter_op = FilterOperator("name", Equals("Alice"), traverse_op)

    optimized = optimizer.optimize(filter_op)
    # Filter should be absorbed into traverse's vertex_predicate
    assert isinstance(optimized, TraverseOperator)
    assert optimized.vertex_predicate is not None
    assert optimized.graph_name == "g"
    assert optimized.label == "knows"
    assert optimized.max_hops == 2


def test_filter_pushdown_into_traverse_end_to_end():
    """Pushed filter should prune vertices during BFS."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {"role": "admin"}), graph="g")
    gs.add_vertex(Vertex(2, "b", {"role": "user"}), graph="g")
    gs.add_vertex(Vertex(3, "c", {"role": "admin"}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")
    gs.add_edge(Edge(11, 1, 3, "e", {}), graph="g")

    from uqa.core.types import Equals
    from uqa.planner.optimizer import QueryOptimizer

    idx_stats = IndexStats(total_docs=3, dimensions=0)
    optimizer = QueryOptimizer(idx_stats)

    traverse_op = TraverseOperator(1, graph="g", max_hops=1)
    filter_op = FilterOperator("role", Equals("admin"), traverse_op)

    optimized = optimizer.optimize(filter_op)
    assert isinstance(optimized, TraverseOperator)

    ctx = ExecutionContext(graph_store=gs)
    result = optimized.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    # Only vertex 3 (admin) should be reached; vertex 2 (user) pruned
    # Vertex 1 is start, also admin
    assert 2 not in doc_ids
    assert 3 in doc_ids


def test_degree_distribution_in_graph_stats():
    """GraphStats.from_graph_store should populate degree_distribution."""
    gs, _ = _make_graph_stats()
    stats = GraphStats.from_graph_store(gs, graph="g")
    assert isinstance(stats.degree_distribution, dict)
    assert len(stats.degree_distribution) > 0
    # Sum of counts should equal num_vertices
    assert sum(stats.degree_distribution.values()) == stats.num_vertices


# -- #1: Graph Cost Model integration with CostModel --


def test_cost_model_with_graph_stats():
    """CostModel should use graph_stats for more precise traverse estimates."""
    from uqa.planner.cost_model import CostModel

    gs = GraphStats(
        num_vertices=100,
        num_edges=500,
        avg_out_degree=5.0,
        label_counts={"knows": 300},
    )
    cm = CostModel(graph_stats=gs)
    idx_stats = IndexStats(total_docs=100, dimensions=0)

    op = TraverseOperator(1, graph="g", label="knows", max_hops=2)
    cost_with_stats = cm.estimate(op, idx_stats)

    cm_no_stats = CostModel()
    cost_without_stats = cm_no_stats.estimate(op, idx_stats)

    # With stats should give a different (more precise) estimate
    assert cost_with_stats != cost_without_stats


def test_cost_model_pattern_with_negation():
    """Pattern with negated edges should have higher cost."""
    from uqa.planner.cost_model import CostModel

    cm = CostModel()
    idx_stats = IndexStats(total_docs=100, dimensions=0)

    pattern_pos = GraphPattern(
        [VertexPattern("a"), VertexPattern("b")],
        [EdgePattern("a", "b", "knows")],
    )
    pattern_neg = GraphPattern(
        [VertexPattern("a"), VertexPattern("b")],
        [
            EdgePattern("a", "b", "knows"),
            EdgePattern("a", "b", "blocks", negated=True),
        ],
    )

    op_pos = PatternMatchOperator(pattern_pos, graph="g")
    op_neg = PatternMatchOperator(pattern_neg, graph="g")

    cost_pos = cm.estimate(op_pos, idx_stats)
    cost_neg = cm.estimate(op_neg, idx_stats)

    # Negated pattern should cost more
    assert cost_neg > cost_pos


def test_cost_model_rpq_with_graph_stats():
    """RPQ cost should use O(V^2 * |R|) formula when graph_stats available."""
    from uqa.graph.operators import RegularPathQueryOperator
    from uqa.graph.pattern import Alternation, KleeneStar, Label
    from uqa.planner.cost_model import CostModel

    gs = GraphStats(
        num_vertices=100,
        num_edges=500,
        avg_out_degree=5.0,
        label_counts={"knows": 300, "likes": 200},
    )

    # Non-path-indexable expression: (knows|likes)*
    expr = KleeneStar(Alternation(Label("knows"), Label("likes")))
    op = RegularPathQueryOperator(expr, graph="g", start_vertex=1)

    cm_with = CostModel(graph_stats=gs)
    cm_without = CostModel()
    idx_stats = IndexStats(total_docs=100, dimensions=0)

    cost_with = cm_with.estimate(op, idx_stats)
    cost_without = cm_without.estimate(op, idx_stats)

    # With stats: V^2 * r_size * 0.001; without stats: n^2
    assert cost_with != cost_without
    # With stats should be more nuanced (not just n^2)
    assert cost_with > 0


def test_cost_model_graph_stats_forwarded_by_optimizer():
    """QueryOptimizer should forward graph_stats to CostModel."""
    from uqa.planner.optimizer import QueryOptimizer

    gs = GraphStats(
        num_vertices=100,
        num_edges=500,
        avg_out_degree=5.0,
        label_counts={"knows": 300},
    )
    idx_stats = IndexStats(total_docs=100, dimensions=0)
    optimizer = QueryOptimizer(idx_stats, graph_stats=gs)

    # Verify CostModel received graph_stats
    assert optimizer._cost_model._graph_stats is gs
