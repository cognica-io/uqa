# History

## 0.25.5 (2026-04-08)

Standalone property graph SQL functions. Six new FROM-clause functions allow creating, querying, traversing, and deleting graph nodes and edges entirely through SQL, without requiring Cypher or the Python API. Nodes are independent entities with auto-generated IDs and JSON properties, operating on named graphs. All 2918 tests pass across 85 test files.

### Standalone Graph SQL Functions

- **`graph_create_node('graph', 'Label', '{"props"}')`** (`sql/compiler.py`): Creates an independent vertex in a named graph with auto-generated ID via `GraphStore.next_vertex_id()`. Properties are passed as a JSON string. Returns a composite ID in the format `graph:Label:vertex_id`. The vertex is not bound to any SQL table.
- **`graph_create_edge('graph', 'TYPE', src, tgt, '{"props"}')`** (`sql/compiler.py`): Creates a directed edge in a named graph with auto-generated ID via `GraphStore.next_edge_id()`. Properties are passed as a JSON string. Returns a composite ID in the format `graph:TYPE:edge_id`.
- **`graph_nodes('graph'[, 'Label'][, '{"filter"}'])`** (`sql/compiler.py`): FROM-clause function returning all vertices in a named graph as rows with columns `id`, `label`, `properties`. Optionally filters by vertex label and/or JSON property predicates (exact match on each key-value pair).
- **`graph_neighbors('graph', id[, 'TYPE'][, 'dir'][, depth])`** (`sql/compiler.py`): FROM-clause function performing multi-hop BFS traversal on a named graph. Returns rows with columns `id`, `label`, `properties`, `depth`, `path`. Supports edge label filtering, direction (`outgoing`/`incoming`/`both`), and configurable depth. Path is a JSON array of vertex IDs from start to destination.
- **`graph_delete_node('graph', id)`** (`sql/compiler.py`): Removes a vertex and all its incident edges from a named graph via `GraphStore.remove_vertex()`. Persistence is handled automatically by the SQLite-backed graph store.
- **`graph_delete_edge('graph', id)`** (`sql/compiler.py`): Removes an edge from a named graph via `GraphStore.remove_edge()`. Persistence is handled automatically by the SQLite-backed graph store.

### Tests

- **37 new tests** in `test_graph_standalone_sql.py`: Covers all 6 functions including auto-ID generation, JSON property round-tripping, label and property filtering, multi-hop BFS with depth and path tracking, direction options, deletion cascading, multi-graph isolation, and full lifecycle end-to-end workflow.
- **Total**: 2918 tests across 85 test files.

## 0.25.4 (2026-04-07)

Fix per-field analyzer resolution in all-field full-text search. When a GIN index covers multiple fields with different analyzers (e.g., `standard_cjk` on one field, `english_stem` on another), all-field search (no explicit field specified) was using only the index-level default analyzer. Fields with custom analyzers produced incorrect tokens at search time. All 2881 tests pass across 84 test files.

### Bug Fix

- **All-field `TermOperator` per-field analysis** (`operators/primitive.py`): When no field is specified, `TermOperator.__call__` now iterates over each field's own search analyzer via `idx.field_analyzers`, tokenizes the query with each analyzer independently, looks up per-field posting lists, and unions all results. Falls back to the index-level `idx.analyzer` when `field_analyzers` is absent.
- **All-field FTS scoring tree per-field analysis** (`sql/compiler.py`): `_compile_fts_tree` now collects terms from each field's search analyzer (with deduplication) when no field is specified, ensuring the scoring tree uses the correct tokens per field. Falls back to `idx.analyzer` when `field_analyzers` is absent.
- **All-field phrase query per-field analysis** (`sql/fts_query.py`): `_compile_phrase` now collects terms from each field's search analyzer (with deduplication) when no field is specified, fixing phrase queries on multi-analyzer GIN indexes.

### Tests

- **Total**: 2881 tests across 84 test files.

## 0.25.3 (2026-04-05)

Version bump for correct PyPI release. No code changes from 0.25.2.

## 0.25.2 (2026-04-05)

Thread-safe query cancellation. A new `CancellationToken` mechanism allows in-flight queries to be cancelled from any thread via `Engine.cancel()`. All 2881 tests pass across 84 test files.

### Query Cancellation

- **`CancellationToken`** and **`QueryCancelled`** exception (`uqa/cancel.py`): Lightweight token that can be set from any thread; operators check it in hot loops and raise `QueryCancelled` when triggered.
- **`Engine.cancel()`** / **`Engine.cancel_token`**: Public API for cancelling the engine's current query. `cancel()` sets the token; `cancel_token` exposes it for external integrations (e.g., wire protocol servers).
- **`PhysicalOperator` base class**: Gains `cancel_token`, `check_cancelled()`, and `propagate_cancel_token()` so every operator tree shares a single token.
- **`JoinOperator` and `CrossJoinOperator`**: Gain `cancel_token` and `check_cancelled()` for join-loop cancellation.
- **Operator hot-loop checks**: SeqScan, PostingListScan, Filter, ExprFilter, Sort, HashAgg, Distinct, Window, InnerJoin, CrossJoin, LeftOuterJoin, and FullOuterJoin check the cancellation token on each iteration.
- **SQLCompiler**: Propagates the engine's cancel token to the operator tree before execution begins.

### Tests

- **Total**: 2881 tests across 84 test files.

## 0.25.1 (2026-04-04)

Register `bayesian_match_with_prior` as a calibrated signal for fusion functions. Previously, `bayesian_match_with_prior` worked only as a standalone WHERE-clause function but raised `Unknown signal function for fusion` when used inside `fuse_attention`, `fuse_log_odds`, or any other fusion meta-function. All 2881 tests pass across 84 test files.

### Bug Fix

- **`bayesian_match_with_prior` in fusion context**: Added the function to `_compile_calibrated_signal` so it can be used as a signal argument inside all fusion meta-functions (`fuse_log_odds`, `fuse_attention`, `fuse_multihead`, `fuse_learned`, `fuse_prob_and`, `fuse_prob_or`, `fuse_prob_not`, `fuse_mean`, `staged_retrieval`, `progressive_fusion`, `sparse_threshold`). Since the function already produces calibrated Bayesian posteriors, no additional calibration wrapper is needed.

### Documentation

- **`uqa-reference.md`**: Updated the calibrated signal list in Section 4.2 (Fusion Meta-Functions) to include `bayesian_match_with_prior`.

### Tests

- **1 new test** in `test_external_prior.py`: `test_bayesian_with_prior_in_fuse_attention` verifies that `bayesian_match_with_prior` works as a signal inside `fuse_attention` and produces scores in (0, 1).
- **Total**: 2881 tests across 84 test files.

## 0.25.0 (2026-04-02)

PostgreSQL compatibility: schema namespaces, session commands, in-memory transactions with real rollback, DDL enhancements, and query result correctness fixes. All 2734 tests pass across 84 test files; 30 examples and 309 benchmarks verified.

### Schema Support

- **`CREATE SCHEMA`** / **`DROP SCHEMA [CASCADE]`**: Full schema namespace support with `SchemaAwareTableStore` that stores tables in `{schema: {table_name: Table}}` with `search_path` resolution. All 80+ table access sites use the dict-compatible interface transparently.
- **`SET search_path TO 'myschema', 'public'`**: Changes schema resolution order at runtime. Unqualified table names resolve through the search path; qualified names (`myschema.users`) resolve directly.
- **Schema-qualified DDL/DML**: `CREATE TABLE myschema.t (...)`, `INSERT INTO myschema.t ...`, `SELECT * FROM myschema.t`, etc.
- **`information_schema.tables`** and **`pg_catalog.pg_tables`** now report the actual schema name per table instead of hardcoded `"public"`.

### Session Commands

- **`SET`** / **`SHOW`** / **`RESET`** / **`RESET ALL`**: Session variable storage with PostgreSQL-compatible defaults (`server_version`, `client_encoding`, `search_path`, `timezone`, etc.). `SET LOCAL` is accepted.
- **`DISCARD ALL`**: Clears session variables, prepared statements, and temporary tables.

### In-Memory Transactions

- **`BEGIN`** / **`COMMIT`** / **`ROLLBACK`**: Full transaction support in in-memory engines with real rollback. `InMemoryTransaction` snapshots all document stores on `begin()` and restores them on `rollback()` via `copy.deepcopy`.
- **`SAVEPOINT`** / **`RELEASE SAVEPOINT`** / **`ROLLBACK TO SAVEPOINT`**: Nested snapshots on a stack.

### DDL Enhancements

- **`DEFAULT CURRENT_TIMESTAMP`**, **`DEFAULT CURRENT_DATE`**: Column defaults can now use SQL value functions and function calls. AST nodes are stored as defaults and evaluated via `ExprEvaluator` at insert time (deferred evaluation, matching PostgreSQL behavior).
- **`ALTER TABLE ADD CONSTRAINT`**: Supports `CHECK`, `UNIQUE`, `PRIMARY KEY`, and `FOREIGN KEY` constraints. CHECK constraints validate existing data before accepting.
- **`ON CONFLICT DO NOTHING`** without explicit column specification: Catches UNIQUE/PK violations at insert time and silently skips the row.
- **In-memory `CREATE INDEX` / `DROP INDEX`**: BTREE index metadata is tracked in `engine._btree_indexes` so `CREATE INDEX` and `DROP INDEX` work without a persistent engine. GIN and RTREE indexes already worked in-memory.

### Query Result Correctness

- **`SELECT *` no longer exposes `_doc_id` / `_score`**: Internal columns are filtered from single-table `SELECT *` results. Graph traversal and search queries retain these columns.
- **Aggregate duplicate columns eliminated**: `SELECT COUNT(*) AS c` now returns only column `c`, not both `c` and `count`. The `_iter_batches` function filters rows through the declared column list.
- **LEFT JOIN + GROUP BY fix**: Unmatched left rows now have all right-side columns explicitly set to `None` (both qualified and unqualified). `GROUP BY` and aggregate arguments use qualified column names (`d.name`, `e.id`) to prevent ambiguity when tables share column names.
- **Date/time functions return proper types**: `CURRENT_DATE` returns `datetime.date`, `NOW()` / `CURRENT_TIMESTAMP` return `datetime.datetime`, `CURRENT_TIME` returns `datetime.time`. `DATE_TRUNC`, `MAKE_TIMESTAMP`, `MAKE_DATE`, `TO_DATE`, `TO_TIMESTAMP` also return native objects. Arrow batch system extended with `TIMESTAMP`, `DATE`, `TIME`, `INTERVAL` DataTypes. Predicate evaluation handles `date`/`str` comparison coercion.

### Internal Changes

- **`SchemaAwareTableStore`** (`engine.py`): Dict-compatible class with `_schemas: dict[str, dict[str, Table]]`, `search_path`, `create_schema()`, `drop_schema()`, `qualified_items()`.
- **`InMemoryTransaction`** (`storage/transaction.py`): Snapshot-based rollback with `_snapshot_tables()` / `_restore_tables()`. Savepoints as nested snapshots.
- **`_qualified_name()`** (`compiler.py`): Static helper to build `"schema.table"` from `RangeVar.schemaname` + `relname`.
- **`_extract_qualified_column_name()`** (`compiler.py`): Returns `"d.name"` for qualified ColumnRef nodes.
- **`_coerce_for_comparison()`** (`core/types.py`): Transparent date/str coercion in `Equals`, `GreaterThan`, etc.
- **`_coerce_datetime()`** (`table.py`): Parses date/time strings into native objects on INSERT for timestamp columns.
- **`_evaluate_default()`** (`table.py`): Evaluates pglast AST nodes via `ExprEvaluator` for deferred column defaults.
- **`_INTERNAL_COLUMNS`** (`compiler.py`): `frozenset({"_doc_id", "_score"})` for filtering internal columns.
- **`DataType.TIMESTAMP/DATE/TIME/INTERVAL`** (`batch.py`): New enum values with Arrow type mappings.

### Tests

- **73 new tests** in `test_pg_compat_bugs.py`: session variables (8), in-memory transactions (4), SELECT * filtering (3), aggregate duplicates (4), LEFT JOIN + GROUP BY (2), DEFAULT SQL functions (4), ADD CONSTRAINT (3), ON CONFLICT DO NOTHING (4), in-memory indexes (4), schema support (12), plus updated datetime tests.
- **Total**: 2880 tests across 84 test files.

## 0.24.0 (2026-04-01)

SQL faceted search and search result highlighting. Two new SQL functions bring search-engine-style faceting and term highlighting into the SQL layer, complementing the existing `@@` full-text search operator. All 2831 tests pass across 84 test files.

### Search Result Highlighting

- **`uqa_highlight(field, query)`**: SELECT scalar function that returns the field text with matched query terms wrapped in `<b>`/`</b>` tags. Uses the table's text analyzer for stemming-aware matching (e.g., query `"run"` highlights `"running"` in the original text).
- **Custom tags**: `uqa_highlight(field, query, '<em>', '</em>')` for arbitrary start/end markup.
- **Snippet extraction**: `uqa_highlight(field, query, start_tag, end_tag, max_fragments, fragment_size)` extracts the best fragments around matches instead of returning the full text. Fragments are snapped to word boundaries with `...` ellipsis markers.
- **Analyzer-aware matching**: The highlighter re-tokenizes the original text to locate character offsets, runs each token through the same analysis pipeline used for indexing, and checks whether the analyzed form matches any analyzed query term. This correctly handles stemming, lowercasing, and stop word removal.
- **FTS query parsing**: `extract_query_terms()` properly parses the FTS grammar (AND/OR/NOT, `"phrases"`, `field:term`) to extract searchable terms, rather than naively splitting on whitespace.

### Faceted Search

- **`uqa_facets(field)`**: SELECT function that transforms the query into facet rows with `facet_value | facet_count` columns. Facet counts are computed over the WHERE-filtered posting list, respecting any `@@`, `text_match`, or other search predicates.
- **Multi-field facets**: `uqa_facets(field1, field2, ...)` returns `facet_field | facet_value | facet_count` rows for multiple fields in a single query.
- **Alphabetically sorted**: Facet values are sorted alphabetically by default.

### New Module

- **`uqa/search/`**: New package containing `highlight.py` with core highlighting logic (`highlight()`, `extract_query_terms()`, fragment extraction) and `__init__.py`.

### Internal Changes

- **`ExprEvaluator`**: New `analyzer` parameter for stemming-aware `uqa_highlight()` evaluation. The table's inverted index analyzer is threaded from `SQLCompiler._execute_relational()` through `ExprProjectOp` to `ExprEvaluator`.
- **`ExprProjectOp`**: New `analyzer` parameter forwarded to `ExprEvaluator` on `open()`.
- **`SQLCompiler._try_facets()`**: Intercepts `uqa_facets()` in the SELECT list before relational execution, runs facet computation over the posting list, and returns facet rows directly.

### Tests

- **35 new tests** in `uqa/tests/test_sql_facets_highlight.py`: 12 highlight utility tests, 7 FTS query term extraction tests, 8 SQL highlight integration tests, 8 SQL facet integration tests.
- **Total**: 2831 tests across 84 test files.

## 0.23.0 (2026-03-30)

GIN index support for explicit full-text search column management, ported from the TypeScript implementation (`uqa-js`). Text columns are no longer auto-indexed on INSERT; users must create a GIN index via `CREATE INDEX ... USING gin` to enable full-text search on specific columns, matching PostgreSQL semantics. All 2796 tests pass across 83 test files.

### GIN Index

- **`CREATE INDEX ... USING gin (col1, col2, ...)`**: Creates a GIN (Generalized Inverted Index) on specified text columns. Only GIN-indexed columns are added to the inverted index on INSERT, UPDATE, and `put_document()`. Previously, all TEXT columns were auto-indexed unconditionally. This change aligns with PostgreSQL where GIN indexes must be explicitly created for full-text search.
- **`WITH (analyzer='...')`**: Optional analyzer parameter on GIN index creation. Assigns a per-field analyzer to each indexed column (e.g., `CREATE INDEX idx ON docs USING gin (body) WITH (analyzer='standard')`).
- **Backfill on creation**: When a GIN index is created on a table with existing rows, all current documents are automatically indexed for the specified columns. No manual re-indexing is required.
- **`DROP INDEX`**: Dropping a GIN index removes the associated columns from `fts_fields`. If no FTS fields remain, the inverted index is cleared entirely.
- **Catalog persistence**: GIN index definitions are persisted to the catalog and restored on Engine restart, including `fts_fields` reconstruction from stored index metadata.
- **`fts_fields` tracking**: Each `Table` now maintains a `fts_fields: set[str]` that controls which columns participate in inverted index operations. INSERT, UPDATE, DELETE, `put_document()`, and `delete_document()` all respect this set.

### Optimizer

- **Row-count-based full scan cost**: The query optimizer's index scan substitution previously used `inverted_index.stats.total_docs` for the full scan cost estimate. With GIN-gated indexing, tables without GIN indexes have `total_docs == 0`, which made the optimizer always prefer full scans over B-tree index scans. The optimizer now accepts an explicit `row_count` parameter from the document store, decoupling the full scan cost estimate from the inverted index state.

### Internal Changes

- **`IndexType.GIN`**: New enum value in `storage/index_types.py`.
- **`Engine._gin_indexes`**: Tracks GIN index definitions (`name -> (table_name, columns)`) for DROP INDEX and DROP TABLE cleanup.
- **`IndexManager.load_from_catalog()`**: Skips GIN indexes (managed by Engine/Table, not IndexManager).
- **CLI `\di`**: Lists GIN-indexed fields from `table.fts_fields` instead of probing the inverted index's internal state.

### Tests

- All existing FTS tests updated to create GIN indexes before inserting data (22 test files updated).
- **Total**: 2796 tests across 83 test files.

## 0.22.1 (2026-03-25)

Bug fix release: ASCIIFoldingFilter CJK preservation, IVF thread-safe parallel reads, JOIN + UQA function predicate pushdown, BOOLEAN column PyArrow compatibility, parameter binding across all DML/DQL paths, and multi-channel NumPy fallback in grid_forward. All 2796 tests pass across 83 test files.

### Bug Fixes

