#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""usql -- interactive SQL shell for the UQA engine.

Usage:
    usql                        Start with an in-memory database
    usql --db mydata.db         Start with persistent SQLite storage
    usql script.sql             Execute a SQL script then enter REPL
    usql --db mydata.db s.sql   Persistent + script
    usql -c "SELECT 1"          Execute a command string and exit

Special commands (backslash):
    \\dt             List tables
    \\d  <table>     Describe table schema
    \\di             List inverted-index fields
    \\dF             List foreign tables
    \\dS             List foreign servers
    \\dg             List named graphs
    \\ds <table>     Show column statistics (requires ANALYZE first)
    \\x              Toggle expanded (vertical) display
    \\o  [file]      Send output to file (no arg restores stdout)
    \\timing         Toggle query timing display
    \\reset          Reset the engine (drop all tables)
    \\q              Quit
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.sql import SqlLexer

from uqa.engine import Engine
from uqa.sql.compiler import SQLResult

# ------------------------------------------------------------------
# SQL + UQA keyword set for the auto-completer
# ------------------------------------------------------------------

_SQL_KEYWORDS = [
    # DDL
    "CREATE", "TABLE", "DROP", "IF", "EXISTS", "PRIMARY", "KEY",
    "NOT", "NULL", "DEFAULT", "SERIAL", "BIGSERIAL",
    "ALTER", "ADD", "COLUMN", "RENAME", "TO", "SET",
    "TRUNCATE", "UNIQUE", "CHECK", "CONSTRAINT",
    # Types
    "INTEGER", "INT", "BIGINT", "SMALLINT", "TEXT", "VARCHAR",
    "REAL", "FLOAT", "DOUBLE", "PRECISION", "NUMERIC", "DECIMAL",
    "BOOLEAN", "BOOL", "CHAR", "CHARACTER", "JSON", "JSONB",
    # DML
    "INSERT", "INTO", "VALUES", "UPDATE", "DELETE",
    "RETURNING", "ON", "CONFLICT", "DO", "NOTHING", "EXCLUDED",
    # DQL
    "SELECT", "FROM", "WHERE", "AND", "OR", "IN", "BETWEEN",
    "ORDER", "BY", "ASC", "DESC", "LIMIT", "OFFSET", "AS", "DISTINCT",
    "GROUP", "HAVING", "LIKE", "ILIKE", "IS",
    "CASE", "WHEN", "THEN", "ELSE", "END",
    "CAST", "COALESCE", "NULLIF",
    "UNION", "ALL", "EXCEPT", "INTERSECT",
    # Joins
    "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "OUTER",
    # Subqueries / CTE
    "WITH", "RECURSIVE",
    # Aggregates
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "ARRAY_AGG", "BOOL_AND", "BOOL_OR", "FILTER",
    # Window functions
    "OVER", "PARTITION", "WINDOW",
    "ROWS", "RANGE", "UNBOUNDED", "PRECEDING", "FOLLOWING",
    "CURRENT", "ROW",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE",
    "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
    "PERCENT_RANK", "CUME_DIST",
    # FDW
    "SERVER", "FOREIGN", "DATA", "WRAPPER", "OPTIONS", "IMPORT",
    # Utility
    "EXPLAIN", "ANALYZE", "GENERATE_SERIES",
    # UQA extensions
    "text_match", "bayesian_match", "knn_match",
    "traverse", "rpq", "text_search",
    "traverse_match",
    "fuse_log_odds", "fuse_prob_and", "fuse_prob_or", "fuse_prob_not",
    # Cypher integration
    "cypher", "create_graph", "drop_graph",
]

_STYLE = Style.from_dict({
    "prompt": "ansicyan bold",
    "bottom-toolbar": "bg:ansibrightblack ansiwhite",
})


# ------------------------------------------------------------------
# Dynamic completer: SQL keywords + live table/column names
# ------------------------------------------------------------------

