# History

## 0.8.0 (2026-03-10)

Apache AGE compatible graph query with openCypher and named graphs.

### Graph Query Language (openCypher)

- Cypher lexer, recursive-descent parser, and AST for the openCypher subset
- `CypherCompiler` executes through `GraphPostingList` (binding table pattern) -- every clause transforms a posting list, consistent with UQA's core thesis
- Clauses: `MATCH`, `OPTIONAL MATCH`, `CREATE`, `MERGE` (with `ON CREATE SET` / `ON MATCH SET`), `SET`, `DELETE` / `DETACH DELETE`, `RETURN`, `WITH`, `UNWIND`
- `RETURN` modifiers: `ORDER BY`, `DESC`, `LIMIT`, `SKIP`, `DISTINCT`, aliases (`AS`), expressions
- Pattern matching: node patterns `(n:Label {props})`, relationship patterns `-[r:TYPE*min..max]->`, variable-length paths, cross-label matching, anonymous nodes
- Expression evaluation: property access, function calls, arithmetic, comparison, `AND`/`OR`/`NOT`/`XOR`, `IN`, `IS NULL`/`IS NOT NULL`, `CASE`/`WHEN`/`THEN`/`ELSE`/`END`, list/map literals, list indexing, parameters (`$param`)
- Built-in functions: `id`, `labels`, `type`, `properties`, `keys`, `size`, `length`, `coalesce`, `toInteger`, `toFloat`, `toString`, `toBoolean`, `toLower`, `toUpper`, `trim`, `left`, `right`, `substring`, `replace`, `split`, `reverse`, `startsWith`, `endsWith`, `contains`, `head`, `tail`, `last`, `range`, `abs`, `ceil`, `floor`, `round`, `sign`, `rand`

### Named Graphs

- `create_graph('name')` SQL function -- creates an isolated graph namespace with dedicated SQLite-backed storage
- `drop_graph('name')` SQL function -- removes a named graph and its storage
- Named graph persistence via `_named_graphs` catalog table
- Named graphs restore automatically on engine restart

### SQL Integration (Apache AGE compatible)

- `cypher('graph_name', $$ MATCH ... RETURN ... $$) AS (col1 agtype, col2 agtype)` -- embed Cypher queries in SQL FROM clause
- Column type inference from Cypher result values (integer, real, boolean, text) instead of hardcoding text
- Positional column mapping between Cypher result keys and AS clause column names
- SQL WHERE, ORDER BY, GROUP BY, JOIN work on cypher() results like any other table

### Vertex Labels

- Added required `label` field to `Vertex` datatype (between `vertex_id` and `properties`)
- `vertices_by_label(label)` for efficient label-based vertex retrieval
- SQLite label index on `_graph_vertices` tables
- `remove_vertex(vertex_id)` -- removes vertex and all incident edges (both in-memory and SQLite)
- `remove_edge(edge_id)` -- removes single edge (both in-memory and SQLite)
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

- Fixed window functions ignoring default frame when `ORDER BY` is present -- now applies SQL-standard `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`

### Scalar Functions

- Fixed `LTRIM`/`RTRIM`/`BTRIM` ignoring the character-set argument
- Added `CONCAT_WS(separator, str1, str2, ...)` -- concatenate with separator, skipping NULLs
- Added `TO_CHAR`, `TO_DATE`, `TO_TIMESTAMP` -- date/time formatting and parsing with PostgreSQL format strings
- Added `MAKE_DATE(year, month, day)` -- construct a date from components
- Added `AGE(timestamp, timestamp)` -- compute interval between two timestamps

### Type System

- Added `INTERVAL` as a recognized CAST target type
- Added `NamedArgExpr` handling for `MAKE_INTERVAL(days => 5, hours => 3)` syntax
- Added PostgreSQL array literal parsing (`'{name,age}'`) for `?&` and `?|` JSON operators

### Storage Layer

- Fixed SQLite thread safety: `ManagedConnection` now serializes all operations with a threading lock and provides atomic `execute_fetchall`/`execute_fetchone` methods
- `SQLiteInvertedIndex` and `SQLiteDocumentStore` use atomic fetch methods to prevent cursor interleaving under concurrent access from the parallel executor
- Fixed `test_text_search_works_after_restart` -- the last remaining test failure

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