- **JOIN + UQA function predicate pushdown**: Queries combining JOINs with UQA posting-list functions (`text_match`, `knn_match`, `fuse_log_odds`, `@@`, etc.) in WHERE clauses now work correctly. UQA functions that reference a single table are pushed down to that table's scan and compiled via `_compile_where()` into posting-list operators (inverted index lookups, vector searches, fusion). A new `_CompiledWhereScanOperator` executes these operators against the table's `ExecutionContext`, enriches matching entries with full document fields for downstream JOIN evaluation, and optionally applies scalar filters. This replaces the previous approach of deferring UQA functions to `ExprFilterOp` (which tried to evaluate them as scalar expressions) or intersecting `GeneralizedPostingList` with single-table `PostingList` (type-incompatible).
- **BOOLEAN column PyArrow compatibility**: `Batch.from_rows()` and `ColumnVector.from_values()` now explicitly cast integer values (0/1) to Python `bool` before creating `pa.array(type=pa.bool_())`. PyArrow does not implicitly convert integers to booleans, causing `ArrowInvalid: Could not convert 1 with type int: tried to convert to boolean` when scanning tables with BOOLEAN columns.
- **Parameter binding in UPDATE/DELETE/SELECT WHERE**: `$N` placeholders now work in WHERE clauses across all DML and DQL statements, including JOIN ON conditions and pushed-down WHERE predicates. Previously, `ParamRef` nodes were not recognized in `_compile_comparison()` (fast path required `A_Const`), `_extract_const_value()` (static method without access to params), or `ExprEvaluator` (no `ParamRef` dispatch). Fixed by: (1) adding `ParamRef` handling to `_extract_const_value()`, (2) extending the fast path in `_compile_comparison()` to accept `ParamRef`, (3) adding `_eval_param_ref()` dispatch to `ExprEvaluator`, and (4) propagating `params` through `ExprProjectOp`, `ExprFilterOp`, `_ExprFilterOperator`, `_FilteredScanOperator`, `_CompiledWhereScanOperator`, `_ExprJoinOperator`, and window function evaluators.
- **ASCIIFoldingFilter CJK preservation**: `ASCIIFoldingFilter._fold()` now processes characters individually. Characters with ASCII equivalents (accented Latin: e with accent -> e, u with umlaut -> u) are folded; characters without ASCII equivalents (Korean, CJK, Arabic, etc.) are preserved as-is. Previously, the filter applied NFKD normalization to the entire token and then stripped all non-ASCII bytes, which decomposed Korean syllables into Jamo and then deleted them entirely. This broke `standard_cjk` analyzer for all CJK text.
- **IVF thread-safe parallel reads**: `ManagedConnection` now creates per-thread read-only SQLite connections for concurrent read access. Fusion operators (`fuse_log_odds`, etc.) execute signal branches in parallel via `ThreadPoolExecutor`; previously all threads shared a single `sqlite3.Connection` where `execute()` returned a cursor under the lock but `fetchall()` ran outside it, causing cursor interleaving and `sqlite3.DatabaseError: database disk image is malformed`. Each reader thread now gets its own WAL-mode connection via `read_fetchall()` / `read_fetchone()`, enabling true concurrent reads. `IVFIndex` search methods (`_ivf_knn`, `_brute_force_knn`, `probed_distances`, etc.) use these per-thread readers.
- **IVF index WAL persistence**: `catalog.close()` now executes `PRAGMA wal_checkpoint(TRUNCATE)` to flush all committed data from the WAL file to the main database before closing. `_train()` now commits in stages (centroids, then vector reassignments, then background stats) instead of accumulating all operations in a single transaction.
- **Multi-channel NumPy fallback in `grid_forward`**: Fixed channel dimension handling when PyTorch is not available. The NumPy fallback path now correctly reshapes multi-channel embeddings for convolution and preserves channel count through pooling layers.

### Tests

- **7 new tests** in `uqa/tests/test_sql.py`: UPDATE with parameterized WHERE, UPDATE with parameterized SET and WHERE, DELETE with parameterized WHERE, SELECT with parameterized WHERE (fast path), SELECT with parameterized expression WHERE, JOIN with UQA function in WHERE (text_match + param binding), JOIN with UQA function and scalar filter combined.
- **1 new test** in `uqa/tests/test_ivf_index.py`: IVF trained state (centroids + background stats + probed_distances) persists across Engine close/reopen with 300 vectors exceeding train_threshold.
- **Total**: 2796 tests across 83 test files.

## 0.22.0 (2026-03-23)

Global pooling layer, kernel initialization modes, and vector calibration theory (Paper 5). Global pooling (`global_pool()`) provides channel-preserving spatial reduction as an alternative to `flatten()`, reducing feature dimensionality while retaining per-channel statistics. Three new kernel initialization strategies -- orthogonal (QR decomposition), Gabor (structured filter bank), and k-means (data-dependent patch dictionary) -- replace or supplement the default Kaiming random initialization for `convolve()` layers. Paper 5 completes the probabilistic unification of sparse and dense retrieval by calibrating vector similarity scores into Bayesian probabilities via likelihood ratios over ANN index statistics. All 2788 tests pass across 83 test files.

### Global Pooling Layer

- **`global_pool('avg'|'max'|'avg_max')`**: Channel-preserving spatial reduction as an alternative to `flatten()`. Reduces spatial dimensions to 1x1 while keeping channel information: `avg` computes per-channel mean over all spatial positions, `max` takes per-channel maximum, `avg_max` concatenates both (doubling the channel count). For example, 8 channels on a 2x2 feature map: `flatten()` produces 32-D, `global_pool('avg')` produces 8-D, `global_pool('avg_max')` produces 16-D.
- **`GlobalPoolSpec`**: Layer specification for `deep_learn()` training pipeline. Integrated into `_specs_to_dicts()` / `_dicts_to_specs()` serialization, `TrainedModel.to_deep_fusion_layers()`, and model catalog persistence.
- **`GlobalPoolLayer`**: Deep fusion layer for inference. Supported in both graph-based execution path and grid-accelerated backend path (`grid_global_pool()` in `_backend.py`).
- **`grid_global_pool(features, grid_h, grid_w, method)`**: Backend function with PyTorch GPU acceleration (adaptive pooling) and NumPy fallback. Batched processing (4096 samples per batch) to prevent GPU OOM.
- **SQL syntax**: `global_pool('avg')`, `global_pool('max')`, `global_pool('avg_max')` inside `deep_learn()` and `deep_fusion()`. Method validation in SQL compiler.
- **Model reconstruction**: `deep_fusion(model('name', $1))` correctly reconstructs `GlobalPoolLayer` from saved model specs instead of defaulting to `FlattenLayer`.

### Kernel Initialization Modes

- **`convolve(n_channels => N, init => 'kaiming'|'orthogonal'|'gabor'|'kmeans')`**: Configurable kernel initialization for conv layers. The `init` parameter selects the initialization strategy.
- **Kaiming (default)**: Random normal initialization scaled by `sqrt(2/fan_in)`. Original behavior, good general-purpose prior.
- **Orthogonal**: QR decomposition (Saxe et al. 2014). Produces maximally diverse filters -- each kernel is orthogonal to all others in the flattened `(in_channels * 3 * 3)` space. Eliminates the redundancy inherent in random initialization.
- **Gabor**: Structured filter bank with 8 orientations x 3 frequencies x 2 phases = 48 Gabor filters (zero-mean, unit-norm bandpass). Remaining channels filled with Kaiming random. Gabor filters are optimal joint space-frequency localized features, analogous to V1 simple cells.
- **K-means**: Data-dependent patch dictionary (Coates & Ng 2012). Extracts 10,000 random 3x3 patches from training images, normalizes them, and runs k-means++ with Lloyd's algorithm to find cluster centroids. Each centroid becomes a conv kernel representing a frequently occurring local pattern.
- **`_generate_kernels(n_channels, in_channels, seed, init_mode, training_data, grid_h, grid_w)`**: Unified kernel generation function dispatching to `generate_orthogonal_kernels()`, `generate_gabor_kernels()`, or `generate_kmeans_kernels()` in `_backend.py`.

### Paper 5: Vector Calibration

- **Paper 5**: *Vector Scores as Likelihood Ratios -- Index-Derived Bayesian Calibration for Hybrid Search* (Jeong, 2026). Transforms vector similarity scores into calibrated relevance probabilities through a likelihood ratio formulation grounded in Bayes' theorem.
- **README**: New "Vector Calibration" subsection in Background section explaining the likelihood ratio framework and its structural identity with Bayesian BM25 calibration.
- **References**: Paper 5 added to References section and "For full formal treatment" cross-reference.

### Tests

- **16 new tests** in `uqa/tests/test_deep_learn.py`: global pooling backend (3), spec serialization (1), SQL training/prediction (3), kernel init modes -- shape and properties (6), SQL integration (2), combined global_pool + orthogonal (1).
- **Total**: 2788 tests across 83 test files.

## 0.21.0 (2026-03-20)

Deep fusion as a complete neural network execution framework with analytical training pipeline. `deep_learn()` trains CNN classifiers via ridge regression and random multi-channel convolution — no backpropagation. Self-attention (Theorem 8.3) as context-dependent PoE. Neural network pruning via elastic net (L1) and magnitude pruning. Parameterized INSERT for 65x faster vector data loading. `deep_predict()` and `deep_fusion(model())` provide inference. PyTorch GPU acceleration for conv/pool/dense/attention operations. Storage backend ABCs for backend-agnostic persistence. Internal data model refactored from scalar logits to multi-channel vectors for full DL pipeline support. All 2771 tests pass across 85 test files.

### Deep Fusion: Multi-Layer Bayesian Fusion Operator

- **`deep_fusion(layer(...), propagate(...), convolve(...), ...)`**: Multi-layer fusion operator that implements deep Bayesian fusion as a multi-layer network with residual connections. Each layer type maps to a neural network architecture: SignalLayer (ResNet), PropagateLayer (GNN), ConvLayer (CNN).
- **Gating functions**: `gating => 'none'` (identity), `gating => 'relu'` (MAP under sparse prior), `gating => 'swish'` (Bayesian posterior mean). Applied per-layer as nonlinear activations.
- **`alpha` parameter**: Confidence scaling for multi-signal log-odds conjunction within signal layers.
- **EXPLAIN**: Tree-formatted plan output showing layer types, signal counts, and parameters.
- **Parallel execution**: Signal layers execute branches concurrently via `ThreadPoolExecutor` when `parallel_workers` is configured.

### Deep Fusion: Spatial CNN (ConvLayer)

- **`convolve('edge_label', ARRAY[w0, w1, ...][, 'direction'])`**: Weighted multi-hop BFS aggregation over graph neighborhoods. `hop_weights[0]` = self (skip connection), `hop_weights[1]` = 1-hop neighbors (3x3 equivalent on grid), `hop_weights[2]` = 2-hop (5x5 receptive field). Weights normalized to sum to 1. Residual connection on channel 0.
- **`estimate_conv_weights(table, edge_label, kernel_hops[, embedding_field])`**: MLE weight estimation from spatial autocorrelation. Computes average cosine similarity between patch embeddings at each hop distance. No backpropagation -- uses data statistics directly.
- **Stacked ConvLayers**: Multiple ConvLayers compose for deeper receptive fields (two 1-hop layers = 5x5 effective field).

### Deep Fusion: Neural Network Layers

- **Channel map data model**: Internal representation refactored from `logit_map: dict[int, float]` (scalar) to `channel_map: dict[int, np.ndarray]` (multi-channel vector). Single-channel (`num_channels=1`) is backward compatible. Existing layers (Signal, Propagate, Conv) operate on channel 0 only; new layers operate on all channels.
- **`pool('edge_label', 'method', pool_size[, 'direction'])`**: Spatial downsampling via greedy BFS partitioning. Groups `pool_size` neighboring nodes, aggregates channel vectors element-wise (`max` or `avg`), keeps smallest doc_id as representative. Reduces active node count.
- **`dense(ARRAY[weights], ARRAY[bias], output_channels => N, input_channels => M)`**: Fully connected layer: `out = W @ input + bias`, then gating. Supports channel expansion (1->4) and reduction (4->2). Weight matrix reshaped from flat array to `(output_channels, input_channels)`.
- **`flatten()`**: Collapses all spatial nodes into a single vector by sorting nodes by doc_id and concatenating channel vectors. Result: 1 node with `S * C` channels.
- **`softmax()`**: Numerically stable softmax classification head (`exp(x - max(x)) / sum(exp(x - max(x)))`). Output score = max probability; full distribution stored in `Payload.fields["class_probs"]`.
- **`batch_norm([epsilon => 1e-5])`**: Per-channel normalization across all nodes to zero mean and unit variance. Stabilizes activations for deeper pipelines.
- **`dropout(p)`**: Inference-mode dropout: scales all values by `(1 - p)`. Prevents over-reliance on any single feature.
- **Vectorized helpers**: `_sigmoid_vec()` and `_apply_gating_vec()` for element-wise NumPy operations on channel vectors.
- **Validation rules**: Spatial layers (propagate, convolve, pool) must not appear after flatten. `pool_size >= 2`. `dropout p` must be in `(0, 1)`. First layer must be a SignalLayer.

### Deep Fusion: Planner Integration

- **Cardinality estimation**: PoolLayer divides cardinality by pool_size. FlattenLayer sets cardinality to 1. DenseLayer, SoftmaxLayer, BatchNormLayer, DropoutLayer are pass-through (no change in node count).
- **Cost estimation**: PoolLayer, ConvLayer, PropagateLayer cost proportional to `total_docs`. DenseLayer cost = `input_channels * output_channels`. FlattenLayer, SoftmaxLayer, BatchNormLayer, DropoutLayer cost proportional to `total_docs`.
- **EXPLAIN format**: Each new layer type displays its parameters in the plan tree: `pool='label', method='max', size=2`, `dense=M->N`, `flatten`, `softmax`, `batch_norm, eps=1e-05`, `dropout, p=0.5`.

### Deep Fusion: Showcase Examples

- **`examples/showcase/deep_fusion_resnet.py`**: Hierarchical signal layers with residual connections. Single layer, two-layer, three-layer hierarchies, gating comparison, EXPLAIN.
- **`examples/showcase/deep_fusion_gnn.py`**: Graph propagation layers for message passing. 1-hop, 2-hop, aggregation comparison, mixed layers, direction control.
- **`examples/showcase/deep_fusion_cnn.py`**: Spatial convolution over grid graphs. Weight estimation, raw vs convolved scores, stacked layers, smoothing visualization.
- **`examples/showcase/deep_fusion_nn.py`**: Complete neural network pipeline. Pooling, dense layers, flatten-dense-softmax classification, batch normalization and dropout, full CNN pipeline, EXPLAIN plan, SQL syntax summary.

### Storage Backend ABCs

- **`DocumentStore`** ABC: Abstract base class with `put`, `get`, `delete`, `clear`, `doc_ids`, `get_field`, `get_fields_bulk`, `has_value`, `eval_path`, `__len__` methods. `MemoryDocumentStore` and `SQLiteDocumentStore` implement the interface.
- **`InvertedIndex`** ABC: Abstract base class with `add_document`, `remove_document`, `get_postings`, `doc_freq`, `term_freq`, `doc_count`, `search`, and analyzer management methods. `MemoryInvertedIndex` and `SQLiteInvertedIndex` implement the interface.
- **Benchmark fix**: Updated benchmark InvertedIndex instantiation for the new ABC hierarchy.

### Deep Learning Training Pipeline

- **`deep_learn('model', label, embedding, 'edge_label', layers..., gating => 'relu', lambda => 1.0)`**: SELECT-clause aggregate function that trains a CNN classifier analytically. Layer-by-layer parameter estimation: `ConvSpec` generates Kaiming-initialized random multi-channel kernels (extreme learning machine prior), `PoolSpec`/`FlattenSpec` are stateless, `DenseSpec` fits via ridge regression `W = (X^T X + lambda I)^{-1} X^T Y` (Bayesian posterior). No backpropagation. Uses existing `HashAggOp` framework via engine-method aggregate callback — no special-casing in the SQL compiler.
- **`deep_predict('model', embedding)`**: Per-row scalar function for inference. Reconstructs the trained pipeline and runs a forward pass through conv/pool/flatten/dense/softmax layers. Returns class probabilities sorted by descending confidence.
- **`deep_fusion(model('name', $1), gating => 'relu')`**: Inference via the deep fusion operator with learned weights. `model('name', $1)` loads a trained model from the catalog and creates the full layer pipeline (EmbedLayer + ConvLayer + PoolLayer + FlattenLayer + DenseLayer + SoftmaxLayer) in a single self-contained call.
- **`build_grid_graph('table', rows, cols, 'label')`**: FROM-clause function that constructs a 4-connected grid graph (right + down edges) for spatial convolution on image data.
- **PoE (Product of Experts) local learning**: Per-stage supervised expert heads with logit averaging (Theorem 8.3) and shrinkage correction `alpha * log(n_experts)` in log-odds space (Theorem 4.4.1).
- **Multi-channel random convolution**: Random Kaiming-initialized kernels as Bayesian prior, ridge regression as posterior. Equivalent to extreme learning machines with spatial structure.
- **EmbedLayer**: Direct vector injection into the deep fusion pipeline. Supports grayscale (1-channel), RGB (3-channel), and RGBA (4-channel) images via `in_channels` parameter. Auto-detects grid dimensions from embedding dimensionality.

### Deep Learning: PyTorch GPU Acceleration

- **`uqa/operators/_backend.py`**: Backend module with automatic device detection (MPS/CUDA/CPU). Falls back to NumPy when PyTorch is not installed.
- **`ridge_solve(X, Y, lam)`**: Ridge regression via `torch.linalg.solve` on GPU (float32). NumPy fallback for CPU-only environments.
- **`grid_forward(embeddings, kernels, pool_sizes, grid_h, grid_w, in_channels, gating)`**: Batch Conv2d + MaxPool2d pipeline. Single GPU upload, single download — no GPU-CPU-GPU roundtrips. 570x speedup over per-node BFS on Apple Silicon MPS.
- **`batch_dense()`, `batch_softmax()`, `batch_batchnorm()`**: GPU-accelerated tensor operations for dense, softmax, and batch normalization layers.

### Deep Learning: Model Catalog

- **`_models` table**: SQLite-backed model persistence via `(model_name TEXT PK, config_json TEXT NOT NULL)`. Auto-migrated on catalog open.
- **`Engine.save_model()`, `Engine.load_model()`, `Engine.delete_model()`**: Dual in-memory + catalog persistence. In-memory engines use `_models` dict; persistent engines write through to SQLite.
- **`TrainedModel` dataclass**: Serializable model configuration with `to_json()` / `from_json()`. Stores conv kernel data, dense weights/bias, class labels, grid size, layer specs, expert weights, and shrinkage parameters.
- **`TrainedModel.to_deep_fusion_layers()`**: Converts trained model configuration into deep fusion layer objects for inference.

### Deep Learning: SQL Compiler Integration

- **Engine-method aggregates**: General mechanism for SELECT-clause aggregate functions backed by Engine methods. `HashAggOp.extra` accepts a callable callback. `_extract_agg_specs()` detects engine methods via `getattr(engine, func_name)` and creates a closure that receives all rows and positional/named arguments.
- **Per-row scalar functions**: `ExprEvaluator` falls back to engine method dispatch for unknown scalar functions. `deep_predict('model', embedding)` evaluates per-row on table columns.
- **`convolve(n_channels => N[, seed => S])`**: Multi-channel random conv spec with optional seed for reproducibility.
- **`model('name', $1)`**: Self-contained deep fusion layer function. Loads trained model from catalog, creates EmbedLayer with correct `in_channels`/`grid_size`, and builds the full inference pipeline.

