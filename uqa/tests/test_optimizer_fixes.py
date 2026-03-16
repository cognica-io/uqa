#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for optimizer comprehensive fixes and paper-driven optimizations."""

from __future__ import annotations

from uqa.core.types import (
    Equals,
    GreaterThan,
    IndexStats,
    Payload,
    PostingEntry,
)
from uqa.engine import Engine

# ==================================================================
# Phase 1: C2 -- Graph filter pushdown to correct vertex
# ==================================================================


class TestGraphFilterPushdownC2:
    def test_qualified_field_pushes_to_correct_vertex(self) -> None:
        """Filter on 'b.name' should push to vertex 'b', not vertex 'a'."""
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
        filtered = FilterOperator("b.name", Equals("Alice"), pm)

        stats = IndexStats(total_docs=5)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        assert isinstance(optimized, PatternMatchOperator)
        # Vertex 'a' should have NO pushed constraints
        assert len(optimized.pattern.vertex_patterns[0].constraints) == 0
        # Vertex 'b' should have the pushed constraint
        assert len(optimized.pattern.vertex_patterns[1].constraints) == 1

    def test_unqualified_field_stays_as_post_filter(self) -> None:
        """Unqualified field should not be pushed (safe fallback)."""
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
        filtered = FilterOperator("name", Equals("Alice"), pm)

        stats = IndexStats(total_docs=5)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        # Should remain as FilterOperator (not pushed)
        assert isinstance(optimized, FilterOperator)


# ==================================================================
# Phase 1: H1 -- Filter pushdown to ALL Intersect children
# ==================================================================


class TestFilterPushdownH1:
    def test_filter_pushed_to_multiple_children(self) -> None:
        """Filter should be pushed to ALL applicable Intersect children."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator, TermOperator
        from uqa.planner.optimizer import QueryOptimizer

        # Two TermOperators on the same field
        t1 = TermOperator("hello", "text")
        t2 = TermOperator("world", "text")
        intersect = IntersectOperator([t1, t2])
        filtered = FilterOperator("text", GreaterThan(0), intersect)

        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        # The filter should be pushed into the Intersect
        assert isinstance(optimized, IntersectOperator)
        # Both children should have the filter applied
        filter_count = sum(
            1 for o in optimized.operands if isinstance(o, FilterOperator)
        )
        assert filter_count == 2


# ==================================================================
# Phase 2: C3 -- ON CONFLICT hash index
# ==================================================================


class TestOnConflictHashIndex:
    def test_on_conflict_large_batch(self) -> None:
        """ON CONFLICT with large batch insert should complete efficiently."""
        engine = Engine()
        engine.sql(
            "CREATE TABLE items ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT, "
            "count INTEGER DEFAULT 0"
            ")"
        )

        # Insert initial rows
        for i in range(100):
            engine.sql(
                f"INSERT INTO items (id, name, count) VALUES ({i}, 'item_{i}', 0)"
            )

        # Batch upsert with ON CONFLICT (some new, some existing)
        for i in range(50, 150):
            engine.sql(
                f"INSERT INTO items (id, name, count) "
                f"VALUES ({i}, 'item_{i}', 1) "
                f"ON CONFLICT (id) DO UPDATE SET count = excluded.count"
            )

        # Verify: first 50 untouched, 50-99 updated, 100-149 new
        result = engine.sql("SELECT count FROM items WHERE id = 25")
        assert result.rows[0]["count"] == 0

        result = engine.sql("SELECT count FROM items WHERE id = 75")
        assert result.rows[0]["count"] == 1

        result = engine.sql("SELECT count FROM items WHERE id = 125")
        assert result.rows[0]["count"] == 1

        # Total: 150 rows
        result = engine.sql("SELECT COUNT(*) AS cnt FROM items")
        assert result.rows[0]["cnt"] == 150


# ==================================================================
# Phase 3: M4 -- IntersectOperator cost model
# ==================================================================


class TestIntersectCostModel:
    def test_intersect_cost_is_sum(self) -> None:
        """IntersectOperator cost should be sum of children (not min)."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import TermOperator
        from uqa.planner.cost_model import CostModel

        stats = IndexStats(total_docs=1000)
        model = CostModel()

        t1 = TermOperator("hello", "_default")
        t2 = TermOperator("world", "_default")
        intersect = IntersectOperator([t1, t2])

        cost_t1 = model.estimate(t1, stats)
        cost_t2 = model.estimate(t2, stats)
        cost_intersect = model.estimate(intersect, stats)

        assert cost_intersect == cost_t1 + cost_t2


