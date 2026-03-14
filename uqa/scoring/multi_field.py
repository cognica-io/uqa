#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from bayesian_bm25 import log_odds_conjunction

from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


class MultiFieldBayesianScorer:
    """Per-field Bayesian BM25 scoring with cross-field log-odds fusion (Section 12.2 #1, Paper 3).

    Each field has independent (alpha, beta, base_rate) calibration parameters
    and an optional weight.  Per-field posteriors are combined via weighted
    log-odds conjunction.
    """

    def __init__(
        self,
        field_configs: list[tuple[str, BayesianBM25Params, float]],
        index_stats: IndexStats,
    ) -> None:
        """
        Args:
            field_configs: List of (field_name, params, weight) tuples.
            index_stats: Shared index statistics.
        """
        self._field_names: list[str] = []
        self._scorers: list[BayesianBM25Scorer] = []
        self._weights: list[float] = []
        for field_name, params, weight in field_configs:
            self._field_names.append(field_name)
            self._scorers.append(BayesianBM25Scorer(params, index_stats))
            self._weights.append(weight)

    def score_document(
        self,
        doc_id: int,
        term_freq_per_field: dict[str, int],
        doc_length_per_field: dict[str, int],
        doc_freq_per_field: dict[str, int],
    ) -> float:
        """Score a document across all fields using weighted log-odds fusion."""
        probs: list[float] = []
        weights: list[float] = []
        for i, field_name in enumerate(self._field_names):
            tf = term_freq_per_field.get(field_name, 0)
            dl = doc_length_per_field.get(field_name, 1)
            df = doc_freq_per_field.get(field_name, 1)
            if tf == 0:
                probs.append(0.5)
            else:
                probs.append(self._scorers[i].score(tf, dl, df))
            weights.append(self._weights[i])

        if len(probs) == 1:
            return probs[0]

        weights_arr = np.array(weights)
        weight_sum = weights_arr.sum()
        if weight_sum > 0:
            weights_arr = weights_arr / weight_sum

        return float(
            log_odds_conjunction(
                np.array(probs),
                alpha=0.0,
                weights=weights_arr,
            )
        )
