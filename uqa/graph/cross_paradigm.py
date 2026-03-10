#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import numpy as np

from uqa.core.posting_list import PostingList
from uqa.core.types import Edge, Payload, PostingEntry, Vertex
from uqa.graph.operators import PatternMatchOperator, TraverseOperator
from uqa.graph.pattern import GraphPattern
from uqa.graph.posting_list import GraphPayload, GraphPostingList
from uqa.graph.store import GraphStore

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
            graph.add_vertex(Vertex(vid, "", props))

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


class VertexEmbeddingOperator:
    """Definition 3.2.1 (Paper 2): Map vertex properties to vector embeddings.

    Extracts the vector stored in a vertex property field and produces a
    posting list scored by cosine similarity to the query vector.
    """

    def __init__(
        self,
        query_vector: np.ndarray,
        vector_field: str = "embedding",
        threshold: float = 0.0,
    ) -> None:
        self.query_vector = query_vector
        self.vector_field = vector_field
        self.threshold = threshold

    def execute(self, ctx: object) -> PostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        entries: list[PostingEntry] = []
        for vid, vertex in graph._vertices.items():
            vec = vertex.properties.get(self.vector_field)
            if vec is None:
                continue
            arr = np.asarray(vec, dtype=np.float64)
            sim = self._cosine_similarity(self.query_vector, arr)
            if sim >= self.threshold:
                entries.append(PostingEntry(vid, Payload(score=float(sim))))
        entries.sort(key=lambda e: e.doc_id)
        return PostingList(entries)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


class VectorEnhancedMatchOperator:
    """Definition 3.2.3 (Paper 2): Pattern match + vector similarity.

    Performs subgraph pattern matching, then re-scores each match by
    vector similarity between a specified vertex variable and the query
    vector. Only matches above the threshold are retained.
    """

    def __init__(
        self,
        pattern: GraphPattern,
        query_vector: np.ndarray,
        score_variable: str,
        vector_field: str = "embedding",
        threshold: float = 0.0,
    ) -> None:
        self.pattern = pattern
        self.query_vector = query_vector
        self.score_variable = score_variable
        self.vector_field = vector_field
        self.threshold = threshold

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        match_op = PatternMatchOperator(self.pattern)
        match_result = match_op.execute(ctx)

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for entry in match_result:
            vid = entry.payload.fields.get(self.score_variable)
            if vid is None:
                continue
            vertex = graph.get_vertex(vid)
            if vertex is None:
                continue
            vec = vertex.properties.get(self.vector_field)
            if vec is None:
                continue
            arr = np.asarray(vec, dtype=np.float64)
            sim = self._cosine_similarity(self.query_vector, arr)
            if sim >= self.threshold:
                new_entry = PostingEntry(
                    entry.doc_id,
                    Payload(score=float(sim), fields=entry.payload.fields),
                )
                entries.append(new_entry)
                gp = match_result.get_graph_payload(entry.doc_id)
                if gp is not None:
                    graph_payloads[entry.doc_id] = GraphPayload(
                        subgraph_vertices=gp.subgraph_vertices,
                        subgraph_edges=gp.subgraph_edges,
                        score=float(sim),
                    )

        return GraphPostingList(entries, graph_payloads)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


class TextToGraphOperator:
    """Definition 3.3.1 (Paper 2): Build a co-occurrence graph from text.

    Tokenizes the text field of each document and creates a graph where:
    - Each unique token is a vertex.
    - An edge connects two tokens that co-occur within the same document,
      weighted by the number of co-occurrences.
    """

    def __init__(
        self,
        source: Any,
        text_field: str = "text",
        window_size: int = 0,
    ) -> None:
        self.source = source
        self.text_field = text_field
        self.window_size = window_size

    def execute(self, ctx: object) -> GraphStore:
        documents: list[dict[str, Any]]
        if hasattr(self.source, "execute"):
            result = self.source.execute(ctx)
            documents = self._posting_list_to_docs(result, ctx)
        else:
            documents = self.source

        token_set: set[str] = set()
        cooccurrences: dict[tuple[str, str], int] = defaultdict(int)

        for doc in documents:
            text = doc.get(self.text_field, "")
            from uqa.analysis.analyzer import DEFAULT_ANALYZER
            tokens = DEFAULT_ANALYZER.analyze(str(text))
            token_set.update(tokens)

            if self.window_size <= 0:
                unique_tokens = sorted(set(tokens))
                for i, t1 in enumerate(unique_tokens):
                    for t2 in unique_tokens[i + 1 :]:
                        pair = (t1, t2)
                        cooccurrences[pair] += 1
            else:
                for i, t1 in enumerate(tokens):
                    end = min(i + self.window_size + 1, len(tokens))
                    for j in range(i + 1, end):
                        t2 = tokens[j]
                        if t1 != t2:
                            pair = (min(t1, t2), max(t1, t2))
                            cooccurrences[pair] += 1

        graph = GraphStore()
        token_to_id: dict[str, int] = {}
        for vid, token in enumerate(sorted(token_set), start=1):
            token_to_id[token] = vid
            graph.add_vertex(Vertex(vid, "", {"token": token}))

        edge_id = 1
        for (t1, t2), weight in cooccurrences.items():
            src = token_to_id[t1]
            tgt = token_to_id[t2]
            edge = Edge(edge_id, src, tgt, "co_occurs", {"weight": weight})
            graph.add_edge(edge)
            edge_id += 1

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
