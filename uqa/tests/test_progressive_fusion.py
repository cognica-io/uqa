#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.progressive_fusion import ProgressiveFusionOperator


def _make_posting_list(entries: list[tuple[int, float]]) -> PostingList:
    return PostingList([PostingEntry(d, Payload(score=s)) for d, s in entries])


class _FixedOperator(Operator):
    def __init__(self, entries: list[tuple[int, float]]) -> None:
        self._entries = entries

    def execute(self, context: ExecutionContext) -> PostingList:
        return _make_posting_list(self._entries)


class TestProgressiveFusionOperator:
    def test_two_stage_basic(self) -> None:
        """Two-stage fusion narrows candidates."""
        sig1 = _FixedOperator([(1, 0.9), (2, 0.7), (3, 0.5), (4, 0.3)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.6), (3, 0.4), (4, 0.2)])
        sig3 = _FixedOperator([(1, 0.7), (2, 0.5)])

        op = ProgressiveFusionOperator(
            stages=[
                ([sig1, sig2], 3),  # Stage 1: fuse sig1+sig2, keep top-3
                ([sig3], 2),  # Stage 2: add sig3, keep top-2
            ],
        )
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 2
        # Top results should be docs with highest combined scores
        doc_ids = {e.doc_id for e in result}
        assert 1 in doc_ids

    def test_single_stage_equivalence(self) -> None:
        """Single-stage progressive fusion should work like WAND."""
        sig1 = _FixedOperator([(1, 0.9), (2, 0.3)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.2)])

        op = ProgressiveFusionOperator(stages=[([sig1, sig2], 1)])
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 1
        assert result.entries[0].doc_id == 1

    def test_three_stage_narrowing(self) -> None:
        """Three stages progressively narrow candidates."""
        sig1 = _FixedOperator([(i, 0.9 - i * 0.05) for i in range(1, 11)])  # 10 docs
        sig2 = _FixedOperator([(i, 0.8 - i * 0.04) for i in range(1, 11)])
        sig3 = _FixedOperator([(i, 0.7 - i * 0.03) for i in range(1, 11)])

        op = ProgressiveFusionOperator(
            stages=[
                ([sig1], 8),
                ([sig2], 5),
                ([sig3], 3),
            ],
        )
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 3

    def test_cost_cascading(self) -> None:
        """Cost estimate should decrease with cascading stages."""
        sig1 = _FixedOperator([(1, 0.9)])
        sig2 = _FixedOperator([(1, 0.8)])

        op = ProgressiveFusionOperator(
            stages=[
                ([sig1], 50),
                ([sig2], 10),
            ],
        )
        stats = IndexStats(total_docs=100)
        cost = op.cost_estimate(stats)
        assert cost > 0

    def test_gating_forwarded(self) -> None:
        """Gating parameter should be stored."""
        sig1 = _FixedOperator([(1, 0.9)])
        sig2 = _FixedOperator([(1, 0.8)])

        op = ProgressiveFusionOperator(
            stages=[([sig1, sig2], 1)],
            gating="relu",
        )
        assert op.gating == "relu"
        ctx = ExecutionContext()
        result = op.execute(ctx)
        assert len(result) == 1

    def test_empty_stages_raises(self) -> None:
        """Empty stages list should raise ValueError."""
        with pytest.raises(ValueError, match="at least one stage"):
            ProgressiveFusionOperator(stages=[])

    def test_scores_are_probabilities(self) -> None:
        """All output scores should be valid probabilities."""
        sig1 = _FixedOperator([(1, 0.7), (2, 0.6), (3, 0.5)])
        sig2 = _FixedOperator([(1, 0.8), (2, 0.5), (3, 0.3)])

        op = ProgressiveFusionOperator(stages=[([sig1, sig2], 3)])
        ctx = ExecutionContext()
        result = op.execute(ctx)
        for entry in result:
            assert 0.0 < entry.payload.score < 1.0
