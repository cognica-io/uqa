#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed graph store with adjacency indexes.

Inherits from :class:`GraphStore` so that graph operators (which access
``_adj_out``, ``_edges``, ``_vertices`` directly) work unchanged.
Every mutation is persisted via write-through.

When *table_name* is ``None`` the store uses the global catalog tables
(``_graph_vertices`` / ``_graph_edges``).  When a table name is given
the store uses per-table tables (``_graph_vertices_{name}`` /
``_graph_edges_{name}``), enabling each SQL table to maintain its own
graph independently.

On construction all existing vertices and edges are loaded from SQLite
into the inherited in-memory dicts, making subsequent operator access
O(1).  The public :meth:`neighbors` method is overridden to query SQLite
directly, taking advantage of the adjacency indexes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from uqa.core.types import Edge, Vertex

if TYPE_CHECKING:
    from uqa.storage.managed_connection import SQLiteConnection
from uqa.graph.store import GraphStore


class SQLiteGraphStore(GraphStore):
    """GraphStore backed by SQLite with adjacency indexes.

    Parameters
    ----------
    conn : sqlite3.Connection
        Shared SQLite connection (from catalog or managed connection).
    table_name : str | None
        When set, the store uses per-table SQLite tables
        (``_graph_vertices_{table_name}`` / ``_graph_edges_{table_name}``).
        When ``None`` (default), the global catalog tables are used.
    """

    def __init__(
        self,
        conn: SQLiteConnection,
        table_name: str | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn
        self._table_name = table_name
        if table_name is not None:
            self._vtx_table = f"_graph_vertices_{table_name}"
            self._edge_table = f"_graph_edges_{table_name}"
        else:
            self._vtx_table = "_graph_vertices"
            self._edge_table = "_graph_edges"
        self._ensure_tables()
        self._load_from_sqlite()

    # -- Schema --------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create per-table graph SQLite tables and indexes if needed."""
        if self._table_name is None:
            # Global tables are created by Catalog._SCHEMA_SQL.
            self._migrate_vertex_label()
            return
        vtx = self._vtx_table
        edg = self._edge_table
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{vtx}" ('
            f"vertex_id INTEGER PRIMARY KEY, "
            f"label TEXT NOT NULL DEFAULT '', "
            f"properties_json TEXT NOT NULL)"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{edg}" ('
            f"edge_id INTEGER PRIMARY KEY, "
            f"source_id INTEGER NOT NULL, "
            f"target_id INTEGER NOT NULL, "
            f"label TEXT NOT NULL, "
            f"properties_json TEXT NOT NULL)"
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{vtx}_label" ON "{vtx}" (label)'
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{edg}_out" ON "{edg}" (source_id, label)'
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{edg}_in" ON "{edg}" (target_id, label)'
        )
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{edg}_label" ON "{edg}" (label)'
        )
        self._conn.commit()

    def _migrate_vertex_label(self) -> None:
        """Add the ``label`` column to an existing vertex table if missing."""
        vtx = self._vtx_table
        cols = {
            row[1]
            for row in self._conn.execute(f'PRAGMA table_info("{vtx}")').fetchall()
        }
        if "label" not in cols:
            self._conn.execute(
                f"ALTER TABLE \"{vtx}\" ADD COLUMN label TEXT NOT NULL DEFAULT ''"
            )
            self._conn.execute(
                f'CREATE INDEX IF NOT EXISTS "{vtx}_label" ON "{vtx}" (label)'
            )
            self._conn.commit()

    # -- Loading -------------------------------------------------------

    def _load_from_sqlite(self) -> None:
        """Populate in-memory dicts from SQLite tables."""
        vtx = self._vtx_table
        edg = self._edge_table

        cursor = self._conn.execute(
            f'SELECT vertex_id, label, properties_json FROM "{vtx}"'
        )
        for vid, label, props_json in cursor:
            vertex = Vertex(
                vertex_id=vid, label=label, properties=json.loads(props_json)
            )
            super().add_vertex(vertex)

        cursor = self._conn.execute(
            f'SELECT edge_id, source_id, target_id, label, properties_json FROM "{edg}"'
        )
        for eid, src, tgt, label, props_json in cursor:
            edge = Edge(
                edge_id=eid,
                source_id=src,
                target_id=tgt,
                label=label,
                properties=json.loads(props_json),
            )
            super().add_edge(edge)

    def clear(self) -> None:
        """Remove all vertices and edges from both memory and SQLite."""
        super().clear()
        self._conn.execute(f'DELETE FROM "{self._vtx_table}"')
        self._conn.execute(f'DELETE FROM "{self._edge_table}"')
        self._conn.commit()

    # -- Mutations (write-through) -------------------------------------

    def add_vertex(self, vertex: Vertex) -> None:
        super().add_vertex(vertex)
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._vtx_table}" '
            f"(vertex_id, label, properties_json) VALUES (?, ?, ?)",
            (vertex.vertex_id, vertex.label, json.dumps(vertex.properties)),
        )
        self._conn.commit()

    def remove_vertex(self, vertex_id: int) -> None:
        super().remove_vertex(vertex_id)
        self._conn.execute(
            f'DELETE FROM "{self._edge_table}" WHERE source_id = ? OR target_id = ?',
            (vertex_id, vertex_id),
        )
        self._conn.execute(
            f'DELETE FROM "{self._vtx_table}" WHERE vertex_id = ?',
            (vertex_id,),
        )
        self._conn.commit()

    def add_edge(self, edge: Edge) -> None:
        super().add_edge(edge)
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._edge_table}" '
            f"(edge_id, source_id, target_id, label, properties_json) "
            f"VALUES (?, ?, ?, ?, ?)",
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.label,
                json.dumps(edge.properties),
            ),
        )
        self._conn.commit()

    def remove_edge(self, edge_id: int) -> None:
        super().remove_edge(edge_id)
        self._conn.execute(
            f'DELETE FROM "{self._edge_table}" WHERE edge_id = ?',
            (edge_id,),
        )
        self._conn.commit()

    # -- SQLite-backed adjacency queries --------------------------------

    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
    ) -> list[int]:
        """Query neighbors using SQLite adjacency indexes."""
        edg = self._edge_table
        if direction == "out":
            if label is not None:
                rows = self._conn.execute(
                    f'SELECT target_id FROM "{edg}" WHERE source_id = ? AND label = ?',
                    (vertex_id, label),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    f'SELECT target_id FROM "{edg}" WHERE source_id = ?',
                    (vertex_id,),
                ).fetchall()
        else:
            if label is not None:
                rows = self._conn.execute(
                    f'SELECT source_id FROM "{edg}" WHERE target_id = ? AND label = ?',
                    (vertex_id, label),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    f'SELECT source_id FROM "{edg}" WHERE target_id = ?',
                    (vertex_id,),
                ).fetchall()
        return [r[0] for r in rows]

    def vertices_by_label(self, label: str) -> list[Vertex]:
        """Return all vertices with the given label using the label index."""
        vtx = self._vtx_table
        rows = self._conn.execute(
            f'SELECT vertex_id, label, properties_json FROM "{vtx}" WHERE label = ?',
            (label,),
        ).fetchall()
        return [
            Vertex(
                vertex_id=vid,
                label=lbl,
                properties=json.loads(props_json),
            )
            for vid, lbl, props_json in rows
        ]

    def edges_by_label(self, label: str) -> list[Edge]:
        """Return all edges with the given label using the label index."""
        edg = self._edge_table
        rows = self._conn.execute(
            f"SELECT edge_id, source_id, target_id, label, properties_json "
            f'FROM "{edg}" WHERE label = ?',
            (label,),
        ).fetchall()
        return [
            Edge(
                edge_id=eid,
                source_id=src,
                target_id=tgt,
                label=lbl,
                properties=json.loads(props_json),
            )
            for eid, src, tgt, lbl, props_json in rows
        ]
