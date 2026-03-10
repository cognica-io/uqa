#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Foreign Data Wrapper (FDW) support.

Covers:
  - DDL: CREATE/DROP SERVER, CREATE/DROP FOREIGN TABLE, IF [NOT] EXISTS
  - DML guards: INSERT/UPDATE/DELETE rejected on foreign tables
  - DuckDB FDW queries: SELECT, WHERE, ORDER BY, LIMIT, DISTINCT
  - Aggregation: GROUP BY, HAVING, SUM, AVG, COUNT on foreign data
  - Joins: foreign-local, foreign-foreign, three-way mixed
  - Subqueries and CTEs involving foreign tables
  - Window functions on foreign data
  - EXPLAIN on foreign table scans
  - DuckDB source normalization: auto-detect Parquet/CSV/JSON paths
  - CSV and JSON file sources
  - Handler lifecycle: caching, close, drop server cleans handler
  - information_schema visibility (FOREIGN TABLE type)
  - Catalog persistence: servers + foreign tables survive engine restart
"""

from __future__ import annotations

import pytest

from uqa.engine import Engine
from uqa.fdw.duckdb_handler import DuckDBFDWHandler


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def engine():
    """In-memory engine."""
    e = Engine()
    yield e
    e.close()


@pytest.fixture
def parquet_path(tmp_path):
    """Write a Parquet file with 5 rows."""
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


@pytest.fixture
def orders_parquet(tmp_path):
    """Write an orders Parquet file for join tests."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({
        "order_id": [1, 2, 3, 4, 5],
        "product_id": [1, 3, 2, 1, 5],
        "customer": ["alice", "bob", "alice", "carol", "bob"],
        "quantity": [2, 5, 1, 3, 10],
    })
    path = str(tmp_path / "orders.parquet")
    pq.write_table(table, path)
    return path


@pytest.fixture
def csv_path(tmp_path):
    """Write a CSV file for CSV source tests."""
    path = str(tmp_path / "data.csv")
    with open(path, "w") as f:
        f.write("id,name,score\n")
        f.write("1,alice,95.5\n")
        f.write("2,bob,87.0\n")
        f.write("3,carol,91.2\n")
    return path


@pytest.fixture
def fdw_engine(engine, parquet_path):
    """Engine with a duckdb_fdw server and foreign table already set up."""
    engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
    engine.sql(
        f"CREATE FOREIGN TABLE data "
        f"(id INTEGER, name TEXT, value INTEGER) "
        f"SERVER local OPTIONS (source '{parquet_path}')"
    )
    return engine


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

    def test_create_server_multiple_options(self, engine):
        engine.sql(
            "CREATE SERVER s3srv FOREIGN DATA WRAPPER duckdb_fdw "
            "OPTIONS (database ':memory:', s3_region 'us-east-1', "
            "s3_access_key_id 'AKID')"
        )
        server = engine._foreign_servers["s3srv"]
        assert server.options["database"] == ":memory:"
        assert server.options["s3_region"] == "us-east-1"
        assert server.options["s3_access_key_id"] == "AKID"

    def test_create_server_arrow(self, engine):
        engine.sql(
            "CREATE SERVER remote FOREIGN DATA WRAPPER arrow_fdw "
            "OPTIONS (host 'localhost', port '8815')"
        )
        server = engine._foreign_servers["remote"]
        assert server.fdw_type == "arrow_fdw"
        assert server.options["host"] == "localhost"
        assert server.options["port"] == "8815"

    def test_create_server_no_options(self, engine):
        engine.sql(
            "CREATE SERVER bare FOREIGN DATA WRAPPER duckdb_fdw"
        )
        assert engine._foreign_servers["bare"].options == {}

    def test_create_server_if_not_exists(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
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

    def test_drop_server_closes_handler(self, engine, parquet_path):
        engine.sql(
            "CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE ft (id INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql("SELECT * FROM ft")
        assert "local" in engine._fdw_handlers
        engine.sql("DROP FOREIGN TABLE ft")
        engine.sql("DROP SERVER local")
        assert "local" not in engine._fdw_handlers


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

    def test_create_foreign_table_column_types(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft "
            "(a INTEGER, b TEXT, c REAL, d BOOLEAN, e BIGINT) "
            "SERVER s1 OPTIONS (source 'x')"
        )
        ft = engine._foreign_tables["ft"]
        assert ft.columns["a"].python_type == int
        assert ft.columns["b"].python_type == str
        assert ft.columns["c"].python_type == float
        assert ft.columns["d"].python_type == bool
        assert ft.columns["e"].python_type == int

    def test_create_foreign_table_if_not_exists(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )
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

    def test_create_foreign_table_name_conflicts_with_regular_table(
        self, engine,
    ):
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

    def test_multiple_foreign_tables_on_same_server(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft1 (id INTEGER) "
            "SERVER s1 OPTIONS (source 'a')"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft2 (name TEXT) "
            "SERVER s1 OPTIONS (source 'b')"
        )
        assert engine._foreign_tables["ft1"].server_name == "s1"
        assert engine._foreign_tables["ft2"].server_name == "s1"

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
        engine.sql("DROP FOREIGN TABLE IF EXISTS nonexistent")

    def test_drop_foreign_table_not_found_error(self, engine):
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("DROP FOREIGN TABLE nonexistent")

    def test_drop_foreign_table_then_server(self, engine):
        engine.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw"
        )
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER s1 OPTIONS (source 'x')"
        )
        engine.sql("DROP FOREIGN TABLE ft")
        engine.sql("DROP SERVER s1")
        assert "s1" not in engine._foreign_servers


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
# DuckDB source normalization
# ======================================================================


