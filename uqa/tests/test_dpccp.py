#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for DPccp join order optimization."""

from __future__ import annotations

import pytest

from uqa.planner.join_enumerator import DPccp
from uqa.planner.join_graph import JoinGraph

# ── JoinGraph unit tests ─────────────────────────────────────────────


class TestJoinGraph:
    def test_add_node(self) -> None:
        g = JoinGraph()
        idx = g.add_node("t1", None, None, 100.0)
        assert idx == 0
        assert len(g) == 1
        assert g.nodes[0].alias == "t1"
        assert g.nodes[0].cardinality == 100.0

    def test_add_edge(self) -> None:
        g = JoinGraph()
        g.add_node("a", None, None, 100.0)
        g.add_node("b", None, None, 200.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)
        assert len(g.edges) == 1
        assert g.neighbors(0) == [1]
        assert g.neighbors(1) == [0]

    def test_edges_between(self) -> None:
        g = JoinGraph()
        g.add_node("a", None, None, 100.0)
        g.add_node("b", None, None, 200.0)
        g.add_node("c", None, None, 300.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)
        g.add_edge(1, 2, "id", "b_id", 0.005)

        edges_ab = g.edges_between(frozenset({0}), frozenset({1}))
        assert len(edges_ab) == 1

        edges_ac = g.edges_between(frozenset({0}), frozenset({2}))
        assert len(edges_ac) == 0

        edges_bc = g.edges_between(frozenset({1}), frozenset({2}))
        assert len(edges_bc) == 1

    def test_estimate_selectivity_with_stats(self) -> None:
        from uqa.sql.table import ColumnStats

        g = JoinGraph()
        stats_a = {"id": ColumnStats(distinct_count=100)}
        stats_b = {"a_id": ColumnStats(distinct_count=50)}
        g.add_node("a", None, None, 100.0, stats_a)
        g.add_node("b", None, None, 200.0, stats_b)

        sel = g.estimate_join_selectivity(0, 1, "id", "a_id")
        assert sel == pytest.approx(1.0 / 100)

    def test_estimate_selectivity_no_stats(self) -> None:
        g = JoinGraph()
        g.add_node("a", None, None, 100.0)
        g.add_node("b", None, None, 200.0)

        sel = g.estimate_join_selectivity(0, 1, "id", "a_id")
        assert sel == pytest.approx(0.01)


# ── DPccp unit tests ─────────────────────────────────────────────────


