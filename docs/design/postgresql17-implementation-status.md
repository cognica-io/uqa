# PostgreSQL 17 Feature Implementation Status

**Last updated:** 2026-03-10
**Total tests:** 1691 (423 PG17-specific across feature-based test files)

---

## Summary

| Priority | Total Features | Completed | Remaining |
|----------|---------------|-----------|-----------|
| P0 | 14 | 14 | 0 |
| P1 | 22 | 22 | 0 |
| P2 | 48 | 48 | 0 |
| P3 | 19 | 11 | 8 |
| **Total** | **103** | **95** | **8** |

---

## P0 — COMPLETED (14/14)

All must-have features for basic SQL compatibility.

| # | Feature | Category | Test Class |
|---|---------|----------|------------|
| 1 | `CREATE TABLE IF NOT EXISTS` | DDL | TestCreateTableIfNotExists |
| 2 | `NULLS FIRST` / `NULLS LAST` | DQL | TestNullsOrdering |
| 3 | Column alias in `ORDER BY` | DQL | TestColumnAliasOrderBy |
| 4 | `GREATEST` / `LEAST` / `NULLIF` | Scalar | TestGreatestLeastNullif |
| 5 | `POSITION`, `CHAR_LENGTH`, `LPAD`, `RPAD`, `REPEAT`, `REVERSE`, `SPLIT_PART` | String | TestStringFunctions, TestStringFunctionAliases |
| 6 | `POWER`/`POW`, `SQRT`, `LOG`, `LN`, `EXP`, `MOD`, `TRUNC` | Math | TestMathFunctions, TestLogTwoArgs |
| 7 | `COUNT(DISTINCT col)` | Aggregate | TestCountDistinct |
| 8 | `STRING_AGG(col, delim)` | Aggregate | TestStringAgg, TestStringAggDistinct |
| 9 | `INSERT INTO ... SELECT` | DML | TestInsertSelect |
| 10 | Subquery in `FROM` (derived table) | DQL | TestDerivedTables, TestDerivedTableAliasCollision |
| 11 | `UNION [ALL]` / `INTERSECT [ALL]` / `EXCEPT [ALL]` | DQL | TestSetOperations |
| 12 | `DATE` / `TIMESTAMP` type support | Type | TestDateTimeTypes |
| 13 | `NOW()` / `CURRENT_TIMESTAMP` / `CURRENT_DATE` | DateTime | TestDateTimeFunctions |
| 14 | `EXTRACT` / `DATE_PART` / `DATE_TRUNC` | DateTime | TestExtractDatePartDateTrunc |

**Files modified:** `compiler.py`, `expr_evaluator.py`, `relational.py`, `table.py`, `sqlite_document_store.py`

---

## P1 — COMPLETED (22/22)

Important features for real-world SQL workloads.

