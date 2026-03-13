#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph indexing structures for accelerating traversal and pattern matching.

Section 6.4, Paper 2: Specialized indexes for graph query processing.

- LabelIndex: maps edge labels to edge IDs for fast label-filtered traversal
- NeighborhoodIndex: caches k-hop neighborhoods per vertex for repeated lookups
- PathIndex: indexes (start, label_sequence, end) triples for RPQ acceleration
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.graph.store import GraphStore


class LabelIndex:
    """Maps edge labels to sorted edge IDs.

    Provides O(1) lookup for "all edges with label L" instead of
    scanning all edges.  The GraphStore already has ``_label_index``;
    this class wraps it with richer query support (multi-label lookup,
    label cardinality).
    """

    def __init__(self) -> None:
        self._label_to_edges: dict[str, list[int]] = defaultdict(list)
        self._label_to_vertices: dict[str, set[int]] = defaultdict(set)

    @classmethod
    def build(cls, graph: GraphStore) -> LabelIndex:
        idx = cls()
        for eid, edge in graph._edges.items():
            idx._label_to_edges[edge.label].append(eid)
            idx._label_to_vertices[edge.label].add(edge.source_id)
            idx._label_to_vertices[edge.label].add(edge.target_id)
        for label in idx._label_to_edges:
            idx._label_to_edges[label].sort()
        return idx

    def edges_by_label(self, label: str) -> list[int]:
        return self._label_to_edges.get(label, [])

    def vertices_by_label(self, label: str) -> set[int]:
        return self._label_to_vertices.get(label, set())

    def labels(self) -> list[str]:
        return sorted(self._label_to_edges.keys())

    def label_count(self, label: str) -> int:
        return len(self._label_to_edges.get(label, []))


class NeighborhoodIndex:
    """Caches k-hop neighborhoods per vertex for repeated traversal lookups.

    After building, ``neighbors(v, k)`` returns the set of vertices
    reachable from v within k hops in O(1) time.
    """

    def __init__(self, max_hops: int = 2) -> None:
        self.max_hops = max_hops
        self._cache: dict[int, dict[int, set[int]]] = {}

    @classmethod
    def build(
        cls,
        graph: GraphStore,
        max_hops: int = 2,
        label: str | None = None,
    ) -> NeighborhoodIndex:
        idx = cls(max_hops=max_hops)
        for vid in graph._vertices:
            idx._cache[vid] = {}
            visited: set[int] = {vid}
            frontier: set[int] = {vid}
            for hop in range(1, max_hops + 1):
                next_frontier: set[int] = set()
                for v in frontier:
                    for eid in graph._adj_out.get(v, []):
                        edge = graph._edges[eid]
                        if label is not None and edge.label != label:
                            continue
                        if edge.target_id not in visited:
                            next_frontier.add(edge.target_id)
                visited.update(next_frontier)
                frontier = next_frontier
                idx._cache[vid][hop] = set(visited)
        return idx

    def neighbors(self, vertex_id: int, hops: int) -> set[int]:
        vertex_cache = self._cache.get(vertex_id)
        if vertex_cache is None:
            return set()
        clamped = min(hops, self.max_hops)
        return vertex_cache.get(clamped, set())

    def has_vertex(self, vertex_id: int) -> bool:
        return vertex_id in self._cache


class PathIndex:
    """Indexes reachable (start, end) pairs for specific label sequences.

    Pre-computes which vertex pairs are connected by a given label path
    (e.g., "knows/works_with") so that RPQ evaluation can skip NFA
    simulation for indexed paths.
    """

    def __init__(self) -> None:
        self._path_pairs: dict[str, set[tuple[int, int]]] = {}

    @classmethod
    def build(
        cls,
        graph: GraphStore,
        label_sequences: list[list[str]],
    ) -> PathIndex:
        idx = cls()
        for seq in label_sequences:
            path_key = "/".join(seq)
            pairs: set[tuple[int, int]] = set()
            for start_vid in graph._vertices:
                ends = cls._follow_path(graph, start_vid, seq)
                for end_vid in ends:
                    pairs.add((start_vid, end_vid))
            idx._path_pairs[path_key] = pairs
        return idx

    @staticmethod
    def _follow_path(graph: GraphStore, start: int, labels: list[str]) -> set[int]:
        current: set[int] = {start}
        for label in labels:
            next_set: set[int] = set()
            for vid in current:
                for eid in graph._adj_out.get(vid, []):
                    edge = graph._edges[eid]
                    if edge.label == label:
                        next_set.add(edge.target_id)
            current = next_set
            if not current:
                break
        return current

    def lookup(self, label_sequence: list[str]) -> set[tuple[int, int]] | None:
        path_key = "/".join(label_sequence)
        return self._path_pairs.get(path_key)

    def has_path(self, label_sequence: list[str]) -> bool:
        path_key = "/".join(label_sequence)
        return path_key in self._path_pairs

    def indexed_paths(self) -> list[str]:
        return sorted(self._path_pairs.keys())
