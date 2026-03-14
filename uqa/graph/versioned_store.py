#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.graph.delta import GraphDelta

if TYPE_CHECKING:
    from uqa.graph.store import GraphStore


class VersionedGraphStore:
    """Version-tracked graph store with delta operations (Section 9.3, Paper 2).

    Wraps a base GraphStore and tracks applied deltas with version
    numbers.  Supports rollback by reverse-applying stored deltas.
    Invalidates path indexes when mutations affect indexed label
    sequences.
    """

    def __init__(self, base: GraphStore) -> None:
        self._base = base
        self._version: int = 0
        self._deltas: list[GraphDelta] = []
        self._inverse_deltas: list[GraphDelta] = []
        self._on_invalidate: list[object] = []

    @property
    def base(self) -> GraphStore:
        return self._base

    @property
    def version(self) -> int:
        return self._version

    def apply(self, delta: GraphDelta) -> int:
        """Apply a delta to the base store, increment version.

        Returns the new version number. Stores inverse operations
        for rollback support.
        """
        inverse = GraphDelta()

        for op in delta.ops:
            if op.kind == "add_vertex" and op.vertex is not None:
                self._base.add_vertex(op.vertex)
                inverse.remove_vertex(op.vertex.vertex_id)
            elif op.kind == "remove_vertex" and op.vertex_id is not None:
                # Store vertex for inverse before removing
                existing = self._base.get_vertex(op.vertex_id)
                self._base.remove_vertex(op.vertex_id)
                if existing is not None:
                    inverse.add_vertex(existing)
            elif op.kind == "add_edge" and op.edge is not None:
                self._base.add_edge(op.edge)
                inverse.remove_edge(op.edge.edge_id)
            elif op.kind == "remove_edge" and op.edge_id is not None:
                existing_edge = self._base.get_edge(op.edge_id)
                self._base.remove_edge(op.edge_id)
                if existing_edge is not None:
                    inverse.add_edge(existing_edge)

        self._version += 1
        self._deltas.append(delta)
        self._inverse_deltas.append(inverse)

        # Notify invalidation callbacks
        affected_labels = delta.affected_edge_labels()
        if affected_labels:
            for callback in self._on_invalidate:
                if callable(callback):
                    callback(affected_labels)

        return self._version

    def rollback(self, to_version: int) -> None:
        """Rollback to a specific version by reverse-applying deltas."""
        if to_version < 0 or to_version > self._version:
            raise ValueError(
                f"Cannot rollback to version {to_version} "
                f"(current: {self._version})"
            )
        while self._version > to_version:
            inverse = self._inverse_deltas.pop()
            self._deltas.pop()
            # Apply inverse operations directly (not via apply())
            for op in inverse.ops:
                if op.kind == "add_vertex" and op.vertex is not None:
                    self._base.add_vertex(op.vertex)
                elif op.kind == "remove_vertex" and op.vertex_id is not None:
                    self._base.remove_vertex(op.vertex_id)
                elif op.kind == "add_edge" and op.edge is not None:
                    self._base.add_edge(op.edge)
                elif op.kind == "remove_edge" and op.edge_id is not None:
                    self._base.remove_edge(op.edge_id)
            self._version -= 1

    def on_invalidate(self, callback: object) -> None:
        """Register a callback for path index invalidation.

        The callback receives a set of affected edge labels.
        """
        self._on_invalidate.append(callback)
