#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""DuckDB Foreign Data Wrapper handler.

Provides in-process access to Parquet files, CSV files, S3 objects,
attached databases, and any other source DuckDB can query.

Server options:
    database   -- Path to a DuckDB database file (default: ``:memory:``).
    extensions -- Comma-separated list of extensions to install/load.
    s3_region, s3_access_key_id, s3_secret_access_key -- S3 credentials.

Foreign table options:
    source -- A DuckDB expression such as ``read_parquet('...')``,
              ``read_csv('...')``, or an attached table name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from uqa.fdw.handler import FDWHandler

if TYPE_CHECKING:
    import pyarrow as pa

    from uqa.fdw.foreign_table import ForeignServer, ForeignTable


class DuckDBFDWHandler(FDWHandler):
    """In-process DuckDB handler for local and remote file queries."""

    def __init__(self, server: ForeignServer) -> None:
        database = server.options.get("database", ":memory:")
        self._conn = duckdb.connect(database, read_only=False)

        # Load requested extensions
        extensions = server.options.get("extensions", "")
        for ext in extensions.split(","):
            ext = ext.strip()
            if ext:
                self._conn.install_extension(ext)
                self._conn.load_extension(ext)

        # Configure S3 credentials if provided
        for key in ("s3_region", "s3_access_key_id", "s3_secret_access_key"):
            value = server.options.get(key)
            if value:
                self._conn.execute(f"SET {key} = '{value}'")

    # File extensions that DuckDB can read directly via read_* functions.
    _FILE_READERS: dict[str, str] = {
        ".parquet": "read_parquet",
        ".csv": "read_csv",
        ".json": "read_json",
        ".ndjson": "read_json",
    }

    @classmethod
    def _normalize_source(cls, source: str) -> str:
        """Wrap bare file paths in the appropriate DuckDB reader function.

        If *source* already contains a function call (detected by ``(``)
        or is a plain identifier (table name), it is returned as-is.
        Otherwise, if it ends with a known file extension, it is wrapped
        in the corresponding ``read_*()`` call.
        """
        if "(" in source:
            return source
        lower = source.lower()
        for ext, reader in cls._FILE_READERS.items():
            if lower.endswith(ext):
                return f"{reader}('{source}')"
        return source

    def scan(
        self,
        foreign_table: ForeignTable,
        columns: list[str] | None = None,
        predicates: list | None = None,
    ) -> pa.Table:
        source = foreign_table.options.get("source")
        if source is None:
            raise ValueError(
                f"Foreign table '{foreign_table.name}' "
                f"missing required option 'source'"
            )

        source = self._normalize_source(source)

        if columns:
            cols = ", ".join(columns)
        else:
            cols = ", ".join(foreign_table.columns.keys())

        sql = f"SELECT {cols} FROM {source}"
        return self._conn.execute(sql).fetch_arrow_table()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