| # | Feature | Category | Test Class |
|---|---------|----------|------------|
| 1 | `ALTER TABLE ADD COLUMN` | DDL | TestAlterTableAddColumn |
| 2 | `ALTER TABLE DROP COLUMN` | DDL | TestAlterTableDropColumn |
| 3 | `ALTER TABLE RENAME COLUMN` | DDL | TestAlterTableRenameColumn |
| 4 | `ALTER TABLE RENAME TO` | DDL | TestAlterTableRenameTo |
| 5 | `ALTER TABLE ALTER COLUMN SET/DROP DEFAULT` | DDL | TestAlterTableDefault |
| 6 | `ALTER TABLE ALTER COLUMN SET/DROP NOT NULL` | DDL | TestAlterTableNotNull |
| 7 | `UNIQUE` constraint | DDL | TestUniqueConstraint |
| 8 | `CHECK` constraint | DDL | TestCheckConstraint |
| 9 | `TRUNCATE TABLE` | DDL | TestTruncateTable |
| 10 | `INSERT ... ON CONFLICT DO NOTHING` | DML | TestOnConflictDoNothing |
| 11 | `INSERT ... ON CONFLICT DO UPDATE` (UPSERT) | DML | TestOnConflictDoUpdate |
| 12 | `INSERT ... RETURNING *` | DML | TestInsertReturning |
| 13 | `UPDATE ... RETURNING *` | DML | TestUpdateReturning |
| 14 | `DELETE ... RETURNING *` | DML | TestDeleteReturning |
| 15 | `RIGHT [OUTER] JOIN` / `FULL [OUTER] JOIN` / `CROSS JOIN` | DQL | TestRightJoin, TestFullOuterJoin, TestCrossJoin |
| 16 | Non-equality JOIN conditions | DQL | TestInnerJoin, TestLeftJoin |
| 17 | `WITH RECURSIVE` | DQL | TestWithRecursive |
| 18 | Multiple FROM tables (implicit cross join) | DQL | TestMultipleFromTables |
| 19 | Column alias / ordinal in `GROUP BY`, expression in `GROUP BY`, complex `HAVING` | DQL | TestGroupByEnhanced, TestComplexHaving |
| 20 | `JSON`/`JSONB` type, `->`, `->>` operators, `JSON_BUILD_OBJECT`, `JSON_BUILD_ARRAY`, `JSON_AGG` | Type/JSON | TestJSONType, TestJSONOperators, TestJSONFunctions |
| 21 | `ROWS BETWEEN` frame, `PERCENT_RANK`, `CUME_DIST`, `NTH_VALUE` | Window | TestWindowFrames, TestPercentRank, TestCumeDist, TestNthValue |
| 22 | `INITCAP`, `TRANSLATE`, `ASCII`, `CHR`, `STARTS_WITH`, `SIGN`, `PI`, `RANDOM`, `GENERATE_SERIES`, `REGEXP_REPLACE`, `NUMERIC(p,s)`, `INTERVAL`, `TIME`, `TIMESTAMPTZ`, `AGE`, `TO_CHAR`, `TO_DATE`, `TO_TIMESTAMP`, `MAKE_DATE`, `CURRENT_TIME`, `BOOL_AND`/`EVERY`, `BOOL_OR`, `ARRAY_AGG`, `AGGREGATE FILTER`, `AGGREGATE ORDER BY`, `information_schema` | Scalar/Misc | TestScalarFunctionsStep7, TestArrayAgg, TestBoolAnd, TestBoolOr, TestAggregateFilter, TestAggregateOrderBy, TestNumericPrecisionScale, TestGenerateSeries, TestInformationSchema |

**Files modified:** `compiler.py`, `expr_evaluator.py`, `relational.py`, `table.py`, `sqlite_document_store.py`, `catalog.py`

---

## P2 — COMPLETED (48/48)

### Previously completed (35 features)

