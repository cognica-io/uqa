#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.graph.pattern import EdgePattern, GraphPattern
    from uqa.graph.store import GraphStore
    from uqa.graph.temporal_filter import TemporalFilter


class TemporalPatternMatchOperator:
    """Temporal-aware pattern matching (Section 10, Paper 2).

    Same as PatternMatchOperator but pushes temporal filter into edge
    constraints so only temporally valid edges participate in pattern
    matching.
    """

    def __init__(
        self,
        pattern: GraphPattern,
        temporal_filter: TemporalFilter | None = None,
        *,
        graph: str,
    ) -> None:
        self.pattern = pattern
        self.temporal_filter = temporal_filter
        self.graph_name = graph

    def execute(self, ctx: object) -> GraphPostingList:
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        g = self.graph_name

        var_candidates = self._compute_candidates(gs, g)

        var_edges: dict[str, list[EdgePattern]] = defaultdict(list)
        for ep in self.pattern.edge_patterns:
            var_edges[ep.source_var].append(ep)
            var_edges[ep.target_var].append(ep)

        variables = [vp.variable for vp in self.pattern.vertex_patterns]
        unassigned = set(variables)
        matches: list[dict[str, int]] = []
        self._backtrack(
            gs, g, var_candidates, var_edges, unassigned, {}, set(), matches
        )

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for i, assignment in enumerate(matches):
            match_vertices = frozenset(assignment.values())
            match_edges = self._collect_match_edges(gs, g, assignment)
            doc_id = i + 1
            entry = PostingEntry(
                doc_id,
                Payload(score=0.9, fields=dict(assignment)),
            )
            entries.append(entry)
            graph_payloads[doc_id] = GraphPayload(
                subgraph_vertices=match_vertices,
                subgraph_edges=match_edges,
            )

        return GraphPostingList(entries, graph_payloads)

    def _compute_candidates(self, gs: GraphStore, g: str) -> dict[str, list[int]]:
        vp_map = {vp.variable: vp for vp in self.pattern.vertex_patterns}
        candidates: dict[str, list[int]] = {}
        graph_vids = gs.vertex_ids_in_graph(g)
        for var, vp in vp_map.items():
            candidates[var] = [
                vid
                for vid in graph_vids
                if vid in gs._vertices
                and all(c(gs._vertices[vid]) for c in vp.constraints)
            ]
        return candidates

    def _backtrack(
        self,
        gs: GraphStore,
        g: str,
        var_candidates: dict[str, list[int]],
        var_edges: dict[str, list[EdgePattern]],
        unassigned: set[str],
        assignment: dict[str, int],
        assigned_values: set[int],
        matches: list[dict[str, int]],
    ) -> None:
        if not unassigned:
            matches.append(dict(assignment))
            return

        var = min(unassigned, key=lambda v: len(var_candidates[v]))

        for vid in var_candidates[var]:
            if vid in assigned_values:
                continue

            assignment[var] = vid
            assigned_values.add(vid)
            unassigned.discard(var)

            if self._validate_edges_for(gs, g, var, var_edges, assignment):
                self._backtrack(
                    gs,
                    g,
                    var_candidates,
                    var_edges,
                    unassigned,
                    assignment,
                    assigned_values,
                    matches,
                )

            del assignment[var]
            assigned_values.discard(vid)
            unassigned.add(var)

    def _validate_edges_for(
        self,
        gs: GraphStore,
        g: str,
        var: str,
        var_edges: dict[str, list[EdgePattern]],
        assignment: dict[str, int],
    ) -> bool:
        for ep in var_edges.get(var, []):
            src_id = assignment.get(ep.source_var)
            tgt_id = assignment.get(ep.target_var)
            if src_id is None or tgt_id is None:
                continue
            found = False
            for eid in gs.out_edge_ids(src_id, graph=g):
                edge = gs.get_edge(eid)
                if edge is None:
                    continue
                if edge.target_id != tgt_id:
                    continue
                if ep.label is not None and edge.label != ep.label:
                    continue
                if not all(c(edge) for c in ep.constraints):
                    continue
                # Apply temporal filter
                if (
                    self.temporal_filter is not None
                    and not self.temporal_filter.is_valid(edge.properties)
                ):
                    continue
                found = True
                break
            if not found:
                return False
        return True

    def _collect_match_edges(
        self, gs: GraphStore, g: str, assignment: dict[str, int]
    ) -> frozenset[int]:
        edge_ids: set[int] = set()
        for ep in self.pattern.edge_patterns:
            src_id = assignment[ep.source_var]
            tgt_id = assignment[ep.target_var]
            for eid in gs.out_edge_ids(src_id, graph=g):
                edge = gs.get_edge(eid)
                if edge is None:
                    continue
                if (
                    edge.target_id == tgt_id
                    and (ep.label is None or edge.label == ep.label)
                    and (
                        self.temporal_filter is None
                        or self.temporal_filter.is_valid(edge.properties)
                    )
                ):
                    edge_ids.add(eid)
                    break
        return frozenset(edge_ids)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs) ** 2
