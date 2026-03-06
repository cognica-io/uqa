from __future__ import annotations

from typing import Any

from uqa.core.hierarchical import HierarchicalDocument, project_paths, unnest_array
from uqa.core.posting_list import PostingList
from uqa.core.types import PathExpr, Payload, PostingEntry, Predicate
from uqa.operators.base import ExecutionContext, Operator


class PathFilterOperator(Operator):
    """Definition 5.3.1: Filter documents by path expression and predicate."""

    def __init__(
        self,
        path: PathExpr,
        predicate: Predicate,
        source: Operator | None = None,
    ) -> None:
        self.path = path
        self.predicate = predicate
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        if self.source is not None:
            source_pl = self.source.execute(context)
            doc_ids = [entry.doc_id for entry in source_pl]
        else:
            doc_ids = sorted(doc_store.doc_ids)

        entries: list[PostingEntry] = []
        for doc_id in doc_ids:
            value = doc_store.eval_path(doc_id, self.path)
            if value is not None and self.predicate.evaluate(value):
                entries.append(PostingEntry(doc_id, Payload(score=0.0)))
        return PostingList(entries)


class PathProjectOperator(Operator):
    """Definition 5.3.2: Project documents to a set of path expressions."""

    def __init__(self, paths: list[PathExpr], source: Operator) -> None:
        self.paths = paths
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        doc_store = context.document_store
        if doc_store is None:
            return source_pl

        entries: list[PostingEntry] = []
        for entry in source_pl:
            doc_data = doc_store.get(entry.doc_id)
            if doc_data is None:
                continue
            hdoc = HierarchicalDocument(entry.doc_id, doc_data)
            projected = project_paths(hdoc, self.paths)
            entries.append(PostingEntry(
                entry.doc_id,
                Payload(
                    positions=entry.payload.positions,
                    score=entry.payload.score,
                    fields=projected,
                ),
            ))
        return PostingList(entries)


class PathUnnestOperator(Operator):
    """Definition 5.3.4: Unnest an array at a given path."""

    def __init__(self, path: PathExpr, source: Operator) -> None:
        self.path = path
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        doc_store = context.document_store
        if doc_store is None:
            return source_pl

        entries: list[PostingEntry] = []
        for entry in source_pl:
            doc_data = doc_store.get(entry.doc_id)
            if doc_data is None:
                continue
            hdoc = HierarchicalDocument(entry.doc_id, doc_data)
            unnested = unnest_array(hdoc, self.path)
            for unnested_doc in unnested:
                fields = dict(entry.payload.fields)
                fields["_unnested_data"] = unnested_doc.data
                entries.append(PostingEntry(
                    entry.doc_id,
                    Payload(
                        positions=entry.payload.positions,
                        score=entry.payload.score,
                        fields=fields,
                    ),
                ))
        return PostingList(entries)