### Deep Learning: Self-Attention (Theorem 8.3)

- **`attention(n_heads => N, mode => 'content'|'random_qk'|'learned_v')`**: Self-attention layer in `deep_learn()` and `deep_fusion()`. Paper 4, Theorem 8.3 derives attention as context-dependent Logarithmic Opinion Pooling (Product of Experts). Relaxing the uniform reliability assumption yields attention weights as expert reliability coefficients.
- **Three training modes**: `content` (Q=K=V=X, no parameters), `random_qk` (random Q,K projections as ELM prior, V=X), `learned_v` (random Q,K, supervised V projection search via ridge regression over random orthogonal candidates).
- **GPU optimization**: Adaptive chunk size (capped at 512 MB attention matrix), single-upload slicing, Q/K precomputation across V candidates, hybrid ridge solve (GPU matmul + CPU LAPACK).

### Deep Learning: Neural Network Pruning

- **`l1_ratio => 0.3`**: Elastic net (L1+L2) regularization via proximal gradient descent (ISTA). Warm-started from ridge solution for fast convergence. Creates naturally sparse weight patterns. GPU-accelerated on MPS/CUDA.
- **`prune_ratio => 0.5`**: Post-training magnitude pruning. Zeroes the smallest fraction of weights by percentile. 50% pruning retains 94.68% accuracy on MNIST (baseline 97.89%, -3.2pp).
- **Combined**: Both L1 sparsity and magnitude pruning can be applied together for maximum compression.
- **`elastic_net_solve(X, Y, lam, l1_ratio)`**: ISTA solver in `_backend.py`. Frobenius norm Lipschitz estimate, soft-threshold proximal operator.
- **`magnitude_prune(W, prune_ratio)`**: Percentile-based weight thresholding.

### Deep Learning: Parameterized INSERT

- **`INSERT INTO t (label, embedding) VALUES ($1, $2)`**: ParamRef support in `_extract_insert_value`. Numpy arrays and scalars passed directly via `params=[label, vec]`, bypassing SQL string formatting and pglast parsing. 65x faster than `ARRAY[...]` literals for vector data.

### Deep Learning: Accuracy Improvements

- **Accuracy-weighted PoE**: Expert head logits weighted by per-stage training accuracy instead of uniform average. Prevents low-accuracy early-stage experts from diluting the final head's signal.
- **Diversity-prior shrinkage**: `alpha = 1/(2*sqrt(n_experts))` from neural-index research. Corrects for conjunction shrinkage in Product of Experts combination.
- **Batched grid_forward**: 2048-sample mini-batches prevent GPU OOM on large datasets. MPS INT_MAX fallback for ridge_solve when tensor exceeds 2^31 elements.
- **Tiny ImageNet**: 50 classes (was 10), 64/128/256 channels (was 16/32), 3-stage pool(2) (was 2-stage pool(4)), horizontal flip augmentation (2x training data), lambda=500. ~30% test accuracy (was ~22%, random baseline 2%).

### Deep Learning: Showcase Examples

- **`examples/showcase/deep_learn_mnist.py`**: Full MNIST pipeline (60,000 train, 10,000 test). Architecture: conv(32ch) -> pool(2) -> conv(64ch) -> pool(2) -> flatten -> dense(10) -> softmax. Training via `SELECT deep_learn(...) FROM mnist_train`. Inference via both `deep_predict()` and `deep_fusion(model())`. Parameterized INSERT for data loading. 97.89% test accuracy.
- **`examples/showcase/deep_learn_tiny_imagenet.py`**: Tiny ImageNet pipeline (50 classes, 500 train/class + flip augmentation, 50 val/class, 64x64 RGB). Architecture: conv(64ch) -> pool(2) -> conv(128ch) -> pool(2) -> conv(256ch) -> pool(2) -> flatten -> dense(50) -> softmax. ~30% test accuracy on 50-class subset (random baseline 2%).
- **`examples/showcase/deep_learn_attention.py`**: Self-attention on MNIST. Three modes (content, random_qk, learned_v), GPU-optimized chunked attention, PoE training pipeline with attention expert heads.
- **`examples/showcase/deep_learn_mnist_pruning.py`**: Neural network pruning on MNIST. Elastic net sweep (l1_ratio 0.1-0.7), magnitude pruning sweep (prune_ratio 0.5-0.9), combined configurations, accuracy vs sparsity summary table.

### Deep Learning: Tests

- **25 tests** in `uqa/tests/test_deep_learn.py`: ridge regression correctness (4), LayerSpec/TrainedModel serialization (3), Python API train+predict (3), SQL aggregate syntax (4), PoE deep_predict/deep_fusion compatibility (2), model catalog persistence (2), pruning (4), self-attention (3).
- **3 parameterized INSERT tests** in `uqa/tests/test_sql.py`: scalar params, vector params, missing param error.

### CI and Tooling

- **Pyright pre-commit hook**: Local system pyright added to `.pre-commit-config.yaml`. Uses project's `pyproject.toml` settings (basic mode, `uqa/` directory).
- **NDArray type annotations**: `ridge_solve`, `_build_kernel_np`, `hop_weights_to_kernel`, `_generate_kernels` return `NDArray[np.floating]` or `NDArray[np.float32]` for correct `.tolist()` type inference.
- **`convolve()` direction validation**: SQL compiler validates direction argument must be `'both'`, `'out'`, or `'in'`.

## 0.20.1 (2026-03-18)

Named graph support for centrality signal functions in WHERE clause and fusion contexts.

### Named Graph Support in Signal Context

- **`pagerank([damping[, iter[, tol]]][, 'graph'])`**: Accepts an optional graph name in WHERE clause and fusion signal contexts. Previously only the FROM-clause variant accepted a graph name; signal functions implicitly used the current table's graph.
- **`hits([iter[, tol]][, 'graph'])`**: Same named graph support in signal context.
- **`betweenness(['graph'])`**: Same named graph support in signal context.
- **`_split_centrality_args()`**: Shared helper that separates numeric arguments from the string graph name argument. Falls back to `_current_graph_name` when no string argument is provided.

## 0.20.0 (2026-03-18)

Named graphs as primary abstraction, index-aware Bayesian calibration of vector similarity scores (Paper 5), performance regression fixes, and 20 paper-to-code improvements across all five papers. Named graphs replace the flat global graph store with per-graph partitioned adjacency indexes. Graph operators, indexes, and SQL functions are graph-scoped. Three new showcase examples demonstrate cross-paradigm unification, Bayesian calibration, and neural network emergence.

### Showcase Examples

- **`examples/showcase/knowledge_discovery.py`**: Progressive four-paradigm unification with 15 landmark ML papers. Demonstrates SQL filtering, FTS (text_match/bayesian_match), vector KNN, graph (PageRank/RPQ), Cypher pattern matching, three-signal log-odds fusion with relational filter, and EXPLAIN plans showing unified posting list operators.
- **`examples/showcase/calibration_matters.py`**: Side-by-side comparison of naive score addition vs Bayesian fusion. Shows signal dominance (BM25 >> cosine similarity), four fusion strategies (naive/log_odds/prob_and/prob_or), CalibrationMetrics (ECE, Brier, reliability diagram), and online parameter learning.
- **`examples/showcase/bayesian_neural.py`**: Step-by-step demonstration that Bayesian multi-signal fusion IS a feedforward neural network (Paper 4). Traces raw scores through sigmoid calibration, logit transform, linear aggregation, and sigmoid output. Compares gating functions (none/ReLU/Swish), fuse_attention as Logarithmic Opinion Pooling, and staged_retrieval as multi-layer depth.

### Vector Calibration (Paper 5)

- **Likelihood ratio calibration**: Transforms raw cosine similarities into calibrated relevance probabilities via `log(f_R(d) / f_G(d)) + logit(P_base)` (Theorem 3.1.1).
- **`VectorProbabilityTransform`** integration from bayesian-bm25 package: KDE and GMM-EM estimation of f_R, KDE-based f_G from IVF probed-cell distances.
- **`CalibratedVectorOperator`**: End-to-end calibrated KNN with four weight sources — Bayesian BM25 cross-modal (Section 4.3), IVF density prior (Strategy 4.6.2), distance gap detection (Strategy 4.6.1), uniform fallback.
- **IVF index statistics**: `cell_populations()`, `probed_distances()`, `background_stats`, `background_samples`, `_centroid_id` in search results.
- **SQL**: `bayesian_knn_match(field, vector, k [, named options])` with `method`, `weight_source`, `base_rate` options. `knn_match` inside fusion auto-upgrades when IVF background stats are available.
- **QueryBuilder**: `.bayesian_knn()` with `weight_source`, `bm25_query`, `bm25_field`, `bandwidth_scale` parameters.
- **`CalibrationMetrics.log_loss()`**: Negative log-likelihood scoring rule (Section 8.3).
- **SQL compiler**: `_extract_int_value()` supports `ParamRef` (`$N` parameters).

### Performance Regression Fixes

- **GraphStore partition cache**: Single-entry `_cached_partition` with identity comparison replaces per-call `_graphs.get(graph)` dict lookup. `_require_graph` consolidated into `_get_partition`. Neighbors benchmarks recovered +23% over original baseline.
- **SortOp Arrow threshold**: `_ARROW_SORT_THRESHOLD = 5000` skips dict-to-Arrow-to-dict roundtrip for small batches where the conversion cost dominates. Sort benchmarks recovered +20% over original baseline.
- **DPccp join cost**: Module-level `_log2` binding and inline comparisons replace `math.log2()` and `min()`/`max()` calls in the O(3^n) inner loop. DPccp star[5] recovered +37% over original baseline.

### Configurable Graph Operator Scores

- **`DEFAULT_GRAPH_SCORE`**: Module-level constant in `uqa/graph/operators.py` (default 0.9). All graph operators now accept an optional `score` parameter instead of hard-coding `Payload(score=0.9)`.
- **`TraverseOperator(score=...)`**, **`PatternMatchOperator(score=...)`**, **`RegularPathQueryOperator(score=...)`**, **`WeightedPathQueryOperator(score=...)`**: Configurable graph contribution to log-odds fusion without source modification.
- **`TemporalTraverseOperator(score=...)`**, **`TemporalPatternMatchOperator(score=...)`**: Same treatment for temporal graph operators.

### Hierarchical Operator Cost Estimation

- **`PathFilterOperator.cost_estimate()`**: Source cost or full scan cost (Paper 1, Section 6.2).
- **`PathProjectOperator.cost_estimate()`**: Streaming map, same cost as source.
- **`PathUnnestOperator.cost_estimate()`**: Source cost with 2x fan-out factor for array expansion.
- **`PathAggregateOperator.cost_estimate()`**: Streaming aggregate, same cost as source.
- **`UnifiedFilterOperator.cost_estimate()`**: Dispatches cost estimate to delegate.

### Log-Odds Mean Aggregation

- **`LogOddsFusion.fuse_mean()`**: Scale-neutral log-odds mean (Definition 4.1.1, Paper 4). Computes the arithmetic mean in log-odds space and maps back via sigmoid without confidence scaling (no `n^alpha` amplification). Distinct from `fuse()` which applies Theorem 4.4.1 amplification. Implements the normalized Logarithmic Opinion Pool (Theorem 4.1.2a).

### Quantile Aggregation Monoid

- **`QuantileMonoid`**: Percentile aggregation monoid (Paper 1, Section 5.1). Supports median (`quantile=0.5`), P95 (`quantile=0.95`), and arbitrary quantiles with linear interpolation. Monoid contract: `combine()` concatenates value lists for parallel decomposition (Theorem 5.1.5).

### Algebraic Simplification Rules

- **`QueryOptimizer._simplify_algebra()`**: Four equivalence-preserving algebraic rewrite rules (Paper 1, Theorem 6.1.2):
  - **Idempotent intersection**: `Intersect(A, A, ...)` removes duplicate operands by identity.
  - **Idempotent union**: `Union(A, A, ...)` removes duplicate operands.
  - **Absorption law**: `Union(A, Intersect(A, B))` simplifies to `A`; `Intersect(A, Union(A, B))` simplifies to `A`.
  - **Empty elimination**: `Intersect(A, empty)` yields empty; `Union(A, empty)` drops empty children.
- Applied first in the optimizer pipeline before filter pushdown and other rewrites.

### Histogram-Based Entropy Estimation

- **`_column_entropy()`** enhanced: When equi-depth histogram bounds are available (but no MCVs), computes entropy from bucket count: `log2(num_buckets)`. Three-tier priority: MCV frequencies > histogram buckets > uniform assumption.

### Named Graphs

- **`_GraphPartition`**: Per-named-graph adjacency state (vertex_ids, edge_ids, adj_out, adj_in, label_index, vertex_label_index). Vertices and edges are stored globally; adjacency indexes are per-graph with zero duplication.
- **`GraphStore` redesign**: All mutations and queries require `graph` keyword parameter. Graph lifecycle (create_graph, drop_graph, has_graph, graph_names). Graph algebra (union_graphs, intersect_graphs, difference_graphs, copy_graph). Per-graph statistics (degree_distribution, label_degree, vertex_label_counts).
- **`SQLiteGraphStore`**: `_graph_catalog` and `_graph_membership` tables for persistence. Named graphs survive close/reopen.
- **SQL function syntax**: `traverse(start, 'label', hops, 'graph_name')` — direct graph name without `graph:` prefix (backward compatible). Same for `rpq()`, `temporal_traverse()`, `pagerank()`, `hits()`, `betweenness()`.
- **`_NamedGraphOperatorWrapper` removed**: All graph operators accept `graph` directly.
- **`GraphPayload.graph_name`**: Graph provenance tracked in posting list payloads.

### Graph Join Operators

- **`GraphGraphJoinOperator`**: Hash join on shared vertex variable between two graph posting lists. Merges GraphPayload metadata (union of subgraph_vertices/edges).
- **`CrossParadigmGraphJoinOperator`**: Joins graph posting list with relational posting list on vertex_field/doc_field match.

### GeneralizedPostingList Operations

- **`intersect()`**, **`difference()`**, **`complement()`**: Two-pointer merge on `doc_ids` tuples for GeneralizedPostingList (join results).
- **`doc_ids_set`** property, **`__and__`**/**`__or__`**/**`__sub__`** operator overloads.

### Semi-Join / Anti-Join

- **`SemiJoinOperator`**: Returns left entries with a match in right (existence check only).
- **`AntiJoinOperator`**: Returns left entries without a match in right.
- Hash join pattern with optional custom condition callable.

### Property Indexes

- **`VertexPropertyIndex`**: Equality (O(1) hash) + range (O(log n) bisect) index on vertex properties.
- **`EdgePropertyIndex`**: Same pattern for edge properties.
- Per-graph scoped via `build(graph_store, *, graph, properties)`.

### Category-Theoretic Functors

- **`Functor`** ABC with `map_object` and `map_morphism`.
- **`GraphToRelationalFunctor`**, **`RelationalToGraphFunctor`**, **`TextToVectorFunctor`**.
- Identity law and composition law verified via property tests.

### Adaptive Confidence Scaling

- **`SignalQuality`**: Coverage ratio, score variance, calibration error metrics per signal.
- **`AdaptiveLogOddsFusion`**: Per-signal confidence alpha computed from quality metrics.
- **`AdaptiveLogOddsFusionOperator`**: Quality-weighted log-odds fusion in the operator tree.

### WAND Bound Tightness

- **`BoundTightnessAnalyzer`**: Tracks upper bound vs actual max for tightness ratio and slack analysis.
- **`AdaptiveWANDScorer`**: Configurable tightening factor on upper bounds with empirical tightness tracking.
- **`TightenedFusionWANDScorer`**: Tightened bounds for multi-signal fusion WAND.

### Graph Cost Model & Cardinality

- **`GraphStats`** enhanced: `vertex_label_counts`, `degree_distribution`, `label_degree_map`, `graph_name`. `from_graph_store(gs, *, graph)` computes per-graph statistics.
- **`CostModel(graph_stats)`**: Traverse `O(sum d^i)`, PatternMatch `O(V^k)`, RPQ `O(V^2 * |R|)` with `_expr_label_count()`.
- **`CardinalityEstimator`**: Label-specific degree for traverse, vertex label selectivity for pattern match, NFA state count for RPQ.

### Pattern Negation

- **`EdgePattern.negated: bool`**: Negated edges skip arc consistency, are processed after positive edges, and invert validation (edge must NOT exist).
- Cost model adds `(1 + 0.2 * negated_count)` overhead.

### Distributivity & De Morgan

- Property-based tests (Hypothesis) for De Morgan's laws on PostingList and GeneralizedPostingList.
- `NOT (A AND B) == (NOT A) OR (NOT B)` and `NOT (A OR B) == (NOT A) AND (NOT B)` verified.

### Information-Theoretic Bounds

- **`_column_entropy()`**: Entropy from histogram or MCV frequencies.
- **`_mutual_information_estimate()`**: MI from column entropies and joint selectivity.
- **`_entropy_cardinality_lower_bound()`**: `n * 2^(-sum H_i)` floors intersection estimates.
- Filter selectivity clamped by `1/2^H(column)`.
- Intersection damping uses MI-based correlation detection.

### RPQ Optimization

- **`_simplify_expr()`**: `a|a -> a`, `(a*)* -> a*`, `a*|a -> a*`, `a*/a* -> a*`, alternation sorting.
- **`_subset_construction()`**: NFA to DFA for small NFAs (<= 32 states).
- **`RPQOperator.execute()`** integrated: simplify -> NFA -> optional DFA -> simulate.
- **`_simulate_dfa()`**: Deterministic BFS without epsilon closures.

### Cross-Paradigm Optimizer

- **`QueryOptimizer(stats, graph_stats=...)`**: Graph statistics forwarded to CostModel and CardinalityEstimator.
- **Filter pushdown into traverse**: Vertex property filters absorbed into `TraverseOperator.vertex_predicate` for BFS pruning.
- **Filter below graph join**: Filters pushed below `GraphJoinOperator` to reduce join input size.
- **Graph-aware fusion reordering**: Graph operators receive 0.5x cost discount when graph_stats available.

## 0.19.0 (2026-03-16)

Full query pushdown for Foreign Data Wrappers. Queries over foreign tables are now delegated entirely to the data source (DuckDB or Arrow Flight SQL) instead of materializing rows in Python. Mixed foreign-local queries ship small local tables to DuckDB for in-process execution. All 2318 tests, 30 examples, and 295 benchmarks pass.

### FDW Full Query Pushdown

