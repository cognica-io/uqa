#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for vector indexes.

Defines the interface that all vector index implementations (IVF, etc.)
must satisfy.  Operators (KNNOperator, VectorSimilarityOperator) depend
only on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.core.posting_list import PostingList
    from uqa.core.types import DocId


class VectorIndex(ABC):
    """Abstract base for vector search indexes.

    Implementations must support add, delete, clear, KNN search,
    threshold search, and a vector count.
    """

    dimensions: int

    @abstractmethod
    def add(self, doc_id: DocId, vector: NDArray) -> None:
        """Insert a vector for the given document."""
        ...

    @abstractmethod
    def delete(self, doc_id: DocId) -> None:
        """Remove a vector by document ID."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all vectors from the index."""
        ...

    @abstractmethod
    def search_knn(self, query: NDArray, k: int) -> PostingList:
        """KNN_k operator (Definition 3.1.3)."""
        ...

    @abstractmethod
    def search_threshold(self, query: NDArray, threshold: float) -> PostingList:
        """V_theta operator (Definition 3.1.2)."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the number of live vectors in the index."""
        ...
