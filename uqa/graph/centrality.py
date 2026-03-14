#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.graph.store import GraphStore


class PageRankOperator:
    """Compute PageRank centrality for all vertices in the graph.

    Uses power iteration on the adjacency matrix with a damping factor.
    Scores are min-max normalized to [0, 1].

    Algorithm:
        1. Initialize rank[v] = 1/N for all vertices.
        2. Iterate: new_rank[v] = (1 - d)/N + d * sum(rank[u] / out_degree(u)
           for u in in_neighbors(v)).
        3. Converge when L1 norm of rank delta < tolerance.
    """

    def __init__(
        self,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> None:
        self.damping = damping
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        vertices = list(graph._vertices.keys())
        n = len(vertices)

        if n == 0:
            return GraphPostingList()

        # Single vertex gets score 1.0
        if n == 1:
            vid = vertices[0]
            entry = PostingEntry(vid, Payload(score=1.0))
            gp = GraphPayload(
                subgraph_vertices=frozenset(vertices),
                subgraph_edges=frozenset(),
            )
            return GraphPostingList([entry], {vid: gp})

        d = self.damping
        rank: dict[int, float] = dict.fromkeys(vertices, 1.0 / n)

        # Precompute out-degree for each vertex
        out_degree: dict[int, int] = {}
        for v in vertices:
            out_degree[v] = len(graph._adj_out.get(v, set()))

        # Precompute in-neighbors for each vertex
        in_neighbors: dict[int, list[int]] = defaultdict(list)
        for v in vertices:
            for eid in graph._adj_in.get(v, set()):
                edge = graph._edges[eid]
                in_neighbors[v].append(edge.source_id)

        for _ in range(self.max_iterations):
            new_rank: dict[int, float] = {}
            for v in vertices:
                incoming_sum = 0.0
                for u in in_neighbors[v]:
                    deg = out_degree[u]
                    if deg > 0:
                        incoming_sum += rank[u] / deg
                new_rank[v] = (1.0 - d) / n + d * incoming_sum

            # Check convergence via L1 norm
            delta = sum(abs(new_rank[v] - rank[v]) for v in vertices)
            rank = new_rank
            if delta < self.tolerance:
                break

        # Min-max normalize to [0, 1]
        min_r = min(rank.values())
        max_r = max(rank.values())
        if max_r - min_r > 0:
            for v in vertices:
                rank[v] = (rank[v] - min_r) / (max_r - min_r)
        else:
            for v in vertices:
                rank[v] = 1.0

        # Build GraphPostingList sorted by doc_id
        all_vids = frozenset(vertices)
        all_eids = frozenset(graph._edges.keys())
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for vid in sorted(vertices):
            entry = PostingEntry(vid, Payload(score=rank[vid]))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=all_vids,
                subgraph_edges=all_eids,
            )

        return GraphPostingList(entries, graph_payloads)

    def cost_estimate(self, stats: IndexStats) -> float:
        return stats.total_docs * self.max_iterations * 0.1


class HITSOperator:
    """Compute HITS (Hyperlink-Induced Topic Search) centrality.

    Uses mutual reinforcement: authority scores are the sum of hub scores
    of in-neighbors, and hub scores are the sum of authority scores of
    out-neighbors.  Scores are min-max normalized to [0, 1].

    The payload score is set to the authority score.  Both hub_score and
    authority_score are stored in Payload.fields.
    """

    def __init__(
        self,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> None:
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        vertices = list(graph._vertices.keys())
        n = len(vertices)

        if n == 0:
            return GraphPostingList()

        # Initialize hub and authority scores to 1.0
        hub: dict[int, float] = dict.fromkeys(vertices, 1.0)
        auth: dict[int, float] = dict.fromkeys(vertices, 1.0)

        # Precompute in-neighbors and out-neighbors
        in_neighbors: dict[int, list[int]] = defaultdict(list)
        out_neighbors: dict[int, list[int]] = defaultdict(list)
        for v in vertices:
            for eid in graph._adj_in.get(v, set()):
                edge = graph._edges[eid]
                in_neighbors[v].append(edge.source_id)
            for eid in graph._adj_out.get(v, set()):
                edge = graph._edges[eid]
                out_neighbors[v].append(edge.target_id)

        for _ in range(self.max_iterations):
            # Update authority: auth[v] = sum of hub[u] for u in in-neighbors
            new_auth: dict[int, float] = {}
            for v in vertices:
                new_auth[v] = sum(hub[u] for u in in_neighbors[v])

            # Update hub: hub[v] = sum of auth[w] for w in out-neighbors
            new_hub: dict[int, float] = {}
            for v in vertices:
                new_hub[v] = sum(new_auth[w] for w in out_neighbors[v])

            # Normalize
            auth_norm = sum(a * a for a in new_auth.values()) ** 0.5
            hub_norm = sum(h * h for h in new_hub.values()) ** 0.5
            if auth_norm > 0:
                for v in vertices:
                    new_auth[v] /= auth_norm
            if hub_norm > 0:
                for v in vertices:
                    new_hub[v] /= hub_norm

            # Check convergence
            delta = sum(abs(new_auth[v] - auth[v]) for v in vertices) + sum(
                abs(new_hub[v] - hub[v]) for v in vertices
            )
            auth = new_auth
            hub = new_hub
            if delta < self.tolerance:
                break

        # Min-max normalize authority and hub scores independently to [0, 1]
        auth = _min_max_normalize(auth, vertices)
        hub = _min_max_normalize(hub, vertices)

        # Build GraphPostingList sorted by doc_id
        all_vids = frozenset(vertices)
        all_eids = frozenset(graph._edges.keys())
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for vid in sorted(vertices):
            entry = PostingEntry(
                vid,
                Payload(
                    score=auth[vid],
                    fields={
                        "hub_score": hub[vid],
                        "authority_score": auth[vid],
                    },
                ),
            )
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=all_vids,
                subgraph_edges=all_eids,
            )

        return GraphPostingList(entries, graph_payloads)

    def cost_estimate(self, stats: IndexStats) -> float:
        return stats.total_docs * self.max_iterations * 0.2