- **DuckDB full pushdown**: When every table in a SELECT references the same DuckDB server, the AST is deparsed back to SQL via `pglast.stream.RawStream` and executed directly on DuckDB. Covers SELECT, WHERE, JOIN, GROUP BY, HAVING, ORDER BY, LIMIT, DISTINCT, window functions, subqueries, and CTEs.
- **Arrow Flight SQL full pushdown**: Same-server pure-foreign queries deparse the AST to SQL, substitute table names with source expressions, and send the rewritten SQL to the Flight SQL endpoint. JOINs, aggregates, and window functions are handled natively by the remote server.
- **Mixed foreign-local pushdown**: When a query JOINs foreign tables with local UQA tables (e.g., a 41M-row Parquet fact table with a 263-row dimension table), local tables are shipped to DuckDB as temp tables via PyArrow, and the full query executes in DuckDB. Local tables larger than 100K rows fall through to the UQA pipeline.
- **AST table reference walker**: `_collect_ast_table_refs()` recursively walks the full pglast AST (FROM, JOINs, subqueries, CTEs) to classify every referenced table as foreign or local.
- **EXPLAIN bypass**: EXPLAIN queries skip the pushdown path to produce UQA plan trees.
- **Automatic fallback**: If DuckDB cannot execute the pushed query (e.g., UQA-specific functions like `spatial_within`), the pushdown returns `None` and the standard UQA operator pipeline takes over.

### FDW Handler Extensions

- **`limit` parameter**: `FDWHandler.scan()`, `DuckDBFDWHandler.scan()`, and `ArrowFlightSQLFDWHandler.scan()` accept an optional `limit` for row-count pushdown.
- **Batch Arrow-to-PostingList conversion**: `_ForeignTableScanOperator.execute()` uses `to_pylist()` per column instead of row-by-row `as_py()` calls, significantly reducing Python overhead for the fallback path.

### Infrastructure

- **`data/download_nyc_taxi.sh`**: Download script for NYC TLC Yellow Taxi trip data (Parquet). Supports yellow/green/fhv/fhvhv types, configurable year and month range, idempotent downloads with HTTP status checking.

## 0.18.1 (2026-03-15)

- **PostingList.difference()**: Reverted to set-based lookup. The two-pointer merge caused a 5-7x regression in difference benchmarks (34K -> 4K iter/sec at size=1000) because CPython's C-level `set.__contains__` outperforms a Python-level while loop. The `__new__` bypass is retained.

## 0.18.0 (2026-03-15)

8 paper-driven optimizations closing gaps between the formal algorithms/complexity bounds in Papers 1 — 4 and the codebase. Replaces set-based PostingList.difference() with O(|A|+|B|) two-pointer merge, adds early termination to IntersectOperator, introduces predicate-aware damping in cardinality estimation, makes the DPccp cost model join-algorithm-aware (index join vs hash join), switches vector threshold merging to np.allclose for floating-point tolerance, converts intersection reordering from cardinality-based to cost-based, enables recursive filter pushdown through nested IntersectOperators, and integrates PathIndex into the Cypher MATCH compiler for O(1) pattern resolution. All 2318 tests, 29 examples, and 295 benchmarks pass.

### PostingList Two-Pointer Difference (Paper 1, Theorem 2.1.2)

- **PostingList.difference()**: Replaced O(|B|) set construction with O(|A|+|B|) two-pointer merge, matching the existing `union()` and `intersect()` implementations
- **GeneralizedPostingList.union()**: Replaced set-based deduplication with two-pointer merge, bypassing `__init__` sort via `__new__` pattern

### IntersectOperator Early Termination (Paper 1, Section 6.2)

- **Sequential path**: Execute operands one at a time; return empty immediately when the accumulator becomes empty, skipping all remaining operands
- **Parallel path**: Short-circuit the `intersect()` reduction loop after `par.execute_branches()` completes
- Combined with cost-based reordering (below), places cheap operators first to maximize early termination probability

### Predicate-Aware Cardinality Damping (Paper 1, Definition 6.2.3)

- **`_intersection_damping()`**: Extracts field names from FilterOperator children to detect predicate correlation
- Same-column predicates (e.g., `age > 30 AND age < 50`): exponent 0.1 (high correlation, minimal additional reduction)
- Different-column predicates: exponent 0.5 (standard sqrt damping, independence assumption)
- Replaces the fixed `sel**0.5` with `sel**damping` where damping is predicate-aware

### DPccp Join Algorithm Awareness (Paper 1, Section 6.2)

- **`_emit_csg_cmp_pair()`**: When `min(|L|, |R|) <= INDEX_JOIN_THRESHOLD` (100), uses index join cost `min_card * log2(max_card + 1)` instead of hash join cost `|L| + |R|`
- **`_greedy_optimize()`**: Same formula applied for consistency in the greedy fallback path
- Eliminates cost model mismatch where DPccp planned hash join but runtime selected index join

### Vector Threshold Merge Tolerance (Paper 1, Theorem 6.1.2)

- Replaced `np.array_equal()` with `np.allclose(rtol=1e-7, atol=1e-9)` in `_merge_vector_thresholds()`
- Semantically identical vectors with tiny floating-point differences now merge correctly into `V_max(theta1, theta2)(q)`

### Cost-Based Intersection Reordering (Paper 1, Section 6.2)

- Added `CostModel` instance to `QueryOptimizer`
- Changed `_reorder_intersect()` sort key from `CardinalityEstimator.estimate()` to `CostModel.estimate()`
- Ensures cheap operators (e.g., TermOperator) execute before expensive operators (e.g., VectorSimilarityOperator) regardless of their output cardinality

### Recursive Filter Pushdown (Paper 1, Theorem 6.1.2)

- `_push_filters_down()` now recursively calls itself on newly created operands before `_recurse_children()`
- `_filter_applies_to()` extended to recursively check inside IntersectOperator children
- `Filter(Intersect(Intersect(T1, T2), T3))` now pushes the filter to all three leaf operators

### PathIndex in Cypher MATCH (Paper 2, Section 9.1)

- **CypherCompiler**: Added `path_index` parameter; `_try_path_index_match()` resolves simple MATCH patterns via pre-computed (start, end) pairs in O(1)
- Guard checks: falls back to BFS for patterns with relationship properties, multiple types, variable-length hops, or constrained intermediate nodes
- **CypherQueryOperator**: Passes `path_index` from execution context to the compiler
- Mirrors `RegularPathQueryOperator._try_index_lookup()` for consistent PathIndex integration across graph paradigms

## 0.17.0 (2026-03-14)

12 paper-derived improvements fully connecting the theoretical foundations from Papers 1 — 4 into the query engine. Adds graph centrality scoring (PageRank, HITS, Betweenness), fusion gating mechanisms (ReLU/Swish), bounded RPQ with aggregate predicates, edge property filter pushdown, join-pattern fusion, cross-paradigm join cost models, threshold-aware vector selectivity, temporal graph cardinality correction, subgraph indexing, incremental pattern matching, random-walk graph sampling for cardinality estimation, and progressive multi-stage WAND fusion. All new features are exposed as SQL functions. All 2305 tests, 29 examples, and 295 benchmarks pass.

### Graph Centrality (Paper 2, Section 9.1)

- **PageRank Operator**: Power iteration with configurable damping (default 0.85), min-max normalized scores in [0, 1]; cost model `O(N * iterations)`
- **HITS Operator**: Hub/authority mutual reinforcement with L2 normalization; `Payload.fields["hub_score"]` and `Payload.fields["authority_score"]`; cost model `O(N * iterations * 2)`
- **Betweenness Centrality Operator**: Brandes algorithm `O(|V| * |E|)` for unweighted directed graphs; normalized by `(N-1) * (N-2)`, clamped to [0, 1]
- All three operators integrated into cost model, cardinality estimator, and SQL compiler
- SQL WHERE functions: `pagerank()`, `hits()`, `betweenness()` as scored filter signals
- SQL FROM functions: `SELECT ... FROM pagerank()`, `FROM hits()`, `FROM betweenness()` as table sources
- Named graph support: `pagerank('graph:name')`, `hits('graph:name')`, `betweenness('graph:name')`

### Fusion Gating (Paper 4, Section 6.5 — 6.7)

- **ReLU/Swish gating** threaded through `LogOddsFusion`, `LogOddsFusionOperator`, `FusionWANDScorer`, optimizer, and SQL compiler
- SQL syntax: `fuse_log_odds(sig1, sig2, 'relu')` or `fuse_log_odds(sig1, sig2, 0.8, 'swish')` (alpha + gating combined)
- Optimizer preserves gating parameter during signal reordering

### Bounded RPQ and Weighted Paths (Paper 2, Section 5.1)

- **BoundedLabel** dataclass: `e{min,max}` syntax parsed by `parse_rpq()`; NFA construction chains mandatory + optional copies with epsilon bypass
- **WeightedPathQueryOperator**: NFA simulation carrying cumulative edge weight `(vertex, nfa_states, weight)`; configurable `aggregate_fn` (sum/max/min) and callable `predicate` for accepting-state filtering
- Cost and cardinality integration for `WeightedPathQueryOperator` (RPQ estimate * 0.5 selectivity)
- SQL function: `weighted_rpq('expr', start, 'prop'[, 'agg'[, threshold]])` in WHERE clause

### Optimizer Improvements (Paper 2, Theorems 6.1.1 — 6.1.2)

- **Edge property filter pushdown**: Filters on `"src_tgt.property"` (e.g., `"a_b.since"`) pushed into `EdgePattern.constraints` during pattern matching, eliminating post-filtering
- **Join-pattern fusion**: `IntersectOperator` with 2+ `PatternMatchOperator` children sharing vertex variables merged into single `PatternMatchOperator`; deduplicates vertex patterns and combines constraints

### Cross-Paradigm Cost and Cardinality (Paper 1, Section 4 — 5)

- **Join cost models**: `TextSimilarityJoinOperator`, `VectorSimilarityJoinOperator`, `GraphJoinOperator`, `HybridJoinOperator`, `CrossParadigmJoinOperator` with domain-specific cost formulas
- **Join cardinality**: Jaccard selectivity (0.05), vector selectivity (0.1), graph average degree, and hybrid formulas
- **Vector selectivity estimation** (Paper 1, Section 5.3): Threshold-aware tiers (0.9 -> 1%, 0.7 -> 5%, 0.5 -> 10%, <0.5 -> 20%)
- **Temporal cardinality correction** (Paper 2, Section 8): `GraphStats.min_timestamp`/`max_timestamp` + `_temporal_selectivity()` applied to traverse and pattern match estimates

### Subgraph Indexing and Incremental Matching (Paper 2, Section 9)

- **SubgraphIndex**: Pre-indexed frequent subgraph patterns with O(1) lookup via canonical key; `build()`, `lookup()`, `invalidate()` by affected edge labels; `PatternMatchOperator` checks cache before backtracking
- **IncrementalPatternMatcher**: Delta-aware pattern matching with 3-step update (invalidate affected matches, re-match constrained to affected vertices, merge); `GraphDelta` dataclass
- **Graph sampling** (Paper 2, Section 6.3): Random walk sampling for cardinality estimation on graphs with 10000+ vertices; falls back to formula-based when graph_store unavailable

### Progressive Fusion (Paper 4, Section 7)

- **ProgressiveFusionOperator**: Cascading multi-stage fusion with WAND pruning; each stage introduces new signals and narrows candidates via top-k cutoff; gating parameter forwarded to `FusionWANDScorer`
- Cascading cost model: each stage cost proportional to candidate survival ratio
- SQL function: `progressive_fusion(sig1, sig2, k1, sig3, k2[, alpha][, 'gating'])` in WHERE clause

### SQL Graph Mutation Functions

- **`graph_add_vertex(id, 'label', 'table'[, 'key=val,...'])`**: Add graph vertex via SQL (FROM-clause table function)
- **`graph_add_edge(eid, src, tgt, 'label', 'table'[, 'key=val,...'])`**: Add graph edge via SQL (FROM-clause table function)
- All centrality and graph SQL functions support both per-table and named graph (`'graph:name'`) sources

### Bug Fixes

- **PostingListScanOp title=None fix**: Graph operators with `payload.fields` (e.g., HITS hub/authority scores) now correctly look up document store columns first, then overlay operator fields, fixing `title=None` for centrality FROM queries

### Examples and Benchmarks

- **`examples/fluent/graph_centrality.py`**: 9 sections demonstrating PageRank, HITS, betweenness, bounded RPQ, weighted paths, subgraph indexing, incremental matching
- **`examples/sql/fusion_gating.py`**: 8 sections demonstrating ReLU/Swish gating, alpha+gating, three-signal gating, staged retrieval, gating+relational filters
- **`examples/sql/graph_centrality.py`**: 16 sections demonstrating pagerank/hits/betweenness SQL, bounded RPQ, weighted RPQ, progressive fusion, graph_add_vertex/edge, named graph centrality — 100% SQL via `engine.sql()`
- **`benchmarks/bench_graph_centrality.py`**: 23 benchmarks across 9 test classes covering all new operators and SQL functions

## 0.16.0 (2026-03-14)

12 paper-derived features connecting all theoretical building blocks from Papers 1 — 4 into the UQA engine. Adds calibration diagnostics, online parameter learning, multi-field scoring, attention-based and learned fusion, multi-signal WAND pruning, multi-stage retrieval pipelines, external prior integration, sparse thresholding, path index acceleration, incremental graph maintenance with versioned rollback, temporal graph operations, and GNN message-passing aggregation. All 2230 tests, 26 examples, and 269 benchmarks pass.

### Scoring

