#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.graph.pattern import GraphPattern
    from uqa.graph.store import GraphStore


@dataclass
class GraphDelta:
    """Describes changes to a graph (added/removed vertices and edges)."""

    added_vertex_ids: set[int] = field(default_factory=set)
    removed_vertex_ids: set[int] = field(default_factory=set)
    added_edge_ids: set[int] = field(default_factory=set)
    removed_edge_ids: set[int] = field(default_factory=set)

    def affected_vertex_ids(self) -> set[int]:
        """All vertex IDs affected by this delta."""
        return self.added_vertex_ids | self.removed_vertex_ids


class IncrementalPatternMatcher:
    """Delta-aware pattern matching (Section 9.3, Paper 2).

    Maintains a set of matches for a given pattern and efficiently
    updates them when the graph changes, rather than re-running
    full pattern matching.
    """

    def __init__(
        self,
        pattern: GraphPattern,
        base_matches: set[frozenset[int]] | None = None,
    ) -> None:
        self.pattern = pattern
        self.base_matches: set[frozenset[int]] = (
            set(base_matches) if base_matches is not None else set()
        )

    def update(
        self,
        graph: GraphStore,
        delta: GraphDelta,
    ) -> set[frozenset[int]]:
        """Update matches incrementally given a GraphDelta.

        1. Invalidate: remove matches containing any affected vertex IDs
        2. Re-match: constrain pattern variables to affected vertices,
           run PatternMatchOperator, collect new matches
        3. Merge new matches into base_matches
        """
        from uqa.graph.operators import PatternMatchOperator
        from uqa.graph.pattern import GraphPattern, VertexPattern
        from uqa.operators.base import ExecutionContext

        affected = delta.affected_vertex_ids()

        # Also collect vertices adjacent to added/removed edges
        for eid in delta.added_edge_ids | delta.removed_edge_ids:
            edge = graph.get_edge(eid)
            if edge is not None:
                affected.add(edge.source_id)
                affected.add(edge.target_id)

        # Step 1: Invalidate matches containing affected vertices
        self.base_matches = {
            match for match in self.base_matches if not match & affected
        }

        # Step 2: Re-match with each variable constrained to affected vertices
        ctx = ExecutionContext(graph_store=graph)
        new_matches: set[frozenset[int]] = set()

        for vp in self.pattern.vertex_patterns:
            # Create a constrained pattern where this variable is
            # restricted to affected vertex IDs
            constrained_vps = []
            for orig_vp in self.pattern.vertex_patterns:
                if orig_vp.variable == vp.variable:

                    def constraint(v, avids=frozenset(affected)):
                        return v.vertex_id in avids

                    constrained_vps.append(
                        VertexPattern(
                            orig_vp.variable,
                            [*orig_vp.constraints, constraint],
                        )
                    )
                else:
                    constrained_vps.append(orig_vp)

            constrained_pattern = GraphPattern(
                constrained_vps, self.pattern.edge_patterns
            )
            pm = PatternMatchOperator(constrained_pattern)
            gpl = pm.execute(ctx)

            for entry in gpl:
                gp = gpl.get_graph_payload(entry.doc_id)
                if gp is not None:
                    new_matches.add(gp.subgraph_vertices)

        # Step 3: Merge
        self.base_matches |= new_matches
        return self.base_matches
