#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import numpy as np
import pytest

from uqa.core.posting_list import GeneralizedPostingList, PostingList
from uqa.core.types import Edge, Payload, PostingEntry, Vertex
from uqa.graph.store import GraphStore
from uqa.joins.base import JoinCondition
from uqa.joins.cross_paradigm import (
    CrossParadigmJoinOperator,
    GraphJoinOperator,
    HybridJoinOperator,
    TextSimilarityJoinOperator,
    VectorSimilarityJoinOperator,
)
from uqa.joins.index import IndexJoinOperator
from uqa.joins.inner import InnerJoinOperator
from uqa.joins.outer import LeftOuterJoinOperator
from uqa.joins.sort_merge import SortMergeJoinOperator


class _MockContext:
    """Minimal execution context for join tests."""

    def __init__(self, graph_store: GraphStore | None = None) -> None:
        self.graph_store = graph_store


@pytest.fixture
def context() -> _MockContext:
    return _MockContext()


@pytest.fixture
def left_entries() -> PostingList:
    return PostingList(
        [
            PostingEntry(
                1, Payload(score=1.0, fields={"dept": "eng", "name": "Alice"})
            ),
            PostingEntry(2, Payload(score=0.8, fields={"dept": "eng", "name": "Bob"})),
            PostingEntry(
                3, Payload(score=0.6, fields={"dept": "sales", "name": "Charlie"})
            ),
            PostingEntry(4, Payload(score=0.4, fields={"dept": "hr", "name": "Diana"})),
        ]
    )


@pytest.fixture
def right_entries() -> PostingList:
    return PostingList(
        [
            PostingEntry(
                10, Payload(score=0.9, fields={"department": "eng", "budget": 100})
            ),
            PostingEntry(
                11, Payload(score=0.7, fields={"department": "sales", "budget": 50})
            ),
            PostingEntry(
                12, Payload(score=0.5, fields={"department": "marketing", "budget": 75})
            ),
        ]
    )


# -- InnerJoinOperator tests --


