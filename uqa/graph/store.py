#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import Edge, Vertex

_EMPTY_SET: set[int] = frozenset()  # type: ignore[assignment]


@dataclass
class _GraphPartition:
    """Per-named-graph adjacency state. No global duplicates."""

    vertex_ids: set[int] = field(default_factory=set)
    edge_ids: set[int] = field(default_factory=set)
    adj_out: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    adj_in: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    label_index: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))
    vertex_label_index: dict[str, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )

    def add_vertex(self, vertex: Vertex) -> None:
        self.vertex_ids.add(vertex.vertex_id)
        self.vertex_label_index[vertex.label].add(vertex.vertex_id)

    def remove_vertex(self, vertex_id: int, edges: dict[int, Edge]) -> None:
        self.vertex_ids.discard(vertex_id)
        # Remove from vertex label index
        for _label, vids in list(self.vertex_label_index.items()):
            vids.discard(vertex_id)

        # Remove all incident edges
        out_eids = list(self.adj_out.pop(vertex_id, set()))
        in_eids = list(self.adj_in.pop(vertex_id, set()))
        for eid in out_eids:
            self.edge_ids.discard(eid)
            edge = edges.get(eid)
            if edge is not None:
                adj_in = self.adj_in.get(edge.target_id)
                if adj_in is not None:
                    adj_in.discard(eid)
                lbl_set = self.label_index.get(edge.label)
                if lbl_set is not None:
                    lbl_set.discard(eid)
        for eid in in_eids:
            self.edge_ids.discard(eid)
            edge = edges.get(eid)
            if edge is not None:
                adj = self.adj_out.get(edge.source_id)
                if adj is not None:
                    adj.discard(eid)
                lbl_set = self.label_index.get(edge.label)
                if lbl_set is not None:
                    lbl_set.discard(eid)

    def add_edge(self, edge: Edge) -> None:
        self.edge_ids.add(edge.edge_id)
        self.adj_out[edge.source_id].add(edge.edge_id)
        self.adj_in[edge.target_id].add(edge.edge_id)
        self.label_index[edge.label].add(edge.edge_id)

    def remove_edge(self, edge_id: int, edge: Edge) -> None:
        self.edge_ids.discard(edge_id)
        adj_out = self.adj_out.get(edge.source_id)
        if adj_out is not None:
            adj_out.discard(edge_id)
        adj_in = self.adj_in.get(edge.target_id)
        if adj_in is not None:
            adj_in.discard(edge_id)
        lbl_set = self.label_index.get(edge.label)
        if lbl_set is not None:
            lbl_set.discard(edge_id)

    def neighbors(
        self,
        vertex_id: int,
        label: str | None,
        direction: str,
        edges: dict[int, Edge],
    ) -> list[int]:
        if direction == "out":
            edge_ids = self.adj_out.get(vertex_id, set())
        else:
            edge_ids = self.adj_in.get(vertex_id, set())

        result: list[int] = []
        for eid in edge_ids:
            edge = edges[eid]
            if label is not None and edge.label != label:
                continue
            if direction == "out":
                result.append(edge.target_id)
            else:
                result.append(edge.source_id)
        return result

    def vertices_by_label(
        self, label: str, vertices: dict[int, Vertex]
    ) -> list[Vertex]:
        return [
            vertices[vid]
            for vid in self.vertex_label_index.get(label, set())
            if vid in vertices
        ]


