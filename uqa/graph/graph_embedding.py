#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.graph.store import GraphStore


class GraphEmbeddingOperator:
    """Structure-based graph embeddings (Paper 2 + Paper 4).

    Computes per-vertex embeddings from structural features:
    - Degree (in/out)
    - Label distribution of neighbors
    - K-hop connectivity statistics

    Embeddings are stored in the payload fields for downstream use
    (e.g., vector similarity search).
    """

    def __init__(
        self,
        dimensions: int = 32,
        k_layers: int = 2,
        *,
        graph: str,
    ) -> None:
        self.dimensions = dimensions
        self.k_layers = k_layers
        self.graph_name = graph

    def execute(self, ctx: object) -> GraphPostingList:
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        g = self.graph_name
        vertices = sorted(gs.vertex_ids_in_graph(g))

        if not vertices:
            return GraphPostingList()

        # Collect all edge labels for one-hot encoding
        all_labels: set[str] = set()
        for vid in vertices:
            for eid in gs.out_edge_ids(vid, graph=g):
                edge = gs.get_edge(eid)
                if edge is not None:
                    all_labels.add(edge.label)
        sorted_labels = sorted(all_labels)
        label_to_idx: dict[str, int] = {l: i for i, l in enumerate(sorted_labels)}
        n_labels = len(sorted_labels)

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}

        for vid in vertices:
            embedding = self._compute_embedding(gs, g, vid, label_to_idx, n_labels)
            entries.append(
                PostingEntry(
                    vid,
                    Payload(
                        score=0.0,
                        fields={"_embedding": embedding},
                    ),
                )
            )
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozenset({vid}),
                subgraph_edges=frozenset(),
            )

        return GraphPostingList(entries, graph_payloads)

    def _compute_embedding(
        self,
        gs: GraphStore,
        g: str,
        vid: int,
        label_to_idx: dict[str, int],
        n_labels: int,
    ) -> list[float]:
        """Compute structural embedding for a vertex."""
        # Feature 1: degree features (2 dims)
        out_degree = len(gs.out_edge_ids(vid, graph=g))
        in_degree = len(gs.in_edge_ids(vid, graph=g))

        # Feature 2: label distribution (n_labels dims, capped at dims/2)
        label_dims = min(n_labels, self.dimensions // 2)
        label_dist = [0.0] * label_dims
        for eid in gs.out_edge_ids(vid, graph=g):
            edge = gs.get_edge(eid)
            if edge is None:
                continue
            idx = label_to_idx.get(edge.label, -1)
            if 0 <= idx < label_dims:
                label_dist[idx] += 1.0
        # Normalize
        total = sum(label_dist)
        if total > 0:
            label_dist = [x / total for x in label_dist]

        # Feature 3: k-hop connectivity (k_layers dims)
        hop_counts: list[float] = []
        visited: set[int] = {vid}
        frontier: set[int] = {vid}
        for _ in range(self.k_layers):
            next_frontier: set[int] = set()
            for v in frontier:
                for eid in gs.out_edge_ids(v, graph=g):
                    edge = gs.get_edge(eid)
                    if edge is None:
                        continue
                    neighbor = edge.target_id
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                        visited.add(neighbor)
            hop_counts.append(float(len(next_frontier)))
            frontier = next_frontier

        # Assemble embedding vector
        raw = [float(out_degree), float(in_degree), *label_dist, *hop_counts]

        # Pad or truncate to target dimensions
        if len(raw) < self.dimensions:
            raw.extend([0.0] * (self.dimensions - len(raw)))
        else:
            raw = raw[: self.dimensions]

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in raw))
        if norm > 0:
            raw = [x / norm for x in raw]

        return raw

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs) * self.k_layers * 2
