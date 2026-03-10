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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uqa.planner.join_graph import JoinEdge, JoinGraph

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


class DPccp:
    """DPccp join order optimizer.

    Given a JoinGraph, finds the minimum-cost join order using dynamic
    programming over connected subgraph complement pairs.
    """

    def __init__(self, graph: JoinGraph) -> None:
        self._graph = graph
        self._dp: dict[frozenset[int], JoinPlan] = {}
        self._all_nodes = frozenset(range(len(graph)))

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
            self._dp[frozenset({i})] = JoinPlan(
                relations=frozenset({i}),
                operator=node.operator,
                cardinality=node.cardinality,
                cost=node.cardinality,
            )

        if n > MAX_DP_RELATIONS:
            return self._greedy_optimize()

        # Enumerate connected subgraph complement pairs
        self._enumerate_csg_cmp_pairs()

        result = self._dp.get(self._all_nodes)
        if result is None:
            # Graph is disconnected; join connected components
            return self._join_disconnected_components()

        return result

    def _enumerate_csg_cmp_pairs(self) -> None:
        """Core DPccp: enumerate all connected subgraph complement pairs.

        For each connected subgraph S1, find connected subgraphs S2 in
        the complement (V - S1) that are adjacent to S1.  For each
        (S1, S2) pair with an edge between them, consider joining them.
        """
        n = len(self._graph)
        nodes = list(range(n))

        # Process subsets in increasing size order
        for size in range(2, n + 1):
            for subset in self._subsets_of_size(nodes, size):
                subset_fs = frozenset(subset)
                if not self._is_connected(subset_fs):
                    continue
                # Try all ways to split this connected subset into two
                # connected parts (S1, S2) where S1 and S2 are both
                # connected and have a join edge between them.
                self._enumerate_splits(subset_fs)

    def _enumerate_splits(self, subset: frozenset[int]) -> None:
        """Try all valid splits of *subset* into (S1, S2).

        A valid split requires:
        1. S1 and S2 are both non-empty and partition subset
        2. S1 and S2 are both connected subgraphs
        3. There is at least one join edge between S1 and S2
        """
        elements = sorted(subset)
        # Enumerate all non-empty proper subsets of *subset*
        # Use bitmask enumeration over the elements
        n = len(elements)
        # Only iterate half the splits (S1 < S2 by canonical order)
        # to avoid evaluating (S1, S2) and (S2, S1) twice
        for mask in range(1, (1 << n) - 1):
            s1_list = [elements[i] for i in range(n) if mask & (1 << i)]
            s2_list = [elements[i] for i in range(n) if not (mask & (1 << i))]

            # Canonical ordering: smallest element of S1 < smallest of S2
            if s1_list[0] > s2_list[0]:
                continue

            s1 = frozenset(s1_list)
            s2 = frozenset(s2_list)

            # Both must be connected
            if not self._is_connected(s1) or not self._is_connected(s2):
                continue

            # Must have a join edge between them
            edges = self._graph.edges_between(s1, s2)
            if not edges:
                continue

            # Both subplans must already exist in DP table
            plan1 = self._dp.get(s1)
            plan2 = self._dp.get(s2)
            if plan1 is None or plan2 is None:
                continue

            self._emit_csg_cmp_pair(plan1, plan2, edges)

    def _emit_csg_cmp_pair(
        self,
        plan1: JoinPlan,
        plan2: JoinPlan,
        edges: list[JoinEdge],
    ) -> None:
        """Consider joining plan1 and plan2 via the given edges."""
        combined = plan1.relations | plan2.relations

        # Compute join cardinality: product * selectivity for each edge
        cardinality = plan1.cardinality * plan2.cardinality
        for edge in edges:
            cardinality *= edge.selectivity

        # Cost = C_out + C_left + C_right
        # C_out approximates hash join cost as the sum of input sizes
        join_cost = plan1.cardinality + plan2.cardinality
        total_cost = join_cost + plan1.cost + plan2.cost

        existing = self._dp.get(combined)
        if existing is None or total_cost < existing.cost:
            self._dp[combined] = JoinPlan(
                relations=combined,
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
                plan = self._dp[frozenset({node_idx})]
            else:
                plan = self._dp.get(component)
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
        remaining = set(self._all_nodes)
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

    def _remap_plan(
        self, plan: JoinPlan, original_indices: list[int]
    ) -> JoinPlan:
        """Remap plan relation indices from subgraph back to original graph."""
        new_rels = frozenset(original_indices[i] for i in plan.relations)
        return JoinPlan(
            relations=new_rels,
            operator=plan.operator,
            cardinality=plan.cardinality,
            cost=plan.cost,
            left=(
                self._remap_plan(plan.left, original_indices)
                if plan.left else None
            ),
            right=(
                self._remap_plan(plan.right, original_indices)
                if plan.right else None
            ),
            join_edge=plan.join_edge,
        )

    def _greedy_optimize(self) -> JoinPlan:
        """Greedy join ordering for large queries (> MAX_DP_RELATIONS).

        At each step, pick the pair of existing plans with the lowest
        join cost and merge them.  This is O(n^3) in the number of
        relations.
        """
        active: dict[frozenset[int], JoinPlan] = dict(self._dp)

        while len(active) > 1:
            best_cost = float("inf")
            best_combined: frozenset[int] | None = None
            best_plan: JoinPlan | None = None

            plans = list(active.values())
            for i, p1 in enumerate(plans):
                for p2 in plans[i + 1:]:
                    edges = self._graph.edges_between(
                        p1.relations, p2.relations
                    )
                    if not edges:
                        continue

                    cardinality = p1.cardinality * p2.cardinality
                    for edge in edges:
                        cardinality *= edge.selectivity

                    cost = (
                        p1.cardinality + p2.cardinality + p1.cost + p2.cost
                    )

                    if cost < best_cost:
                        best_cost = cost
                        best_combined = p1.relations | p2.relations
                        best_plan = JoinPlan(
                            relations=best_combined,
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
            assert best_combined is not None
            for rel_set in list(active.keys()):
                if rel_set.issubset(best_combined):
                    del active[rel_set]
            active[best_combined] = best_plan

        return next(iter(active.values()))

    @staticmethod
    def _subsets_of_size(
        elements: list[int], size: int
    ) -> list[list[int]]:
        """Generate all subsets of *elements* with exactly *size* elements."""
        if size == 0:
            return [[]]
        if size > len(elements):
            return []

        result: list[list[int]] = []

        def backtrack(start: int, current: list[int]) -> None:
            if len(current) == size:
                result.append(list(current))
                return
            remaining = size - len(current)
            for i in range(start, len(elements) - remaining + 1):
                current.append(elements[i])
                backtrack(i + 1, current)
                current.pop()

        backtrack(0, [])
        return result
