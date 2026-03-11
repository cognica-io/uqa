#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for Foreign Data Wrapper handlers.

Each handler knows how to connect to a specific kind of external data
source and return query results as a ``pyarrow.Table``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

    from uqa.fdw.foreign_table import FDWPredicate, ForeignTable


class FDWHandler(ABC):
    """Interface for scanning external data sources.

    Implementations must provide :meth:`scan` (fetch data) and
    :meth:`close` (release resources).
    """

    @abstractmethod
    def scan(
        self,
        foreign_table: ForeignTable,
        columns: list[str] | None = None,
        predicates: list[FDWPredicate] | None = None,
    ) -> pa.Table:
        """Scan the foreign table and return an Arrow table.

        Parameters:
            foreign_table: The foreign table metadata.
            columns: Optional column projection (all columns if None).
            predicates: Pushdown predicates for server-side filtering.
                Each :class:`FDWPredicate` carries a column name, a
                comparison operator, and a literal value.  Handlers
                translate these into native filter expressions (e.g.
                SQL WHERE clauses) so the data source can prune data
                before transmission -- critical for Hive partition
                pruning and remote query efficiency.

        Returns:
            A ``pyarrow.Table`` containing the requested data.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by this handler."""
