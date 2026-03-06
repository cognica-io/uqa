from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from uqa.api.query_builder import QueryBuilder
from uqa.core.types import DocId, Edge, Vertex
from uqa.storage.document_store import DocumentStore
from uqa.storage.inverted_index import InvertedIndex
from uqa.storage.vector_index import HNSWIndex
from uqa.graph.store import GraphStore
from uqa.storage.block_max_index import BlockMaxIndex


class Engine:
    """Main engine: initializes all storage and provides query interface."""

    def __init__(
        self,
        vector_dimensions: int = 64,
        max_elements: int = 10000,
    ):
        self.document_store = DocumentStore()
        self.inverted_index = InvertedIndex()
        self.vector_index = HNSWIndex(
            dimensions=vector_dimensions,
            max_elements=max_elements,
        )
        self.graph_store = GraphStore()
        self.block_max_index = BlockMaxIndex()
        self._vector_dimensions = vector_dimensions

    def add_document(
        self,
        doc_id: DocId,
        document: dict[str, Any],
        embedding: NDArray | None = None,
    ) -> None:
        """Add a document to all relevant indexes."""
        self.document_store.put(doc_id, document)

        text_fields = {
            k: v for k, v in document.items() if isinstance(v, str)
        }
        if text_fields:
            self.inverted_index.add_document(doc_id, text_fields)

        if embedding is not None:
            self.vector_index.add(doc_id, embedding)

    def add_graph_vertex(self, vertex: Vertex) -> None:
        self.graph_store.add_vertex(vertex)

    def add_graph_edge(self, edge: Edge) -> None:
        self.graph_store.add_edge(edge)

    def query(self) -> QueryBuilder:
        return QueryBuilder(self)

    def _build_context(self) -> Any:
        from uqa.operators.base import ExecutionContext

        return ExecutionContext(
            document_store=self.document_store,
            inverted_index=self.inverted_index,
            vector_index=self.vector_index,
            graph_store=self.graph_store,
            block_max_index=self.block_max_index,
        )
