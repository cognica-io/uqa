#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Scan operators: read rows from storage into batches.

``SeqScanOp`` performs a sequential scan over a SQL table, yielding all
rows in batches.  ``PostingListScanOp`` bridges the UQA posting-list
world with the physical execution engine by converting a
:class:`PostingList` (produced by text/vector/graph operators) into
batched row output with document data looked up from the store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from uqa.execution.batch import (
    Batch,
    DataType,
    DEFAULT_BATCH_SIZE,
    _SQL_TO_DTYPE,
)
from uqa.execution.physical import PhysicalOperator

if TYPE_CHECKING:
    from uqa.core.posting_list import PostingList
    from uqa.sql.table import Table
    from uqa.storage.document_store import DocumentStore


class SeqScanOp(PhysicalOperator):
    """Sequential scan: reads all rows from a table in batches."""

    def __init__(
        self, table: Table, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> None:
        self._table = table
        self._batch_size = batch_size
        self._iterator: Iterator[tuple[int, dict[str, Any]]] | None = None
        self._schema: dict[str, DataType] = {}

    def open(self) -> None:
        self._schema = {
            "_doc_id": DataType.INTEGER,
        }
        for name, col in self._table.columns.items():
            self._schema[name] = _SQL_TO_DTYPE.get(
                col.type_name, DataType.TEXT
            )
        store = self._table.document_store
        doc_ids = sorted(store.doc_ids)
        self._iterator = self._yield_rows(store, doc_ids)

    @staticmethod
    def _yield_rows(
        store: Any, doc_ids: list[int]
    ) -> Iterator[tuple[int, dict[str, Any]]]:
        for doc_id in doc_ids:
            data = store.get(doc_id)
            if data is not None:
                yield doc_id, data

    def next(self) -> Batch | None:
        if self._iterator is None:
            return None
        rows: list[dict[str, Any]] = []
        for _ in range(self._batch_size):
            try:
                doc_id, data = next(self._iterator)
                row: dict[str, Any] = {"_doc_id": doc_id}
                row.update(data)
                rows.append(row)
            except StopIteration:
                break
        if not rows:
            return None
        return Batch.from_rows(rows, self._schema)

    def close(self) -> None:
        self._iterator = None


class PostingListScanOp(PhysicalOperator):
    """Bridge from PostingList to batched row output.

    Looks up document data from the document store for each posting
    entry.  Includes ``_doc_id`` and ``_score`` columns.
    """

    def __init__(
        self,
        posting_list: PostingList,
        document_store: DocumentStore | None,
        schema: dict[str, DataType] | None = None,
        graph_store: Any = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._pl = posting_list
        self._doc_store = document_store
        self._graph_store = graph_store
        self._schema = schema
        self._batch_size = batch_size
        self._offset = 0

    def open(self) -> None:
        self._offset = 0

    def next(self) -> Batch | None:
        entries = self._pl.entries
        if self._offset >= len(entries):
            return None

        end = min(self._offset + self._batch_size, len(entries))
        batch_entries = entries[self._offset : end]
        self._offset = end

        rows: list[dict[str, Any]] = []
        for entry in batch_entries:
            # GeneralizedPostingEntry (from joins) has doc_ids tuple,
            # PostingEntry has doc_id scalar.
            doc_id = (
                entry.doc_ids[0]
                if hasattr(entry, "doc_ids")
                else entry.doc_id
            )
            row: dict[str, Any] = {
                "_doc_id": doc_id,
                "_score": entry.payload.score,
            }
            # For join entries, fields are pre-populated in payload.
            # Skip document store lookup if fields are already present.
            if entry.payload.fields:
                row.update(entry.payload.fields)
            else:
                doc = self._doc_store.get(doc_id) if self._doc_store is not None else None
                if doc is not None:
                    row.update(doc)
                elif self._graph_store is not None:
                    vertex = self._graph_store.get_vertex(doc_id)
                    if vertex is not None:
                        row.update(vertex.properties)
            rows.append(row)

        if not rows:
            return None

        schema: dict[str, DataType] = {
            "_doc_id": DataType.INTEGER,
            "_score": DataType.FLOAT,
        }
        if self._schema:
            schema.update(self._schema)
        return Batch.from_rows(rows, schema)

    def close(self) -> None:
        self._offset = 0