- **Calibration Metrics** (Paper 3 S11.3): `CalibrationMetrics` class wrapping `bayesian_bm25` ECE, Brier score, reliability diagram; `Engine.calibration_report()` for end-to-end calibration diagnostics
- **Online Parameter Learning** (Paper 3 S8): `ParameterLearner` wrapping `BayesianProbabilityTransform.fit()`/`.update()` for batch and online calibration; `Engine.learn_scoring_params()`, `Engine.update_scoring_params()`; `QueryBuilder.learn_params()`
- **External Prior Features** (Paper 3 S12.2 #6): `ExternalPriorScorer` combining BM25 likelihood with document-level priors via log-odds addition; `recency_prior()` and `authority_prior()` helper factories; `bayesian_match_with_prior()` SQL function; `QueryBuilder.score_bayesian_with_prior()`
- **Multi-Field Bayesian BM25** (Paper 3 S12.2 #1): `MultiFieldBayesianScorer` with per-field (alpha, beta, base_rate) calibration and cross-field weighted log-odds fusion; `MultiFieldSearchOperator`; `multi_field_match()` SQL function; `QueryBuilder.score_multi_field_bayesian()`
- **Sparse Thresholding / ReLU-as-MAP** (Paper 4 S6.5): `SparseThresholdOperator` applying `max(0, score - threshold)` to exclude zero-evidence documents; `sparse_threshold()` SQL function; `QueryBuilder.sparse_threshold()`

### Fusion

- **Attention-Based Fusion** (Paper 4 S8): `AttentionFusion` wrapping `AttentionLogOddsWeights` with query-feature-dependent attention weights via softmax over `W @ query_features`; `QueryFeatureExtractor` computing [mean_idf, max_idf, min_idf, coverage_ratio, query_length, vocab_overlap_ratio]; `AttentionFusionOperator`; `fuse_attention()` SQL function; `QueryBuilder.fuse_attention()`; state_dict/load_state_dict for persistence
- **Learned Fusion** (Paper 4 S8): `LearnedFusion` wrapping `LearnableLogOddsWeights` for per-signal weights without query features; `LearnedFusionOperator`; `fuse_learned()` SQL function; `QueryBuilder.fuse_learned()`
- **Multi-Signal WAND Pruning** (Paper 4 S8.7): `FusionWANDScorer` using per-signal upper bounds for safe fused pruning (log_odds_conjunction monotonicity); `LogOddsFusionOperator` gains optional `top_k` parameter that delegates to WAND
- **Multi-Stage Inference Pipeline** (Paper 4 S9): `MultiStageOperator` with cascading (operator, cutoff) stages where cutoff is top-k (int) or threshold (float); `staged_retrieval()` SQL function; `QueryBuilder.multi_stage()`

### Graph

- **Path Index Integration** (Paper 2 S9.1): `PathIndex` connected to `RegularPathQueryOperator` for O(1) RPQ lookups on simple Concat-of-Labels expressions; `Engine.build_path_index()` / `get_path_index()` / `drop_path_index()`; catalog persistence via `_path_indexes` table; `ExecutionContext.path_index` field; cost model uses reduced cost for indexable RPQs
- **Incremental Graph Maintenance** (Paper 2 S9.3): `GraphDelta` recording add/remove vertex/edge operations with `affected_vertex_ids()` and `affected_edge_labels()`; `VersionedGraphStore` with `apply()`/`rollback()` and inverse delta storage; `Engine.apply_graph_delta()` with automatic path index invalidation
- **Temporal Graphs** (Paper 2 S10): `TemporalFilter` checking `valid_from`/`valid_to` edge properties for point-in-time or range queries; `TemporalTraverseOperator` and `TemporalPatternMatchOperator` pushing temporal filter into edge constraints; `temporal_traverse()` SQL function; `QueryBuilder.temporal_traverse()`
- **GNN Message Passing** (Paper 2 + Paper 4): `MessagePassingOperator` with k-layer neighbor feature aggregation (mean/sum/max) and sigmoid calibration; `GraphEmbeddingOperator` computing structural embeddings from degree, label distribution, and k-hop connectivity; `message_passing()` and `graph_embedding()` SQL functions; `QueryBuilder.message_passing()`

### Integration

- **SQL compiler**: 9 new WHERE-clause functions (`sparse_threshold`, `multi_field_match`, `fuse_attention`, `fuse_learned`, `staged_retrieval`, `bayesian_match_with_prior`, `temporal_traverse`, `message_passing`, `graph_embedding`)
- **QueryBuilder**: 12 new fluent methods (`sparse_threshold`, `score_multi_field_bayesian`, `fuse_attention`, `fuse_learned`, `multi_stage`, `learn_params`, `score_bayesian_with_prior`, `temporal_traverse`, `message_passing`, and 3 Engine-level methods)
- **Planner**: CostModel, CardinalityEstimator, PlanExecutor, and QueryOptimizer updated for all 10 new operator types
- **Catalog**: `_path_indexes` table for path index persistence

### Tests, Examples, and Benchmarks

- 212 new tests across 12 test files (2230 total)
- 7 new example files (4 SQL + 3 fluent API)
- 5 new benchmark files with 77 benchmark tests (269 total)

## 0.15.0 (2026-03-14)

Comprehensive performance optimization across 4 layers (Core Engine, SQL Compiler, Storage, Graph/Search), plus the `@@` full-text search operator with a query string mini-language supporting boolean logic, phrase search, field targeting, and hybrid text+vector fusion via log-odds. All 2018 tests, 20 examples, and 192 benchmarks pass.

### Full-Text Search `@@` Operator

- **Query string mini-language**: `column @@ 'query'` parses a query string supporting bare terms, quoted phrases (`"..."`), field targeting (`field:term`, `field:"phrase"`), vector literals (`field:[0.1, 0.2]`), boolean operators (`AND`, `OR`, `NOT`), implicit AND for adjacent terms, and parenthesized grouping with correct precedence (NOT > AND > OR)
- **Recursive descent parser**: `FTSParser` in `uqa/sql/fts_query.py` with lexer, AST nodes (`TermNode`, `PhraseNode`, `VectorNode`, `AndNode`, `OrNode`, `NotNode`), and AST-to-operator compiler
- **Posting-list-native compilation**: each AST node maps to existing UQA operators —`TermNode` to `TermOperator` + `ScoreOperator(BayesianBM25)`, `PhraseNode` to `IntersectOperator` + `ScoreOperator`, `VectorNode` to `_CalibratedKNNOperator`, `OrNode` to `UnionOperator`, `NotNode` to `ComplementOperator`
- **Hybrid text+vector AND**: when AND mixes text and vector signals, `LogOddsFusionOperator` is used for calibrated probability fusion; pure-text AND uses `IntersectOperator`
- **`_all` column support**: `WHERE _all @@ 'query'` searches all text columns
- **SQL integration**: pglast parses `@@` as `A_Expr(kind=AEXPR_OP, name='@@')`; `_compile_comparison` dispatches to `compile_fts_match()`

### Correctness

- **Double-stemming fix**: `_make_text_search_op` was pre-analyzing the query into stemmed tokens, then passing them to `TermOperator` which re-analyzed internally. For terms where Porter stemming is not idempotent (e.g., `database` -> `databas` -> `databa`), the second stemming produced a token absent from the index, returning zero results. Fixed by passing the raw query string to a single `TermOperator` (which handles tokenization internally) and using pre-analyzed terms only for `ScoreOperator` IDF computation.
- **WAND doc_length bug fix**: `WANDScorer` and `BlockMaxWANDScorer` were passing term frequency as document length to `BM25Scorer.score()`, producing incorrect BM25 length normalization. Both scorers now accept an optional `inverted_index` parameter and look up actual document lengths per field.

### Storage

- **SQLite PRAGMAs**: add `synchronous=NORMAL`, `cache_size=-8000` (8 MB), `temp_store=MEMORY`, `mmap_size=268435456` (256 MB) for faster I/O
- **Bulk prefetch**: `ScoreOperator` and `FilterOperator` now batch-fetch doc lengths, term frequencies, and field values via new `get_doc_lengths_bulk`, `get_term_freqs_bulk`, and `get_fields_bulk` methods on both in-memory and SQLite-backed stores, eliminating N+1 query patterns
- **IVF vectorization**: brute-force KNN and threshold search replaced with NumPy matrix multiplication (`data @ q`) and `np.argpartition` for top-k selection; k-means centroid update uses `np.add.at` and `np.bincount`
- **IVF batch SQL**: centroid persistence and vector reassignment use `executemany`; IVF KNN/threshold scan uses single `WHERE centroid_id IN (...)` query instead of N per-centroid queries
- **Block-max index**: `save_to_sqlite` uses `executemany` for batch INSERT
- **SQLite graph store**: `_load_from_sqlite` uses cursor iteration instead of `fetchall()`
- **Deferred skip pointer rebuild**: `remove_document` adds affected (field, term) pairs to `_dirty_terms` instead of rebuilding skip pointers immediately; flush happens on next query
- **Selective skip pointer flush**: `get_posting_list` flushes only the specific (field, term) being queried, not all dirty terms
- **Cross-field UNION ALL**: `get_total_term_freq` and `doc_freq_any_field` in `SQLiteInvertedIndex` use a single `UNION ALL` query instead of N per-field queries

### Core Engine

- **PostingList.entries**: remove defensive copy (`list(self._entries)` to `self._entries`); all callers are read-only
- **PostingList.doc_ids cache**: lazy-computed `_doc_ids_cache` populated on first access; PostingList is immutable after construction so cache is always valid
- **InvertedIndex.stats cache**: `_cached_stats` avoids recomputing `IndexStats` on every access; invalidated by `add_document`, `remove_document`, `add_posting`, `set_doc_count`, `add_total_length`, `clear`
- **Cross-field secondary index**: in-memory `_term_to_keys` dict maps each term to its (field, term) keys, replacing full `_index` scan in `get_posting_list_any_field`, `get_total_term_freq`, and `doc_freq_any_field`
- **ASCIIFolding fast-path**: `ASCIIFoldingFilter._fold` short-circuits with `token.isascii()` before NFKD normalization
- **NGram attribute localization**: `NGramFilter.filter` localizes `_min_gram`, `_max_gram`, `_keep_short`, and `result.append` lookups in the inner loop

### SQL Compiler

- **ExprEvaluator class-level dispatch**: `_DISPATCH_NAMES` dict mapping node types to method name strings is defined once at class level; `evaluate()` uses `getattr(self, method_name)` instead of constructing a 13-entry dict of bound methods per instance
- **Query parse cache**: `_parse_sql_cached` with `@lru_cache(maxsize=256)` avoids re-parsing identical SQL strings
- **UNIQUE constraint hash index**: `Table._unique_indexes` provides O(1) duplicate detection on INSERT instead of O(N) scan; maintained incrementally across INSERT, UPDATE, DELETE, TRUNCATE
- **FK validation direct lookup**: `has_value(field, value)` on `DocumentStore` and `SQLiteDocumentStore` replaces full-set construction with a point query (`SELECT 1 ... LIMIT 1`)
- **LIMIT pushdown**: when SELECT has no WHERE/ORDER BY/GROUP BY/HAVING/DISTINCT/window, the scan limit is pushed into `_scan_all` to avoid reading unnecessary rows
- **Single-pass ANALYZE**: `Table.analyze()` fetches each document once via `get()` and collects all column values per doc, instead of calling `get_field()` per column per doc
- **Persistent ThreadPoolExecutor**: `ParallelExecutor` reuses a single thread pool across queries instead of creating and destroying one per `execute_branches` call
- **Correlated subquery context injection**: `ExprEvaluator` accepts an `outer_row` parameter; correlated ColumnRefs are resolved at evaluation time via `_eval_column_ref` fallback instead of cloning the entire AST per outer row
- **Uncorrelated subquery memoization**: `ExprEvaluator._eval_sublink` caches results of uncorrelated EXPR_SUBLINK, ANY_SUBLINK, and EXISTS_SUBLINK by AST node identity
- **CTE inlining**: single-reference non-recursive CTEs are inlined as derived tables at FROM resolution time instead of being materialized upfront; reference count is computed via `_count_cte_refs` AST walk
- **Predicate pushdown into views/derived tables**: safe WHERE predicates (no aggregates, window functions, GROUP BY, DISTINCT, LIMIT in subquery) are injected into the subquery's WHERE clause before materialization via `_try_predicate_pushdown`
- **Join reordering for implicit cross joins**: multi-table FROM clauses with 3+ tables and equijoin predicates in WHERE are optimized via DPccp join enumerator (`_try_implicit_join_reorder`) instead of left-deep cross join chains

### Scoring

- **WAND bisect-based cursor management**: both `WANDScorer` and `BlockMaxWANDScorer` maintain a sorted list of `(cur_doc_id, term_index)` pairs updated via `bisect.insort` on cursor advance, instead of re-sorting all term indices on every iteration

### Execution

- **PyArrow `to_pylist()`**: `Batch.to_rows()` uses `RecordBatch.to_pylist()` (single C++ call) instead of `to_pydict()` + Python list comprehension
- **Single-pass sort**: `SortOp._sort_rows` uses `functools.cmp_to_key` with a composite comparator handling all sort keys in one pass, instead of K stable sort passes (one per key)
- **Streaming aggregation**: `HashAggOp` uses incremental accumulators for COUNT, SUM, AVG, MIN, MAX, BOOL_AND, BOOL_OR (no per-group row materialization); complex aggregates (ARRAY_AGG, STRING_AGG with ORDER BY, JSON_AGG, FILTER, DISTINCT, percentiles) fall back to full materialization
- **O(n) CUME_DIST**: single linear pass identifying peer group boundaries instead of O(n^2) nested loop
- **Pre-computed RANGE frame order values**: `_resolve_range_frame_index` accepts pre-computed `order_vals`, `non_null_vals`, and `non_null_indices` arrays, computed once per partition instead of once per row

### Graph

- **Set-based adjacency**: `GraphStore._adj_out`, `_adj_in`, `_label_index`, `_vertex_label_index` changed from `list` to `set`; `add_vertex`/`add_edge` use `.add()`, `remove_vertex`/`remove_edge` use `.discard()`
- **Set intersection for label-filtered traversal**: `TraversalOperator` uses `adj & label_eids` set intersection instead of list comprehension filter
- **Shared frozenset in traversal**: `TraversalOperator` creates a single `frozenset(visited)` and `frozenset(all_edges)` shared across all `GraphPayload` entries instead of one per entry
- **NFA state hoisting**: `RegularPathOperator` computes `_collect_nfa_states` and `_epsilon_closure` once before the start-vertex loop instead of once per start vertex
- **Set-based result pairs**: `RegularPathOperator` uses `set[tuple[int, int]]` for result pairs, eliminating O(n) `not in list` checks
- **Type-tagged vertex/edge refs**: `_VertexRef(int)` and `_EdgeRef(int)` marker subclasses eliminate double `get_vertex`/`get_edge` lookups in `_to_agtype`, `_eval` (PropertyAccess), SET, and DELETE

### Fusion

- **Small-list fast path**: `LogOddsFusion.fuse` uses `np.asarray(dtype=float64)` for lists with 4 or fewer elements, avoiding full `np.array` construction overhead

## 0.14.1 (2026-03-13)

Fix log-odds fusion scoring when one signal has zero coverage (e.g., BM25 vocabulary gap for out-of-vocabulary terms), and clean up linting across IVF-related files.

### Fusion

- **Coverage-based default probability**: replace fixed `default_prob=0.01` with a per-signal default derived from coverage ratio — `default = 0.5 * (1 - r) + 0.01 * r` where `r = signal_hits / total_docs`
  - At zero coverage (vocabulary gap), the default is 0.5 — neutral in log-odds space (`logit(0.5) = 0`), contributing no evidence rather than strong negative evidence (`logit(0.01) = -4.6`)
  - At full coverage, the default remains 0.01 — a missing document is genuinely penalized
  - Partial coverage interpolates smoothly between the two extremes
- **All three fusion code paths updated**: `LogOddsFusionOperator` (SQL), `_FusionOperator` (fluent API), and `ProbBoolFusionOperator` (prob-boolean)
- **5 new tests**: formula boundary values, zero/full/partial coverage behavior, prob-boolean coverage defaults

### Code Quality

- Fix ruff lint errors in IVF implementation (unused imports, bare `assert`, simplifiable expressions)
- Fix ruff format errors in IVF-related files

## 0.14.0 (2026-03-13)

Replace HNSW with IVF (Inverted File Index) backed by SQLite, aligning vector search with UQA's posting-list-as-universal-abstraction thesis and eliminating the hnswlib C++ dependency.

### Vector Search

- **IVF (Inverted File Index)**: replaced HNSW with a pure-numpy IVF implementation that persists natively to SQLite; centroids stay in memory while posting lists are lazy-loaded per query
- **VectorIndex ABC**: new abstract base class (`uqa/storage/vector_index.py`) decouples operators from the concrete index implementation
- **IVFIndex**: k-means++ initialization with Lloyd's iterations (max 25, tolerance 1e-4); vectors L2-normalized on add so cosine similarity reduces to dot product
- **Three-state lifecycle**: UNTRAINED (brute-force scan), TRAINED (IVF search), STALE (>20% deletes triggers retrain on next search)
- **Auto-train**: training triggers automatically when vector count reaches `max(2 * nlist, 256)`
- **SQLite persistence**: two tables per index (`_ivf_centroids_{table}_{field}`, `_ivf_lists_{table}_{field}`); centroids and posting lists survive engine restart without O(N log N) rebuild
- **Backward-compatible SQL syntax**: `CREATE INDEX ... USING hnsw` maps to IVF; `USING ivf` also accepted; WITH parameters: `nlist`, `nprobe` (old `ef_construction`, `m` silently ignored)

### Dependencies

- **Removed `hnswlib >= 0.8`**: no more C++ extension dependency; vector search is pure Python + numpy
- **Lowered `pyarrow` minimum from 20.0 to 10.0**: all pyarrow APIs used are stable since 6.0; 10.0 provides a comfortable margin

### Benchmarks

- **IVF vector benchmarks**: 7 new benchmarks in `bench_storage.py` covering add, build, brute-force vs trained KNN, threshold search, delete, k-means training, and persistence roundtrip
- 192 benchmarks across 8 files (was 185)

### Tests

- 1962 tests across 49 test files (28 new IVF tests)

## 0.13.0 (2026-03-13)

Dual analyzer support: Elasticsearch-style index/search analyzer split per field with synonym expansion, catalog persistence, and production tooling.

### Text Analysis

- **Dual analyzer per field**: separate index-time and search-time analyzers with fallback chain (search -> index -> default), following the Elasticsearch/Lucene pattern
- **`set_table_analyzer()` SQL table function**: `SELECT * FROM set_table_analyzer('table', 'field', 'analyzer'[, 'phase'])` assigns analyzers with `'index'`, `'search'`, or `'both'` phase
- **Search-time synonym expansion**: SynonymFilter in the search pipeline expands query terms at read time (e.g., "car" -> "car OR automobile OR vehicle OR auto")
- **Index-time synonym expansion**: SynonymFilter in the index pipeline creates postings for all synonym variants at write time
- **TermOperator multi-token union**: analyzer output with multiple tokens (e.g., from synonym expansion) now uses union instead of intersect, enabling correct synonym search semantics
- **`_table_field_analyzers` catalog table**: persists `(table_name, field, phase, analyzer_name)` tuples to SQLite; restored on engine restart
- **`Engine.set_table_analyzer()`**: Python API with `phase` parameter (`"index"`, `"search"`, or `"both"`) and automatic catalog persistence
- **`Engine.get_table_analyzer()`**: Python API with `phase` parameter for retrieving field-specific analyzers

### Production Tooling

- **Ruff linting and formatting**: integrated ruff for code quality and consistent formatting
- **Pyright type checking**: zero errors and zero warnings across the entire codebase
- **CI/CD workflows**: GitHub Actions for lint checks and PyPI publishing via OIDC Trusted Publisher
- **Pre-commit hooks**: automated lint and format checks before each commit
- **PEP 561 `py.typed` marker**: enables downstream type checking for UQA as a library

### Tests and Examples

- **14 new tests**: `TestDualAnalyzer` (7), `TestTermOperatorSynonymUnion` (2), `TestDualAnalyzerCatalogPersistence` (3), `TestSetTableAnalyzerSQL` (2)
- **`examples/sql/synonyms.py`**: 12-section example demonstrating search-time and index-time synonym expansion, dual analyzers, multi-term queries, BM25 scoring with synonyms, hybrid search + filter, and catalog persistence

## 0.12.0 (2026-03-12)

Geospatial support: POINT column type with R*Tree spatial indexing, spatial query functions, and cross-paradigm fusion.

### Geospatial

- **POINT column type**: stores 2-D coordinates as `[longitude, latitude]`; persisted as JSON in SQLite
- **R*Tree spatial index**: `CREATE INDEX ... USING rtree (column)` creates SQLite R*Tree virtual table for O(log N) spatial queries
- **`spatial_within(field, POINT(x, y), distance_m)`**: indexed range query returning all points within a radius; produces PostingList with proximity scores (`1.0 - dist/max_dist`)
- **`ST_Distance(point1, point2)`**: scalar Haversine great-circle distance in meters
- **`ST_Within(point1, point2, distance_m)`**: scalar distance predicate (boolean)
- **`ST_DWithin(point1, point2, distance_m)`**: alias for ST_Within
- **`POINT(x, y)` constructor**: usable in SELECT, INSERT VALUES, and WHERE clauses
- **Two-pass spatial search**: coarse R*Tree bounding box filter + fine Haversine great-circle verification
- **Bounding box formula**: spherical law of cosines for accurate longitude delta at any latitude and radius
- **Brute-force fallback**: SpatialWithinOperator scans all documents when no R*Tree index exists
- **Fusion support**: `spatial_within()` works as a signal in `fuse_log_odds`, `fuse_prob_and`, `fuse_prob_or`
- **DML integration**: INSERT, UPDATE, DELETE, and TRUNCATE maintain spatial index consistency
- **Persistence**: R*Tree data persists in SQLite; restored on Engine restart via catalog
- **Parameter binding**: `$N` parameters supported for POINT coordinates and distance values
- **Unknown function fallback**: scalar boolean functions in WHERE (e.g., `ST_DWithin`) now fall through to expression evaluation instead of raising an error

### Tests and Examples

- 31 new spatial tests across 5 test classes (TestHaversine, TestSpatialIndex, TestSpatialSQL, TestSpatialPersistence, TestSpatialFusion)
- 14-example geospatial SQL demo (`examples/sql/spatial.py`)
- Total: 1927 tests across 49 test files, 18 examples

## 0.11.2 (2026-03-12)

Performance optimization across core, storage, execution engine, and scoring subsystems. 21 files changed, ~27 optimizations spanning 4 categories.

### Core

- **`PostingList.from_sorted()` classmethod**: bypass O(n log n) sort + O(n) dedup for pre-sorted entries; used by ~25 internal callers (ScoreOperator, FilterOperator, FacetOperator, fusion operators, SQLite index readers, compiler scan operators, BTreeIndex, aggregation/hierarchical operators)
- **LIKE/ILike regex caching**: `@functools.lru_cache(256)` on SQL LIKE pattern-to-compiled-regex conversion

### Storage

- **SQLite batch writes**: `executemany()` for posting list inserts instead of per-term `execute()`
- **Deferred skip pointer rebuilds**: track dirty (field, term) pairs; rebuild lazily via `flush_skip_pointers()` before first query after writes
- **Positions binary encoding**: `struct.pack`/`struct.unpack` replaces `json.dumps`/`json.loads` for posting list positions (backward-compatible: detects legacy JSON format at read time)
- **`get_field()` prepared statement cache**: per-field SQL string cache avoids f-string construction per call
- **IndexStats caching**: cache `IndexStats` on instance after first computation; invalidate on `add_document()`, `remove_document()`, `clear()`
- **Vector batch load**: hnswlib `add_items()` batch API on startup instead of per-vector `add()`
- **`iter_all()` for SeqScanOp**: single `SELECT * ORDER BY _rowid` instead of N individual `get(doc_id)` calls
- **InvertedIndex O(1) term freq lookup**: changed `_index` from `dict[key, list]` to `dict[key, dict[DocId, PostingEntry]]`; `get_term_freq()` is now O(1) instead of O(df)
- **InvertedIndex efficient `remove_document`**: reverse map `_doc_terms` tracks which posting lists contain each document; removal touches only relevant entries instead of scanning entire index

### Execution Engine

- **Arrow-native sort**: `pc.sort_indices()` for single-pass C++ multi-key sort with `null_placement`; falls back to Python stable sort when keys have mixed NULLS FIRST/LAST
- **Vectorized ExprProjectOp**: simple expressions (column refs, constants, arithmetic +/-/*/) evaluated directly on Arrow arrays via `pc.add`/`pc.subtract`/`pc.multiply`/`pc.divide`, bypassing row-by-row `to_rows()`/`from_rows()` conversion; complex expressions (CASE, COALESCE, function calls, JSON, subqueries) fall back to ExprEvaluator
- **Arrow compute FilterOp**: vectorized `pc.equal`/`pc.greater`/`pc.less`/`pc.is_null` for simple scalar predicates; falls back to per-row evaluation for LIKE, BETWEEN, custom predicates
- **PostingListScanOp entry caching**: cache `entries` reference in `open()` instead of O(n) copy on every `next()` call
- **HashAggOp ExprEvaluator reuse**: single evaluator created in `open()` and reused across all groups instead of per-group instantiation
- **Window RANGE frame bisect**: `bisect_left`/`bisect_right` for O(log n) peer group boundary lookup replacing O(n) linear scan

### Scoring

- **BM25/BayesianBM25 `score_with_idf()`**: pre-computed IDF value accepted directly, avoiding redundant `doc_freq` lookups in the inner scoring loop
- **ScoreOperator loop invariant hoisting**: `doc_freq` hoisted outside per-doc loop (per-term constant), `get_doc_length` hoisted outside per-term loop (per-doc constant); for a 3-term query over 1000 docs: `doc_freq` calls reduced from 3000 to 3, `get_doc_length` calls from 3000 to 1000
- **WAND cursor-based pivot skipping**: replaced O(|union|) full-materialization with cursor-based pivot advancement using binary search (`_advance_cursor`); complexity reduced from O(|union|) to O(|result| * T * log(df))
- **BlockMaxWAND cursor-based pivot skipping**: same cursor-based algorithm using per-block max scores from BlockMaxIndex for tighter pruning bounds

### SQL Compiler

- **ExprEvaluator dispatch table**: replaced 14-type `isinstance` chain with `dict[type, Callable]` for O(1) node evaluation dispatch
- **Scalar function dispatch table**: replaced ~100-branch if/elif chain in `_call_scalar_function()` with module-level `dict[str, Callable]` lookup
- **Module-level imports**: moved ~30 inline `import json/re/math/base64/...` from hot paths to module top level across `expr_evaluator.py`, `sqlite_document_store.py`, `types.py`
- **CTE/View materialization skip**: transient tables (CTEs, views, derived) skip inverted index building since they are never text-searched
- **Progressive k-expansion for HNSW threshold search**: starts with k=100, doubles until last result falls below threshold or index exhausted; preserves O(d log N) advantage instead of scanning entire index

### Benchmarks

- 185 pytest-benchmark tests across 8 suites (posting list, storage, compiler, execution, planner, scoring, graph, end-to-end SQL)


## 0.11.1 (2026-03-12)

Public API improvements and quickstart example.

### Public API

- **`engine.get_document(doc_id, table)`**: retrieve a document by ID from a table's document store; returns the stored dict or `None`
- **`engine.get_graph_store(table)`**: return the `GraphStore` associated with a table for direct vertex lookups and index building
- **`engine.get_table_analyzer(table, field)`**: symmetric getter for `set_table_analyzer()`; returns the analyzer assigned to a table field

### Examples

- **`examples/quickstart.py`**: hybrid search (text + vector + fusion) in under 30 lines, demonstrating `text_match`, `knn_match`, `fuse_log_odds`, and `EXPLAIN`
- Removed all `engine._tables[...]` private API access from 8 example files, replaced with public `get_document()`, `get_graph_store()`, and `set_table_analyzer()` calls

### Documentation

- Updated README with quickstart section and `get_document()` usage
- Updated `docs/references/uqa-api-manual.md` with new public API methods
- Updated GitHub Pages (`docs.html`, `examples.html`) with new API documentation and quickstart links


## 0.11.0 (2026-03-12)

Query optimizer overhaul, vector index architecture redesign, and USQL formal grammar specification.

### Query Optimizer: Correctness Fixes

- **Graph filter pushdown to correct vertex (C2)**: filter on `b.name` was always pushed to the first vertex pattern regardless of which vertex has the field; now parses `variable.property` prefix and pushes the constraint only to the matching vertex pattern
- **`_fuse_join_pattern` dropping input operator (C1)**: `PatternMatchOperator` fusion discarded the first operator entirely; disabled the unsafe optimization, now recurses children correctly
- **Filter pushdown to all Intersect children (H1)**: `pushed = True` after the first child prevented pushing to other applicable children; now pushes the filter to ALL children whose schema includes the filter field
- **ON CONFLICT O(N) full scan per row (C3)**: `_find_conflict` did a linear scan per inserted row; replaced with hash index built before the insert loop for O(1) lookup per row
- **FK validation O(N) scan per check (C4)**: all 4 FK validators (`_validate_insert`, `_validate_delete`, `_validate_update`, `_validate_parent_update`) did full table scans; replaced with set-based lookups

### Query Optimizer: Performance Improvements

- **DPccp enabled for 2-table joins (H2)**: changed threshold from `len(relations) < 3` to `< 2`, so DPccp chooses optimal join order (including build side) even for 2-table joins
- **Predicate pushdown below joins (H3)**: AND-decomposed WHERE conjuncts referencing a single table alias are now pushed into that table's scan as `ExprFilterOp`, reducing rows entering the join; cross-table conjuncts remain as deferred WHERE
- **Constant folding pass (H4)**: bottom-up fold of `A_Expr` with `A_Const` operands and `BoolExpr(AND/OR)` with constant args; skips `ColumnRef`, side-effecting functions (`random`, `nextval`, `now`)
- **ExprEvaluator cached across batches (H5)**: `ExprFilterOp.next()` and `ExprProjectOp.next()` were creating a new `ExprEvaluator` per batch; moved construction to `open()` for single allocation
- **Hash join build on smaller side (H7)**: `InnerJoinOperator` now compares input sizes and builds the hash table on the smaller side while preserving left/right output semantics

### Query Optimizer: Cost Model & Cardinality

- **IntersectOperator cost model (M4)**: was `min(child_costs)` but all children must be evaluated; changed to `sum(child_costs)`
- **Named constants for cost model (M2)**: replaced magic numbers with `SCORE_OVERHEAD_FACTOR`, `FILTER_SCAN_FRACTION`, `GROUP_BY_OVERHEAD_FACTOR`, `VERTEX_AGG_FRACTION`, `TRAVERSE_FRACTION`; uses `graph_stats` for `PatternMatchOperator` cost when available
- **Independence damping in cardinality (M1)**: strict independence assumption `(result * card) / n` replaced with sqrt damping on subsequent selectivities after sorting children ascending
- **Histogram zero-width bucket (L1)**: added clarifying comment for correct zero-width bucket behavior
- **Graph stats fallback (L2)**: added comments explaining the `n^1.5` heuristic fallback when graph statistics are unavailable

### Vector Index Architecture

- **Vectors stored in document store**: `VECTOR(N)` columns are now stored as JSON arrays in the document store (SQLite `_data_{table}` table), not in a separate HNSW index; this enables `DROP INDEX` + re-`CREATE INDEX` workflows
- **Explicit HNSW index creation**: HNSW indexes are created via `CREATE INDEX ... USING hnsw (column)` with optional `WITH (ef_construction, m)` parameters, matching the pgvector model
- **Brute-force fallback**: when no HNSW index exists on a vector column, `knn_match()` falls back to exact brute-force cosine similarity scan over all stored vectors
- **Auto-resize**: `HNSWIndex` automatically doubles capacity when the index is full; removed the `max_elements` constructor parameter
- **Removed `vector_dimensions` from Table**: vector dimensionality is no longer stored on the table; inferred from the first inserted vector and validated on subsequent inserts

### USQL Grammar Specification

- New `docs/references/usql-grammar.md` — complete formal EBNF grammar specification (ISO 14977 notation) for all implemented SQL syntax, covering 22 sections: DDL, DML, SELECT, CTEs, window functions, aggregates, expressions, data types, scalar functions, JSON/JSONB, arrays, search functions, fusion, Cypher integration, transactions, EXPLAIN/ANALYZE, information_schema, and 2 appendices (operator precedence, reserved words)

### Documentation

- Updated `docs/references/uqa-api-manual.md`, `uqa-reference.md`, `technical-overview.md` for the new vector index architecture (explicit CREATE INDEX, brute-force fallback, document store storage)
- Removed 4 unimplemented features from `docs/references/usql-manual.md`: `GENERATED ALWAYS AS ... STORED`, `SIMILAR TO`, `ROLLUP`/`CUBE`/`GROUPING SETS`, `NATURAL JOIN`
- Added `GROUP BY computed expression` to `usql-manual.md` (was implemented but undocumented)

### Bug Fixes

- Fixed DuckDB FDW deprecated API: changed `fetch_arrow_table()` to `to_arrow_table()` for DuckDB 1.4.3+ compatibility

### Tests

- 1896 tests across 48 test files + 185 benchmarks across 8 benchmark files
- New `test_cost_optimizer.py` with 17 tests: optimizer correctness (graph filter pushdown, Intersect filter, join pattern fusion), cost model (Intersect sum, named constants), cardinality (independence damping, histogram zero-width)


## 0.10.1 (2026-03-11)

DPccp join enumerator optimization and benchmark infrastructure.

### DPccp Join Enumerator Optimization

- **Integer bitmask DP table**: replaced `frozenset[int]` keys with `int` bitmask keys throughout the DP table, reducing per-lookup cost from O(k) frozenset hashing to O(1) integer hashing
- **Bytearray connectivity lookup**: replaced `set[frozenset[int]]` with a `bytearray(2^n)` lookup table indexed by bitmask, giving O(1) array-indexed connectivity checks instead of O(k) hash-based set lookups
- **Incremental connected subgraph enumeration**: builds connected subgraphs bottom-up via BFS extension with the `neighbor > min(S)` invariant, avoiding generation of disconnected subsets entirely; replaces the brute-force C(n,k) subset enumeration with per-subset BFS connectivity check
- **Canonical submask enumeration**: enumerates only the half of submasks that contain the lowest set bit (`sub_rest | lowest_bit`), skipping the non-canonical half without branch checks; replaces the `if mask & 1` filter on all 2^k masks
- **`edges_between` adjacency list traversal**: iterates adjacency lists of the smaller set for O(|smaller| * degree) instead of scanning all edges O(E)
- Star-16 topology: **51x speedup** (92s to 1.8s); star-8: 4.3x speedup; star-10: 5.6x speedup

### Benchmark Infrastructure

- Added pytest-benchmark integration with 185 benchmarks across 8 files covering all subsystems
- `benchmarks/data/generators.py` — `BenchmarkDataGenerator` with configurable scale factor and deterministic seeding; Zipf distribution for terms, power-law for graph degree, log-normal for document lengths
- `benchmarks/data/schemas.py` — DDL and column definitions for benchmark tables
- `benchmarks/conftest.py` — shared fixtures for engine setup and data population
- `benchmarks/bench_posting_list.py` — 34 benchmarks: union, intersect, difference by size and overlap ratio, top-k, N-way merge, payload merge
- `benchmarks/bench_storage.py` — 14 benchmarks: document store (put/get/scan), inverted index (add/lookup/doc_freq), vector index (build/knn), graph store (vertices/edges/neighbors)
- `benchmarks/bench_compiler.py` — 21 benchmarks: pglast parsing, SELECT/JOIN/aggregate/subquery/CTE/window/DML compilation
- `benchmarks/bench_execution.py` — 22 benchmarks: sequential scan, filter, project, sort, hash aggregate, distinct, window, limit, pipeline
- `benchmarks/bench_planner.py` — 28 benchmarks: DPccp (chain/star/clique/cycle at varying sizes), topology comparison, greedy fallback (chain/star at 20-30 relations), histogram construction, selectivity estimation
- `benchmarks/bench_scoring.py` — 25 benchmarks: BM25 (single/batch/IDF/combine), Bayesian BM25, vector cosine similarity, log-odds fusion (single/batch/weighted)
- `benchmarks/bench_graph.py` — 16 benchmarks: BFS traversal, neighbors lookup, vertex label lookup, pattern matching, RPQ compilation, Cypher compilation
- `benchmarks/bench_e2e.py` — 25 benchmarks: OLTP (point lookup/range scan/insert/update/delete), OLAP (aggregate/having/order/distinct), JOIN (2-way/3-way/filtered/aggregate), subquery, CTE, window functions, ANALYZE
- `pytest-benchmark >= 5.0` added to `[project.optional-dependencies]` in pyproject.toml

### CI

- GitHub Actions benchmark workflow (`.github/workflows/benchmarks.yml`): runs 185 benchmarks on every push and PR, stores baseline in `gh-pages` branch, compares against baseline with 150% alert threshold, comments on and blocks PRs with significant regressions

### Tests

- 1879 tests across 47 test files + 185 benchmarks across 8 benchmark files


## 0.10.0 (2026-03-11)

Interactive SQL shell enhancements, graph pattern matching optimization, and technical documentation.

### Interactive SQL Shell

- `\di` — list inverted-index fields per table
- `\dF` — list foreign tables (server, source, options)
- `\dS` — list foreign servers (type, connection options)
- `\dg` — list named graphs (vertex/edge counts)
- `\x` — toggle expanded (vertical) display (`-[ RECORD N ]---` format)
- `\o [file]` — redirect output to file (no argument restores stdout)
- `\?` — show help with all backslash commands
- Backslash auto-completion: typing `\` triggers completion of all backslash commands with descriptions
- `\dt` updated to show foreign tables alongside regular tables with type column
- `\d <table>` updated to resolve and describe foreign tables
- Toolbar displays foreign table count, expanded display state, and output file path
- SQL keyword auto-completion expanded from ~30 to ~100 keywords (DDL, DML, joins, window functions, FDW, CTE, aggregates, Cypher integration, JSON types)
- Foreign table names included in auto-completion with "foreign table" metadata

### Graph Pattern Matching Optimization

- **Candidate pre-computation with arc consistency**: before backtracking begins, each pattern variable's candidate set is computed by evaluating vertex constraints once; edge constraints are then propagated in a fixpoint loop to eliminate candidates that cannot participate in any valid match
- **MRV (Minimum Remaining Values) variable ordering**: at each recursion step, the algorithm selects the unassigned variable with the fewest remaining candidates ("fail-first" heuristic), dramatically reducing the effective branching factor
- **Incremental edge validation**: each variable binding immediately validates all edge constraints connecting to previously bound variables, pruning invalid partial assignments at depth $d$ instead of deferring all edge checks to depth $k$
- These three techniques reduce the effective search space by orders of magnitude compared to the naive $O(\|V\|^k)$ backtracking, while the theoretical worst-case bound remains unchanged (NP-complete)
- `CypherCompiler._expand_var_length()`: BFS frontier changed from `list.pop(0)` (O(n)) to `deque.popleft()` (O(1)); path tracking changed from mutable list copy to immutable tuple concatenation

### Documentation

- `docs/references/technical-overview.md` — comprehensive technical document mapping all three research papers to the implementation codebase, with LaTeX formulas and Mermaid diagrams covering: posting list algebra, cross-paradigm operators, BM25/Bayesian BM25 scoring, log-odds fusion, graph-posting list isomorphism, subgraph isomorphism mitigations, system architecture, and theory-to-code mapping tables

### Tests

- 1879 tests across 47 test files (up from 1824 in v0.9.3)
- `test_cli.py` with 55 tests: keywords (10), completer (7), list tables (3), describe table (4), list indexes (3), list foreign tables (2), list foreign servers (2), list graphs (2), expanded display (4), output redirection (4), backslash dispatch (8), toolbar (5), banner (1)


## 0.9.3 (2026-03-11)

Foreign Data Wrapper support with Hive partitioning and predicate pushdown.

### Foreign Data Wrappers

- `CREATE SERVER ... FOREIGN DATA WRAPPER` DDL for registering external data sources
- `CREATE FOREIGN TABLE ... SERVER ... OPTIONS (source '...')` for mapping external files to SQL tables
- `DROP SERVER [IF EXISTS]` / `DROP FOREIGN TABLE [IF EXISTS]` with dependency validation
- DuckDB FDW handler (`duckdb_fdw`): in-process access to Parquet, CSV, JSON, and ndjson files
  - Auto-detection of file type from extension (`.parquet`, `.csv`, `.json`, `.ndjson`)
  - S3 credentials support (`s3_region`, `s3_access_key_id`, `s3_secret_access_key`)
- Arrow Flight SQL FDW handler (`arrow_fdw`): remote access via gRPC with TLS and authentication
- Foreign tables are read-only (INSERT/UPDATE/DELETE rejected with clear error messages)
- Handler caching per server with lazy initialization
- Full SQL support on foreign tables: WHERE, ORDER BY, LIMIT, DISTINCT, GROUP BY, HAVING, JOINs, subqueries, CTEs, window functions
- `information_schema.tables` shows foreign tables with `FOREIGN TABLE` type
- Catalog persistence: servers and foreign tables survive engine restart

### FDW: Hive Partitioning

- `hive_partitioning` option on `CREATE FOREIGN TABLE` for Hive-style directory layout (`key=value/`) discovery
  - Supported for Parquet and CSV via DuckDB FDW
  - Partition columns (extracted from directory names) appear as regular queryable columns
  - Auto-injected into `read_parquet()` / `read_csv()` when source is a bare file path

### FDW: Predicate Pushdown

- WHERE clause predicates are now pushed down to FDW handlers for server-side filtering
  - Comparison operators: `=`, `!=`, `<>`, `<`, `<=`, `>`, `>=`
  - Set membership: `IN (v1, v2, ...)`
  - Pattern matching: `LIKE`, `NOT LIKE`, `ILIKE`, `NOT ILIKE`
  - `BETWEEN` (split into `>=` and `<=`)
- `_extract_pushdown_predicates` in SQL compiler recursively splits AND-connected WHERE clauses into pushable and deferred parts
  - Pushable predicates forwarded to DuckDB/Arrow Flight SQL as native WHERE clauses
  - Non-pushable predicates (OR, subqueries, complex expressions) remain as post-scan `ExprFilterOp`
- DuckDB handler uses parameterized queries (`?` placeholders) for safe predicate injection
- Arrow Flight SQL handler inlines literals with proper quoting

### FDW: Data Model

- `FDWPredicate` dataclass for handler-agnostic predicate representation (column, operator, value)
- `FDWHandler.scan()` interface updated with typed `predicates: list[FDWPredicate]` parameter
- `_ForeignTableScanOperator` carries `pushdown_predicates` to handler's `scan()` method

### Dependencies

- Added `duckdb >= 1.0` to README requirements (was already in pyproject.toml)

### Tests

- 1824 tests across 46 test files (up from 1671 in v0.9.2)
- `test_fdw.py` with 133 tests: DDL (16), DML guards (3), queries (16), aggregation (6), joins (6), subqueries/CTEs (4), window functions (2), EXPLAIN (1), file sources (5), handler lifecycle (4), information_schema (3), catalog persistence (4), Hive partition discovery (5), predicate pushdown (11), Hive aggregation (3), Hive joins (1), Hive order/limit (2), source normalization (10), WHERE clause building (10), predicate extraction (8), CSV partitioning (1), Hive catalog persistence (1), ORDER BY fix (1)


## 0.9.2 (2026-03-10)

Enhanced text analysis pipeline with NGramFilter, analyzer presets, and CI.

### Text Analysis

- `NGramFilter(min_gram, max_gram, keep_short)`: character-level n-gram token filter for CJK and substring matching
  - `keep_short` option preserves tokens shorter than `min_gram` instead of dropping them
- Updated `standard` analyzer preset: StandardTokenizer + LowerCase + ASCIIFolding + StopWord + PorterStem
- New `standard_cjk` analyzer preset: standard + NGramFilter(2, 3, keep_short=True) for CJK text
- `DEFAULT_ANALYZER` changed from `whitespace` to `standard`

### CI

- Added GitHub Actions workflow for running unit tests on Python 3.12 and 3.13
- Version consistency check workflow validates pyproject.toml, `__init__.py`, and CITATION.cff

### Tests

- 1671 tests across 44 test files (up from 1659 in v0.9.1)
- NGramFilter tests: default, short_token_dropped, keep_short, keep_short_mixed, roundtrip, roundtrip_keep_short, validation
- Analyzer preset tests: standard stemming/ASCII folding, standard_cjk, standard_cjk keep_short
- Index tests use explicit `whitespace_analyzer()` for isolation from DEFAULT_ANALYZER changes


## 0.9.1 (2026-03-10)

Arrow and Parquet export with zero-copy optimization.

### SQLResult Export

- `to_arrow()` — convert query results to a `pyarrow.Table`
- `to_parquet(path)` — write query results to a Parquet file
- Zero-copy path: physical execution engine preserves original Arrow `RecordBatch` objects, so `to_arrow()` calls `pa.Table.from_batches()` without intermediate dict conversion
- Lazy row materialization: `SQLResult.rows` property converts from batches on first access only
- Generator-based `__iter__` — iterates over results without materializing all rows at once
- Automatic type inference: int64, float64, string, bool, timestamp, date, time, duration, binary, list

### QueryBuilder Export

- `execute_arrow()` — execute fluent query and return a `pyarrow.Table` with `_doc_id`, `_score`, and field columns
- `execute_parquet(path)` — execute fluent query and write results to a Parquet file
- `PostingList` to Arrow conversion via `_posting_list_to_arrow()` helper

### Tests

- 1659 tests across 44 test files (up from 1646 in v0.9.0)
- `test_query_builder.py` with 7 tests: `execute_arrow` (4), `execute_parquet` (3)
- `test_sql.py` — 6 new tests: `to_arrow` (4), `to_parquet` (2)

### Examples

- `examples/sql/export.py` — 10 examples: Arrow conversion, column access, Parquet write/read, type preservation, aggregation, empty results, lazy iteration, JOIN export
- `examples/fluent/export.py` — 8 examples: text search to Arrow, BM25/Bayesian BM25 scoring, Parquet round-trip, empty results, Arrow compute


## 0.9.0 (2026-03-10)

Lucene-style text analysis pipeline with configurable analyzers.

### Text Analysis Pipeline

- Composable `CharFilter -> Tokenizer -> TokenFilter` pipeline (Lucene architecture)
- `Analyzer` class with `analyze(text) -> list[str]`, JSON serialization roundtrip (`to_dict`/`from_dict`/`to_json`/`from_json`)
- `DEFAULT_ANALYZER` uses the `standard` preset (StandardTokenizer + LowerCase + ASCIIFolding + StopWord + PorterStem)

### Tokenizers

- `WhitespaceTokenizer`: split on whitespace (`str.split()`)
- `StandardTokenizer`: Unicode word-boundary tokenizer (`\w+`)
- `LetterTokenizer`: ASCII letters only (`[a-zA-Z]+`)
- `NGramTokenizer(min_gram, max_gram)`: character-level n-grams for fuzzy matching
- `PatternTokenizer(pattern)`: split by regex delimiter
- `KeywordTokenizer`: entire input as a single token

### Token Filters

- `LowerCaseFilter`: case normalization
- `StopWordFilter(language, custom_words)`: stop word removal with English built-in list
- `PorterStemFilter`: Porter stemming algorithm (M. F. Porter, 1980) — morphological normalization
- `ASCIIFoldingFilter`: fold Unicode to ASCII equivalents (NFKD normalization)
- `SynonymFilter(synonyms)`: expand tokens with synonym alternatives
- `EdgeNGramFilter(min_gram, max_gram)`: prefix n-grams for autocomplete/typeahead
- `LengthFilter(min_length, max_length)`: filter tokens by length

### Char Filters

- `HTMLStripCharFilter`: strip HTML tags, decode common entities (`&amp;`, `&lt;`, etc.)
- `MappingCharFilter(mapping)`: string-level character replacements (longest-match-first)
- `PatternReplaceCharFilter(pattern, replacement)`: regex-based text replacement

### Named Analyzer Registry

- Built-in presets: `whitespace`, `standard`, `standard_cjk`, `keyword`
- `register_analyzer(name, analyzer)` / `get_analyzer(name)` / `drop_analyzer(name)` / `list_analyzers()`
- Cannot overwrite or drop built-in analyzers

### Inverted Index Integration

- `InvertedIndex` and `SQLiteInvertedIndex` accept `analyzer` and `field_analyzers` parameters
- `set_field_analyzer(field, analyzer)` / `get_field_analyzer(field)` for per-field overrides
- All tokenization uses the analyzer pipeline instead of hardcoded `text.lower().split()`
- Analyzer symmetry: same analyzer used at index time and query time

### SQL Table Functions

- `create_analyzer('name', 'config_json')` — create a named analyzer from JSON configuration
- `drop_analyzer('name')` — remove a custom analyzer
- `list_analyzers()` — enumerate all registered analyzers (built-in + custom)

### Engine API

- `engine.create_analyzer(name, config)` — create and persist a named analyzer
- `engine.drop_analyzer(name)` — drop a named analyzer
- `engine.set_table_analyzer(table, field, analyzer_name)` — assign analyzer to a table field

### Catalog Persistence

- New `_analyzers` table in SQLite catalog for named analyzer configurations
- Analyzers restore automatically on engine restart via `_load_from_catalog()`

### Query-Time Integration

- `_make_text_search_op` and `_build_text_search_from` in SQL compiler use field analyzer
- `score_bm25()` and `score_bayesian_bm25()` in QueryBuilder use field analyzer (added optional `field` parameter)
- Cross-paradigm operators (`TextToGraphOperator`, `TextSimilarityJoinOperator`) use `DEFAULT_ANALYZER`

### Tests

- 1646 tests across 43 test files (up from 1576 in v0.8.0)
- `test_analysis.py` with 70 tests: tokenizers (14), token filters (17), char filters (8), analyzer composition (7), named registry (5), inverted index integration (8), SQL table functions (3), catalog persistence (1), SQLite inverted index (4), query builder (1), cross-paradigm (2)

### Examples

- `examples/fluent/analysis.py` — 14 examples: built-in analyzers, custom pipelines, stemming, autocomplete, synonyms, ASCII folding, per-field analyzers, BM25 scoring, serialization
- `examples/sql/analysis.py` — 11 examples: SQL table functions, analyzer assignment, persistence across sessions


## 0.8.0 (2026-03-10)

Apache AGE compatible graph query with openCypher and named graphs.

### Graph Query Language (openCypher)

- Cypher lexer, recursive-descent parser, and AST for the openCypher subset
- `CypherCompiler` executes through `GraphPostingList` (binding table pattern) — every clause transforms a posting list, consistent with UQA's core thesis
- Clauses: `MATCH`, `OPTIONAL MATCH`, `CREATE`, `MERGE` (with `ON CREATE SET` / `ON MATCH SET`), `SET`, `DELETE` / `DETACH DELETE`, `RETURN`, `WITH`, `UNWIND`
- `RETURN` modifiers: `ORDER BY`, `DESC`, `LIMIT`, `SKIP`, `DISTINCT`, aliases (`AS`), expressions
- Pattern matching: node patterns `(n:Label {props})`, relationship patterns `-[r:TYPE*min..max]->`, variable-length paths, cross-label matching, anonymous nodes
- Expression evaluation: property access, function calls, arithmetic, comparison, `AND`/`OR`/`NOT`/`XOR`, `IN`, `IS NULL`/`IS NOT NULL`, `CASE`/`WHEN`/`THEN`/`ELSE`/`END`, list/map literals, list indexing, parameters (`$param`)
- Built-in functions: `id`, `labels`, `type`, `properties`, `keys`, `size`, `length`, `coalesce`, `toInteger`, `toFloat`, `toString`, `toBoolean`, `toLower`, `toUpper`, `trim`, `left`, `right`, `substring`, `replace`, `split`, `reverse`, `startsWith`, `endsWith`, `contains`, `head`, `tail`, `last`, `range`, `abs`, `ceil`, `floor`, `round`, `sign`, `rand`

### Named Graphs

- `create_graph('name')` SQL function — creates an isolated graph namespace with dedicated SQLite-backed storage
- `drop_graph('name')` SQL function — removes a named graph and its storage
- Named graph persistence via `_named_graphs` catalog table
- Named graphs restore automatically on engine restart

### SQL Integration (Apache AGE compatible)

- `cypher('graph_name', $$ MATCH ... RETURN ... $$) AS (col1 agtype, col2 agtype)` — embed Cypher queries in SQL FROM clause
- Column type inference from Cypher result values (integer, real, boolean, text) instead of hardcoding text
- Positional column mapping between Cypher result keys and AS clause column names
- SQL WHERE, ORDER BY, GROUP BY, JOIN work on cypher() results like any other table

### Vertex Labels

- Added required `label` field to `Vertex` datatype (between `vertex_id` and `properties`)
- `vertices_by_label(label)` for efficient label-based vertex retrieval
- SQLite label index on `_graph_vertices` tables
- `remove_vertex(vertex_id)` — removes vertex and all incident edges (both in-memory and SQLite)
- `remove_edge(edge_id)` — removes single edge (both in-memory and SQLite)
- Auto-incrementing vertex/edge ID generators (`next_vertex_id()`, `next_edge_id()`)

### Tests

- 1576 tests across 42 test files (up from 1474 in v0.7.1)
- `test_cypher.py` with 102 tests: lexer (14), parser (19), match (12), create (4), set (2), delete (3), merge (3), return (8), with (2), unwind (2), functions (7), posting list (4), SQL integration (7), named graphs (3), vertex labels (6), additional coverage (6)


## 0.7.1 (2026-03-10)

PostgreSQL compatibility fixes and SQLite thread safety.

### SQL Compiler

- Fixed `SELECT *` failure on tables created by `CREATE TABLE AS SELECT` with explicit columns (`A_Star` attribute error in `_build_sort_keys`)
- Fixed `SELECT *` failure after `DELETE ... USING` (same root cause as above)
- Fixed aggregate functions not recognized inside `IN` subquery `HAVING` clauses (added `_ensure_having_aggs` recursive AST walk)
- Fixed aggregates nested inside scalar functions (e.g., `ROUND(STDDEV(salary), 2)`) treated as unknown scalar functions (recursive `_collect_agg_funcs`, `ExprProjectOp` for wrapper expressions)
- Fixed JSON containment/existence operators (`@>`, `?`, `?&`, `?|`) not working in `WHERE` clauses (non-basic operators now route through `ExprFilterOperator`)

### Execution Engine

- Fixed window functions ignoring default frame when `ORDER BY` is present — now applies SQL-standard `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`

### Scalar Functions

- Fixed `LTRIM`/`RTRIM`/`BTRIM` ignoring the character-set argument
- Added `CONCAT_WS(separator, str1, str2, ...)` — concatenate with separator, skipping NULLs
- Added `TO_CHAR`, `TO_DATE`, `TO_TIMESTAMP` — date/time formatting and parsing with PostgreSQL format strings
- Added `MAKE_DATE(year, month, day)` — construct a date from components
- Added `AGE(timestamp, timestamp)` — compute interval between two timestamps

### Type System

- Added `INTERVAL` as a recognized CAST target type
- Added `NamedArgExpr` handling for `MAKE_INTERVAL(days => 5, hours => 3)` syntax
- Added PostgreSQL array literal parsing (`'{name,age}'`) for `?&` and `?|` JSON operators

### Storage Layer

- Fixed SQLite thread safety: `ManagedConnection` now serializes all operations with a threading lock and provides atomic `execute_fetchall`/`execute_fetchone` methods
- `SQLiteInvertedIndex` and `SQLiteDocumentStore` use atomic fetch methods to prevent cursor interleaving under concurrent access from the parallel executor
- Fixed `test_text_search_works_after_restart` — the last remaining test failure

### Batch Processing

- Fixed `Batch.from_rows` failure on mixed-type lists (e.g., `json_build_array(1, 2, 'three')`) by normalizing to uniform string arrays

### Tests

- 1474 tests across 41 test files (up from 1423 in v0.7.0)
- Added `test_pg_compat_bugs.py` with 48 regression tests covering all 10 PostgreSQL compatibility fixes
- Added 3 mixed-type JSON array tests in `test_json.py`


## 0.7.0 (2026-03-09)

Statistical aggregates, regression functions, and extended scalar/DDL support.

### Statistical Aggregates

- `CORR(y, x)`: Pearson correlation coefficient
- `COVAR_POP(y, x)` / `COVAR_SAMP(y, x)`: population and sample covariance
- `REGR_SLOPE(y, x)` / `REGR_INTERCEPT(y, x)`: linear regression slope and intercept
- `REGR_R2(y, x)`: coefficient of determination
- `REGR_COUNT(y, x)` / `REGR_AVGX(y, x)` / `REGR_AVGY(y, x)`: regression count and averages
- `REGR_SXX(y, x)` / `REGR_SYY(y, x)` / `REGR_SXY(y, x)`: regression sum of squares
- All two-argument aggregates handle NULL pairs correctly (skip when either is NULL)

### String Functions

- `ENCODE(data, format)` / `DECODE(data, format)`: binary-to-text encoding (base64, hex, escape)
- `REGEXP_SPLIT_TO_ARRAY(string, pattern [, flags])`: split by regex into an array
- `REGEXP_SPLIT_TO_TABLE(string, pattern [, flags])`: split by regex into rows (FROM clause)

### Math Functions

- `MIN_SCALE(numeric)`: minimum decimal digits needed to represent a value
- `TRIM_SCALE(numeric)`: remove trailing zeros from a numeric value

### Date/Time Functions

- `ISFINITE(date/timestamp/interval)`: test whether a value is finite
- `CLOCK_TIMESTAMP()`: current timestamp (changes during statement execution)
- `TIMEOFDAY()`: current date and time as text string

### JSON Functions

- `JSONB_STRIP_NULLS(json)`: recursively remove null-valued keys from JSON objects

### DDL

- `ALTER SEQUENCE`: RESTART [WITH n], INCREMENT BY n, START WITH n
- `TABLE name`: shorthand for `SELECT * FROM name` (already supported by pglast)

### System Catalogs

- `pg_catalog.pg_type`: PostgreSQL-compatible type catalog with OIDs

### Tests

- 1423 tests across 40 test files (up from 1392 in v0.6.0)
- 31 new tests: regression functions, covariance/correlation, regexp_split_to_table, pg_type, ALTER SEQUENCE, TABLE shorthand


## 0.6.0 (2026-03-09)

PostgreSQL 17 SQL compatibility — JOINs, DDL/DML extensions, constraints, advanced aggregates, window frames, date/time, JSON, arrays, sequences, system catalogs, and 80+ scalar functions.

### JOIN Support

- `INNER JOIN`, `LEFT JOIN`, `RIGHT JOIN`, `FULL OUTER JOIN`, `CROSS JOIN`
- Non-equality JOIN ON conditions (`ON a.x >= b.y AND a.x <= b.z`)
- Multi-table JOIN chains (`A JOIN B ON ... JOIN C ON ...`)
- Multiple FROM tables (implicit cross join / self-join)
- Qualified column resolution with dual-keyed fields (`e.name`, `d.name`)
- `_ExprJoinOperator` for compound/non-equality ON clauses

### Set Operations

- `UNION` / `UNION ALL`
- `INTERSECT` / `INTERSECT ALL`
- `EXCEPT` / `EXCEPT ALL`
- Chained set operations with ORDER BY and LIMIT

### Subqueries

- Subquery in FROM (derived table): `SELECT ... FROM (SELECT ...) AS alias`
- Correlated subqueries: `WHERE col > (SELECT AVG(col) FROM t2 WHERE t2.id = t1.id)`
- EXISTS subquery: `WHERE EXISTS (SELECT 1 FROM ...)`
- Scalar subquery in SELECT: `SELECT (SELECT COUNT(*) FROM ...) AS cnt`
- `INSERT INTO ... SELECT`

### Recursive CTEs

- `WITH RECURSIVE` with positional column remapping between base case and recursive step
- Depth tracking and hierarchical traversal

### Aggregate Functions

- `COUNT(DISTINCT col)`, `STRING_AGG(col, delimiter)`, `ARRAY_AGG(col)`
- `BOOL_AND(col)`, `BOOL_OR(col)`
- `STDDEV(col)`, `VARIANCE(col)`
- `PERCENTILE_CONT(fraction) WITHIN GROUP (ORDER BY col)`
- `PERCENTILE_DISC(fraction) WITHIN GROUP (ORDER BY col)`
- `MODE() WITHIN GROUP (ORDER BY col)`
- `JSON_OBJECT_AGG(key, value)`, `JSONB_OBJECT_AGG(key, value)`
- Aggregate `FILTER (WHERE ...)` clause
- Aggregate `ORDER BY` within aggregate (e.g., `STRING_AGG(col, ',' ORDER BY col)`)
- `DISTINCT` modifier for `STRING_AGG`, `ARRAY_AGG`
- Expression args in aggregates: `SUM(CASE WHEN ... THEN ... END)`
- GROUP BY with computed expressions: `GROUP BY DATE_TRUNC('month', col)`

### Window Functions

- `PERCENT_RANK()`, `CUME_DIST()`, `NTH_VALUE(col, n)`
- `ROWS BETWEEN` frame clause (UNBOUNDED PRECEDING, n PRECEDING, CURRENT ROW, n FOLLOWING, UNBOUNDED FOLLOWING)
- `RANGE BETWEEN` frame clause
- `WINDOW w AS (...)` named window definitions
- `FILTER (WHERE ...)` on window aggregate functions
- Running totals, moving averages via window frames

### Date/Time

- `DATE`, `TIMESTAMP`, `TIMESTAMPTZ`, `TIME`, `INTERVAL` column types (stored as ISO 8601 strings)
- `EXTRACT(field FROM col)`: year, month, day, hour, minute, second, dow, doy, epoch, quarter, week
- `DATE_PART('field', col)` alias for EXTRACT
- `DATE_TRUNC('precision', col)`: truncation to year, month, day, hour, minute, second, quarter, week
- `NOW()`, `CURRENT_TIMESTAMP`, `CURRENT_DATE`, `CURRENT_TIME`
- `AGE(timestamp)`, `AGE(timestamp, timestamp)`
- `TO_CHAR`, `TO_DATE`, `TO_TIMESTAMP`, `MAKE_DATE`, `MAKE_TIMESTAMP`, `MAKE_INTERVAL`, `TO_NUMBER`
- `OVERLAPS` operator for range overlap testing

### JSON/JSONB

- `->>` operator: extract field as text
- `->` operator: extract field as JSON
- `#>` / `#>>` operators: extract nested path as JSON / text
- `@>` / `<@` containment operators with recursive matching
- `?` / `?|` / `?&` key existence operators
- `JSONB_SET(target, path, value)`: set value at JSON path
- `JSON_BUILD_OBJECT`, `JSON_BUILD_ARRAY`, `JSON_AGG`, `JSON_OBJECT_AGG`
- `JSON_OBJECT_KEYS`, `JSON_EXTRACT_PATH`, `JSON_TYPEOF`
- `JSON_EACH` / `JSON_EACH_TEXT` as table functions in FROM clause
- `JSON_ARRAY_ELEMENTS` / `JSON_ARRAY_ELEMENTS_TEXT` as table functions in FROM clause
- `::jsonb` type cast for JSON literals

### Scalar Functions

- String: `POSITION`, `CHAR_LENGTH`/`CHARACTER_LENGTH`, `LPAD`, `RPAD`, `REPEAT`, `REVERSE`, `SPLIT_PART`, `LEFT`, `RIGHT`, `INITCAP`, `TRANSLATE`, `REPLACE`, `REGEXP_REPLACE`, `REGEXP_MATCH`, `STARTS_WITH`, `ENCODE`, `DECODE`, `MD5`, `CHR`, `ASCII`, `OCTET_LENGTH`, `FORMAT`, `OVERLAY`
- Math: `POWER`/`POW`, `SQRT`, `LOG`, `LN`, `EXP`, `MOD`, `TRUNC`, `SIGN`, `PI`, `RANDOM`, `DEGREES`, `RADIANS`, `DIV`, `GCD`, `LCM`, `FACTORIAL`, `CBRT`, `WIDTH_BUCKET`, trig functions (`SIN`, `COS`, `TAN`, `ASIN`, `ACOS`, `ATAN`, `ATAN2`)
- Conditional: `GREATEST`, `LEAST`, `NULLIF`
- Type: `UUID`, `BYTEA`, `INTEGER[]` (array) types, `GEN_RANDOM_UUID()`
- Array: `ARRAY_LENGTH`, `ARRAY_UPPER`, `ARRAY_LOWER`, `ARRAY_CAT`, `ARRAY_APPEND`, `ARRAY_REMOVE`, `CARDINALITY`, `UNNEST`
- Boolean literal handling (`TRUE`, `FALSE` as `PgBoolean`)

### DDL/DML

- `CREATE TABLE IF NOT EXISTS`
- `CREATE TABLE AS SELECT`
- `CREATE TEMPORARY TABLE` (in-memory storage, skips catalog persistence)
- `ALTER TABLE`: ADD/DROP/RENAME COLUMN, RENAME TO, SET/DROP DEFAULT, SET/DROP NOT NULL, ALTER COLUMN TYPE ... USING
- `TRUNCATE TABLE`
- `CREATE SEQUENCE` / `NEXTVAL` / `CURRVAL` / `SETVAL`
- Constraints: `UNIQUE`, `CHECK`, `FOREIGN KEY` (with insert/update/delete validation)
- `INSERT ... ON CONFLICT DO NOTHING/UPDATE` (UPSERT)
- `INSERT ... RETURNING`, `UPDATE ... RETURNING`, `DELETE ... RETURNING`
- `UPDATE ... FROM ...` (join in UPDATE)
- `DELETE ... USING ...` (join in DELETE)
- `SERIAL` / `BIGSERIAL` auto-increment with sequence tracking
- TEXT primary key support (auto-generated integer doc_id)
- `NULLS FIRST` / `NULLS LAST` in ORDER BY
- Column alias in ORDER BY
- Ordinal references in ORDER BY (`ORDER BY 1, 2`)
- `BOOLEAN` column default values (`DEFAULT TRUE/FALSE`)
- `FETCH FIRST n ROWS ONLY` (SQL standard LIMIT alternative)
- Standalone `VALUES` query

### Table Functions

- `GENERATE_SERIES(start, stop[, step])` in FROM clause
- `UNNEST(array)` in FROM clause
- `JSON_EACH` / `JSON_EACH_TEXT` in FROM clause
- `JSON_ARRAY_ELEMENTS` / `JSON_ARRAY_ELEMENTS_TEXT` in FROM clause

### System Catalogs

- `information_schema.columns`
- `pg_catalog.pg_tables`
- `pg_catalog.pg_views`
- `pg_catalog.pg_indexes`

### LATERAL Subquery

- `LATERAL` subquery in FROM clause with per-row re-evaluation
- Outer row columns visible inside the lateral subquery

### Examples

- `examples/sql/joins_and_subqueries.py` — 20 examples: all JOIN types, derived tables, set operations, recursive CTE, INSERT...SELECT, CREATE TABLE AS SELECT
- `examples/sql/analytics.py` — 24 examples: advanced aggregates, window functions, JSON, date/time, string/math functions, UPSERT, DELETE RETURNING
- `examples/fluent/multi_paradigm.py` — 5 scenarios: product discovery, recommendation engine, order analytics, fusion comparison, query plans

### Tests

- 1423 tests across 40 feature-based test files (up from 1000 in v0.5.0)
- Tests organized by feature: `test_ddl.py`, `test_aggregates.py`, `test_scalar_functions.py`, `test_datetime.py`, `test_json.py`, `test_types.py`, `test_sequence.py`, `test_sql_joins.py`, `test_table_functions.py`, `test_window.py`, `test_update_delete.py`, `test_cte.py`, `test_catalog.py`


## 0.5.0 (2026-03-08)

Per-table storage normalization — all storage is now scoped to explicit tables with full bidirectional interop between the fluent API and SQL.

### Breaking Changes

- Removed all global store instances from Engine (`document_store`, `inverted_index`, `vector_index`, `graph_store`, `block_max_index`)
- `engine.add_document()`, `engine.delete_document()`, `engine.add_graph_vertex()`, `engine.add_graph_edge()` now require a `table` parameter
- `engine.query()` now requires a `table` parameter: `engine.query(table="papers")`
- Removed `engine.set_query_vector()` and `engine.set_negative_vector()` — vectors are now inline in SQL via `ARRAY[...]` literals or `$N` parameter binding
- Removed `FROM _default` pseudo-table — all SQL queries must reference a real table
- Removed `engine._build_context()` — replaced by `engine._context_for_table(table_name)`

### Per-Table Architecture

- Each `Table` owns all storage: `document_store`, `inverted_index`, `vector_indexes`, `graph_store`, `block_max_index`
- `BlockMaxIndex` added to `Table` for completeness (both in-memory and SQLite-backed modes)
- Fluent API and SQL API share the same per-table storage — data inserted via SQL is queryable via fluent and vice versa
- `QueryBuilder` propagates `table` parameter through all chained operations (`_chain`, `and_`, `or_`, `not_`, `filter`, `join`, `score_bm25`, `fuse_log_odds`, etc.)

### SQL Compiler

- `_context_for_table()` handles `None` table for FROM-less queries (`SELECT 1 AS val`)
- `_scan_all()` produces a single dummy row for expression-only queries
- `PostingListScanOp` handles `None` document store for table-less queries
- `knn_match(field, vector, k)` and `vector_exclude(field, pos, neg, k, threshold)` use field-based syntax with inline vectors
- `traverse()` and `rpq()` auto-detect the first available table when no table argument is provided

### Documentation

- Updated README and reference guide: all examples use explicit table names
- Rewritten programmatic document API section for per-table architecture
- UQA reference guide PDF added

### Tests

- 1000 tests across 31 test files (up from 999 in v0.4.0)
- All test fixtures updated for per-table access patterns


## 0.4.0 (2026-03-08)

Hierarchical data SQL integration, Arrow native nested types, graph-sourced WHERE.

### SQL Integration

- `path_agg(path, func)`: per-row nested array aggregation (sum, count, avg, min, max) in SELECT
- `path_value(path)`: nested field access in SELECT
- `path_filter(path, value)` / `path_filter(path, op, value)`: hierarchical WHERE predicate with equality and comparison operators
- `BOOLEAN` column type with `DEFAULT TRUE/FALSE` support (`PgBoolean` AST node handling)
- Deferred WHERE for graph-sourced queries: `FROM traverse()/rpq()` with relational WHERE predicates now correctly filter on vertex properties via physical `FilterOp` instead of posting list operators

### Arrow Execution Engine

- Native nested type support: `pa.array(values, from_pandas=True)` for automatic Arrow type inference of list/struct columns
- Removed JSON serialization workaround for complex column values

### Hierarchical Data

- `HierarchicalDocument.eval_path`: implicit array wildcard — when a string path component follows a list, maps over all array elements
- `PathFilterOperator`: any-match semantics — when `eval_path` returns a list, matches if ANY element satisfies the predicate

### Operator Fixes

- `FacetOperator`, `AggregateOperator`, `PathAggregateOperator`: handle `source=None` internally by scanning all document IDs, consistent with `FilterOperator`

### Examples

- Reorganized examples into `examples/fluent/` (4 files) and `examples/sql/` (4 files)
- Fluent API: text_search, vector_and_hybrid, graph, hierarchical
- SQL: basics (DDL/DML/DQL/CTE/window/transactions/views/prepared), functions (text_match/bayesian_match/knn_match/path_agg/path_value/path_filter), graph (traverse/rpq/aggregates/GROUP BY/WHERE), fusion (log_odds/prob_and/prob_or/prob_not/EXPLAIN)

### Tests

- 999 tests across 31 test files (up from 930 in v0.3.0)


## 0.3.0 (2026-03-08)

Disk spilling and multi-index correctness.

### Execution Engine

- Disk spilling for blocking operators when input exceeds `spill_threshold` rows
- `SortOp`: external merge sort — sorted runs spilled to Arrow IPC stream files, merged via k-way min-heap
- `HashAggOp`: Grace hash partitioning — rows hash-distributed into 16 on-disk partitions, each aggregated independently
- `DistinctOp`: hash partition dedup — same partitioning strategy, per-partition deduplication
- `WindowOp`: accepts `spill_threshold` parameter for API consistency
- Spill infrastructure: `SpillManager`, `SpillWriter`, `read_rows_from_ipc`, `merge_sorted_runs` in `execution/spill.py`
- Configurable `spill_threshold` parameter on `Engine` (0 disables, default)

### Bug Fixes

- Fixed `BlockMaxIndex` table-name collision: key changed from `(field, term)` to `(table_name, field, term)` across in-memory dict, SQLite persistence, and all callers (`BlockMaxWANDScorer`, `SQLiteInvertedIndex.load_block_max_into`)
- Added legacy schema migration for old `_global_blockmax` tables without `table_name` column

### Tests

- 930 tests across 30 test files (up from 899 in v0.2.1)


## 0.2.1 (2026-03-08)

Apache Arrow columnar execution engine.

### Execution Engine

- Replaced custom `Batch`/`ColumnVector` with Apache Arrow `RecordBatch`/`Array`
- `Batch` wraps `pyarrow.RecordBatch` with optional selection vector for lazy filtering
- `ColumnVector` wraps `pyarrow.Array` with automatic null handling and Python type conversion
- Zero-copy slicing via `RecordBatch.slice()` in `LimitOp`
- Arrow `take()` kernel for selection vector materialization in `compact()`
- Bulk row conversion via `RecordBatch.to_pydict()` in `to_rows()`
- Arrow type enforcement exposed and fixed hidden bugs in CTE/View type name resolution, `A_Const` expression routing, and NULL-only column handling

### Dependencies

- Added `pyarrow >= 20.0` as a required dependency


## 0.2.0 (2026-03-07)

Production-grade storage, execution engine, advanced SQL features, and query optimization.

### Storage Layer

- SQLite-backed document store (`SQLiteDocumentStore`) with typed per-table columns
- SQLite-backed inverted index (`SQLiteInvertedIndex`) with per-table-field posting lists
- SQLite-backed vector index (`SQLiteVectorIndex`) with write-through HNSW persistence
- SQLite-backed graph store (`SQLiteGraphStore`) with adjacency indexes
- B-tree index infrastructure: `CREATE INDEX` / `DROP INDEX` with optimizer integration
- Index manager with catalog persistence and automatic restoration on restart
- Catalog schema migration for backward compatibility with old-format databases
- `ManagedConnection` proxy for transaction-aware commit suppression
- WAL mode with `check_same_thread=False` for safe concurrent reads

### Execution Engine

- Volcano iterator model with columnar batch processing (`Batch`, `ColumnVector`, `PhysicalOperator`)
- Physical operators: SeqScan, PostingListScan, Filter, Project, ExprProject, Sort, Limit, HashAgg, Distinct, Window
- Expression evaluator: arithmetic, comparison, logical, string/math functions, CASE, CAST, COALESCE, IS NULL, concatenation
- Parallel execution via `ThreadPoolExecutor` for independent operator branches (Union, Intersect, Fusion)
- Configurable `parallel_workers` parameter (default 4, 0 to disable)

### SQL Features

- DML: `UPDATE ... SET ... WHERE`, `DELETE FROM ... WHERE` with expression support
- `OFFSET` clause, `LIKE` / `ILIKE` / `NOT LIKE` / `NOT ILIKE` pattern matching
- Subqueries: `IN (SELECT ...)`, `EXISTS (SELECT ...)`, scalar subqueries
- Correlated subqueries: `WHERE inner.col = outer.col` with per-row substitution
- Common Table Expressions: `WITH name AS (SELECT ...) SELECT ...`
- Views: `CREATE VIEW` / `DROP VIEW [IF EXISTS]` / `SELECT` from views
- Window functions: `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `NTILE`, `LAG`, `LEAD`, `FIRST_VALUE`, `LAST_VALUE`, aggregates `OVER (PARTITION BY ... ORDER BY ...)`
- Prepared statements: `PREPARE name AS ...` / `EXECUTE name(params)` / `DEALLOCATE name`
- Transactions: `BEGIN` / `COMMIT` / `ROLLBACK` / `SAVEPOINT` / `RELEASE SAVEPOINT`

### Query Optimizer

- Cost-based optimizer with equi-depth histograms and Most Common Values (MCV)
- Histogram-aware selectivity estimation for range predicates (BETWEEN, >, <)
- MCV lookup for equality predicates with exact frequency
- Cross-paradigm cardinality estimation for Score, Traverse, PatternMatch, Fusion, Hybrid operators
- Fusion signal reordering by ascending cost (cheapest first)
- B-tree index scan substitution (replace full scans when index scan is cheaper)
- `CostModel` covers all operator types including fusion, graph, and hybrid
- `EXPLAIN` shows detailed plans for all operators (Score, Fusion, Graph, RPQ)

### Tests

- 899 tests across 29 test files (up from 266 in v0.1.0)


## 0.1.0 (2026-03-06)

Initial release of the UQA prototype.

### Core

- PostingList with sorted entries and boolean algebra (union, intersect, complement)
- GeneralizedPostingList for join operations
- HierarchicalDocument with path evaluation

### Storage

- In-memory DocumentStore, InvertedIndex, HNSWIndex (hnswlib), BlockMaxIndex

### Scoring

- BM25 with configurable parameters (k1, b, avgdl)
- Bayesian BM25 — calibrated P(relevant) in [0, 1] with composite prior
- VectorScorer — cosine similarity to probability conversion
- WAND and BlockMaxWAND top-k pruning

### Fusion

- Log-odds conjunction with confidence scaling (Paper 4)
- Probabilistic boolean: AND, OR, NOT in log-space

### Graph

- GraphStore with adjacency lists and label index
- TraverseOperator (BFS), PatternMatchOperator (backtracking)
- RegularPathQueryOperator (Thompson NFA simulation)
- Cross-paradigm operators (ToGraph, FromGraph, SemanticGraphSearch, VertexEmbedding, VectorEnhancedMatch, TextToGraph)

### Joins

- InnerJoinOperator (hash join), SortMergeJoinOperator, IndexJoinOperator
- LeftOuterJoinOperator
- TextSimilarityJoinOperator (Jaccard), VectorSimilarityJoinOperator
- GraphJoinOperator (edge connectivity), CrossParadigmJoinOperator (vertex-document)

### Operators

- Primitive: Term, VectorSimilarity, KNN, Filter, Facet, Score
- Boolean: Union, Intersect, Complement
- Hybrid: HybridTextVector, SemanticFilter, LogOddsFusion, ProbBoolFusion, ProbNot
- Aggregation: Count, Sum, Avg, Min, Max monoids with GroupBy
- Hierarchical: PathFilter, PathProject, PathUnnest

### Planner

- CostModel with operator-type dispatch
- CardinalityEstimator with column statistics (equality, range, IN, BETWEEN)
- QueryOptimizer: filter pushdown, vector threshold merge, intersect reordering
- PlanExecutor with timing stats and EXPLAIN output

### SQL

- pglast-based compiler (PostgreSQL parser)
- DDL: CREATE TABLE, DROP TABLE [IF EXISTS]
- DML: INSERT INTO ... VALUES
- DQL: SELECT [DISTINCT] with WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, JOIN
- EXPLAIN and ANALYZE support
- Extended functions: text_match, bayesian_match, knn_match, traverse_match
- Fusion meta-functions: fuse_log_odds, fuse_prob_and, fuse_prob_or, fuse_prob_not
- FROM-clause table functions: traverse, rpq, text_search
- Per-table storage isolation with DocumentStore + InvertedIndex

### Tools

- `usql` — interactive SQL shell with prompt_toolkit
  - Syntax highlighting (Pygments SQL lexer)
  - Context-aware auto-completion (keywords, table names, column names)
  - Auto-suggest from history
  - Backslash commands: \dt, \d, \ds, \timing, \reset, \q
  - SQL script file execution

### Tests

- 266 tests covering all modules
- Property-based tests with Hypothesis (boolean algebra axioms, scoring monotonicity)