class BetweennessCentralityOperator:
    """Compute betweenness centrality for all vertices using Brandes algorithm.

    Complexity: O(|V| * |E|) for unweighted directed graphs.
    Scores are normalized by (N-1)*(N-2) for directed graphs and clamped
    to [0, 1].
    """

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        vertices = list(graph._vertices.keys())
        n = len(vertices)

        if n == 0:
            return GraphPostingList()

        # Single vertex: betweenness is 0.0 (no paths)
        if n == 1:
            vid = vertices[0]
            entry = PostingEntry(vid, Payload(score=0.0))
            gp = GraphPayload(
                subgraph_vertices=frozenset(vertices),
                subgraph_edges=frozenset(),
            )
            return GraphPostingList([entry], {vid: gp})

        # Precompute out-neighbors
        out_neighbors: dict[int, list[int]] = defaultdict(list)
        for v in vertices:
            for eid in graph._adj_out.get(v, set()):
                edge = graph._edges[eid]
                out_neighbors[v].append(edge.target_id)

        # Brandes algorithm
        cb: dict[int, float] = dict.fromkeys(vertices, 0.0)

        for s in vertices:
            # Single-source shortest paths from s
            stack: list[int] = []
            predecessors: dict[int, list[int]] = {v: [] for v in vertices}
            sigma: dict[int, int] = dict.fromkeys(vertices, 0)
            sigma[s] = 1
            dist: dict[int, int] = dict.fromkeys(vertices, -1)
            dist[s] = 0

            queue: deque[int] = deque([s])
            while queue:
                v = queue.popleft()
                stack.append(v)
                for w in out_neighbors[v]:
                    # w found for the first time?
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    # Shortest path to w via v?
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        predecessors[w].append(v)

            # Accumulation
            delta: dict[int, float] = dict.fromkeys(vertices, 0.0)
            while stack:
                w = stack.pop()
                for v in predecessors[w]:
                    if sigma[w] > 0:
                        delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != s:
                    cb[w] += delta[w]

        # Normalize by (N-1)*(N-2) for directed graphs
        normalization = (n - 1) * (n - 2)
        if normalization > 0:
            for v in vertices:
                cb[v] /= normalization

        # Clamp to [0, 1]
        for v in vertices:
            cb[v] = max(0.0, min(1.0, cb[v]))

        # Build GraphPostingList sorted by doc_id
        all_vids = frozenset(vertices)
        all_eids = frozenset(graph._edges.keys())
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for vid in sorted(vertices):
            entry = PostingEntry(vid, Payload(score=cb[vid]))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=all_vids,
                subgraph_edges=all_eids,
            )

        return GraphPostingList(entries, graph_payloads)

    def cost_estimate(self, stats: IndexStats) -> float:
        return stats.total_docs**2 * 0.5


def _min_max_normalize(
    scores: dict[int, float], vertices: list[int]
) -> dict[int, float]:
    """Min-max normalize scores to [0, 1]."""
    min_s = min(scores.values())
    max_s = max(scores.values())
    if max_s - min_s > 0:
        return {v: (scores[v] - min_s) / (max_s - min_s) for v in vertices}
    # All scores equal: return 1.0 if there are values, else 0.0
    return dict.fromkeys(vertices, 1.0)
