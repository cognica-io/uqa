#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for PostgreSQL 17 P1 feature compatibility."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


@pytest.fixture
def engine_with_table(engine):
    engine.sql(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
    )
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
        engine_with_table.sql(
            "UPDATE users SET email = 'alice@test.com' WHERE id = 1"
        )
        result = engine_with_table.sql(
            "SELECT email FROM users WHERE id = 1"
        )
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
        result = engine_with_table.sql(
            "SELECT active FROM users WHERE id = 4"
        )
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
            engine_with_table.sql(
                "ALTER TABLE users DROP COLUMN nonexistent"
            )

    def test_drop_column_if_exists(self, engine_with_table):
        # Should not raise with IF EXISTS
        engine_with_table.sql(
            "ALTER TABLE users DROP COLUMN IF EXISTS nonexistent"
        )


# ==================================================================
# ALTER TABLE -- RENAME COLUMN
# ==================================================================


class TestAlterTableRenameColumn:
    def test_rename_column(self, engine_with_table):
        engine_with_table.sql(
            "ALTER TABLE users RENAME COLUMN name TO full_name"
        )
        result = engine_with_table.sql(
            "SELECT full_name FROM users WHERE id = 1"
        )
        assert result.rows[0]["full_name"] == "Alice"

    def test_rename_column_nonexistent_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="does not exist"):
            engine_with_table.sql(
                "ALTER TABLE users RENAME COLUMN xyz TO abc"
            )

    def test_rename_column_duplicate_raises(self, engine_with_table):
        with pytest.raises(ValueError, match="already exists"):
            engine_with_table.sql(
                "ALTER TABLE users RENAME COLUMN name TO age"
            )


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
        engine_with_table.sql(
            "ALTER TABLE users ALTER COLUMN age SET DEFAULT 18"
        )
        engine_with_table.sql(
            "INSERT INTO users (id, name) VALUES (4, 'Dave')"
        )
        result = engine_with_table.sql(
            "SELECT age FROM users WHERE id = 4"
        )
        assert result.rows[0]["age"] == 18

    def test_drop_default(self, engine_with_table):
        engine_with_table.sql(
            "ALTER TABLE users ALTER COLUMN age SET DEFAULT 18"
        )
        engine_with_table.sql(
            "ALTER TABLE users ALTER COLUMN age DROP DEFAULT"
        )
        engine_with_table.sql(
            "INSERT INTO users (id, name) VALUES (5, 'Eve')"
        )
        result = engine_with_table.sql(
            "SELECT age FROM users WHERE id = 5"
        )
        # No default -- age should be absent
        assert result.rows[0].get("age") is None


# ==================================================================
# ALTER TABLE -- SET/DROP NOT NULL
# ==================================================================


class TestAlterTableNotNull:
    def test_set_not_null(self, engine_with_table):
        engine_with_table.sql(
            "ALTER TABLE users ALTER COLUMN name SET NOT NULL"
        )
        with pytest.raises(ValueError, match="NOT NULL"):
            engine_with_table.sql(
                "INSERT INTO users (id, age) VALUES (4, 28)"
            )

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
        engine_with_table.sql(
            "INSERT INTO users (id, name, age) VALUES (1, 'New', 20)"
        )
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
        engine.sql(
            "CREATE TABLE t (id INTEGER, price REAL CHECK (price >= 0.0))"
        )
        engine.sql("INSERT INTO t (id, price) VALUES (1, 9.99)")
        with pytest.raises(ValueError, match="CHECK constraint"):
            engine.sql("INSERT INTO t (id, price) VALUES (2, -0.01)")


# ==================================================================
# INSERT ... RETURNING
# ==================================================================


