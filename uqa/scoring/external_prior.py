#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from bayesian_bm25 import BayesianProbabilityTransform

from uqa.scoring.bm25 import BM25Scorer

if TYPE_CHECKING:
    from collections.abc import Callable

    from uqa.core.types import IndexStats
    from uqa.scoring.bayesian_bm25 import BayesianBM25Params


class ExternalPriorScorer:
    """Bayesian BM25 scorer with external prior features (Section 12.2 #6, Paper 3).

    Combines the BM25 likelihood with a document-level prior via log-odds
    addition:

        logit(posterior) = logit(likelihood) + logit(prior)

    The prior is computed by a user-supplied function that maps document
    fields to a probability in (0, 1).
    """

    def __init__(
        self,
        params: BayesianBM25Params,
        index_stats: IndexStats,
        prior_fn: Callable[[dict[str, Any]], float],
    ) -> None:
        self.params = params
        self.bm25 = BM25Scorer(params.bm25, index_stats)
        base_rate = params.base_rate if params.base_rate != 0.5 else None
        self._transform = BayesianProbabilityTransform(
            alpha=params.alpha,
            beta=params.beta,
            base_rate=base_rate,
        )
        self._prior_fn = prior_fn

    def score_with_prior(
        self,
        term_freq: int,
        doc_length: int,
        doc_freq: int,
        doc_fields: dict[str, Any],
    ) -> float:
        """Compute posterior with external prior via log-odds fusion."""
        # Compute BM25 likelihood probability
        idf_val = self.bm25.idf(doc_freq)
        raw = self.bm25.score_with_idf(term_freq, doc_length, idf_val)
        avg_dl = self.bm25.stats.avg_doc_length
        doc_len_ratio = doc_length / avg_dl if avg_dl > 0 else 1.0
        likelihood = float(
            self._transform.score_to_probability(raw, term_freq, doc_len_ratio)
        )

        # Compute prior from document fields
        prior = self._prior_fn(doc_fields)
        prior = max(1e-10, min(1.0 - 1e-10, prior))

        # Combine via log-odds addition
        if 0 < likelihood < 1:
            logit_likelihood = math.log(likelihood / (1.0 - likelihood))
        elif likelihood >= 1:
            logit_likelihood = 10.0
        else:
            logit_likelihood = -10.0
        logit_prior = math.log(prior / (1.0 - prior))
        logit_posterior = logit_likelihood + logit_prior

        # Sigmoid back to probability
        return 1.0 / (1.0 + math.exp(-logit_posterior))


def recency_prior(
    field: str, decay_days: float = 30.0
) -> Callable[[dict[str, Any]], float]:
    """Create a recency-based prior function.

    Documents with a more recent timestamp in ``field`` receive higher
    prior probability.  The prior decays exponentially with age:

        prior = 0.5 + 0.4 * exp(-age_days / decay_days)

    Returns 0.5 (neutral prior) when the field is missing.
    """
    import datetime

    def _prior(doc_fields: dict[str, Any]) -> float:
        val = doc_fields.get(field)
        if val is None:
            return 0.5
        if isinstance(val, str):
            try:
                val = datetime.datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return 0.5
        if isinstance(val, datetime.datetime):
            now = datetime.datetime.now(tz=val.tzinfo)
            age_days = max(0.0, (now - val).total_seconds() / 86400.0)
            return 0.5 + 0.4 * math.exp(-age_days / decay_days)
        return 0.5

    return _prior


def authority_prior(
    field: str,
    levels: dict[str, float] | None = None,
) -> Callable[[dict[str, Any]], float]:
    """Create an authority-based prior function.

    Maps categorical authority levels to prior probabilities.
    Default levels: {"high": 0.8, "medium": 0.6, "low": 0.4}.
    Returns 0.5 (neutral) when the field is missing or unrecognized.
    """
    if levels is None:
        levels = {"high": 0.8, "medium": 0.6, "low": 0.4}
    _levels = dict(levels)

    def _prior(doc_fields: dict[str, Any]) -> float:
        val = doc_fields.get(field)
        if val is None:
            return 0.5
        return _levels.get(str(val), 0.5)

    return _prior
