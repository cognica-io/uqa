#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for DDL operations: ALTER TABLE, TRUNCATE, constraints, foreign keys."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_table(engine):
    engine.sql("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    engine.sql("INSERT INTO users (id, name, age) VALUES (3, 'Carol', 35)")
    return engine


# ==================================================================
# ALTER TABLE -- ADD COLUMN
# ==================================================================


class TestAlterTableAddColumn:
    def test_add_column(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users ADD COLUMN email TEXT")
        engine_with_table.sql("UPDATE users SET email = 'alice@test.com' WHERE id = 1")
        result = engine_with_table.sql("SELECT email FROM users WHERE id = 1")
        assert result.rows[0]["email"] == "alice@test.com"

    def test_add_column_duplicate_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="already exists"):
            engine_with_table.sql("ALTER TABLE users ADD COLUMN name TEXT")

    def test_add_column_with_default(self, engine_with_table):
        engine_with_table.sql(
            "ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT TRUE"
        )
        # New inserts should get the default
        engine_with_table.sql(
            "INSERT INTO users (id, name, age) VALUES (4, 'Dave', 28)"
        )
        result = engine_with_table.sql("SELECT active FROM users WHERE id = 4")
        assert result.rows[0]["active"] is True


# ==================================================================
# ALTER TABLE -- DROP COLUMN
# ==================================================================


class TestAlterTableDropColumn:
    def test_drop_column(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users DROP COLUMN age")
        result = engine_with_table.sql("SELECT name FROM users WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"
        # age should not be queryable
        result = engine_with_table.sql("SELECT * FROM users WHERE id = 1")
        assert "age" not in result.rows[0]

    def test_drop_column_nonexistent_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="does not exist"):
            engine_with_table.sql("ALTER TABLE users DROP COLUMN nonexistent")

    def test_drop_column_if_exists(self, engine_with_table):
        # Should not raise with IF EXISTS
        engine_with_table.sql("ALTER TABLE users DROP COLUMN IF EXISTS nonexistent")


# ==================================================================
# ALTER TABLE -- RENAME COLUMN
# ==================================================================


class TestAlterTableRenameColumn:
    def test_rename_column(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users RENAME COLUMN name TO full_name")
        result = engine_with_table.sql("SELECT full_name FROM users WHERE id = 1")
        assert result.rows[0]["full_name"] == "Alice"

    def test_rename_column_nonexistent_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="does not exist"):
            engine_with_table.sql("ALTER TABLE users RENAME COLUMN xyz TO abc")

    def test_rename_column_duplicate_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="already exists"):
            engine_with_table.sql("ALTER TABLE users RENAME COLUMN name TO age")


# ==================================================================
# ALTER TABLE -- RENAME TO
# ==================================================================


class TestAlterTableRenameTo:
    def test_rename_table(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users RENAME TO people")
        result = engine_with_table.sql("SELECT COUNT(*) AS cnt FROM people")
        assert result.rows[0]["cnt"] == 3
        with pytest.raises(ValueError, match="does not exist"):
            engine_with_table.sql("SELECT * FROM users")

    def test_rename_table_duplicate_raises(self, engine_with_table):
        engine_with_table.sql("CREATE TABLE other (id INTEGER)")
        with pytest.raises(ValueError, match="already exists"):
            engine_with_table.sql("ALTER TABLE users RENAME TO other")


# ==================================================================
# ALTER TABLE -- SET/DROP DEFAULT
# ==================================================================


class TestAlterTableDefault:
    def test_set_default(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users ALTER COLUMN age SET DEFAULT 18")
        engine_with_table.sql("INSERT INTO users (id, name) VALUES (4, 'Dave')")
        result = engine_with_table.sql("SELECT age FROM users WHERE id = 4")
        assert result.rows[0]["age"] == 18

    def test_drop_default(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users ALTER COLUMN age SET DEFAULT 18")
        engine_with_table.sql("ALTER TABLE users ALTER COLUMN age DROP DEFAULT")
        engine_with_table.sql("INSERT INTO users (id, name) VALUES (5, 'Eve')")
        result = engine_with_table.sql("SELECT age FROM users WHERE id = 5")
        # No default -- age should be absent
        assert result.rows[0].get("age") is None


# ==================================================================
# ALTER TABLE -- SET/DROP NOT NULL
# ==================================================================


class TestAlterTableNotNull:
    def test_set_not_null(self, engine_with_table):
        engine_with_table.sql("ALTER TABLE users ALTER COLUMN name SET NOT NULL")
        with pytest.raises(ValueError, match="NOT NULL"):
            engine_with_table.sql("INSERT INTO users (id, age) VALUES (4, 28)")

    def test_set_not_null_with_existing_nulls_raises(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        with pytest.raises(ValueError, match="contains NULL"):
            engine.sql("ALTER TABLE t ALTER COLUMN val SET NOT NULL")

    def test_drop_not_null(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, val TEXT NOT NULL)")
        engine.sql("ALTER TABLE t ALTER COLUMN val DROP NOT NULL")
        # Should now allow NULL
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert result.rows[0].get("val") is None


# ==================================================================
# TRUNCATE TABLE
# ==================================================================


class TestTruncateTable:
    def test_truncate_basic(self, engine_with_table):
        engine_with_table.sql("TRUNCATE TABLE users")
        result = engine_with_table.sql("SELECT COUNT(*) AS cnt FROM users")
        assert result.rows[0]["cnt"] == 0

    def test_truncate_resets_auto_increment(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t (val) VALUES ('a')")
        engine.sql("INSERT INTO t (val) VALUES ('b')")
        engine.sql("TRUNCATE TABLE t")
        engine.sql("INSERT INTO t (val) VALUES ('c')")
        result = engine.sql("SELECT id FROM t")
        assert result.rows[0]["id"] == 1

    def test_truncate_preserves_schema(self, engine_with_table):
        engine_with_table.sql("TRUNCATE TABLE users")
        # Schema should still be intact
        engine_with_table.sql("INSERT INTO users (id, name, age) VALUES (1, 'New', 20)")
        result = engine_with_table.sql("SELECT name FROM users WHERE id = 1")
        assert result.rows[0]["name"] == "New"

    def test_truncate_nonexistent_raises(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("TRUNCATE TABLE nonexistent")


# ==================================================================
# UNIQUE constraint
# ==================================================================


class TestUniqueConstraint:
    def test_unique_basic(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, email TEXT UNIQUE)")
        engine.sql("INSERT INTO t (id, email) VALUES (1, 'a@test.com')")
        with pytest.raises(ValueError, match="UNIQUE constraint"):
            engine.sql("INSERT INTO t (id, email) VALUES (2, 'a@test.com')")

    def test_unique_allows_different_values(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, email TEXT UNIQUE)")
        engine.sql("INSERT INTO t (id, email) VALUES (1, 'a@test.com')")
        engine.sql("INSERT INTO t (id, email) VALUES (2, 'b@test.com')")
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2

    def test_unique_allows_null(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, email TEXT UNIQUE)")
        engine.sql("INSERT INTO t (id, email) VALUES (1, 'a@test.com')")
        engine.sql("INSERT INTO t (id) VALUES (2)")
        engine.sql("INSERT INTO t (id) VALUES (3)")
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 3

    def test_primary_key_enforces_uniqueness(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO t (id, val) VALUES (1, 'a')")
        with pytest.raises(ValueError, match="UNIQUE constraint"):
            engine.sql("INSERT INTO t (id, val) VALUES (1, 'b')")


# ==================================================================
# CHECK constraint
# ==================================================================


class TestCheckConstraint:
    def test_check_basic(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, age INTEGER CHECK (age > 0))")
        engine.sql("INSERT INTO t (id, age) VALUES (1, 25)")
        with pytest.raises(ValueError, match="CHECK constraint"):
            engine.sql("INSERT INTO t (id, age) VALUES (2, -1)")

    def test_check_allows_valid(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, age INTEGER CHECK (age > 0))")
        engine.sql("INSERT INTO t (id, age) VALUES (1, 1)")
        engine.sql("INSERT INTO t (id, age) VALUES (2, 100)")
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2

    def test_check_with_comparison(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER, price REAL CHECK (price >= 0.0))")
        engine.sql("INSERT INTO t (id, price) VALUES (1, 9.99)")
        with pytest.raises(ValueError, match="CHECK constraint"):
            engine.sql("INSERT INTO t (id, price) VALUES (2, -0.01)")


# ==================================================================
# ALTER TABLE -- ALTER COLUMN TYPE
# ==================================================================


class TestAlterColumnType:
    def test_change_type(self, engine_with_table):
        engine_with_table.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER, name TEXT)"
        )
        engine_with_table.sql("INSERT INTO t (id, val, name) VALUES (1, 10, 'alpha')")
        engine_with_table.sql("INSERT INTO t (id, val, name) VALUES (2, 20, 'bravo')")
        engine_with_table.sql("INSERT INTO t (id, val, name) VALUES (3, 30, 'charlie')")
        engine_with_table.sql("ALTER TABLE t ALTER COLUMN val TYPE TEXT")
        result = engine_with_table.sql("SELECT val FROM t WHERE id = 1")
        assert isinstance(result.rows[0]["val"], str)
        assert result.rows[0]["val"] == "10"


# ==================================================================
# FOREIGN KEY constraint
# ==================================================================


class TestForeignKey:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE parents (id INT PRIMARY KEY, name TEXT)")
        e.sql("INSERT INTO parents VALUES (1, 'Parent1')")
        e.sql("INSERT INTO parents VALUES (2, 'Parent2')")
        yield e

    def test_basic_fk_insert(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        r = engine.sql("SELECT id, parent_id, val FROM children")
        assert len(r.rows) == 1
        assert r.rows[0]["parent_id"] == 1

    def test_fk_insert_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        with pytest.raises(ValueError, match="FOREIGN KEY constraint violated"):
            engine.sql("INSERT INTO children VALUES (1, 999, 'bad')")

    def test_fk_null_allowed(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        # NULL FK should be allowed
        engine.sql("INSERT INTO children VALUES (1, NULL, 'orphan')")
        r = engine.sql("SELECT id, parent_id, val FROM children")
        assert len(r.rows) == 1
        assert r.rows[0]["parent_id"] is None

    def test_fk_delete_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(ValueError, match="FOREIGN KEY constraint violated"):
            engine.sql("DELETE FROM parents WHERE id = 1")

    def test_fk_delete_unreferenced(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        # Deleting parent 2 (not referenced) should work
        engine.sql("DELETE FROM parents WHERE id = 2")
        r = engine.sql("SELECT id, name FROM parents")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 1

    def test_fk_update_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(ValueError, match="FOREIGN KEY constraint violated"):
            engine.sql("UPDATE children SET parent_id = 999 WHERE id = 1")

    def test_fk_update_valid(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        engine.sql("UPDATE children SET parent_id = 2 WHERE id = 1")
        r = engine.sql("SELECT parent_id FROM children WHERE id = 1")
        assert r.rows[0]["parent_id"] == 2

    def test_fk_update_parent_pk_violation(self, engine):
        """Updating a referenced parent PK should be rejected."""
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(ValueError, match="FOREIGN KEY constraint violated"):
            engine.sql("UPDATE parents SET id = 99 WHERE id = 1")