class TestSourceNormalization:

    def test_parquet_path_auto_wrapped(self):
        result = DuckDBFDWHandler._normalize_source("/data/file.parquet")
        assert result == "read_parquet('/data/file.parquet')"

    def test_csv_path_auto_wrapped(self):
        result = DuckDBFDWHandler._normalize_source("/data/file.csv")
        assert result == "read_csv('/data/file.csv')"

    def test_json_path_auto_wrapped(self):
        result = DuckDBFDWHandler._normalize_source("/data/file.json")
        assert result == "read_json('/data/file.json')"

    def test_ndjson_path_auto_wrapped(self):
        result = DuckDBFDWHandler._normalize_source("/data/file.ndjson")
        assert result == "read_json('/data/file.ndjson')"

    def test_expression_with_parens_not_wrapped(self):
        src = "read_parquet('s3://bucket/data.parquet')"
        assert DuckDBFDWHandler._normalize_source(src) == src

    def test_table_name_not_wrapped(self):
        assert DuckDBFDWHandler._normalize_source("my_table") == "my_table"

    def test_case_insensitive_extension(self):
        result = DuckDBFDWHandler._normalize_source("/data/FILE.PARQUET")
        assert result == "read_parquet('/data/FILE.PARQUET')"


# ======================================================================
# DuckDB FDW: basic queries
# ======================================================================


