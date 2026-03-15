#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""DPccp join enumeration algorithm (Moerkotte & Neumann, 2006).

Enumerates connected subgraph complement pairs of the join graph to
find the optimal join order via dynamic programming.  Complexity is
O(3^n) where n is the number of relations, compared to O(n!) for
exhaustive enumeration.

The algorithm produces bushy join trees when they are cheaper than
left-deep trees, and falls back to a greedy heuristic for queries
with more than MAX_DP_RELATIONS relations.

Internally, relation subsets are represented as integer bitmasks for
O(1) hash lookup and set operations, avoiding the O(k) overhead of
frozenset construction and hashing in the inner enumeration loops.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from uqa.planner.join_graph import JoinEdge, JoinGraph

# Use index join when the smaller side has fewer rows than this threshold.
# Mirrors the constant in join_order.py; duplicated here to avoid a
# circular import (join_order imports DPccp from this module).
INDEX_JOIN_THRESHOLD = 100

# Maximum number of relations for exact DP enumeration.
# Beyond this threshold, use greedy heuristic to avoid
# exponential planning time.
MAX_DP_RELATIONS = 16


@dataclass(slots=True)
class JoinPlan:
    """A (sub)plan for joining a set of relations.

    Attributes:
        relations: Frozenset of relation indices in this plan.
        operator: The join operator tree for this subset.
        cardinality: Estimated result cardinality.
        cost: Estimated total cost (cumulative).
        left: Left child plan (None for base relations).
        right: Right child plan (None for base relations).
        join_edge: The join predicate used (None for base relations).
    """

    relations: frozenset[int]
    operator: Any
    cardinality: float
    cost: float
    left: JoinPlan | None = None
    right: JoinPlan | None = None
    join_edge: JoinEdge | None = None


def _mask_to_frozenset(mask: int) -> frozenset[int]:
    """Convert a bitmask to a frozenset of set bit positions."""
    result: list[int] = []
    i = 0
    while mask:
        if mask & 1:
            result.append(i)
        mask >>= 1
        i += 1
    return frozenset(result)


def _frozenset_to_mask(fs: frozenset[int]) -> int:
    """Convert a frozenset of integers to a bitmask."""
    mask = 0
    for i in fs:
        mask |= 1 << i
    return mask