class TestInsertReturning:
    def test_returning_star(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
        )
        result = engine.sql(
            "INSERT INTO t (id, name, age) VALUES (1, 'Alice', 30) "
            "RETURNING *"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[0]["age"] == 30

    def test_returning_specific_columns(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
        )
        result = engine.sql(
            "INSERT INTO t (id, name, age) VALUES (1, 'Alice', 30) "
            "RETURNING id, name"
        )
        assert result.columns == ["id", "name"]
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        assert "age" not in result.rows[0]

    def test_returning_with_alias(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        result = engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice') "
            "RETURNING id AS user_id, name AS user_name"
        )
        assert result.rows[0]["user_id"] == 1
        assert result.rows[0]["user_name"] == "Alice"

    def test_returning_multi_row(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        result = engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice'), (2, 'Bob') "
            "RETURNING id, name"
        )
        assert len(result.rows) == 2
        ids = [r["id"] for r in result.rows]
        assert 1 in ids
        assert 2 in ids

    def test_returning_serial(self, engine):
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
        result = engine.sql(
            "INSERT INTO t (name) VALUES ('Alice') RETURNING id"
        )
        assert result.rows[0]["id"] == 1


# ==================================================================
# UPDATE ... RETURNING
# ==================================================================


class TestUpdateReturning:
    def test_returning_updated_values(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 31 WHERE id = 1 RETURNING id, age"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["age"] == 31

    def test_returning_star(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 99 WHERE id = 2 RETURNING *"
        )
        assert result.rows[0]["id"] == 2
        assert result.rows[0]["name"] == "Bob"
        assert result.rows[0]["age"] == 99

    def test_returning_multiple_rows(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = age + 1 WHERE age < 35 "
            "RETURNING id, age"
        )
        assert len(result.rows) == 2
        for row in result.rows:
            if row["id"] == 1:
                assert row["age"] == 31
            elif row["id"] == 2:
                assert row["age"] == 26

    def test_returning_no_match(self, engine_with_table):
        result = engine_with_table.sql(
            "UPDATE users SET age = 0 WHERE id = 999 RETURNING id"
        )
        assert len(result.rows) == 0


# ==================================================================
# DELETE ... RETURNING
# ==================================================================


class TestDeleteReturning:
    def test_returning_deleted_row(self, engine_with_table):
        result = engine_with_table.sql(
            "DELETE FROM users WHERE id = 1 RETURNING *"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        # Verify row is actually gone
        check = engine_with_table.sql(
            "SELECT COUNT(*) AS cnt FROM users WHERE id = 1"
        )
        assert check.rows[0]["cnt"] == 0

    def test_returning_specific_columns(self, engine_with_table):
        result = engine_with_table.sql(
            "DELETE FROM users WHERE id = 2 RETURNING name"
        )
        assert result.columns == ["name"]
        assert result.rows[0]["name"] == "Bob"

    def test_returning_multiple_deletes(self, engine_with_table):
        result = engine_with_table.sql(
            "DELETE FROM users WHERE age >= 30 RETURNING id, name"
        )
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Carol"}

    def test_returning_no_match(self, engine_with_table):
        result = engine_with_table.sql(
            "DELETE FROM users WHERE id = 999 RETURNING id"
        )
        assert result.columns == ["id"]
        assert len(result.rows) == 0


# ==================================================================
# INSERT ... ON CONFLICT DO NOTHING
# ==================================================================


class TestOnConflictDoNothing:
    def test_skip_on_conflict(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Bob') "
            "ON CONFLICT (id) DO NOTHING"
        )
        result = engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"

    def test_insert_non_conflicting(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        engine.sql(
            "INSERT INTO t (id, name) VALUES (2, 'Bob') "
            "ON CONFLICT (id) DO NOTHING"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 2

    def test_multi_row_partial_conflict(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql("INSERT INTO t (id, name) VALUES (1, 'Alice')")
        engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Dup'), (2, 'Bob') "
            "ON CONFLICT (id) DO NOTHING"
        )
        result = engine.sql(
            "SELECT COUNT(*) AS cnt FROM t"
        )
        assert result.rows[0]["cnt"] == 2
        result = engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"


# ==================================================================
# INSERT ... ON CONFLICT DO UPDATE (UPSERT)
# ==================================================================


class TestOnConflictDoUpdate:
    def test_upsert_basic(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)"
        )
        engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 200) "
            "ON CONFLICT (id) DO UPDATE SET score = excluded.score"
        )
        result = engine.sql("SELECT score FROM t WHERE id = 1")
        assert result.rows[0]["score"] == 200

    def test_upsert_multiple_set_columns(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)"
        )
        engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alicia', 200) "
            "ON CONFLICT (id) DO UPDATE "
            "SET name = excluded.name, score = excluded.score"
        )
        result = engine.sql("SELECT name, score FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alicia"
        assert result.rows[0]["score"] == 200

    def test_upsert_no_conflict_inserts(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql(
            "INSERT INTO t (id, name) VALUES (1, 'Alice') "
            "ON CONFLICT (id) DO UPDATE SET name = excluded.name"
        )
        result = engine.sql("SELECT name FROM t WHERE id = 1")
        assert result.rows[0]["name"] == "Alice"

    def test_upsert_with_returning(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)"
        )
        engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 100)"
        )
        result = engine.sql(
            "INSERT INTO t (id, name, score) VALUES (1, 'Alice', 200) "
            "ON CONFLICT (id) DO UPDATE SET score = excluded.score "
            "RETURNING id, score"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["score"] == 200

    def test_upsert_on_unique_column(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER, email TEXT UNIQUE, name TEXT)"
        )
        engine.sql(
            "INSERT INTO t (id, email, name) VALUES (1, 'a@b.com', 'Alice')"
        )
        engine.sql(
            "INSERT INTO t (id, email, name) "
            "VALUES (2, 'a@b.com', 'Bob') "
            "ON CONFLICT (email) DO UPDATE SET name = excluded.name"
        )
        result = engine.sql("SELECT name FROM t WHERE email = 'a@b.com'")
        assert result.rows[0]["name"] == "Bob"
        result = engine.sql("SELECT COUNT(*) AS cnt FROM t")
        assert result.rows[0]["cnt"] == 1


# ==================================================================
# INNER JOIN
# ==================================================================


@pytest.fixture
def engine_with_orders(engine):
    """Two related tables: users and orders."""
    engine.sql(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
    )
    engine.sql("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    engine.sql("INSERT INTO users (id, name) VALUES (2, 'Bob')")
    engine.sql("INSERT INTO users (id, name) VALUES (3, 'Carol')")
    engine.sql(
        "CREATE TABLE orders ("
        "  oid INTEGER PRIMARY KEY, user_id INTEGER, product TEXT"
        ")"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) VALUES (10, 1, 'Book')"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) "
        "VALUES (11, 1, 'Pen')"
    )
    engine.sql(
        "INSERT INTO orders (oid, user_id, product) "
        "VALUES (12, 2, 'Notebook')"
    )
    return engine


