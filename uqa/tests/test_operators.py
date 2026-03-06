#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for operators and storage layer.

Tests:
- TermOperator returns correct posting list
- FilterOperator with each predicate type
- Boolean composition (union, intersect, complement)
- HybridTextVectorOperator = intersect of term and vector results
- AggregationMonoid laws (identity, associativity via combine)
- Hierarchical ops on nested JSON
"""
from __future__ import annotations

import numpy as np
import pytest

from uqa.core.hierarchical import HierarchicalDocument
from uqa.core.posting_list import PostingList
from uqa.core.types import (
    Between,
    Equals,
    GreaterThan,
    GreaterThanOrEqual,
    InSet,
    LessThan,
    LessThanOrEqual,
    NotEquals,
    Payload,
    PostingEntry,
)
from uqa.operators.aggregation import (
    AggregateOperator,
    AvgMonoid,
    CountMonoid,
    GroupByOperator,
    MaxMonoid,
    MinMonoid,
    SumMonoid,
)
from uqa.operators.base import ExecutionContext
from uqa.operators.boolean import ComplementOperator, IntersectOperator, UnionOperator
from uqa.operators.hierarchical import (
    PathFilterOperator,
    PathProjectOperator,
    PathUnnestOperator,
)
from uqa.operators.hybrid import HybridTextVectorOperator, SemanticFilterOperator
from uqa.operators.primitive import (
    FacetOperator,
    FilterOperator,
    KNNOperator,
    TermOperator,
    VectorSimilarityOperator,
)
from uqa.storage.document_store import DocumentStore
from uqa.storage.inverted_index import InvertedIndex
from uqa.storage.vector_index import HNSWIndex


@pytest.fixture
def doc_store(sample_documents: list[dict]) -> DocumentStore:
    store = DocumentStore()
    for doc in sample_documents:
        store.put(doc["doc_id"], doc)
    return store


@pytest.fixture
def inv_index(sample_documents: list[dict]) -> InvertedIndex:
    idx = InvertedIndex()
    for doc in sample_documents:
        fields = {}
        if "title" in doc:
            fields["title"] = doc["title"]
        if "abstract" in doc:
            fields["abstract"] = doc["abstract"]
        idx.add_document(doc["doc_id"], fields)
    return idx


@pytest.fixture
def vec_index(sample_vectors: dict[int, np.ndarray]) -> HNSWIndex:
    dim = 64
    index = HNSWIndex(dimensions=dim, max_elements=100)
    for doc_id, vector in sample_vectors.items():
        index.add(doc_id, vector)
    return index


@pytest.fixture
def context(
    doc_store: DocumentStore,
    inv_index: InvertedIndex,
    vec_index: HNSWIndex,
) -> ExecutionContext:
    return ExecutionContext(
        document_store=doc_store,
        inverted_index=inv_index,
        vector_index=vec_index,
    )


# -- TermOperator --

class TestTermOperator:
    def test_returns_correct_posting_list(self, context: ExecutionContext) -> None:
        op = TermOperator("neural", field="title")
        result = op.execute(context)
        assert len(result) > 0
        # "neural" appears in doc 1 ("introduction to neural networks")
        # and doc 3 ("graph neural networks")
        doc_ids = result.doc_ids
        assert 1 in doc_ids
        assert 3 in doc_ids

    def test_missing_term_returns_empty(self, context: ExecutionContext) -> None:
        op = TermOperator("nonexistent_term_xyz", field="title")
        result = op.execute(context)
        assert len(result) == 0

    def test_term_with_positions(self, context: ExecutionContext) -> None:
        op = TermOperator("neural", field="title")
        result = op.execute(context)
        for entry in result:
            assert len(entry.payload.positions) > 0


# -- FilterOperator --

class TestFilterOperator:
    def test_equals(self, context: ExecutionContext) -> None:
        op = FilterOperator("category", Equals("machine learning"))
        result = op.execute(context)
        assert result.doc_ids == {1, 3}

    def test_not_equals(self, context: ExecutionContext) -> None:
        op = FilterOperator("category", NotEquals("machine learning"))
        result = op.execute(context)
        assert 1 not in result.doc_ids
        assert 3 not in result.doc_ids
        assert len(result) == 3

    def test_greater_than(self, context: ExecutionContext) -> None:
        op = FilterOperator("year", GreaterThan(2024))
        result = op.execute(context)
        assert result.doc_ids == {4, 5}

    def test_greater_than_or_equal(self, context: ExecutionContext) -> None:
        op = FilterOperator("year", GreaterThanOrEqual(2024))
        result = op.execute(context)
        assert result.doc_ids == {2, 3, 4, 5}

    def test_less_than(self, context: ExecutionContext) -> None:
        op = FilterOperator("year", LessThan(2024))
        result = op.execute(context)
        assert result.doc_ids == {1}

    def test_less_than_or_equal(self, context: ExecutionContext) -> None:
        op = FilterOperator("year", LessThanOrEqual(2024))
        result = op.execute(context)
        assert result.doc_ids == {1, 2, 3}

    def test_in_set(self, context: ExecutionContext) -> None:
        op = FilterOperator(
            "category", InSet(frozenset(["machine learning", "optimization"]))
        )
        result = op.execute(context)
        assert result.doc_ids == {1, 3, 4}

    def test_between(self, context: ExecutionContext) -> None:
        op = FilterOperator("year", Between(2024, 2025))
        result = op.execute(context)
        assert result.doc_ids == {2, 3, 4, 5}


# -- Boolean operators --

class TestBooleanOperators:
    def test_union(self, context: ExecutionContext) -> None:
        op_a = TermOperator("neural", field="title")
        op_b = TermOperator("bayesian", field="title")
        union_op = UnionOperator([op_a, op_b])
        result = union_op.execute(context)
        # neural: docs 1, 3; bayesian: doc 4
        assert {1, 3, 4}.issubset(result.doc_ids)

    def test_intersect(self, context: ExecutionContext) -> None:
        op_a = TermOperator("neural", field="title")
        op_b = TermOperator("networks", field="title")
        intersect_op = IntersectOperator([op_a, op_b])
        result = intersect_op.execute(context)
        # Both "neural" and "networks" appear in docs 1 and 3
        assert result.doc_ids == {1, 3}

    def test_complement(self, context: ExecutionContext) -> None:
        op = TermOperator("neural", field="title")
        complement_op = ComplementOperator(op)
        result = complement_op.execute(context)
        # neural: docs 1, 3 -> complement should have 2, 4, 5
        neural_docs = op.execute(context).doc_ids
        for doc_id in result.doc_ids:
            assert doc_id not in neural_docs


# -- HybridTextVectorOperator --

class TestHybridOperator:
    def test_hybrid_is_intersect_of_term_and_vector(
        self, context: ExecutionContext, sample_vectors: dict[int, np.ndarray]
    ) -> None:
        query_vec = sample_vectors[1]
        # Use a very low threshold so vector returns all docs
        hybrid_op = HybridTextVectorOperator("neural", query_vec, threshold=-1.0)
        hybrid_result = hybrid_op.execute(context)

        # Manually compute intersect
        term_result = TermOperator("neural", field="title").execute(context)
        # Note: hybrid uses field=None for term, but we test the set relationship
        vec_result = VectorSimilarityOperator(query_vec, threshold=-1.0).execute(context)
        manual_intersect = term_result.intersect(vec_result)

        assert hybrid_result.doc_ids == manual_intersect.doc_ids

    def test_semantic_filter(
        self, context: ExecutionContext, sample_vectors: dict[int, np.ndarray]
    ) -> None:
        query_vec = sample_vectors[1]
        source = FilterOperator("year", GreaterThanOrEqual(2024))
        sem_filter = SemanticFilterOperator(source, query_vec, threshold=-1.0)
        result = sem_filter.execute(context)
        # Should be subset of filter result
        filter_result = source.execute(context)
        assert result.doc_ids.issubset(filter_result.doc_ids)


# -- AggregationMonoid laws --

class TestAggregationMonoids:
    def test_count_identity(self) -> None:
        m = CountMonoid()
        assert m.finalize(m.identity()) == 0

    def test_count_accumulate(self) -> None:
        m = CountMonoid()
        state = m.identity()
        state = m.accumulate(state, "anything")
        state = m.accumulate(state, "else")
        assert m.finalize(state) == 2

    def test_count_combine_associativity(self) -> None:
        m = CountMonoid()
        a = m.accumulate(m.identity(), 1)
        b = m.accumulate(m.identity(), 2)
        c = m.accumulate(m.identity(), 3)
        # (a + b) + c == a + (b + c)
        assert m.combine(m.combine(a, b), c) == m.combine(a, m.combine(b, c))

    def test_sum_identity(self) -> None:
        m = SumMonoid()
        assert m.finalize(m.identity()) == 0.0

    def test_sum_accumulate(self) -> None:
        m = SumMonoid()
        state = m.identity()
        state = m.accumulate(state, 3.0)
        state = m.accumulate(state, 7.0)
        assert m.finalize(state) == 10.0

    def test_sum_combine_associativity(self) -> None:
        m = SumMonoid()
        a = m.accumulate(m.identity(), 1.0)
        b = m.accumulate(m.identity(), 2.0)
        c = m.accumulate(m.identity(), 3.0)
        assert m.combine(m.combine(a, b), c) == m.combine(a, m.combine(b, c))

    def test_avg_correct(self) -> None:
        m = AvgMonoid()
        state = m.identity()
        for v in [2.0, 4.0, 6.0]:
            state = m.accumulate(state, v)
        assert m.finalize(state) == 4.0

    def test_avg_combine_associativity(self) -> None:
        m = AvgMonoid()
        a = m.accumulate(m.identity(), 2.0)
        b = m.accumulate(m.identity(), 4.0)
        c = m.accumulate(m.identity(), 6.0)
        lhs = m.combine(m.combine(a, b), c)
        rhs = m.combine(a, m.combine(b, c))
        assert m.finalize(lhs) == m.finalize(rhs)

    def test_min_identity(self) -> None:
        m = MinMonoid()
        assert m.finalize(m.identity()) == float("inf")

    def test_min_accumulate(self) -> None:
        m = MinMonoid()
        state = m.identity()
        state = m.accumulate(state, 5.0)
        state = m.accumulate(state, 3.0)
        state = m.accumulate(state, 7.0)
        assert m.finalize(state) == 3.0

    def test_max_identity(self) -> None:
        m = MaxMonoid()
        assert m.finalize(m.identity()) == float("-inf")

    def test_max_accumulate(self) -> None:
        m = MaxMonoid()
        state = m.identity()
        state = m.accumulate(state, 5.0)
        state = m.accumulate(state, 3.0)
        state = m.accumulate(state, 7.0)
        assert m.finalize(state) == 7.0

    def test_aggregate_operator(self, context: ExecutionContext) -> None:
        source = FilterOperator("year", GreaterThanOrEqual(2024))
        agg = AggregateOperator(source, "year", AvgMonoid())
        result = agg.execute(context)
        assert len(result) == 1
        entry = result.entries[0]
        # Years 2024, 2024, 2025, 2025 -> avg = 2024.5
        assert entry.payload.fields["_aggregate"] == pytest.approx(2024.5)

    def test_group_by_operator(self, context: ExecutionContext) -> None:
        source = FilterOperator("year", GreaterThanOrEqual(2023))
        group_op = GroupByOperator(source, "category", "year", CountMonoid())
        result = group_op.execute(context)
        assert len(result) > 0
        # Check that group keys are present
        groups = {e.payload.fields["_group_key"] for e in result}
        assert "machine learning" in groups


# -- Hierarchical operators --

class TestHierarchicalOperators:
    @pytest.fixture
    def hier_context(self, hierarchical_doc: HierarchicalDocument) -> ExecutionContext:
        store = DocumentStore()
        store.put(hierarchical_doc.doc_id, hierarchical_doc.data)
        return ExecutionContext(document_store=store)

    def test_path_filter(self, hier_context: ExecutionContext) -> None:
        op = PathFilterOperator(
            path=["metadata", "author"],
            predicate=Equals("Alice"),
        )
        result = op.execute(hier_context)
        assert len(result) == 1
        assert 1 in result.doc_ids

    def test_path_filter_no_match(self, hier_context: ExecutionContext) -> None:
        op = PathFilterOperator(
            path=["metadata", "author"],
            predicate=Equals("Bob"),
        )
        result = op.execute(hier_context)
        assert len(result) == 0

    def test_path_project(self, hier_context: ExecutionContext) -> None:
        # Create a source that returns the document
        source = PathFilterOperator(
            path=["metadata", "author"],
            predicate=Equals("Alice"),
        )
        project_op = PathProjectOperator(
            paths=[["title"], ["metadata", "author"]],
            source=source,
        )
        result = project_op.execute(hier_context)
        assert len(result) == 1
        entry = result.entries[0]
        assert entry.payload.fields["title"] == "test document"
        assert entry.payload.fields["metadata.author"] == "Alice"

    def test_path_unnest(self, hier_context: ExecutionContext) -> None:
        source = PathFilterOperator(
            path=["metadata", "author"],
            predicate=Equals("Alice"),
        )
        unnest_op = PathUnnestOperator(
            path=["metadata", "tags"],
            source=source,
        )
        result = unnest_op.execute(hier_context)
        # PostingList deduplicates by doc_id, so all unnested entries (same doc_id=1)
        # collapse to a single entry. Verify the unnest operation ran successfully.
        assert len(result) == 1
        assert 1 in result.doc_ids
        entry = result.entries[0]
        # The entry should have unnested data in its fields
        assert "_unnested_data" in entry.payload.fields


# -- Vector operators --

class TestVectorOperators:
    def test_knn_returns_k_results(
        self, context: ExecutionContext, sample_vectors: dict[int, np.ndarray]
    ) -> None:
        query = sample_vectors[1]
        op = KNNOperator(query, k=3)
        result = op.execute(context)
        assert len(result) == 3

    def test_vector_similarity_threshold(
        self, context: ExecutionContext, sample_vectors: dict[int, np.ndarray]
    ) -> None:
        query = sample_vectors[1]
        # Very high threshold should return few or no results
        op = VectorSimilarityOperator(query, threshold=0.99)
        result = op.execute(context)
        # At minimum, the query vector itself (doc 1) should have similarity ~1.0
        assert 1 in result.doc_ids


# -- FacetOperator --

class TestFacetOperator:
    def test_facet_counts(self, context: ExecutionContext) -> None:
        source = FilterOperator("year", GreaterThanOrEqual(2023))
        facet_op = FacetOperator("category", source)
        result = facet_op.execute(context)
        assert len(result) > 0
        # Check that facet values contain expected categories
        facet_values = {e.payload.fields["_facet_value"] for e in result}
        assert "machine learning" in facet_values


# -- Storage layer --

class TestDocumentStore:
    def test_put_get(self) -> None:
        store = DocumentStore()
        store.put(1, {"title": "test"})
        assert store.get(1) == {"title": "test"}

    def test_delete(self) -> None:
        store = DocumentStore()
        store.put(1, {"title": "test"})
        store.delete(1)
        assert store.get(1) is None

    def test_get_field(self) -> None:
        store = DocumentStore()
        store.put(1, {"title": "test", "year": 2024})
        assert store.get_field(1, "title") == "test"
        assert store.get_field(1, "year") == 2024

    def test_eval_path(self) -> None:
        store = DocumentStore()
        store.put(1, {"metadata": {"author": "Alice"}})
        assert store.eval_path(1, ["metadata", "author"]) == "Alice"


class TestInvertedIndex:
    def test_add_and_retrieve(self) -> None:
        idx = InvertedIndex()
        idx.add_document(1, {"title": "hello world"})
        pl = idx.get_posting_list("title", "hello")
        assert len(pl) == 1
        assert 1 in pl.doc_ids

    def test_doc_freq(self) -> None:
        idx = InvertedIndex()
        idx.add_document(1, {"title": "hello world"})
        idx.add_document(2, {"title": "hello there"})
        assert idx.doc_freq("title", "hello") == 2
        assert idx.doc_freq("title", "world") == 1

    def test_positions(self) -> None:
        idx = InvertedIndex()
        idx.add_document(1, {"title": "the quick brown fox the"})
        pl = idx.get_posting_list("title", "the")
        entry = pl.get_entry(1)
        assert entry is not None
        assert 0 in entry.payload.positions
        assert 4 in entry.payload.positions

    def test_stats(self) -> None:
        idx = InvertedIndex()
        idx.add_document(1, {"title": "hello world"})
        idx.add_document(2, {"title": "hello there friend"})
        stats = idx.stats
        assert stats.total_docs == 2
        assert stats.avg_doc_length > 0


class TestHNSWIndex:
    def test_add_and_knn(self) -> None:
        rng = np.random.RandomState(42)
        idx = HNSWIndex(dimensions=16, max_elements=10)
        vectors = {i: rng.randn(16).astype(np.float32) for i in range(1, 6)}
        for doc_id, vec in vectors.items():
            idx.add(doc_id, vec)
        result = idx.search_knn(vectors[1], k=3)
        assert len(result) == 3
        assert 1 in result.doc_ids

    def test_search_threshold(self) -> None:
        rng = np.random.RandomState(42)
        idx = HNSWIndex(dimensions=16, max_elements=10)
        vectors = {i: rng.randn(16).astype(np.float32) for i in range(1, 6)}
        for doc_id, vec in vectors.items():
            idx.add(doc_id, vec)
        # The exact vector should have similarity ~1.0
        result = idx.search_threshold(vectors[1], threshold=0.99)
        assert 1 in result.doc_ids
