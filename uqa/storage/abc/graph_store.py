#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for graph stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import Edge, Vertex


class GraphStore(ABC):
    """Abstract interface for graph storage backends.

    A graph store manages named graphs with vertices and edges, supporting
    graph lifecycle, mutations, queries, adjacency access, and statistics.
    Concrete implementations include in-memory and SQLite-backed stores.
    """

    # --- Graph lifecycle ---

    @abstractmethod
    def create_graph(self, name: str) -> None:
        """Create a new named graph."""

    @abstractmethod
    def drop_graph(self, name: str) -> None:
        """Drop a named graph and its data."""

    @abstractmethod
    def graph_names(self) -> list[str]:
        """Return sorted list of graph names."""

    @abstractmethod
    def has_graph(self, name: str) -> bool:
        """Return True if graph exists."""

    # --- Graph algebra ---

    @abstractmethod
    def union_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as union of g1 and g2."""

    @abstractmethod
    def intersect_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as intersection of g1 and g2."""

    @abstractmethod
    def difference_graphs(self, g1: str, g2: str, target: str) -> None:
        """Create target graph as g1 - g2."""

    @abstractmethod
    def copy_graph(self, source: str, target: str) -> None:
        """Copy source graph to target graph."""

    # --- Mutations ---

    @abstractmethod
    def add_vertex(self, vertex: Vertex, *, graph: str) -> None:
        """Add a vertex to a named graph."""

    @abstractmethod
    def add_edge(self, edge: Edge, *, graph: str) -> None:
        """Add an edge to a named graph."""

    @abstractmethod
    def remove_vertex(self, vertex_id: int, *, graph: str) -> None:
        """Remove a vertex from a named graph."""

    @abstractmethod
    def remove_edge(self, edge_id: int, *, graph: str) -> None:
        """Remove an edge from a named graph."""

    # --- Queries ---

    @abstractmethod
    def neighbors(
        self,
        vertex_id: int,
        label: str | None = None,
        direction: str = "out",
        *,
        graph: str,
    ) -> list[int]:
        """Return neighbor vertex IDs."""

    @abstractmethod
    def vertices_by_label(self, label: str, *, graph: str) -> list[Vertex]:
        """Return vertices with a given label in a graph."""

    @abstractmethod
    def vertices_in_graph(self, graph: str) -> list[Vertex]:
        """Return all vertices in a graph."""

    @abstractmethod
    def edges_in_graph(self, graph: str) -> list[Edge]:
        """Return all edges in a graph."""

    @abstractmethod
    def vertex_graphs(self, vertex_id: int) -> set[str]:
        """Return set of graph names a vertex belongs to."""

    # --- Graph-scoped adjacency accessors ---

    @abstractmethod
    def out_edge_ids(self, vertex_id: int, *, graph: str) -> set[int]:
        """Return outgoing edge IDs for vertex in a specific graph."""

    @abstractmethod
    def in_edge_ids(self, vertex_id: int, *, graph: str) -> set[int]:
        """Return incoming edge IDs for vertex in a specific graph."""

    @abstractmethod
    def edge_ids_by_label(self, label: str, *, graph: str) -> set[int]:
        """Return edge IDs with a given label in a specific graph."""

    @abstractmethod
    def vertex_ids_in_graph(self, graph: str) -> set[int]:
        """Return all vertex IDs in a specific graph."""

    # --- Statistics ---

    @abstractmethod
    def degree_distribution(self, graph: str) -> dict[int, int]:
        """Out-degree distribution for vertices in graph."""

    @abstractmethod
    def label_degree(self, label: str, graph: str) -> float:
        """Average out-degree for edges with given label in graph."""

    @abstractmethod
    def vertex_label_counts(self, graph: str) -> dict[str, int]:
        """Count of vertices per vertex label in graph."""

    # --- Global accessors ---

    @abstractmethod
    def get_vertex(self, vertex_id: int) -> Vertex | None:
        """Return vertex by ID, or None."""

    @abstractmethod
    def get_edge(self, edge_id: int) -> Edge | None:
        """Return edge by ID, or None."""

    @abstractmethod
    def next_vertex_id(self) -> int:
        """Return and advance the next available vertex ID."""

    @abstractmethod
    def next_edge_id(self) -> int:
        """Return and advance the next available edge ID."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all vertices, edges, and graphs."""

    @property
    @abstractmethod
    def vertices(self) -> dict[int, Vertex]:
        """Return a copy of all vertices."""

    @property
    @abstractmethod
    def edges(self) -> dict[int, Edge]:
        """Return a copy of all edges."""