| # | Feature | Category | Test Class |
|---|---------|----------|------------|
| 1 | `OCTET_LENGTH(str)` | String | TestOctetLength |
| 2 | `MD5(str)` | String | TestMD5 |
| 3 | `FORMAT(formatstr, ...)` | String | TestFormat |
| 4 | `OVERLAY(str PLACING repl FROM pos [FOR len])` | String | TestOverlay |
| 5 | `REGEXP_MATCH(str, pat)` | String | TestRegexpMatch |
| 6 | `REGEXP_REPLACE` (extended, already in P1) | String | TestRegexpReplace |
| 7 | `CBRT(x)` | Math | TestCbrt |
| 8 | `DEGREES(x)` / `RADIANS(x)` | Math | TestDegreesRadians |
| 9 | `SIN`/`COS`/`TAN`/`ASIN`/`ACOS`/`ATAN`/`ATAN2` | Math | TestTrigFunctions |
| 10 | `DIV(a, b)` | Math | TestDiv |
| 11 | `GCD(a, b)` / `LCM(a, b)` | Math | TestGcdLcm |
| 12 | `WIDTH_BUCKET(val, lo, hi, n)` | Math | TestWidthBucket |
| 13 | `ARRAY` types (`INTEGER[]`, etc.) | Type | TestArrayLiteral, TestArrayColumn |
| 14 | Array functions (`ARRAY_LENGTH`, `ARRAY_UPPER`, `ARRAY_LOWER`, `ARRAY_CAT`, `ARRAY_APPEND`, `ARRAY_REMOVE`, `CARDINALITY`) | Scalar | TestArrayFunctions |
| 15 | `UUID` type / `GEN_RANDOM_UUID()` | Type | TestUUID |
| 16 | `BYTEA` type | Type | TestBytea |
| 17 | `STDDEV` / `STDDEV_POP` / `STDDEV_SAMP` | Aggregate | TestStddev |
| 18 | `VARIANCE` / `VAR_POP` / `VAR_SAMP` | Aggregate | TestVariance |
| 19 | `PERCENTILE_CONT(frac) WITHIN GROUP (ORDER BY col)` | Aggregate | TestPercentileCont |
| 20 | `PERCENTILE_DISC(frac) WITHIN GROUP (ORDER BY col)` | Aggregate | TestPercentileDisc |
| 21 | `MODE() WITHIN GROUP (ORDER BY col)` | Aggregate | TestMode |
| 22 | `JSON_OBJECT_AGG(key, val)` / `JSONB_OBJECT_AGG` | Aggregate | TestJSONObjectAgg |
| 23 | Named window: `WINDOW w AS (...)` | Window | TestNamedWindow |
| 24 | `RANGE BETWEEN` frame | Window | TestRangeBetween |
| 25 | `#>` / `#>>` (JSON path operators) | JSON | TestJSONPathOperator |
| 26 | `@>` / `<@` (JSON containment) | JSON | TestJSONContainment |
| 27 | `JSONB_SET(target, path, val)` | JSON | TestJSONBSet |
| 28 | `JSON_OBJECT_KEYS(json)` | JSON | TestJSONObjectKeys |
| 29 | `CREATE TABLE AS SELECT` | DDL | TestCreateTableAs |
| 30 | `FETCH FIRST n ROWS ONLY` | DQL | TestFetchFirst |
| 31 | `ALTER TABLE ALTER COLUMN TYPE ... USING` | DDL | TestAlterColumnType |
| 32 | `CREATE SEQUENCE` / `NEXTVAL` / `CURRVAL` / `SETVAL` | Sequence | TestSequence |
| 33 | `pg_catalog.pg_tables` / `pg_catalog.pg_views` | System | TestPGCatalog |
| 34 | `UNNEST(array)` | Table func | TestUnnest |
| 35 | `JSON_EXTRACT_PATH` / `JSON_TYPEOF` | JSON | TestJSONTypeof, TestJSONExtractPath (in P1 test file) |

### Newly completed (13 features)

| # | Feature | Category | Test Class |
|---|---------|----------|------------|
| 36 | `FOREIGN KEY` constraint | DDL | TestForeignKey |
| 37 | `CREATE TEMPORARY TABLE` | DDL | TestCreateTemporaryTable |
| 38 | `UPDATE ... FROM ...` (join in UPDATE) | DML | TestUpdateFrom |
| 39 | `DELETE ... USING ...` (join in DELETE) | DML | TestDeleteUsing |
| 40 | `LATERAL` subquery | DQL | TestLateral |
| 41 | `?` / `?|` / `?&` (JSON key existence) | JSON | TestJSONKeyExistence |
| 42 | `JSON_EACH` / `JSON_EACH_TEXT` | JSON | TestJSONEach |
| 43 | `JSON_ARRAY_ELEMENTS` | JSON | TestJSONArrayElements |
| 44 | `OVERLAPS` operator | DateTime | TestOverlaps |
| 45 | `MAKE_TIMESTAMP` / `MAKE_INTERVAL` / `TO_NUMBER` | DateTime | TestMakeTimestamp, TestMakeInterval, TestToNumber |
| 46 | `VALUES` as standalone query | DQL | TestStandaloneValues |
| 47 | `FILTER (WHERE ...)` on window aggregate | Window | TestWindowFilter |
| 48 | `pg_catalog.pg_indexes` | System | TestPGIndexes |

**Files modified:** `compiler.py`, `expr_evaluator.py`, `relational.py`, `table.py`, `engine.py`

---

## P3 — IN PROGRESS (11/19)

### Completed (11 features)

