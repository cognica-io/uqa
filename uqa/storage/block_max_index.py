#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.posting_list import PostingList
    from uqa.scoring.bm25 import BM25Scorer
    from uqa.storage.managed_connection import SQLiteConnection


class BlockMaxIndex:
    """Per-block maximum score index for BMW optimization.

    Storage: O(|PostingList| / B * |Terms|) -- Theorem 6.2.2, Paper 3.
    """

    def __init__(self, block_size: int = 128) -> None:
        self.block_size = block_size
        self._block_maxes: dict[tuple[str, str, str], list[float]] = {}

    def build(
        self,
        posting_list: PostingList,
        scorer: BM25Scorer,
        field: str,
        term: str,
        table_name: str = "",
    ) -> None:
        """Compute per-block max scores for a posting list."""
        entries = posting_list.entries
        if not entries:
            self._block_maxes[(table_name, field, term)] = []
            return

        doc_freq = len(entries)
        block_maxes: list[float] = []

        for block_start in range(0, len(entries), self.block_size):
            block_end = min(block_start + self.block_size, len(entries))
            block_entries = entries[block_start:block_end]
            max_score = 0.0
            for entry in block_entries:
                tf = len(entry.payload.positions) if entry.payload.positions else 1
                score = scorer.score(tf, tf, doc_freq)
                max_score = max(max_score, score)
            block_maxes.append(max_score)

        self._block_maxes[(table_name, field, term)] = block_maxes

    def get_block_max(
        self, field: str, term: str, block_idx: int, table_name: str = ""
    ) -> float:
        """Return max score for a given block."""
        maxes = self._block_maxes.get((table_name, field, term))
        if maxes is None or block_idx >= len(maxes):
            return 0.0
        return maxes[block_idx]

    def num_blocks(self, field: str, term: str, table_name: str = "") -> int:
        maxes = self._block_maxes.get((table_name, field, term))
        if maxes is None:
            return 0
        return len(maxes)

    # -- SQLite persistence --------------------------------------------

    def save_to_sqlite(self, conn: SQLiteConnection) -> None:
        """Persist all block-max scores to a ``_global_blockmax`` table."""
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _global_blockmax ("
            "    table_name TEXT    NOT NULL,"
            "    field      TEXT    NOT NULL,"
            "    term       TEXT    NOT NULL,"
            "    block_idx  INTEGER NOT NULL,"
            "    max_score  REAL    NOT NULL,"
            "    PRIMARY KEY (table_name, field, term, block_idx)"
            ")"
        )
        conn.execute("DELETE FROM _global_blockmax")
        for (table_name, field, term), maxes in self._block_maxes.items():
            for block_idx, max_score in enumerate(maxes):
                conn.execute(
                    "INSERT INTO _global_blockmax "
                    "(table_name, field, term, block_idx, max_score) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (table_name, field, term, block_idx, max_score),
                )
        conn.commit()

    def load_from_sqlite(self, conn: SQLiteConnection) -> None:
        """Load block-max scores from the ``_global_blockmax`` table."""
        # Check if table exists.
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='_global_blockmax'"
        ).fetchone()
        if row is None:
            return

        # Detect legacy schema (without table_name column) and migrate.
        col_info = conn.execute("PRAGMA table_info(_global_blockmax)").fetchall()
        col_names = {r[1] for r in col_info}
        if "table_name" not in col_names:
            self._migrate_legacy_blockmax(conn)
            return

        rows = conn.execute(
            "SELECT table_name, field, term, block_idx, max_score "
            "FROM _global_blockmax "
            "ORDER BY table_name, field, term, block_idx"
        ).fetchall()

        current_key: tuple[str, str, str] | None = None
        scores: list[float] = []
        for table_name, field, term, _block_idx, max_score in rows:
            key = (table_name, field, term)
            if key != current_key:
                if current_key is not None:
                    self._block_maxes[current_key] = scores
                current_key = key
                scores = []
            scores.append(max_score)
        if current_key is not None:
            self._block_maxes[current_key] = scores

    def _migrate_legacy_blockmax(self, conn: SQLiteConnection) -> None:
        """Migrate old _global_blockmax (without table_name) to new schema."""
        rows = conn.execute(
            "SELECT field, term, block_idx, max_score "
            "FROM _global_blockmax ORDER BY field, term, block_idx"
        ).fetchall()

        conn.execute("DROP TABLE _global_blockmax")
        conn.execute(
            "CREATE TABLE _global_blockmax ("
            "    table_name TEXT    NOT NULL,"
            "    field      TEXT    NOT NULL,"
            "    term       TEXT    NOT NULL,"
            "    block_idx  INTEGER NOT NULL,"
            "    max_score  REAL    NOT NULL,"
            "    PRIMARY KEY (table_name, field, term, block_idx)"
            ")"
        )

        current_key: tuple[str, str] | None = None
        scores: list[float] = []
        for field, term, block_idx, max_score in rows:
            key = (field, term)
            if key != current_key:
                if current_key is not None:
                    self._block_maxes[("", *current_key)] = scores
                current_key = key
                scores = []
            scores.append(max_score)
            conn.execute(
                "INSERT INTO _global_blockmax "
                "(table_name, field, term, block_idx, max_score) "
                "VALUES (?, ?, ?, ?, ?)",
                ("", field, term, block_idx, max_score),
            )
        if current_key is not None:
            self._block_maxes[("", *current_key)] = scores
        conn.commit()
