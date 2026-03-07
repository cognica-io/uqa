#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQLite-backed graph store with adjacency indexes.

Inherits from :class:`GraphStore` so that graph operators (which access
``_adj_out``, ``_edges``, ``_vertices`` directly) work unchanged.
Every mutation is persisted to the catalog's ``_graph_vertices`` and
``_graph_edges`` tables via write-through.

On construction all existing vertices and edges are loaded from SQLite
into the inherited in-memory dicts, making subsequent operator access
O(1).  The public :meth:`neighbors` method is overridden to query SQLite
directly, taking advantage of the adjacency indexes:

.. code-block:: sql

    CREATE INDEX _graph_edges_out   ON _graph_edges (source_id, label);
    CREATE INDEX _graph_edges_in    ON _graph_edges (target_id, label);
    CREATE INDEX _graph_edges_label ON _graph_edges (label);
"""

from __future__ import annotations

import json
import sqlite3

from uqa.core.types import Edge, Vertex
from uqa.graph.store import GraphStore


class SQLiteGraphStore(GraphStore):
    """GraphStore backed by SQLite with adjacency indexes."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn
        self._load_from_sqlite()

    # -- Loading -------------------------------------------------------

    def _load_from_sqlite(self) -> None:
        """Populate in-memory dicts from the catalog SQLite tables."""
        rows = self._conn.execute(
            "SELECT vertex_id, properties_json FROM _graph_vertices"
        ).fetchall()
        for vid, props_json in rows:
            vertex = Vertex(vertex_id=vid, properties=json.loads(props_json))
            super().add_vertex(vertex)

        rows = self._conn.execute(
            "SELECT edge_id, source_id, target_id, label, properties_json "
            "FROM _graph_edges"
        ).fetchall()
        for eid, src, tgt, label, props_json in rows:
            edge = Edge(
                edge_id=eid,
                source_id=src,
                target_id=tgt,
                label=label,
                properties=json.loads(props_json),
            )
            super().add_edge(edge)

    # -- Mutations (write-through) -------------------------------------

    def add_vertex(self, vertex: Vertex) -> None:
        super().add_vertex(vertex)
        self._conn.execute(
            "INSERT OR REPLACE INTO _graph_vertices "
            "(vertex_id, properties_json) VALUES (?, ?)",
            (vertex.vertex_id, json.dumps(vertex.properties)),
        )
        self._conn.commit()

    def add_edge(self, edge: Edge) -> None:
        super().add_edge(edge)
        self._conn.execute(
            "INSERT OR REPLACE INTO _graph_edges "
            "(edge_id, source_id, target_id, label, properties_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.label,
                json.dumps(edge.properties),
            ),
        )
        self._conn.commit()

    # -- SQLite-backed adjacency queries --------------------------------

    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
    ) -> list[int]:
        """Query neighbors using SQLite adjacency indexes.

        Falls back to the same semantics as :class:`GraphStore` but
        executes via SQL, leveraging the composite indexes on
        ``(source_id, label)`` and ``(target_id, label)``.
        """
        if direction == "out":
            if label is not None:
                rows = self._conn.execute(
                    "SELECT target_id FROM _graph_edges "
                    "WHERE source_id = ? AND label = ?",
                    (vertex_id, label),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT target_id FROM _graph_edges "
                    "WHERE source_id = ?",
                    (vertex_id,),
                ).fetchall()
        else:
            if label is not None:
                rows = self._conn.execute(
                    "SELECT source_id FROM _graph_edges "
                    "WHERE target_id = ? AND label = ?",
                    (vertex_id, label),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT source_id FROM _graph_edges "
                    "WHERE target_id = ?",
                    (vertex_id,),
                ).fetchall()
        return [r[0] for r in rows]

    def edges_by_label(self, label: str) -> list[Edge]:
        """Return all edges with the given label using the label index."""
        rows = self._conn.execute(
            "SELECT edge_id, source_id, target_id, label, properties_json "
            "FROM _graph_edges WHERE label = ?",
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
