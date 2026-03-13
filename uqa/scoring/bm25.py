#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import IndexStats


@dataclass(slots=True)
class BM25Params:
    """BM25 tuning parameters."""

    k1: float = 1.2
    b: float = 0.75
    boost: float = 1.0


class BM25Scorer:
    """Standard BM25 scorer (Definition 3.2.1, Paper 3).

    Properties (Theorem 3.2.2):
    - Monotonically increasing in term frequency
    - Monotonically decreasing in document length
    - Upper bound: boost * IDF (Theorem 3.2.3)
    """

    def __init__(self, params: BM25Params, index_stats: IndexStats) -> None:
        self.params = params
        self.stats = index_stats

    def idf(self, doc_freq: int) -> float:
        """Robertson-Sparck Jones IDF (Definition 3.1.1, Paper 3).

        IDF(t) = ln((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
        """
        n = self.stats.total_docs
        return math.log((n - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

    def score(self, term_freq: int, doc_length: int, doc_freq: int) -> float:
        """Compute BM25 score using the numerically stable formulation.

        score(f, n) = w - w / (1 + f * inv_norm)
        where w = boost * IDF and inv_norm = 1 / (k1 * ((1-b) + b * dl/avgdl))
        """
        idf_val = self.idf(doc_freq)
        return self.score_with_idf(term_freq, doc_length, idf_val)

    def score_with_idf(self, term_freq: int, doc_length: int, idf_val: float) -> float:
        """Compute BM25 score with a pre-computed IDF value.

        Avoids redundant IDF computation when scoring many documents
        for the same term.
        """
        w = self.params.boost * idf_val
        b_factor = (1.0 - self.params.b) + self.params.b * (
            doc_length / self.stats.avg_doc_length
        )
        inv_norm = 1.0 / (self.params.k1 * b_factor)
        return w - w / (1.0 + term_freq * inv_norm)

    def combine_scores(self, scores: list[float]) -> float:
        """BM25 scores are additive across query terms."""
        return sum(scores)

    def upper_bound(self, doc_freq: int) -> float:
        """Theorem 3.2.3: sup score = boost * IDF."""
        return self.params.boost * self.idf(doc_freq)