class GraphStore:
    """Named-graph-native graph storage. All operations are graph-scoped.

    Vertices/edges are stored globally (shared across named graphs).
    Adjacency indexes are per-graph -- no global indexes, zero duplication
    overhead.
    """

    def __init__(self) -> None:
        self._vertices: dict[int, Vertex] = {}
        self._edges: dict[int, Edge] = {}
        self._graphs: dict[str, _GraphPartition] = {}
        self._vertex_membership: dict[int, set[str]] = defaultdict(set)
        self._edge_membership: dict[int, set[str]] = defaultdict(set)
        self._next_vertex_id: int = 1
        self._next_edge_id: int = 1

    # --- Graph lifecycle ---

    def create_graph(self, name: str) -> None:
        if name in self._graphs:
            raise ValueError(f"Graph '{name}' already exists")
        self._graphs[name] = _GraphPartition()

    def drop_graph(self, name: str) -> None:
        partition = self._graphs.pop(name, None)
        if partition is None:
            raise ValueError(f"Graph '{name}' does not exist")
        # Remove membership records
        for vid in partition.vertex_ids:
            membership = self._vertex_membership.get(vid)
            if membership is not None:
                membership.discard(name)
                if not membership:
                    self._vertices.pop(vid, None)
                    self._vertex_membership.pop(vid, None)
        for eid in partition.edge_ids:
            membership = self._edge_membership.get(eid)
            if membership is not None:
                membership.discard(name)
                if not membership:
                    self._edges.pop(eid, None)
                    self._edge_membership.pop(eid, None)

    def graph_names(self) -> list[str]:
        return sorted(self._graphs.keys())

    def has_graph(self, name: str) -> bool:
        return name in self._graphs

    # --- Graph-level algebra ---

    def union_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as union of g1 and g2."""
        p1 = self._require_graph(g1)
        p2 = self._require_graph(g2)
        self._ensure_graph(target)
        tp = self._graphs[target]
        for vid in p1.vertex_ids | p2.vertex_ids:
            vertex = self._vertices.get(vid)
            if vertex is not None and vid not in tp.vertex_ids:
                tp.add_vertex(vertex)
                self._vertex_membership[vid].add(target)
        for eid in p1.edge_ids | p2.edge_ids:
            edge = self._edges.get(eid)
            if edge is not None and eid not in tp.edge_ids:
                tp.add_edge(edge)
                self._edge_membership[eid].add(target)

    def intersect_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as intersection of g1 and g2."""
        p1 = self._require_graph(g1)
        p2 = self._require_graph(g2)
        self._ensure_graph(target)
        tp = self._graphs[target]
        for vid in p1.vertex_ids & p2.vertex_ids:
            vertex = self._vertices.get(vid)
            if vertex is not None and vid not in tp.vertex_ids:
                tp.add_vertex(vertex)
                self._vertex_membership[vid].add(target)
        for eid in p1.edge_ids & p2.edge_ids:
            edge = self._edges.get(eid)
            if edge is not None and eid not in tp.edge_ids:
                tp.add_edge(edge)
                self._edge_membership[eid].add(target)

    def difference_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as g1 - g2."""
        p1 = self._require_graph(g1)
        p2 = self._require_graph(g2)
        self._ensure_graph(target)
        tp = self._graphs[target]
        for vid in p1.vertex_ids - p2.vertex_ids:
            vertex = self._vertices.get(vid)
            if vertex is not None and vid not in tp.vertex_ids:
                tp.add_vertex(vertex)
                self._vertex_membership[vid].add(target)
        for eid in p1.edge_ids - p2.edge_ids:
            edge = self._edges.get(eid)
            if edge is not None and eid not in tp.edge_ids:
                tp.add_edge(edge)
                self._edge_membership[eid].add(target)

    def copy_graph(self, source: str, target: str) -> None:
        """Copy source graph to target graph."""
        sp = self._require_graph(source)
        self._ensure_graph(target)
        tp = self._graphs[target]
        for vid in sp.vertex_ids:
            vertex = self._vertices.get(vid)
            if vertex is not None and vid not in tp.vertex_ids:
                tp.add_vertex(vertex)
                self._vertex_membership[vid].add(target)
        for eid in sp.edge_ids:
            edge = self._edges.get(eid)
            if edge is not None and eid not in tp.edge_ids:
                tp.add_edge(edge)
                self._edge_membership[eid].add(target)

    # --- Mutations (graph is REQUIRED, no default) ---

    def add_vertex(self, vertex: Vertex, *, graph: str) -> None:
        vid = vertex.vertex_id
        self._vertices[vid] = vertex
        partition = self._graphs.get(graph)
        if partition is None:
            partition = _GraphPartition()
            self._graphs[graph] = partition
        partition.vertex_ids.add(vid)
        partition.vertex_label_index[vertex.label].add(vid)
        self._vertex_membership[vid].add(graph)
        if vid >= self._next_vertex_id:
            self._next_vertex_id = vid + 1

    def add_edge(self, edge: Edge, *, graph: str) -> None:
        eid = edge.edge_id
        self._edges[eid] = edge
        partition = self._graphs.get(graph)
        if partition is None:
            partition = _GraphPartition()
            self._graphs[graph] = partition
        partition.edge_ids.add(eid)
        partition.adj_out[edge.source_id].add(eid)
        partition.adj_in[edge.target_id].add(eid)
        partition.label_index[edge.label].add(eid)
        self._edge_membership[eid].add(graph)
        if eid >= self._next_edge_id:
            self._next_edge_id = eid + 1

    def remove_vertex(self, vertex_id: int, *, graph: str) -> None:
        partition = self._require_graph(graph)
        if vertex_id not in partition.vertex_ids:
            return
        partition.remove_vertex(vertex_id, self._edges)
        membership = self._vertex_membership.get(vertex_id)
        if membership is not None:
            membership.discard(graph)
            if not membership:
                self._vertices.pop(vertex_id, None)
                self._vertex_membership.pop(vertex_id, None)

    def remove_edge(self, edge_id: int, *, graph: str) -> None:
        partition = self._require_graph(graph)
        edge = self._edges.get(edge_id)
        if edge is None or edge_id not in partition.edge_ids:
            return
        partition.remove_edge(edge_id, edge)
        membership = self._edge_membership.get(edge_id)
        if membership is not None:
            membership.discard(graph)
            if not membership:
                self._edges.pop(edge_id, None)
                self._edge_membership.pop(edge_id, None)

    # --- Queries (graph is REQUIRED) ---

    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
        *,
        graph: str,
    ) -> list[int]:
        partition = self._graphs.get(graph)
        if partition is None:
            raise ValueError(f"Graph '{graph}' does not exist")
        if direction == "out":
            edge_ids = partition.adj_out.get(vertex_id, _EMPTY_SET)
        else:
            edge_ids = partition.adj_in.get(vertex_id, _EMPTY_SET)
        edges = self._edges
        result: list[int] = []
        for eid in edge_ids:
            edge = edges[eid]
            if label is not None and edge.label != label:
                continue
            result.append(edge.target_id if direction == "out" else edge.source_id)
        return result

    def vertices_by_label(self, label: str, *, graph: str) -> list[Vertex]:
        return self._require_graph(graph).vertices_by_label(label, self._vertices)

    def vertices_in_graph(self, graph: str) -> list[Vertex]:
        partition = self._require_graph(graph)
        return [
            self._vertices[vid]
            for vid in sorted(partition.vertex_ids)
            if vid in self._vertices
        ]

    def edges_in_graph(self, graph: str) -> list[Edge]:
        partition = self._require_graph(graph)
        return [
            self._edges[eid] for eid in sorted(partition.edge_ids) if eid in self._edges
        ]

    def vertex_graphs(self, vertex_id: int) -> set[str]:
        return set(self._vertex_membership.get(vertex_id, set()))

    # --- Graph-scoped adjacency accessors (for operators) ---

    def out_edge_ids(self, vertex_id: int, *, graph: str) -> set[int]:
        """Return outgoing edge IDs for vertex in a specific graph."""
        partition = self._graphs.get(graph)
        if partition is None:
            raise ValueError(f"Graph '{graph}' does not exist")
        return partition.adj_out.get(vertex_id, _EMPTY_SET)

    def in_edge_ids(self, vertex_id: int, *, graph: str) -> set[int]:
        """Return incoming edge IDs for vertex in a specific graph."""
        partition = self._graphs.get(graph)
        if partition is None:
            raise ValueError(f"Graph '{graph}' does not exist")
        return partition.adj_in.get(vertex_id, _EMPTY_SET)

    def edge_ids_by_label(self, label: str, *, graph: str) -> set[int]:
        """Return edge IDs with a given label in a specific graph."""
        partition = self._graphs.get(graph)
        if partition is None:
            raise ValueError(f"Graph '{graph}' does not exist")
        return partition.label_index.get(label, _EMPTY_SET)

    def vertex_ids_in_graph(self, graph: str) -> set[int]:
        """Return all vertex IDs in a specific graph."""
        partition = self._graphs.get(graph)
        if partition is None:
            raise ValueError(f"Graph '{graph}' does not exist")
        return partition.vertex_ids

    # --- Statistics (per-graph) ---

    def degree_distribution(self, graph: str) -> dict[int, int]:
        """Out-degree distribution for vertices in graph."""
        partition = self._require_graph(graph)
        dist: dict[int, int] = defaultdict(int)
        for vid in partition.vertex_ids:
            degree = len(partition.adj_out.get(vid, set()))
            dist[degree] += 1
        return dict(dist)

    def label_degree(self, label: str, graph: str) -> float:
        """Average out-degree for edges with given label in graph."""
        partition = self._require_graph(graph)
        eids = partition.label_index.get(label, set())
        if not eids:
            return 0.0
        source_ids: set[int] = set()
        for eid in eids:
            edge = self._edges.get(eid)
            if edge is not None:
                source_ids.add(edge.source_id)
        if not source_ids:
            return 0.0
        return len(eids) / len(source_ids)

    def vertex_label_counts(self, graph: str) -> dict[str, int]:
        """Count of vertices per vertex label in graph."""
        partition = self._require_graph(graph)
        return {
            label: len(vids & partition.vertex_ids)
            for label, vids in partition.vertex_label_index.items()
            if vids & partition.vertex_ids
        }

    # --- Global accessors (read-only, for cross-graph operations) ---

    def get_vertex(self, vertex_id: int) -> Vertex | None:
        return self._vertices.get(vertex_id)

    def get_edge(self, edge_id: int) -> Edge | None:
        return self._edges.get(edge_id)

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

    def clear(self) -> None:
        """Remove all vertices, edges, and graphs."""
        self._vertices.clear()
        self._edges.clear()
        self._graphs.clear()
        self._vertex_membership.clear()
        self._edge_membership.clear()
        self._next_vertex_id = 1
        self._next_edge_id = 1

    @property
    def vertices(self) -> dict[int, Vertex]:
        return dict(self._vertices)

    @property
    def edges(self) -> dict[int, Edge]:
        return dict(self._edges)

    # --- Internal helpers ---

    def _ensure_graph(self, name: str) -> None:
        """Create graph if it does not exist."""
        if name not in self._graphs:
            self._graphs[name] = _GraphPartition()

    def _require_graph(self, name: str) -> _GraphPartition:
        """Return partition, raising if graph does not exist."""
        p = self._graphs.get(name)
        if p is None:
            raise ValueError(f"Graph '{name}' does not exist")
        return p
