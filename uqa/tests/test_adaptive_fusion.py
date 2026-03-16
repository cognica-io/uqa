#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.fusion.log_odds import AdaptiveLogOddsFusion, LogOddsFusion, SignalQuality
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.hybrid import AdaptiveLogOddsFusionOperator

# -- Helper --


class _ConstantOperator(Operator):
    """Returns a fixed PostingList regardless of context."""

    def __init__(self, pl: PostingList) -> None:
        self._pl = pl

    def execute(self, context: ExecutionContext) -> PostingList:
        return self._pl


# -- SignalQuality tests --


def test_signal_quality_creation() -> None:
    sq = SignalQuality(coverage_ratio=0.8, score_variance=0.05, calibration_error=0.1)
    assert sq.coverage_ratio == 0.8
    assert sq.score_variance == 0.05
    assert sq.calibration_error == 0.1


# -- compute_signal_alpha tests --


def test_compute_signal_alpha_high_quality() -> None:
    """High coverage, low variance, low calibration error -> high alpha."""
    fusion = AdaptiveLogOddsFusion(base_alpha=0.5)
    sq = SignalQuality(coverage_ratio=1.0, score_variance=0.0, calibration_error=0.0)
    alpha = fusion.compute_signal_alpha(sq)
    # alpha = 0.5 * (1.0 * 1.0) / 1.0 = 0.5
    assert alpha == pytest.approx(0.5, abs=1e-9)


def test_compute_signal_alpha_low_quality() -> None:
    """Low coverage, high variance, high calibration error -> low alpha."""
    fusion = AdaptiveLogOddsFusion(base_alpha=0.5)
    sq = SignalQuality(coverage_ratio=0.1, score_variance=5.0, calibration_error=0.4)
    alpha = fusion.compute_signal_alpha(sq)
    # alpha = 0.5 * (0.1 * 0.6) / 6.0 = 0.5 * 0.06 / 6.0 = 0.005 -> clamped to 0.01
    assert alpha == pytest.approx(0.01, abs=1e-9)


def test_compute_signal_alpha_clamping() -> None:
    """Verify alpha is clamped to [0.01, 1.0]."""
    fusion = AdaptiveLogOddsFusion(base_alpha=0.5)

    # Near-zero coverage should clamp to 0.01
    sq_low = SignalQuality(
        coverage_ratio=0.0, score_variance=0.0, calibration_error=0.0
    )
    alpha_low = fusion.compute_signal_alpha(sq_low)
    assert alpha_low == pytest.approx(0.01, abs=1e-9)

    # Very high base_alpha with perfect quality should clamp to 1.0
    fusion_high = AdaptiveLogOddsFusion(base_alpha=5.0)
    sq_high = SignalQuality(
        coverage_ratio=1.0, score_variance=0.0, calibration_error=0.0
    )
    alpha_high = fusion_high.compute_signal_alpha(sq_high)
    assert alpha_high == pytest.approx(1.0, abs=1e-9)


# -- fuse_adaptive tests --


def test_adaptive_fuse_single_signal() -> None:
    """Single signal returns original probability."""
    fusion = AdaptiveLogOddsFusion(base_alpha=0.5)
    sq = SignalQuality(coverage_ratio=1.0, score_variance=0.0, calibration_error=0.0)
    result = fusion.fuse_adaptive([0.8], [sq])
    assert result == pytest.approx(0.8, abs=1e-9)


def test_adaptive_fuse_uniform_quality() -> None:
    """All signals same quality -> similar to standard fusion."""
    adaptive = AdaptiveLogOddsFusion(base_alpha=0.5)
    standard = LogOddsFusion(confidence_alpha=0.5)

    probs = [0.7, 0.8, 0.6]
    sq = SignalQuality(coverage_ratio=1.0, score_variance=0.0, calibration_error=0.0)
    qualities = [sq, sq, sq]

    adaptive_result = adaptive.fuse_adaptive(probs, qualities)
    standard_result = standard.fuse(probs)

    # Both should produce results on the same side of 0.5
    assert adaptive_result > 0.5
    assert standard_result > 0.5


def test_adaptive_fuse_mixed_quality() -> None:
    """High quality signal dominates over low quality."""
    fusion = AdaptiveLogOddsFusion(base_alpha=0.5)

    high_q = SignalQuality(
        coverage_ratio=1.0, score_variance=0.0, calibration_error=0.0
    )
    low_q = SignalQuality(coverage_ratio=0.1, score_variance=5.0, calibration_error=0.4)

    # High-quality signal says relevant (0.9), low-quality says irrelevant (0.1)
    result_high_first = fusion.fuse_adaptive([0.9, 0.1], [high_q, low_q])
    # Swap: low-quality says relevant (0.9), high-quality says irrelevant (0.1)
    result_low_first = fusion.fuse_adaptive([0.1, 0.9], [high_q, low_q])

    # When high-quality signal says relevant, the result should be higher
    assert result_high_first > result_low_first


# -- AdaptiveLogOddsFusionOperator tests --


def test_adaptive_operator_basic() -> None:
    """Operator fuses two signals with adaptive weights."""
    pl1 = PostingList.from_sorted(
        [
            PostingEntry(1, Payload(score=0.8)),
            PostingEntry(2, Payload(score=0.7)),
            PostingEntry(3, Payload(score=0.6)),
        ]
    )
    pl2 = PostingList.from_sorted(
        [
            PostingEntry(1, Payload(score=0.9)),
            PostingEntry(2, Payload(score=0.3)),
        ]
    )

    op = AdaptiveLogOddsFusionOperator(
        signals=[_ConstantOperator(pl1), _ConstantOperator(pl2)],
        base_alpha=0.5,
    )
    ctx = ExecutionContext()
    result = op.execute(ctx)

    assert len(result) == 3
    doc_ids = [e.doc_id for e in result]
    assert doc_ids == [1, 2, 3]

    # All fused scores should be in (0, 1)
    for entry in result:
        assert 0.0 < entry.payload.score < 1.0


def test_adaptive_operator_empty() -> None:
    """No signals -> empty PostingList."""
    op = AdaptiveLogOddsFusionOperator(signals=[], base_alpha=0.5)
    ctx = ExecutionContext()
    result = op.execute(ctx)
    assert len(result) == 0


def test_adaptive_operator_cost_estimate() -> None:
    """Cost estimate is the sum of signal costs."""
    pl1 = PostingList.from_sorted([PostingEntry(1, Payload(score=0.5))])
    pl2 = PostingList.from_sorted([PostingEntry(2, Payload(score=0.5))])

    op = AdaptiveLogOddsFusionOperator(
        signals=[_ConstantOperator(pl1), _ConstantOperator(pl2)],
    )
    stats = IndexStats(total_docs=100)
    # Each _ConstantOperator inherits from Operator, whose default cost = total_docs
    assert op.cost_estimate(stats) == 200.0