class TestDuckDBFDWBasicQueries:

    def test_select_all(self, fdw_engine):
        result = fdw_engine.sql("SELECT * FROM data ORDER BY id")
        assert len(result.rows) == 5
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "alice"
        assert result.rows[4]["id"] == 5
        assert result.rows[4]["name"] == "eve"

    def test_select_columns(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name, value FROM data ORDER BY id"
        )
        assert result.columns == ["name", "value"]
        assert result.rows[0]["name"] == "alice"
        assert result.rows[0]["value"] == 10

    def test_where_equality(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE id = 3"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "carol"

    def test_where_comparison(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name, value FROM data WHERE value > 25 ORDER BY value"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "carol"
        assert result.rows[0]["value"] == 30

    def test_where_and(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE value >= 20 AND value <= 40"
        )
        assert len(result.rows) == 3

    def test_where_or(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE name = 'alice' OR name = 'eve'"
        )
        assert len(result.rows) == 2

    def test_where_in(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE id IN (1, 3, 5) ORDER BY id"
        )
        assert [r["name"] for r in result.rows] == [
            "alice", "carol", "eve",
        ]

    def test_where_between(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE value BETWEEN 20 AND 40 "
            "ORDER BY value"
        )
        assert len(result.rows) == 3

    def test_where_like(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data WHERE name LIKE '%o%' ORDER BY name"
        )
        assert [r["name"] for r in result.rows] == ["bob", "carol"]

    def test_order_by_desc(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name, value FROM data ORDER BY value DESC"
        )
        assert result.rows[0]["name"] == "eve"
        assert result.rows[4]["name"] == "alice"

    def test_limit(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT * FROM data ORDER BY id LIMIT 2"
        )
        assert len(result.rows) == 2

    def test_limit_offset(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT name FROM data ORDER BY id LIMIT 2 OFFSET 2"
        )
        assert [r["name"] for r in result.rows] == ["carol", "dave"]

    def test_distinct(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT DISTINCT value FROM data ORDER BY value"
        )
        assert len(result.rows) == 5

    def test_count(self, fdw_engine):
        result = fdw_engine.sql("SELECT COUNT(*) AS cnt FROM data")
        assert result.rows[0]["cnt"] == 5

    def test_sum(self, fdw_engine):
        result = fdw_engine.sql("SELECT SUM(value) AS total FROM data")
        assert result.rows[0]["total"] == 150

    def test_avg(self, fdw_engine):
        result = fdw_engine.sql("SELECT AVG(value) AS avg_val FROM data")
        assert result.rows[0]["avg_val"] == 30.0

    def test_min_max(self, fdw_engine):
        result = fdw_engine.sql(
            "SELECT MIN(value) AS lo, MAX(value) AS hi FROM data"
        )
        assert result.rows[0]["lo"] == 10
        assert result.rows[0]["hi"] == 50


# ======================================================================
# DuckDB FDW: GROUP BY / HAVING
# ======================================================================


class TestDuckDBFDWAggregation:

    @pytest.fixture(autouse=True)
    def setup(self, engine, tmp_path):
        import pyarrow as pa
        import pyarrow.parquet as pq

        path = str(tmp_path / "sales.parquet")
        pq.write_table(pa.table({
            "region": ["East", "East", "West", "West", "East"],
            "product": ["A", "B", "A", "B", "A"],
            "amount": [100, 200, 150, 250, 120],
        }), path)

        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE sales "
            f"(region TEXT, product TEXT, amount INTEGER) "
            f"SERVER local OPTIONS (source '{path}')"
        )
        self.engine = engine

    def test_group_by(self):
        result = self.engine.sql(
            "SELECT region, SUM(amount) AS total "
            "FROM sales GROUP BY region ORDER BY region"
        )
        assert len(result.rows) == 2
        assert result.rows[0]["region"] == "East"
        assert result.rows[0]["total"] == 420
        assert result.rows[1]["region"] == "West"
        assert result.rows[1]["total"] == 400

    def test_group_by_having(self):
        result = self.engine.sql(
            "SELECT region, COUNT(*) AS cnt "
            "FROM sales GROUP BY region HAVING COUNT(*) > 2"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["region"] == "East"

    def test_group_by_multiple_columns(self):
        result = self.engine.sql(
            "SELECT region, product, SUM(amount) AS total "
            "FROM sales GROUP BY region, product "
            "ORDER BY region, product"
        )
        assert len(result.rows) == 4


# ======================================================================
# DuckDB FDW: joins
# ======================================================================


class TestDuckDBFDWJoins:

    def test_join_foreign_and_local(self, fdw_engine):
        fdw_engine.sql("CREATE TABLE tags (id INTEGER, tag TEXT)")
        fdw_engine.sql(
            "INSERT INTO tags (id, tag) VALUES "
            "(1, 'admin'), (2, 'user'), (3, 'guest')"
        )
        result = fdw_engine.sql(
            "SELECT d.name, t.tag FROM data d "
            "INNER JOIN tags t ON d.id = t.id "
            "ORDER BY d.id"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "alice"
        assert result.rows[0]["tag"] == "admin"
        assert result.rows[2]["name"] == "carol"
        assert result.rows[2]["tag"] == "guest"

    def test_join_two_foreign_tables(
        self, engine, parquet_path, orders_parquet,
    ):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE products "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE orders "
            f"(order_id INTEGER, product_id INTEGER, "
            f"customer TEXT, quantity INTEGER) "
            f"SERVER local OPTIONS (source '{orders_parquet}')"
        )
        result = engine.sql(
            "SELECT o.order_id, p.name, o.quantity "
            "FROM orders o "
            "INNER JOIN products p ON o.product_id = p.id "
            "ORDER BY o.order_id"
        )
        assert len(result.rows) == 5
        assert result.rows[0]["name"] == "alice"
        assert result.rows[0]["quantity"] == 2

    def test_three_way_join_local_and_foreign(
        self, engine, parquet_path, orders_parquet,
    ):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE products "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE orders "
            f"(order_id INTEGER, product_id INTEGER, "
            f"customer TEXT, quantity INTEGER) "
            f"SERVER local OPTIONS (source '{orders_parquet}')"
        )
        engine.sql(
            "CREATE TABLE customer_tiers "
            "(customer TEXT PRIMARY KEY, tier TEXT)"
        )
        engine.sql(
            "INSERT INTO customer_tiers (customer, tier) VALUES "
            "('alice', 'gold'), ('bob', 'silver'), ('carol', 'bronze')"
        )
        result = engine.sql(
            "SELECT o.order_id, p.name AS product, "
            "c.tier, o.quantity "
            "FROM orders o "
            "INNER JOIN products p ON o.product_id = p.id "
            "INNER JOIN customer_tiers c ON o.customer = c.customer "
            "ORDER BY o.order_id"
        )
        assert len(result.rows) == 5
        assert result.rows[0]["product"] == "alice"
        assert result.rows[0]["tier"] == "gold"

    def test_left_join_foreign_and_local(self, fdw_engine):
        fdw_engine.sql("CREATE TABLE tags (id INTEGER, tag TEXT)")
        fdw_engine.sql(
            "INSERT INTO tags (id, tag) VALUES (1, 'admin'), (3, 'guest')"
        )
        result = fdw_engine.sql(
            "SELECT d.name, t.tag FROM data d "
            "LEFT JOIN tags t ON d.id = t.id "
            "ORDER BY d.id"
        )
        assert len(result.rows) == 5
        assert result.rows[0]["tag"] == "admin"
        assert result.rows[1]["tag"] is None
        assert result.rows[2]["tag"] == "guest"


# ======================================================================
# DuckDB FDW: subqueries and CTEs
# ======================================================================


class TestDuckDBFDWSubqueries:

    def test_subquery_in_where(self, fdw_engine):
        fdw_engine.sql("CREATE TABLE selected (id INTEGER)")
        fdw_engine.sql(
            "INSERT INTO selected (id) VALUES (1), (3), (5)"
        )
        result = fdw_engine.sql(
            "SELECT name FROM data "
            "WHERE id IN (SELECT id FROM selected) "
            "ORDER BY id"
        )
        assert [r["name"] for r in result.rows] == [
            "alice", "carol", "eve",
        ]

    def test_cte_over_foreign_table(self, fdw_engine):
        result = fdw_engine.sql("""
            WITH high_value AS (
                SELECT name, value FROM data WHERE value >= 30
            )
            SELECT name FROM high_value ORDER BY value
        """)
        assert [r["name"] for r in result.rows] == [
            "carol", "dave", "eve",
        ]

    def test_scalar_subquery(self, fdw_engine):
        result = fdw_engine.sql("""
            SELECT name, value,
                   (SELECT AVG(value) FROM data) AS avg_val
            FROM data
            WHERE value > (SELECT AVG(value) FROM data)
            ORDER BY value
        """)
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "dave"
        assert result.rows[1]["name"] == "eve"


# ======================================================================
# DuckDB FDW: window functions
# ======================================================================


class TestDuckDBFDWWindowFunctions:

    def test_row_number(self, fdw_engine):
        result = fdw_engine.sql("""
            SELECT name, value,
                   ROW_NUMBER() OVER (ORDER BY value DESC) AS rn
            FROM data
        """)
        ranked = {r["rn"]: r["name"] for r in result.rows}
        assert ranked[1] == "eve"
        assert ranked[5] == "alice"

    def test_rank(self, fdw_engine):
        result = fdw_engine.sql("""
            SELECT name,
                   RANK() OVER (ORDER BY value DESC) AS rnk
            FROM data
        """)
        assert len(result.rows) == 5

    def test_running_sum(self, fdw_engine):
        result = fdw_engine.sql("""
            SELECT name, value,
                   SUM(value) OVER (ORDER BY id) AS running
            FROM data
        """)
        totals = [r["running"] for r in result.rows]
        assert totals == [10, 30, 60, 100, 150]


# ======================================================================
# DuckDB FDW: EXPLAIN
# ======================================================================


class TestDuckDBFDWExplain:

    def test_explain_foreign_table(self, fdw_engine):
        result = fdw_engine.sql("EXPLAIN SELECT * FROM data")
        assert len(result.rows) > 0
        plans = [r["plan"] for r in result.rows]
        plan_text = " ".join(plans)
        assert "ForeignTableScan" in plan_text or "Scan" in plan_text


# ======================================================================
# DuckDB FDW: file sources
# ======================================================================


class TestDuckDBFDWSources:

    def test_parquet_auto_detected(self, engine, parquet_path):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM data")
        assert result.rows[0]["cnt"] == 5

    def test_explicit_read_parquet(self, engine, parquet_path):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local "
            f"OPTIONS (source 'read_parquet(''{parquet_path}'')')"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM data")
        assert result.rows[0]["cnt"] == 5

    def test_csv_auto_detected(self, engine, csv_path):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE csvdata "
            f"(id INTEGER, name TEXT, score REAL) "
            f"SERVER local OPTIONS (source '{csv_path}')"
        )
        result = engine.sql(
            "SELECT * FROM csvdata ORDER BY id"
        )
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "alice"
        assert result.rows[0]["score"] == pytest.approx(95.5)

    def test_csv_explicit_read_csv(self, engine, csv_path):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE csvdata "
            f"(id INTEGER, name TEXT, score REAL) "
            f"SERVER local "
            f"OPTIONS (source 'read_csv(''{csv_path}'')')"
        )
        result = engine.sql("SELECT COUNT(*) AS cnt FROM csvdata")
        assert result.rows[0]["cnt"] == 3

    def test_json_auto_detected(self, engine, tmp_path):
        json_path = str(tmp_path / "data.json")
        with open(json_path, "w") as f:
            f.write('[{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]')

        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE jsondata (x INTEGER, y TEXT) "
            f"SERVER local OPTIONS (source '{json_path}')"
        )
        result = engine.sql("SELECT * FROM jsondata ORDER BY x")
        assert len(result.rows) == 2
        assert result.rows[0]["y"] == "a"

    def test_missing_source_option(self, engine):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            "CREATE FOREIGN TABLE ft (id INTEGER) "
            "SERVER local OPTIONS (dummy 'x')"
        )
        with pytest.raises(ValueError, match="missing required option"):
            engine.sql("SELECT * FROM ft")


