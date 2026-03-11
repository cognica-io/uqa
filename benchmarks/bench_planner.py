#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for the query planner.

Covers DPccp join enumeration, greedy fallback, histogram construction,
and cardinality estimation.
"""

from __future__ import annotations

import pytest

from uqa.planner.join_graph import JoinGraph
from uqa.planner.join_enumerator import DPccp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_chain_graph(n: int) -> JoinGraph:
    """Build a chain join graph: R0 - R1 - R2 - ... - R(n-1)."""
    g = JoinGraph()
    for i in range(n):
        g.add_node(
            alias=f"r{i}",
            operator=None,
            table=None,
            cardinality=1000.0,
        )
    for i in range(n - 1):
        g.add_edge(i, i + 1, f"c{i}", f"c{i}", selectivity=0.01)
    return g


def _build_star_graph(n: int) -> JoinGraph:
    """Build a star join graph: R0 is the center, connected to R1..R(n-1)."""
    g = JoinGraph()
    for i in range(n):
        g.add_node(
            alias=f"r{i}",
            operator=None,
            table=None,
            cardinality=1000.0 if i == 0 else 100.0,
        )
    for i in range(1, n):
        g.add_edge(0, i, "center_id", f"fk{i}", selectivity=0.01)
    return g


def _build_clique_graph(n: int) -> JoinGraph:
    """Build a fully connected (clique) join graph."""
    g = JoinGraph()
    for i in range(n):
        g.add_node(
            alias=f"r{i}",
            operator=None,
            table=None,
            cardinality=100.0,
        )
    for i in range(n):
        for j in range(i + 1, n):
            g.add_edge(i, j, f"c{i}", f"c{j}", selectivity=0.1)
    return g


def _build_cycle_graph(n: int) -> JoinGraph:
    """Build a cycle join graph: R0 - R1 - ... - R(n-1) - R0."""
    g = JoinGraph()
    for i in range(n):
        g.add_node(
            alias=f"r{i}",
            operator=None,
            table=None,
            cardinality=500.0,
        )
    for i in range(n):
        g.add_edge(i, (i + 1) % n, f"c{i}", f"c{(i+1)%n}", selectivity=0.02)
    return g


# ---------------------------------------------------------------------------
# DPccp with varying relation counts
# ---------------------------------------------------------------------------

class TestDPccp:
    @pytest.mark.parametrize("n", [3, 5, 8, 10])
    def test_chain(self, benchmark, n: int) -> None:
        g = _build_chain_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))

    @pytest.mark.parametrize("n", [3, 5, 8, 10, 16])
    def test_star(self, benchmark, n: int) -> None:
        g = _build_star_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))

    @pytest.mark.parametrize("n", [3, 5, 8])
    def test_clique(self, benchmark, n: int) -> None:
        g = _build_clique_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))

    @pytest.mark.parametrize("n", [3, 5, 8, 10])
    def test_cycle(self, benchmark, n: int) -> None:
        g = _build_cycle_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))


# ---------------------------------------------------------------------------
# DPccp topology comparison at fixed size
# ---------------------------------------------------------------------------

class TestDPccpTopology:
    def test_chain_8(self, benchmark) -> None:
        g = _build_chain_graph(8)
        dp = DPccp(g)
        benchmark(dp.optimize)

    def test_star_8(self, benchmark) -> None:
        g = _build_star_graph(8)
        dp = DPccp(g)
        benchmark(dp.optimize)

    def test_clique_8(self, benchmark) -> None:
        g = _build_clique_graph(8)
        dp = DPccp(g)
        benchmark(dp.optimize)

    def test_cycle_8(self, benchmark) -> None:
        g = _build_cycle_graph(8)
        dp = DPccp(g)
        benchmark(dp.optimize)


# ---------------------------------------------------------------------------
# Greedy fallback for large queries
# ---------------------------------------------------------------------------

class TestGreedyFallback:
    @pytest.mark.parametrize("n", [16, 20, 30])
    def test_greedy_chain(self, benchmark, n: int) -> None:
        g = _build_chain_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))

    @pytest.mark.parametrize("n", [20, 30])
    def test_greedy_star(self, benchmark, n: int) -> None:
        g = _build_star_graph(n)
        dp = DPccp(g)
        plan = benchmark(dp.optimize)
        assert plan.relations == frozenset(range(n))


# ---------------------------------------------------------------------------
# Histogram and cardinality estimation
# ---------------------------------------------------------------------------

class TestHistogram:
    def test_analyze(self, benchmark) -> None:
        """Benchmark ANALYZE (histogram + MCV construction)."""
        from uqa.engine import Engine
        from benchmarks.data.generators import BenchmarkDataGenerator
        from benchmarks.data.schemas import BENCH_TABLE_DDL

        e = Engine()
        e.sql(BENCH_TABLE_DDL)
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        for row in rows:
            active_str = "TRUE" if row["active"] else "FALSE"
            e.sql(
                f"INSERT INTO bench VALUES ("
                f"{row['id']}, '{row['name']}', {row['value']}, "
                f"'{row['category']}', {row['quantity']}, {active_str})"
            )

        benchmark(e.sql, "ANALYZE bench")


class TestSelectivity:
    def test_equality_selectivity(self, benchmark) -> None:
        """Benchmark selectivity estimation for equality predicates."""
        from uqa.engine import Engine
        from benchmarks.data.generators import BenchmarkDataGenerator
        from benchmarks.data.schemas import BENCH_TABLE_DDL

        e = Engine()
        e.sql(BENCH_TABLE_DDL)
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        for row in rows:
            active_str = "TRUE" if row["active"] else "FALSE"
            e.sql(
                f"INSERT INTO bench VALUES ("
                f"{row['id']}, '{row['name']}', {row['value']}, "
                f"'{row['category']}', {row['quantity']}, {active_str})"
            )
        e.sql("ANALYZE bench")

        benchmark(e.sql, "SELECT * FROM bench WHERE category = 'cat_5'")

    def test_range_selectivity(self, benchmark) -> None:
        """Benchmark selectivity estimation for range predicates."""
        from uqa.engine import Engine
        from benchmarks.data.generators import BenchmarkDataGenerator
        from benchmarks.data.schemas import BENCH_TABLE_DDL

        e = Engine()
        e.sql(BENCH_TABLE_DDL)
        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        rows = gen.table_rows(num_rows=1000)
        for row in rows:
            active_str = "TRUE" if row["active"] else "FALSE"
            e.sql(
                f"INSERT INTO bench VALUES ("
                f"{row['id']}, '{row['name']}', {row['value']}, "
                f"'{row['category']}', {row['quantity']}, {active_str})"
            )
        e.sql("ANALYZE bench")

        benchmark(e.sql, "SELECT * FROM bench WHERE value BETWEEN 100 AND 500")
