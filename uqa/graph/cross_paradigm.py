from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from uqa.core.types import Payload, PostingEntry
from uqa.graph.operators import TraverseOperator
from uqa.graph.posting_list import GraphPayload, GraphPostingList
from uqa.graph.store import GraphStore
from uqa.core.types import Edge, Vertex

if TYPE_CHECKING:
    pass


class ToGraphOperator:
    """Definition 3.1.1: Convert documents to graph vertices + edges.

    Each document becomes a vertex. Edges are created based on
    the edge_field, which should contain a list of target doc_ids.
    """

    def __init__(
        self,
        source: Any,
        id_field: str = "doc_id",
        edge_field: str = "links",
    ) -> None:
        self.source = source
        self.id_field = id_field
        self.edge_field = edge_field

    def execute(self, ctx: object) -> GraphStore:
        graph = GraphStore()
        documents: list[dict[str, Any]]
        if hasattr(self.source, "execute"):
            result = self.source.execute(ctx)
            documents = self._posting_list_to_docs(result, ctx)
        else:
            documents = self.source

        edge_counter = 1
        for doc in documents:
            vid = doc.get(self.id_field, 0)
            props = {k: v for k, v in doc.items() if k != self.id_field}
            graph.add_vertex(Vertex(vid, props))

        for doc in documents:
            vid = doc.get(self.id_field, 0)
            targets = doc.get(self.edge_field, [])
            if isinstance(targets, list):
                for target_id in targets:
                    edge = Edge(edge_counter, vid, target_id, "link")
                    graph.add_edge(edge)
                    edge_counter += 1

        return graph

    @staticmethod
    def _posting_list_to_docs(
        pl: Any, ctx: object
    ) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for entry in pl:
            doc: dict[str, Any] = {"doc_id": entry.doc_id}
            doc.update(entry.payload.fields)
            docs.append(doc)
        return docs


class FromGraphOperator:
    """Definition 3.1.2: Convert graph posting list to standard posting list."""

    def __init__(self, source_op: Any) -> None:
        self.source_op = source_op

    def execute(self, ctx: object) -> Any:
        gpl: GraphPostingList = self.source_op.execute(ctx)
        return gpl.to_posting_list()


class SemanticGraphSearchOperator:
    """Definition 3.3.2: Traverse + vector similarity filter.

    Performs graph traversal then filters results by cosine similarity
    to a query vector, using vertex properties.
    """

    def __init__(
        self,
        start_vertex: int,
        label: str | None,
        max_hops: int,
        query_vector: np.ndarray,
        vector_field: str = "embedding",
        threshold: float = 0.5,
    ) -> None:
        self.start_vertex = start_vertex
        self.label = label
        self.max_hops = max_hops
        self.query_vector = query_vector
        self.vector_field = vector_field
        self.threshold = threshold

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        # First traverse
        traverse = TraverseOperator(self.start_vertex, self.label, self.max_hops)
        gpl = traverse.execute(ctx)

        # Filter by vector similarity
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for entry in gpl:
            vertex = graph.get_vertex(entry.doc_id)
            if vertex is None:
                continue
            vec = vertex.properties.get(self.vector_field)
            if vec is None:
                continue
            sim = self._cosine_similarity(self.query_vector, np.asarray(vec))
            if sim >= self.threshold:
                new_entry = PostingEntry(
                    entry.doc_id, Payload(score=float(sim))
                )
                entries.append(new_entry)
                gp = gpl.get_graph_payload(entry.doc_id)
                if gp is not None:
                    graph_payloads[entry.doc_id] = GraphPayload(
                        subgraph_vertices=gp.subgraph_vertices,
                        subgraph_edges=gp.subgraph_edges,
                        score=float(sim),
                    )

        return GraphPostingList(entries, graph_payloads)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
