#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry, Predicate
from uqa.operators.base import ExecutionContext, Operator

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.storage.index_abc import Index


def _brute_force_knn(
    context: ExecutionContext, field: str, query: NDArray, k: int,
) -> PostingList:
    """Exact KNN via sequential cosine similarity scan over document store."""
    doc_store = context.document_store
    if doc_store is None:
        return PostingList()

    query_f = np.asarray(query, dtype=np.float32)
    qnorm = np.linalg.norm(query_f)
    if qnorm == 0:
        return PostingList()
    query_unit = query_f / qnorm

    scored: list[tuple[int, float]] = []
    for doc_id in doc_store.doc_ids:
        vec_data = doc_store.get_field(doc_id, field)
        if vec_data is None:
            continue
        vec = np.asarray(vec_data, dtype=np.float32)
        vnorm = np.linalg.norm(vec)
        if vnorm == 0:
            continue
        similarity = float(np.dot(query_unit, vec / vnorm))
        scored.append((doc_id, similarity))

    scored.sort(key=lambda x: x[1], reverse=True)
    entries = [
        PostingEntry(doc_id, Payload(score=sim))
        for doc_id, sim in scored[:k]
    ]
    return PostingList(entries)


def _brute_force_threshold(
    context: ExecutionContext, field: str, query: NDArray, threshold: float,
) -> PostingList:
    """Exact threshold search via sequential cosine similarity scan."""
    doc_store = context.document_store
    if doc_store is None:
        return PostingList()

    query_f = np.asarray(query, dtype=np.float32)
    qnorm = np.linalg.norm(query_f)
    if qnorm == 0:
        return PostingList()
    query_unit = query_f / qnorm

    entries: list[PostingEntry] = []
    for doc_id in doc_store.doc_ids:
        vec_data = doc_store.get_field(doc_id, field)
        if vec_data is None:
            continue
        vec = np.asarray(vec_data, dtype=np.float32)
        vnorm = np.linalg.norm(vec)
        if vnorm == 0:
            continue
        similarity = float(np.dot(query_unit, vec / vnorm))
        if similarity >= threshold:
            entries.append(PostingEntry(doc_id, Payload(score=similarity)))

    return PostingList(entries)


class TermOperator(Operator):
    """Definition 3.1.1: T(term) -> PostingList.

    Retrieves the posting list for a term from the inverted index.
    """

    def __init__(self, term: str, field: str | None = None) -> None:
        self.term = term
        self.field = field

    def execute(self, context: ExecutionContext) -> PostingList:
        idx = context.inverted_index
        if idx is None:
            return PostingList()

        # Analyze the query term using the same analyzer that indexed the field
        analyzer = idx.get_field_analyzer(self.field) if self.field else idx.analyzer
        tokens = analyzer.analyze(self.term)
        if not tokens:
            return PostingList()

        if self.field is not None:
            lists = [idx.get_posting_list(self.field, t) for t in tokens]
        else:
            lists = [idx.get_posting_list_any_field(t) for t in tokens]

        # Single token: return directly; multiple tokens: intersect
        result = lists[0]
        for pl in lists[1:]:
            result = result.intersect(pl)
        return result

    def cost_estimate(self, stats: IndexStats) -> float:
        if self.field is not None:
            return float(stats.doc_freq(self.field, self.term))
        return float(stats.total_docs)


class VectorSimilarityOperator(Operator):
    """Definition 3.1.2: V_theta(q) -> PostingList.

    Returns documents with similarity >= threshold.
    Uses HNSW index if available, otherwise exact sequential scan.
    """

    def __init__(
        self,
        query_vector: NDArray,
        threshold: float,
        field: str = "embedding",
    ) -> None:
        self.query_vector = query_vector
        self.threshold = threshold
        self.field = field

    def execute(self, context: ExecutionContext) -> PostingList:
        vec_idx = context.vector_indexes.get(self.field)
        if vec_idx is not None:
            return vec_idx.search_threshold(self.query_vector, self.threshold)
        return _brute_force_threshold(
            context, self.field, self.query_vector, self.threshold
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        import math
        return float(stats.dimensions) * math.log2(stats.total_docs + 1)


class KNNOperator(Operator):
    """Definition 3.1.3: KNN_k(q) -> PostingList.

    Returns top-k nearest neighbors.
    Uses HNSW index if available, otherwise exact sequential scan.
    """

    def __init__(
        self,
        query_vector: NDArray,
        k: int,
        field: str = "embedding",
    ) -> None:
        self.query_vector = query_vector
        self.k = k
        self.field = field

    def execute(self, context: ExecutionContext) -> PostingList:
        vec_idx = context.vector_indexes.get(self.field)
        if vec_idx is not None:
            return vec_idx.search_knn(self.query_vector, self.k)
        return _brute_force_knn(
            context, self.field, self.query_vector, self.k
        )

    def cost_estimate(self, stats: IndexStats) -> float:
        import math
        return float(stats.dimensions) * math.log2(stats.total_docs + 1)


class FilterOperator(Operator):
    """Definition 3.1.4: Filter_{f,predicate} -> PostingList.

    Filters a source posting list (or all documents) by applying a predicate to a field.
    """

    def __init__(
        self,
        field: str,
        predicate: Predicate,
        source: Operator | None = None,
    ) -> None:
        self.field = field
        self.predicate = predicate
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        from uqa.core.types import is_null_predicate
        null_aware = is_null_predicate(self.predicate)

        if self.source is not None:
            source_pl = self.source.execute(context)
            # Iterate source entries directly (already sorted by doc_id).
            # This avoids O(n) dict construction and preserves the
            # entry's original payload (including scores).
            entries: list[PostingEntry] = []
            for entry in source_pl:
                value = doc_store.get_field(entry.doc_id, self.field)
                if null_aware:
                    matched = self.predicate.evaluate(value)
                else:
                    matched = value is not None and self.predicate.evaluate(value)
                if matched:
                    entries.append(entry)
        else:
            candidate_ids = sorted(doc_store.doc_ids)
            entries = []
            for doc_id in candidate_ids:
                value = doc_store.get_field(doc_id, self.field)
                if null_aware:
                    matched = self.predicate.evaluate(value)
                else:
                    matched = value is not None and self.predicate.evaluate(value)
                if matched:
                    entries.append(PostingEntry(doc_id, Payload(score=0.0)))
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs)


