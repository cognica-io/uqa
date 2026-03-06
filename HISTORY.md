# History

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
