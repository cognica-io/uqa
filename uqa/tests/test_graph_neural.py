#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math

import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.graph_embedding import GraphEmbeddingOperator
from uqa.graph.message_passing import MessagePassingOperator
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext


def _build_test_graph() -> GraphStore:
    g = GraphStore()
    g.add_vertex(Vertex(1, "person", {"name": "Alice", "score": 0.8}))
    g.add_vertex(Vertex(2, "person", {"name": "Bob", "score": 0.6}))
    g.add_vertex(Vertex(3, "person", {"name": "Carol", "score": 0.4}))
    g.add_vertex(Vertex(4, "person", {"name": "Dave", "score": 0.2}))
    g.add_edge(Edge(1, 1, 2, "knows"))
    g.add_edge(Edge(2, 2, 3, "knows"))
    g.add_edge(Edge(3, 3, 4, "works_with"))
    g.add_edge(Edge(4, 1, 3, "works_with"))
    return g


class TestMessagePassingOperator:
    """Tests for MessagePassingOperator."""

    def test_basic_execution(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(
            k_layers=1, aggregation="mean", property_name="score"
        )
        result = op.execute(ctx)
        assert len(result) == 4

    def test_scores_are_probabilities(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(
            k_layers=2, aggregation="mean", property_name="score"
        )
        result = op.execute(ctx)
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0

    def test_sum_aggregation(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(
            k_layers=1, aggregation="sum", property_name="score"
        )
        result = op.execute(ctx)
        assert len(result) == 4

    def test_max_aggregation(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(
            k_layers=1, aggregation="max", property_name="score"
        )
        result = op.execute(ctx)
        assert len(result) == 4

    def test_no_property_uses_default(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(k_layers=1)
        result = op.execute(ctx)
        assert len(result) == 4

    def test_empty_graph(self) -> None:
        g = GraphStore()
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator()
        result = op.execute(ctx)
        assert len(result) == 0

    def test_isolated_vertex(self) -> None:
        g = GraphStore()
        g.add_vertex(Vertex(1, "person", {"score": 0.5}))
        ctx = ExecutionContext(graph_store=g)
        op = MessagePassingOperator(k_layers=1, property_name="score")
        result = op.execute(ctx)
        assert len(result) == 1

    def test_k_layers_effect(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op1 = MessagePassingOperator(k_layers=1, property_name="score")
        op2 = MessagePassingOperator(k_layers=3, property_name="score")
        r1 = op1.execute(ctx)
        r2 = op2.execute(ctx)
        # More layers should produce different scores
        scores1 = {e.doc_id: e.payload.score for e in r1}
        scores2 = {e.doc_id: e.payload.score for e in r2}
        assert scores1 != scores2

    def test_cost_estimate(self) -> None:
        from uqa.core.types import IndexStats

        op = MessagePassingOperator(k_layers=3)
        stats = IndexStats(total_docs=100)
        assert op.cost_estimate(stats) == pytest.approx(300.0)


class TestGraphEmbeddingOperator:
    """Tests for GraphEmbeddingOperator."""

    def test_basic_execution(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = GraphEmbeddingOperator(dimensions=16, k_layers=2)
        result = op.execute(ctx)
        assert len(result) == 4

    def test_embedding_dimensions(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = GraphEmbeddingOperator(dimensions=8, k_layers=1)
        result = op.execute(ctx)
        for entry in result:
            emb = entry.payload.fields.get("_embedding")
            assert emb is not None
            assert len(emb) == 8

    def test_embedding_normalized(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = GraphEmbeddingOperator(dimensions=16)
        result = op.execute(ctx)
        for entry in result:
            emb = entry.payload.fields["_embedding"]
            norm = math.sqrt(sum(x * x for x in emb))
            if norm > 0:
                assert abs(norm - 1.0) < 1e-6

    def test_different_vertices_different_embeddings(self) -> None:
        g = _build_test_graph()
        ctx = ExecutionContext(graph_store=g)
        op = GraphEmbeddingOperator(dimensions=16)
        result = op.execute(ctx)
        embeddings = {e.doc_id: e.payload.fields["_embedding"] for e in result}
        # At least some vertices should have different embeddings
        assert embeddings[1] != embeddings[4]

    def test_empty_graph(self) -> None:
        g = GraphStore()
        ctx = ExecutionContext(graph_store=g)
        op = GraphEmbeddingOperator()
        result = op.execute(ctx)
        assert len(result) == 0

    def test_cost_estimate(self) -> None:
        from uqa.core.types import IndexStats

        op = GraphEmbeddingOperator(dimensions=32, k_layers=2)
        stats = IndexStats(total_docs=100)
        assert op.cost_estimate(stats) == pytest.approx(400.0)


class TestGNNSQL:
    """Tests for message_passing and graph_embedding via SQL."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE g (id SERIAL PRIMARY KEY, name TEXT)")
        g = e._tables["g"].graph_store
        g.add_vertex(Vertex(1, "person", {"score": 0.8}))
        g.add_vertex(Vertex(2, "person", {"score": 0.6}))
        g.add_edge(Edge(1, 1, 2, "knows"))
        return e

    def test_message_passing_sql(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM g WHERE message_passing(2, 'mean', 'score')")
        assert result is not None

    def test_graph_embedding_sql(self, engine: Engine) -> None:
        result = engine.sql("SELECT * FROM g WHERE graph_embedding(16, 2)")
        assert result is not None


class TestGNNQueryBuilder:
    """Tests for QueryBuilder message_passing method."""

    @pytest.fixture
    def engine(self) -> Engine:
        e = Engine()
        e.sql("CREATE TABLE g (id SERIAL PRIMARY KEY, name TEXT)")
        g = e._tables["g"].graph_store
        g.add_vertex(Vertex(1, "person", {"score": 0.8}))
        g.add_vertex(Vertex(2, "person", {"score": 0.6}))
        g.add_edge(Edge(1, 1, 2, "knows"))
        return e

    def test_query_builder_message_passing(self, engine: Engine) -> None:
        result = (
            engine.query("g")
            .message_passing(k_layers=2, property_name="score")
            .execute()
        )
        assert len(result) > 0
