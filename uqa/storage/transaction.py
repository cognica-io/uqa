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

import copy
from typing import TYPE_CHECKING, Any

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


class _TableSnapshot:
    """Snapshot of a single table's mutable state."""

    __slots__ = ("documents", "next_id", "unique_indexes")

    def __init__(
        self,
        documents: dict[int, dict],
        next_id: int,
        unique_indexes: dict[str, dict[Any, int]],
    ) -> None:
        self.documents = documents
        self.next_id = next_id
        self.unique_indexes = unique_indexes


def _snapshot_tables(tables: Any) -> dict[str, _TableSnapshot]:
    """Deep-copy mutable state of all in-memory tables.

    Uses qualified keys (``schema.table``) to avoid collisions when
    multiple schemas contain tables with the same name.
    """
    snapshots: dict[str, _TableSnapshot] = {}
    if hasattr(tables, "qualified_items"):
        items = ((f"{s}.{n}", t) for s, n, t in tables.qualified_items())
    else:
        items = tables.items()
    for key, table in items:
        store = table.document_store
        docs = copy.deepcopy(getattr(store, "_documents", {}))
        unique = copy.deepcopy(getattr(table, "_unique_indexes", {}))
        snapshots[key] = _TableSnapshot(
            documents=docs,
            next_id=getattr(table, "_next_id", 1),
            unique_indexes=unique,
        )
    return snapshots


def _restore_tables(tables: Any, snapshots: dict[str, _TableSnapshot]) -> None:
    """Restore table state from snapshots."""
    for key, snap in snapshots.items():
        table = tables.get(key)
        if table is None:
            continue
        store = table.document_store
        if hasattr(store, "_documents"):
            store._documents = snap.documents
        table._next_id = snap.next_id
        table._unique_indexes = snap.unique_indexes
        table._unique_indexes_built = bool(snap.unique_indexes)


class InMemoryTransaction:
    """Transaction for in-memory engines with real rollback support.

    On ``begin``, snapshots all table document stores.  ``rollback()``
    restores the snapshot, discarding all writes since ``begin``.
    ``commit()`` discards the snapshot, making writes permanent.

    Savepoints create nested snapshots on a stack.
    """

    def __init__(self, tables: Any) -> None:
        self._tables = tables
        self._finished = False
        self._snapshot = _snapshot_tables(tables)
        self._savepoints: dict[str, dict[str, _TableSnapshot]] = {}

    @property
    def active(self) -> bool:
        return not self._finished

    def commit(self) -> None:
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._snapshot = {}
        self._savepoints.clear()
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            raise RuntimeError("Transaction already finished")
        _restore_tables(self._tables, self._snapshot)
        self._snapshot = {}
        self._savepoints.clear()
        self._finished = True

    def savepoint(self, name: str) -> None:
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._savepoints[name] = _snapshot_tables(self._tables)

    def release_savepoint(self, name: str) -> None:
        if self._finished:
            raise RuntimeError("Transaction already finished")
        self._savepoints.pop(name, None)

    def rollback_to(self, name: str) -> None:
        if self._finished:
            raise RuntimeError("Transaction already finished")
        snap = self._savepoints.get(name)
        if snap is None:
            raise ValueError(f"Savepoint '{name}' does not exist")
        _restore_tables(self._tables, snap)

    def __enter__(self) -> InMemoryTransaction:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        if not self._finished:
            self.rollback()
        return False
