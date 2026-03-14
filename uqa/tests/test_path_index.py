#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import os

import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.index import PathIndex
from uqa.graph.operators import RegularPathQueryOperator
from uqa.graph.pattern import Alternation, Concat, KleeneStar, Label
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext


def _build_test_graph() -> GraphStore:
    """Build a test graph: A -knows-> B -works_with-> C -manages-> D"""
    g = GraphStore()
    g.add_vertex(Vertex(1, "person", {"name": "Alice"}))
    g.add_vertex(Vertex(2, "person", {"name": "Bob"}))
    g.add_vertex(Vertex(3, "person", {"name": "Carol"}))
    g.add_vertex(Vertex(4, "person", {"name": "Dave"}))
    g.add_edge(Edge(1, 1, 2, "knows"))
    g.add_edge(Edge(2, 2, 3, "works_with"))
    g.add_edge(Edge(3, 3, 4, "manages"))
    g.add_edge(Edge(4, 1, 3, "knows"))
    return g


class TestPathIndex:
    """Tests for PathIndex class."""

    def test_build_single_label(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        pairs = idx.lookup(["knows"])
        assert pairs is not None
        assert (1, 2) in pairs
        assert (1, 3) in pairs

    def test_build_two_label_sequence(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows", "works_with"]])
        pairs = idx.lookup(["knows", "works_with"])
        assert pairs is not None
        assert (1, 3) in pairs

    def test_lookup_unindexed_path(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        assert idx.lookup(["works_with"]) is None

    def test_has_path(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        assert idx.has_path(["knows"])
        assert not idx.has_path(["manages"])

    def test_indexed_paths(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"], ["works_with"]])
        paths = idx.indexed_paths()
        assert "knows" in paths
        assert "works_with" in paths


class TestRPQWithPathIndex:
    """Tests for RegularPathQueryOperator with PathIndex integration."""

    def test_rpq_uses_index_for_simple_label(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        ctx = ExecutionContext(graph_store=g, path_index=idx)

        op = RegularPathQueryOperator(Label("knows"), start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        assert 2 in doc_ids
        assert 3 in doc_ids

    def test_rpq_uses_index_for_concat(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows", "works_with"]])
        ctx = ExecutionContext(graph_store=g, path_index=idx)

        expr = Concat(Label("knows"), Label("works_with"))
        op = RegularPathQueryOperator(expr, start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        assert 3 in doc_ids

    def test_rpq_falls_back_for_alternation(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        ctx = ExecutionContext(graph_store=g, path_index=idx)

        expr = Alternation(Label("knows"), Label("works_with"))
        op = RegularPathQueryOperator(expr, start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        assert 2 in doc_ids or 3 in doc_ids

    def test_rpq_falls_back_for_kleene_star(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        ctx = ExecutionContext(graph_store=g, path_index=idx)

        expr = KleeneStar(Label("knows"))
        op = RegularPathQueryOperator(expr, start_vertex=1)
        result = op.execute(ctx)
        assert len(result) > 0

    def test_rpq_without_index(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)

        op = RegularPathQueryOperator(Label("knows"), start_vertex=1)
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        assert 2 in doc_ids

    def test_rpq_all_starts_with_index(self) -> None:
        g = _build_test_graph()
        idx = PathIndex.build(g, [["knows"]])
        ctx = ExecutionContext(graph_store=g, path_index=idx)

        op = RegularPathQueryOperator(Label("knows"))
        result = op.execute(ctx)
        doc_ids = {e.doc_id for e in result}
        assert 2 in doc_ids
        assert 3 in doc_ids

    def test_extract_label_sequence_single(self) -> None:
        result = RegularPathQueryOperator._extract_label_sequence(Label("knows"))
        assert result == ["knows"]

    def test_extract_label_sequence_concat(self) -> None:
        expr = Concat(Label("a"), Label("b"))
        result = RegularPathQueryOperator._extract_label_sequence(expr)
        assert result == ["a", "b"]

    def test_extract_label_sequence_nested_concat(self) -> None:
        expr = Concat(Concat(Label("a"), Label("b")), Label("c"))
        result = RegularPathQueryOperator._extract_label_sequence(expr)
        assert result == ["a", "b", "c"]

    def test_extract_label_sequence_alternation(self) -> None:
        expr = Alternation(Label("a"), Label("b"))
        result = RegularPathQueryOperator._extract_label_sequence(expr)
        assert result is None

    def test_extract_label_sequence_kleene_star(self) -> None:
        expr = KleeneStar(Label("a"))
        result = RegularPathQueryOperator._extract_label_sequence(expr)
        assert result is None


class TestEnginePathIndex:
    """Tests for Engine path index management."""

    def test_build_and_get_path_index(self) -> None:
        e = Engine()
        g = e.create_graph("social")
        g.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        g.add_vertex(Vertex(2, "person", {"name": "Bob"}))
        g.add_edge(Edge(1, 1, 2, "knows"))

        e.build_path_index("social", [["knows"]])
        idx = e.get_path_index("social")
        assert idx is not None
        assert idx.has_path(["knows"])

    def test_drop_path_index(self) -> None:
        e = Engine()
        g = e.create_graph("social")
        g.add_vertex(Vertex(1, "person"))
        g.add_vertex(Vertex(2, "person"))
        g.add_edge(Edge(1, 1, 2, "knows"))

        e.build_path_index("social", [["knows"]])
        e.drop_path_index("social")
        assert e.get_path_index("social") is None

    def test_build_index_nonexistent_graph(self) -> None:
        e = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            e.build_path_index("nonexistent", [["knows"]])

    def test_path_index_persistence(self, tmp_path: object) -> None:
        db_path = os.path.join(str(tmp_path), "test.db")

        e1 = Engine(db_path=db_path)
        g = e1.create_graph("social")
        g.add_vertex(Vertex(1, "person", {"name": "Alice"}))
        g.add_vertex(Vertex(2, "person", {"name": "Bob"}))
        g.add_edge(Edge(1, 1, 2, "knows"))
        e1.build_path_index("social", [["knows"]])
        e1.close()

        e2 = Engine(db_path=db_path)
        idx = e2.get_path_index("social")
        assert idx is not None
        assert idx.has_path(["knows"])
        e2.close()


class TestCostModelWithPathIndex:
    """Test cost model changes for path-indexable RPQs."""

    def test_indexable_rpq_cheaper(self) -> None:
        from uqa.core.types import IndexStats
        from uqa.planner.cost_model import CostModel

        stats = IndexStats(total_docs=100)
        model = CostModel()

        simple_op = RegularPathQueryOperator(Label("knows"))
        complex_op = RegularPathQueryOperator(
            Alternation(Label("knows"), Label("works_with"))
        )

        simple_cost = model.estimate(simple_op, stats)
        complex_cost = model.estimate(complex_op, stats)
        assert simple_cost < complex_cost
