#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from uqa.api.query_builder import QueryBuilder

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from uqa.fdw.foreign_table import ForeignServer, ForeignTable
    from uqa.fdw.handler import FDWHandler
    from uqa.graph.index import PathIndex
from uqa.core.types import DocId, Edge, Payload, PostingEntry, Vertex
from uqa.graph.store import GraphStore, MemoryGraphStore
from uqa.planner.parallel import ParallelExecutor
from uqa.sql.table import _SQL_TYPE_MAP, ColumnDef, ColumnStats, Table
from uqa.storage.catalog import Catalog
from uqa.storage.index_manager import IndexManager
from uqa.storage.transaction import Transaction


class Engine:
    """Main engine: all storage is per-table, no global stores.

    When ``db_path`` is provided the engine persists every mutation to a
    SQLite database (write-through) and restores state on next startup.
    When ``db_path`` is ``None`` the engine is purely in-memory.
    """

    def __init__(
        self,
        db_path: str | None = None,
        parallel_workers: int = 4,
        spill_threshold: int = 0,
    ):
        self._parallel_executor = ParallelExecutor(max_workers=parallel_workers)
        self.spill_threshold = spill_threshold
        self._tables: dict[str, Any] = {}
        self._views: dict[str, Any] = {}  # name -> SelectStmt AST
        self._prepared: dict[str, Any] = {}  # name -> PrepareStmt AST
        self._sequences: dict[str, dict[str, int]] = {}
        self._temp_tables: set[str] = set()
        self._graph_store: GraphStore = MemoryGraphStore()
        self._versioned_graphs: dict[str, Any] = {}
        self._path_indexes: dict[str, PathIndex] = {}

        self._foreign_servers: dict[str, ForeignServer] = {}
        self._foreign_tables: dict[str, ForeignTable] = {}
        self._fdw_handlers: dict[str, FDWHandler] = {}

        # Persistence and transactions
        self._catalog: Catalog | None = None
        self._index_manager: IndexManager | None = None
        self._transaction: Transaction | None = None
        if db_path is not None:
            self._catalog = Catalog(db_path)
            self._index_manager = IndexManager(self._catalog.conn, self._catalog)
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
                if type_name in ("vector", "point"):
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
        from uqa.analysis.analyzer import (
            Analyzer,
            get_analyzer,
            register_analyzer,
        )

        for name, config in catalog.load_analyzers():
            analyzer = Analyzer.from_dict(config)
            try:
                register_analyzer(name, analyzer)
            except ValueError:
                pass  # already registered (built-in or duplicate)

        # -- Field-to-analyzer mappings --------------------------------
        for (
            tbl_name,
            field,
            phase,
            analyzer_name,
        ) in catalog.load_table_field_analyzers():
            tbl = self._tables.get(tbl_name)
            if tbl is None:
                continue
            try:
                analyzer = get_analyzer(analyzer_name)
            except ValueError:
                continue
            tbl.inverted_index.set_field_analyzer(field, analyzer, phase=phase)

        # -- Named graphs ----------------------------------------------
        for graph_name in catalog.load_named_graphs():
            if not self._graph_store.has_graph(graph_name):
                self._graph_store.create_graph(graph_name)

        # -- Path indexes ----------------------------------------------
        from uqa.graph.index import PathIndex

        for graph_name, label_sequences in catalog.load_path_indexes():
            if self._graph_store.has_graph(graph_name):
                self._path_indexes[graph_name] = PathIndex.build(
                    self._graph_store, label_sequences, graph_name=graph_name
                )

        # -- Foreign servers and tables --------------------------------
        from uqa.fdw.foreign_table import ForeignServer, ForeignTable

        for name, fdw_type, options in catalog.load_foreign_servers():
            self._foreign_servers[name] = ForeignServer(
                name=name,
                fdw_type=fdw_type,
                options=options,
            )

        for name, server_name, col_dicts, options in catalog.load_foreign_tables():
            cols = OrderedDict()
            for cd in col_dicts:
                type_name = cd["type_name"]
                if type_name in ("vector", "point"):
                    python_type = list
                else:
                    python_type = _SQL_TYPE_MAP[type_name]
                cols[cd["name"]] = ColumnDef(
                    name=cd["name"],
                    type_name=type_name,
                    python_type=python_type,
                    primary_key=cd.get("primary_key", False),
                    not_null=cd.get("not_null", False),
                )
            self._foreign_tables[name] = ForeignTable(
                name=name,
                server_name=server_name,
                columns=cols,
                options=options,
            )

        # -- Indexes ---------------------------------------------------
        if self._index_manager is not None:
            self._index_manager.load_from_catalog()

        # -- IVF vector indexes ----------------------------------------
        # IVF tables persist in SQLite, so we reconstruct the IVFIndex
        # wrapper and attach it to the table.
        from uqa.storage.ivf_index import IVFIndex

        for _name, idx_type, tbl_name, cols, params in catalog.load_indexes():
            if idx_type not in ("ivf", "hnsw"):
                continue
            tbl = self._tables.get(tbl_name)
            if tbl is None:
                continue
            col_name = cols[0] if cols else None
            if col_name is None:
                continue
            ivf_kwargs: dict[str, Any] = {
                "conn": catalog.conn,
                "table_name": tbl_name,
                "field_name": col_name,
                "dimensions": tbl.columns[col_name].vector_dimensions or 0,
            }
            if "nlist" in params:
                ivf_kwargs["nlist"] = params["nlist"]
            if "nprobe" in params:
                ivf_kwargs["nprobe"] = params["nprobe"]
            tbl.vector_indexes[col_name] = IVFIndex(**ivf_kwargs)

        # -- R*Tree spatial indexes ------------------------------------
        # R*Tree virtual table data persists in SQLite, so we only need
        # to reconstruct the SpatialIndex wrapper and attach it to the
        # table.  The R*Tree data is already populated.
        from uqa.storage.spatial_index import SpatialIndex

        for _name, idx_type, tbl_name, cols, _params in catalog.load_indexes():
            if idx_type != "rtree":
                continue
            tbl = self._tables.get(tbl_name)
            if tbl is None:
                continue
            col_name = cols[0] if cols else None
            if col_name is None:
                continue
            sp_idx = SpatialIndex(tbl_name, col_name, conn=catalog.conn)
            tbl.spatial_indexes[col_name] = sp_idx

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
            entry = PostingEntry(doc_id, Payload(positions=positions, score=0.0))
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

        # Store embedding vector in the document store alongside scalar data.
        vec_col_for_index: str | None = None
        vec_array = None
        if embedding is not None:
            import numpy as np

            vec_col_for_index = next(
                (
                    name
                    for name, col in tbl.columns.items()
                    if col.vector_dimensions is not None
                ),
                None,
            )
            if vec_col_for_index is not None:
                vec_array = np.asarray(embedding, dtype=np.float32)
                stored[vec_col_for_index] = vec_array.tolist()

        tbl.document_store.put(doc_id, stored)

        text_fields = {k: v for k, v in stored.items() if isinstance(v, str)}
        if text_fields:
            tbl.inverted_index.add_document(doc_id, text_fields)

        if vec_col_for_index is not None and vec_array is not None:
            vec_idx = tbl.vector_indexes.get(vec_col_for_index)
            if vec_idx is not None:
                vec_idx.add(doc_id, vec_array)

    def get_document(self, doc_id: DocId, table: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID from the given table.

        Returns the stored document dict, or ``None`` if the document
        does not exist.
        """
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        return tbl.document_store.get(doc_id)

    def delete_document(self, doc_id: DocId, table: str) -> None:
        """Remove a document from a table's storage and indexes."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.document_store.delete(doc_id)
        tbl.inverted_index.remove_document(doc_id)

    def get_graph_store(self, table: str) -> GraphStore:
        """Return the graph store associated with the given table."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        return tbl.graph_store

    def add_graph_vertex(self, vertex: Vertex, table: str) -> None:
        """Add a graph vertex to a table's graph store."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.graph_store.add_vertex(vertex, graph=table)

    def add_graph_edge(self, edge: Edge, table: str) -> None:
        """Add a graph edge to a table's graph store."""
        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")
        tbl.graph_store.add_edge(edge, graph=table)

    # -- Named graph management ----------------------------------------

    def create_graph(self, name: str) -> GraphStore:
        """Create a named graph."""
        self._graph_store.create_graph(name)
        if self._catalog is not None:
            self._catalog.save_named_graph(name)
        return self._graph_store

    def drop_graph(self, name: str) -> None:
        """Drop a named graph and all its data."""
        self._graph_store.drop_graph(name)
        if self._catalog is not None:
            self._catalog.drop_named_graph(name)

    def get_graph(self, name: str) -> GraphStore:
        """Return the graph store, raising if named graph does not exist."""
        if not self._graph_store.has_graph(name):
            raise ValueError(f"Graph '{name}' does not exist")
        return self._graph_store

    def has_graph(self, name: str) -> bool:
        """Return True if a named graph with *name* exists."""
        return self._graph_store.has_graph(name)

    @property
    def graph_store(self) -> GraphStore:
        """Return the global graph store."""
        return self._graph_store

    # -- Path index management -----------------------------------------

    def build_path_index(
        self, graph_name: str, label_sequences: list[list[str]]
    ) -> None:
        """Build a path index for a named graph (Section 9.1, Paper 2).

        Pre-computes reachable (start, end) vertex pairs for the given
        label sequences, enabling O(1) RPQ lookups.
        """
        from uqa.graph.index import PathIndex

        if not self._graph_store.has_graph(graph_name):
            raise ValueError(f"Graph '{graph_name}' does not exist")
        idx = PathIndex.build(self._graph_store, label_sequences, graph_name=graph_name)
        self._path_indexes[graph_name] = idx
        if self._catalog is not None:
            self._catalog.save_path_index(graph_name, label_sequences)

    def get_path_index(self, graph_name: str) -> PathIndex | None:
        """Return the path index for a named graph, or None."""
        return self._path_indexes.get(graph_name)

    def drop_path_index(self, graph_name: str) -> None:
        """Remove the path index for a named graph."""
        self._path_indexes.pop(graph_name, None)
        if self._catalog is not None:
            self._catalog.drop_path_index(graph_name)

    # -- Graph delta management (Section 9.3, Paper 2) -----------------

    def apply_graph_delta(self, graph_name: str, delta: Any) -> int:
        """Apply a graph delta to a named graph (Section 9.3, Paper 2).

        Applies the delta operations, increments the graph version, and
        invalidates any path indexes whose label sequences overlap with
        the delta's affected edge labels.
        """
        from uqa.graph.versioned_store import VersionedGraphStore

        if not self._graph_store.has_graph(graph_name):
            raise ValueError(f"Graph '{graph_name}' does not exist")

        # Wrap in VersionedGraphStore if not already tracked
        versioned = self._versioned_graphs.get(graph_name)
        if versioned is None:
            versioned = VersionedGraphStore(self._graph_store, graph_name=graph_name)
            self._versioned_graphs[graph_name] = versioned

        version = versioned.apply(delta)

        # Invalidate path index if affected labels overlap
        path_idx = self._path_indexes.get(graph_name)
        if path_idx is not None:
            affected = delta.affected_edge_labels()
            for indexed_path in path_idx.indexed_paths():
                path_labels = set(indexed_path.split("/"))
                if path_labels & affected:
                    self._path_indexes.pop(graph_name, None)
                    if self._catalog is not None:
                        self._catalog.drop_path_index(graph_name)
                    break

        return version

    # -- Analyzer management -------------------------------------------

    def create_analyzer(self, name: str, config: dict[str, Any]) -> None:
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
        self,
        table_name: str,
        field: str,
        analyzer_name: str,
        phase: str = "both",
    ) -> None:
        """Assign a named analyzer to a table field.

        ``phase`` controls which phase the analyzer applies to:
        ``"index"`` for indexing only, ``"search"`` for search only,
        or ``"both"`` (default) for both phases.
        """
        from uqa.analysis.analyzer import get_analyzer

        if phase not in ("index", "search", "both"):
            raise ValueError(
                f"phase must be 'index', 'search', or 'both', got '{phase}'"
            )
        tbl = self._tables.get(table_name)
        if tbl is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        analyzer = get_analyzer(analyzer_name)
        tbl.inverted_index.set_field_analyzer(field, analyzer, phase=phase)
        if self._catalog is not None:
            if phase == "both":
                self._catalog.save_table_field_analyzer(
                    table_name, field, "index", analyzer_name
                )
                self._catalog.save_table_field_analyzer(
                    table_name, field, "search", analyzer_name
                )
            else:
                self._catalog.save_table_field_analyzer(
                    table_name, field, phase, analyzer_name
                )

    def get_table_analyzer(
        self, table_name: str, field: str, phase: str = "index"
    ) -> Any:
        """Return the analyzer assigned to a table field.

        ``phase`` selects whether to return the index-time or
        search-time analyzer.  Defaults to ``"index"``.
        """
        tbl = self._tables.get(table_name)
        if tbl is None:
            raise ValueError(f"Table '{table_name}' does not exist")
        if phase == "search":
            return tbl.inverted_index.get_search_analyzer(field)
        return tbl.inverted_index.get_field_analyzer(field)

    # -- Scoring parameters (Papers 3-4) -------------------------------

    def save_scoring_params(self, name: str, params: dict[str, Any]) -> None:
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

    def learn_scoring_params(
        self,
        table: str,
        field: str,
        query: str,
        labels: list[int],
        *,
        mode: str = "balanced",
    ) -> dict[str, float]:
        """Learn Bayesian BM25 calibration parameters from relevance judgments.

        Scores every labeled document and fits (alpha, beta, base_rate) to
        minimize calibration error.  Persists the learned parameters.
        """
        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer
        from uqa.scoring.parameter_learner import ParameterLearner

        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")

        ctx = self._context_for_table(table)
        idx = ctx.inverted_index
        analyzer = idx.get_search_analyzer(field) if field else idx.analyzer
        terms = analyzer.analyze(query)
        scorer = BayesianBM25Scorer(BayesianBM25Params(), idx.stats)

        retrieval = TermOperator(query, field)
        score_op = ScoreOperator(scorer, retrieval, terms, field=field)
        result_pl = score_op.execute(ctx)

        score_map: dict[int, float] = {}
        for entry in result_pl:
            score_map[entry.doc_id] = entry.payload.score

        doc_ids = sorted(tbl.document_store.doc_ids)
        if len(labels) != len(doc_ids):
            raise ValueError(
                f"labels length ({len(labels)}) must match "
                f"document count ({len(doc_ids)})"
            )

        scores = [score_map.get(did, 0.0) for did in doc_ids]
        learner = ParameterLearner()
        learned = learner.fit(scores, labels, mode=mode)

        param_name = f"{table}.{field}.{query}"
        self.save_scoring_params(param_name, learned)
        return learned

    def update_scoring_params(
        self,
        table: str,
        field: str,
        score: float,
        label: int,
    ) -> None:
        """Online update of Bayesian calibration parameters with a single observation."""
        from uqa.scoring.parameter_learner import ParameterLearner

        param_name = f"{table}.{field}"
        existing = self.load_scoring_params(param_name)

        if existing is not None:
            learner = ParameterLearner(
                alpha=existing.get("alpha", 1.0),
                beta=existing.get("beta", 0.0),
                base_rate=existing.get("base_rate", 0.5),
            )
        else:
            learner = ParameterLearner()

        learner.update(score, label)
        self.save_scoring_params(param_name, learner.params())

    def calibration_report(
        self,
        table: str,
        field: str,
        query: str,
        labels: list[int],
    ) -> dict:
        """Compute calibration diagnostics for a Bayesian BM25 query.

        Scores every labeled document using Bayesian BM25 and compares
        predicted probabilities against ground-truth binary labels.
        """
        from uqa.scoring.calibration import CalibrationMetrics

        tbl = self._tables.get(table)
        if tbl is None:
            raise ValueError(f"Table '{table}' does not exist")

        from uqa.operators.primitive import ScoreOperator, TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

        ctx = self._context_for_table(table)
        idx = ctx.inverted_index
        analyzer = idx.get_search_analyzer(field) if field else idx.analyzer
        terms = analyzer.analyze(query)
        scorer = BayesianBM25Scorer(BayesianBM25Params(), idx.stats)

        retrieval = TermOperator(query, field)
        score_op = ScoreOperator(scorer, retrieval, terms, field=field)
        result_pl = score_op.execute(ctx)

        score_map: dict[int, float] = {}
        for entry in result_pl:
            score_map[entry.doc_id] = entry.payload.score

        doc_ids = sorted(tbl.document_store.doc_ids)
        if len(labels) != len(doc_ids):
            raise ValueError(
                f"labels length ({len(labels)}) must match "
                f"document count ({len(doc_ids)})"
            )

        probabilities = [score_map.get(did, 0.0) for did in doc_ids]
        return CalibrationMetrics.report(probabilities, labels)

    # -- Vector calibration (Paper 5) ----------------------------------

    def vector_background_stats(
        self, table: str, field: str
    ) -> tuple[float, float] | None:
        """Return the IVF background distribution (mu_G, sigma_G).

        Returns ``None`` if the IVF index for the given table/field has
        not been trained or no background statistics are available.
        """
        tbl = self._tables.get(table)
        if tbl is None:
            return None
        vec_idx = tbl.vector_indexes.get(field)
        if vec_idx is not None and hasattr(vec_idx, "background_stats"):
            return vec_idx.background_stats  # type: ignore[return-value]
        return None

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
            raise ValueError("Transactions require a persistent engine (db_path)")
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

        # Close all FDW handlers
        for handler in self._fdw_handlers.values():
            handler.close()
        self._fdw_handlers.clear()
        self._foreign_tables.clear()
        self._foreign_servers.clear()

        # Drop all temporary tables (session-scoped)
        for table_name in list(self._temp_tables):
            self._tables.pop(table_name, None)
        self._temp_tables.clear()

        # Shut down the parallel executor thread pool before closing
        # the catalog connection to avoid SQLite access from orphaned
        # threads.
        self._parallel_executor.shutdown()

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
            spatial_indexes=tbl.spatial_indexes,
            graph_store=tbl.graph_store,
            block_max_index=tbl.block_max_index,
            index_manager=self._index_manager,
            parallel_executor=self._parallel_executor,
        )