class _FakeOp:
    """Minimal operator stub for testing."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"FakeOp({self.name})"


class TestDPccp:
    def test_single_relation(self) -> None:
        g = JoinGraph()
        g.add_node("t1", _FakeOp("t1"), None, 100.0)
        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0})
        assert plan.cardinality == 100.0

    def test_two_relations(self) -> None:
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 100.0)
        g.add_node("b", _FakeOp("b"), None, 200.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)

        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0, 1})
        assert plan.left is not None
        assert plan.right is not None
        # Cardinality: 100 * 200 * 0.01 = 200
        assert plan.cardinality == pytest.approx(200.0)

    def test_three_relations_chain(self) -> None:
        """A -- B -- C chain: DPccp should find optimal order."""
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 1000.0)
        g.add_node("b", _FakeOp("b"), None, 10.0)
        g.add_node("c", _FakeOp("c"), None, 500.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)  # a-b
        g.add_edge(1, 2, "id", "b_id", 0.01)  # b-c

        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0, 1, 2})
        # DPccp should prefer joining small tables first.
        # Cost model: C_total = (|L| + |R|) + C_left + C_right
        # Base cost = cardinality.
        #
        # (B JOIN C) JOIN A:
        #   B JOIN C: card=10*500*0.01=50, cost=(10+500)+10+500 = 1020
        #   then JOIN A: card=50*1000*0.01=500, cost=(50+1000)+1020+1000 = 3070
        #
        # (B JOIN A) JOIN C:
        #   B JOIN A: card=10*1000*0.01=100, cost=(10+1000)+10+1000 = 2020
        #   then JOIN C: card=100*500*0.01=500, cost=(100+500)+2020+500 = 3120
        #
        # Best is (B JOIN C) JOIN A with cost 3070
        assert plan.cost == pytest.approx(3070.0)

    def test_four_relations_star(self) -> None:
        """Star join: A at center connected to B, C, D."""
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 100.0)
        g.add_node("b", _FakeOp("b"), None, 1000.0)
        g.add_node("c", _FakeOp("c"), None, 500.0)
        g.add_node("d", _FakeOp("d"), None, 200.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)
        g.add_edge(0, 2, "id", "a_id", 0.01)
        g.add_edge(0, 3, "id", "a_id", 0.01)

        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0, 1, 2, 3})

    def test_disconnected_graph(self) -> None:
        """Disconnected components should be cross-joined."""
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 100.0)
        g.add_node("b", _FakeOp("b"), None, 200.0)
        g.add_node("c", _FakeOp("c"), None, 50.0)
        g.add_node("d", _FakeOp("d"), None, 300.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)
        g.add_edge(2, 3, "id", "c_id", 0.01)

        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0, 1, 2, 3})

    def test_plan_materialization_preserves_structure(self) -> None:
        """Ensure JoinPlan tree has correct left/right children."""
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 100.0)
        g.add_node("b", _FakeOp("b"), None, 100.0)
        g.add_edge(0, 1, "id", "a_id", 0.01)

        plan = DPccp(g).optimize()
        assert plan.left is not None
        assert plan.right is not None
        child_rels = plan.left.relations | plan.right.relations
        assert child_rels == frozenset({0, 1})

    def test_bushy_tree_possible(self) -> None:
        """4-way join can produce bushy tree: (A*B) JOIN (C*D)."""
        g = JoinGraph()
        g.add_node("a", _FakeOp("a"), None, 100.0)
        g.add_node("b", _FakeOp("b"), None, 100.0)
        g.add_node("c", _FakeOp("c"), None, 100.0)
        g.add_node("d", _FakeOp("d"), None, 100.0)
        g.add_edge(0, 1, "id", "a_id", 0.1)
        g.add_edge(1, 2, "id", "b_id", 0.1)
        g.add_edge(2, 3, "id", "c_id", 0.1)
        g.add_edge(0, 3, "id2", "a_id2", 0.1)

        plan = DPccp(g).optimize()
        assert plan.relations == frozenset({0, 1, 2, 3})

    def test_empty_graph_raises(self) -> None:
        g = JoinGraph()
        with pytest.raises(ValueError, match="no relations"):
            DPccp(g).optimize()


# ── JoinOrderOptimizer unit tests ────────────────────────────────────


class TestJoinOrderOptimizer:
    def test_three_way_join_produces_operator(self) -> None:
        from uqa.joins.index import IndexJoinOperator
        from uqa.joins.inner import InnerJoinOperator
        from uqa.planner.join_order import JoinOrderOptimizer

        relations = [
            {
                "alias": "a",
                "operator": _FakeOp("a"),
                "table": None,
                "cardinality": 1000.0,
                "column_stats": {},
            },
            {
                "alias": "b",
                "operator": _FakeOp("b"),
                "table": None,
                "cardinality": 10.0,
                "column_stats": {},
            },
            {
                "alias": "c",
                "operator": _FakeOp("c"),
                "table": None,
                "cardinality": 500.0,
                "column_stats": {},
            },
        ]
        predicates = [
            {
                "left_alias": "a",
                "right_alias": "b",
                "left_field": "id",
                "right_field": "a_id",
            },
            {
                "left_alias": "b",
                "right_alias": "c",
                "left_field": "id",
                "right_field": "b_id",
            },
        ]

        optimizer = JoinOrderOptimizer()
        operator, table = optimizer.optimize(relations, predicates)
        # Optimizer chooses IndexJoin or InnerJoin based on cardinality
        assert isinstance(operator, (InnerJoinOperator, IndexJoinOperator))
        assert table is None


# ── SQL integration tests ────────────────────────────────────────────


class TestDPccpSQLIntegration:
    def _make_engine(self):
        from uqa.engine import Engine

        engine = Engine()

        # Create tables with varying sizes to make join order matter
        engine.sql("CREATE TABLE departments (id INT PRIMARY KEY, name TEXT)")
        engine.sql(
            "CREATE TABLE employees (id INT PRIMARY KEY, name TEXT, dept_id INT)"
        )
        engine.sql(
            "CREATE TABLE projects (id INT PRIMARY KEY, title TEXT, lead_id INT)"
        )
        engine.sql(
            "CREATE TABLE assignments (id INT PRIMARY KEY, emp_id INT, proj_id INT)"
        )

        # Populate with different cardinalities
        for i in range(1, 4):
            engine.sql(f"INSERT INTO departments (id, name) VALUES ({i}, 'dept_{i}')")
        for i in range(1, 21):
            engine.sql(
                f"INSERT INTO employees (id, name, dept_id) "
                f"VALUES ({i}, 'emp_{i}', {(i % 3) + 1})"
            )
        for i in range(1, 6):
            engine.sql(
                f"INSERT INTO projects (id, title, lead_id) "
                f"VALUES ({i}, 'proj_{i}', {i})"
            )
        for i in range(1, 31):
            engine.sql(
                f"INSERT INTO assignments (id, emp_id, proj_id) "
                f"VALUES ({i}, {(i % 20) + 1}, {(i % 5) + 1})"
            )
        return engine

    def test_three_way_inner_join(self) -> None:
        engine = self._make_engine()
        result = engine.sql(
            "SELECT e.name, d.name AS dept "
            "FROM employees e "
            "INNER JOIN departments d ON e.dept_id = d.id "
            "INNER JOIN projects p ON p.lead_id = e.id "
            "ORDER BY e.name"
        )
        assert len(result.rows) > 0
        # All rows should have both employee and department names
        for row in result.rows:
            assert row["name"] is not None
            assert row["dept"] is not None

    def test_four_way_inner_join(self) -> None:
        engine = self._make_engine()
        result = engine.sql(
            "SELECT e.name AS emp, d.name AS dept, p.title AS project "
            "FROM employees e "
            "INNER JOIN departments d ON e.dept_id = d.id "
            "INNER JOIN assignments a ON a.emp_id = e.id "
            "INNER JOIN projects p ON a.proj_id = p.id "
            "ORDER BY e.name"
        )
        assert len(result.rows) > 0
        for row in result.rows:
            assert row["emp"] is not None
            assert row["dept"] is not None
            assert row["project"] is not None

    def test_two_way_join_unchanged(self) -> None:
        """Two-way joins should still work (DPccp not triggered)."""
        engine = self._make_engine()
        result = engine.sql(
            "SELECT e.name, d.name AS dept "
            "FROM employees e "
            "INNER JOIN departments d ON e.dept_id = d.id "
            "ORDER BY e.name"
        )
        assert len(result.rows) == 20

    def test_outer_join_not_reordered(self) -> None:
        """LEFT JOINs should not be reordered by DPccp."""
        engine = self._make_engine()
        result = engine.sql(
            "SELECT e.name, d.name AS dept, p.title "
            "FROM employees e "
            "LEFT JOIN departments d ON e.dept_id = d.id "
            "LEFT JOIN projects p ON p.lead_id = e.id "
            "ORDER BY e.name"
        )
        # All 20 employees should appear (LEFT JOIN preserves all)
        assert len(result.rows) == 20

    def test_mixed_inner_outer_not_reordered(self) -> None:
        """Mix of INNER and LEFT JOIN should not trigger DPccp."""
        engine = self._make_engine()
        result = engine.sql(
            "SELECT e.name, d.name AS dept, p.title "
            "FROM employees e "
            "INNER JOIN departments d ON e.dept_id = d.id "
            "LEFT JOIN projects p ON p.lead_id = e.id "
            "ORDER BY e.name"
        )
        assert len(result.rows) == 20

    def test_three_way_join_result_correctness(self) -> None:
        """Verify result correctness regardless of join order."""
        engine = self._make_engine()

        # 3-way join
        result = engine.sql(
            "SELECT e.name, d.name AS dept, a.id AS assign_id "
            "FROM departments d "
            "INNER JOIN employees e ON e.dept_id = d.id "
            "INNER JOIN assignments a ON a.emp_id = e.id "
            "ORDER BY a.id"
        )

        # Cross-check with sequential 2-way joins
        result2 = engine.sql(
            "SELECT e.name, d.name AS dept, a.id AS assign_id "
            "FROM departments d "
            "INNER JOIN employees e ON e.dept_id = d.id "
            "ORDER BY e.name"
        )
        emp_dept = {row["name"]: row["dept"] for row in result2.rows}

        for row in result.rows:
            assert row["name"] in emp_dept
            assert row["dept"] == emp_dept[row["name"]]
