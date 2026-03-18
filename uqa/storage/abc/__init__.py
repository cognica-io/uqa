#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base classes for storage backends."""

from uqa.storage.abc.document_store import DocumentStore
from uqa.storage.abc.graph_store import GraphStore
from uqa.storage.abc.inverted_index import IndexedTerms, InvertedIndex

__all__ = [
    "DocumentStore",
    "GraphStore",
    "IndexedTerms",
    "InvertedIndex",
]