class FacetOperator(Operator):
    """Definition 3.1.5: Facet_f(source) -> dict[value, count].

    Counts distinct field values over a source posting list.
    Returns a PostingList with facet counts stored in payload fields.
    """

    def __init__(self, field: str, source: Operator | None = None) -> None:
        self.field = field
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        if self.source is not None:
            source_pl = self.source.execute(context)
            candidate_ids = [entry.doc_id for entry in source_pl]
        else:
            candidate_ids = sorted(doc_store.doc_ids)

        value_counts: Counter[str] = Counter()
        for doc_id in candidate_ids:
            value = doc_store.get_field(doc_id, self.field)
            if value is not None:
                value_counts[str(value)] += 1

        entries: list[PostingEntry] = []
        for i, (value, count) in enumerate(sorted(value_counts.items())):
            entries.append(PostingEntry(
                doc_id=i,
                payload=Payload(
                    score=float(count),
                    fields={
                        "_facet_field": self.field,
                        "_facet_value": value,
                        "_facet_count": count,
                    },
                ),
            ))
        return PostingList.from_sorted(entries)


class ScoreOperator(Operator):
    """Definition 3.1.6: Score_q(source) -> PostingList with scores.

    Applies BM25 or Bayesian BM25 scoring to a source posting list.
    """

    def __init__(
        self,
        scorer: object,
        source: Operator,
        query_terms: list[str],
        field: str | None = None,
    ) -> None:
        self.scorer = scorer
        self.source = source
        self.query_terms = query_terms
        self.field = field

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        idx = context.inverted_index
        if idx is None:
            return source_pl

        # Pre-compute per-term IDF values (hoisted out of per-doc loop).
        has_idf = hasattr(self.scorer, "score_with_idf")
        has_combine = hasattr(self.scorer, "combine_scores")
        term_idfs: list[float] = []
        if has_idf:
            for term in self.query_terms:
                if self.field is not None:
                    df = idx.doc_freq(self.field, term)
                else:
                    df = idx.doc_freq_any_field(term)
                term_idfs.append(self.scorer.idf(df))  # type: ignore[union-attr]

        entries: list[PostingEntry] = []
        for entry in source_pl:
            # Per-doc constants: doc length (hoisted out of per-term loop).
            if self.field is not None:
                dl = idx.get_doc_length(entry.doc_id, self.field)
            else:
                dl = idx.get_total_doc_length(entry.doc_id)

            per_term_scores: list[float] = []
            for i, term in enumerate(self.query_terms):
                if self.field is not None:
                    tf = idx.get_term_freq(entry.doc_id, self.field, term)
                else:
                    tf = idx.get_total_term_freq(entry.doc_id, term)

                if has_idf:
                    per_term_scores.append(
                        self.scorer.score_with_idf(tf, dl, term_idfs[i])  # type: ignore[union-attr]
                    )
                else:
                    if self.field is not None:
                        df = idx.doc_freq(self.field, term)
                    else:
                        df = idx.doc_freq_any_field(term)
                    per_term_scores.append(
                        self.scorer.score(tf, dl, df)  # type: ignore[union-attr]
                    )

            if has_combine:
                total_score = self.scorer.combine_scores(per_term_scores)  # type: ignore[union-attr]
            else:
                total_score = sum(per_term_scores)
            entries.append(PostingEntry(
                entry.doc_id,
                Payload(
                    positions=entry.payload.positions,
                    score=total_score,
                    fields=entry.payload.fields,
                ),
            ))
        return PostingList.from_sorted(entries)


class IndexScanOperator(Operator):
    """Index-backed scan: uses a B-tree (or other) index instead of a full table scan."""

    def __init__(
        self, index: Index, field: str, predicate: Predicate
    ) -> None:
        self.index = index
        self.field = field
        self.predicate = predicate

    def execute(self, context: ExecutionContext) -> PostingList:
        return self.index.scan(self.predicate)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.index.scan_cost(self.predicate)
