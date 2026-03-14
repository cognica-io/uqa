#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.primitive import TermOperator, VectorSimilarityOperator

if TYPE_CHECKING:
    from numpy.typing import NDArray


def _coverage_based_default(n_hits: int, n_total: int, *, floor: float = 0.01) -> float:
    """Compute default probability for missing entries based on signal coverage.

    Interpolates between neutral (0.5) and negative evidence (floor) based on
    how many documents the signal actually returned:

        default = 0.5 * (1 - r) + floor * r

    where r = n_hits / n_total is the signal's coverage ratio.

    When a signal returns nothing (r=0), absence of a document is not
    informative, so the default is 0.5 (neutral in log-odds space,
    logit(0.5) = 0).  When a signal covers all candidate documents (r=1),
    absence is strong negative evidence, so the default equals *floor*.
    """
    if n_total == 0:
        return 0.5
    ratio = n_hits / n_total
    return 0.5 * (1.0 - ratio) + floor * ratio


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
        return self.term_op.execute(context).intersect(self.vector_op.execute(context))

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
        return self.source.execute(context).intersect(self.vector_op.execute(context))

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

    Documents missing from a signal receive a coverage-based default
    probability.  When a signal returns nothing (vocabulary gap), the
    default is 0.5 (neutral — logit(0.5) = 0, no contribution to fusion).
    When a signal has full coverage, missing documents receive 0.01
    (strong negative evidence).  Partial coverage interpolates between
    the two extremes.
    """

    def __init__(
        self,
        signals: list[Operator],
        alpha: float = 0.5,
        top_k: int | None = None,
    ) -> None:
        self.signals = signals
        self.alpha = alpha
        self.top_k = top_k

    def execute(self, context: ExecutionContext) -> PostingList:
        from bayesian_bm25 import log_odds_conjunction

        par = context.parallel_executor
        if par is not None and par.enabled:
            posting_lists = par.execute_branches(self.signals, context)
        else:
            posting_lists = [sig.execute(context) for sig in self.signals]

        # Use WAND pruning when top_k is specified
        if self.top_k is not None:
            from uqa.scoring.fusion_wand import FusionWANDScorer

            # Compute per-signal upper bounds
            upper_bounds = []
            for pl in posting_lists:
                if pl:
                    ub = max(entry.payload.score for entry in pl)
                else:
                    ub = 0.5
                upper_bounds.append(ub)

            scorer = FusionWANDScorer(
                posting_lists, upper_bounds, alpha=self.alpha, k=self.top_k
            )
            return scorer.score_top_k()

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        sorted_ids = sorted(all_doc_ids)
        num_docs = len(sorted_ids)
        num_signals = len(score_maps)

        if num_docs == 0:
            return PostingList()

        # Compute per-signal default probability based on coverage ratio.
        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        # Build (num_docs, num_signals) probability matrix.
        prob_matrix = np.empty((num_docs, num_signals), dtype=np.float64)
        for j, smap in enumerate(score_maps):
            default_j = defaults[j]
            for i, doc_id in enumerate(sorted_ids):
                score = smap.get(doc_id)
                prob_matrix[i, j] = score if score is not None else default_j

        # Fuse each row using log_odds_conjunction.
        entries: list[PostingEntry] = []
        alpha = self.alpha
        for i, doc_id in enumerate(sorted_ids):
            row = prob_matrix[i]
            if num_signals == 1:
                fused = float(row[0])
            else:
                fused = float(log_odds_conjunction(row, alpha=alpha))
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(sig.cost_estimate(stats) for sig in self.signals)


class ProbBoolFusionOperator(Operator):
    """Probabilistic boolean fusion (Paper 3, Section 5).

    Combines signals using probabilistic AND or OR.
    All signal operators MUST produce calibrated probabilities in (0, 1).

    Documents missing from a signal receive a coverage-based default
    probability, following the same interpolation as LogOddsFusionOperator.
    """

    def __init__(
        self,
        signals: list[Operator],
        mode: str = "and",
    ) -> None:
        self.signals = signals
        self.mode = mode

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

        sorted_ids = sorted(all_doc_ids)
        num_docs = len(sorted_ids)

        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        fuse_fn = (
            ProbabilisticBoolean.prob_and
            if self.mode == "and"
            else ProbabilisticBoolean.prob_or
        )
        entries: list[PostingEntry] = []
        for doc_id in sorted_ids:
            probs = [smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)]
            fused = fuse_fn(probs)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return sum(sig.cost_estimate(stats) for sig in self.signals)


class VectorExclusionOperator(Operator):
    """Definition 3.3.3: VE(V1, V2) = V1 AND NOT V2.

    Keeps documents from V1 that are dissimilar to V2's query vector.
    V1 produces the candidate set; any document also appearing in V2
    (i.e., similar to the negative query) is removed.
    """

    def __init__(
        self,
        positive: Operator,
        negative_vector: NDArray,
        negative_threshold: float,
        field: str = "embedding",
    ) -> None:
        self.positive = positive
        self.negative_op = VectorSimilarityOperator(
            negative_vector, negative_threshold, field=field
        )

    def execute(self, context: ExecutionContext) -> PostingList:
        positive_pl = self.positive.execute(context)
        negative_pl = self.negative_op.execute(context)
        negative_ids = {entry.doc_id for entry in negative_pl}
        entries = [e for e in positive_pl if e.doc_id not in negative_ids]
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.positive.cost_estimate(stats) + self.negative_op.cost_estimate(
            stats
        )


class FacetVectorOperator(Operator):
    """Definition 3.3.4: FV(Phi_f, V_theta) = Facet over vector-similar docs.

    Computes facet counts only over documents that pass the vector
    similarity threshold, giving facet distributions conditioned on
    semantic relevance.
    """

    def __init__(
        self,
        facet_field: str,
        query_vector: NDArray,
        threshold: float,
        source: Operator | None = None,
    ) -> None:
        self.facet_field = facet_field
        self.vector_op = VectorSimilarityOperator(query_vector, threshold)
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        from collections import Counter

        vector_pl = self.vector_op.execute(context)
        vector_ids = {entry.doc_id for entry in vector_pl}

        if self.source is not None:
            source_pl = self.source.execute(context)
            candidate_ids = [e.doc_id for e in source_pl if e.doc_id in vector_ids]
        else:
            candidate_ids = sorted(vector_ids)

        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        value_counts: Counter[str] = Counter()
        for doc_id in candidate_ids:
            value = doc_store.get_field(doc_id, self.facet_field)
            if value is not None:
                value_counts[str(value)] += 1

        entries: list[PostingEntry] = []
        for i, (value, count) in enumerate(sorted(value_counts.items())):
            entries.append(
                PostingEntry(
                    doc_id=i,
                    payload=Payload(
                        score=float(count),
                        fields={
                            "_facet_field": self.facet_field,
                            "_facet_value": value,
                            "_facet_count": count,
                        },
                    ),
                )
            )
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        base = self.vector_op.cost_estimate(stats)
        if self.source is not None:
            base += self.source.cost_estimate(stats)
        return base


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

        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.signal.cost_estimate(stats)