| # | Feature | Category | Test Class |
|---|---------|----------|------------|
| 4 | `ENCODE(data, format)` / `DECODE` | String | (scalar function) |
| 5 | `REGEXP_SPLIT_TO_TABLE` / `REGEXP_SPLIT_TO_ARRAY` | String | TestRegexpSplitToTable |
| 6 | `MIN_SCALE(numeric)` / `TRIM_SCALE` | Math | (scalar function) |
| 7 | `CORR(y, x)` / `COVAR_POP` / `COVAR_SAMP` | Aggregate | TestCovarianceCorrelation |
| 8 | `REGR_*` (10 regression functions) | Aggregate | TestRegressionFunctions |
| 11 | `ISFINITE(date/ts/interval)` | DateTime | (scalar function) |
| 12 | `CLOCK_TIMESTAMP()` / `TIMEOFDAY()` | DateTime | (scalar function) |
| 13 | `JSONB_STRIP_NULLS` | JSON | (scalar function) |
| 17 | `pg_catalog.pg_type` | System | TestPgType |
| 18 | `ALTER SEQUENCE` | Sequence | TestAlterSequence |
| 19 | `TABLE name` (shorthand for `SELECT * FROM name`) | Misc | TestTableShorthand |

### Remaining (8 features)

| # | Feature | Category | Design Doc Ref |
|---|---------|----------|----------------|
| 1 | `COPY ... FROM/TO` | DML | 2.2.2 |
| 2 | `SELECT ... FOR UPDATE` | DQL | 2.2.3 |
| 3 | `INET` / `CIDR` types | Type | 2.2.4 |
| 9 | `GROUPS BETWEEN` frame | Window | 2.2.7 |
| 10 | `EXCLUDE CURRENT ROW` / `EXCLUDE GROUP` / `EXCLUDE TIES` | Window | 2.2.7 |
| 14 | `JSON_POPULATE_RECORD` | JSON | 2.2.9 |
| 15 | `JSONB_PATH_QUERY` (SQL/JSON path) | JSON | 2.2.9 |
| 16 | `JSON_TABLE` (PG 17) | JSON | 2.2.9 |

**Not planned:** `DO` blocks, PL/pgSQL stored functions.

---

## Files Modified (Cumulative)

| File | P0 | P1 | P2 | P3 | Role |
|------|----|----|-----|-----|------|
| `uqa/sql/compiler.py` | Y | Y | Y | Y | Central SQL compiler: AST dispatch, operator tree construction |
| `uqa/sql/expr_evaluator.py` | Y | Y | Y | Y | Per-row expression evaluation: scalars, casts, aggregates |
| `uqa/execution/relational.py` | Y | Y | Y | Y | Volcano physical operators: HashAggOp, SortOp, WindowOp |
| `uqa/sql/table.py` | Y | Y | Y | -- | Table schema, ColumnDef, type mapping, ForeignKeyDef |
| `uqa/storage/sqlite_document_store.py` | Y | Y | Y | -- | SQLite-backed document storage |
| `uqa/storage/catalog.py` | -- | Y | -- | -- | SQLite system catalog |
| `uqa/engine.py` | -- | -- | Y | -- | Main engine (sequences, temp tables) |

---

## Test Coverage

423 PG17-specific tests distributed across feature-based test files:

| Test File | PG17 Tests | Coverage |
|-----------|-----------|----------|
| `test_sql.py` | 43 | DDL, DML, set operations, derived tables |
| `test_ddl.py` | 36 | ALTER TABLE, TRUNCATE, constraints |
| `test_scalar_functions.py` | 70 | String, math, conditional functions |
| `test_aggregates.py` | 46 | Statistical, string, boolean aggregates |
| `test_datetime.py` | 36 | DATE/TIMESTAMP, EXTRACT, DATE_TRUNC |
| `test_json.py` | 37 | JSON operators, functions, containment |
| `test_types.py` | 14 | ARRAY, UUID, BYTEA |
| `test_sequence.py` | 4 | CREATE SEQUENCE, NEXTVAL, CURRVAL |
| `test_sql_joins.py` | 14 | All JOIN types, LATERAL |
| `test_table_functions.py` | 7 | GENERATE_SERIES, UNNEST |
| `test_window.py` | 52 | Window functions, frames, FILTER |
| `test_update_delete.py` | 37 | RETURNING, UPSERT, UPDATE FROM |
| `test_cte.py` | 8 | Recursive CTE |
| `test_catalog.py` | 19 | information_schema, pg_catalog |
| **Total PG17 tests** | **423** | |
| **Total project tests** | **1423** | |

All 1423 tests pass across 40 test files.
