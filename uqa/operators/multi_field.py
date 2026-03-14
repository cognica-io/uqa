#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


class MultiFieldSearchOperator(Operator):
    """Multi-field Bayesian BM25 search (Section 12.2 #1, Paper 3).

    Searches multiple text fields for the same query, computes per-field
    Bayesian BM25 scores, and fuses them via weighted log-odds conjunction.
    """

    def __init__(
        self,
        fields: list[str],
        query: str,
        weights: list[float] | None = None,
    ) -> None:
        self.fields = fields
        self.query = query
        self.weights = weights or [1.0] * len(fields)

    def execute(self, context: ExecutionContext) -> PostingList:
        import numpy as np
        from bayesian_bm25 import log_odds_conjunction

        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

        idx = context.inverted_index
        if idx is None:
            return PostingList()

        # Score each field independently
        per_field_scores: list[dict[int, float]] = []
        all_doc_ids: set[int] = set()

        for field_name in self.fields:
            analyzer = idx.get_search_analyzer(field_name)
            terms = analyzer.analyze(self.query)
            retrieval = TermOperator(self.query, field_name)
            scorer = BayesianBM25Scorer(BayesianBM25Params(), idx.stats)
            score_op = ScoreOperator(scorer, retrieval, terms, field=field_name)
            result = score_op.execute(context)

            smap: dict[int, float] = {}
            for entry in result:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            per_field_scores.append(smap)

        # Fuse per-field scores via weighted log-odds conjunction
        # Normalize weights to sum to 1 as required by log_odds_conjunction
        entries: list[PostingEntry] = []
        raw_weights = np.array(self.weights)
        weight_sum = raw_weights.sum()
        weights_arr = raw_weights / weight_sum if weight_sum > 0 else raw_weights

        for doc_id in sorted(all_doc_ids):
            probs = []
            for smap in per_field_scores:
                probs.append(smap.get(doc_id, 0.5))
            if len(probs) == 1:
                fused = probs[0]
            else:
                fused = float(
                    log_odds_conjunction(
                        np.array(probs), alpha=0.0, weights=weights_arr
                    )
                )
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs) * len(self.fields)
