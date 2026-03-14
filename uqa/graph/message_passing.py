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


class MessagePassingOperator:
    """K-layer message-passing aggregation (Paper 2 + Paper 4).

    Performs k rounds of neighbor feature aggregation over graph vertices.
    Each vertex accumulates its neighbors' property values, then the
    aggregated features are calibrated via sigmoid to produce probabilities.
    """

    def __init__(
        self,
        k_layers: int = 2,
        aggregation: str = "mean",
        property_name: str | None = None,
    ) -> None:
        self.k_layers = k_layers
        self.aggregation = aggregation
        self.property_name = property_name

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]

        if not graph._vertices:
            return GraphPostingList()

        # Initialize features from vertex properties
        features: dict[int, float] = {}
        for vid, vertex in graph._vertices.items():
            if self.property_name is not None:
                val = vertex.properties.get(self.property_name, 0.0)
                features[vid] = float(val) if isinstance(val, (int, float)) else 0.0
            else:
                features[vid] = 1.0

        # K rounds of message passing
        for _ in range(self.k_layers):
            new_features: dict[int, float] = {}
            for vid in graph._vertices:
                neighbor_values: list[float] = []
                for eid in graph._adj_out.get(vid, set()):
                    edge = graph._edges[eid]
                    neighbor_values.append(features.get(edge.target_id, 0.0))
                for eid in graph._adj_in.get(vid, set()):
                    edge = graph._edges[eid]
                    neighbor_values.append(features.get(edge.source_id, 0.0))

                if not neighbor_values:
                    new_features[vid] = features[vid]
                    continue

                if self.aggregation == "mean":
                    agg = sum(neighbor_values) / len(neighbor_values)
                elif self.aggregation == "sum":
                    agg = sum(neighbor_values)
                elif self.aggregation == "max":
                    agg = max(neighbor_values)
                else:
                    agg = sum(neighbor_values) / len(neighbor_values)

                # Combine with self-feature (residual connection)
                new_features[vid] = features[vid] + agg

            features = new_features

        # Calibrate via sigmoid
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for vid in sorted(graph._vertices):
            score = 1.0 / (1.0 + math.exp(-features[vid]))
            entries.append(PostingEntry(vid, Payload(score=score)))
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozenset({vid}),
                subgraph_edges=frozenset(),
            )

        return GraphPostingList(entries, graph_payloads)

    def cost_estimate(self, stats: IndexStats) -> float:
        return float(stats.total_docs) * self.k_layers