# ======================================================================
# Handler lifecycle
# ======================================================================


class TestHandlerLifecycle:

    def test_handler_cached_per_server(self, fdw_engine, parquet_path):
        fdw_engine.sql("SELECT * FROM data")
        fdw_engine.sql("SELECT * FROM data")
        assert "local" in fdw_engine._fdw_handlers

    def test_handler_shared_across_tables(
        self, engine, parquet_path, orders_parquet,
    ):
        engine.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine.sql(
            f"CREATE FOREIGN TABLE ft1 (id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine.sql(
            f"CREATE FOREIGN TABLE ft2 "
            f"(order_id INTEGER, product_id INTEGER, "
            f"customer TEXT, quantity INTEGER) "
            f"SERVER local OPTIONS (source '{orders_parquet}')"
        )
        engine.sql("SELECT * FROM ft1")
        engine.sql("SELECT * FROM ft2")
        assert len(engine._fdw_handlers) == 1

    def test_close_clears_handlers(self, fdw_engine):
        fdw_engine.sql("SELECT * FROM data")
        assert len(fdw_engine._fdw_handlers) == 1
        fdw_engine.close()
        assert len(fdw_engine._fdw_handlers) == 0
        assert len(fdw_engine._foreign_tables) == 0
        assert len(fdw_engine._foreign_servers) == 0


