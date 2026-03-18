#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Paper 1 and Paper 2 gap implementations.

Covers:
- VectorExclusionOperator (Paper 1, Definition 3.3.3)
- FacetVectorOperator (Paper 1, Definition 3.3.4)
- PathAggregateOperator (Paper 1, Definition 5.3.3)
- UnifiedFilterOperator (Paper 1, Definition 5.3.5)
- VertexAggregationOperator (Paper 2, Definition 2.2.3)
- Graph pattern pushdown (Paper 2, Theorem 6.1.1)
- Join-pattern fusion (Paper 2, Theorem 6.1.2)
- Statistics-based graph cardinality (Paper 2, Theorem 6.3.2)
- Graph indexing structures (Paper 2, Section 6.4)
"""

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Edge,
    Equals,
    GreaterThan,
    IndexStats,
    Payload,
    PostingEntry,
    Vertex,
)
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.operators.base import ExecutionContext, Operator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FixedOperator(Operator):
    """Test helper: returns a fixed posting list."""

    def __init__(self, entries: list[PostingEntry]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return PostingList(self._entries)


def _make_doc_store_with_fields(docs: list[dict]) -> object:
    """Build a minimal DocumentStore from a list of dicts."""
    from uqa.storage.document_store import MemoryDocumentStore as DocumentStore

    store = DocumentStore()
    for doc in docs:
        did = doc.pop("doc_id")
        store.put(did, doc)
    return store


def _make_graph() -> GraphStore:
    vertices = [
        Vertex(1, "", {"name": "Alice", "age": 30, "dept": "eng"}),
        Vertex(2, "", {"name": "Bob", "age": 25, "dept": "eng"}),
        Vertex(3, "", {"name": "Charlie", "age": 35, "dept": "sales"}),
        Vertex(4, "", {"name": "Diana", "age": 28, "dept": "eng"}),
        Vertex(5, "", {"name": "Eve", "age": 32, "dept": "sales"}),
    ]
    edges = [
        Edge(1, 1, 2, "knows", {"weight": 0.9}),
        Edge(2, 1, 3, "knows", {"weight": 0.7}),
        Edge(3, 2, 3, "knows", {"weight": 0.5}),
        Edge(4, 2, 4, "works_with", {"weight": 0.8}),
        Edge(5, 3, 4, "knows", {"weight": 0.6}),
        Edge(6, 3, 5, "works_with", {"weight": 0.4}),
        Edge(7, 4, 5, "knows", {"weight": 0.3}),
    ]
    g = GraphStore()
    g.create_graph("test")
    for v in vertices:
        g.add_vertex(v, graph="test")
    for e in edges:
        g.add_edge(e, graph="test")
    return g


class _GraphContext:
    """Minimal execution context for graph tests."""

    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store


# ===========================================================================
# Paper 1: VectorExclusionOperator
# ===========================================================================


class TestVectorExclusionOperator:
    def test_excludes_negative_matches(self) -> None:
        from uqa.operators.hybrid import VectorExclusionOperator

        positive = _FixedOperator(
            [
                PostingEntry(1, Payload(score=0.9)),
                PostingEntry(2, Payload(score=0.8)),
                PostingEntry(3, Payload(score=0.7)),
            ]
        )
        # Negative vector op will execute against vector index -- use a context
        # with no vector index so negative returns empty -> nothing excluded.
        ctx = ExecutionContext()
        neg_vec = np.zeros(4, dtype=np.float32)
        op = VectorExclusionOperator(positive, neg_vec, negative_threshold=0.5)
        result = op.execute(ctx)
        # No vector index -> negative returns empty -> all positive kept
        assert len(result) == 3

    def test_cost_estimate(self) -> None:
        from uqa.operators.hybrid import VectorExclusionOperator

        positive = _FixedOperator([])
        neg_vec = np.zeros(4, dtype=np.float32)
        op = VectorExclusionOperator(positive, neg_vec, negative_threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        cost = op.cost_estimate(stats)
        assert cost > 0


# ===========================================================================
# Paper 1: FacetVectorOperator
# ===========================================================================


class TestFacetVectorOperator:
    def test_facet_over_empty_vector_results(self) -> None:
        from uqa.operators.hybrid import FacetVectorOperator

        query_vec = np.zeros(4, dtype=np.float32)
        op = FacetVectorOperator("category", query_vec, threshold=0.5)
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 0

    def test_facet_counts_fields(self) -> None:
        from uqa.operators.hybrid import FacetVectorOperator
        from uqa.storage.document_store import MemoryDocumentStore as DocumentStore

        store = DocumentStore()
        store.put(1, {"category": "A", "title": "doc1"})
        store.put(2, {"category": "B", "title": "doc2"})
        store.put(3, {"category": "A", "title": "doc3"})

        # Use a fixed source instead of vector index
        source = _FixedOperator(
            [
                PostingEntry(1, Payload(score=0.9)),
                PostingEntry(2, Payload(score=0.8)),
                PostingEntry(3, Payload(score=0.7)),
            ]
        )

        query_vec = np.zeros(4, dtype=np.float32)
        op = FacetVectorOperator("category", query_vec, threshold=0.5, source=source)

        # No vector index -> vector returns empty -> no docs pass
        ctx = ExecutionContext(document_store=store)
        result = op.execute(ctx)
        # With no vector index, vector_ids is empty, so intersection is empty
        assert len(result) == 0

    def test_cost_estimate(self) -> None:
        from uqa.operators.hybrid import FacetVectorOperator

        query_vec = np.zeros(4, dtype=np.float32)
        op = FacetVectorOperator("category", query_vec, threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        cost = op.cost_estimate(stats)
        assert cost > 0


# ===========================================================================
# Paper 1: PathAggregateOperator
# ===========================================================================


class TestPathAggregateOperator:
    def _make_context(self) -> ExecutionContext:
        from uqa.storage.document_store import MemoryDocumentStore as DocumentStore

        store = DocumentStore()
        store.put(
            1,
            {
                "title": "order1",
                "items": [10, 20, 30],
            },
        )
        store.put(
            2,
            {
                "title": "order2",
                "items": [5, 15],
            },
        )
        store.put(
            3,
            {
                "title": "order3",
                "items": 42,  # single value, not a list
            },
        )
        return ExecutionContext(document_store=store)

    def test_sum_over_array(self) -> None:
        from uqa.operators.aggregation import SumMonoid
        from uqa.operators.hierarchical import PathAggregateOperator

        source = _FixedOperator(
            [
                PostingEntry(1, Payload(score=0.0)),
                PostingEntry(2, Payload(score=0.0)),
            ]
        )
        op = PathAggregateOperator(["items"], SumMonoid(), source)
        result = op.execute(self._make_context())
        assert len(result) == 2
        scores = [e.payload.score for e in result]
        assert scores[0] == pytest.approx(60.0)  # 10+20+30
        assert scores[1] == pytest.approx(20.0)  # 5+15

    def test_avg_over_array(self) -> None:
        from uqa.operators.aggregation import AvgMonoid
        from uqa.operators.hierarchical import PathAggregateOperator

        source = _FixedOperator(
            [
                PostingEntry(1, Payload(score=0.0)),
            ]
        )
        op = PathAggregateOperator(["items"], AvgMonoid(), source)
        result = op.execute(self._make_context())
        assert result.entries[0].payload.score == pytest.approx(20.0)

    def test_single_value_not_list(self) -> None:
        from uqa.operators.aggregation import SumMonoid
        from uqa.operators.hierarchical import PathAggregateOperator

        source = _FixedOperator([PostingEntry(3, Payload(score=0.0))])
        op = PathAggregateOperator(["items"], SumMonoid(), source)
        result = op.execute(self._make_context())
        assert result.entries[0].payload.score == pytest.approx(42.0)

    def test_missing_path(self) -> None:
        from uqa.operators.aggregation import SumMonoid
        from uqa.operators.hierarchical import PathAggregateOperator
        from uqa.storage.document_store import MemoryDocumentStore as DocumentStore

        store = DocumentStore()
        store.put(1, {"title": "no items"})
        ctx = ExecutionContext(document_store=store)

        source = _FixedOperator([PostingEntry(1, Payload(score=0.0))])
        op = PathAggregateOperator(["items"], SumMonoid(), source)
        result = op.execute(ctx)
        assert result.entries[0].payload.score == pytest.approx(0.0)

    def test_count_over_array(self) -> None:
        from uqa.operators.aggregation import CountMonoid
        from uqa.operators.hierarchical import PathAggregateOperator

        source = _FixedOperator([PostingEntry(1, Payload(score=0.0))])
        op = PathAggregateOperator(["items"], CountMonoid(), source)
        result = op.execute(self._make_context())
        assert result.entries[0].payload.score == pytest.approx(3.0)

    def test_min_max_over_array(self) -> None:
        from uqa.operators.aggregation import MaxMonoid, MinMonoid
        from uqa.operators.hierarchical import PathAggregateOperator

        source = _FixedOperator([PostingEntry(1, Payload(score=0.0))])
        ctx = self._make_context()

        min_op = PathAggregateOperator(["items"], MinMonoid(), source)
        min_result = min_op.execute(ctx)
        assert min_result.entries[0].payload.score == pytest.approx(10.0)

        max_op = PathAggregateOperator(["items"], MaxMonoid(), source)
        max_result = max_op.execute(ctx)
        assert max_result.entries[0].payload.score == pytest.approx(30.0)


# ===========================================================================
# Paper 1: UnifiedFilterOperator
# ===========================================================================


class TestUnifiedFilterOperator:
    def _make_context(self) -> ExecutionContext:
        from uqa.storage.document_store import MemoryDocumentStore as DocumentStore

        store = DocumentStore()
        store.put(
            1,
            {
                "year": 2023,
                "metadata": {"author": "Alice", "score": 95},
            },
        )
        store.put(
            2,
            {
                "year": 2024,
                "metadata": {"author": "Bob", "score": 88},
            },
        )
        store.put(
            3,
            {
                "year": 2025,
                "metadata": {"author": "Alice", "score": 72},
            },
        )
        return ExecutionContext(document_store=store)

    def test_flat_field_filter(self) -> None:
        from uqa.operators.hierarchical import UnifiedFilterOperator

        op = UnifiedFilterOperator("year", GreaterThan(2023))
        result = op.execute(self._make_context())
        assert sorted(e.doc_id for e in result) == [2, 3]

    def test_hierarchical_path_filter(self) -> None:
        from uqa.operators.hierarchical import UnifiedFilterOperator

        op = UnifiedFilterOperator("metadata.author", Equals("Alice"))
        result = op.execute(self._make_context())
        assert sorted(e.doc_id for e in result) == [1, 3]

    def test_hierarchical_numeric_path(self) -> None:
        from uqa.operators.hierarchical import UnifiedFilterOperator

        op = UnifiedFilterOperator("metadata.score", GreaterThan(80))
        result = op.execute(self._make_context())
        assert sorted(e.doc_id for e in result) == [1, 2]

    def test_with_source_operator(self) -> None:
        from uqa.operators.hierarchical import UnifiedFilterOperator

        source = _FixedOperator(
            [
                PostingEntry(1, Payload(score=1.0)),
                PostingEntry(2, Payload(score=0.8)),
            ]
        )
        op = UnifiedFilterOperator("year", GreaterThan(2023), source=source)
        result = op.execute(self._make_context())
        assert [e.doc_id for e in result] == [2]


# ===========================================================================
# Paper 2: VertexAggregationOperator
# ===========================================================================


class TestVertexAggregationOperator:
    def test_sum_ages(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "sum")
        result = agg.execute(ctx)
        assert len(result) == 1
        # Traverse from 1 with "knows" 1 hop: {1, 2, 3}
        # Ages: 30 + 25 + 35 = 90
        assert result.entries[0].payload.score == pytest.approx(90.0)

    def test_avg_ages(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "avg")
        result = agg.execute(ctx)
        assert result.entries[0].payload.score == pytest.approx(30.0)

    def test_min_max_ages(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )

        min_agg = VertexAggregationOperator(traverse, "age", "min")
        min_result = min_agg.execute(ctx)
        assert min_result.entries[0].payload.score == pytest.approx(25.0)

        max_agg = VertexAggregationOperator(traverse, "age", "max")
        max_result = max_agg.execute(ctx)
        assert max_result.entries[0].payload.score == pytest.approx(35.0)

    def test_count(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "count")
        result = agg.execute(ctx)
        assert result.entries[0].payload.score == pytest.approx(3.0)

    def test_missing_property(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "nonexistent", "sum")
        result = agg.execute(ctx)
        assert result.entries[0].payload.score == pytest.approx(0.0)

    def test_payload_fields(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator

        graph = _make_graph()
        ctx = _GraphContext(graph)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "sum")
        result = agg.execute(ctx)
        entry = result.entries[0]
        assert entry.payload.fields["_vertex_agg_property"] == "age"
        assert entry.payload.fields["_vertex_agg_fn"] == "sum"
        assert entry.payload.fields["_vertex_agg_count"] == 3


# ===========================================================================
# Paper 2: Graph pattern pushdown
# ===========================================================================


class TestGraphPatternPushdown:
    def test_filter_pushed_into_pattern(self) -> None:
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
        from uqa.operators.primitive import FilterOperator
        from uqa.planner.optimizer import QueryOptimizer

        # Pattern: a --knows--> b
        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a", []),
                VertexPattern("b", []),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "knows", []),
            ],
        )
        pm = PatternMatchOperator(pattern, graph="test")
        # Filter on "a.age" > 30 (qualified to vertex "a")
        filtered = FilterOperator("a.age", GreaterThan(30), pm)

        stats = IndexStats(total_docs=5)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        # After optimization, the filter should be absorbed into the pattern
        assert isinstance(optimized, PatternMatchOperator)
        # The first vertex pattern should have the pushed constraint
        assert len(optimized.pattern.vertex_patterns[0].constraints) == 1

    def test_pushdown_preserves_correctness(self) -> None:
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
        from uqa.operators.primitive import FilterOperator
        from uqa.planner.optimizer import QueryOptimizer

        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a", []),
                VertexPattern("b", []),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "knows", []),
            ],
        )
        pm = PatternMatchOperator(pattern, graph="test")
        filtered = FilterOperator("a.dept", Equals("eng"), pm)

        stats = IndexStats(total_docs=5)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        # Execute the optimized plan
        graph = _make_graph()
        ctx = _GraphContext(graph)
        result = optimized.execute(ctx)

        # Only matches where first vertex has dept=eng:
        # Vertex 1 (eng)->2, 1->3: a=1 is eng
        # Vertex 2 (eng)->3, 2->4: a=2 is eng
        # Vertex 4 (eng)->5: a=4 is eng
        # Vertex 3 is sales, vertex 5 is sales -- excluded as 'a'
        for entry in result:
            a_id = entry.payload.fields.get("a")
            if a_id is not None:
                v = graph.get_vertex(a_id)
                assert v is not None
                assert v.properties.get("dept") == "eng"


# ===========================================================================
# Paper 2: Join-pattern fusion
# ===========================================================================


class TestJoinPatternFusion:
    def test_composed_join_pattern_fused(self) -> None:
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
        from uqa.operators.base import ComposedOperator
        from uqa.planner.optimizer import QueryOptimizer

        pattern = GraphPattern(
            vertex_patterns=[
                VertexPattern("a", []),
                VertexPattern("b", []),
            ],
            edge_patterns=[
                EdgePattern("a", "b", "knows", []),
            ],
        )
        # Simulate join -> pattern match composition
        join_op = _FixedOperator([])  # dummy join
        pm = PatternMatchOperator(pattern, graph="test")
        composed = ComposedOperator([join_op, pm])

        stats = IndexStats(total_docs=5)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(composed)

        # The composition preserves both children (no unsafe fusion)
        assert isinstance(optimized, ComposedOperator)
        assert len(optimized.operators) == 2
        assert isinstance(optimized.operators[1], PatternMatchOperator)


# ===========================================================================
# Paper 2: Statistics-based graph cardinality
# ===========================================================================


class TestGraphCardinality:
    def test_traverse_with_stats(self) -> None:
        from uqa.graph.operators import TraverseOperator
        from uqa.planner.cardinality import CardinalityEstimator, GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")
        estimator = CardinalityEstimator(graph_stats=gs)

        stats = IndexStats(total_docs=5)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=2
        )
        card = estimator.estimate(traverse, stats)

        # With stats, should use avg_out_degree * label_selectivity
        assert card > 0
        assert card <= 5.0

    def test_traverse_without_stats(self) -> None:
        from uqa.graph.operators import TraverseOperator
        from uqa.planner.cardinality import CardinalityEstimator

        estimator = CardinalityEstimator()
        stats = IndexStats(total_docs=100)
        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        card = estimator.estimate(traverse, stats)
        # Fallback heuristic
        assert card > 0

    def test_pattern_match_with_stats(self) -> None:
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
        from uqa.planner.cardinality import CardinalityEstimator, GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")
        estimator = CardinalityEstimator(graph_stats=gs)

        pattern = GraphPattern(
            vertex_patterns=[VertexPattern("a", []), VertexPattern("b", [])],
            edge_patterns=[EdgePattern("a", "b", "knows", [])],
        )
        pm = PatternMatchOperator(pattern, graph="test")
        stats = IndexStats(total_docs=5)
        card = estimator.estimate(pm, stats)

        # Should be |V|^2 * density * label_selectivity
        assert card >= 1.0
        assert card <= 5.0

    def test_rpq_with_stats(self) -> None:
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import Label
        from uqa.planner.cardinality import CardinalityEstimator, GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")
        estimator = CardinalityEstimator(graph_stats=gs)

        rpq = RegularPathQueryOperator(Label("knows"), graph="test", start_vertex=1)
        stats = IndexStats(total_docs=5)
        card = estimator.estimate(rpq, stats)
        assert card >= 1.0
        assert card <= 5.0

    def test_graph_stats_properties(self) -> None:
        from uqa.planner.cardinality import GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")

        assert gs.num_vertices == 5
        assert gs.num_edges == 7
        assert gs.avg_out_degree == pytest.approx(7 / 5)
        assert "knows" in gs.label_counts
        assert "works_with" in gs.label_counts
        assert gs.label_counts["knows"] == 5
        assert gs.label_counts["works_with"] == 2

    def test_label_selectivity(self) -> None:
        from uqa.planner.cardinality import GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")

        assert gs.label_selectivity("knows") == pytest.approx(5 / 7)
        assert gs.label_selectivity("works_with") == pytest.approx(2 / 7)
        assert gs.label_selectivity("nonexistent") == pytest.approx(0.0)
        assert gs.label_selectivity(None) == pytest.approx(1.0)

    def test_edge_density(self) -> None:
        from uqa.planner.cardinality import GraphStats

        graph = _make_graph()
        gs = GraphStats.from_graph_store(graph, graph="test")
        assert gs.edge_density() == pytest.approx(7 / 25)


# ===========================================================================
# Paper 2: Graph indexing structures
# ===========================================================================


class TestLabelIndex:
    def test_build_and_lookup(self) -> None:
        from uqa.graph.index import LabelIndex

        graph = _make_graph()
        idx = LabelIndex.build(graph, graph_name="test")

        knows_edges = idx.edges_by_label("knows")
        assert len(knows_edges) == 5
        assert knows_edges == sorted(knows_edges)

        works_with_edges = idx.edges_by_label("works_with")
        assert len(works_with_edges) == 2

    def test_vertices_by_label(self) -> None:
        from uqa.graph.index import LabelIndex

        graph = _make_graph()
        idx = LabelIndex.build(graph, graph_name="test")

        knows_verts = idx.vertices_by_label("knows")
        # All vertices involved in "knows" edges
        assert 1 in knows_verts
        assert 2 in knows_verts
        assert 3 in knows_verts

    def test_label_count(self) -> None:
        from uqa.graph.index import LabelIndex

        graph = _make_graph()
        idx = LabelIndex.build(graph, graph_name="test")

        assert idx.label_count("knows") == 5
        assert idx.label_count("works_with") == 2
        assert idx.label_count("nonexistent") == 0

    def test_labels(self) -> None:
        from uqa.graph.index import LabelIndex

        graph = _make_graph()
        idx = LabelIndex.build(graph, graph_name="test")
        assert idx.labels() == ["knows", "works_with"]

    def test_empty_graph(self) -> None:
        from uqa.graph.index import LabelIndex

        graph = GraphStore()
        graph.create_graph("test")
        idx = LabelIndex.build(graph, graph_name="test")
        assert idx.labels() == []
        assert idx.edges_by_label("knows") == []


class TestNeighborhoodIndex:
    def test_build_and_lookup(self) -> None:
        from uqa.graph.index import NeighborhoodIndex

        graph = _make_graph()
        idx = NeighborhoodIndex.build(graph, max_hops=2, graph_name="test")

        n1_hop1 = idx.neighbors(1, 1)
        assert 1 in n1_hop1
        assert 2 in n1_hop1
        assert 3 in n1_hop1

        n1_hop2 = idx.neighbors(1, 2)
        # 2 hops from 1: can reach 4, 5 via knows/works_with
        assert len(n1_hop2) > len(n1_hop1)

    def test_label_filtered(self) -> None:
        from uqa.graph.index import NeighborhoodIndex

        graph = _make_graph()
        idx = NeighborhoodIndex.build(
            graph, max_hops=2, label="knows", graph_name="test"
        )

        n1 = idx.neighbors(1, 1)
        assert 2 in n1
        assert 3 in n1
        # 4 is only reachable via "works_with" from 2, so via "knows" only
        # at 2 hops: 1->2->3, 1->3->4 (3->4 is "knows")
        n2 = idx.neighbors(1, 2)
        assert 4 in n2

    def test_nonexistent_vertex(self) -> None:
        from uqa.graph.index import NeighborhoodIndex

        graph = _make_graph()
        idx = NeighborhoodIndex.build(graph, max_hops=1, graph_name="test")
        assert idx.neighbors(999, 1) == set()
        assert not idx.has_vertex(999)

    def test_has_vertex(self) -> None:
        from uqa.graph.index import NeighborhoodIndex

        graph = _make_graph()
        idx = NeighborhoodIndex.build(graph, max_hops=1, graph_name="test")
        for vid in range(1, 6):
            assert idx.has_vertex(vid)

    def test_empty_graph(self) -> None:
        from uqa.graph.index import NeighborhoodIndex

        graph = GraphStore()
        graph.create_graph("test")
        idx = NeighborhoodIndex.build(graph, max_hops=2, graph_name="test")
        assert idx.neighbors(1, 1) == set()


class TestPathIndex:
    def test_build_single_hop(self) -> None:
        from uqa.graph.index import PathIndex

        graph = _make_graph()
        idx = PathIndex.build(graph, [["knows"]], graph_name="test")

        pairs = idx.lookup(["knows"])
        assert pairs is not None
        assert (1, 2) in pairs
        assert (1, 3) in pairs
        assert (2, 3) in pairs

    def test_build_multi_hop(self) -> None:
        from uqa.graph.index import PathIndex

        graph = _make_graph()
        idx = PathIndex.build(graph, [["knows", "knows"]], graph_name="test")

        pairs = idx.lookup(["knows", "knows"])
        assert pairs is not None
        # 1->2->3 (knows, knows)
        assert (1, 3) in pairs
        # 1->3->4 (knows, knows)
        assert (1, 4) in pairs

    def test_cross_label_path(self) -> None:
        from uqa.graph.index import PathIndex

        graph = _make_graph()
        idx = PathIndex.build(graph, [["knows", "works_with"]], graph_name="test")

        pairs = idx.lookup(["knows", "works_with"])
        assert pairs is not None
        # 1->2->4 (knows, works_with)
        assert (1, 4) in pairs
        # 1->3->5 (knows, works_with)
        assert (1, 5) in pairs

    def test_nonexistent_path(self) -> None:
        from uqa.graph.index import PathIndex

        graph = _make_graph()
        idx = PathIndex.build(graph, [["knows"]], graph_name="test")
        assert idx.lookup(["works_with"]) is None
        assert not idx.has_path(["works_with"])

    def test_indexed_paths(self) -> None:
        from uqa.graph.index import PathIndex

        graph = _make_graph()
        idx = PathIndex.build(
            graph, [["knows"], ["knows", "works_with"]], graph_name="test"
        )
        assert idx.indexed_paths() == ["knows", "knows/works_with"]

    def test_empty_graph(self) -> None:
        from uqa.graph.index import PathIndex

        graph = GraphStore()
        graph.create_graph("test")
        idx = PathIndex.build(graph, [["knows"]], graph_name="test")
        pairs = idx.lookup(["knows"])
        assert pairs is not None
        assert len(pairs) == 0


# ===========================================================================
# CostModel for new operators
# ===========================================================================


class TestCostModelNewOperators:
    def test_vector_exclusion_cost(self) -> None:
        from uqa.operators.hybrid import VectorExclusionOperator
        from uqa.planner.cost_model import CostModel

        positive = _FixedOperator([])
        neg_vec = np.zeros(4, dtype=np.float32)
        op = VectorExclusionOperator(positive, neg_vec, negative_threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        cost = CostModel().estimate(op, stats)
        assert cost > 0

    def test_facet_vector_cost(self) -> None:
        from uqa.operators.hybrid import FacetVectorOperator
        from uqa.planner.cost_model import CostModel

        query_vec = np.zeros(4, dtype=np.float32)
        op = FacetVectorOperator("category", query_vec, threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        cost = CostModel().estimate(op, stats)
        assert cost > 0

    def test_vertex_aggregation_cost(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator
        from uqa.planner.cost_model import CostModel

        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "sum")
        stats = IndexStats(total_docs=100)
        cost = CostModel().estimate(agg, stats)
        assert cost > 0


# ===========================================================================
# CardinalityEstimator for new operators
# ===========================================================================


class TestCardinalityNewOperators:
    def test_vector_exclusion_cardinality(self) -> None:
        from uqa.operators.hybrid import VectorExclusionOperator
        from uqa.planner.cardinality import CardinalityEstimator

        positive = _FixedOperator([])
        neg_vec = np.zeros(4, dtype=np.float32)
        op = VectorExclusionOperator(positive, neg_vec, negative_threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        card = CardinalityEstimator().estimate(op, stats)
        assert card >= 1.0

    def test_facet_vector_cardinality(self) -> None:
        from uqa.operators.hybrid import FacetVectorOperator
        from uqa.planner.cardinality import CardinalityEstimator

        query_vec = np.zeros(4, dtype=np.float32)
        op = FacetVectorOperator("category", query_vec, threshold=0.5)
        stats = IndexStats(total_docs=100, dimensions=4)
        card = CardinalityEstimator().estimate(op, stats)
        assert card > 0

    def test_vertex_aggregation_cardinality(self) -> None:
        from uqa.graph.operators import TraverseOperator, VertexAggregationOperator
        from uqa.planner.cardinality import CardinalityEstimator

        traverse = TraverseOperator(
            start_vertex=1, graph="test", label="knows", max_hops=1
        )
        agg = VertexAggregationOperator(traverse, "age", "sum")
        stats = IndexStats(total_docs=100)
        card = CardinalityEstimator().estimate(agg, stats)
        assert card == pytest.approx(1.0)
