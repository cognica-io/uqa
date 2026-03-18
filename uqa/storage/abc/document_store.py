#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for document stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from uqa.core.types import DocId, FieldName, PathExpr


class DocumentStore(ABC):
    """Abstract interface for document storage backends.

    A document store maps ``DocId`` keys to ``dict`` values and supports
    field-level access, bulk retrieval, and hierarchical path evaluation.
    Concrete implementations include in-memory and SQLite-backed stores.
    """

    @abstractmethod
    def put(self, doc_id: DocId, document: dict) -> None:
        """Insert or replace a document keyed by *doc_id*."""

    @abstractmethod
    def get(self, doc_id: DocId) -> dict | None:
        """Return the document as a dict, or ``None`` if absent."""

    @abstractmethod
    def delete(self, doc_id: DocId) -> None:
        """Delete a document. No error if *doc_id* does not exist."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all documents."""

    @abstractmethod
    def get_field(self, doc_id: DocId, field: FieldName) -> Any:
        """Return a single field value, or ``None`` if absent."""

    @abstractmethod
    def get_fields_bulk(
        self, doc_ids: list[DocId], field: FieldName
    ) -> dict[DocId, Any]:
        """Return field values for multiple doc_ids in a single call."""

    @abstractmethod
    def has_value(self, field: FieldName, value: Any) -> bool:
        """Return True if any document has ``field == value``."""

    @abstractmethod
    def eval_path(self, doc_id: DocId, path: PathExpr) -> Any:
        """Evaluate a hierarchical path expression against a document."""

    @property
    @abstractmethod
    def doc_ids(self) -> set[DocId]:
        """Return the set of all stored document IDs."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of stored documents."""

    def iter_all(self) -> Iterator[tuple[int, dict]]:
        """Yield all ``(doc_id, document)`` pairs in ID order.

        The default implementation fetches each document individually.
        SQLite-backed stores override this with a single query.
        """
        for doc_id in sorted(self.doc_ids):
            doc = self.get(doc_id)
            if doc is not None:
                yield doc_id, doc