class DPccp:
    """DPccp join order optimizer.

    Given a JoinGraph, finds the minimum-cost join order using dynamic
    programming over connected subgraph complement pairs.

    The DP table uses integer bitmask keys for O(1) operations in the
    inner enumeration loop.  JoinPlan.relations remains a frozenset
    for API compatibility.
    """

    def __init__(self, graph: JoinGraph) -> None:
        self._graph = graph
        self._dp: dict[int, JoinPlan] = {}
        self._all_mask = (1 << len(graph)) - 1

    def optimize(self) -> JoinPlan:
        """Find the optimal join plan for all relations in the graph.

        Returns the JoinPlan covering all relations with minimum cost.
        Falls back to greedy for large queries.
        """
        n = len(self._graph)
        if n == 0:
            raise ValueError("Join graph has no relations")
        if n == 1:
            node = self._graph.nodes[0]
            return JoinPlan(
                relations=frozenset({0}),
                operator=node.operator,
                cardinality=node.cardinality,
                cost=node.cardinality,
            )

        # Initialize base relations
        for i in range(n):
            node = self._graph.nodes[i]
            self._dp[1 << i] = JoinPlan(
                relations=frozenset({i}),
                operator=node.operator,
                cardinality=node.cardinality,
                cost=node.cardinality,
            )

        if n > MAX_DP_RELATIONS:
            return self._greedy_optimize()

        # Enumerate connected subgraph complement pairs
        self._enumerate_csg_cmp_pairs()

        result = self._dp.get(self._all_mask)
        if result is None:
            # Graph is disconnected; join connected components
            return self._join_disconnected_components()

        return result

    def _enumerate_csg_cmp_pairs(self) -> None:
        """Core DPccp: enumerate all connected subgraph complement pairs.

        Builds connected subgraphs incrementally via BFS extension
        instead of generating all C(n,k) subsets and filtering.
        Each connected subgraph S is formed by extending a smaller
        connected subgraph with an adjacent vertex whose index exceeds
        min(S), ensuring each subgraph is generated exactly once.

        Uses a bytearray lookup table (indexed by bitmask) for O(1)
        connectivity checks instead of hash-based set lookups.
        """
        n = len(self._graph)

        # Pre-compute neighbor lists as Python lists for faster iteration.
        neighbors: list[list[int]] = [self._graph.neighbors(i) for i in range(n)]

        # Bytearray lookup table: connected[mask] == 1 iff the subgraph
        # represented by mask is connected.  At most 2^16 = 64 KB for
        # MAX_DP_RELATIONS = 16.
        connected = bytearray(1 << n)
        prev_layer: list[int] = []
        for i in range(n):
            mask = 1 << i
            connected[mask] = 1
            prev_layer.append(mask)

        for _size in range(2, n + 1):
            cur_layer: list[int] = []
            for s_mask in prev_layer:
                # Find lowest set bit position (= min node in subset).
                min_node = (s_mask & -s_mask).bit_length() - 1
                # Try extending with each neighbor of each node in s.
                node = 0
                tmp = s_mask
                while tmp:
                    if tmp & 1:
                        for nb in neighbors[node]:
                            if nb > min_node and not (s_mask & (1 << nb)):
                                new_mask = s_mask | (1 << nb)
                                if not connected[new_mask]:
                                    connected[new_mask] = 1
                                    cur_layer.append(new_mask)
                    tmp >>= 1
                    node += 1

            # Phase 2: Enumerate valid splits for each new subgraph.
            for subset_mask in cur_layer:
                self._enumerate_splits(subset_mask, connected)

            prev_layer = cur_layer

    def _enumerate_splits(
        self,
        subset_mask: int,
        connected: bytearray,
    ) -> None:
        """Try all valid splits of *subset_mask* into (s1, s2).

        Enumerates only submasks that contain the lowest set bit
        (canonical half) using the identity:
        ``rest = subset_mask ^ lowest_bit``; iterate submasks of
        ``rest`` and OR in ``lowest_bit``.  This skips the entire
        non-canonical half without branch checks.

        Connectivity is checked via O(1) bytearray indexing.
        """
        dp = self._dp
        graph = self._graph
        lowest_bit = subset_mask & -subset_mask
        rest = subset_mask ^ lowest_bit

        # Enumerate submasks of rest; each | lowest_bit gives a
        # canonical submask of subset_mask (containing the min element).
        # Start from (rest - 1) & rest to skip the full set.
        # The loop body is split: the while handles sub_rest > 0,
        # and the trailing block handles sub_rest == 0 (singleton s1).
        sub_rest = (rest - 1) & rest
        while sub_rest:
            sub = sub_rest | lowest_bit
            comp = subset_mask ^ sub
            if connected[sub] and connected[comp]:
                plan1 = dp.get(sub)
                plan2 = dp.get(comp)
                if plan1 is not None and plan2 is not None:
                    edges = graph.edges_between(plan1.relations, plan2.relations)
                    if edges:
                        self._emit_csg_cmp_pair(plan1, plan2, edges, subset_mask)
            sub_rest = (sub_rest - 1) & rest

        # sub_rest == 0: s1 = {min element}, s2 = rest of subset.
        # Singletons are always connected, so only check s2.
        if connected[rest]:
            plan1 = dp.get(lowest_bit)
            plan2 = dp.get(rest)
            if plan1 is not None and plan2 is not None:
                edges = graph.edges_between(plan1.relations, plan2.relations)
                if edges:
                    self._emit_csg_cmp_pair(plan1, plan2, edges, subset_mask)

    def _emit_csg_cmp_pair(
        self,
        plan1: JoinPlan,
        plan2: JoinPlan,
        edges: list[JoinEdge],
        combined_mask: int,
    ) -> None:
        """Consider joining plan1 and plan2 via the given edges."""
        # Compute join cardinality: product * selectivity for each edge
        cardinality = plan1.cardinality * plan2.cardinality
        for edge in edges:
            cardinality *= edge.selectivity

        # Cost = C_out + C_left + C_right
        # Use index join cost when the smaller side fits within threshold;
        # otherwise use hash join cost.
        min_card = min(plan1.cardinality, plan2.cardinality)
        max_card = max(plan1.cardinality, plan2.cardinality)
        if min_card <= INDEX_JOIN_THRESHOLD:
            join_cost = min_card * math.log2(max_card + 1)
        else:
            join_cost = plan1.cardinality + plan2.cardinality
        total_cost = join_cost + plan1.cost + plan2.cost

        existing = self._dp.get(combined_mask)
        if existing is None or total_cost < existing.cost:
            self._dp[combined_mask] = JoinPlan(
                relations=plan1.relations | plan2.relations,
                operator=None,  # Built later during plan materialization
                cardinality=cardinality,
                cost=total_cost,
                left=plan1,
                right=plan2,
                join_edge=edges[0],  # Primary join edge
            )

    def _is_connected(self, subset: frozenset[int]) -> bool:
        """Check if the subgraph induced by *subset* is connected."""
        if len(subset) <= 1:
            return True

        start = next(iter(subset))
        visited: set[int] = {start}
        stack = [start]

        while stack:
            node = stack.pop()
            for neighbor in self._graph.neighbors(node):
                if neighbor in subset and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        return len(visited) == len(subset)

    def _join_disconnected_components(self) -> JoinPlan:
        """Handle disconnected join graphs by cross-joining components.

        When the join graph is not fully connected (e.g. FROM a, b
        with no join predicate), identify connected components and
        join them with cross products.
        """
        components = self._find_connected_components()

        # Solve each component independently
        component_plans: list[JoinPlan] = []
        for component in components:
            if len(component) == 1:
                node_idx = next(iter(component))
                plan = self._dp[1 << node_idx]
            else:
                comp_mask = _frozenset_to_mask(component)
                plan = self._dp.get(comp_mask)
                if plan is None:
                    # Component was not solved; should not happen for
                    # connected components but handle gracefully
                    sub_graph = self._build_subgraph(component)
                    sub_solver = DPccp(sub_graph)
                    sub_plan = sub_solver.optimize()
                    plan = self._remap_plan(sub_plan, sorted(component))
            component_plans.append(plan)

        # Cross-join components in order of ascending cardinality
        component_plans.sort(key=lambda p: p.cardinality)
        result = component_plans[0]
        for plan in component_plans[1:]:
            combined = result.relations | plan.relations
            cardinality = result.cardinality * plan.cardinality
            cost = cardinality + result.cost + plan.cost
            result = JoinPlan(
                relations=combined,
                operator=None,
                cardinality=cardinality,
                cost=cost,
                left=result,
                right=plan,
                join_edge=None,  # Cross join
            )
        return result

    def _find_connected_components(self) -> list[frozenset[int]]:
        """Find all connected components of the join graph."""
        all_nodes = set(range(len(self._graph)))
        remaining = set(all_nodes)
        components: list[frozenset[int]] = []

        while remaining:
            start = next(iter(remaining))
            visited: set[int] = {start}
            stack = [start]

            while stack:
                node = stack.pop()
                for neighbor in self._graph.neighbors(node):
                    if neighbor in remaining and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

            components.append(frozenset(visited))
            remaining -= visited

        return components

    def _build_subgraph(self, nodes: frozenset[int]) -> JoinGraph:
        """Build a JoinGraph containing only the given nodes."""
        sub = JoinGraph()
        index_map: dict[int, int] = {}

        for old_idx in sorted(nodes):
            node = self._graph.nodes[old_idx]
            new_idx = sub.add_node(
                alias=node.alias,
                operator=node.operator,
                table=node.table,
                cardinality=node.cardinality,
                column_stats=node.column_stats,
            )
            index_map[old_idx] = new_idx

        for edge in self._graph.edges:
            if edge.left_node in nodes and edge.right_node in nodes:
                sub.add_edge(
                    left_node=index_map[edge.left_node],
                    right_node=index_map[edge.right_node],
                    left_field=edge.left_field,
                    right_field=edge.right_field,
                    selectivity=edge.selectivity,
                )

        return sub

    def _remap_plan(self, plan: JoinPlan, original_indices: list[int]) -> JoinPlan:
        """Remap plan relation indices from subgraph back to original graph."""
        new_rels = frozenset(original_indices[i] for i in plan.relations)
        return JoinPlan(
            relations=new_rels,
            operator=plan.operator,
            cardinality=plan.cardinality,
            cost=plan.cost,
            left=(self._remap_plan(plan.left, original_indices) if plan.left else None),
            right=(
                self._remap_plan(plan.right, original_indices) if plan.right else None
            ),
            join_edge=plan.join_edge,
        )

    def _greedy_optimize(self) -> JoinPlan:
        """Greedy join ordering for large queries (> MAX_DP_RELATIONS).

        At each step, pick the pair of existing plans with the lowest
        join cost and merge them.  This is O(n^3) in the number of
        relations.
        """
        active: dict[int, JoinPlan] = dict(self._dp)

        while len(active) > 1:
            best_cost = float("inf")
            best_combined_mask: int = 0
            best_plan: JoinPlan | None = None

            items = list(active.items())
            for i, (m1, p1) in enumerate(items):
                for m2, p2 in items[i + 1 :]:
                    edges = self._graph.edges_between(p1.relations, p2.relations)
                    if not edges:
                        continue

                    cardinality = p1.cardinality * p2.cardinality
                    for edge in edges:
                        cardinality *= edge.selectivity

                    greedy_min = min(p1.cardinality, p2.cardinality)
                    greedy_max = max(p1.cardinality, p2.cardinality)
                    if greedy_min <= INDEX_JOIN_THRESHOLD:
                        greedy_join_cost = greedy_min * math.log2(greedy_max + 1)
                    else:
                        greedy_join_cost = p1.cardinality + p2.cardinality
                    cost = greedy_join_cost + p1.cost + p2.cost

                    if cost < best_cost:
                        best_cost = cost
                        best_combined_mask = m1 | m2
                        best_plan = JoinPlan(
                            relations=p1.relations | p2.relations,
                            operator=None,
                            cardinality=cardinality,
                            cost=cost,
                            left=p1,
                            right=p2,
                            join_edge=edges[0],
                        )

            if best_plan is None:
                # No more edges; cross-join remaining
                remaining = list(active.values())
                remaining.sort(key=lambda p: p.cardinality)
                result = remaining[0]
                for plan in remaining[1:]:
                    combined = result.relations | plan.relations
                    cardinality = result.cardinality * plan.cardinality
                    cost = cardinality + result.cost + plan.cost
                    result = JoinPlan(
                        relations=combined,
                        operator=None,
                        cardinality=cardinality,
                        cost=cost,
                        left=result,
                        right=plan,
                        join_edge=None,
                    )
                return result

            # Merge the best pair
            for rel_mask in list(active.keys()):
                if rel_mask & best_combined_mask == rel_mask:
                    del active[rel_mask]
            active[best_combined_mask] = best_plan

        return next(iter(active.values()))
