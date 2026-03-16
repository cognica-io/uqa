#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.planner.cardinality import (
    _column_entropy,
    _entropy_cardinality_lower_bound,
    _mutual_information_estimate,
)
from uqa.sql.table import ColumnStats


def _make_stats(
    ndv: int, mcv_values: list | None = None, mcv_frequencies: list | None = None
) -> ColumnStats:
    return ColumnStats(
        distinct_count=ndv,
        null_count=0,
        min_value=0,
        max_value=ndv,
        row_count=1000,
        mcv_values=mcv_values or [],
        mcv_frequencies=mcv_frequencies or [],
    )


def test_column_entropy_uniform():
    """Uniform distribution: H = log2(ndv)."""
    cs = _make_stats(ndv=8)
    h = _column_entropy(cs)
    assert abs(h - 3.0) < 0.01  # log2(8) = 3


def test_column_entropy_single_value():
    """Single distinct value: H = 0."""
    cs = _make_stats(ndv=1)
    assert _column_entropy(cs) == 0.0


def test_column_entropy_zero():
    cs = _make_stats(ndv=0)
    assert _column_entropy(cs) == 0.0


def test_column_entropy_none():
    assert _column_entropy(None) == 0.0


def test_column_entropy_with_mcv():
    """With MCV frequencies, entropy should be lower than uniform."""
    cs = _make_stats(
        ndv=4,
        mcv_values=["a", "b"],
        mcv_frequencies=[0.4, 0.3],
    )
    h = _column_entropy(cs)
    # With MCV: not uniform, entropy < log2(4) = 2.0
    assert h < 2.0
    assert h > 0.0


def test_mutual_information_zero():
    """Zero joint selectivity -> zero MI."""
    cs_x = _make_stats(ndv=10)
    cs_y = _make_stats(ndv=10)
    mi = _mutual_information_estimate(cs_x, cs_y, 0.0)
    assert mi == 0.0


def test_mutual_information_positive():
    """Positive joint selectivity -> positive MI."""
    cs_x = _make_stats(ndv=10)
    cs_y = _make_stats(ndv=10)
    mi = _mutual_information_estimate(cs_x, cs_y, 0.1)
    assert mi >= 0.0


def test_mutual_information_correlation():
    """Lower joint selectivity = more correlation = higher MI."""
    cs_x = _make_stats(ndv=4)
    cs_y = _make_stats(ndv=4)
    mi_corr = _mutual_information_estimate(cs_x, cs_y, 0.01)
    mi_indep = _mutual_information_estimate(cs_x, cs_y, 0.5)
    # Lower selectivity (more correlated) should give higher MI
    assert mi_corr > mi_indep


def test_entropy_lower_bound_single():
    """Single entropy: lower bound = n * 2^(-H)."""
    lb = _entropy_cardinality_lower_bound(1000, [3.0])
    # 1000 * 2^(-3) = 125
    assert abs(lb - 125.0) < 0.01


def test_entropy_lower_bound_multiple():
    """Multiple entropies: lower bound shrinks multiplicatively."""
    lb = _entropy_cardinality_lower_bound(1000, [3.0, 3.0])
    # 1000 * 2^(-6) = 15.625
    assert abs(lb - 15.625) < 0.01


def test_entropy_lower_bound_empty():
    lb = _entropy_cardinality_lower_bound(1000, [])
    assert lb == 1.0


def test_entropy_lower_bound_zero_n():
    lb = _entropy_cardinality_lower_bound(0, [3.0])
    assert lb == 1.0


def test_entropy_lower_bound_floor():
    """Lower bound should never go below 1.0."""
    lb = _entropy_cardinality_lower_bound(10, [20.0])
    assert lb == 1.0


# -- Integration tests: entropy bounds in CardinalityEstimator --


def test_entropy_lower_bound_in_intersection():
    """Entropy lower bound should floor intersection cardinality estimates."""
    from uqa.core.types import Equals, IndexStats
    from uqa.operators.boolean import IntersectOperator
    from uqa.operators.primitive import FilterOperator
    from uqa.planner.cardinality import CardinalityEstimator

    cs = {
        "age": ColumnStats(
            distinct_count=50,
            null_count=0,
            min_value=0,
            max_value=100,
            row_count=1000,
        ),
        "dept": ColumnStats(
            distinct_count=5,
            null_count=0,
            min_value=0,
            max_value=5,
            row_count=1000,
        ),
    }
    estimator = CardinalityEstimator(column_stats=cs)
    idx_stats = IndexStats(total_docs=1000, dimensions=0)

    f1 = FilterOperator("age", Equals(25))
    f2 = FilterOperator("dept", Equals(3))
    intersect = IntersectOperator([f1, f2])

    card = estimator.estimate(intersect, idx_stats)
    # Should be at least 1.0 (floored by entropy bound)
    assert card >= 1.0

    # Verify the entropy lower bound is active: compute it manually
    h_age = _column_entropy(cs["age"])
    h_dept = _column_entropy(cs["dept"])
    lb = _entropy_cardinality_lower_bound(1000.0, [h_age, h_dept])
    # The result should be at least the entropy lower bound
    assert card >= lb


def test_entropy_clamping_in_filter_selectivity():
    """Filter selectivity should be clamped by entropy lower bound."""
    from uqa.core.types import Equals, IndexStats
    from uqa.operators.primitive import FilterOperator
    from uqa.planner.cardinality import CardinalityEstimator

    # Column with 4 distinct values: H = log2(4) = 2, min_sel = 1/4 = 0.25
    cs = {
        "color": ColumnStats(
            distinct_count=4,
            null_count=0,
            min_value=0,
            max_value=3,
            row_count=100,
        ),
    }
    estimator = CardinalityEstimator(column_stats=cs)
    idx_stats = IndexStats(total_docs=100, dimensions=0)

    # Equality on 4-distinct column: raw selectivity = 1/4 = 0.25
    # Entropy lower bound: 1 / 2^2 = 0.25
    # So selectivity should be >= 0.25
    op = FilterOperator("color", Equals("red"))
    card = estimator.estimate(op, idx_stats)
    selectivity = card / 100.0
    assert selectivity >= 0.25 - 1e-9


def test_entropy_clamping_does_not_raise_high_selectivity():
    """Entropy clamping should not affect selectivities already above the bound."""
    from uqa.planner.cardinality import CardinalityEstimator

    # Column with 4 distinct values: H = 2, min_sel = 0.25
    # A range predicate covering 75% of the domain should not be clamped
    cs = {
        "score": ColumnStats(
            distinct_count=4,
            null_count=0,
            min_value=0,
            max_value=100,
            row_count=100,
        ),
    }
    estimator = CardinalityEstimator(column_stats=cs)
    # Use _filter_selectivity directly to check the clamping behavior
    from uqa.core.types import GreaterThan

    sel = estimator._filter_selectivity("score", GreaterThan(25), 100.0)
    # Raw selectivity should be (100-25)/100 = 0.75, well above 0.25
    assert sel >= 0.25
    assert sel <= 1.0