_BACKSLASH_COMMANDS = [
    ("\\dt", "List tables"),
    ("\\d", "Describe table"),
    ("\\di", "List indexes"),
    ("\\dF", "List foreign tables"),
    ("\\dS", "List foreign servers"),
    ("\\dg", "List graphs"),
    ("\\ds", "Show statistics"),
    ("\\x", "Expanded display"),
    ("\\o", "Output to file"),
    ("\\timing", "Toggle timing"),
    ("\\reset", "Reset engine"),
    ("\\q", "Quit"),
    ("\\?", "Help"),
]


class SQLCompleter(Completer):
    """Context-aware SQL completer that includes table and column names."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._keyword_upper = {kw.upper() for kw in _SQL_KEYWORDS}

    def get_completions(
        self, document: Document, complete_event: object
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # Backslash command completion
        if text.lstrip().startswith("\\"):
            prefix = text.lstrip()
            for cmd, desc in _BACKSLASH_COMMANDS:
                if cmd.startswith(prefix):
                    yield Completion(
                        cmd,
                        start_position=-len(prefix),
                        display_meta=desc,
                    )
            return

        word = document.get_word_before_cursor()
        if not word:
            return

        upper = word.upper()

        # Check the keyword immediately before the current word
        before_word = document.text_before_cursor[: -len(word)].upper()
        after_table_kw = any(
            before_word.rstrip().endswith(kw)
            for kw in ("FROM", "INTO", "TABLE", "ANALYZE", "JOIN")
        )

        candidates: list[tuple[str, str]] = []

        # SQL keywords
        for kw in _SQL_KEYWORDS:
            if kw.upper().startswith(upper):
                candidates.append((kw, "keyword"))

        # Table names (regular + foreign)
        for name in self._engine._tables:
            if name.upper().startswith(upper):
                candidates.append((name, "table"))
        for name in self._engine._foreign_tables:
            if name.upper().startswith(upper):
                candidates.append((name, "foreign table"))

        # Column names (from all known tables, regular + foreign)
        if not after_table_kw:
            seen: set[str] = set()
            for table in self._engine._tables.values():
                for col_name in table.columns:
                    if col_name not in seen and col_name.upper().startswith(upper):
                        seen.add(col_name)
                        candidates.append((col_name, "column"))
            for ftable in self._engine._foreign_tables.values():
                for col_name in ftable.columns:
                    if col_name not in seen and col_name.upper().startswith(upper):
                        seen.add(col_name)
                        candidates.append((col_name, "column"))

        # Sort: tables first when after FROM/INTO, otherwise keywords first
        def sort_key(item: tuple[str, str]) -> tuple[int, str]:
            text, kind = item
            if after_table_kw:
                order = {
                    "table": 0, "foreign table": 1,
                    "keyword": 2, "column": 3,
                }
            else:
                order = {
                    "keyword": 0, "column": 1,
                    "table": 2, "foreign table": 3,
                }
            return (order.get(kind, 9), text.lower())

        candidates.sort(key=sort_key)

        for text, kind in candidates:
            display_meta = kind
            yield Completion(
                text, start_position=-len(word), display_meta=display_meta
            )


# ------------------------------------------------------------------
# Shell
# ------------------------------------------------------------------

class UQAShell:
    """Interactive SQL shell backed by a UQA Engine."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._engine = Engine(db_path=db_path)
        self._show_timing = False
        self._expanded = False
        self._output_file: str | None = None
        self._completer = SQLCompleter(self._engine)
        self._session: PromptSession | None = None

    # -- public API -------------------------------------------------

    def run_file(self, path: str) -> None:
        """Execute every statement in a SQL script file."""
        with open(path) as f:
            text = f.read()
        self._execute_text(text)

    @staticmethod
    def _history_path() -> str:
        """Return the path to the usql history file, creating the directory if needed."""
        history_dir = Path(os.path.expanduser("~/.cognica/uqa"))
        history_dir.mkdir(parents=True, exist_ok=True)
        return str(history_dir / ".usql_history")

    def _ensure_session(self) -> PromptSession:
        """Lazily create the PromptSession on first REPL use."""
        if self._session is None:
            self._session = PromptSession(
                history=FileHistory(self._history_path()),
                auto_suggest=AutoSuggestFromHistory(),
                lexer=PygmentsLexer(SqlLexer),
                completer=self._completer,
                style=_STYLE,
                multiline=False,
                complete_while_typing=True,
            )
        return self._session

    def repl(self) -> None:
        """Enter the read-eval-print loop."""
        session = self._ensure_session()
        self._print_banner()
        buf = ""
        while True:
            try:
                prompt = "usql> " if not buf else "  ... "
                line = session.prompt(
                    HTML(f"<prompt>{prompt}</prompt>"),
                    bottom_toolbar=self._toolbar,
                )
            except KeyboardInterrupt:
                if buf:
                    buf = ""
                    print()
                    continue
                print()
                continue
            except EOFError:
                print()
                break

            stripped = line.strip()

            # Empty line when no buffer: do nothing
            if not stripped and not buf:
                continue

            # Backslash commands (only at the start, not inside a buffer)
            if not buf and stripped.startswith("\\"):
                self._handle_backslash(stripped)
                continue

            buf += line + "\n"

            # A semicolon terminates the statement
            if ";" not in buf:
                continue

            self._execute_text(buf)
            buf = ""

    # -- statement execution ----------------------------------------

    def _execute_text(self, text: str) -> None:
        """Split on semicolons and execute each statement."""
        for raw in text.split(";"):
            stmt = raw.strip()
            if not stmt:
                continue
            # Skip pure comments
            if all(
                ln.strip().startswith("--") or not ln.strip()
                for ln in stmt.splitlines()
            ):
                continue
            self._execute_one(stmt)

    def _execute_one(self, stmt: str) -> None:
        t0 = time.perf_counter()
        try:
            result = self._engine.sql(stmt)
        except Exception as exc:
            print(f"ERROR: {exc}")
            return
        elapsed = (time.perf_counter() - t0) * 1000.0

        self._print_result(result)
        if self._show_timing:
            self._output(f"Time: {elapsed:.3f} ms")

    def _output(self, text: str) -> None:
        """Print to the current output destination (stdout or file)."""
        if self._output_file is not None:
            with open(self._output_file, "a") as f:
                f.write(text + "\n")
        else:
            print(text)

    def _print_result(self, result: SQLResult) -> None:
        # Suppress output for DDL/utility (empty columns = no output)
        if not result.columns and not result.rows:
            return
        if self._expanded:
            self._print_expanded(result)
        else:
            self._output(str(result))

    def _print_expanded(self, result: SQLResult) -> None:
        """Print result in vertical (expanded) format, one column per line."""
        rows = result.rows
        if not rows:
            self._output("(0 rows)")
            return
        col_width = max(len(c) for c in result.columns)
        parts: list[str] = []
        for i, row in enumerate(rows):
            parts.append(f"-[ RECORD {i + 1} ]" + "-" * max(0, col_width - 7))
            for col in result.columns:
                val = row.get(col, "")
                parts.append(f"{col:<{col_width}} | {val}")
        parts.append(f"({len(rows)} rows)")
        self._output("\n".join(parts))

    # -- backslash commands -----------------------------------------

    def _handle_backslash(self, cmd: str) -> None:
        parts = cmd.split(None, 1)
        verb = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb in ("\\q", "\\quit"):
            raise SystemExit(0)

        if verb == "\\dt":
            self._cmd_list_tables()
        elif verb == "\\d":
            self._cmd_describe_table(arg)
        elif verb == "\\di":
            self._cmd_list_indexes()
        elif verb == "\\dF":
            self._cmd_list_foreign_tables()
        elif verb == "\\dS":
            self._cmd_list_foreign_servers()
        elif verb == "\\dg":
            self._cmd_list_graphs()
        elif verb == "\\ds":
            self._cmd_show_stats(arg)
        elif verb == "\\x":
            self._expanded = not self._expanded
            state = "on" if self._expanded else "off"
            print(f"Expanded display is {state}.")
        elif verb == "\\o":
            self._cmd_output(arg)
        elif verb == "\\timing":
            self._show_timing = not self._show_timing
            state = "on" if self._show_timing else "off"
            print(f"Timing is {state}.")
        elif verb == "\\reset":
            self._engine.close()
            self._engine = Engine(db_path=self._db_path)
            self._completer._engine = self._engine
            print("Engine reset.")
        elif verb in ("\\h", "\\help", "\\?"):
            self._cmd_help()
        else:
            print(f"Unknown command: {verb}")
            self._cmd_help()

    def _cmd_list_tables(self) -> None:
        tables = self._engine._tables
        ftables = self._engine._foreign_tables
        if not tables and not ftables:
            print("No tables.")
            return
        rows = []
        for name, table in sorted(tables.items()):
            rows.append({
                "table_name": name,
                "type": "table",
                "columns": len(table.columns),
                "rows": table.row_count,
            })
        for name, ft in sorted(ftables.items()):
            rows.append({
                "table_name": name,
                "type": "foreign",
                "columns": len(ft.columns),
                "rows": "",
            })
        print(SQLResult(["table_name", "type", "columns", "rows"], rows))

    def _cmd_describe_table(self, name: str) -> None:
        if not name:
            print("Usage: \\d <table_name>")
            return
        table = self._engine._tables.get(name)
        ftable = self._engine._foreign_tables.get(name) if table is None else None
        if table is None and ftable is None:
            print(f"Table '{name}' does not exist.")
            return
        rows = []
        if table is not None:
            for col in table.columns.values():
                flags = []
                if col.primary_key:
                    flags.append("PK")
                if col.not_null:
                    flags.append("NOT NULL")
                if col.auto_increment:
                    flags.append("AUTO")
                if col.default is not None:
                    flags.append(f"DEFAULT {col.default}")
                rows.append({
                    "column": col.name,
                    "type": col.type_name,
                    "constraints": " ".join(flags) if flags else "",
                })
            print(f'Table "{name}"')
        else:
            for col in ftable.columns.values():
                rows.append({
                    "column": col.name,
                    "type": col.type_name,
                    "constraints": "",
                })
            print(f'Foreign table "{name}" (server: {ftable.server_name})')
        print(SQLResult(["column", "type", "constraints"], rows))

    def _cmd_show_stats(self, name: str) -> None:
        if not name:
            print("Usage: \\ds <table_name>")
            return
        table = self._engine._tables.get(name)
        if table is None:
            print(f"Table '{name}' does not exist.")
            return
        if not table._stats:
            print(f"No statistics for '{name}'. Run ANALYZE {name} first.")
            return
        rows = []
        for col_name, cs in table._stats.items():
            rows.append({
                "column": col_name,
                "distinct": cs.distinct_count,
                "nulls": cs.null_count,
                "min": cs.min_value if cs.min_value is not None else "",
                "max": cs.max_value if cs.max_value is not None else "",
                "selectivity": cs.selectivity,
            })
        print(f'Statistics for "{name}" ({table.row_count} rows)')
        print(SQLResult(
            ["column", "distinct", "nulls", "min", "max", "selectivity"],
            rows,
        ))

    def _cmd_list_indexes(self) -> None:
        tables = self._engine._tables
        if not tables:
            print("No tables.")
            return
        rows = []
        for name, table in sorted(tables.items()):
            idx = table.inverted_index
            if hasattr(idx, "_known_fields"):
                fields = sorted(idx._known_fields)
            else:
                fields = sorted({f for (f, _) in idx._index})
            if fields:
                rows.append({
                    "table_name": name,
                    "indexed_fields": ", ".join(fields),
                })
        if not rows:
            print("No indexed fields.")
            return
        print(SQLResult(["table_name", "indexed_fields"], rows))

    def _cmd_list_foreign_tables(self) -> None:
        ftables = self._engine._foreign_tables
        if not ftables:
            print("No foreign tables.")
            return
        rows = []
        for name, ft in sorted(ftables.items()):
            opts = []
            if ft.options.get("hive_partitioning", "").lower() == "true":
                opts.append("hive")
            source = ft.options.get("source", "")
            rows.append({
                "table_name": name,
                "server": ft.server_name,
                "columns": len(ft.columns),
                "source": source,
                "options": ", ".join(opts) if opts else "",
            })
        print(SQLResult(
            ["table_name", "server", "columns", "source", "options"], rows
        ))

    def _cmd_list_foreign_servers(self) -> None:
        servers = self._engine._foreign_servers
        if not servers:
            print("No foreign servers.")
            return
        rows = []
        for name, srv in sorted(servers.items()):
            opts = " ".join(f"{k}={v}" for k, v in srv.options.items())
            rows.append({
                "server_name": name,
                "fdw_type": srv.fdw_type,
                "options": opts,
            })
        print(SQLResult(["server_name", "fdw_type", "options"], rows))

    def _cmd_list_graphs(self) -> None:
        graphs = self._engine._named_graphs
        if not graphs:
            print("No named graphs.")
            return
        rows = []
        for name, store in sorted(graphs.items()):
            rows.append({
                "graph_name": name,
                "vertices": len(store._vertices),
                "edges": len(store._edges),
            })
        print(SQLResult(["graph_name", "vertices", "edges"], rows))

    def _cmd_output(self, arg: str) -> None:
        if arg:
            self._output_file = arg
            print(f"Output redirected to: {arg}")
        else:
            if self._output_file is not None:
                print(f"Output restored to stdout (was: {self._output_file}).")
            self._output_file = None

    @staticmethod
    def _cmd_help() -> None:
        print("Backslash commands:")
        print("  \\dt             List tables")
        print("  \\d  <table>     Describe table schema")
        print("  \\di             List inverted-index fields")
        print("  \\dF             List foreign tables")
        print("  \\dS             List foreign servers")
        print("  \\dg             List named graphs")
        print("  \\ds <table>     Show column statistics")
        print("  \\x              Toggle expanded display")
        print("  \\o  [file]      Redirect output to file")
        print("  \\timing         Toggle query timing")
        print("  \\reset          Reset engine")
        print("  \\q              Quit")

    # -- UI helpers -------------------------------------------------

    def _toolbar(self) -> str:
        nt = len(self._engine._tables)
        nf = len(self._engine._foreign_tables)
        timing = "on" if self._show_timing else "off"
        expanded = "on" if self._expanded else "off"
        db = self._db_path or ":memory:"
        parts = [f"db: {db}", f"tables: {nt}"]
        if nf:
            parts.append(f"foreign: {nf}")
        parts.extend([f"timing: {timing}", f"expanded: {expanded}"])
        if self._output_file:
            parts.append(f"output: {self._output_file}")
        parts.append("\\? for help")
        return " usql | " + " | ".join(parts) + " "

    def _print_banner(self) -> None:
        db = self._db_path or ":memory:"
        from uqa import __version__
        print(f"usql {__version__} -- UQA interactive SQL shell")
        print(f"Database: {db}")
        print("Type SQL statements terminated by ';'")
        print("Use \\? for help, \\q to quit.")
        print()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="usql -- UQA interactive SQL shell"
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="SQLite database file for persistent storage",
    )
    parser.add_argument(
        "-c",
        metavar="COMMAND",
        default=None,
        help="Execute a single SQL command string and exit",
    )
    parser.add_argument(
        "scripts",
        nargs="*",
        metavar="script.sql",
        help="SQL script files to execute before entering REPL",
    )
    args = parser.parse_args()

    shell = UQAShell(db_path=args.db)

    # -c: execute command string and exit (no REPL)
    if args.c is not None:
        try:
            shell._execute_text(args.c)
        finally:
            shell._engine.close()
        return

    for path in args.scripts:
        try:
            shell.run_file(path)
        except FileNotFoundError:
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Enter REPL only when stdin is a terminal.
    # When script files are given without a terminal, exit after execution.
    try:
        if sys.stdin.isatty():
            shell.repl()
        elif not args.scripts:
            shell.repl()
    finally:
        shell._engine.close()


if __name__ == "__main__":
    main()
