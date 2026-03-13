#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the usql interactive shell (uqa.cli)."""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.cli import _SQL_KEYWORDS, UQAShell

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture()
def shell():
    """In-memory shell for testing."""
    s = UQAShell()
    yield s
    s._engine.close()


@pytest.fixture()
def shell_with_table(shell):
    """Shell with a simple table pre-created."""
    shell._engine.sql("CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT, age INT)")
    shell._engine.sql("INSERT INTO users (name, age) VALUES ('Alice', 30)")
    shell._engine.sql("INSERT INTO users (name, age) VALUES ('Bob', 25)")
    return shell


@pytest.fixture()
def shell_with_foreign_table(shell):
    """Shell with a DuckDB foreign server and table."""
    try:
        import duckdb  # noqa: F401
    except ImportError:
        pytest.skip("duckdb not installed")

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        parquet_path = f.name

    try:
        import duckdb as _duckdb

        conn = _duckdb.connect()
        conn.execute(
            f"COPY (SELECT 1 AS id, 'x' AS val) TO '{parquet_path}' (FORMAT PARQUET)"
        )
        conn.close()

        shell._engine.sql("CREATE SERVER test_srv FOREIGN DATA WRAPPER duckdb_fdw")
        shell._engine.sql(
            f"CREATE FOREIGN TABLE ftest ("
            f"  id INTEGER, val TEXT"
            f") SERVER test_srv OPTIONS (source '{parquet_path}')"
        )
        yield shell
    finally:
        os.unlink(parquet_path)


# ------------------------------------------------------------------
# Keyword expansion
# ------------------------------------------------------------------


class TestKeywords:
    """Verify the expanded keyword list covers key categories."""

    def test_ddl_keywords(self):
        for kw in (
            "ALTER",
            "ADD",
            "COLUMN",
            "RENAME",
            "TRUNCATE",
            "UNIQUE",
            "CHECK",
            "CONSTRAINT",
        ):
            assert kw in _SQL_KEYWORDS

    def test_dml_keywords(self):
        for kw in ("UPDATE", "DELETE", "RETURNING", "CONFLICT", "EXCLUDED"):
            assert kw in _SQL_KEYWORDS

    def test_join_keywords(self):
        for kw in ("RIGHT", "FULL", "CROSS"):
            assert kw in _SQL_KEYWORDS

    def test_window_keywords(self):
        for kw in (
            "OVER",
            "PARTITION",
            "WINDOW",
            "ROWS",
            "RANGE",
            "UNBOUNDED",
            "PRECEDING",
            "FOLLOWING",
            "ROW_NUMBER",
            "RANK",
            "DENSE_RANK",
            "PERCENT_RANK",
            "CUME_DIST",
            "NTH_VALUE",
        ):
            assert kw in _SQL_KEYWORDS

    def test_fdw_keywords(self):
        for kw in ("SERVER", "FOREIGN", "DATA", "WRAPPER", "OPTIONS"):
            assert kw in _SQL_KEYWORDS

    def test_cypher_keywords(self):
        for kw in ("cypher", "create_graph", "drop_graph"):
            assert kw in _SQL_KEYWORDS

    def test_cte_keywords(self):
        assert "WITH" in _SQL_KEYWORDS
        assert "RECURSIVE" in _SQL_KEYWORDS

    def test_aggregate_keywords(self):
        for kw in ("ARRAY_AGG", "BOOL_AND", "BOOL_OR", "FILTER"):
            assert kw in _SQL_KEYWORDS

    def test_type_keywords(self):
        assert "JSON" in _SQL_KEYWORDS
        assert "JSONB" in _SQL_KEYWORDS

    def test_misc_keywords(self):
        for kw in (
            "CASE",
            "WHEN",
            "THEN",
            "ELSE",
            "END",
            "CAST",
            "COALESCE",
            "NULLIF",
            "UNION",
            "ALL",
            "EXCEPT",
            "INTERSECT",
            "OFFSET",
            "ILIKE",
            "GENERATE_SERIES",
        ):
            assert kw in _SQL_KEYWORDS


