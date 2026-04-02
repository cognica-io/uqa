#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Phase 3: Transaction Manager.

Covers:
- ManagedConnection commit suppression
- Transaction class (commit, rollback, context manager)
- Savepoint support
- SQL-level BEGIN / COMMIT / ROLLBACK
- SQL-level SAVEPOINT / RELEASE / ROLLBACK TO
- Transaction atomicity (all-or-nothing)
- Engine integration
"""

from __future__ import annotations

import sqlite3

import pytest

from uqa.storage.managed_connection import ManagedConnection
from uqa.storage.transaction import Transaction

# ======================================================================
# ManagedConnection
# ======================================================================


class TestManagedConnection:
    def test_commit_forwarded_when_no_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()

        # Value should be committed
        row = raw.execute("SELECT x FROM t").fetchone()
        assert row[0] == 1
        raw.close()

    def test_commit_suppressed_during_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.begin_transaction()
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()  # Should be suppressed

        assert conn.in_transaction

        # Verify via a second connection that the insert is NOT yet visible
        raw2 = sqlite3.connect(db)
        row = raw2.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        raw2.close()

        conn.commit_transaction()
        assert not conn.in_transaction
        raw.close()

    def test_rollback_suppressed_during_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.begin_transaction()
        conn.execute("INSERT INTO t VALUES (1)")
        conn.rollback()  # Should be suppressed

        assert conn.in_transaction
        conn.commit_transaction()

        row = raw.execute("SELECT x FROM t").fetchone()
        assert row[0] == 1
        raw.close()

    def test_rollback_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.begin_transaction()
        conn.execute("INSERT INTO t VALUES (42)")
        conn.rollback_transaction()

        row = raw.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        raw.close()

    def test_savepoint(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.begin_transaction()
        conn.execute("INSERT INTO t VALUES (1)")
        conn.savepoint("sp1")
        conn.execute("INSERT INTO t VALUES (2)")
        conn.rollback_to_savepoint("sp1")
        conn.commit_transaction()

        rows = raw.execute("SELECT x FROM t ORDER BY x").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        raw.close()

    def test_release_savepoint(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        conn.begin_transaction()
        conn.execute("INSERT INTO t VALUES (1)")
        conn.savepoint("sp1")
        conn.execute("INSERT INTO t VALUES (2)")
        conn.release_savepoint("sp1")
        conn.commit_transaction()

        rows = raw.execute("SELECT x FROM t ORDER BY x").fetchall()
        assert len(rows) == 2
        raw.close()

    def test_getattr_proxies_to_raw(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        conn = ManagedConnection(raw)

        # total_changes is a property of sqlite3.Connection
        assert conn.total_changes == raw.total_changes
        raw.close()


# ======================================================================
# Transaction Class
# ======================================================================


class TestTransaction:
    def test_commit(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        txn = Transaction(conn)
        conn.execute("INSERT INTO t VALUES (1)")
        txn.commit()

        assert not txn.active
        row = raw.execute("SELECT x FROM t").fetchone()
        assert row[0] == 1
        raw.close()

    def test_rollback(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        txn = Transaction(conn)
        conn.execute("INSERT INTO t VALUES (1)")
        txn.rollback()

        assert not txn.active
        row = raw.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        raw.close()

    def test_context_manager_commit(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        with Transaction(conn) as txn:
            conn.execute("INSERT INTO t VALUES (1)")
            txn.commit()

        row = raw.execute("SELECT x FROM t").fetchone()
        assert row[0] == 1
        raw.close()

    def test_context_manager_auto_rollback(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        with Transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            # No commit -- should auto-rollback on exit

        row = raw.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        raw.close()

    def test_context_manager_rollback_on_exception(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        with pytest.raises(RuntimeError), Transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("test error")

        row = raw.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        raw.close()

    def test_double_commit_raises(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        conn = ManagedConnection(raw)

        txn = Transaction(conn)
        txn.commit()
        with pytest.raises(RuntimeError, match="already finished"):
            txn.commit()
        raw.close()

    def test_double_rollback_raises(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        conn = ManagedConnection(raw)

        txn = Transaction(conn)
        txn.rollback()
        with pytest.raises(RuntimeError, match="already finished"):
            txn.rollback()
        raw.close()

    def test_savepoint_in_transaction(self, tmp_path):
        db = str(tmp_path / "test.db")
        raw = sqlite3.connect(db)
        raw.execute("CREATE TABLE t (x INTEGER)")
        raw.commit()
        conn = ManagedConnection(raw)

        txn = Transaction(conn)
        conn.execute("INSERT INTO t VALUES (1)")
        txn.savepoint("sp1")
        conn.execute("INSERT INTO t VALUES (2)")
        txn.rollback_to("sp1")
        txn.commit()

        rows = raw.execute("SELECT x FROM t ORDER BY x").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        raw.close()


# ======================================================================
# SQL Transaction Statements
# ======================================================================


class TestSQLTransactions:
    def test_begin_commit(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("COMMIT")

            result = engine.sql("SELECT x FROM t ORDER BY x")
            assert [r["x"] for r in result] == [1, 2]

    def test_begin_rollback(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("INSERT INTO t (x) VALUES (0)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("ROLLBACK")

            result = engine.sql("SELECT x FROM t")
            assert len(result) == 1
            assert result.rows[0]["x"] == 0

    def test_rollback_survives_close_reopen(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("INSERT INTO t (x) VALUES (0)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("ROLLBACK")

        with Engine(db_path=db) as engine:
            result = engine.sql("SELECT x FROM t")
            assert len(result) == 1

    def test_commit_survives_close_reopen(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("COMMIT")

        with Engine(db_path=db) as engine:
            result = engine.sql("SELECT x FROM t ORDER BY x")
            assert len(result) == 2

    def test_savepoint(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("SAVEPOINT sp1")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("ROLLBACK TO SAVEPOINT sp1")
            engine.sql("INSERT INTO t (x) VALUES (3)")
            engine.sql("COMMIT")

            result = engine.sql("SELECT x FROM t ORDER BY x")
            values = [r["x"] for r in result]
            assert values == [1, 3]

    def test_release_savepoint(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("SAVEPOINT sp1")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("RELEASE SAVEPOINT sp1")
            engine.sql("COMMIT")

            result = engine.sql("SELECT x FROM t ORDER BY x")
            assert len(result) == 2

    def test_begin_without_db_path_works(self):
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("BEGIN")
        engine.sql("COMMIT")

    def test_commit_without_begin_raises(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with (
            Engine(db_path=db) as engine,
            pytest.raises(ValueError, match="No active transaction"),
        ):
            engine.sql("COMMIT")

    def test_rollback_without_begin_raises(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with (
            Engine(db_path=db) as engine,
            pytest.raises(ValueError, match="No active transaction"),
        ):
            engine.sql("ROLLBACK")

    def test_double_begin_raises(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("BEGIN")
            with pytest.raises(ValueError, match="already active"):
                engine.sql("BEGIN")
            engine.sql("ROLLBACK")

    def test_nested_savepoints(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("BEGIN")
            engine.sql("INSERT INTO t (x) VALUES (1)")
            engine.sql("SAVEPOINT sp1")
            engine.sql("INSERT INTO t (x) VALUES (2)")
            engine.sql("SAVEPOINT sp2")
            engine.sql("INSERT INTO t (x) VALUES (3)")
            engine.sql("ROLLBACK TO SAVEPOINT sp2")
            engine.sql("RELEASE SAVEPOINT sp1")
            engine.sql("COMMIT")

            result = engine.sql("SELECT x FROM t ORDER BY x")
            values = [r["x"] for r in result]
            assert values == [1, 2]


# ======================================================================
# Engine.begin() API
# ======================================================================


class TestEngineBeginAPI:
    def test_begin_returns_transaction(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            txn = engine.begin()
            assert txn.active
            txn.rollback()

    def test_begin_commit_via_api(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")

            txn = engine.begin()
            engine.sql("INSERT INTO t (x) VALUES (10)")
            engine.sql("INSERT INTO t (x) VALUES (20)")
            txn.commit()

            result = engine.sql("SELECT x FROM t ORDER BY x")
            assert [r["x"] for r in result] == [10, 20]

    def test_begin_rollback_via_api(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("INSERT INTO t (x) VALUES (0)")

            txn = engine.begin()
            engine.sql("INSERT INTO t (x) VALUES (10)")
            txn.rollback()

            result = engine.sql("SELECT x FROM t")
            assert len(result) == 1

    def test_context_manager_auto_rollback(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        with Engine(db_path=db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
            engine.sql("INSERT INTO t (x) VALUES (0)")

            with engine.begin():
                engine.sql("INSERT INTO t (x) VALUES (10)")
                # No commit -> auto-rollback

            result = engine.sql("SELECT x FROM t")
            assert len(result) == 1

    def test_close_rollbacks_active_transaction(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        engine = Engine(db_path=db)
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, x INTEGER)")
        engine.sql("INSERT INTO t (x) VALUES (0)")
        engine.begin()
        engine.sql("INSERT INTO t (x) VALUES (10)")
        engine.close()

        with Engine(db_path=db) as engine2:
            result = engine2.sql("SELECT x FROM t")
            assert len(result) == 1

    def test_in_memory_begin_returns_transaction(self):
        from uqa.engine import Engine
        from uqa.storage.transaction import InMemoryTransaction

        engine = Engine()
        txn = engine.begin()
        assert isinstance(txn, InMemoryTransaction)
        assert txn.active
        txn.commit()
        assert not txn.active

    def test_in_memory_rollback_restores_data(self):
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t VALUES (1, 'original')")
        txn = engine.begin()
        engine.sql("INSERT INTO t VALUES (2, 'rolled_back')")
        txn.rollback()
        result = engine.sql("SELECT * FROM t")
        assert len(result.rows) == 1
        assert result.rows[0]["val"] == "original"
