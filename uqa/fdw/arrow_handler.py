#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Arrow Flight SQL Foreign Data Wrapper handler.

Connects to remote Arrow Flight SQL services (Dremio, DataFusion,
Apache Arrow Flight SQL servers, etc.) using ``pyarrow.flight``.

Server options:
    host     -- Hostname of the Flight SQL server.
    port     -- Port number (default: ``8815``).
    tls      -- ``"true"`` to enable TLS (default: ``"false"``).
    username -- Optional authentication username.
    password -- Optional authentication password.

Foreign table options:
    source -- Table name on the remote server.
    query  -- Full SQL query to execute on the remote server
              (takes precedence over ``source`` if both are set).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.fdw.handler import FDWHandler

if TYPE_CHECKING:
    import pyarrow as pa

    from uqa.fdw.foreign_table import ForeignServer, ForeignTable


class ArrowFlightSQLFDWHandler(FDWHandler):
    """Arrow Flight SQL client handler for remote Arrow services."""

    def __init__(self, server: ForeignServer) -> None:
        import pyarrow.flight as flight

        host = server.options.get("host", "localhost")
        port = int(server.options.get("port", "8815"))
        use_tls = server.options.get("tls", "false").lower() == "true"

        scheme = "grpc+tls" if use_tls else "grpc"
        location = f"{scheme}://{host}:{port}"
        self._client = flight.FlightClient(location)

        # Authenticate if credentials are provided
        username = server.options.get("username")
        password = server.options.get("password")
        if username and password:
            self._client.authenticate_basic_token(username, password)

    def scan(
        self,
        foreign_table: ForeignTable,
        columns: list[str] | None = None,
        predicates: list | None = None,
    ) -> pa.Table:
        import pyarrow.flight as flight

        # Prefer explicit query over table name
        query = foreign_table.options.get("query")
        if query is None:
            source = foreign_table.options.get("source")
            if source is None:
                raise ValueError(
                    f"Foreign table '{foreign_table.name}' "
                    f"missing required option 'source' or 'query'"
                )
            if columns:
                cols = ", ".join(columns)
            else:
                cols = ", ".join(foreign_table.columns.keys())
            query = f"SELECT {cols} FROM {source}"

        descriptor = flight.FlightDescriptor.for_command(query.encode("utf-8"))
        info = self._client.get_flight_info(descriptor)

        # Read all endpoints and concatenate
        tables = []
        for endpoint in info.endpoints:
            reader = self._client.do_get(endpoint.ticket)
            tables.append(reader.read_all())

        if not tables:
            import pyarrow as pa

            return pa.table({
                col: [] for col in foreign_table.columns
            })

        import pyarrow as pa

        return pa.concat_tables(tables)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
