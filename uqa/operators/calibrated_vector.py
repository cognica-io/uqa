#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Calibrated vector search operator (Paper 5).

Performs KNN or threshold vector search, then transforms the raw cosine
similarities into calibrated relevance probabilities via the likelihood
ratio framework of Theorem 3.1.1.  Importance weights for f_R
estimation come from one of:

    1. External BM25 probabilities (cross-modal, Section 4.3)
    2. IVF cell-density prior (Strategy 4.6.2)
    3. Distance gap detection (Strategy 4.6.1)
    4. Uniform weights (fallback)

Calibration is delegated to bayesian_bm25.VectorProbabilityTransform.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from bayesian_bm25.vector_probability import (
    VectorProbabilityTransform,
    ivf_density_prior,
)

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.operators.base import Operator

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.core.types import IndexStats
    from uqa.operators.base import ExecutionContext
    from uqa.storage.ivf_index import IVFIndex


class CalibratedVectorOperator(Operator):
    """KNN search with likelihood ratio calibration (Paper 5).

    Retrieves top-K results from the vector index, builds a
    VectorProbabilityTransform from IVF background distances, and
    produces calibrated relevance probabilities as posting list scores.

    Parameters
    ----------
    query_vector : ndarray
        Query embedding.
    k : int
        Number of nearest neighbours to retrieve.
    field : str
        Vector field name in the table.
    estimation_method : str
        ``"kde"``, ``"gmm"``, or ``"auto"`` for f_R estimation.
    base_rate : float
        Prior probability of relevance.
    weight_source : str
        Source of importance weights for f_R estimation:
        ``"bayesian_bm25"`` (cross-modal BM25 probabilities, Section 4.3),
        ``"density_prior"`` (IVF cell populations, Strategy 4.6.2),
        ``"distance_gap"`` (Strategy 4.6.1),
        ``"uniform"`` (no weighting).
    bm25_query : str or None
        Query text for BM25 cross-modal weights.  Required when
        *weight_source* is ``"bayesian_bm25"``.
    bm25_field : str or None
        Text field for BM25 scoring.  Defaults to the first text
        field if not specified.
    density_gamma : float
        Sensitivity parameter for the IVF density prior.
    bandwidth_scale : float
        Multiplier for Silverman bandwidth (Remark 4.4.2).
    """

    def __init__(
        self,
        query_vector: NDArray,
        k: int,
        field: str = "embedding",
        estimation_method: str = "kde",
        base_rate: float = 0.5,
        weight_source: str = "density_prior",
        bm25_query: str | None = None,
        bm25_field: str | None = None,
        density_gamma: float = 1.0,
        bandwidth_scale: float = 1.0,
    ) -> None:
        self.query_vector = query_vector
        self.k = k
        self.field = field
        self.estimation_method = estimation_method
        self.base_rate = base_rate
        self.weight_source = weight_source
        self.bm25_query = bm25_query
        self.bm25_field = bm25_field
        self.density_gamma = density_gamma
        self.bandwidth_scale = bandwidth_scale

    def execute(self, context: ExecutionContext) -> PostingList:
        vec_idx = context.vector_indexes.get(self.field)
        if vec_idx is None:
            return PostingList()

        # 1. Retrieve raw top-K results.
        raw_results = vec_idx.search_knn(self.query_vector, self.k)
        if len(raw_results) == 0:
            return raw_results

        # 2. Extract entries, similarities, and convert to distances.
        raw_entries = list(raw_results)
        doc_ids = [e.doc_id for e in raw_entries]
        similarities = np.array(
            [e.payload.score for e in raw_entries], dtype=np.float64
        )
        distances = 1.0 - similarities

        # 3. Obtain background distances for f_G estimation.
        #
        #    In IVF search the candidate pool is the probed cells.
        #    The distances to ALL vectors in those cells approximate
        #    f_G for this query (Theorem 6.2.2) at zero additional
        #    cost.  Fallback: train-time random-query distance samples
        #    (Definition 4.5.1) when probed distances are unavailable.
        ivf: IVFIndex | None = None
        bg_distances: np.ndarray | None = None
        if hasattr(vec_idx, "probed_distances"):
            ivf = vec_idx  # type: ignore[assignment]
            bg_distances = ivf.probed_distances(self.query_vector)  # type: ignore[union-attr]

        if (bg_distances is None or len(bg_distances) == 0) and hasattr(
            vec_idx, "background_samples"
        ):
            ivf = vec_idx  # type: ignore[assignment]
            bg_distances = ivf.background_samples  # type: ignore[union-attr]

        if bg_distances is None or len(bg_distances) == 0:
            return raw_results

        # 4. Build VectorProbabilityTransform from background distances.
        vpt = VectorProbabilityTransform.fit_background(
            bg_distances, base_rate=self.base_rate
        )

        # 5. Compute importance weights and determine calibration method.
        weights, density_prior, method = self._resolve_weights_and_method(
            raw_entries, ivf, distances, context
        )

        # 6. Calibrate via VectorProbabilityTransform.
        calibrated = np.asarray(
            vpt.calibrate(
                distances,
                weights=weights,
                method=method,
                bandwidth_factor=self.bandwidth_scale,
                density_prior=density_prior,
            ),
            dtype=np.float64,
        )

        # 7. Build output posting list with calibrated probabilities.
        entries: list[PostingEntry] = []
        for i, doc_id in enumerate(doc_ids):
            fields = dict(raw_entries[i].payload.fields)
            fields["_raw_similarity"] = float(similarities[i])
            entries.append(
                PostingEntry(
                    doc_id,
                    Payload(score=float(calibrated[i]), fields=fields),
                )
            )
        return PostingList(entries)

    def _resolve_weights_and_method(
        self,
        results: list[PostingEntry],
        ivf: IVFIndex | None,
        distances: np.ndarray,
        context: ExecutionContext,
    ) -> tuple[np.ndarray | None, np.ndarray | None, str]:
        """Determine weights, density_prior, and method from configuration.

        Returns (weights, density_prior, method) where:
        - weights: BM25 cross-modal weights or None
        - density_prior: IVF density prior weights or None
        - method: estimation method string for VPT.calibrate()
        """
        if self.weight_source == "bayesian_bm25":
            weights = self._bm25_weights(results, context)
            return weights, None, self.estimation_method

        if self.weight_source == "density_prior" and ivf is not None:
            centroid_ids = np.array(
                [e.payload.fields.get("_centroid_id", -1) for e in results],
                dtype=np.int64,
            )
            cell_pops = ivf.cell_populations()
            avg_pop = ivf.total_vectors / max(ivf.nlist, 1)
            # Vectorised ivf_density_prior: one call per centroid.
            prior = np.array(
                [
                    float(
                        ivf_density_prior(
                            cell_pops.get(int(cid), 1),
                            avg_pop,
                            gamma=self.density_gamma,
                        )
                    )
                    for cid in centroid_ids
                ],
                dtype=np.float64,
            )
            return None, prior, self.estimation_method

        if self.weight_source == "distance_gap":
            # Let VPT auto-routing handle gap detection.
            return None, None, "auto"

        # "uniform" or unknown -- let VPT decide with no external signal.
        return None, None, self.estimation_method

    def _bm25_weights(
        self,
        results: list[PostingEntry],
        context: ExecutionContext,
    ) -> np.ndarray:
        """Cross-modal Bayesian BM25 importance weights (Section 4.3).

        Uses the full Bayesian BM25 scoring pipeline (Paper 3) to
        produce calibrated posterior probabilities P(R=1|s) for each
        document.  These serve as the importance weights w_i in
        Definition 4.3.1.
        """
        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

        n = len(results)
        weights = np.full(n, 0.01, dtype=np.float64)

        inv_idx = context.inverted_index
        if inv_idx is None or self.bm25_query is None:
            return weights

        bm25_field = self.bm25_field or ""
        query_text = self.bm25_query

        scorer = BayesianBM25Scorer(BayesianBM25Params(), inv_idx.stats)
        terms = query_text.lower().split()
        if not terms:
            return weights

        term_op = TermOperator(query_text, bm25_field)
        score_op = ScoreOperator(scorer, term_op, terms, field=bm25_field)
        scored_pl = score_op.execute(context)

        bm25_map: dict[int, float] = {}
        for entry in scored_pl:
            bm25_map[entry.doc_id] = entry.payload.score

        for i, entry in enumerate(results):
            weights[i] = bm25_map.get(entry.doc_id, 0.01)

        return np.clip(weights, 0.01, 0.99)

    def cost_estimate(self, stats: IndexStats) -> float:
        import math

        return float(stats.dimensions) * math.log2(stats.total_docs + 1)