class TestInnerJoinOperator:
    def test_basic_inner_join(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        condition = JoinCondition("dept", "department")
        op = InnerJoinOperator(left_entries, right_entries, condition)
        result = op.execute(context)

        pairs = {e.doc_ids for e in result}
        # Alice(1) + eng(10), Bob(2) + eng(10), Charlie(3) + sales(11)
        assert (1, 10) in pairs
        assert (2, 10) in pairs
        assert (3, 11) in pairs
        # Diana(4) has dept=hr, no match
        assert all(e.doc_ids[0] != 4 for e in result)
        assert len(result) == 3

    def test_inner_join_no_matches(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "a"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(2, Payload(fields={"key": "b"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = InnerJoinOperator(left, right, condition)
        result = op.execute(context)
        assert len(result) == 0

    def test_inner_join_multiple_matches(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "x"})),
                PostingEntry(2, Payload(fields={"key": "x"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"key": "x"})),
                PostingEntry(11, Payload(fields={"key": "x"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = InnerJoinOperator(left, right, condition)
        result = op.execute(context)
        # 2 left x 2 right = 4 pairs
        assert len(result) == 4

    def test_commutativity(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        """inner_join(A,B) has same pairs as inner_join(B,A), up to tuple reorder."""
        cond_ab = JoinCondition("dept", "department")
        result_ab = InnerJoinOperator(left_entries, right_entries, cond_ab).execute(
            context
        )

        cond_ba = JoinCondition("department", "dept")
        result_ba = InnerJoinOperator(right_entries, left_entries, cond_ba).execute(
            context
        )

        # Extract unordered pairs
        pairs_ab = {frozenset(e.doc_ids) for e in result_ab}
        pairs_ba = {frozenset(e.doc_ids) for e in result_ba}
        assert pairs_ab == pairs_ba

    def test_associativity(self, context: _MockContext) -> None:
        """Three-way join associativity."""
        a = PostingList(
            [
                PostingEntry(1, Payload(fields={"k1": "x", "k2": "p"})),
                PostingEntry(2, Payload(fields={"k1": "y", "k2": "q"})),
            ]
        )
        b = PostingList(
            [
                PostingEntry(10, Payload(fields={"k1": "x", "k3": "m"})),
                PostingEntry(11, Payload(fields={"k1": "y", "k3": "n"})),
            ]
        )
        c = PostingList(
            [
                PostingEntry(100, Payload(fields={"k3": "m"})),
                PostingEntry(101, Payload(fields={"k3": "n"})),
            ]
        )

        # (A join B) join C
        ab_cond = JoinCondition("k1", "k1")
        ab = InnerJoinOperator(a, b, ab_cond).execute(context)
        # Wrap ab result entries as PostingList for second join
        ab_as_pl = _generalized_to_posting_list(ab, key_field="k3")
        bc_cond = JoinCondition("k3", "k3")
        result_left = InnerJoinOperator(ab_as_pl, c, bc_cond).execute(context)

        # A join (B join C)
        bc = InnerJoinOperator(b, c, bc_cond).execute(context)
        bc_as_pl = _generalized_to_posting_list(bc, key_field="k1")
        result_right = InnerJoinOperator(a, bc_as_pl, ab_cond).execute(context)

        # Both should produce same number of results
        assert len(result_left) == len(result_right)

    def test_distribution_over_union(self, context: _MockContext) -> None:
        """Join(A, B union C) = Join(A,B) union Join(A,C)."""
        a = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "x"})),
                PostingEntry(2, Payload(fields={"key": "y"})),
            ]
        )
        b = PostingList(
            [
                PostingEntry(10, Payload(fields={"key": "x"})),
            ]
        )
        c = PostingList(
            [
                PostingEntry(11, Payload(fields={"key": "y"})),
            ]
        )

        cond = JoinCondition("key", "key")

        # Join(A, B union C)
        b_union_c = b.union(c)
        result_left = InnerJoinOperator(a, b_union_c, cond).execute(context)

        # Join(A,B) union Join(A,C)
        join_ab = InnerJoinOperator(a, b, cond).execute(context)
        join_ac = InnerJoinOperator(a, c, cond).execute(context)
        result_right = join_ab.union(join_ac)

        pairs_left = {e.doc_ids for e in result_left}
        pairs_right = {e.doc_ids for e in result_right}
        assert pairs_left == pairs_right


# -- LeftOuterJoinOperator tests --


class TestLeftOuterJoinOperator:
    def test_basic_left_outer_join(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        condition = JoinCondition("dept", "department")
        op = LeftOuterJoinOperator(left_entries, right_entries, condition)
        result = op.execute(context)

        # All 4 left entries should be preserved
        left_doc_ids = set()
        for entry in result:
            left_doc_ids.add(entry.doc_ids[0])
        assert left_doc_ids == {1, 2, 3, 4}

    def test_unmatched_entries_preserved(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "a"})),
                PostingEntry(2, Payload(fields={"key": "b"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"key": "a"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = LeftOuterJoinOperator(left, right, condition)
        result = op.execute(context)

        # Entry 1 matches, entry 2 preserved with single-element tuple
        assert len(result) == 2
        entries_by_left = {e.doc_ids[0]: e for e in result}
        assert entries_by_left[1].doc_ids == (1, 10)
        assert entries_by_left[2].doc_ids == (2,)

    def test_all_entries_present(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        """All left entries must be in result."""
        condition = JoinCondition("dept", "department")
        op = LeftOuterJoinOperator(left_entries, right_entries, condition)
        result = op.execute(context)

        left_ids_in_result = {e.doc_ids[0] for e in result}
        expected_left_ids = {e.doc_id for e in left_entries}
        assert expected_left_ids == left_ids_in_result


# -- TextSimilarityJoinOperator tests --


class TestTextSimilarityJoinOperator:
    def test_jaccard_similarity(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"text": "the quick brown fox"})),
                PostingEntry(2, Payload(fields={"text": "hello world"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"text": "the quick brown dog"})),
                PostingEntry(11, Payload(fields={"text": "goodbye world"})),
            ]
        )

        op = TextSimilarityJoinOperator(left, right, "text", "text", threshold=0.5)
        result = op.execute(context)

        # "the quick brown fox" vs "the quick brown dog":
        # intersection = {the, quick, brown}, union = {the, quick, brown, fox, dog}
        # Jaccard = 3/5 = 0.6 >= 0.5
        pairs = {e.doc_ids for e in result}
        assert (1, 10) in pairs

    def test_below_threshold(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"text": "alpha beta gamma"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"text": "delta epsilon zeta"})),
            ]
        )

        op = TextSimilarityJoinOperator(left, right, "text", "text", threshold=0.5)
        result = op.execute(context)
        assert len(result) == 0


# -- VectorSimilarityJoinOperator tests --


