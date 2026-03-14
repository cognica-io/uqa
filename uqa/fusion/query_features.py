#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.storage.inverted_index import InvertedIndex


class QueryFeatureExtractor:
    """Extract query-level features for attention-based fusion (Section 8, Paper 4).

    Features: [mean_idf, max_idf, min_idf, coverage_ratio, query_length, vocab_overlap_ratio]
    """

    def __init__(self, inverted_index: InvertedIndex) -> None:
        self._index = inverted_index

    @property
    def n_features(self) -> int:
        return 6

    def extract(self, query_terms: list[str], field: str | None = None) -> NDArray:
        """Extract feature vector for a query."""
        stats = self._index.stats
        n = stats.total_docs
        if n == 0:
            return np.zeros(self.n_features, dtype=np.float64)

        field_name = field or "_default"
        idfs: list[float] = []
        vocab_hits = 0

        for term in query_terms:
            df = stats.doc_freq(field_name, term)
            if df > 0:
                vocab_hits += 1
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
                idfs.append(idf)

        if not idfs:
            return np.array([0.0, 0.0, 0.0, 0.0, float(len(query_terms)), 0.0])

        mean_idf = sum(idfs) / len(idfs)
        max_idf = max(idfs)
        min_idf = min(idfs)
        coverage_ratio = len(idfs) / max(1, n)
        query_length = float(len(query_terms))
        vocab_overlap = vocab_hits / max(1, len(query_terms))

        return np.array(
            [mean_idf, max_idf, min_idf, coverage_ratio, query_length, vocab_overlap],
            dtype=np.float64,
        )
