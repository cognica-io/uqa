# History

## 0.3.0 (2026-03-08)

Disk spilling and multi-index correctness.

### Execution Engine

- Disk spilling for blocking operators when input exceeds `spill_threshold` rows
- `SortOp`: external merge sort -- sorted runs spilled to Arrow IPC stream files, merged via k-way min-heap
- `HashAggOp`: Grace hash partitioning -- rows hash-distributed into 16 on-disk partitions, each aggregated independently
- `DistinctOp`: hash partition dedup -- same partitioning strategy, per-partition deduplication
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