# ------------------------------------------------------------------
# Completer
# ------------------------------------------------------------------


class TestCompleter:
    """Test auto-completion with backslash commands and foreign tables."""

    def test_completes_backslash_commands(self, shell):
        from prompt_toolkit.document import Document

        completer = shell._completer
        doc = Document("\\d")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "\\dt" in texts
        assert "\\di" in texts
        assert "\\dF" in texts
        assert "\\dS" in texts
        assert "\\dg" in texts
        assert "\\ds" in texts

    def test_completes_backslash_single(self, shell):
        from prompt_toolkit.document import Document

        completer = shell._completer
        doc = Document("\\")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "\\dt" in texts
        assert "\\x" in texts
        assert "\\o" in texts
        assert "\\timing" in texts
        assert "\\q" in texts
        assert "\\?" in texts

    def test_backslash_shows_descriptions(self, shell):
        from prompt_toolkit.document import Document

        completer = shell._completer
        doc = Document("\\x")
        results = list(completer.get_completions(doc, None))
        assert len(results) == 1
        assert results[0].text == "\\x"
        assert "Expanded" in str(results[0].display_meta)

    def test_backslash_no_sql_keywords(self, shell):
        from prompt_toolkit.document import Document

        completer = shell._completer
        doc = Document("\\t")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "\\timing" in texts
        assert "TEXT" not in texts

    def test_completes_regular_table(self, shell_with_table):
        from prompt_toolkit.document import Document

        completer = shell_with_table._completer
        doc = Document("SELECT * FROM use")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "users" in texts

    def test_completes_foreign_table(self, shell_with_foreign_table):
        from prompt_toolkit.document import Document

        completer = shell_with_foreign_table._completer
        doc = Document("SELECT * FROM fte")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "ftest" in texts
        metas = [str(c.display_meta) for c in results if c.text == "ftest"]
        assert "foreign table" in metas[0]

    def test_completes_foreign_table_columns(self, shell_with_foreign_table):
        from prompt_toolkit.document import Document

        completer = shell_with_foreign_table._completer
        doc = Document("SELECT va")
        results = list(completer.get_completions(doc, None))
        texts = [c.text for c in results]
        assert "val" in texts


# ------------------------------------------------------------------
# \dt -- list tables (with type column)
# ------------------------------------------------------------------


class TestListTables:
    def test_list_tables_empty(self, shell, capsys):
        shell._cmd_list_tables()
        assert "No tables." in capsys.readouterr().out

    def test_list_tables_with_regular(self, shell_with_table, capsys):
        shell_with_table._cmd_list_tables()
        out = capsys.readouterr().out
        assert "users" in out
        assert "table" in out

    def test_list_tables_includes_foreign(self, shell_with_foreign_table, capsys):
        shell_with_foreign_table._cmd_list_tables()
        out = capsys.readouterr().out
        assert "ftest" in out
        assert "foreign" in out


# ------------------------------------------------------------------
# \d -- describe table (regular + foreign)
# ------------------------------------------------------------------


class TestDescribeTable:
    def test_describe_regular_table(self, shell_with_table, capsys):
        shell_with_table._cmd_describe_table("users")
        out = capsys.readouterr().out
        assert 'Table "users"' in out
        assert "name" in out
        assert "age" in out

    def test_describe_foreign_table(self, shell_with_foreign_table, capsys):
        shell_with_foreign_table._cmd_describe_table("ftest")
        out = capsys.readouterr().out
        assert 'Foreign table "ftest"' in out
        assert "test_srv" in out
        assert "id" in out
        assert "val" in out

    def test_describe_nonexistent(self, shell, capsys):
        shell._cmd_describe_table("nope")
        assert "does not exist" in capsys.readouterr().out

    def test_describe_no_arg(self, shell, capsys):
        shell._cmd_describe_table("")
        assert "Usage" in capsys.readouterr().out


# ------------------------------------------------------------------
# \di -- list indexes
# ------------------------------------------------------------------