class TestInnerJoin:
    def test_inner_join_basic(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        assert len(result.rows) == 3
        products = {r["product"] for r in result.rows}
        assert products == {"Book", "Pen", "Notebook"}

    def test_inner_join_excludes_unmatched(self, engine_with_orders):
        # Carol has no orders -- should not appear
        result = engine_with_orders.sql(
            "SELECT users.name "
            "FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        names = {r["name"] for r in result.rows}
        assert "Carol" not in names


# ==================================================================
# LEFT JOIN
# ==================================================================


class TestLeftJoin:
    def test_left_join_preserves_left(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        # Alice(2) + Bob(1) + Carol(unmatched) = 4 rows
        assert len(result.rows) == 4
        names = {r["name"] for r in result.rows}
        assert "Carol" in names

    def test_left_join_null_for_unmatched(self, engine_with_orders):
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        carol_rows = [r for r in result.rows if r["name"] == "Carol"]
        assert len(carol_rows) == 1
        assert carol_rows[0].get("product") is None


# ==================================================================
# CROSS JOIN
# ==================================================================


class TestCrossJoin:
    def test_cross_join_cartesian(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("INSERT INTO a (id, val) VALUES (2, 'y')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        engine.sql("INSERT INTO b (id, label) VALUES (10, 'p')")
        engine.sql("INSERT INTO b (id, label) VALUES (20, 'q')")
        engine.sql("INSERT INTO b (id, label) VALUES (30, 'r')")
        result = engine.sql(
            "SELECT a.val, b.label FROM a CROSS JOIN b"
        )
        assert len(result.rows) == 6  # 2 * 3

    def test_cross_join_empty_side(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        result = engine.sql("SELECT * FROM a CROSS JOIN b")
        assert len(result.rows) == 0


# ==================================================================
# RIGHT JOIN
# ==================================================================


class TestRightJoin:
    def test_right_join_preserves_right(self, engine_with_orders):
        # All orders preserved, even if user is missing
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        )
        products = {r["product"] for r in result.rows}
        assert "Ghost" in products
        assert len(result.rows) == 4

    def test_right_join_null_for_unmatched_left(self, engine_with_orders):
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        )
        ghost_rows = [r for r in result.rows if r["product"] == "Ghost"]
        assert len(ghost_rows) == 1
        assert ghost_rows[0].get("name") is None


# ==================================================================
# FULL OUTER JOIN
# ==================================================================


class TestFullOuterJoin:
    def test_full_join_preserves_both(self, engine_with_orders):
        # Add order with no matching user
        engine_with_orders.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (13, 99, 'Ghost')"
        )
        result = engine_with_orders.sql(
            "SELECT users.name, orders.product "
            "FROM users FULL OUTER JOIN orders "
            "ON users.id = orders.user_id"
        )
        # Alice(2) + Bob(1) + Carol(unmatched left) + Ghost(unmatched right) = 5
        assert len(result.rows) == 5
        names = {r.get("name") for r in result.rows}
        assert "Carol" in names
        products = {r.get("product") for r in result.rows}
        assert "Ghost" in products

    def test_full_join_no_overlap(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO b (id, val) VALUES (2, 'y')")
        result = engine.sql(
            "SELECT * FROM a FULL OUTER JOIN b ON a.id = b.id"
        )
        assert len(result.rows) == 2


# ==================================================================
# Multiple FROM tables (implicit CROSS JOIN)
# ==================================================================


class TestMultipleFromTables:
    def test_implicit_cross_join(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
        engine.sql("INSERT INTO a (id, val) VALUES (1, 'x')")
        engine.sql("INSERT INTO a (id, val) VALUES (2, 'y')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, label TEXT)")
        engine.sql("INSERT INTO b (id, label) VALUES (10, 'p')")
        engine.sql("INSERT INTO b (id, label) VALUES (20, 'q')")
        result = engine.sql("SELECT a.val, b.label FROM a, b")
        assert len(result.rows) == 4  # 2 * 2

    def test_implicit_cross_join_with_where(self, engine):
        engine.sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        engine.sql("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        engine.sql("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        engine.sql(
            "CREATE TABLE orders ("
            "  oid INTEGER PRIMARY KEY, user_id INTEGER, product TEXT"
            ")"
        )
        engine.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (10, 1, 'Book')"
        )
        engine.sql(
            "INSERT INTO orders (oid, user_id, product) "
            "VALUES (11, 2, 'Pen')"
        )
        result = engine.sql(
            "SELECT users.name, orders.product "
            "FROM users, orders "
            "WHERE users.id = orders.user_id"
        )
        assert len(result.rows) == 2

    def test_three_table_cross_join(self, engine):
        engine.sql("CREATE TABLE a (id INTEGER PRIMARY KEY, x TEXT)")
        engine.sql("INSERT INTO a (id, x) VALUES (1, 'a')")
        engine.sql("CREATE TABLE b (id INTEGER PRIMARY KEY, y TEXT)")
        engine.sql("INSERT INTO b (id, y) VALUES (1, 'b')")
        engine.sql("CREATE TABLE c (id INTEGER PRIMARY KEY, z TEXT)")
        engine.sql("INSERT INTO c (id, z) VALUES (1, 'c')")
        engine.sql("INSERT INTO c (id, z) VALUES (2, 'd')")
        result = engine.sql("SELECT a.x, b.y, c.z FROM a, b, c")
        assert len(result.rows) == 2  # 1 * 1 * 2


# ==================================================================
# WITH RECURSIVE
# ==================================================================


class TestWithRecursive:
    def test_recursive_count(self, engine):
        result = engine.sql(
            "WITH RECURSIVE cnt(x) AS ("
            "  SELECT 1"
            "  UNION ALL"
            "  SELECT x + 1 FROM cnt WHERE x < 5"
            ") SELECT x FROM cnt"
        )
        values = [r["x"] for r in result.rows]
        assert values == [1, 2, 3, 4, 5]

    def test_recursive_union_dedup(self, engine):
        # UNION (not ALL) should deduplicate
        result = engine.sql(
            "WITH RECURSIVE seq(n) AS ("
            "  SELECT 1"
            "  UNION"
            "  SELECT n + 1 FROM seq WHERE n < 3"
            ") SELECT n FROM seq"
        )
        values = sorted(r["n"] for r in result.rows)
        assert values == [1, 2, 3]

    def test_recursive_hierarchy(self, engine):
        engine.sql(
            "CREATE TABLE employees ("
            "  eid INTEGER PRIMARY KEY, ename TEXT, manager_id INTEGER"
            ")"
        )
        engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) "
            "VALUES (1, 'CEO', 0)"
        )
        engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) "
            "VALUES (2, 'VP', 1)"
        )
        engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) "
            "VALUES (3, 'Manager', 2)"
        )
        engine.sql(
            "INSERT INTO employees (eid, ename, manager_id) "
            "VALUES (4, 'Developer', 3)"
        )
        # Use distinct column names to avoid collision in join
        result = engine.sql(
            "WITH RECURSIVE chain(cid, cname, lvl) AS ("
            "  SELECT eid, ename, 0 FROM employees WHERE eid = 1"
            "  UNION ALL"
            "  SELECT e.eid, e.ename, c.lvl + 1 "
            "  FROM employees e "
            "  INNER JOIN chain c ON e.manager_id = c.cid"
            ") SELECT cname, lvl FROM chain"
        )
        assert len(result.rows) == 4
        names = {r["cname"] for r in result.rows}
        assert names == {"CEO", "VP", "Manager", "Developer"}

    def test_recursive_empty_base(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        result = engine.sql(
            "WITH RECURSIVE r(n) AS ("
            "  SELECT id FROM t WHERE id = 999"
            "  UNION ALL"
            "  SELECT n + 1 FROM r WHERE n < 5"
            ") SELECT n FROM r"
        )
        assert len(result.rows) == 0


# ==================================================================
# GENERATE_SERIES
# ==================================================================


class TestGenerateSeries:
    def test_basic(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(1, 5) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [1, 2, 3, 4, 5]

    def test_with_step(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(0, 10, 3) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [0, 3, 6, 9]

    def test_descending(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(5, 1, -1) AS t(n)"
        )
        values = [r["n"] for r in result.rows]
        assert values == [5, 4, 3, 2, 1]

    def test_single_value(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(1, 1) AS t(n)"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["n"] == 1

    def test_empty_range(self, engine):
        result = engine.sql(
            "SELECT n FROM generate_series(5, 1) AS t(n)"
        )
        assert len(result.rows) == 0


# ==================================================================
# GROUP BY alias and ordinal
# ==================================================================


class TestGroupByEnhanced:
    def test_group_by_ordinal(self, engine):
        engine.sql(
            "CREATE TABLE sales ("
            "  id INTEGER PRIMARY KEY, region TEXT, amount INTEGER"
            ")"
        )
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (1, 'East', 100)")
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (2, 'West', 200)")
        engine.sql("INSERT INTO sales (id, region, amount) VALUES (3, 'East', 150)")
        result = engine.sql(
            "SELECT region, SUM(amount) AS total FROM sales GROUP BY 1"
        )
        assert len(result.rows) == 2
        totals = {r["region"]: r["total"] for r in result.rows}
        assert totals["East"] == 250
        assert totals["West"] == 200

    def test_group_by_alias(self, engine):
        engine.sql(
            "CREATE TABLE items ("
            "  id INTEGER PRIMARY KEY, category TEXT, price INTEGER"
            ")"
        )
        engine.sql("INSERT INTO items (id, category, price) VALUES (1, 'A', 10)")
        engine.sql("INSERT INTO items (id, category, price) VALUES (2, 'B', 20)")
        engine.sql("INSERT INTO items (id, category, price) VALUES (3, 'A', 30)")
        result = engine.sql(
            "SELECT category AS cat, COUNT(*) AS cnt "
            "FROM items GROUP BY cat"
        )
        assert len(result.rows) == 2
        counts = {r["cat"]: r["cnt"] for r in result.rows}
        assert counts["A"] == 2
        assert counts["B"] == 1


# ==================================================================
# Complex HAVING
# ==================================================================


class TestComplexHaving:
    def test_having_with_and(self, engine):
        engine.sql(
            "CREATE TABLE sales ("
            "  id INTEGER PRIMARY KEY, region TEXT, amount INTEGER"
            ")"
        )
        for i, (region, amount) in enumerate([
            ("East", 100), ("East", 200), ("East", 50),
            ("West", 300), ("West", 400),
            ("North", 10),
        ], 1):
            engine.sql(
                f"INSERT INTO sales (id, region, amount) "
                f"VALUES ({i}, '{region}', {amount})"
            )
        result = engine.sql(
            "SELECT region, COUNT(*) AS cnt, SUM(amount) AS total "
            "FROM sales GROUP BY region "
            "HAVING COUNT(*) > 2 AND SUM(amount) > 300"
        )
        # East: count=3>2, sum=350>300 -> pass
        # West: count=2, not >2 -> fail
        # North: count=1, not >2 -> fail
        assert len(result.rows) == 1
        assert result.rows[0]["region"] == "East"

    def test_having_aggregate_comparison(self, engine):
        engine.sql(
            "CREATE TABLE scores ("
            "  id INTEGER PRIMARY KEY, team TEXT, score INTEGER"
            ")"
        )
        engine.sql("INSERT INTO scores (id, team, score) VALUES (1, 'A', 90)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (2, 'A', 80)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (3, 'B', 50)")
        engine.sql("INSERT INTO scores (id, team, score) VALUES (4, 'B', 60)")
        # Teams where max > 2 * min
        result = engine.sql(
            "SELECT team, MAX(score) AS hi, MIN(score) AS lo "
            "FROM scores GROUP BY team "
            "HAVING MAX(score) > MIN(score) + 20"
        )
        # A: max=90, min=80, diff=10 -> no
        # B: max=60, min=50, diff=10 -> no
        assert len(result.rows) == 0

    def test_having_simple(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, cat TEXT, val INTEGER)"
        )
        engine.sql("INSERT INTO t (id, cat, val) VALUES (1, 'a', 10)")
        engine.sql("INSERT INTO t (id, cat, val) VALUES (2, 'a', 20)")
        engine.sql("INSERT INTO t (id, cat, val) VALUES (3, 'b', 30)")
        result = engine.sql(
            "SELECT cat, COUNT(*) AS cnt FROM t "
            "GROUP BY cat HAVING COUNT(*) > 1"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["cat"] == "a"


# ==================================================================
# Step 5: JSON/JSONB type and operators
# ==================================================================


@pytest.fixture
def engine_with_json(engine):
    engine.sql(
        "CREATE TABLE docs ("
        "  id INTEGER PRIMARY KEY, data JSON, label TEXT"
        ")"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(1, '{\"name\": \"Alice\", \"age\": 30, \"tags\": [\"a\", \"b\"]}', 'first')"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(2, '{\"name\": \"Bob\", \"age\": 25, \"tags\": [\"c\"]}', 'second')"
    )
    engine.sql(
        "INSERT INTO docs (id, data, label) VALUES "
        "(3, '{\"name\": \"Carol\", \"nested\": {\"x\": 10}}', 'third')"
    )
    return engine


class TestJSONType:
    def test_create_table_with_json(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, data JSON)"
        )
        result = engine.sql("SELECT * FROM t")
        assert "data" in result.columns

    def test_create_table_with_jsonb(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, data JSONB)"
        )
        result = engine.sql("SELECT * FROM t")
        assert "data" in result.columns

    def test_insert_json_string(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data FROM docs WHERE id = 1"
        )
        data = result.rows[0]["data"]
        assert isinstance(data, dict)
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_insert_json_array(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, items JSON)"
        )
        engine.sql(
            "INSERT INTO t (id, items) VALUES (1, '[1, 2, 3]')"
        )
        result = engine.sql("SELECT items FROM t WHERE id = 1")
        assert result.rows[0]["items"] == [1, 2, 3]


class TestJSONOperators:
    def test_arrow_text_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'name' AS name FROM docs WHERE id = 1"
        )
        assert result.rows[0]["name"] == "Alice"

    def test_double_arrow_text_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->>'name' AS name FROM docs WHERE id = 1"
        )
        # ->> returns text
        assert result.rows[0]["name"] == "Alice"
        assert isinstance(result.rows[0]["name"], str)

    def test_arrow_integer_key(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'tags'->0 AS first_tag FROM docs WHERE id = 1"
        )
        assert result.rows[0]["first_tag"] == "a"

    def test_arrow_nested_object(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'nested'->'x' AS x FROM docs WHERE id = 3"
        )
        assert result.rows[0]["x"] == 10

    def test_double_arrow_returns_text_for_nested(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->>'tags' AS tags FROM docs WHERE id = 1"
        )
        # ->> on array returns JSON string representation
        assert isinstance(result.rows[0]["tags"], str)
        assert '"a"' in result.rows[0]["tags"]

    def test_arrow_missing_key_returns_null(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT data->'nonexistent' AS v FROM docs WHERE id = 1"
        )
        assert result.rows[0]["v"] is None

    def test_json_in_where(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT id FROM docs WHERE data->>'name' = 'Bob'"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 2


class TestJSONFunctions:
    def test_json_build_object(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT json_build_object('a', 1, 'b', 2) AS obj FROM t"
        )
        assert result.rows[0]["obj"] == {"a": 1, "b": 2}

    def test_json_build_array(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT json_build_array(1, 2, 3) AS arr FROM t"
        )
        assert result.rows[0]["arr"] == [1, 2, 3]

    def test_json_typeof_object(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_typeof(data) AS t FROM docs WHERE id = 1"
        )
        assert result.rows[0]["t"] == "object"

    def test_json_typeof_array(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_typeof(data->'tags') AS t FROM docs WHERE id = 1"
        )
        assert result.rows[0]["t"] == "array"

    def test_json_array_length(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_array_length(data->'tags') AS n FROM docs WHERE id = 1"
        )
        assert result.rows[0]["n"] == 2

    def test_json_array_length_single(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_array_length(data->'tags') AS n FROM docs WHERE id = 2"
        )
        assert result.rows[0]["n"] == 1

    def test_json_extract_path(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_extract_path(data, 'nested', 'x') AS v "
            "FROM docs WHERE id = 3"
        )
        assert result.rows[0]["v"] == 10

    def test_json_extract_path_text(self, engine_with_json):
        result = engine_with_json.sql(
            "SELECT json_extract_path_text(data, 'name') AS v "
            "FROM docs WHERE id = 1"
        )
        assert result.rows[0]["v"] == "Alice"
        assert isinstance(result.rows[0]["v"], str)

    def test_cast_to_json(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, raw TEXT)")
        engine.sql(
            "INSERT INTO t (id, raw) VALUES (1, '{\"x\": 42}')"
        )
        result = engine.sql(
            "SELECT CAST(raw AS json)->'x' AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] == 42


# ==================================================================
# Step 5: NUMERIC(precision, scale)
# ==================================================================


class TestNumericPrecisionScale:
    def test_create_table_numeric(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, price NUMERIC(10, 2))"
        )
        result = engine.sql("SELECT * FROM t")
        assert "price" in result.columns

    def test_insert_rounds_to_scale(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, price NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, price) VALUES (1, 19.999)")
        result = engine.sql("SELECT price FROM t WHERE id = 1")
        assert result.rows[0]["price"] == 20.00

    def test_insert_preserves_scale(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, amount NUMERIC(8, 3))"
        )
        engine.sql("INSERT INTO t (id, amount) VALUES (1, 123.456)")
        result = engine.sql("SELECT amount FROM t WHERE id = 1")
        assert result.rows[0]["amount"] == 123.456

    def test_numeric_arithmetic(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, a NUMERIC(10, 2), b NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, a, b) VALUES (1, 10.50, 3.25)")
        result = engine.sql("SELECT a + b AS total FROM t WHERE id = 1")
        assert abs(result.rows[0]["total"] - 13.75) < 0.001

    def test_numeric_comparison(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC(10, 2))"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 10.50)")
        engine.sql("INSERT INTO t (id, val) VALUES (2, 20.75)")
        engine.sql("INSERT INTO t (id, val) VALUES (3, 5.25)")
        result = engine.sql(
            "SELECT id FROM t WHERE val > 10.00 ORDER BY id"
        )
        ids = [r["id"] for r in result.rows]
        assert ids == [1, 2]

    def test_numeric_no_scale_specified(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC(10))"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 42.9)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        # NUMERIC(10) with scale=0 rounds to integer
        assert result.rows[0]["val"] == 43.0

    def test_plain_numeric_no_precision(self, engine):
        # Plain NUMERIC without precision/scale works as float
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val NUMERIC)"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 3.14159)")
        result = engine.sql("SELECT val FROM t WHERE id = 1")
        assert abs(result.rows[0]["val"] - 3.14159) < 0.001


