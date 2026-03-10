#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Foreign Data Wrapper (FDW) support.

Covers DDL (CREATE/DROP SERVER, CREATE/DROP FOREIGN TABLE),
DML guards, DuckDB FDW handler, information_schema integration,
and catalog persistence.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.engine import Engine


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def engine():
    """In-memory engine for DDL tests."""
    e = Engine()
    yield e
    e.close()


@pytest.fixture
def parquet_path(tmp_path):
    """Write a small Parquet file and return its path."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({
        "id": [1, 2, 3, 4, 5],
        "name": ["alice", "bob", "carol", "dave", "eve"],
        "value": [10, 20, 30, 40, 50],
    })
    path = str(tmp_path / "test_data.parquet")
    pq.write_table(table, path)
    return path


# ======================================================================
# DDL: CREATE / DROP SERVER
# ======================================================================


class TestCreateDropServer:

    def test_create_server(self, engine):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        assert "local" in engine._foreign_servers
        assert engine._foreign_servers["local"].fdw_type == "duckdb_fdw"

    def test_create_server_with_options(self, engine):
        engine.sql(
            "CREATE SERVER mydb FOREIGN DATA WRAPPER duckdb_fdw "
            "OPTIONS (database '/tmp/test.db')"
        )
        server = engine._foreign_servers["mydb"]
        assert server.options["database"] == "/tmp/test.db"

    def test_create_server_arrow(self, engine):
        engine.sql(
            "CREATE SERVER remote FOREIGN DATA WRAPPER arrow_fdw "
            "OPTIONS (host 'localhost', port '8815')"
        )
        server = engine._foreign_servers["remote"]
        assert server.fdw_type == "arrow_fdw"
        assert server.options["host"] == "localhost"
        assert server.options["port"] == "8815"

    def test_create_server_if_not_exists(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        # Should not raise
        engine.sql(
            "CREATE SERVER IF NOT EXISTS s1 "
            "FOREIGN DATA WRAPPER duckdb_fdw"
        )

    def test_create_duplicate_server_error(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        with pytest.raises(ValueError, match="already exists"):
            engine.sql(
                "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
            )

    def test_create_server_unsupported_fdw(self, engine):
        with pytest.raises(ValueError, match="Unsupported FDW type"):
            engine.sql(
                "CREATE SERVER bad FOREIGN DATA WRAPPER postgres_fdw"
            )

    def test_drop_server(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql("DROP SERVER s1")
        assert "s1" not in engine._foreign_servers

    def test_drop_server_if_exists(self, engine):
        # Should not raise
        engine.sql("DROP SERVER IF EXISTS nonexistent")

    def test_drop_server_not_found_error(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DROP SERVER nonexistent")

    def test_drop_server_with_dependent_table(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'dummy')"
        )
        with pytest.raises(ValueError, match="depends on it"):
            engine.sql("DROP SERVER s1")


# ======================================================================
# DDL: CREATE / DROP FOREIGN TABLE
# ======================================================================


class TestCreateDropForeignTable:

    def test_create_foreign_table(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE data "
            "(id INTEGER, name TEXT, value REAL) "
            "SERVER s1 OPTIONS (source 'test.parquet')"
        )
        assert "data" in engine._foreign_tables
        ft = engine._foreign_tables["data"]
        assert ft.server_name == "s1"
        assert list(ft.columns.keys()) == ["id", "name", "value"]
        assert ft.options["source"] == "test.parquet"

    def test_create_foreign_table_if_not_exists(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )
        # Should not raise
        engine.sql(
            "CREATE FOREIGN TABLE IF NOT EXISTS ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )

    def test_create_duplicate_foreign_table_error(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )
        with pytest.raises(ValueError, match="already exists"):
            engine.sql(
                "CREATE FOREIGN TABLE ft (id INTEGER) "
                "SERVER s1 OPTIONS (source 'x')"
            )

    def test_create_foreign_table_name_conflicts_with_table(self, engine):
        engine.sql("CREATE TABLE data (id INTEGER)")
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        with pytest.raises(ValueError, match="already exists"):
            engine.sql(
                "CREATE FOREIGN TABLE data (id INTEGER) "
                "SERVER s1 OPTIONS (source 'x')"
            )

    def test_create_foreign_table_missing_server(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql(
                "CREATE FOREIGN TABLE ft (id INTEGER) "
                "SERVER nonexistent OPTIONS (source 'x')"
            )

    def test_drop_foreign_table(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )
        engine.sql("DROP FOREIGN TABLE ft")
        assert "ft" not in engine._foreign_tables

    def test_drop_foreign_table_if_exists(self, engine):
        # Should not raise
        engine.sql("DROP FOREIGN TABLE IF EXISTS nonexistent")

    def test_drop_foreign_table_not_found_error(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DROP FOREIGN TABLE nonexistent")


# ======================================================================
# DML guard: INSERT / UPDATE / DELETE on foreign table
# ======================================================================


class TestDMLGuard:

    @pytest.fixture(autouse=True)
    def setup_foreign_table(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER, name TEXT) "
            "SERVER s1 OPTIONS (source 'dummy')"
        )

    def test_insert_rejected(self, engine):
        with pytest.raises(ValueError, match="Cannot INSERT"):
            engine.sql("INSERT INTO ft (id, name) VALUES (1, 'a')")

    def test_update_rejected(self, engine):
        with pytest.raises(ValueError, match="Cannot UPDATE"):
            engine.sql("UPDATE ft SET name = 'b' WHERE id = 1")

    def test_delete_rejected(self, engine):
        with pytest.raises(ValueError, match="Cannot DELETE"):
            engine.sql("DELETE FROM ft WHERE id = 1")


# ======================================================================
# DuckDB FDW: SELECT from Parquet
# ======================================================================


class TestDuckDBFDW:

    def test_select_all(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        result = engine.sql("SELECT * FROM data ORDER BY id")
        assert len(result.rows) == 5
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "alice"
        assert result.rows[4]["id"] == 5

    def test_select_with_where(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        result = engine.sql(
            "SELECT name, value FROM data WHERE value > 25 ORDER BY value"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "carol"
        assert result.rows[0]["value"] == 30

    def test_select_with_limit(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        result = engine.sql(
            "SELECT * FROM data ORDER BY id LIMIT 2"
        )
        assert len(result.rows) == 2

    def test_select_with_aggregation(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        result = engine.sql("SELECT SUM(value) AS total FROM data")
        assert result.rows[0]["total"] == 150

    def test_join_local_and_foreign(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql("CREATE TABLE tags (id INTEGER, tag TEXT)")
        engine.sql(
            "INSERT INTO tags (id, tag) VALUES "
            "(1, 'admin'), (2, 'user'), (3, 'guest')"
        )
        result = engine.sql(
            "SELECT d.name, t.tag FROM data d "
            "INNER JOIN tags t ON d.id = t.id "
            "ORDER BY d.id"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "alice"
        assert result.rows[0]["tag"] == "admin"
        assert result.rows[2]["name"] == "carol"
        assert result.rows[2]["tag"] == "guest"

    def test_source_expression(self, engine, parquet_path):
        """The source option can be a DuckDB expression like read_parquet()."""
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local "
            f"OPTIONS (source 'read_parquet(''{parquet_path}'')')"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM data")
        assert result.rows[0]["cnt"] == 5

    def test_handler_cached(self, engine, parquet_path):
        """Handler should be cached per server, not recreated per scan."""
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql("SELECT * FROM data")
        engine.sql("SELECT * FROM data")
        assert "local" in engine._fdw_handlers

    def test_csv_source(self, engine, tmp_path):
        """DuckDB can also read CSV files."""
        csv_path = str(tmp_path / "test.csv")
        with open(csv_path, "w") as f:
            f.write("id,name\n1,alice\n2,bob\n")

        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE csvdata (id INTEGER, name TEXT) "
            f"SERVER local "
            f"OPTIONS (source 'read_csv(''{csv_path}'')')"
        )
        result = engine.sql("SELECT * FROM csvdata ORDER BY id")
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "alice"


# ======================================================================
# information_schema integration
# ======================================================================


class TestInformationSchema:

    def test_foreign_table_visible(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql("CREATE TABLE local_t (x INTEGER)")
        result = engine.sql(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "ORDER BY table_name"
        )
        names = {r["table_name"]: r["table_type"] for r in result.rows}
        assert names["data"] == "FOREIGN TABLE"
        assert names["local_t"] == "BASE TABLE"


# ======================================================================
# Catalog persistence
# ======================================================================


class TestCatalogPersistence:

    def test_persist_and_restore(self, tmp_path, parquet_path):
        db_path = str(tmp_path / "test.db")

        # Create and populate
        engine1 = Engine(db_path=db_path)
        engine1.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw "
            "OPTIONS (database ':memory:')"
        )
        engine1.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine1.close()

        # Reopen and verify
        engine2 = Engine(db_path=db_path)
        assert "local" in engine2._foreign_servers
        assert engine2._foreign_servers["local"].fdw_type == "duckdb_fdw"
        assert "data" in engine2._foreign_tables
        ft = engine2._foreign_tables["data"]
        assert ft.server_name == "local"
        assert list(ft.columns.keys()) == ["id", "name", "value"]
        assert ft.options["source"] == parquet_path

        # Query still works after restore
        result = engine2.sql("SELECT * FROM data ORDER BY id")
        assert len(result.rows) == 5
        engine2.close()

    def test_drop_and_persist(self, tmp_path, parquet_path):
        db_path = str(tmp_path / "test.db")

        engine1 = Engine(db_path=db_path)
        engine1.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine1.sql(
            f"CREATE FOREIGN TABLE data (id INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine1.sql("DROP FOREIGN TABLE data")
        engine1.sql("DROP SERVER local")
        engine1.close()

        engine2 = Engine(db_path=db_path)
        assert "local" not in engine2._foreign_servers
        assert "data" not in engine2._foreign_tables
        engine2.close()


# ======================================================================
# Handler unit tests
# ======================================================================


class TestDuckDBHandler:

    def test_missing_source_option(self, engine):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER local OPTIONS (dummy 'x')"
        )
        with pytest.raises(ValueError, match="missing required option"):
            engine.sql("SELECT * FROM ft")

    def test_close_handler(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE data (id INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql("SELECT * FROM data")
        assert "local" in engine._fdw_handlers
        engine.close()
        assert len(engine._fdw_handlers) == 0