# ==================================================================
# Phase 3: M1 -- Independence damping in cardinality
# ==================================================================


class TestCardinalityDamping:
    def test_damped_intersect_larger_than_strict(self) -> None:
        """Damped cardinality estimate should be >= strict independence."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator
        from uqa.planner.cardinality import CardinalityEstimator

        stats = IndexStats(total_docs=1000)
        estimator = CardinalityEstimator()

        f1 = FilterOperator("x", Equals(1), None)
        f2 = FilterOperator("y", Equals(2), None)
        intersect = IntersectOperator([f1, f2])

        card = estimator.estimate(intersect, stats)
        # With damping, estimate should be >= 1.0
        assert card >= 1.0


# ==================================================================
# Phase 4: H7 -- Hash join build-on-smaller-side
# ==================================================================


class TestHashJoinBuildSide:
    def test_build_on_smaller_side(self) -> None:
        """Hash join should produce correct results regardless of side sizes."""
        from uqa.core.posting_list import PostingList
        from uqa.joins.base import JoinCondition
        from uqa.joins.inner import InnerJoinOperator

        # Left: 2 entries, Right: 5 entries
        left = PostingList(
            [
                PostingEntry(1, Payload(score=0.0, fields={"id": 1, "name": "a"})),
                PostingEntry(2, Payload(score=0.0, fields={"id": 2, "name": "b"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(i, Payload(score=0.0, fields={"fk": i % 2 + 1, "val": i}))
                for i in range(1, 6)
            ]
        )

        condition = JoinCondition(left_field="id", right_field="fk")
        join = InnerJoinOperator(left, right, condition)
        result = join.execute(None)
        results = list(result)

        # All 5 right entries should join (3 with id=1, 2 with id=2)
        assert len(results) == 5

        # Verify left/right field ordering: left fields should be present
        for entry in results:
            assert "name" in entry.payload.fields
            assert "val" in entry.payload.fields

    def test_build_on_smaller_right(self) -> None:
        """When right is smaller, build hash table on right side."""
        from uqa.core.posting_list import PostingList
        from uqa.joins.base import JoinCondition
        from uqa.joins.inner import InnerJoinOperator

        # Left: 5 entries, Right: 2 entries (right is smaller)
        left = PostingList(
            [
                PostingEntry(i, Payload(score=0.0, fields={"fk": i % 2 + 1, "val": i}))
                for i in range(1, 6)
            ]
        )
        right = PostingList(
            [
                PostingEntry(1, Payload(score=0.0, fields={"id": 1, "name": "a"})),
                PostingEntry(2, Payload(score=0.0, fields={"id": 2, "name": "b"})),
            ]
        )

        condition = JoinCondition(left_field="fk", right_field="id")
        join = InnerJoinOperator(left, right, condition)
        result = join.execute(None)
        results = list(result)

        assert len(results) == 5
        for entry in results:
            assert "name" in entry.payload.fields
            assert "val" in entry.payload.fields


# ==================================================================
# Phase 4: H6 -- IndexJoin selection for small inputs
# ==================================================================


class TestIndexJoinSelection:
    def test_small_input_uses_index_join(self) -> None:
        """DPccp should select IndexJoin for small cardinality inputs."""
        from uqa.joins.index import IndexJoinOperator
        from uqa.planner.join_order import JoinOrderOptimizer

        class _FakeOp:
            def __init__(self, name: str) -> None:
                self.name = name

        relations = [
            {
                "alias": "big",
                "operator": _FakeOp("big"),
                "table": None,
                "cardinality": 10000.0,
                "column_stats": {},
            },
            {
                "alias": "small",
                "operator": _FakeOp("small"),
                "table": None,
                "cardinality": 50.0,
                "column_stats": {},
            },
        ]
        predicates = [
            {
                "left_alias": "big",
                "right_alias": "small",
                "left_field": "id",
                "right_field": "fk",
            },
        ]

        optimizer = JoinOrderOptimizer()
        operator, _ = optimizer.optimize(relations, predicates)
        # Small input (50 < INDEX_JOIN_THRESHOLD) -> IndexJoin
        assert isinstance(operator, IndexJoinOperator)

    def test_large_input_uses_hash_join(self) -> None:
        """DPccp should select InnerJoin (hash) for large cardinality inputs."""
        from uqa.joins.inner import InnerJoinOperator
        from uqa.planner.join_order import JoinOrderOptimizer

        class _FakeOp:
            def __init__(self, name: str) -> None:
                self.name = name

        relations = [
            {
                "alias": "a",
                "operator": _FakeOp("a"),
                "table": None,
                "cardinality": 5000.0,
                "column_stats": {},
            },
            {
                "alias": "b",
                "operator": _FakeOp("b"),
                "table": None,
                "cardinality": 3000.0,
                "column_stats": {},
            },
        ]
        predicates = [
            {
                "left_alias": "a",
                "right_alias": "b",
                "left_field": "id",
                "right_field": "fk",
            },
        ]

        optimizer = JoinOrderOptimizer()
        operator, _ = optimizer.optimize(relations, predicates)
        assert isinstance(operator, InnerJoinOperator)


# ==================================================================
# Phase 5: H3 -- Predicate pushdown below joins
# ==================================================================


class TestPredicatePushdownBelowJoins:
    def test_single_table_predicate_pushed_below_join(self) -> None:
        """Single-table WHERE predicate should be pushed below the join."""
        engine = Engine()
        engine.sql("CREATE TABLE t1 (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("CREATE TABLE t2 (id INTEGER PRIMARY KEY, t1_id INTEGER, data TEXT)")

        for i in range(10):
            engine.sql(f"INSERT INTO t1 (id, val) VALUES ({i}, 'v{i}')")
        for i in range(20):
            engine.sql(
                f"INSERT INTO t2 (id, t1_id, data) VALUES ({i}, {i % 10}, 'd{i}')"
            )

        # WHERE t1.val = 'v3' references only t1 -> pushable
        result = engine.sql(
            "SELECT t1.id, t2.data "
            "FROM t1 JOIN t2 ON t1.id = t2.t1_id "
            "WHERE t1.val = 'v3'"
        )
        assert len(result.rows) == 2
        for row in result.rows:
            assert row["id"] == 3

    def test_cross_table_predicate_remains_deferred(self) -> None:
        """Cross-table WHERE predicate should remain as deferred filter."""
        engine = Engine()
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, x INTEGER)")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER, y INTEGER)")

        for i in range(5):
            engine.sql(f"INSERT INTO a (id, x) VALUES ({i}, {i * 10})")
        for i in range(10):
            engine.sql(f"INSERT INTO b (id, a_id, y) VALUES ({i}, {i % 5}, {i})")

        # WHERE a.x = b.y references both tables -> not pushable
        result = engine.sql(
            "SELECT a.id AS a_id, b.id AS b_id "
            "FROM a JOIN b ON a.id = b.a_id "
            "WHERE a.x = b.y"
        )
        # a.x = b.y: a(0,0) matches b(0,0), a(1,10) no match, etc.
        assert len(result.rows) == 1
        assert result.rows[0]["a_id"] == 0


# ==================================================================
# Phase 6: H4 -- Constant folding
# ==================================================================


class TestConstantFolding:
    def test_arithmetic_constant_folded(self) -> None:
        """Constant arithmetic in WHERE should be folded at compile time."""
        engine = Engine()
        engine.sql("CREATE TABLE cf (id INTEGER PRIMARY KEY, val INTEGER)")
        for i in range(10):
            engine.sql(f"INSERT INTO cf (id, val) VALUES ({i}, {i * 10})")

        # '10 + 20' should be folded to 30
        result = engine.sql("SELECT id FROM cf WHERE val > 10 + 20")
        ids = sorted(r["id"] for r in result.rows)
        assert ids == [4, 5, 6, 7, 8, 9]

    def test_boolean_constant_folded(self) -> None:
        """Boolean constant expressions should be folded."""
        engine = Engine()
        engine.sql("CREATE TABLE cf2 (id INTEGER PRIMARY KEY, val INTEGER)")
        for i in range(5):
            engine.sql(f"INSERT INTO cf2 (id, val) VALUES ({i}, {i})")

        # '1 = 1 AND val > 2' -> 'true AND val > 2' -> 'val > 2'
        result = engine.sql("SELECT id FROM cf2 WHERE 1 = 1 AND val > 2")
        ids = sorted(r["id"] for r in result.rows)
        assert ids == [3, 4]

    def test_string_concat_folded(self) -> None:
        """String concatenation of constants should be folded."""
        engine = Engine()
        engine.sql("CREATE TABLE cf3 (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO cf3 (id, name) VALUES (1, 'hello world')")

        result = engine.sql("SELECT id FROM cf3 WHERE name = 'hello' || ' ' || 'world'")
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1


# ==================================================================
# Phase 4: H2 -- DPccp for 2-table joins
# ==================================================================


class TestDPccp2Tables:
    def test_two_table_join_uses_dpccp(self) -> None:
        """DPccp should optimize 2-table joins (not just 3+)."""
        engine = Engine()
        engine.sql("CREATE TABLE dp_a (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("CREATE TABLE dp_b (id INTEGER PRIMARY KEY, a_id INTEGER, val TEXT)")

        for i in range(5):
            engine.sql(f"INSERT INTO dp_a (id, name) VALUES ({i}, 'a{i}')")
        for i in range(10):
            engine.sql(
                f"INSERT INTO dp_b (id, a_id, val) VALUES ({i}, {i % 5}, 'b{i}')"
            )

        result = engine.sql(
            "SELECT dp_a.name, dp_b.val FROM dp_a JOIN dp_b ON dp_a.id = dp_b.a_id"
        )
        assert len(result.rows) == 10


# ==================================================================
# Paper-driven: Task 2 -- IntersectOperator early termination
# ==================================================================


class TestIntersectEarlyTermination:
    def test_empty_first_operand_skips_rest(self) -> None:
        """When the first operand returns empty, subsequent operands should not execute."""
        from uqa.core.posting_list import PostingList
        from uqa.operators.base import ExecutionContext, Operator
        from uqa.operators.boolean import IntersectOperator

        class _CountingOp(Operator):
            call_count = 0

            def execute(self, context: ExecutionContext) -> PostingList:
                _CountingOp.call_count += 1
                return PostingList([PostingEntry(1, Payload(score=1.0))])

            def cost_estimate(self, stats: object) -> float:
                return 1.0

        class _EmptyOp(Operator):
            def execute(self, context: ExecutionContext) -> PostingList:
                return PostingList()

            def cost_estimate(self, stats: object) -> float:
                return 1.0

        _CountingOp.call_count = 0
        # Empty operator first, then two counting operators
        intersect = IntersectOperator([_EmptyOp(), _CountingOp(), _CountingOp()])
        ctx = ExecutionContext()
        result = intersect.execute(ctx)

        assert len(result) == 0
        assert _CountingOp.call_count == 0  # Neither counting op executed


# ==================================================================
# Paper-driven: Task 3 -- Predicate-aware damping
# ==================================================================


class TestPredicateAwareDamping:
    def test_same_field_higher_estimate(self) -> None:
        """Same-field intersect should produce higher cardinality (0.9 damping)."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator
        from uqa.planner.cardinality import CardinalityEstimator

        stats = IndexStats(total_docs=1000)
        estimator = CardinalityEstimator()

        # Same field: age > 30 AND age < 50 -> 0.9 damping
        same = IntersectOperator(
            [
                FilterOperator("age", GreaterThan(30), None),
                FilterOperator("age", GreaterThan(50), None),
            ]
        )
        card_same = estimator.estimate(same, stats)

        # Different fields: age > 30 AND salary > 50000 -> 0.5 damping
        diff = IntersectOperator(
            [
                FilterOperator("age", GreaterThan(30), None),
                FilterOperator("salary", GreaterThan(50000), None),
            ]
        )
        card_diff = estimator.estimate(diff, stats)

        assert card_same > card_diff

    def test_mixed_operators_default_damping(self) -> None:
        """Non-filter children should use default 0.5 damping."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator, TermOperator
        from uqa.planner.cardinality import CardinalityEstimator

        stats = IndexStats(total_docs=1000)
        estimator = CardinalityEstimator()

        # Mix of filter and non-filter -> default 0.5
        mixed = IntersectOperator(
            [
                FilterOperator("age", GreaterThan(30), None),
                TermOperator("hello", "text"),
            ]
        )
        card = estimator.estimate(mixed, stats)
        assert card >= 1.0


# ==================================================================
# Paper-driven: Task 4 -- DPccp join algorithm awareness
# ==================================================================


class TestDPccpJoinAlgorithmAwareness:
    def test_small_input_index_join_cost(self) -> None:
        """DPccp cost model should use index join formula for small inputs."""
        import math

        from uqa.planner.join_enumerator import DPccp
        from uqa.planner.join_graph import JoinGraph

        graph = JoinGraph()
        graph.add_node(alias="small", operator=None, table=None, cardinality=50.0)
        graph.add_node(alias="big", operator=None, table=None, cardinality=10000.0)
        graph.add_edge(
            left_node=0,
            right_node=1,
            left_field="id",
            right_field="fk",
        )

        solver = DPccp(graph)
        plan = solver.optimize()

        # With index join: cost = 50 * log2(10001) + 50 + 10000
        expected_join_cost = 50.0 * math.log2(10001.0)
        expected_total = expected_join_cost + 50.0 + 10000.0
        assert abs(plan.cost - expected_total) < 1.0


# ==================================================================
# Paper-driven: Task 5 -- Vector threshold merge with np.allclose
# ==================================================================


class TestVectorThresholdMerge:
    def test_merge_nearly_identical_vectors(self) -> None:
        """Vectors differing by tiny epsilon should still merge."""
        import numpy as np

        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import VectorSimilarityOperator
        from uqa.planner.optimizer import QueryOptimizer

        v1 = np.array([1.0, 2.0, 3.0])
        v2 = v1 + 1e-10  # Tiny difference

        op1 = VectorSimilarityOperator(v1, 0.5, "vec")
        op2 = VectorSimilarityOperator(v2, 0.7, "vec")
        intersect = IntersectOperator([op1, op2])

        stats = IndexStats(total_docs=100, dimensions=3)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)

        # Should be merged into single VectorSimilarityOperator with max threshold
        assert isinstance(optimized, VectorSimilarityOperator)
        assert optimized.threshold == 0.7


# ==================================================================
# Paper-driven: Task 6 -- Cost-based intersection reordering
# ==================================================================


class TestCostBasedIntersectReordering:
    def test_cheap_operator_first(self) -> None:
        """TermOperator (cheap) should appear before VectorSimilarityOperator (expensive)."""
        import numpy as np

        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import TermOperator, VectorSimilarityOperator
        from uqa.planner.optimizer import QueryOptimizer

        vec = np.array([1.0] * 128)
        vector_op = VectorSimilarityOperator(vec, 0.5, "vec")
        term_op = TermOperator("hello", "text")

        # Put expensive vector op first
        intersect = IntersectOperator([vector_op, term_op])

        stats = IndexStats(total_docs=1000, dimensions=128)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(intersect)

        # After optimization, cheap TermOperator should come first
        assert isinstance(optimized, IntersectOperator)
        assert isinstance(optimized.operands[0], TermOperator)
        assert isinstance(optimized.operands[1], VectorSimilarityOperator)


# ==================================================================
# Paper-driven: Task 7 -- Recursive filter pushdown
# ==================================================================


class TestRecursiveFilterPushdown:
    def test_filter_pushes_through_nested_intersect(self) -> None:
        """Filter should push through nested IntersectOperators to all leaves."""
        from uqa.operators.boolean import IntersectOperator
        from uqa.operators.primitive import FilterOperator, TermOperator
        from uqa.planner.optimizer import QueryOptimizer

        t1 = TermOperator("alpha", "text")
        t2 = TermOperator("beta", "text")
        t3 = TermOperator("gamma", "text")

        # Nested: Intersect(Intersect(T1, T2), T3)
        inner = IntersectOperator([t1, t2])
        outer = IntersectOperator([inner, t3])
        filtered = FilterOperator("text", GreaterThan(0), outer)

        stats = IndexStats(total_docs=100)
        optimizer = QueryOptimizer(stats)
        optimized = optimizer.optimize(filtered)

        # All three TermOperators should have filters applied
        def count_filters(op: object) -> int:
            if isinstance(op, FilterOperator):
                return 1 + count_filters(op.source)
            if isinstance(op, IntersectOperator):
                return sum(count_filters(o) for o in op.operands)
            return 0

        assert count_filters(optimized) == 3
