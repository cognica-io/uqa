#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""User-level transaction with savepoint support.

A ``Transaction`` wraps a :class:`ManagedConnection` and provides
explicit ``commit()`` / ``rollback()`` semantics.  While active, all
store-level auto-commits are suppressed by the connection proxy.

Usage::

    txn = engine.begin()
    try:
        engine.sql("INSERT INTO t (x) VALUES (1)")
        engine.sql("INSERT INTO t (x) VALUES (2)")
        txn.commit()
    except Exception:
        txn.rollback()
        raise

Or as a context manager (auto-rollback on exception)::

    with engine.begin() as txn:
        engine.sql("INSERT INTO t (x) VALUES (1)")
        engine.sql("INSERT INTO t (x) VALUES (2)")
        txn.commit()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.storage.managed_connection import ManagedConnection


class Transaction:
    """Explicit user transaction over a managed SQLite connection."""

    def __init__(self, conn: ManagedConnection) -> None:
        self._conn = conn
        self._finished = False
        self._conn.begin_transaction()

    @property
    def active(self) -> bool:
        return not self._finished

    def commit(self) -> None:
        """Commit the transaction."""
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._conn.commit_transaction()
        self._finished = True

    def rollback(self) -> None:
        """Rollback the transaction."""
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._conn.rollback_transaction()
        self._finished = True

    # -- Savepoints (nested transactions) ------------------------------

    def savepoint(self, name: str) -> None:
        """Create a savepoint within this transaction."""
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._conn.savepoint(name)

    def release_savepoint(self, name: str) -> None:
        """Release (commit) a savepoint."""
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._conn.release_savepoint(name)

    def rollback_to(self, name: str) -> None:
        """Rollback to a savepoint (undo work since savepoint)."""
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._conn.rollback_to_savepoint(name)

    # -- Context manager -----------------------------------------------

    def __enter__(self) -> Transaction:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        if not self._finished:
            self.rollback()
        return False