# ==================================================================
# Step 6: ARRAY_AGG, BOOL_AND/OR, Aggregate FILTER, Aggregate ORDER BY
# ==================================================================


@pytest.fixture
def engine_with_products(engine):
    engine.sql(
        "CREATE TABLE products ("
        "  id INTEGER PRIMARY KEY, category TEXT, name TEXT,"
        "  price INTEGER, active BOOLEAN"
        ")"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (1, 'fruit', 'Apple', 3, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (2, 'fruit', 'Banana', 2, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (3, 'fruit', 'Cherry', 5, false)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (4, 'veggie', 'Daikon', 4, true)"
    )
    engine.sql(
        "INSERT INTO products (id, category, name, price, active) "
        "VALUES (5, 'veggie', 'Eggplant', 6, false)"
    )
    return engine


class TestArrayAgg:
    def test_basic(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name) AS names FROM products"
        )
        names = result.rows[0]["names"]
        assert isinstance(names, list)
        assert set(names) == {"Apple", "Banana", "Cherry", "Daikon", "Eggplant"}

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, array_agg(name) AS names "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["names"] for r in result.rows}
        assert set(by_cat["fruit"]) == {"Apple", "Banana", "Cherry"}
        assert set(by_cat["veggie"]) == {"Daikon", "Eggplant"}

    def test_with_order_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name ORDER BY name) AS names FROM products"
        )
        assert result.rows[0]["names"] == [
            "Apple", "Banana", "Cherry", "Daikon", "Eggplant"
        ]

    def test_with_order_by_desc(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT array_agg(name ORDER BY name DESC) AS names FROM products"
        )
        assert result.rows[0]["names"] == [
            "Eggplant", "Daikon", "Cherry", "Banana", "Apple"
        ]


