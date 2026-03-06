#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any

from uqa.core.hierarchical import HierarchicalDocument
from uqa.core.types import DocId, FieldName, PathExpr


class DocumentStore:
    """Storage for full documents (flat and hierarchical)."""

    def __init__(self) -> None:
        self._documents: dict[DocId, dict] = {}

    def put(self, doc_id: DocId, document: dict) -> None:
        self._documents[doc_id] = document

    def get(self, doc_id: DocId) -> dict | None:
        return self._documents.get(doc_id)

    def delete(self, doc_id: DocId) -> None:
        self._documents.pop(doc_id, None)

    def get_field(self, doc_id: DocId, field: FieldName) -> Any:
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        return doc.get(field)

    def eval_path(self, doc_id: DocId, path: PathExpr) -> Any:
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        hdoc = HierarchicalDocument(doc_id, doc)
        return hdoc.eval_path(path)

    @property
    def doc_ids(self) -> set[DocId]:
        return set(self._documents.keys())

    def __len__(self) -> int:
        return len(self._documents)
