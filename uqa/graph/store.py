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

    def add_vertex(self, vertex: Vertex) -> None:
        self._vertices[vertex.vertex_id] = vertex

    def add_edge(self, edge: Edge) -> None:
        self._edges[edge.edge_id] = edge
        self._adj_out[edge.source_id].append(edge.edge_id)
        self._adj_in[edge.target_id].append(edge.edge_id)
        self._label_index[edge.label].append(edge.edge_id)

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