# ======================================================================
# information_schema integration
# ======================================================================


class TestInformationSchema:

    def test_foreign_table_type(self, fdw_engine):
        fdw_engine.sql("CREATE TABLE local_t (x INTEGER)")
        result = fdw_engine.sql(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "ORDER BY table_name"
        )
        types = {r["table_name"]: r["table_type"] for r in result.rows}
        assert types["data"] == "FOREIGN TABLE"
        assert types["local_t"] == "BASE TABLE"

    def test_foreign_table_with_view(self, fdw_engine):
        fdw_engine.sql(
            "CREATE VIEW high_value AS "
            "SELECT name FROM data WHERE value > 30"
        )
        result = fdw_engine.sql(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "ORDER BY table_name"
        )
        types = {r["table_name"]: r["table_type"] for r in result.rows}
        assert types["data"] == "FOREIGN TABLE"
        assert types["high_value"] == "VIEW"

    def test_dropped_foreign_table_disappears(self, fdw_engine):
        result1 = fdw_engine.sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_type = 'FOREIGN TABLE'"
        )
        assert any(r["table_name"] == "data" for r in result1.rows)

        fdw_engine.sql("DROP FOREIGN TABLE data")
        result2 = fdw_engine.sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_type = 'FOREIGN TABLE'"
        )
        assert not any(r["table_name"] == "data" for r in result2.rows)