class TestVectorSimilarityJoinOperator:
    def test_cosine_similarity(self, context: _MockContext) -> None:
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([1.0, 0.0, 0.0])
        v3 = np.array([0.0, 1.0, 0.0])

        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"vec": v1})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"vec": v2})),
                PostingEntry(11, Payload(fields={"vec": v3})),
            ]
        )

        op = VectorSimilarityJoinOperator(left, right, "vec", "vec", threshold=0.9)
        result = op.execute(context)

        pairs = {e.doc_ids for e in result}
        # v1 . v2 = 1.0 >= 0.9
        assert (1, 10) in pairs
        # v1 . v3 = 0.0 < 0.9
        assert (1, 11) not in pairs

    def test_threshold_boundary(self, context: _MockContext) -> None:
        v1 = np.array([1.0, 1.0])
        v2 = np.array([1.0, 0.0])

        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"vec": v1})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"vec": v2})),
            ]
        )

        # cos(v1, v2) = 1/sqrt(2) ~= 0.707
        op_high = VectorSimilarityJoinOperator(left, right, "vec", "vec", threshold=0.8)
        assert len(op_high.execute(context)) == 0

        op_low = VectorSimilarityJoinOperator(left, right, "vec", "vec", threshold=0.7)
        assert len(op_low.execute(context)) == 1


# -- HybridJoinOperator tests --


class TestHybridJoinOperator:
    def test_structured_plus_vector(self, context: _MockContext) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.9, 0.1])
        v3 = np.array([0.0, 1.0])

        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"cat": "A", "vec": v1})),
                PostingEntry(2, Payload(fields={"cat": "B", "vec": v1})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"cat": "A", "vec": v2})),
                PostingEntry(11, Payload(fields={"cat": "A", "vec": v3})),
                PostingEntry(12, Payload(fields={"cat": "B", "vec": v3})),
            ]
        )

        op = HybridJoinOperator(left, right, "cat", "vec", threshold=0.8)
        result = op.execute(context)

        pairs = {e.doc_ids for e in result}
        # (1, 10): cat=A match, cos(v1, v2) high -> should match
        assert (1, 10) in pairs
        # (1, 11): cat=A match, cos(v1, v3)=0.0 < 0.8 -> no
        assert (1, 11) not in pairs
        # (2, 12): cat=B match, cos(v1, v3)=0.0 < 0.8 -> no
        assert (2, 12) not in pairs


# -- Helper --


def _generalized_to_posting_list(
    gpl: GeneralizedPostingList, key_field: str
) -> PostingList:
    """Convert GeneralizedPostingList back to PostingList for chained joins."""
    entries: list[PostingEntry] = []
    for _i, ge in enumerate(gpl):
        entries.append(
            PostingEntry(
                doc_id=ge.doc_ids[0],
                payload=ge.payload,
            )
        )
    return PostingList(entries)


# -- SortMergeJoinOperator tests --


