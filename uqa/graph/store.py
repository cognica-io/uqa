#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict

from uqa.core.types import Edge, Vertex


class GraphStore:
    """Adjacency-list graph storage with property maps."""

    def __init__(self) -> None:
        self._vertices: dict[int, Vertex] = {}
        self._edges: dict[int, Edge] = {}
        self._adj_out: dict[int, list[int]] = defaultdict(list)
        self._adj_in: dict[int, list[int]] = defaultdict(list)
        self._label_index: dict[str, list[int]] = defaultdict(list)
        self._vertex_label_index: dict[str, list[int]] = defaultdict(list)
        self._next_vertex_id: int = 1
        self._next_edge_id: int = 1

    def add_vertex(self, vertex: Vertex) -> None:
        self._vertices[vertex.vertex_id] = vertex
        self._vertex_label_index[vertex.label].append(vertex.vertex_id)
        if vertex.vertex_id >= self._next_vertex_id:
            self._next_vertex_id = vertex.vertex_id + 1

    def remove_vertex(self, vertex_id: int) -> None:
        """Remove a vertex and all its incident edges."""
        vertex = self._vertices.pop(vertex_id, None)
        if vertex is None:
            return
        # Remove from vertex label index
        vids = self._vertex_label_index.get(vertex.label, [])
        if vertex_id in vids:
            vids.remove(vertex_id)

        # Remove all incident edges (both directions)
        out_eids = list(self._adj_out.pop(vertex_id, []))
        in_eids = list(self._adj_in.pop(vertex_id, []))
        for eid in out_eids:
            edge = self._edges.pop(eid, None)
            if edge is not None:
                self._adj_in.get(edge.target_id, []).remove(eid) if eid in self._adj_in.get(edge.target_id, []) else None
                lbl_list = self._label_index.get(edge.label, [])
                if eid in lbl_list:
                    lbl_list.remove(eid)
        for eid in in_eids:
            edge = self._edges.pop(eid, None)
            if edge is not None:
                adj = self._adj_out.get(edge.source_id, [])
                if eid in adj:
                    adj.remove(eid)
                lbl_list = self._label_index.get(edge.label, [])
                if eid in lbl_list:
                    lbl_list.remove(eid)

    def add_edge(self, edge: Edge) -> None:
        self._edges[edge.edge_id] = edge
        self._adj_out[edge.source_id].append(edge.edge_id)
        self._adj_in[edge.target_id].append(edge.edge_id)
        self._label_index[edge.label].append(edge.edge_id)
        if edge.edge_id >= self._next_edge_id:
            self._next_edge_id = edge.edge_id + 1

    def remove_edge(self, edge_id: int) -> None:
        """Remove a single edge by ID."""
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return
        adj_out = self._adj_out.get(edge.source_id, [])
        if edge_id in adj_out:
            adj_out.remove(edge_id)
        adj_in = self._adj_in.get(edge.target_id, [])
        if edge_id in adj_in:
            adj_in.remove(edge_id)
        lbl_list = self._label_index.get(edge.label, [])
        if edge_id in lbl_list:
            lbl_list.remove(edge_id)

    def next_vertex_id(self) -> int:
        """Return and advance the next available vertex ID."""
        vid = self._next_vertex_id
        self._next_vertex_id += 1
        return vid

    def next_edge_id(self) -> int:
        """Return and advance the next available edge ID."""
        eid = self._next_edge_id
        self._next_edge_id += 1
        return eid

    def vertices_by_label(self, label: str) -> list[Vertex]:
        """Return all vertices with the given label."""
        return [
            self._vertices[vid]
            for vid in self._vertex_label_index.get(label, [])
            if vid in self._vertices
        ]

    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
    ) -> list[int]:
        """Return neighbor vertex IDs reachable from vertex_id.

        Args:
            vertex_id: Source vertex.
            label: Edge label filter (None = any label).
            direction: "out" for outgoing, "in" for incoming.

        Returns:
            List of neighbor vertex IDs.
        """
        if direction == "out":
            edge_ids = self._adj_out.get(vertex_id, [])
        else:
            edge_ids = self._adj_in.get(vertex_id, [])

        result: list[int] = []
        for eid in edge_ids:
            edge = self._edges[eid]
            if label is not None and edge.label != label:
                continue
            if direction == "out":
                result.append(edge.target_id)
            else:
                result.append(edge.source_id)
        return result

    def clear(self) -> None:
        """Remove all vertices and edges."""
        self._vertices.clear()
        self._edges.clear()
        self._adj_out.clear()
        self._adj_in.clear()
        self._label_index.clear()
        self._vertex_label_index.clear()
        self._next_vertex_id = 1
        self._next_edge_id = 1

    def get_vertex(self, vertex_id: int) -> Vertex | None:
        return self._vertices.get(vertex_id)

    def get_edge(self, edge_id: int) -> Edge | None:
        return self._edges.get(edge_id)

    @property
    def vertices(self) -> dict[int, Vertex]:
        return dict(self._vertices)

    @property
    def edges(self) -> dict[int, Edge]:
        return dict(self._edges)
