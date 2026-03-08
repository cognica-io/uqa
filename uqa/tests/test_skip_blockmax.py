#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Phase 2 Section 3.2.2: Skip Pointers and Block-Max Persistence.

Covers skip pointer construction, forward-seek, block-max score computation,
persistence across reconnection, and integration with BlockMaxIndex.
"""

from __future__ import annotations

import sqlite3

import pytest

from uqa.core.types import IndexStats
from uqa.scoring.bm25 import BM25Params, BM25Scorer
from uqa.storage.block_max_index import BlockMaxIndex
from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex


# -- Helpers ---------------------------------------------------------------


def _make_index(tmp_path, table_name: str = "docs") -> SQLiteInvertedIndex:
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    return SQLiteInvertedIndex(conn, table_name)


def _make_scorer(total_docs: int = 10, avg_doc_length: float = 5.0) -> BM25Scorer:
    stats = IndexStats(total_docs=total_docs, avg_doc_length=avg_doc_length)
    return BM25Scorer(BM25Params(), stats)


def _bulk_insert(idx: SQLiteInvertedIndex, n: int, field: str = "body") -> None:
    """Insert N documents each containing 'alpha' plus a unique term."""
    for i in range(1, n + 1):
        idx.add_document(i, {field: f"alpha term{i}"})


# ======================================================================
# Skip Pointers
# ======================================================================


class TestSkipPointerConstruction:
    def test_skip_table_created(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})

        # The skip table should exist.
        row = idx._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = ?",
            (f"_skip_{idx._table_name}_body",),
        ).fetchone()
        assert row is not None

    def test_skip_entries_for_small_posting_list(self, tmp_path):
        """A posting list smaller than BLOCK_SIZE has exactly one skip entry."""
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello"})
        idx.add_document(2, {"body": "hello"})
        idx.add_document(3, {"body": "hello"})

        skip_tbl = idx._skip_table_name("body")
        rows = idx._conn.execute(
            f'SELECT skip_doc_id, skip_offset FROM "{skip_tbl}" '
            "WHERE term = ? ORDER BY skip_doc_id",
            ("hello",),
        ).fetchall()

        # Only one skip entry at offset 0 (the first doc).
        assert len(rows) == 1
        assert rows[0] == (1, 0)

    def test_skip_entries_for_large_posting_list(self, tmp_path):
        """A posting list with 300 docs should have 3 skip entries (0, 128, 256)."""
        idx = _make_index(tmp_path)
        for i in range(1, 301):
            idx.add_document(i, {"body": "alpha"})

        skip_tbl = idx._skip_table_name("body")
        rows = idx._conn.execute(
            f'SELECT skip_doc_id, skip_offset FROM "{skip_tbl}" '
            "WHERE term = ? ORDER BY skip_offset",
            ("alpha",),
        ).fetchall()

        assert len(rows) == 3
        # Offsets should be 0, 128, 256
        offsets = [r[1] for r in rows]
        assert offsets == [0, 128, 256]

        # First skip should point to doc_id 1
        assert rows[0][0] == 1
        # Second skip should point to doc_id 129
        assert rows[1][0] == 129
        # Third skip should point to doc_id 257
        assert rows[2][0] == 257

    def test_skip_rebuilt_on_remove(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 200):
            idx.add_document(i, {"body": "alpha"})

        skip_tbl = idx._skip_table_name("body")

        # Before remove: 2 skip entries (0, 128)
        rows_before = idx._conn.execute(
            f'SELECT COUNT(*) FROM "{skip_tbl}" WHERE term = ?',
            ("alpha",),
        ).fetchone()
        assert rows_before[0] == 2

        # Remove doc_ids 1..72 (72 docs), leaving 127 docs (< 128 -> 1 skip)
        for i in range(1, 73):
            idx.remove_document(i)

        rows_after = idx._conn.execute(
            f'SELECT COUNT(*) FROM "{skip_tbl}" WHERE term = ?',
            ("alpha",),
        ).fetchone()
        assert rows_after[0] == 1


class TestSkipTo:
    def test_skip_to_finds_nearest(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 301):
            idx.add_document(i, {"body": "alpha"})

        # Skip to doc 150: nearest skip entry should be at doc 129 (offset 128)
        skip_doc_id, skip_offset = idx.skip_to("body", "alpha", 150)
        assert skip_doc_id == 129
        assert skip_offset == 128

    def test_skip_to_exact_match(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 301):
            idx.add_document(i, {"body": "alpha"})

        # Skip to doc 129: exact match on skip entry
        skip_doc_id, skip_offset = idx.skip_to("body", "alpha", 129)
        assert skip_doc_id == 129
        assert skip_offset == 128

    def test_skip_to_before_first(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(100, 200):
            idx.add_document(i, {"body": "alpha"})

        # Skip to doc 50: before all skip entries
        skip_doc_id, skip_offset = idx.skip_to("body", "alpha", 50)
        assert skip_doc_id == 0
        assert skip_offset == 0

    def test_skip_to_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        skip_doc_id, skip_offset = idx.skip_to("body", "alpha", 100)
        assert skip_doc_id == 0
        assert skip_offset == 0

    def test_skip_to_nonexistent_term(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello"})

        skip_doc_id, skip_offset = idx.skip_to("body", "nonexistent", 1)
        assert skip_doc_id == 0
        assert skip_offset == 0


# ======================================================================
# Block-Max Scores
# ======================================================================


class TestBlockMaxScores:
    def test_blockmax_table_created(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})

        row = idx._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = ?",
            (f"_blockmax_{idx._table_name}_body",),
        ).fetchone()
        assert row is not None

    def test_build_block_max_single_block(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 11):
            idx.add_document(i, {"body": "alpha"})

        scorer = _make_scorer()
        idx.build_block_max_scores("body", "alpha", scorer)

        scores = idx.get_all_block_max_scores("body", "alpha")
        assert len(scores) == 1
        assert scores[0] > 0.0

    def test_build_block_max_multiple_blocks(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 301):
            idx.add_document(i, {"body": "alpha"})

        scorer = _make_scorer(total_docs=300)
        idx.build_block_max_scores("body", "alpha", scorer)

        scores = idx.get_all_block_max_scores("body", "alpha")
        # 300 docs / 128 block size = 3 blocks
        assert len(scores) == 3
        assert all(s > 0.0 for s in scores)

    def test_get_block_max_score_by_index(self, tmp_path):
        idx = _make_index(tmp_path)
        for i in range(1, 301):
            idx.add_document(i, {"body": "alpha"})

        scorer = _make_scorer(total_docs=300)
        idx.build_block_max_scores("body", "alpha", scorer)

        score_0 = idx.get_block_max_score("body", "alpha", 0)
        score_1 = idx.get_block_max_score("body", "alpha", 1)
        assert score_0 > 0.0
        assert score_1 > 0.0

        # Nonexistent block returns 0
        score_missing = idx.get_block_max_score("body", "alpha", 99)
        assert score_missing == 0.0

    def test_get_block_max_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        assert idx.get_block_max_score("nonexistent", "alpha", 0) == 0.0

    def test_get_all_block_max_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        assert idx.get_all_block_max_scores("nonexistent", "alpha") == []

    def test_build_all_block_max_scores(self, tmp_path):
        idx = _make_index(tmp_path)
        idx.add_document(1, {"body": "hello world"})
        idx.add_document(2, {"body": "hello there"})
        idx.add_document(3, {"body": "goodbye world"})

        scorer = _make_scorer(total_docs=3)
        idx.build_all_block_max_scores("body", scorer)

        # "hello" has 2 docs, "world" has 2 docs, etc.
        hello_scores = idx.get_all_block_max_scores("body", "hello")
        assert len(hello_scores) == 1
        assert hello_scores[0] > 0.0

        world_scores = idx.get_all_block_max_scores("body", "world")
        assert len(world_scores) == 1
        assert world_scores[0] > 0.0

    def test_build_block_max_for_nonexistent_field(self, tmp_path):
        idx = _make_index(tmp_path)
        scorer = _make_scorer()
        # Should be a no-op, not raise.
        idx.build_block_max_scores("nonexistent", "alpha", scorer)
        idx.build_all_block_max_scores("nonexistent", scorer)


# ======================================================================
# Persistence across reconnection
# ======================================================================


class TestSkipBlockMaxPersistence:
    def test_skip_pointers_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        conn1 = sqlite3.connect(db)
        idx1 = SQLiteInvertedIndex(conn1, "docs")
        for i in range(1, 200):
            idx1.add_document(i, {"body": "alpha"})
        conn1.close()

        conn2 = sqlite3.connect(db)
        idx2 = SQLiteInvertedIndex(conn2, "docs")

        skip_doc_id, skip_offset = idx2.skip_to("body", "alpha", 150)
        assert skip_doc_id == 129
        assert skip_offset == 128
        conn2.close()

    def test_block_max_scores_survive_reconnection(self, tmp_path):
        db = str(tmp_path / "persist.db")

        conn1 = sqlite3.connect(db)
        idx1 = SQLiteInvertedIndex(conn1, "docs")
        for i in range(1, 11):
            idx1.add_document(i, {"body": "alpha"})
        scorer = _make_scorer()
        idx1.build_block_max_scores("body", "alpha", scorer)
        conn1.close()

        conn2 = sqlite3.connect(db)
        idx2 = SQLiteInvertedIndex(conn2, "docs")

        scores = idx2.get_all_block_max_scores("body", "alpha")
        assert len(scores) == 1
        assert scores[0] > 0.0
        conn2.close()

    def test_load_block_max_into_memory_index(self, tmp_path):
        db = str(tmp_path / "persist.db")

        conn1 = sqlite3.connect(db)
        idx1 = SQLiteInvertedIndex(conn1, "docs")
        for i in range(1, 11):
            idx1.add_document(i, {"body": "alpha"})
        scorer = _make_scorer()
        idx1.build_block_max_scores("body", "alpha", scorer)

        bm_idx = BlockMaxIndex()
        idx1.load_block_max_into(bm_idx)
        conn1.close()

        # BlockMaxIndex should have the scores scoped by table name.
        assert bm_idx.num_blocks("body", "alpha", table_name="docs") == 1
        assert bm_idx.get_block_max("body", "alpha", 0, table_name="docs") > 0.0


# ======================================================================
# BlockMaxIndex SQLite persistence
# ======================================================================


class TestBlockMaxIndexPersistence:
    def test_save_and_load(self, tmp_path):
        db = str(tmp_path / "test.db")

        bm = BlockMaxIndex()
        bm._block_maxes[("articles", "body", "hello")] = [1.5, 2.3, 0.9]
        bm._block_maxes[("articles", "title", "world")] = [3.0]

        conn = sqlite3.connect(db)
        bm.save_to_sqlite(conn)
        conn.close()

        bm2 = BlockMaxIndex()
        conn2 = sqlite3.connect(db)
        bm2.load_from_sqlite(conn2)
        conn2.close()

        assert bm2.get_block_max("body", "hello", 0, table_name="articles") == 1.5
        assert bm2.get_block_max("body", "hello", 1, table_name="articles") == 2.3
        assert bm2.get_block_max("body", "hello", 2, table_name="articles") == 0.9
        assert bm2.get_block_max("title", "world", 0, table_name="articles") == 3.0
        assert bm2.num_blocks("body", "hello", table_name="articles") == 3
        assert bm2.num_blocks("title", "world", table_name="articles") == 1

    def test_save_and_load_multi_table_isolation(self, tmp_path):
        """Block-max scores from different tables must not collide."""
        db = str(tmp_path / "test.db")

        bm = BlockMaxIndex()
        bm._block_maxes[("articles", "body", "hello")] = [1.5]
        bm._block_maxes[("comments", "body", "hello")] = [9.9]

        conn = sqlite3.connect(db)
        bm.save_to_sqlite(conn)
        conn.close()

        bm2 = BlockMaxIndex()
        conn2 = sqlite3.connect(db)
        bm2.load_from_sqlite(conn2)
        conn2.close()

        assert bm2.get_block_max("body", "hello", 0, table_name="articles") == 1.5
        assert bm2.get_block_max("body", "hello", 0, table_name="comments") == 9.9

    def test_save_overwrites_previous(self, tmp_path):
        db = str(tmp_path / "test.db")

        conn = sqlite3.connect(db)

        bm1 = BlockMaxIndex()
        bm1._block_maxes[("", "body", "hello")] = [1.0]
        bm1.save_to_sqlite(conn)

        bm2 = BlockMaxIndex()
        bm2._block_maxes[("", "body", "hello")] = [9.9]
        bm2.save_to_sqlite(conn)

        bm3 = BlockMaxIndex()
        bm3.load_from_sqlite(conn)
        conn.close()

        assert bm3.get_block_max("body", "hello", 0) == 9.9
        assert bm3.num_blocks("body", "hello") == 1

    def test_load_from_empty_database(self, tmp_path):
        db = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db)

        bm = BlockMaxIndex()
        bm.load_from_sqlite(conn)
        conn.close()

        assert bm.num_blocks("body", "hello") == 0

    def test_load_legacy_schema_migration(self, tmp_path):
        """Old databases without table_name column should auto-migrate."""
        db = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE _global_blockmax ("
            "    field     TEXT    NOT NULL,"
            "    term      TEXT    NOT NULL,"
            "    block_idx INTEGER NOT NULL,"
            "    max_score REAL    NOT NULL,"
            "    PRIMARY KEY (field, term, block_idx)"
            ")"
        )
        conn.execute(
            "INSERT INTO _global_blockmax VALUES ('body', 'hello', 0, 2.5)"
        )
        conn.commit()

        bm = BlockMaxIndex()
        bm.load_from_sqlite(conn)
        conn.close()

        # Legacy rows are loaded with table_name=""
        assert bm.get_block_max("body", "hello", 0) == 2.5
        assert bm.num_blocks("body", "hello") == 1


# ======================================================================
# Integration: Engine with skip pointers and block-max
# ======================================================================


class TestEngineIntegration:
    def test_sql_table_has_skip_pointers(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, body TEXT)")
            for i in range(1, 200):
                engine.sql(
                    f"INSERT INTO docs (body) VALUES ('alpha term{i}')"
                )

            table = engine._tables["docs"]
            inv_idx = table.inverted_index

            # skip_to should work
            skip_doc, skip_off = inv_idx.skip_to("body", "alpha", 150)
            assert skip_doc > 0
            assert skip_off > 0

    def test_drop_table_cleans_skip_and_blockmax(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, body TEXT)")
            engine.sql("INSERT INTO docs (body) VALUES ('hello world')")

            # Verify tables exist.
            row = engine._catalog.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND (name LIKE '_skip_docs_%' OR name LIKE '_blockmax_docs_%')"
            ).fetchone()
            assert row[0] >= 2  # at least skip + blockmax for 'body'

            engine.sql("DROP TABLE docs")

            # Verify cleaned up.
            row = engine._catalog.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND (name LIKE '_skip_docs_%' OR name LIKE '_blockmax_docs_%')"
            ).fetchone()
            assert row[0] == 0


# ======================================================================
# Block size constant
# ======================================================================


class TestBlockSize:
    def test_default_block_size(self, tmp_path):
        idx = _make_index(tmp_path)
        assert idx.BLOCK_SIZE == 128
