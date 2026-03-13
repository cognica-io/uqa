# History

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