class TestBoolAnd:
    def test_all_true(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, flag BOOLEAN)"
        )
        engine.sql("INSERT INTO t (id, flag) VALUES (1, true)")
        engine.sql("INSERT INTO t (id, flag) VALUES (2, true)")
        result = engine.sql("SELECT bool_and(flag) AS result FROM t")
        assert result.rows[0]["result"] is True

    def test_mixed(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT bool_and(active) AS result FROM products"
        )
        assert result.rows[0]["result"] is False

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, bool_and(active) AS all_active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["all_active"] for r in result.rows}
        assert by_cat["fruit"] is False
        assert by_cat["veggie"] is False


class TestBoolOr:
    def test_all_false(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, flag BOOLEAN)"
        )
        engine.sql("INSERT INTO t (id, flag) VALUES (1, false)")
        engine.sql("INSERT INTO t (id, flag) VALUES (2, false)")
        result = engine.sql("SELECT bool_or(flag) AS result FROM t")
        assert result.rows[0]["result"] is False

    def test_mixed(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT bool_or(active) AS result FROM products"
        )
        assert result.rows[0]["result"] is True

    def test_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, bool_or(active) AS any_active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["any_active"] for r in result.rows}
        assert by_cat["fruit"] is True
        assert by_cat["veggie"] is True


