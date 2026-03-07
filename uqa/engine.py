#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from uqa.api.query_builder import QueryBuilder
from uqa.core.types import DocId, Edge, Payload, PostingEntry, Vertex
from uqa.storage.catalog import Catalog
from uqa.storage.document_store import DocumentStore
from uqa.storage.inverted_index import InvertedIndex
from uqa.storage.vector_index import HNSWIndex
from uqa.graph.store import GraphStore
from uqa.storage.block_max_index import BlockMaxIndex
from uqa.storage.index_manager import IndexManager
from uqa.storage.sqlite_graph_store import SQLiteGraphStore
from uqa.storage.sqlite_vector_index import SQLiteVectorIndex
from uqa.storage.transaction import Transaction
from uqa.sql.table import ColumnDef, ColumnStats, Table, _SQL_TYPE_MAP


class Engine:
    """Main engine: initializes all storage and provides query interface.

    When ``db_path`` is provided the engine persists every mutation to a
    SQLite database (write-through) and restores state on next startup.
    When ``db_path`` is ``None`` the engine is purely in-memory.
    """

    def __init__(
        self,
        db_path: str | None = None,
        vector_dimensions: int = 64,
        max_elements: int = 10000,
    ):
        self.document_store = DocumentStore()
        self.inverted_index = InvertedIndex()
        self.vector_index: HNSWIndex = HNSWIndex(
            dimensions=vector_dimensions,
            max_elements=max_elements,
        )
        self.graph_store: GraphStore = GraphStore()
        self.block_max_index = BlockMaxIndex()
        self._vector_dimensions = vector_dimensions
        self._max_elements = max_elements
        self._tables: dict[str, Any] = {}

        # Persistence and transactions
        self._catalog: Catalog | None = None
        self._index_manager: IndexManager | None = None
        self._transaction: Transaction | None = None
        if db_path is not None:
            self._catalog = Catalog(db_path)
            self._index_manager = IndexManager(
                self._catalog.conn, self._catalog
            )
            self.vector_index = SQLiteVectorIndex(
                self._catalog.conn,
                dimensions=vector_dimensions,
                max_elements=max_elements,
            )
            self.graph_store = SQLiteGraphStore(self._catalog.conn)
            self._catalog.set_metadata(
                "vector_dimensions", str(vector_dimensions)
            )
            self._catalog.set_metadata("max_elements", str(max_elements))
            self._load_from_catalog()

    # -- Catalog restore -----------------------------------------------

    def _load_from_catalog(self) -> None:
        """Rebuild all in-memory state from the SQLite catalog."""
        catalog = self._catalog
        assert catalog is not None

        # -- SQL tables ------------------------------------------------
        # Tables use SQLite-backed stores (SQLiteDocumentStore /
        # SQLiteInvertedIndex) that share the catalog connection.
        # Documents and postings are already in per-table SQLite tables,
        # so no manual restore is needed.
        for name, col_dicts in catalog.load_table_schemas():
            columns = [
                ColumnDef(
                    name=cd["name"],
                    type_name=cd["type_name"],
                    python_type=_SQL_TYPE_MAP[cd["type_name"]],
                    primary_key=cd["primary_key"],
                    not_null=cd["not_null"],
                    auto_increment=cd["auto_increment"],
                    default=cd["default"],
                )
                for cd in col_dicts
            ]
            table = Table(name, columns, conn=catalog.conn)

            # Migrate old-format databases: if documents exist in the
            # shared _documents table but not in per-table SQLite tables,
            # copy them over.
            self._migrate_old_format_table(catalog, name, table)

            # Restore _next_id from SQLite
            max_id = table.document_store.max_doc_id()
            if max_id > 0:
                table._next_id = max_id + 1

            # Restore column statistics
            for col_name, dc, nc, mn, mx, rc in catalog.load_column_stats(
                name
            ):
                table._stats[col_name] = ColumnStats(
                    distinct_count=dc,
                    null_count=nc,
                    min_value=mn,
                    max_value=mx,
                    row_count=rc,
                )

            self._tables[name] = table

        # -- Indexes ---------------------------------------------------
        if self._index_manager is not None:
            self._index_manager.load_from_catalog()

        # -- Global documents (programmatic API) -----------------------
        for doc_id, data in catalog.load_documents(""):
            self.document_store.put(doc_id, data)

        # Restore global inverted index
        if not self._restore_inverted_index(
            catalog, "", self.inverted_index
        ):
            self._migrate_inverted_index(
                catalog, "", self.document_store, self.inverted_index
            )

        # -- Vectors ---------------------------------------------------
        # SQLiteVectorIndex loads vectors from SQLite on construction.
        # Only load manually for plain HNSWIndex.
        if not isinstance(self.vector_index, SQLiteVectorIndex):
            for doc_id, embedding in catalog.load_vectors():
                self.vector_index.add(doc_id, embedding)

        # -- Graph -----------------------------------------------------
        # SQLiteGraphStore loads vertices and edges from SQLite on
        # construction.  Only load manually for plain GraphStore.
        if not isinstance(self.graph_store, SQLiteGraphStore):
            for vertex_id, props in catalog.load_vertices():
                self.graph_store.add_vertex(
                    Vertex(vertex_id=vertex_id, properties=props)
                )
            for eid, src, dst, label, props in catalog.load_edges():
                self.graph_store.add_edge(
                    Edge(
                        edge_id=eid,
                        source_id=src,
                        target_id=dst,
                        label=label,
                        properties=props,
                    )
                )

    @staticmethod
    def _migrate_old_format_table(
        catalog: Catalog, table_name: str, table: Any
    ) -> None:
        """Migrate old-format data into per-table SQLite tables.

        Old databases stored documents in the shared ``_documents`` table
        and postings in ``_postings``.  This method copies them into the
        new per-table SQLite tables (``_data_{name}``,
        ``_inverted_{name}_{field}``) and removes the old rows.
        """
        old_docs = catalog.load_documents(table_name)
        if not old_docs:
            return

        # Copy documents into SQLiteDocumentStore
        for doc_id, data in old_docs:
            coerced: dict[str, Any] = {}
            for col_name, col_def in table.columns.items():
                if col_name in data and data[col_name] is not None:
                    coerced[col_name] = col_def.python_type(data[col_name])
            table.document_store.put(doc_id, coerced)

        # Copy postings into SQLiteInvertedIndex
        old_postings = catalog.load_postings(table_name)
        for field, term, doc_id, positions in old_postings:
            entry = PostingEntry(
                doc_id, Payload(positions=positions, score=0.0)
            )
            table.inverted_index.add_posting(field, term, entry)

        # Copy doc lengths
        for doc_id, lengths in catalog.load_doc_lengths(table_name):
            table.inverted_index.set_doc_length(doc_id, lengths)
            for field, length in lengths.items():
                table.inverted_index.add_total_length(field, length)

        # Set doc count from number of unique docs with lengths
        doc_length_entries = catalog.load_doc_lengths(table_name)
        if doc_length_entries:
            table.inverted_index.set_doc_count(len(doc_length_entries))

        # Remove old-format rows
        catalog.conn.execute(
            "DELETE FROM _documents WHERE table_name = ?", (table_name,)
        )
        catalog.conn.execute(
            "DELETE FROM _postings WHERE table_name = ?", (table_name,)
        )
        catalog.conn.execute(
            "DELETE FROM _doc_lengths WHERE table_name = ?", (table_name,)
        )
        catalog.conn.commit()

    @staticmethod
    def _restore_inverted_index(
        catalog: Catalog,
        table_name: str,
        inverted_index: InvertedIndex,
    ) -> bool:
        """Restore an in-memory inverted index from persisted postings.

        Used only for the global (programmatic API) inverted index.
        Returns True if postings were found and restored, False otherwise.
        """
        postings = catalog.load_postings(table_name)
        if not postings:
            return False

        doc_lengths_list = catalog.load_doc_lengths(table_name)

        # Populate posting entries
        for field, term, doc_id, positions in postings:
            entry = PostingEntry(
                doc_id, Payload(positions=positions, score=0.0)
            )
            inverted_index.add_posting(field, term, entry)

        # Populate doc lengths and compute aggregate stats
        inverted_index.set_doc_count(len(doc_lengths_list))
        for doc_id, lengths in doc_lengths_list:
            inverted_index.set_doc_length(doc_id, lengths)
            for field, length in lengths.items():
                inverted_index.add_total_length(field, length)

        return True

    @staticmethod
    def _migrate_inverted_index(
        catalog: Catalog,
        table_name: str,
        document_store: DocumentStore,
        inverted_index: InvertedIndex,
    ) -> None:
        """Backward compat: re-tokenize global documents and persist postings.

        Called once when opening a database created before posting
        persistence was added.  Subsequent restarts use the fast path.
        """
        doc_ids = sorted(document_store.doc_ids)
        if not doc_ids:
            return

        catalog.begin()
        try:
            for doc_id in doc_ids:
                data = document_store.get(doc_id)
                if data is None:
                    continue
                text_fields = {
                    k: v for k, v in data.items() if isinstance(v, str)
                }
                if text_fields:
                    indexed = inverted_index.add_document(
                        doc_id, text_fields
                    )
                    catalog.save_postings(
                        table_name,
                        doc_id,
                        indexed.field_lengths,
                        indexed.postings,
                    )
            catalog.commit()
        except Exception:
            catalog.rollback()
            raise

    # -- Public API ----------------------------------------------------

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
        indexed = None
        if text_fields:
            indexed = self.inverted_index.add_document(doc_id, text_fields)

        if embedding is not None:
            self.vector_index.add(doc_id, embedding)

        if self._catalog is not None:
            self._catalog.begin()
            try:
                self._catalog.save_document("", doc_id, document)
                if indexed is not None:
                    self._catalog.save_postings(
                        "", doc_id,
                        indexed.field_lengths, indexed.postings,
                    )
                # SQLiteVectorIndex handles persistence via write-through.
                if embedding is not None and not isinstance(
                    self.vector_index, SQLiteVectorIndex
                ):
                    self._catalog.save_vector(doc_id, embedding)
                self._catalog.commit()
            except Exception:
                self._catalog.rollback()
                raise

    def delete_document(self, doc_id: DocId) -> None:
        """Remove a document from all in-memory indexes and catalog."""
        self.document_store.delete(doc_id)
        self.inverted_index.remove_document(doc_id)
        if isinstance(self.vector_index, SQLiteVectorIndex):
            self.vector_index.delete(doc_id)
        if self._catalog is not None:
            self._catalog.begin()
            try:
                self._catalog.delete_document("", doc_id)
                # SQLiteVectorIndex handles persistence via write-through.
                if not isinstance(self.vector_index, SQLiteVectorIndex):
                    self._catalog.delete_vector(doc_id)
                self._catalog.commit()
            except Exception:
                self._catalog.rollback()
                raise

    def add_graph_vertex(self, vertex: Vertex) -> None:
        self.graph_store.add_vertex(vertex)
        # SQLiteGraphStore handles persistence via write-through.
        if self._catalog is not None and not isinstance(
            self.graph_store, SQLiteGraphStore
        ):
            self._catalog.save_vertex(vertex.vertex_id, vertex.properties)

    def add_graph_edge(self, edge: Edge) -> None:
        self.graph_store.add_edge(edge)
        # SQLiteGraphStore handles persistence via write-through.
        if self._catalog is not None and not isinstance(
            self.graph_store, SQLiteGraphStore
        ):
            self._catalog.save_edge(
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.label,
                edge.properties,
            )

    # -- Scoring parameters (Papers 3-4) -------------------------------

    def save_scoring_params(
        self, name: str, params: dict[str, Any]
    ) -> None:
        """Persist Bayesian calibration parameters for a named signal.

        Parameters are stored as a JSON dict with keys such as:
        alpha, beta, base_rate (Paper 3), confidence_alpha (Paper 4).
        """
        if self._catalog is not None:
            self._catalog.save_scoring_params(name, params)

    def load_scoring_params(self, name: str) -> dict[str, Any] | None:
        """Load persisted calibration parameters for a named signal."""
        if self._catalog is not None:
            return self._catalog.load_scoring_params(name)
        return None

    def load_all_scoring_params(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all persisted scoring parameter sets."""
        if self._catalog is not None:
            return self._catalog.load_all_scoring_params()
        return []

    # -- Transaction interface -----------------------------------------

    def begin(self) -> Transaction:
        """Start an explicit transaction.

        Returns a :class:`Transaction` that must be committed or rolled
        back.  While a transaction is active, all writes are deferred
        until ``commit()``.  Can also be used as a context manager.

        Raises :class:`ValueError` for in-memory engines or if a
        transaction is already active.
        """
        if self._catalog is None:
            raise ValueError(
                "Transactions require a persistent engine (db_path)"
            )
        if self._transaction is not None and self._transaction.active:
            raise ValueError("Transaction already active")
        self._transaction = Transaction(self._catalog.conn)
        return self._transaction

    # -- Query interface -----------------------------------------------

    def query(self) -> QueryBuilder:
        return QueryBuilder(self)

    def sql(self, query: str) -> Any:
        """Execute a SQL query against the engine's storage."""
        from uqa.sql.compiler import SQLCompiler

        compiler = SQLCompiler(self)
        return compiler.execute(query)

    def close(self) -> None:
        """Close the persistent catalog (no-op if in-memory only)."""
        if self._transaction is not None and self._transaction.active:
            self._transaction.rollback()
            self._transaction = None
        if self._catalog is not None:
            self._catalog.close()
            self._catalog = None

    def __enter__(self) -> Engine:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _build_context(self) -> Any:
        from uqa.operators.base import ExecutionContext

        return ExecutionContext(
            document_store=self.document_store,
            inverted_index=self.inverted_index,
            vector_index=self.vector_index,
            graph_store=self.graph_store,
            block_max_index=self.block_max_index,
            index_manager=self._index_manager,
        )
