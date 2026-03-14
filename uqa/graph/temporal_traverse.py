#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.graph.store import GraphStore
    from uqa.graph.temporal_filter import TemporalFilter


class TemporalTraverseOperator:
    """Temporal-aware BFS traversal (Section 10, Paper 2).

    Same as TraverseOperator but skips edges failing the temporal
    filter.  Only edges valid at the given timestamp or within the
    given time range are followed.
    """

    def __init__(
        self,
        start_vertex: int,
        label: str | None = None,
        max_hops: int = 1,
        temporal_filter: TemporalFilter | None = None,
    ) -> None:
        self.start_vertex = start_vertex
        self.label = label
        self.max_hops = max_hops
        self.temporal_filter = temporal_filter

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        visited: set[int] = set()
        frontier: set[int] = {self.start_vertex}
        all_edges: set[int] = set()

        for _ in range(self.max_hops):
            next_frontier: set[int] = set()
            for v in frontier:
                adj = graph._adj_out.get(v, set())
                if self.label is not None:
                    label_eids = graph._label_index.get(self.label, set())
                    edge_ids = adj & label_eids
                else:
                    edge_ids = adj
                for eid in edge_ids:
                    edge = graph._edges[eid]
                    # Apply temporal filter
                    if (
                        self.temporal_filter is not None
                        and not self.temporal_filter.is_valid(edge.properties)
                    ):
                        continue
                    neighbor = edge.target_id
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                        all_edges.add(eid)
            visited.update(frontier)
            frontier = next_frontier
            if not frontier:
                break
        visited.update(frontier)

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        frozen_visited = frozenset(visited)
        frozen_edges = frozenset(all_edges)
        for vid in sorted(visited):
            entry = PostingEntry(vid, Payload(score=0.9))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozen_visited,
                subgraph_edges=frozen_edges,
            )

        return GraphPostingList(entries, graph_payloads)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs) * 0.1
