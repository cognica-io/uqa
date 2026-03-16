#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for cost-based optimizer: histograms, MCVs, selectivity estimation."""

from __future__ import annotations

import pytest

from uqa.engine import Engine
from uqa.planner.cardinality import CardinalityEstimator
from uqa.sql.table import ColumnStats

# ==================================================================
# Histogram construction
# ==================================================================


class TestHistogram:
    def test_histogram_basic(self):
        from uqa.sql.table import Table

        boundaries = Table._build_histogram([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert boundaries[0] == 1
        assert boundaries[-1] == 10
        assert len(boundaries) >= 2

    def test_histogram_empty(self):
        from uqa.sql.table import Table

        assert Table._build_histogram([]) == []

    def test_histogram_single_value(self):
        from uqa.sql.table import Table

        boundaries = Table._build_histogram([42])
        assert boundaries == [42, 42]

    def test_histogram_duplicates(self):
        from uqa.sql.table import Table

        boundaries = Table._build_histogram([1, 1, 1, 1, 2, 2, 3])
        assert boundaries[0] == 1
        assert boundaries[-1] == 3

    def test_histogram_strings(self):
        from uqa.sql.table import Table

        boundaries = Table._build_histogram(["a", "b", "c", "d", "e"])
        assert boundaries[0] == "a"
        assert boundaries[-1] == "e"


# ==================================================================
# MCV construction
# ==================================================================


class TestMCV:
    def test_mcv_skewed(self):
        from uqa.sql.table import Table

        # 'x' appears 50 times, 'y' appears 5 times, 45 others once each
        values = ["x"] * 50 + ["y"] * 5 + [f"z{i}" for i in range(45)]
        total = len(values)
        mcv_values, mcv_frequencies = Table._build_mcv(values, total)
        assert "x" in mcv_values
        assert mcv_frequencies[mcv_values.index("x")] == 50 / total

    def test_mcv_uniform(self):
        from uqa.sql.table import Table

        # All values appear once -- no MCV above average
        values = list(range(100))
        mcv_values, mcv_frequencies = Table._build_mcv(values, 100)
        assert mcv_values == []
        assert mcv_frequencies == []

    def test_mcv_empty(self):
        from uqa.sql.table import Table

        mcv_values, _mcv_frequencies = Table._build_mcv([], 0)
        assert mcv_values == []


# ==================================================================
# ANALYZE integration
# ==================================================================


class TestAnalyzeHistogramMCV:
    def test_analyze_creates_histogram(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        for i in range(1, 101):
            e.sql(f"INSERT INTO t (id, val) VALUES ({i}, {i})")
        e.sql("ANALYZE t")

        stats = e._tables["t"]._stats["val"]
        assert len(stats.histogram) >= 2
        assert stats.histogram[0] == 1
        assert stats.histogram[-1] == 100

    def test_analyze_creates_mcv(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, cat TEXT)")
        # Insert skewed data: 'A' appears 50 times, 'B' 30, 'C' 20
        for i in range(1, 101):
            if i <= 50:
                cat = "A"
            elif i <= 80:
                cat = "B"
            else:
                cat = "C"
            e.sql(f"INSERT INTO t (id, cat) VALUES ({i}, '{cat}')")
        e.sql("ANALYZE t")

        stats = e._tables["t"]._stats["cat"]
        assert "A" in stats.mcv_values
        idx_a = stats.mcv_values.index("A")
        assert abs(stats.mcv_frequencies[idx_a] - 0.5) < 0.01


# ==================================================================
# Selectivity estimation with histograms/MCVs
# ==================================================================


class TestSelectivityEstimation:
    @pytest.fixture
    def estimator_with_stats(self):
        """Estimator with histogram and MCV stats."""
        cs = ColumnStats(
            distinct_count=100,
            null_count=0,
            min_value=1,
            max_value=1000,
            row_count=1000,
            histogram=[1, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
            mcv_values=[42, 100],
            mcv_frequencies=[0.15, 0.10],
        )
        return CardinalityEstimator({"val": cs})

    def test_equality_mcv_hit(self, estimator_with_stats):
        """MCV value returns exact frequency."""
        from uqa.core.types import Equals, IndexStats

        stats = IndexStats(total_docs=1000)
        from uqa.operators.primitive import FilterOperator

        op = FilterOperator("val", Equals(42))
        card = estimator_with_stats.estimate(op, stats)
        assert abs(card - 150) < 1  # 0.15 * 1000

    def test_equality_mcv_miss(self, estimator_with_stats):
        """Non-MCV value uses 1/NDV, clamped by entropy lower bound."""
        from uqa.core.types import Equals, IndexStats
        from uqa.operators.primitive import FilterOperator

        stats = IndexStats(total_docs=1000)
        op = FilterOperator("val", Equals(999))
        card = estimator_with_stats.estimate(op, stats)
        # Base selectivity is 1/100 = 0.01 -> card = 10.
        # The entropy-based lower bound (1/2^H) raises the minimum
        # selectivity when column entropy is moderate, so the card
        # is >= 10 but bounded well below the full table.
        assert 10 <= card < 50

    def test_range_histogram(self, estimator_with_stats):
        """Range predicate uses histogram buckets."""
        from uqa.core.types import Between, IndexStats
        from uqa.operators.primitive import FilterOperator

        stats = IndexStats(total_docs=1000)
        # BETWEEN 200 AND 500 covers ~3 out of 10 buckets
        op = FilterOperator("val", Between(200, 500))
        card = estimator_with_stats.estimate(op, stats)
        # Should be roughly 300, give or take bucket boundaries
        assert 200 < card < 500

    def test_gt_histogram(self, estimator_with_stats):
        """Greater-than uses histogram."""
        from uqa.core.types import GreaterThan, IndexStats
        from uqa.operators.primitive import FilterOperator

        stats = IndexStats(total_docs=1000)
        op = FilterOperator("val", GreaterThan(500))
        card = estimator_with_stats.estimate(op, stats)
        # > 500 should cover roughly half the range
        assert 300 < card < 700

    def test_lt_histogram(self, estimator_with_stats):
        """Less-than uses histogram."""
        from uqa.core.types import IndexStats, LessThan
        from uqa.operators.primitive import FilterOperator

        stats = IndexStats(total_docs=1000)
        op = FilterOperator("val", LessThan(200))
        card = estimator_with_stats.estimate(op, stats)
        # < 200 should cover roughly 2 out of 10 buckets
        assert 100 < card < 400

    def test_no_stats_fallback(self):
        """Without stats, selectivity defaults to 0.5."""
        from uqa.core.types import Equals, IndexStats
        from uqa.operators.primitive import FilterOperator

        est = CardinalityEstimator()
        stats = IndexStats(total_docs=1000)
        op = FilterOperator("x", Equals(42))
        card = est.estimate(op, stats)
        assert card == 500  # 0.5 * 1000


# ==================================================================
# End-to-end optimizer with ANALYZE
# ==================================================================


class TestOptimizerEndToEnd:
    def test_analyze_improves_explain(self):
        """EXPLAIN after ANALYZE should show estimated cost."""
        e = Engine()
        e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        for i in range(1, 51):
            e.sql(f"INSERT INTO t (id, val) VALUES ({i}, {i})")
        e.sql("ANALYZE t")
        r = e.sql("EXPLAIN SELECT val FROM t WHERE val > 25")
        plan_text = " ".join(row["plan"] for row in r.rows)
        assert "cost" in plan_text.lower()

    def test_histogram_persists(self, tmp_path):
        """Histogram data survives engine restart."""
        db = str(tmp_path / "test.db")

        with Engine(db_path=db) as e:
            e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
            for i in range(1, 101):
                e.sql(f"INSERT INTO t (id, val) VALUES ({i}, {i})")
            e.sql("ANALYZE t")
            original_hist = e._tables["t"]._stats["val"].histogram

        with Engine(db_path=db) as e:
            restored_hist = e._tables["t"]._stats["val"].histogram
            assert restored_hist == original_hist

    def test_mcv_persists(self, tmp_path):
        """MCV data survives engine restart."""
        db = str(tmp_path / "test.db")

        with Engine(db_path=db) as e:
            e.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, cat TEXT)")
            for i in range(1, 101):
                cat = "A" if i <= 60 else "B"
                e.sql(f"INSERT INTO t (id, cat) VALUES ({i}, '{cat}')")
            e.sql("ANALYZE t")
            original_mcv = e._tables["t"]._stats["cat"].mcv_values

        with Engine(db_path=db) as e:
            restored_mcv = e._tables["t"]._stats["cat"].mcv_values
            assert restored_mcv == original_mcv
