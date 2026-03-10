#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Join order optimizer: builds optimal operator trees from DPccp plans.

Bridges the gap between the DPccp enumerator (which produces abstract
JoinPlans) and the SQL compiler (which needs concrete join operator
trees).  Materializes the chosen join order into InnerJoinOperator /
CrossJoinOperator instances.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from uqa.planner.join_enumerator import DPccp, JoinPlan
from uqa.planner.join_graph import JoinGraph

if TYPE_CHECKING:
    from uqa.sql.table import Table


class JoinOrderOptimizer:
    """Determines optimal join ordering using DPccp.

    Usage::

        optimizer = JoinOrderOptimizer()
        operator = optimizer.optimize(relations, predicates)
    """

    def optimize(
        self,
        relations: list[dict[str, Any]],
        predicates: list[dict[str, Any]],
    ) -> tuple[Any, Table | None]:
        """Find the optimal join order and build the operator tree.

        Parameters
        ----------
        relations:
            List of dicts with keys:
            - ``alias``: Table alias or name
            - ``operator``: Scan operator for this relation
            - ``table``: Table object (may be None)
            - ``cardinality``: Estimated row count
            - ``column_stats``: Per-column ColumnStats dict
        predicates:
            List of dicts with keys:
            - ``left_alias``: Left table alias
            - ``right_alias``: Right table alias
            - ``left_field``: Left join column
            - ``right_field``: Right join column

        Returns
        -------
        tuple[operator, Table | None]
            The root join operator and the first resolved Table.
        """
        if len(relations) <= 1:
            rel = relations[0]
            return rel["operator"], rel["table"]

        graph = self._build_graph(relations, predicates)
        solver = DPccp(graph)
        plan = solver.optimize()
        operator = self._materialize(plan, graph)

        # Return the first non-None table as context table
        table = None
        for rel in relations:
            if rel["table"] is not None:
                table = rel["table"]
                break

        return operator, table

    def _build_graph(
        self,
        relations: list[dict[str, Any]],
        predicates: list[dict[str, Any]],
    ) -> JoinGraph:
        """Construct a JoinGraph from relation and predicate descriptions."""
        graph = JoinGraph()
        alias_to_idx: dict[str, int] = {}

        for rel in relations:
            idx = graph.add_node(
                alias=rel["alias"],
                operator=rel["operator"],
                table=rel["table"],
                cardinality=rel["cardinality"],
                column_stats=rel.get("column_stats", {}),
            )
            alias = rel["alias"]
            if alias is not None:
                alias_to_idx[alias] = idx

        for pred in predicates:
            left_idx = alias_to_idx.get(pred["left_alias"])
            right_idx = alias_to_idx.get(pred["right_alias"])
            if left_idx is None or right_idx is None:
                continue

            selectivity = graph.estimate_join_selectivity(
                left_idx, right_idx,
                pred["left_field"], pred["right_field"],
            )
            graph.add_edge(
                left_node=left_idx,
                right_node=right_idx,
                left_field=pred["left_field"],
                right_field=pred["right_field"],
                selectivity=selectivity,
            )

        return graph

    def _materialize(self, plan: JoinPlan, graph: JoinGraph) -> Any:
        """Recursively build join operators from a JoinPlan tree."""
        if plan.left is None and plan.right is None:
            # Base relation: return its scan operator
            return plan.operator

        assert plan.left is not None and plan.right is not None

        left_op = self._materialize(plan.left, graph)
        right_op = self._materialize(plan.right, graph)

        if plan.join_edge is None:
            # Cross join (no predicate between components)
            from uqa.joins.cross import CrossJoinOperator
            return CrossJoinOperator(left_op, right_op)

        from uqa.joins.base import JoinCondition
        from uqa.joins.inner import InnerJoinOperator

        condition = JoinCondition(
            left_field=plan.join_edge.left_field,
            right_field=plan.join_edge.right_field,
        )

        # Orient the condition fields correctly:
        # If the plan swapped left/right relative to the edge definition,
        # we need to swap the condition fields too.
        edge = plan.join_edge
        left_rels = plan.left.relations
        if edge.left_node not in left_rels and edge.right_node in left_rels:
            condition = JoinCondition(
                left_field=edge.right_field,
                right_field=edge.left_field,
            )

        return InnerJoinOperator(left_op, right_op, condition)
