#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import Edge, Vertex


@dataclass
class _DeltaOp:
    """A single mutation operation in a graph delta."""

    kind: str  # "add_vertex", "remove_vertex", "add_edge", "remove_edge"
    vertex: Vertex | None = None
    edge: Edge | None = None
    vertex_id: int | None = None
    edge_id: int | None = None


class GraphDelta:
    """Records add/remove vertex/edge operations (Section 9.3, Paper 2).

    A GraphDelta accumulates mutation operations that can be applied
    atomically to a GraphStore.  It tracks which vertices and edge
    labels are affected, enabling targeted path index invalidation.
    """

    def __init__(self) -> None:
        self._ops: list[_DeltaOp] = []

    def add_vertex(self, vertex: Vertex) -> None:
        self._ops.append(_DeltaOp(kind="add_vertex", vertex=vertex))

    def remove_vertex(self, vertex_id: int) -> None:
        self._ops.append(_DeltaOp(kind="remove_vertex", vertex_id=vertex_id))

    def add_edge(self, edge: Edge) -> None:
        self._ops.append(_DeltaOp(kind="add_edge", edge=edge))

    def remove_edge(self, edge_id: int) -> None:
        self._ops.append(_DeltaOp(kind="remove_edge", edge_id=edge_id))

    @property
    def ops(self) -> list[_DeltaOp]:
        return list(self._ops)

    def affected_vertex_ids(self) -> set[int]:
        """Return the set of vertex IDs affected by this delta."""
        ids: set[int] = set()
        for op in self._ops:
            if op.kind == "add_vertex" and op.vertex is not None:
                ids.add(op.vertex.vertex_id)
            elif op.kind == "remove_vertex" and op.vertex_id is not None:
                ids.add(op.vertex_id)
            elif op.kind == "add_edge" and op.edge is not None:
                ids.add(op.edge.source_id)
                ids.add(op.edge.target_id)
            elif op.kind == "remove_edge" and op.edge_id is not None:
                ids.add(op.edge_id)  # edge_id is not vertex_id; we skip
        return ids

    def affected_edge_labels(self) -> set[str]:
        """Return the set of edge labels affected by this delta."""
        labels: set[str] = set()
        for op in self._ops:
            if op.kind == "add_edge" and op.edge is not None:
                labels.add(op.edge.label)
        return labels

    def is_empty(self) -> bool:
        return len(self._ops) == 0

    def __len__(self) -> int:
        return len(self._ops)
