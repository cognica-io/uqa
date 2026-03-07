#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.primitive import TermOperator, VectorSimilarityOperator

if TYPE_CHECKING:
    from numpy.typing import NDArray


class HybridTextVectorOperator(Operator):
    """Definition 3.3.1: Hybrid_{t,q,theta} = T(t) AND V_theta(q)."""

    def __init__(
        self,
        term: str,
        query_vector: NDArray,
        threshold: float,
    ) -> None:
        self.term_op = TermOperator(term)
        self.vector_op = VectorSimilarityOperator(query_vector, threshold)

    def execute(self, context: ExecutionContext) -> PostingList:
        return self.term_op.execute(context).intersect(
            self.vector_op.execute(context)
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        return min(
            self.term_op.cost_estimate(stats),
            self.vector_op.cost_estimate(stats),
        )


class SemanticFilterOperator(Operator):
    """Definition 3.3.4: SemanticFilter_{q,theta,L} = L AND V_theta(q)."""

    def __init__(
        self,
        source: Operator,
        query_vector: NDArray,
        threshold: float,
    ) -> None:
        self.source = source
        self.vector_op = VectorSimilarityOperator(query_vector, threshold)

    def execute(self, context: ExecutionContext) -> PostingList:
        return self.source.execute(context).intersect(
            self.vector_op.execute(context)
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        return min(
            self.source.cost_estimate(stats),
            self.vector_op.cost_estimate(stats),
        )


class LogOddsFusionOperator(Operator):
    """Multi-signal fusion via log-odds conjunction (Paper 4, Section 4).

    Combines multiple operator signals into a single calibrated probability
    score per document using LogOddsFusion.

    All signal operators MUST produce calibrated probabilities in (0, 1):
    - bayesian_match: Bayesian BM25 -> P(relevant) in [0, 1]
    - knn_match: cosine similarity -> P_vector = (1 + sim) / 2
    - traverse_match: graph reachability -> 0.9 (reachable)

    Documents missing from a signal receive default_prob (no evidence).
    """

    def __init__(
        self,
        signals: list[Operator],
        alpha: float = 0.5,
        default_prob: float = 0.01,
    ) -> None:
        self.signals = signals
        self.alpha = alpha
        self.default_prob = default_prob

    def execute(self, context: ExecutionContext) -> PostingList:
        from uqa.fusion.log_odds import LogOddsFusion

        par = context.parallel_executor
        if par is not None and par.enabled:
            posting_lists = par.execute_branches(self.signals, context)
        else:
            posting_lists = [sig.execute(context) for sig in self.signals]

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        fusion = LogOddsFusion(confidence_alpha=self.alpha)
        entries: list[PostingEntry] = []
        for doc_id in sorted(all_doc_ids):
            probs = [
                smap.get(doc_id, self.default_prob) for smap in score_maps
            ]
            fused = fusion.fuse(probs)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(sig.cost_estimate(stats) for sig in self.signals)


class ProbBoolFusionOperator(Operator):
    """Probabilistic boolean fusion (Paper 3, Section 5).

    Combines signals using probabilistic AND or OR.
    All signal operators MUST produce calibrated probabilities in (0, 1).
    """

    def __init__(
        self,
        signals: list[Operator],
        mode: str = "and",
        default_prob: float = 0.01,
    ) -> None:
        self.signals = signals
        self.mode = mode
        self.default_prob = default_prob

    def execute(self, context: ExecutionContext) -> PostingList:
        from uqa.fusion.boolean import ProbabilisticBoolean

        par = context.parallel_executor
        if par is not None and par.enabled:
            posting_lists = par.execute_branches(self.signals, context)
        else:
            posting_lists = [sig.execute(context) for sig in self.signals]

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        fuse_fn = (
            ProbabilisticBoolean.prob_and
            if self.mode == "and"
            else ProbabilisticBoolean.prob_or
        )
        entries: list[PostingEntry] = []
        for doc_id in sorted(all_doc_ids):
            probs = [
                smap.get(doc_id, self.default_prob) for smap in score_maps
            ]
            fused = fuse_fn(probs)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(sig.cost_estimate(stats) for sig in self.signals)


class ProbNotOperator(Operator):
    """Probabilistic NOT (Paper 3, Section 5): P(NOT signal) = 1 - P(signal).

    Inverts the calibrated probability of a single signal.
    Documents present in the signal get score = 1 - original_score.
    Documents absent (from full document set) get score = 1 - default_prob.
    """

    def __init__(
        self,
        signal: Operator,
        default_prob: float = 0.01,
    ) -> None:
        self.signal = signal
        self.default_prob = default_prob

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.signal.execute(context)

        score_map: dict[int, float] = {}
        for entry in source_pl:
            score_map[entry.doc_id] = entry.payload.score

        all_ids: set[int] = set(score_map.keys())
        if context.document_store is not None:
            all_ids.update(context.document_store.doc_ids)

        entries: list[PostingEntry] = []
        for doc_id in sorted(all_ids):
            p = score_map.get(doc_id, self.default_prob)
            entries.append(PostingEntry(doc_id, Payload(score=1.0 - p)))

        return PostingList(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.signal.cost_estimate(stats)
