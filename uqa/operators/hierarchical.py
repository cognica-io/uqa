#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.hierarchical import HierarchicalDocument, project_paths, unnest_array
from uqa.core.posting_list import PostingList
from uqa.core.types import PathExpr, Payload, PostingEntry, Predicate
from uqa.operators.base import ExecutionContext, Operator

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.aggregation import AggregationMonoid


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
            if value is None:
                continue
            if isinstance(value, list):
                if any(self.predicate.evaluate(v) for v in value if v is not None):
                    entries.append(PostingEntry(doc_id, Payload(score=0.0)))
            elif self.predicate.evaluate(value):
                entries.append(PostingEntry(doc_id, Payload(score=0.0)))
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        base = (
            self.source.cost_estimate(stats)
            if self.source is not None
            else float(stats.total_docs)
        )
        return base  # linear scan over source docs


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
            entries.append(
                PostingEntry(
                    entry.doc_id,
                    Payload(
                        positions=entry.payload.positions,
                        score=entry.payload.score,
                        fields=projected,
                    ),
                )
            )
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.source.cost_estimate(stats)


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
                entries.append(
                    PostingEntry(
                        entry.doc_id,
                        Payload(
                            positions=entry.payload.positions,
                            score=entry.payload.score,
                            fields=fields,
                        ),
                    )
                )
        return PostingList(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        return self.source.cost_estimate(stats) * 2.0


class PathAggregateOperator(Operator):
    """Definition 5.3.3: PA(path, M) -- aggregate nested array values.

    Applies an aggregation monoid M to the array of values at a nested
    path within each document.  For example, PA("orders.amount", SumMonoid)
    sums all ``amount`` values across nested ``orders`` arrays.

    The result is a posting list where each document's score is the
    aggregated value and the raw result is stored in payload fields.
    """

    def __init__(
        self,
        path: PathExpr,
        monoid: AggregationMonoid,
        source: Operator | None = None,
    ) -> None:
        self.path = path
        self.monoid = monoid
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        if self.source is not None:
            source_pl = self.source.execute(context)
            candidate_ids = [entry.doc_id for entry in source_pl]
        else:
            candidate_ids = sorted(doc_store.doc_ids)

        entries: list[PostingEntry] = []
        for doc_id in candidate_ids:
            doc_data = doc_store.get(doc_id)
            if doc_data is None:
                continue
            hdoc = HierarchicalDocument(doc_id, doc_data)
            values = hdoc.eval_path(self.path)

            state = self.monoid.identity()
            if isinstance(values, list):
                for v in values:
                    if v is not None:
                        state = self.monoid.accumulate(state, v)
            elif values is not None:
                state = self.monoid.accumulate(state, values)

            result = self.monoid.finalize(state)
            path_key = ".".join(str(c) for c in self.path)
            score = float(result) if isinstance(result, int | float) else 0.0
            entries.append(
                PostingEntry(
                    doc_id,
                    Payload(
                        score=score,
                        fields={
                            "_path_aggregate_path": path_key,
                            "_path_aggregate": result,
                        },
                    ),
                )
            )
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats: IndexStats) -> float:
        base = (
            self.source.cost_estimate(stats)
            if self.source is not None
            else float(stats.total_docs)
        )
        return base


class UnifiedFilterOperator(Operator):
    """Definition 5.3.5: Unified filter dispatching flat vs hierarchical.

    Automatically detects whether the field expression is a flat field
    name (e.g. "year") or a hierarchical path (e.g. "metadata.author")
    and dispatches to FilterOperator or PathFilterOperator accordingly.
    """

    def __init__(
        self,
        field_expr: str,
        predicate: Predicate,
        source: Operator | None = None,
    ) -> None:
        self.field_expr = field_expr
        self.predicate = predicate
        self.source = source

    def execute(self, context: ExecutionContext) -> PostingList:
        if "." in self.field_expr:
            path: PathExpr = []
            for component in self.field_expr.split("."):
                if component.isdigit():
                    path.append(int(component))
                else:
                    path.append(component)
            delegate = PathFilterOperator(path, self.predicate, self.source)
        else:
            from uqa.operators.primitive import FilterOperator

            delegate = FilterOperator(self.field_expr, self.predicate, self.source)
        return delegate.execute(context)

    def cost_estimate(self, stats: IndexStats) -> float:
        base = (
            self.source.cost_estimate(stats)
            if self.source is not None
            else float(stats.total_docs)
        )
        return base
