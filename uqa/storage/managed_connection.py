#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Connection proxy that suppresses auto-commits during user transactions.

All SQLite-backed stores (``SQLiteDocumentStore``, ``SQLiteInvertedIndex``,
``SQLiteGraphStore``, ``SQLiteVectorIndex``) call ``conn.commit()`` after
every write.  During a user transaction (``BEGIN`` ... ``COMMIT``), these
auto-commits must be suppressed so the user controls transaction
boundaries.

``ManagedConnection`` wraps a raw ``sqlite3.Connection`` and:

- Forwards all attribute access to the raw connection via ``__getattr__``
- Overrides ``commit()`` to become a no-op during user transactions
- Provides ``begin_transaction()`` / ``commit_transaction()`` /
  ``rollback_transaction()`` for explicit user-level control
- Provides ``savepoint()`` / ``release_savepoint()`` /
  ``rollback_to_savepoint()`` for nested transaction support
"""

from __future__ import annotations

import sqlite3


class ManagedConnection:
    """Proxy around ``sqlite3.Connection`` with transaction suppression."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw
        self._in_transaction = False

    # -- Proxy all unhandled attributes to the raw connection -----------

    def __getattr__(self, name: str) -> object:
        return getattr(self._raw, name)

    # -- Override commit/rollback to respect transaction state ----------

    def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
        return self._raw.execute(sql, parameters)

    def executemany(
        self, sql: str, parameters: object
    ) -> sqlite3.Cursor:
        return self._raw.executemany(sql, parameters)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        return self._raw.executescript(sql)

    def commit(self) -> None:
        """Commit unless inside a user transaction."""
        if not self._in_transaction:
            self._raw.commit()

    def rollback(self) -> None:
        """Rollback unless inside a user transaction.

        During a user transaction, individual statement errors should
        not rollback the entire transaction -- the user decides via
        explicit ``COMMIT`` or ``ROLLBACK``.
        """
        if not self._in_transaction:
            self._raw.rollback()

    # -- User-level transaction control --------------------------------

    @property
    def in_transaction(self) -> bool:
        return self._in_transaction

    def begin_transaction(self) -> None:
        """Start an explicit user transaction (``BEGIN IMMEDIATE``)."""
        self._raw.execute("BEGIN IMMEDIATE")
        self._in_transaction = True

    def commit_transaction(self) -> None:
        """Commit the user transaction."""
        self._raw.commit()
        self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback the user transaction."""
        self._raw.rollback()
        self._in_transaction = False

    # -- Savepoint support (nested transactions) -----------------------

    def savepoint(self, name: str) -> None:
        self._raw.execute(f'SAVEPOINT "{name}"')

    def release_savepoint(self, name: str) -> None:
        self._raw.execute(f'RELEASE SAVEPOINT "{name}"')

    def rollback_to_savepoint(self, name: str) -> None:
        self._raw.execute(f'ROLLBACK TO SAVEPOINT "{name}"')

    # -- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._raw.close()
