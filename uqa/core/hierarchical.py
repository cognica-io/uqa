#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any

from uqa.core.types import DocId, PathExpr, Payload, PostingEntry
from uqa.core.posting_list import PostingList


class HierarchicalDocument:
    """Recursive document structure (Definition 5.2.1, Paper 1)."""

    def __init__(self, doc_id: DocId, data: dict | list | Any):
        self.doc_id = doc_id
        self.data = data

    def eval_path(self, path: PathExpr) -> Any:
        """Path evaluation (Definition 5.2.3)."""
        current = self.data
        for component in path:
            if isinstance(current, dict) and isinstance(component, str):
                current = current.get(component)
            elif isinstance(current, list) and isinstance(component, int):
                current = current[component] if component < len(current) else None
            else:
                return None
            if current is None:
                return None
        return current


def project_paths(
    doc: HierarchicalDocument, paths: list[PathExpr]
) -> dict[str, Any]:
    """Project a document to a subset of paths (Definition 5.3.2)."""
    result: dict[str, Any] = {}
    for path in paths:
        key = ".".join(str(c) for c in path)
        result[key] = doc.eval_path(path)
    return result


def unnest_array(
    doc: HierarchicalDocument, path: PathExpr
) -> list[HierarchicalDocument]:
    """Unnest an array at a path into separate documents (Definition 5.3.4)."""
    arr = doc.eval_path(path)
    if not isinstance(arr, list):
        return []
    result: list[HierarchicalDocument] = []
    for i, item in enumerate(arr):
        nested = dict(doc.data) if isinstance(doc.data, dict) else {}
        path_key = ".".join(str(c) for c in path)
        nested[path_key + "._unnested"] = item
        nested["_unnest_index"] = i
        result.append(HierarchicalDocument(doc.doc_id, nested))
    return result