# ======================================================================
# Catalog persistence
# ======================================================================


class TestCatalogPersistence:

    def test_persist_and_restore_server(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine1 = Engine(db_path=db_path)
        engine1.sql(
            "CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw "
            "OPTIONS (database ':memory:')"
        )
        engine1.close()

        engine2 = Engine(db_path=db_path)
        assert "s1" in engine2._foreign_servers
        server = engine2._foreign_servers["s1"]
        assert server.fdw_type == "duckdb_fdw"
        assert server.options["database"] == ":memory:"
        engine2.close()

    def test_persist_and_restore_foreign_table(self, tmp_path, parquet_path):
        db_path = str(tmp_path / "test.db")
        engine1 = Engine(db_path=db_path)
        engine1.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine1.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine1.close()

        engine2 = Engine(db_path=db_path)
        assert "data" in engine2._foreign_tables
        ft = engine2._foreign_tables["data"]
        assert ft.server_name == "local"
        assert list(ft.columns.keys()) == ["id", "name", "value"]
        assert ft.options["source"] == parquet_path
        engine2.close()

    def test_query_after_restore(self, tmp_path, parquet_path):
        db_path = str(tmp_path / "test.db")
        engine1 = Engine(db_path=db_path)
        engine1.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
        engine1.sql(
            f"CREATE FOREIGN TABLE data "
            f"(id INTEGER, name TEXT, value INTEGER) "
            f"SERVER local OPTIONS (source '{parquet_path}')"
        )
        engine1.close()

        engine2 = Engine(db_path=db_path)
        result = engine2.sql("SELECT * FROM data ORDER BY id")
        assert len(result.rows) == 5
        assert result.rows[0]["name"] == "alice"
        engine2.close()

    def test_drop_persists(self, tmp_path, parquet_path):
        db_path = str(tmp_path / "test.db")
        engine1 = Engine(db_path=db_path)
        engine1.sql("CREATE SERVER local FOREIGN DATA WRAPPER duckdb_fdw")
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

    def test_multiple_servers_persist(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine1 = Engine(db_path=db_path)
        engine1.sql("CREATE SERVER s1 FOREIGN DATA WRAPPER duckdb_fdw")
        engine1.sql(
            "CREATE SERVER s2 FOREIGN DATA WRAPPER arrow_fdw "
            "OPTIONS (host 'example.com', port '443')"
        )
        engine1.close()

        engine2 = Engine(db_path=db_path)
        assert "s1" in engine2._foreign_servers
        assert "s2" in engine2._foreign_servers
        assert engine2._foreign_servers["s2"].fdw_type == "arrow_fdw"
        assert engine2._foreign_servers["s2"].options["host"] == "example.com"
        engine2.close()
