#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed graph store with per-graph adjacency indexes.

Inherits from :class:`GraphStore` and persists every mutation via
write-through.  Named graphs are tracked in a ``_graph_catalog`` table.

On construction all existing vertices, edges, and graph memberships are
loaded from SQLite into the inherited in-memory structures.
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
        When set, the store uses per-table SQLite tables.
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
            self._membership_table = f"_graph_membership_{table_name}"
            self._catalog_table = f"_graph_catalog_{table_name}"
        else:
            self._vtx_table = "_graph_vertices"
            self._edge_table = "_graph_edges"
            self._membership_table = "_graph_membership"
            self._catalog_table = "_graph_catalog"
        self._ensure_tables()
        self._load_from_sqlite()

    # -- Schema --------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create graph SQLite tables and indexes if needed."""
        vtx = self._vtx_table
        edg = self._edge_table
        mem = self._membership_table
        cat = self._catalog_table

        if self._table_name is None:
            self._migrate_vertex_label()

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
            f'CREATE TABLE IF NOT EXISTS "{mem}" ('
            f"entity_type TEXT NOT NULL, "  # 'vertex' or 'edge'
            f"entity_id INTEGER NOT NULL, "
            f"graph_name TEXT NOT NULL, "
            f"PRIMARY KEY (entity_type, entity_id, graph_name))"
        )
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{cat}" (graph_name TEXT PRIMARY KEY)'
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
        self._conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{mem}_graph" ON "{mem}" (graph_name)'
        )
        self._conn.commit()

    def _migrate_vertex_label(self) -> None:
        """Add the ``label`` column to an existing vertex table if missing."""
        vtx = self._vtx_table
        try:
            cols = {
                row[1]
                for row in self._conn.execute(f'PRAGMA table_info("{vtx}")').fetchall()
            }
        except Exception:
            return
        if cols and "label" not in cols:
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
        mem = self._membership_table
        cat = self._catalog_table

        # Load graph catalog
        try:
            for (name,) in self._conn.execute(
                f'SELECT graph_name FROM "{cat}"'
            ).fetchall():
                if not self.has_graph(name):
                    self._graphs[name] = __import__(
                        "uqa.graph.store", fromlist=["_GraphPartition"]
                    )._GraphPartition()
        except Exception:
            pass

        # Load vertices (global)
        try:
            cursor = self._conn.execute(
                f'SELECT vertex_id, label, properties_json FROM "{vtx}"'
            )
            for vid, label, props_json in cursor:
                vertex = Vertex(
                    vertex_id=vid, label=label, properties=json.loads(props_json)
                )
                self._vertices[vid] = vertex
                if vid >= self._next_vertex_id:
                    self._next_vertex_id = vid + 1
        except Exception:
            pass

        # Load edges (global)
        try:
            cursor = self._conn.execute(
                f"SELECT edge_id, source_id, target_id, label, properties_json "
                f'FROM "{edg}"'
            )
            for eid, src, tgt, label, props_json in cursor:
                edge = Edge(
                    edge_id=eid,
                    source_id=src,
                    target_id=tgt,
                    label=label,
                    properties=json.loads(props_json),
                )
                self._edges[eid] = edge
                if eid >= self._next_edge_id:
                    self._next_edge_id = eid + 1
        except Exception:
            pass

        # Load memberships and rebuild partitions
        try:
            cursor = self._conn.execute(
                f'SELECT entity_type, entity_id, graph_name FROM "{mem}"'
            )
            for entity_type, entity_id, graph_name in cursor:
                self._ensure_graph(graph_name)
                partition = self._graphs[graph_name]
                if entity_type == "vertex":
                    vertex = self._vertices.get(entity_id)
                    if vertex is not None:
                        partition.add_vertex(vertex)
                        self._vertex_membership[entity_id].add(graph_name)
                elif entity_type == "edge":
                    edge = self._edges.get(entity_id)
                    if edge is not None:
                        partition.add_edge(edge)
                        self._edge_membership[entity_id].add(graph_name)
        except Exception:
            pass

    def clear(self) -> None:
        """Remove all vertices, edges, and graphs from both memory and SQLite."""
        super().clear()
        self._conn.execute(f'DELETE FROM "{self._vtx_table}"')
        self._conn.execute(f'DELETE FROM "{self._edge_table}"')
        self._conn.execute(f'DELETE FROM "{self._membership_table}"')
        self._conn.execute(f'DELETE FROM "{self._catalog_table}"')
        self._conn.commit()

    # -- Graph lifecycle (write-through) --------------------------------

    def create_graph(self, name: str) -> None:
        super().create_graph(name)
        self._conn.execute(
            f'INSERT OR IGNORE INTO "{self._catalog_table}" (graph_name) VALUES (?)',
            (name,),
        )
        self._conn.commit()

    def drop_graph(self, name: str) -> None:
        super().drop_graph(name)
        self._conn.execute(
            f'DELETE FROM "{self._membership_table}" WHERE graph_name = ?',
            (name,),
        )
        self._conn.execute(
            f'DELETE FROM "{self._catalog_table}" WHERE graph_name = ?',
            (name,),
        )
        self._conn.commit()

    # -- Mutations (write-through) -------------------------------------

    def add_vertex(self, vertex: Vertex, *, graph: str) -> None:
        super().add_vertex(vertex, graph=graph)
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._vtx_table}" '
            f"(vertex_id, label, properties_json) VALUES (?, ?, ?)",
            (vertex.vertex_id, vertex.label, json.dumps(vertex.properties)),
        )
        self._conn.execute(
            f'INSERT OR IGNORE INTO "{self._membership_table}" '
            f"(entity_type, entity_id, graph_name) VALUES (?, ?, ?)",
            ("vertex", vertex.vertex_id, graph),
        )
        self._conn.commit()

    def remove_vertex(self, vertex_id: int, *, graph: str) -> None:
        super().remove_vertex(vertex_id, graph=graph)
        # Check if vertex is still in any graph
        if vertex_id not in self._vertex_membership:
            self._conn.execute(
                f'DELETE FROM "{self._vtx_table}" WHERE vertex_id = ?',
                (vertex_id,),
            )
        self._conn.execute(
            f'DELETE FROM "{self._membership_table}" '
            f"WHERE entity_type = 'vertex' AND entity_id = ? AND graph_name = ?",
            (vertex_id, graph),
        )
        # Remove orphaned edges from this graph
        self._conn.execute(
            f'DELETE FROM "{self._membership_table}" '
            f"WHERE entity_type = 'edge' AND graph_name = ? AND entity_id NOT IN "
            f'(SELECT edge_id FROM "{self._edge_table}")',
            (graph,),
        )
        self._conn.commit()

    def add_edge(self, edge: Edge, *, graph: str) -> None:
        super().add_edge(edge, graph=graph)
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
        self._conn.execute(
            f'INSERT OR IGNORE INTO "{self._membership_table}" '
            f"(entity_type, entity_id, graph_name) VALUES (?, ?, ?)",
            ("edge", edge.edge_id, graph),
        )
        self._conn.commit()

    def remove_edge(self, edge_id: int, *, graph: str) -> None:
        super().remove_edge(edge_id, graph=graph)
        if edge_id not in self._edge_membership:
            self._conn.execute(
                f'DELETE FROM "{self._edge_table}" WHERE edge_id = ?',
                (edge_id,),
            )
        self._conn.execute(
            f'DELETE FROM "{self._membership_table}" '
            f"WHERE entity_type = 'edge' AND entity_id = ? AND graph_name = ?",
            (edge_id, graph),
        )
        self._conn.commit()

    # -- SQLite-backed queries -----------------------------------------

    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
        *,
        graph: str,
    ) -> list[int]:
        """Query neighbors using graph-scoped partition (in-memory)."""
        return super().neighbors(vertex_id, label, direction, graph=graph)

    def vertices_by_label(self, label: str, *, graph: str) -> list[Vertex]:
        """Return all vertices with the given label in the specified graph."""
        return super().vertices_by_label(label, graph=graph)

    def edges_by_label(self, label: str, *, graph: str) -> list[Edge]:
        """Return all edges with the given label in the specified graph."""
        partition = self._get_partition(graph)
        eids = partition.label_index.get(label, set())
        return [self._edges[eid] for eid in eids if eid in self._edges]
