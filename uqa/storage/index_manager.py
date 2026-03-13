#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Index manager: creates, drops, looks up, and restores indexes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.storage.btree_index import BTreeIndex
from uqa.storage.index_types import IndexDef, IndexType

if TYPE_CHECKING:
    from uqa.core.types import Predicate
    from uqa.storage.catalog import Catalog
    from uqa.storage.index_abc import Index
    from uqa.storage.managed_connection import SQLiteConnection


class IndexManager:
    """Manages all indexes across all tables."""

    def __init__(self, conn: SQLiteConnection, catalog: Catalog) -> None:
        self._conn = conn
        self._catalog = catalog
        self._indexes: dict[str, Index] = {}

    def create_index(self, index_def: IndexDef) -> Index:
        """Build a physical index and persist its definition."""
        if index_def.name in self._indexes:
            raise ValueError(f"Index '{index_def.name}' already exists")

        index = self._make_index(index_def)
        index.build()
        self._catalog.save_index(index_def)
        self._indexes[index_def.name] = index
        return index

    def drop_index(self, name: str) -> None:
        """Drop a physical index and remove from catalog."""
        index = self._indexes.get(name)
        if index is None:
            raise ValueError(f"Index '{name}' does not exist")
        index.drop()
        self._catalog.drop_index(name)
        del self._indexes[name]

    def drop_index_if_exists(self, name: str) -> None:
        """Drop an index if it exists, no-op otherwise."""
        if name in self._indexes:
            self.drop_index(name)

    def drop_indexes_for_table(self, table_name: str) -> None:
        """Drop all indexes belonging to a table (cascade on DROP TABLE)."""
        to_drop = [
            name
            for name, idx in self._indexes.items()
            if idx.index_def.table_name == table_name
        ]
        for name in to_drop:
            index = self._indexes[name]
            index.drop()
            del self._indexes[name]
        # Catalog rows are deleted by Catalog.drop_table_schema() cascade

    def find_covering_index(
        self, table_name: str, column: str, predicate: Predicate
    ) -> Index | None:
        """Find the cheapest index covering (table_name, column) for predicate."""
        best: Index | None = None
        best_cost = float("inf")
        for index in self._indexes.values():
            idef = index.index_def
            if idef.table_name != table_name:
                continue
            if idef.columns[0] != column:
                continue
            cost = index.scan_cost(predicate)
            if cost < best_cost:
                best = index
                best_cost = cost
        return best

    def get_indexes_for_table(self, table_name: str) -> list[Index]:
        """Return all indexes for a given table."""
        return [
            idx
            for idx in self._indexes.values()
            if idx.index_def.table_name == table_name
        ]

    def load_from_catalog(self) -> None:
        """Restore all indexes from the catalog on startup.

        The physical SQLite indexes already exist in the database file,
        so we only reconstruct the in-memory Index objects.
        HNSW and RTREE indexes are skipped here -- they are restored
        by the engine which has access to the Table objects.
        """
        for name, idx_type, tbl, cols, params in self._catalog.load_indexes():
            # HNSW and RTREE are managed by Engine/Table, not IndexManager.
            if idx_type in ("hnsw", "rtree"):
                continue
            index_def = IndexDef(
                name=name,
                index_type=IndexType(idx_type),
                table_name=tbl,
                columns=tuple(cols),
                parameters=params,
            )
            # The physical index already exists; just wrap it
            index = self._make_index(index_def)
            self._indexes[name] = index

    def has_index(self, name: str) -> bool:
        return name in self._indexes

    def _make_index(self, index_def: IndexDef) -> Index:
        """Create an Index instance from a definition."""
        if index_def.index_type == IndexType.BTREE:
            return BTreeIndex(index_def, self._conn)
        raise ValueError(f"Unsupported index type: {index_def.index_type.value}")
