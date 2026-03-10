#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Foreign Data Wrapper metadata dataclasses.

A :class:`ForeignServer` represents a connection to an external data source
(e.g. a DuckDB in-process database or an Arrow Flight SQL endpoint).

A :class:`ForeignTable` describes a virtual table backed by a foreign server,
mapping SQL columns to data in the external source.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from uqa.sql.table import ColumnDef


@dataclass(frozen=True, slots=True)
class ForeignServer:
    """Connection metadata for an external data source.

    Attributes:
        name: Unique server name.
        fdw_type: Handler type -- ``"duckdb_fdw"`` or ``"arrow_fdw"``.
        options: Key-value connection options (database path, host, etc.).
    """

    name: str
    fdw_type: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ForeignTable:
    """Virtual table backed by a foreign server.

    Attributes:
        name: Table name visible in SQL.
        server_name: Name of the :class:`ForeignServer` providing data.
        columns: Ordered column definitions (reuses :class:`ColumnDef`).
        options: Handler-specific options (e.g. ``source`` for DuckDB).
    """

    name: str
    server_name: str
    columns: OrderedDict[str, ColumnDef] = field(default_factory=OrderedDict)
    options: dict[str, str] = field(default_factory=dict)
