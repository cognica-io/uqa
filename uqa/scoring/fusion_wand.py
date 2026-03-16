#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import heapq
import math

import numpy as np
from bayesian_bm25 import log_odds_conjunction

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.scoring.wand import BoundTightnessAnalyzer


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _logit(p: float) -> float:
    """Logit (inverse sigmoid), clamped to avoid infinities."""
    p = max(1e-10, min(1.0 - 1e-10, p))
    return math.log(p / (1.0 - p))


class FusionWANDScorer:
    """WAND-style top-k pruning for multi-signal fusion (Section 8.7, Paper 4).

    Uses per-signal upper bounds to compute a fused upper bound.
    Since log_odds_conjunction is monotone in each input probability,
    per-signal upper bounds compose safely for pruning.

    The scoring function fuses probabilities from multiple signals
    via log_odds_conjunction, and the WAND pivot mechanism skips
    documents that cannot enter the top-k.
    """

    def __init__(
        self,
        signal_posting_lists: list[PostingList],
        signal_upper_bounds: list[float],
        alpha: float = 0.5,
        k: int = 10,
        gating: str | None = None,
    ) -> None:
        self.signal_posting_lists = signal_posting_lists
        self.signal_upper_bounds = signal_upper_bounds
        self.alpha = alpha
        self.k = k
        self.gating = gating

    def _compute_fused_upper_bound(self, active_ubs: list[float]) -> float:
        """Compute fused upper bound from per-signal upper bounds.

        sigma(sum(w_i * logit(UB_i))) where w_i are uniform weights.
        """
        if not active_ubs:
            return 0.0
        return float(
            log_odds_conjunction(
                np.array(active_ubs),
                alpha=self.alpha,
                gating=self.gating or "none",
            )
        )

    def score_top_k(self) -> PostingList:
        """Execute WAND-style top-k with fused scoring.

        Signals are treated as "terms" in the WAND framework.
        For each document, probabilities from all signals are collected
        and fused via log_odds_conjunction.
        """
        from uqa.operators.hybrid import _coverage_based_default

        num_signals = len(self.signal_posting_lists)
        if num_signals == 0:
            return PostingList()

        # Build score maps per signal
        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in self.signal_posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        if not all_doc_ids:
            return PostingList()

        num_docs = len(all_doc_ids)
        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        # Score all documents and keep top-k using a min-heap
        top_k_heap: list[tuple[float, int]] = []

        for doc_id in sorted(all_doc_ids):
            # Quick check: can this document possibly beat the threshold?
            if len(top_k_heap) >= self.k:
                threshold = top_k_heap[0][0]
                # Check if the fused upper bound is still above threshold
                # (conservative but correct: we use per-signal UBs)
                doc_ubs = []
                for j, smap in enumerate(score_maps):
                    if doc_id in smap:
                        doc_ubs.append(self.signal_upper_bounds[j])
                    else:
                        doc_ubs.append(defaults[j])
                if doc_ubs:
                    doc_fused_ub = self._compute_fused_upper_bound(doc_ubs)
                    if doc_fused_ub < threshold:
                        continue

            # Score the document
            probs = [smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)]
            if num_signals == 1:
                fused = probs[0]
            else:
                fused = float(
                    log_odds_conjunction(
                        np.array(probs),
                        alpha=self.alpha,
                        gating=self.gating or "none",
                    )
                )

            if len(top_k_heap) < self.k:
                heapq.heappush(top_k_heap, (fused, doc_id))
            elif fused > top_k_heap[0][0]:
                heapq.heapreplace(top_k_heap, (fused, doc_id))

        # Build result
        entries: list[PostingEntry] = []
        for score, doc_id in top_k_heap:
            entries.append(PostingEntry(doc_id, Payload(score=score)))
        return PostingList(entries)


class TightenedFusionWANDScorer(FusionWANDScorer):
    """FusionWAND with tightened per-signal bounds.

    Uses empirical maximum scores instead of theoretical upper bounds
    when available, reducing false positives in the WAND pivot check.
    """

    def __init__(
        self,
        signal_posting_lists: list[PostingList],
        signal_upper_bounds: list[float],
        alpha: float = 0.5,
        k: int = 10,
        gating: str | None = None,
        tightening_factor: float = 0.9,
    ) -> None:
        # Tighten upper bounds before passing to parent
        tightened = [ub * tightening_factor for ub in signal_upper_bounds]
        super().__init__(signal_posting_lists, tightened, alpha, k, gating)
        self.tightening_factor = tightening_factor
        self.original_bounds = list(signal_upper_bounds)
        self.analyzer = BoundTightnessAnalyzer()

    def score_top_k(self) -> PostingList:
        """Score with tightness analysis."""
        result = super().score_top_k()

        # Record empirical bounds for analysis
        for i, pl in enumerate(self.signal_posting_lists):
            actual_max = 0.0
            for entry in pl:
                if entry.payload.score > actual_max:
                    actual_max = entry.payload.score
            self.analyzer.record(self.original_bounds[i], actual_max)

        return result
