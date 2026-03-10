#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any

from numpy.typing import NDArray

from uqa.api.query_builder import QueryBuilder
from uqa.core.types import DocId, Edge, Payload, PostingEntry, Vertex
from uqa.graph.store import GraphStore
from uqa.storage.catalog import Catalog
from uqa.planner.parallel import ParallelExecutor
from uqa.storage.index_manager import IndexManager
from uqa.storage.sqlite_graph_store import SQLiteGraphStore
from uqa.storage.transaction import Transaction
from uqa.sql.table import ColumnDef, ColumnStats, Table, _SQL_TYPE_MAP


class Engine:
    """Main engine: all storage is per-table, no global stores.

    When ``db_path`` is provided the engine persists every mutation to a
    SQLite database (write-through) and restores state on next startup.
    When ``db_path`` is ``None`` the engine is purely in-memory.
    """

    def __init__(
        self,
        db_path: str | None = None,
        vector_dimensions: int = 64,
        max_elements: int = 10000,
        parallel_workers: int = 4,
        spill_threshold: int = 0,
    ):
        self._vector_dimensions = vector_dimensions
        self._max_elements = max_elements
        self._parallel_executor = ParallelExecutor(
            max_workers=parallel_workers
        )
        self.spill_threshold = spill_threshold
        self._tables: dict[str, Any] = {}
        self._views: dict[str, Any] = {}  # name -> SelectStmt AST
        self._prepared: dict[str, Any] = {}  # name -> PrepareStmt AST
        self._sequences: dict[str, dict[str, int]] = {}
        self._temp_tables: set[str] = set()
        self._named_graphs: dict[str, GraphStore] = {}

        # Persistence and transactions
        self._catalog: Catalog | None = None
        self._index_manager: IndexManager | None = None
        self._transaction: Transaction | None = None
        if db_path is not None:
            self._catalog = Catalog(db_path)
            self._index_manager = IndexManager(
                self._catalog.conn, self._catalog
            )
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
            columns = []
            for cd in col_dicts:
                type_name = cd["type_name"]
                if type_name == "vector":
                    python_type: type = list
                else:
                    python_type = _SQL_TYPE_MAP[type_name]
                columns.append(
                    ColumnDef(
                        name=cd["name"],
                        type_name=type_name,
                        python_type=python_type,
                        primary_key=cd["primary_key"],
                        not_null=cd["not_null"],
                        auto_increment=cd["auto_increment"],
                        default=cd["default"],
                        vector_dimensions=cd.get("vector_dimensions"),
                    )
                )
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
            for row in catalog.load_column_stats(name):
                col_name, dc, nc, mn, mx, rc = row[:6]
                hist = row[6] if len(row) > 6 else []
                mcv_v = row[7] if len(row) > 7 else []
                mcv_f = row[8] if len(row) > 8 else []
                table._stats[col_name] = ColumnStats(
                    distinct_count=dc,
                    null_count=nc,
                    min_value=mn,
                    max_value=mx,
                    row_count=rc,
                    histogram=hist,
                    mcv_values=mcv_v,
                    mcv_frequencies=mcv_f,
                )

            self._tables[name] = table

        # -- Analyzers -------------------------------------------------
        from uqa.analysis.analyzer import Analyzer, register_analyzer

        for name, config in catalog.load_analyzers():
            analyzer = Analyzer.from_dict(config)
            try:
                register_analyzer(name, analyzer)
            except ValueError:
                pass  # already registered (built-in or duplicate)

        # -- Named graphs ----------------------------------------------
        for graph_name in catalog.load_named_graphs():
            self._named_graphs[graph_name] = SQLiteGraphStore(
                catalog.conn, table_name=f"_graph_{graph_name}"
            )

        # -- Indexes ---------------------------------------------------
        if self._index_manager is not None:
            self._index_manager.load_from_catalog()

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

    # -- Public API ----------------------------------------------------

    def add_document(
        self,
        doc_id: DocId,
        document: dict[str, Any],
        table: str,
        embedding: NDArray | None = None,
    ) -> None:
        """Add a document to a table's storage and indexes.

        The document is stored in the table's document store, text fields
        are indexed into the table's inverted index, and an optional
        embedding vector is added to the first available vector index.
        """
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")

        # Include the primary key in stored data for consistency with
        # SQL INSERT (Table.insert) which always stores the PK column.
        stored = dict(document)
        if tbl.primary_key is not None and tbl.primary_key not in stored:
            pk_col = tbl.columns[tbl.primary_key]
            stored[tbl.primary_key] = pk_col.python_type(doc_id)

        tbl.document_store.put(doc_id, stored)

        text_fields = {
            k: v for k, v in stored.items() if isinstance(v, str)
        }
        if text_fields:
            tbl.inverted_index.add_document(doc_id, text_fields)

        if embedding is not None:
            vec_idx = next(iter(tbl.vector_indexes.values()), None)
            if vec_idx is not None:
                vec_idx.add(doc_id, embedding)

    def delete_document(self, doc_id: DocId, table: str) -> None:
        """Remove a document from a table's storage and indexes."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.document_store.delete(doc_id)
        tbl.inverted_index.remove_document(doc_id)

    def add_graph_vertex(self, vertex: Vertex, table: str) -> None:
        """Add a graph vertex to a table's graph store."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.graph_store.add_vertex(vertex)

    def add_graph_edge(self, edge: Edge, table: str) -> None:
        """Add a graph edge to a table's graph store."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.graph_store.add_edge(edge)

    # -- Named graph management ----------------------------------------

    def create_graph(self, name: str) -> GraphStore:
        """Create a named graph (Apache AGE ``create_graph``)."""
        if name in self._named_graphs:
            raise ValueError(f"Graph '{name}' already exists")
        if self._catalog is not None:
            store: GraphStore = SQLiteGraphStore(
                self._catalog.conn, table_name=f"_graph_{name}"
            )
            self._catalog.save_named_graph(name)
        else:
            store = GraphStore()
        self._named_graphs[name] = store
        return store

    def drop_graph(self, name: str) -> None:
        """Drop a named graph and all its data."""
        store = self._named_graphs.pop(name, None)
        if store is None:
            raise ValueError(f"Graph '{name}' does not exist")
        store.clear()
        if self._catalog is not None:
            self._catalog.drop_named_graph(name)
            # Drop the per-graph SQLite tables
            conn = self._catalog.conn
            prefix = f"_graph_{name}"
            conn.execute(f'DROP TABLE IF EXISTS "_graph_vertices_{prefix}"')
            conn.execute(f'DROP TABLE IF EXISTS "_graph_edges_{prefix}"')
            conn.commit()

    def get_graph(self, name: str) -> GraphStore:
        """Return the named graph store, raising if it does not exist."""
        store = self._named_graphs.get(name)
        if store is None:
            raise ValueError(f"Graph '{name}' does not exist")
        return store

    def has_graph(self, name: str) -> bool:
        """Return True if a named graph with *name* exists."""
        return name in self._named_graphs

    # -- Analyzer management -------------------------------------------

    def create_analyzer(
        self, name: str, config: dict[str, Any]
    ) -> None:
        """Create a named analyzer and persist it to the catalog.

        ``config`` is the Analyzer serialization dict with keys:
        ``tokenizer``, ``token_filters``, ``char_filters``.
        """
        from uqa.analysis.analyzer import Analyzer, register_analyzer

        analyzer = Analyzer.from_dict(config)
        register_analyzer(name, analyzer)
        if self._catalog is not None:
            self._catalog.save_analyzer(name, config)

    def drop_analyzer(self, name: str) -> None:
        """Drop a named analyzer."""
        from uqa.analysis.analyzer import drop_analyzer

        drop_analyzer(name)
        if self._catalog is not None:
            self._catalog.drop_analyzer(name)

    def set_table_analyzer(
        self, table_name: str, field: str, analyzer_name: str
    ) -> None:
        """Assign a named analyzer to a table field for indexing and search."""
        from uqa.analysis.analyzer import get_analyzer

        tbl = self._tables.get(table_name)
        if tbl is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        analyzer = get_analyzer(analyzer_name)
        tbl.inverted_index.set_field_analyzer(field, analyzer)

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

    def query(self, table: str) -> QueryBuilder:
        """Create a fluent query builder scoped to a table."""
        return QueryBuilder(self, table=table)

    def sql(self, query: str, params: list[Any] | None = None) -> Any:
        """Execute a SQL query against the engine's storage.

        *params* is an optional list of parameter values for ``$1``,
        ``$2``, ... placeholders (e.g. numpy arrays for vector search).
        """
        from uqa.sql.compiler import SQLCompiler

        compiler = SQLCompiler(self)
        return compiler.execute(query, params=params)

    def close(self) -> None:
        """Close the engine and clean up resources.

        Drops all temporary tables and closes the persistent catalog.
        """
        if self._transaction is not None and self._transaction.active:
            self._transaction.rollback()
            self._transaction = None

        # Drop all temporary tables (session-scoped)
        for table_name in list(self._temp_tables):
            self._tables.pop(table_name, None)
        self._temp_tables.clear()

        if self._catalog is not None:
            self._catalog.close()
            self._catalog = None

    def __enter__(self) -> Engine:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _context_for_table(self, table_name: str) -> Any:
        """Build an ExecutionContext scoped to a specific table."""
        from uqa.operators.base import ExecutionContext

        tbl = self._tables.get(table_name)
        if tbl is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        return ExecutionContext(
            document_store=tbl.document_store,
            inverted_index=tbl.inverted_index,
            vector_indexes=tbl.vector_indexes,
            graph_store=tbl.graph_store,
            block_max_index=tbl.block_max_index,
            index_manager=self._index_manager,
            parallel_executor=self._parallel_executor,
        )