class TestListIndexes:
    def test_no_tables(self, shell, capsys):
        shell._cmd_list_indexes()
        assert "No tables." in capsys.readouterr().out

    def test_no_indexed_fields(self, shell, capsys):
        shell._engine.sql("CREATE TABLE nums (id INT PRIMARY KEY, val INT)")
        shell._cmd_list_indexes()
        assert "No indexed fields." in capsys.readouterr().out

    def test_shows_indexed_text_fields(self, shell, capsys):
        shell._engine.sql(
            "CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, body TEXT)"
        )
        shell._engine.sql("INSERT INTO docs (title, body) VALUES ('Hello', 'World')")
        shell._cmd_list_indexes()
        out = capsys.readouterr().out
        assert "docs" in out
        assert "title" in out
        assert "body" in out


# ------------------------------------------------------------------
# \dF -- list foreign tables
# ------------------------------------------------------------------


class TestListForeignTables:
    def test_no_foreign_tables(self, shell, capsys):
        shell._cmd_list_foreign_tables()
        assert "No foreign tables." in capsys.readouterr().out

    def test_lists_foreign_table(self, shell_with_foreign_table, capsys):
        shell_with_foreign_table._cmd_list_foreign_tables()
        out = capsys.readouterr().out
        assert "ftest" in out
        assert "test_srv" in out


# ------------------------------------------------------------------
# \dS -- list foreign servers
# ------------------------------------------------------------------


class TestListForeignServers:
    def test_no_foreign_servers(self, shell, capsys):
        shell._cmd_list_foreign_servers()
        assert "No foreign servers." in capsys.readouterr().out

    def test_lists_foreign_server(self, shell_with_foreign_table, capsys):
        shell_with_foreign_table._cmd_list_foreign_servers()
        out = capsys.readouterr().out
        assert "test_srv" in out
        assert "duckdb_fdw" in out


# ------------------------------------------------------------------
# \dg -- list graphs
# ------------------------------------------------------------------


class TestListGraphs:
    def test_no_graphs(self, shell, capsys):
        shell._cmd_list_graphs()
        assert "No named graphs." in capsys.readouterr().out

    def test_lists_graph(self, shell, capsys):
        shell._engine.sql("SELECT * FROM create_graph('social')")
        shell._engine.sql(
            "SELECT * FROM cypher('social', $$ "
            "CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'}) "
            "RETURN a $$) AS (v agtype)"
        )
        shell._cmd_list_graphs()
        out = capsys.readouterr().out
        assert "social" in out
        assert "2" in out  # 2 vertices
        assert "1" in out  # 1 edge


# ------------------------------------------------------------------
# \x -- expanded display
# ------------------------------------------------------------------


class TestExpandedDisplay:
    def test_toggle_expanded(self, shell, capsys):
        assert not shell._expanded
        shell._handle_backslash("\\x")
        assert shell._expanded
        out = capsys.readouterr().out
        assert "on" in out

        shell._handle_backslash("\\x")
        assert not shell._expanded
        out = capsys.readouterr().out
        assert "off" in out

    def test_expanded_output(self, shell_with_table, capsys):
        shell_with_table._expanded = True
        result = shell_with_table._engine.sql("SELECT * FROM users ORDER BY id")
        shell_with_table._print_result(result)
        out = capsys.readouterr().out
        assert "-[ RECORD 1 ]" in out
        assert "-[ RECORD 2 ]" in out
        assert "Alice" in out
        assert "Bob" in out
        assert "(2 rows)" in out

    def test_expanded_empty(self, shell, capsys):
        from uqa.sql.compiler import SQLResult

        shell._expanded = True
        result = SQLResult(["a"], [])
        shell._print_result(result)
        out = capsys.readouterr().out
        assert "(0 rows)" in out

    def test_normal_output_unchanged(self, shell_with_table, capsys):
        assert not shell_with_table._expanded
        result = shell_with_table._engine.sql("SELECT * FROM users ORDER BY id")
        shell_with_table._print_result(result)
        out = capsys.readouterr().out
        assert "RECORD" not in out
        assert "Alice" in out


# ------------------------------------------------------------------
# \o -- output to file
# ------------------------------------------------------------------


