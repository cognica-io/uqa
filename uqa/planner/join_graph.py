#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Join graph construction for join order optimization.

A join graph represents the relations (nodes) and join predicates
(edges) extracted from a SQL query's FROM/JOIN clauses.  Each node
stores cardinality and column statistics; each edge stores the join
predicate (equijoin field pair) and selectivity estimate.

This graph is the input to the DPccp join enumerator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class JoinEdge:
    """An edge in the join graph representing an equijoin predicate.

    Attributes:
        left_node: Index of the left relation.
        right_node: Index of the right relation.
        left_field: Join column on the left side.
        right_field: Join column on the right side.
        selectivity: Estimated join selectivity (1 / max(NDV_l, NDV_r)).
    """

    left_node: int
    right_node: int
    left_field: str
    right_field: str
    selectivity: float = 1.0


@dataclass(slots=True)
class JoinNode:
    """A node in the join graph representing a base relation.

    Attributes:
        index: Node index (0-based position in the node list).
        alias: Table alias or name.
        operator: The scan operator for this relation.
        table: The Table object (may be None for derived tables).
        cardinality: Estimated row count.
        column_stats: Per-column statistics from ANALYZE.
    """

    index: int
    alias: str | None
    operator: Any
    table: Any
    cardinality: float
    column_stats: dict[str, Any] = field(default_factory=dict)


class JoinGraph:
    """Undirected graph of relations connected by join predicates.

    Nodes are base relations; edges are equijoin conditions.
    The adjacency list representation supports efficient neighbor
    enumeration required by the DPccp algorithm.
    """

    def __init__(self) -> None:
        self.nodes: list[JoinNode] = []
        self.edges: list[JoinEdge] = []
        self._adjacency: dict[int, list[JoinEdge]] = {}

    def add_node(
        self,
        alias: str | None,
        operator: Any,
        table: Any,
        cardinality: float,
        column_stats: dict[str, Any] | None = None,
    ) -> int:
        """Add a relation node and return its index."""
        idx = len(self.nodes)
        self.nodes.append(
            JoinNode(
                index=idx,
                alias=alias,
                operator=operator,
                table=table,
                cardinality=cardinality,
                column_stats=column_stats or {},
            )
        )
        self._adjacency[idx] = []
        return idx

    def add_edge(
        self,
        left_node: int,
        right_node: int,
        left_field: str,
        right_field: str,
        selectivity: float = 1.0,
    ) -> None:
        """Add a join predicate edge between two relation nodes."""
        edge = JoinEdge(
            left_node=left_node,
            right_node=right_node,
            left_field=left_field,
            right_field=right_field,
            selectivity=selectivity,
        )
        self.edges.append(edge)
        self._adjacency[left_node].append(edge)
        self._adjacency[right_node].append(edge)

    def neighbors(self, node: int) -> list[int]:
        """Return the indices of all nodes adjacent to *node*."""
        result: list[int] = []
        for edge in self._adjacency.get(node, []):
            other = edge.right_node if edge.left_node == node else edge.left_node
            result.append(other)
        return result

    def edges_between(
        self, set_a: frozenset[int], set_b: frozenset[int]
    ) -> list[JoinEdge]:
        """Return all edges connecting a node in *set_a* to a node in *set_b*.

        Iterates the adjacency lists of the smaller set for O(|smaller| * degree)
        instead of scanning all edges O(E).
        """
        result: list[JoinEdge] = []
        smaller, larger = (set_a, set_b) if len(set_a) <= len(set_b) else (set_b, set_a)
        for node in smaller:
            for edge in self._adjacency.get(node, []):
                other = edge.right_node if edge.left_node == node else edge.left_node
                if other in larger:
                    result.append(edge)
        return result

    def __len__(self) -> int:
        return len(self.nodes)

    def estimate_join_selectivity(
        self,
        left_node: int,
        right_node: int,
        left_field: str,
        right_field: str,
    ) -> float:
        """Estimate equijoin selectivity as 1 / max(NDV_left, NDV_right).

        Falls back to a default of 1/100 when statistics are unavailable.
        """
        left_stats = self.nodes[left_node].column_stats.get(left_field)
        right_stats = self.nodes[right_node].column_stats.get(right_field)

        left_ndv = (
            left_stats.distinct_count
            if left_stats is not None and left_stats.distinct_count > 0
            else 0
        )
        right_ndv = (
            right_stats.distinct_count
            if right_stats is not None and right_stats.distinct_count > 0
            else 0
        )

        max_ndv = max(left_ndv, right_ndv)
        if max_ndv > 0:
            return 1.0 / max_ndv
        # Default selectivity when no statistics are available
        return 0.01