class TestAggregateFilter:
    def test_count_with_filter(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT COUNT(*) FILTER (WHERE active) AS active_count "
            "FROM products"
        )
        assert result.rows[0]["active_count"] == 3

    def test_sum_with_filter(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT SUM(price) FILTER (WHERE active) AS active_total "
            "FROM products"
        )
        # Apple=3, Banana=2, Daikon=4 -> 9
        assert result.rows[0]["active_total"] == 9

    def test_filter_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, "
            "  COUNT(*) AS total, "
            "  COUNT(*) FILTER (WHERE active) AS active "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r for r in result.rows}
        assert by_cat["fruit"]["total"] == 3
        assert by_cat["fruit"]["active"] == 2
        assert by_cat["veggie"]["total"] == 2
        assert by_cat["veggie"]["active"] == 1

    def test_filter_with_comparison(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT COUNT(*) FILTER (WHERE price > 3) AS expensive "
            "FROM products"
        )
        # Daikon=4, Cherry=5, Eggplant=6 -> 3
        assert result.rows[0]["expensive"] == 3


class TestAggregateOrderBy:
    def test_string_agg_ordered(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT string_agg(name, ', ' ORDER BY name) AS names "
            "FROM products"
        )
        assert result.rows[0]["names"] == (
            "Apple, Banana, Cherry, Daikon, Eggplant"
        )

    def test_string_agg_ordered_desc(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT string_agg(name, ', ' ORDER BY name DESC) AS names "
            "FROM products"
        )
        assert result.rows[0]["names"] == (
            "Eggplant, Daikon, Cherry, Banana, Apple"
        )

    def test_array_agg_ordered_with_group_by(self, engine_with_products):
        result = engine_with_products.sql(
            "SELECT category, "
            "  array_agg(name ORDER BY price DESC) AS by_price "
            "FROM products GROUP BY category"
        )
        by_cat = {r["category"]: r["by_price"] for r in result.rows}
        assert by_cat["fruit"] == ["Cherry", "Apple", "Banana"]
        assert by_cat["veggie"] == ["Eggplant", "Daikon"]