class TestOutputRedirection:
    def test_redirect_to_file(self, shell_with_table):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name

        try:
            shell_with_table._cmd_output(path)
            assert shell_with_table._output_file == path

            result = shell_with_table._engine.sql("SELECT * FROM users ORDER BY id")
            shell_with_table._print_result(result)

            with open(path) as f:
                content = f.read()
            assert "Alice" in content
            assert "Bob" in content
        finally:
            os.unlink(path)

    def test_restore_stdout(self, shell, capsys):
        shell._output_file = "/tmp/test_usql_out.txt"
        shell._cmd_output("")
        assert shell._output_file is None
        out = capsys.readouterr().out
        assert "stdout" in out

    def test_output_timing_to_file(self, shell_with_table):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name

        try:
            shell_with_table._output_file = path
            shell_with_table._show_timing = True

            shell_with_table._execute_one("SELECT 1 AS x")

            with open(path) as f:
                content = f.read()
            assert "Time:" in content
        finally:
            os.unlink(path)

    def test_expanded_to_file(self, shell_with_table):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name

        try:
            shell_with_table._output_file = path
            shell_with_table._expanded = True

            result = shell_with_table._engine.sql("SELECT * FROM users ORDER BY id")
            shell_with_table._print_result(result)

            with open(path) as f:
                content = f.read()
            assert "RECORD 1" in content
        finally:
            os.unlink(path)


# ------------------------------------------------------------------
# Backslash dispatch
# ------------------------------------------------------------------


class TestBackslashDispatch:
    def test_di(self, shell, capsys):
        shell._handle_backslash("\\di")
        out = capsys.readouterr().out
        assert "No tables" in out or "No indexed" in out

    def test_dF(self, shell, capsys):
        shell._handle_backslash("\\dF")
        assert "No foreign tables." in capsys.readouterr().out

    def test_dS(self, shell, capsys):
        shell._handle_backslash("\\dS")
        assert "No foreign servers." in capsys.readouterr().out

    def test_dg(self, shell, capsys):
        shell._handle_backslash("\\dg")
        assert "No named graphs." in capsys.readouterr().out

    def test_x_dispatch(self, shell, capsys):
        shell._handle_backslash("\\x")
        assert shell._expanded is True

    def test_o_dispatch(self, shell, capsys):
        shell._handle_backslash("\\o /tmp/usql_test_dispatch.txt")
        assert shell._output_file == "/tmp/usql_test_dispatch.txt"
        shell._cmd_output("")  # restore

    def test_help(self, shell, capsys):
        shell._handle_backslash("\\?")
        out = capsys.readouterr().out
        assert "\\di" in out
        assert "\\dF" in out
        assert "\\dS" in out
        assert "\\dg" in out
        assert "\\x" in out
        assert "\\o" in out

    def test_unknown_command(self, shell, capsys):
        shell._handle_backslash("\\zzz")
        out = capsys.readouterr().out
        assert "Unknown command" in out


# ------------------------------------------------------------------
# Toolbar
# ------------------------------------------------------------------


class TestToolbar:
    def test_toolbar_default(self, shell):
        tb = shell._toolbar()
        assert "tables: 0" in tb
        assert "timing: off" in tb
        assert "expanded: off" in tb
        assert "\\? for help" in tb

    def test_toolbar_with_foreign(self, shell_with_foreign_table):
        tb = shell_with_foreign_table._toolbar()
        assert "foreign:" in tb

    def test_toolbar_with_output(self, shell):
        shell._output_file = "/tmp/out.txt"
        tb = shell._toolbar()
        assert "output: /tmp/out.txt" in tb

    def test_toolbar_timing_on(self, shell):
        shell._show_timing = True
        tb = shell._toolbar()
        assert "timing: on" in tb

    def test_toolbar_expanded_on(self, shell):
        shell._expanded = True
        tb = shell._toolbar()
        assert "expanded: on" in tb


# ------------------------------------------------------------------
# Banner
# ------------------------------------------------------------------


class TestBanner:
    def test_banner(self, shell, capsys):
        shell._print_banner()
        out = capsys.readouterr().out
        assert "usql" in out
        assert "\\?" in out
        assert "\\q" in out