class TestSortMergeJoinOperator:
    def test_basic_sort_merge(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        condition = JoinCondition("dept", "department")
        op = SortMergeJoinOperator(left_entries, right_entries, condition)
        result = op.execute(context)

        pairs = {e.doc_ids for e in result}
        assert (1, 10) in pairs
        assert (2, 10) in pairs
        assert (3, 11) in pairs
        assert all(e.doc_ids[0] != 4 for e in result)
        assert len(result) == 3

    def test_equivalent_to_hash_join(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        """Sort-merge join produces same results as hash join."""
        condition = JoinCondition("dept", "department")
        hash_result = InnerJoinOperator(left_entries, right_entries, condition).execute(
            context
        )
        merge_result = SortMergeJoinOperator(
            left_entries, right_entries, condition
        ).execute(context)

        hash_pairs = {e.doc_ids for e in hash_result}
        merge_pairs = {e.doc_ids for e in merge_result}
        assert hash_pairs == merge_pairs

    def test_no_matches(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "a"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(2, Payload(fields={"key": "b"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = SortMergeJoinOperator(left, right, condition)
        result = op.execute(context)
        assert len(result) == 0

    def test_multiple_matches(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "x"})),
                PostingEntry(2, Payload(fields={"key": "x"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"key": "x"})),
                PostingEntry(11, Payload(fields={"key": "x"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = SortMergeJoinOperator(left, right, condition)
        result = op.execute(context)
        assert len(result) == 4


# -- IndexJoinOperator tests --


class TestIndexJoinOperator:
    def test_basic_index_join(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        condition = JoinCondition("dept", "department")
        op = IndexJoinOperator(left_entries, right_entries, condition)
        result = op.execute(context)

        pairs = {e.doc_ids for e in result}
        assert (1, 10) in pairs
        assert (2, 10) in pairs
        assert (3, 11) in pairs
        assert len(result) == 3

    def test_equivalent_to_hash_join(
        self,
        context: _MockContext,
        left_entries: PostingList,
        right_entries: PostingList,
    ) -> None:
        """Index join produces same results as hash join."""
        condition = JoinCondition("dept", "department")
        hash_result = InnerJoinOperator(left_entries, right_entries, condition).execute(
            context
        )
        index_result = IndexJoinOperator(
            left_entries, right_entries, condition
        ).execute(context)

        hash_pairs = {e.doc_ids for e in hash_result}
        index_pairs = {e.doc_ids for e in index_result}
        assert hash_pairs == index_pairs

    def test_no_matches(self, context: _MockContext) -> None:
        left = PostingList(
            [
                PostingEntry(1, Payload(fields={"key": "a"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(2, Payload(fields={"key": "b"})),
            ]
        )
        condition = JoinCondition("key", "key")
        op = IndexJoinOperator(left, right, condition)
        result = op.execute(context)
        assert len(result) == 0


# -- GraphJoinOperator tests --


class TestGraphJoinOperator:
    def test_basic_graph_join(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {"name": "A"}), graph="test")
        store.add_vertex(Vertex(2, "", {"name": "B"}), graph="test")
        store.add_vertex(Vertex(3, "", {"name": "C"}), graph="test")
        store.add_edge(Edge(1, 1, 2, "knows"), graph="test")
        store.add_edge(Edge(2, 1, 3, "knows"), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList(
            [
                PostingEntry(1, Payload(score=1.0, fields={"role": "author"})),
            ]
        )
        right = PostingList(
            [
                PostingEntry(2, Payload(score=0.5, fields={"role": "reviewer"})),
                PostingEntry(3, Payload(score=0.3, fields={"role": "editor"})),
                PostingEntry(4, Payload(score=0.1, fields={"role": "reader"})),
            ]
        )

        op = GraphJoinOperator(left, right, label="knows")
        result = op.execute(ctx)

        pairs = {e.doc_ids for e in result}
        assert (1, 2) in pairs
        assert (1, 3) in pairs
        assert (1, 4) not in pairs
        assert len(result) == 2

    def test_label_filter(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {}), graph="test")
        store.add_vertex(Vertex(2, "", {}), graph="test")
        store.add_vertex(Vertex(3, "", {}), graph="test")
        store.add_edge(Edge(1, 1, 2, "knows"), graph="test")
        store.add_edge(Edge(2, 1, 3, "works_with"), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList([PostingEntry(1, Payload())])
        right = PostingList(
            [
                PostingEntry(2, Payload()),
                PostingEntry(3, Payload()),
            ]
        )

        op = GraphJoinOperator(left, right, label="knows")
        result = op.execute(ctx)
        pairs = {e.doc_ids for e in result}
        assert (1, 2) in pairs
        assert (1, 3) not in pairs

    def test_no_label_filter(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {}), graph="test")
        store.add_vertex(Vertex(2, "", {}), graph="test")
        store.add_vertex(Vertex(3, "", {}), graph="test")
        store.add_edge(Edge(1, 1, 2, "knows"), graph="test")
        store.add_edge(Edge(2, 1, 3, "works_with"), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList([PostingEntry(1, Payload())])
        right = PostingList(
            [
                PostingEntry(2, Payload()),
                PostingEntry(3, Payload()),
            ]
        )

        op = GraphJoinOperator(left, right, label=None)
        result = op.execute(ctx)
        assert len(result) == 2


# -- CrossParadigmJoinOperator tests --


class TestCrossParadigmJoinOperator:
    def test_vertex_to_document_join(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {"department": "eng"}), graph="test")
        store.add_vertex(Vertex(2, "", {"department": "sales"}), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList(
            [
                PostingEntry(1, Payload(score=0.9)),
                PostingEntry(2, Payload(score=0.8)),
            ]
        )
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"dept": "eng", "budget": 100})),
                PostingEntry(11, Payload(fields={"dept": "sales", "budget": 50})),
                PostingEntry(12, Payload(fields={"dept": "hr", "budget": 75})),
            ]
        )

        op = CrossParadigmJoinOperator(left, right, "department", "dept")
        result = op.execute(ctx)

        pairs = {e.doc_ids for e in result}
        assert (1, 10) in pairs
        assert (2, 11) in pairs
        assert len(result) == 2

    def test_no_match(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {"category": "A"}), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList([PostingEntry(1, Payload())])
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"cat": "B"})),
            ]
        )

        op = CrossParadigmJoinOperator(left, right, "category", "cat")
        result = op.execute(ctx)
        assert len(result) == 0

    def test_merged_fields_include_vertex_properties(self) -> None:
        store = GraphStore()
        store.create_graph("test")
        store.add_vertex(Vertex(1, "", {"name": "Alice", "dept": "eng"}), graph="test")
        ctx = _MockContext(graph_store=store)

        left = PostingList([PostingEntry(1, Payload(score=1.0))])
        right = PostingList(
            [
                PostingEntry(10, Payload(fields={"dept": "eng", "title": "Manager"})),
            ]
        )

        op = CrossParadigmJoinOperator(left, right, "dept", "dept")
        result = op.execute(ctx)
        assert len(result) == 1
        entry = next(iter(result))
        assert entry.payload.fields["name"] == "Alice"
        assert entry.payload.fields["title"] == "Manager"
