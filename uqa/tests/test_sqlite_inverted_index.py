#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQLiteInvertedIndex -- SQLite-backed inverted index."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from uqa.core.posting_list import PostingList
from uqa.core.types import IndexStats, Payload, PostingEntry
from uqa.storage.inverted_index import IndexedTerms
from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex


# ======================================================================
# Helpers
# ======================================================================


def _make_index(tmp_path, table_name: str = "docs") -> SQLiteInvertedIndex:
    """Create a SQLiteInvertedIndex backed by a temp database."""
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    return SQLiteInvertedIndex(conn, table_name)


# ======================================================================
# Basic add / retrieve
# ======================================================================


class TestAddDocumentAndRetrieve:
    def test_single_document_single_field(self, tmp_path):
        idx = _make_index(tmp_path)
        result = idx.add_document(1, {"title": "hello world"})

        assert isinstance(result, IndexedTerms)
        assert result.field_lengths == {"title": 2}

        pl = idx.get_posting_list("title", "hello")
        assert len(pl) == 1
        assert pl.entries[0].doc_id == 1
        assert pl.entries[0].payload.score == 0.0

    def test_posting_list_sorted_by_doc_id(self, tmp_path):
        idx = _make_index(tmp_path)
        # Insert in reverse order to verify sorting.
        idx.add_document(3, {"body": "alpha"})
        idx.add_document(1, {"body": "alpha"})
        idx.add_document(2, {"body": "alpha"})

        pl = idx.get_posting_list("body", "alpha")
        doc_ids = [e.doc_id for e in pl.entries]
        assert doc_ids == [1, 2, 3]

    def test_multiple_terms_in_one_document(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "the quick brown fox"})

        for term in ("the", "quick", "brown", "fox"):
            pl = idx.get_posting_list("title", term)
            assert len(pl) == 1
            assert pl.entries[0].doc_id == 1

    def test_multiple_documents_shared_term(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "hello there"})
        idx.add_document(3, {"body": "goodbye world"})

        pl_hello = idx.get_posting_list("body", "hello")
        assert len(pl_hello) == 2
        assert {e.doc_id for e in pl_hello.entries} == {1, 2}

        pl_world = idx.get_posting_list("body", "world")
        assert len(pl_world) == 2
        assert {e.doc_id for e in pl_world.entries} == {1, 3}

    def test_positions_are_preserved(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "the cat sat on the mat"})

        pl = idx.get_posting_list("body", "the")
        assert len(pl) == 1
        assert pl.entries[0].payload.positions == (0, 4)

        pl_cat = idx.get_posting_list("body", "cat")
        assert pl_cat.entries[0].payload.positions == (1,)

    def test_empty_posting_list_for_nonexistent_term(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello"})

        pl = idx.get_posting_list("title", "nonexistent")
        assert len(pl) == 0

    def test_empty_posting_list_for_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello"})

        pl = idx.get_posting_list("unknown_field", "hello")
        assert len(pl) == 0


# ======================================================================
# doc_freq / term frequency
# ======================================================================


class TestDocFreqAndTermFreq:
    def test_doc_freq_single_term(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "hello there"})
        idx.add_document(3, {"body": "goodbye"})

        assert idx.doc_freq("body", "hello") == 2
        assert idx.doc_freq("body", "world") == 1
        assert idx.doc_freq("body", "goodbye") == 1
        assert idx.doc_freq("body", "missing") == 0

    def test_doc_freq_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello"})
        assert idx.doc_freq("other", "hello") == 0

    def test_get_term_freq(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "the cat sat on the mat"})

        assert idx.get_term_freq(1, "body", "the") == 2
        assert idx.get_term_freq(1, "body", "cat") == 1
        assert idx.get_term_freq(1, "body", "missing") == 0
        assert idx.get_term_freq(99, "body", "the") == 0

    def test_get_total_term_freq(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello world", "body": "hello there hello"})

        # "hello" appears 1 time in title, 2 times in body = 3 total
        assert idx.get_total_term_freq(1, "hello") == 3
        assert idx.get_total_term_freq(1, "world") == 1
        assert idx.get_total_term_freq(1, "missing") == 0

    def test_doc_freq_any_field(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello", "body": "hello world"})
        idx.add_document(2, {"title": "goodbye", "body": "hello"})

        # doc 1 and doc 2 both have "hello" (distinct doc_ids)
        assert idx.doc_freq_any_field("hello") == 2
        assert idx.doc_freq_any_field("world") == 1
        assert idx.doc_freq_any_field("goodbye") == 1
        assert idx.doc_freq_any_field("missing") == 0


# ======================================================================
# remove_document
# ======================================================================


class TestRemoveDocument:
    def test_removes_all_postings(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "hello there"})

        idx.remove_document(1)

        pl = idx.get_posting_list("body", "hello")
        assert len(pl) == 1
        assert pl.entries[0].doc_id == 2

        pl_world = idx.get_posting_list("body", "world")
        assert len(pl_world) == 0

    def test_updates_stats_on_remove(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "goodbye"})

        stats_before = idx.stats
        assert stats_before.total_docs == 2

        idx.remove_document(1)

        stats_after = idx.stats
        assert stats_after.total_docs == 1

    def test_removes_doc_lengths(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "goodbye"})

        idx.remove_document(1)

        assert idx.get_doc_length(1, "body") == 0
        assert idx.get_doc_length(2, "body") == 1

    def test_remove_nonexistent_is_safe(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello"})
        # Should not raise.
        idx.remove_document(999)
        assert len(idx.get_posting_list("body", "hello")) == 1


# ======================================================================
# Doc lengths
# ======================================================================


class TestDocLengths:
    def test_get_doc_length(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello world", "body": "a b c d e"})

        assert idx.get_doc_length(1, "title") == 2
        assert idx.get_doc_length(1, "body") == 5

    def test_get_doc_length_missing_doc(self, tmp_path):
        idx = _make_index(tmp_path)
        assert idx.get_doc_length(99, "body") == 0

    def test_get_total_doc_length(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello world", "body": "a b c d e"})
        assert idx.get_total_doc_length(1) == 7  # 2 + 5

    def test_get_total_doc_length_missing_doc(self, tmp_path):
        idx = _make_index(tmp_path)
        assert idx.get_total_doc_length(99) == 0


# ======================================================================
# get_posting_list_any_field
# ======================================================================


class TestPostingListAnyField:
    def test_merges_across_fields(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello", "body": "world"})
        idx.add_document(2, {"title": "world", "body": "hello"})

        pl = idx.get_posting_list_any_field("hello")
        assert len(pl) == 2
        doc_ids = {e.doc_id for e in pl.entries}
        assert doc_ids == {1, 2}

    def test_deduplicates_across_fields(self, tmp_path):
        idx = _make_index(tmp_path)
        # doc 1 has "hello" in both fields
        idx.add_document(1, {"title": "hello", "body": "hello world"})

        pl = idx.get_posting_list_any_field("hello")
        assert len(pl) == 1
        assert pl.entries[0].doc_id == 1

    def test_empty_for_missing_term(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello"})

        pl = idx.get_posting_list_any_field("nonexistent")
        assert len(pl) == 0


# ======================================================================
# stats property
# ======================================================================


class TestStats:
    def test_empty_index(self, tmp_path):
        idx = _make_index(tmp_path)
        s = idx.stats
        assert s.total_docs == 0
        assert s.avg_doc_length == 0.0

    def test_single_document(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world test"})

        s = idx.stats
        assert s.total_docs == 1
        assert s.avg_doc_length == 3.0

    def test_multiple_documents(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})       # length 2
        idx.add_document(2, {"body": "a b c d"})            # length 4

        s = idx.stats
        assert s.total_docs == 2
        # total_length = 6, avg = 3.0
        assert s.avg_doc_length == 3.0

    def test_stats_doc_freqs(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "hello there"})

        s = idx.stats
        assert s.doc_freq("body", "hello") == 2
        assert s.doc_freq("body", "world") == 1
        assert s.doc_freq("body", "there") == 1

    def test_stats_with_multiple_fields(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello", "body": "world foo"})

        s = idx.stats
        # doc_count is max across fields: both fields have 1 doc
        assert s.total_docs == 1
        # total_length = 1 (title) + 2 (body) = 3
        assert s.avg_doc_length == 3.0


# ======================================================================
# Tokenization
# ======================================================================


class TestTokenization:
    def test_lowercased(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "Hello WORLD"})

        pl = idx.get_posting_list("title", "hello")
        assert len(pl) == 1

        pl_upper = idx.get_posting_list("title", "Hello")
        assert len(pl_upper) == 0

    def test_split_on_whitespace(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"title": "hello   world"})

        pl = idx.get_posting_list("title", "hello")
        assert len(pl) == 1
        pl2 = idx.get_posting_list("title", "world")
        assert len(pl2) == 1

    def test_tokenize_method(self, tmp_path):
        idx = _make_index(tmp_path)
        tokens = idx._tokenize("Hello World FOO")
        assert tokens == ["hello", "world", "foo"]


# ======================================================================
# Restore methods (catalog migration backward compatibility)
# ======================================================================


class TestRestoreMethods:
    def test_add_posting(self, tmp_path):
        idx = _make_index(tmp_path)
        entry = PostingEntry(
            doc_id=1,
            payload=Payload(positions=(0, 3), score=0.0),
        )
        idx.add_posting("body", "hello", entry)

        pl = idx.get_posting_list("body", "hello")
        assert len(pl) == 1
        assert pl.entries[0].doc_id == 1
        assert pl.entries[0].payload.positions == (0, 3)

    def test_set_doc_length(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.set_doc_length(1, {"title": 3, "body": 5})

        assert idx.get_doc_length(1, "title") == 3
        assert idx.get_doc_length(1, "body") == 5

    def test_set_doc_count(self, tmp_path):
        idx = _make_index(tmp_path)
        # We need a field stats row to exist first.
        idx.add_total_length("body", 10)
        idx.set_doc_count(5)

        s = idx.stats
        assert s.total_docs == 5

    def test_add_total_length(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_total_length("body", 10)
        idx.add_total_length("body", 5)

        # total_length for body should be 15
        row = idx._conn.execute(
            f'SELECT total_length FROM "_field_stats_{idx._table_name}" '
            "WHERE field = ?",
            ("body",),
        ).fetchone()
        assert row[0] == 15


# ======================================================================
# Table isolation (two tables sharing one connection)
# ======================================================================


class TestTableIsolation:
    def test_separate_tables_same_connection(self, tmp_path):
        db = str(tmp_path / "shared.db")
        conn = sqlite3.connect(db)

        idx_a = SQLiteInvertedIndex(conn, "table_a")
        idx_b = SQLiteInvertedIndex(conn, "table_b")

        idx_a.add_document(1, {"body": "hello world"})
        idx_b.add_document(1, {"body": "goodbye moon"})

        pl_a = idx_a.get_posting_list("body", "hello")
        pl_b = idx_b.get_posting_list("body", "hello")
        assert len(pl_a) == 1
        assert len(pl_b) == 0

        pl_b2 = idx_b.get_posting_list("body", "goodbye")
        assert len(pl_b2) == 1

        assert idx_a.stats.total_docs == 1
        assert idx_b.stats.total_docs == 1

    def test_remove_does_not_affect_other_table(self, tmp_path):
        db = str(tmp_path / "shared.db")
        conn = sqlite3.connect(db)

        idx_a = SQLiteInvertedIndex(conn, "table_a")
        idx_b = SQLiteInvertedIndex(conn, "table_b")

        idx_a.add_document(1, {"body": "hello"})
        idx_b.add_document(1, {"body": "hello"})

        idx_a.remove_document(1)

        assert len(idx_a.get_posting_list("body", "hello")) == 0
        assert len(idx_b.get_posting_list("body", "hello")) == 1


# ======================================================================
# IndexedTerms return value
# ======================================================================


class TestIndexedTermsReturn:
    def test_field_lengths(self, tmp_path):
        idx = _make_index(tmp_path)
        result = idx.add_document(1, {"title": "a b c", "body": "x y"})

        assert result.field_lengths == {"title": 3, "body": 2}

    def test_postings_keys(self, tmp_path):
        idx = _make_index(tmp_path)
        result = idx.add_document(1, {"title": "hello world"})

        assert ("title", "hello") in result.postings
        assert ("title", "world") in result.postings
        assert result.postings[("title", "hello")] == (0,)
        assert result.postings[("title", "world")] == (1,)

    def test_postings_with_repeated_term(self, tmp_path):
        idx = _make_index(tmp_path)
        result = idx.add_document(1, {"body": "the cat and the dog"})

        assert result.postings[("body", "the")] == (0, 3)
        assert result.postings[("body", "cat")] == (1,)


# ======================================================================
# Persistence across reconnection
# ======================================================================


class TestPersistence:
    def test_data_survives_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        conn1 = sqlite3.connect(db)
        idx1 = SQLiteInvertedIndex(conn1, "docs")
        idx1.add_document(1, {"title": "hello world"})
        idx1.add_document(2, {"title": "foo bar"})
        conn1.close()

        conn2 = sqlite3.connect(db)
        idx2 = SQLiteInvertedIndex(conn2, "docs")

        pl = idx2.get_posting_list("title", "hello")
        assert len(pl) == 1
        assert pl.entries[0].doc_id == 1

        assert idx2.get_doc_length(1, "title") == 2
        assert idx2.stats.total_docs == 2
        conn2.close()