# ==================================================================
# Step 7: Window frames, PERCENT_RANK, CUME_DIST, NTH_VALUE,
#         scalar functions, information_schema
# ==================================================================


@pytest.fixture
def engine_with_scores(engine):
    engine.sql(
        "CREATE TABLE scores ("
        "  id INTEGER PRIMARY KEY, name TEXT, score INTEGER"
        ")"
    )
    engine.sql("INSERT INTO scores (id, name, score) VALUES (1, 'A', 100)")
    engine.sql("INSERT INTO scores (id, name, score) VALUES (2, 'B', 200)")
    engine.sql("INSERT INTO scores (id, name, score) VALUES (3, 'C', 200)")
    engine.sql("INSERT INTO scores (id, name, score) VALUES (4, 'D', 300)")
    engine.sql("INSERT INTO scores (id, name, score) VALUES (5, 'E', 400)")
    return engine


class TestPercentRank:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  percent_rank() OVER (ORDER BY score) AS pr "
            "FROM scores ORDER BY score"
        )
        prs = [r["pr"] for r in result.rows]
        # ranks: 1, 2, 2, 4, 5 -> (0/4, 1/4, 1/4, 3/4, 4/4)
        assert prs[0] == 0.0
        assert prs[1] == 0.25
        assert prs[2] == 0.25
        assert prs[3] == 0.75
        assert prs[4] == 1.0


