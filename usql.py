#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""usql -- interactive SQL shell for the UQA engine.

Usage:
    python usql.py                        Start with an in-memory database
    python usql.py --db mydata.db         Start with persistent SQLite storage
    python usql.py script.sql             Execute a SQL script then enter REPL
    python usql.py --db mydata.db s.sql   Persistent + script

Special commands (backslash):
    \\dt             List tables
    \\d  <table>     Describe table schema
    \\ds <table>     Show column statistics (requires ANALYZE first)
    \\timing         Toggle query timing display
    \\reset          Reset the engine (drop all tables)
    \\q              Quit
"""

from __future__ import annotations

import argparse
import sys
import time
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
    # Types
    "INTEGER", "INT", "BIGINT", "SMALLINT", "TEXT", "VARCHAR",
    "REAL", "FLOAT", "DOUBLE", "PRECISION", "NUMERIC", "DECIMAL",
    "BOOLEAN", "BOOL", "CHAR", "CHARACTER",
    # DML
    "INSERT", "INTO", "VALUES",
    # DQL
    "SELECT", "FROM", "WHERE", "AND", "OR", "IN", "BETWEEN",
    "ORDER", "BY", "ASC", "DESC", "LIMIT", "AS", "DISTINCT",
    "GROUP", "HAVING", "JOIN", "INNER", "LEFT", "OUTER", "ON",
    "LIKE", "IS",
    # Aggregates
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    # Utility
    "EXPLAIN", "ANALYZE",
    # UQA extensions
    "text_match", "bayesian_match", "knn_match",
    "traverse", "rpq", "text_search",
    "traverse_match",
    "fuse_log_odds", "fuse_prob_and", "fuse_prob_or", "fuse_prob_not",
]

_STYLE = Style.from_dict({
    "prompt": "ansicyan bold",
    "bottom-toolbar": "bg:ansibrightblack ansiwhite",
})


# ------------------------------------------------------------------
# Dynamic completer: SQL keywords + live table/column names
# ------------------------------------------------------------------

class SQLCompleter(Completer):
    """Context-aware SQL completer that includes table and column names."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._keyword_upper = {kw.upper() for kw in _SQL_KEYWORDS}

    def get_completions(
        self, document: Document, complete_event: object
    ) -> Iterable[Completion]:
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

        # Table names
        for name in self._engine._tables:
            if name.upper().startswith(upper):
                candidates.append((name, "table"))

        # Column names (from all known tables)
        if not after_table_kw:
            seen: set[str] = set()
            for table in self._engine._tables.values():
                for col_name in table.columns:
                    if col_name not in seen and col_name.upper().startswith(upper):
                        seen.add(col_name)
                        candidates.append((col_name, "column"))

        # Sort: tables first when after FROM/INTO, otherwise keywords first
        def sort_key(item: tuple[str, str]) -> tuple[int, str]:
            text, kind = item
            if after_table_kw:
                order = {"table": 0, "keyword": 1, "column": 2}
            else:
                order = {"keyword": 0, "column": 1, "table": 2}
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
        self._engine = Engine(
            db_path=db_path, vector_dimensions=64, max_elements=10000
        )
        self._show_timing = False
        self._completer = SQLCompleter(self._engine)
        self._session: PromptSession = PromptSession(
            history=FileHistory(".usql_history"),
            auto_suggest=AutoSuggestFromHistory(),
            lexer=PygmentsLexer(SqlLexer),
            completer=self._completer,
            style=_STYLE,
            multiline=False,
            complete_while_typing=True,
        )

    # -- public API -------------------------------------------------

    def run_file(self, path: str) -> None:
        """Execute every statement in a SQL script file."""
        with open(path) as f:
            text = f.read()
        self._execute_text(text)

    def repl(self) -> None:
        """Enter the read-eval-print loop."""
        self._print_banner()
        buf = ""
        while True:
            try:
                prompt = "usql> " if not buf else "  ... "
                line = self._session.prompt(
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
            print(f"Time: {elapsed:.3f} ms")

    def _print_result(self, result: SQLResult) -> None:
        # Suppress output for DDL/utility (empty columns = no output)
        if not result.columns and not result.rows:
            return
        print(str(result))

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
        elif verb == "\\ds":
            self._cmd_show_stats(arg)
        elif verb == "\\timing":
            self._show_timing = not self._show_timing
            state = "on" if self._show_timing else "off"
            print(f"Timing is {state}.")
        elif verb == "\\reset":
            self._engine.close()
            self._engine = Engine(
                db_path=self._db_path,
                vector_dimensions=64,
                max_elements=10000,
            )
            self._completer._engine = self._engine
            print("Engine reset.")
        elif verb in ("\\h", "\\help", "\\?"):
            self._cmd_help()
        else:
            print(f"Unknown command: {verb}")
            self._cmd_help()

    def _cmd_list_tables(self) -> None:
        tables = self._engine._tables
        if not tables:
            print("No tables.")
            return
        rows = []
        for name, table in sorted(tables.items()):
            rows.append({
                "table_name": name,
                "columns": len(table.columns),
                "rows": table.row_count,
            })
        print(SQLResult(["table_name", "columns", "rows"], rows))

    def _cmd_describe_table(self, name: str) -> None:
        if not name:
            print("Usage: \\d <table_name>")
            return
        table = self._engine._tables.get(name)
        if table is None:
            print(f"Table '{name}' does not exist.")
            return
        rows = []
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

    @staticmethod
    def _cmd_help() -> None:
        print("Backslash commands:")
        print("  \\dt             List tables")
        print("  \\d  <table>     Describe table schema")
        print("  \\ds <table>     Show column statistics")
        print("  \\timing         Toggle query timing")
        print("  \\reset          Reset engine")
        print("  \\q              Quit")

    # -- UI helpers -------------------------------------------------

    def _toolbar(self) -> str:
        n = len(self._engine._tables)
        timing = "on" if self._show_timing else "off"
        db = self._db_path or ":memory:"
        return f" usql | db: {db} | tables: {n} | timing: {timing} | \\q to quit "

    def _print_banner(self) -> None:
        db = self._db_path or ":memory:"
        print("usql -- UQA interactive SQL shell")
        print(f"Database: {db}")
        print("Type SQL statements terminated by ';'")
        print("Use \\dt, \\d <table>, \\ds <table>, \\timing, \\reset, \\q")
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
        "scripts",
        nargs="*",
        metavar="script.sql",
        help="SQL script files to execute before entering REPL",
    )
    args = parser.parse_args()

    shell = UQAShell(db_path=args.db)

    for path in args.scripts:
        try:
            shell.run_file(path)
        except FileNotFoundError:
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        shell.repl()
    finally:
        shell._engine.close()


if __name__ == "__main__":
    main()
