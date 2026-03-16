#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.scoring.fusion_wand import TightenedFusionWANDScorer
from uqa.scoring.wand import AdaptiveWANDScorer, BoundTightnessAnalyzer


def _make_posting_list(entries: list[tuple[int, float]]) -> PostingList:
    return PostingList([PostingEntry(d, Payload(score=s)) for d, s in entries])


class _MockScorer:
    def __init__(self, score: float) -> None:
        self._score = score

    def score(self, tf: int, doc_length: int, df: int) -> float:
        return self._score

    def upper_bound(self, df: int) -> float:
        return self._score * 2.0  # Deliberately loose bound


# -- BoundTightnessAnalyzer tests --


def test_bound_tightness_analyzer_empty() -> None:
    analyzer = BoundTightnessAnalyzer()
    assert analyzer.tightness_ratio() == 1.0


def test_bound_tightness_analyzer_perfect() -> None:
    analyzer = BoundTightnessAnalyzer()
    analyzer.record(5.0, 5.0)
    analyzer.record(3.0, 3.0)
    assert analyzer.tightness_ratio() == pytest.approx(1.0)


def test_bound_tightness_analyzer_loose() -> None:
    analyzer = BoundTightnessAnalyzer()
    # upper_bound=10, actual_max=5 -> ratio=0.5
    analyzer.record(10.0, 5.0)
    assert analyzer.tightness_ratio() == pytest.approx(0.5)


def test_bound_tightness_slack() -> None:
    analyzer = BoundTightnessAnalyzer()
    analyzer.record(10.0, 5.0)  # ratio=0.5, slack=0.5
    assert analyzer.slack() == pytest.approx(0.5)

    analyzer.clear()
    analyzer.record(4.0, 4.0)  # ratio=1.0, slack=0.0
    assert analyzer.slack() == pytest.approx(0.0)


def test_bound_tightness_worst_index() -> None:
    analyzer = BoundTightnessAnalyzer()
    analyzer.record(10.0, 9.0)  # ratio=0.9
    analyzer.record(10.0, 2.0)  # ratio=0.2 (worst)
    analyzer.record(10.0, 7.0)  # ratio=0.7
    assert analyzer.worst_bound_index() == 1


def test_bound_tightness_worst_index_empty() -> None:
    analyzer = BoundTightnessAnalyzer()
    assert analyzer.worst_bound_index() == 0


def test_bound_tightness_zero_upper_bound() -> None:
    analyzer = BoundTightnessAnalyzer()
    analyzer.record(0.0, 0.0)  # ub=0 -> ratio defaults to 1.0
    assert analyzer.tightness_ratio() == pytest.approx(1.0)


def test_bound_tightness_clear() -> None:
    analyzer = BoundTightnessAnalyzer()
    analyzer.record(10.0, 5.0)
    assert analyzer.tightness_ratio() == pytest.approx(0.5)
    analyzer.clear()
    assert analyzer.tightness_ratio() == pytest.approx(1.0)


# -- AdaptiveWANDScorer tests --


def test_adaptive_wand_tightening() -> None:
    scorer1 = _MockScorer(1.0)
    scorer2 = _MockScorer(2.0)
    pl1 = _make_posting_list([(1, 0.8), (2, 0.6)])
    pl2 = _make_posting_list([(1, 0.9), (3, 0.5)])

    adaptive = AdaptiveWANDScorer(
        scorers=[scorer1, scorer2],
        k=2,
        posting_lists=[pl1, pl2],
        tightening_factor=0.8,
    )

    # _compute_upper_bounds should apply tightening factor
    bounds = adaptive._compute_upper_bounds()
    # scorer1.upper_bound(2) = 2.0, * 0.8 = 1.6
    # scorer2.upper_bound(2) = 4.0, * 0.8 = 3.2
    assert bounds[0] == pytest.approx(1.6)
    assert bounds[1] == pytest.approx(3.2)


def test_adaptive_wand_produces_results() -> None:
    scorer1 = _MockScorer(1.0)
    scorer2 = _MockScorer(0.5)
    pl1 = _make_posting_list([(1, 0.9), (2, 0.7), (3, 0.5)])
    pl2 = _make_posting_list([(1, 0.8), (2, 0.6), (4, 0.3)])

    adaptive = AdaptiveWANDScorer(
        scorers=[scorer1, scorer2],
        k=2,
        posting_lists=[pl1, pl2],
        tightening_factor=0.9,
    )
    result = adaptive.score_top_k()
    # Should produce results (at most k=2)
    assert len(result) <= 2
    assert len(result) > 0


def test_adaptive_wand_analyzer_populated() -> None:
    scorer1 = _MockScorer(1.0)
    pl1 = _make_posting_list([(1, 0.5), (2, 0.8)])

    adaptive = AdaptiveWANDScorer(
        scorers=[scorer1],
        k=2,
        posting_lists=[pl1],
        tightening_factor=0.9,
    )
    adaptive.score_top_k()

    # Analyzer should have recorded one observation per posting list
    assert adaptive.analyzer.tightness_ratio() < 1.0
    # upper_bound = 2.0 (from MockScorer), actual_max = 0.8
    # ratio = 0.8 / 2.0 = 0.4
    assert adaptive.analyzer.tightness_ratio() == pytest.approx(0.4)


# -- TightenedFusionWANDScorer tests --


def test_tightened_fusion_wand() -> None:
    pl1 = _make_posting_list([(1, 0.9), (2, 0.7), (3, 0.5)])
    pl2 = _make_posting_list([(1, 0.8), (2, 0.6), (4, 0.4)])

    scorer = TightenedFusionWANDScorer(
        signal_posting_lists=[pl1, pl2],
        signal_upper_bounds=[0.95, 0.85],
        k=2,
        tightening_factor=0.9,
    )
    result = scorer.score_top_k()
    assert len(result) <= 2
    assert len(result) > 0


def test_tightened_fusion_analyzer() -> None:
    pl1 = _make_posting_list([(1, 0.9), (2, 0.7)])
    pl2 = _make_posting_list([(1, 0.8), (3, 0.4)])

    scorer = TightenedFusionWANDScorer(
        signal_posting_lists=[pl1, pl2],
        signal_upper_bounds=[1.0, 1.0],
        k=2,
        tightening_factor=0.85,
    )
    scorer.score_top_k()

    # Analyzer should be populated after scoring
    assert scorer.analyzer.tightness_ratio() < 1.0
    # original_bounds=[1.0, 1.0], actual_max for pl1=0.9, pl2=0.8
    # ratios: 0.9/1.0=0.9, 0.8/1.0=0.8 -> avg=0.85
    assert scorer.analyzer.tightness_ratio() == pytest.approx(0.85)


def test_tightened_fusion_preserves_original_bounds() -> None:
    pl1 = _make_posting_list([(1, 0.9)])
    scorer = TightenedFusionWANDScorer(
        signal_posting_lists=[pl1],
        signal_upper_bounds=[1.0],
        k=1,
        tightening_factor=0.8,
    )
    # original_bounds should be untouched
    assert scorer.original_bounds == [1.0]
    # But signal_upper_bounds should be tightened
    assert scorer.signal_upper_bounds == [pytest.approx(0.8)]