class TestCumeDist:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  cume_dist() OVER (ORDER BY score) AS cd "
            "FROM scores ORDER BY score"
        )
        cds = [r["cd"] for r in result.rows]
        # A(100): 1/5=0.2, B(200): 3/5=0.6, C(200): 3/5=0.6,
        # D(300): 4/5=0.8, E(400): 5/5=1.0
        assert cds[0] == 0.2
        assert cds[1] == 0.6
        assert cds[2] == 0.6
        assert cds[3] == 0.8
        assert cds[4] == 1.0


class TestNthValue:
    def test_basic(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  nth_value(name, 2) OVER (ORDER BY score) AS second "
            "FROM scores"
        )
        # 2nd value in the partition ordered by score: B
        for row in result.rows:
            assert row["second"] == "B"

    def test_nth_value_out_of_range(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)"
        )
        engine.sql("INSERT INTO t (id, val) VALUES (1, 10)")
        result = engine.sql(
            "SELECT nth_value(val, 5) OVER (ORDER BY id) AS v FROM t"
        )
        assert result.rows[0]["v"] is None


class TestWindowFrames:
    def test_running_sum(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, score, "
            "  SUM(score) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
            "  ) AS running_total "
            "FROM scores ORDER BY id"
        )
        totals = [r["running_total"] for r in result.rows]
        assert totals == [100, 300, 500, 800, 1200]

    def test_sliding_window_avg(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)"
        )
        for i, v in enumerate([10, 20, 30, 40, 50], start=1):
            engine.sql(
                f"INSERT INTO t (id, val) VALUES ({i}, {v})"
            )
        result = engine.sql(
            "SELECT id, val, "
            "  AVG(val) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING"
            "  ) AS moving_avg "
            "FROM t ORDER BY id"
        )
        avgs = [r["moving_avg"] for r in result.rows]
        # Row 1: avg(10,20) = 15
        # Row 2: avg(10,20,30) = 20
        # Row 3: avg(20,30,40) = 30
        # Row 4: avg(30,40,50) = 40
        # Row 5: avg(40,50) = 45
        assert avgs == [15.0, 20.0, 30.0, 40.0, 45.0]

    def test_unbounded_frame(self, engine_with_scores):
        result = engine_with_scores.sql(
            "SELECT name, "
            "  SUM(score) OVER ("
            "    ORDER BY id "
            "    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING"
            "  ) AS total "
            "FROM scores"
        )
        # Every row sees the full partition sum
        for row in result.rows:
            assert row["total"] == 1200


class TestScalarFunctionsStep7:
    def test_initcap(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT initcap('hello world') AS v FROM t"
        )
        assert result.rows[0]["v"] == "Hello World"

    def test_translate(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql(
            "SELECT translate('12345', '143', 'ax') AS v FROM t"
        )
        # '1'->'a', '4'->'x', '3' deleted
        assert result.rows[0]["v"] == "a2x5"

    def test_ascii(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT ascii('A') AS v FROM t")
        assert result.rows[0]["v"] == 65

    def test_chr(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.sql("INSERT INTO t (id) VALUES (1)")
        result = engine.sql("SELECT chr(65) AS v FROM t")
        assert result.rows[0]["v"] == "A"

    def test_starts_with(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO t (id, name) VALUES (1, 'PostgreSQL')")
        result = engine.sql(
            "SELECT starts_with(name, 'Post') AS v FROM t WHERE id = 1"
        )
        assert result.rows[0]["v"] is True


class TestInformationSchema:
    def test_tables_lists_tables(self, engine):
        engine.sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        engine.sql("CREATE TABLE orders (id INTEGER PRIMARY KEY)")
        result = engine.sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        names = [r["table_name"] for r in result.rows]
        assert "users" in names
        assert "orders" in names

    def test_tables_shows_views(self, engine):
        engine.sql("CREATE TABLE t (id INTEGER PRIMARY KEY, val INTEGER)")
        engine.sql("CREATE VIEW v AS SELECT id FROM t")
        result = engine.sql(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_name IN ('t', 'v') "
            "ORDER BY table_name"
        )
        by_name = {r["table_name"]: r["table_type"] for r in result.rows}
        assert by_name["t"] == "BASE TABLE"
        assert by_name["v"] == "VIEW"

    def test_columns_lists_columns(self, engine):
        engine.sql(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY, name TEXT, age INTEGER"
            ")"
        )
        result = engine.sql(
            "SELECT column_name, data_type, ordinal_position "
            "FROM information_schema.columns "
            "WHERE table_name = 'users' "
            "ORDER BY ordinal_position"
        )
        cols = [(r["column_name"], r["data_type"]) for r in result.rows]
        assert cols == [("id", "integer"), ("name", "text"), ("age", "integer")]

    def test_columns_is_nullable(self, engine):
        engine.sql(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT NOT NULL)"
        )
        result = engine.sql(
            "SELECT column_name, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 't' "
            "ORDER BY ordinal_position"
        )
        by_col = {r["column_name"]: r["is_nullable"] for r in result.rows}
        assert by_col["id"] == "NO"
        assert by_col["val"] == "NO"
