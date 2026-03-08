#!/usr/bin/env python3
"""Standard SQL examples using the engine.sql() API.

Demonstrates:
  - DDL: CREATE TABLE, DROP TABLE, CREATE VIEW
  - DML: INSERT, UPDATE, DELETE
  - DQL: SELECT, WHERE, ORDER BY, LIMIT, OFFSET, DISTINCT
  - Aggregation: GROUP BY, HAVING, COUNT, SUM, AVG, MIN, MAX
  - CTE (WITH ... AS), window functions, subqueries
  - Transactions: BEGIN, COMMIT, ROLLBACK, SAVEPOINT
  - Prepared statements: PREPARE, EXECUTE, DEALLOCATE
  - EXPLAIN and ANALYZE
"""

from uqa.engine import Engine

engine = Engine()


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    # Header
    header = "  " + " | ".join(f"{c:<15}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = [str(row.get(c, ""))[:15].ljust(15) for c in result.columns]
        print("  " + " | ".join(vals))


print("=" * 70)
print("Standard SQL Examples")
print("=" * 70)


# ==================================================================
# DDL: CREATE TABLE
# ==================================================================
engine.sql("""
    CREATE TABLE employees (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        dept TEXT NOT NULL,
        role TEXT NOT NULL,
        salary INTEGER NOT NULL,
        years INTEGER DEFAULT 0,
        active BOOLEAN DEFAULT TRUE
    )
""")
print("\n--- 1. CREATE TABLE employees ---")
print("  Table created.")


# ==================================================================
# DML: INSERT
# ==================================================================
engine.sql("""INSERT INTO employees (name, dept, role, salary, years, active) VALUES
    ('Alice',   'Engineering', 'manager',  150000, 12, TRUE),
    ('Bob',     'Engineering', 'senior',   130000, 8,  TRUE),
    ('Charlie', 'Engineering', 'junior',   95000,  2,  TRUE),
    ('Diana',   'Sales',       'manager',  140000, 10, TRUE),
    ('Eve',     'Sales',       'senior',   120000, 6,  TRUE),
    ('Frank',   'Sales',       'junior',   85000,  1,  TRUE),
    ('Grace',   'Marketing',   'manager',  135000, 9,  TRUE),
    ('Hank',    'Marketing',   'senior',   115000, 5,  TRUE),
    ('Ivy',     'Engineering', 'senior',   125000, 7,  FALSE),
    ('Jack',    'Engineering', 'intern',   60000,  0,  TRUE)
""")
print("\n--- 2. INSERT 10 employees ---")
print("  10 rows inserted.")


# ==================================================================
# DQL: Basic SELECT
# ==================================================================
show("3. SELECT * (first 5)", engine.sql(
    "SELECT * FROM employees ORDER BY id LIMIT 5"
))


# ==================================================================
# WHERE: comparisons, IN, BETWEEN, LIKE
# ==================================================================
show("4. WHERE dept = 'Engineering'", engine.sql(
    "SELECT name, role, salary FROM employees WHERE dept = 'Engineering' ORDER BY salary DESC"
))

show("5. WHERE salary BETWEEN 100000 AND 140000", engine.sql(
    "SELECT name, dept, salary FROM employees WHERE salary BETWEEN 100000 AND 140000"
))

show("6. WHERE role IN ('manager', 'senior')", engine.sql(
    "SELECT name, dept, role FROM employees WHERE role IN ('manager', 'senior')"
))

show("7. WHERE name LIKE 'A%' OR name LIKE 'B%'", engine.sql(
    "SELECT name, dept FROM employees WHERE name LIKE 'A%' OR name LIKE 'B%'"
))


# ==================================================================
# DISTINCT
# ==================================================================
show("8. SELECT DISTINCT dept", engine.sql(
    "SELECT DISTINCT dept FROM employees"
))


# ==================================================================
# Aggregation: GROUP BY, HAVING
# ==================================================================
show("9. GROUP BY dept", engine.sql(
    "SELECT dept, COUNT(*) AS headcount, AVG(salary) AS avg_salary "
    "FROM employees WHERE active = TRUE GROUP BY dept"
))

show("10. GROUP BY + HAVING", engine.sql(
    "SELECT dept, SUM(salary) AS total_salary "
    "FROM employees GROUP BY dept HAVING SUM(salary) > 300000"
))

show("11. Aggregate-only (no GROUP BY)", engine.sql(
    "SELECT COUNT(*) AS total, AVG(salary) AS avg, MIN(salary) AS lo, MAX(salary) AS hi "
    "FROM employees WHERE active = TRUE"
))


# ==================================================================
# Computed expressions
# ==================================================================
show("12. Computed: salary * 1.1 raise", engine.sql(
    "SELECT name, salary, salary * 1.1 AS new_salary FROM employees "
    "WHERE dept = 'Engineering' AND active = TRUE ORDER BY salary DESC"
))


# ==================================================================
# CASE expression
# ==================================================================
show("13. CASE expression", engine.sql("""
    SELECT name, salary,
        CASE
            WHEN salary >= 130000 THEN 'high'
            WHEN salary >= 100000 THEN 'mid'
            ELSE 'entry'
        END AS tier
    FROM employees WHERE active = TRUE ORDER BY salary DESC LIMIT 6
"""))


# ==================================================================
# Subquery: IN (SELECT ...)
# ==================================================================
show("14. Subquery: dept with managers", engine.sql("""
    SELECT name, dept, salary FROM employees
    WHERE dept IN (SELECT dept FROM employees WHERE role = 'manager')
    ORDER BY dept, salary DESC
"""))


# ==================================================================
# CTE (WITH ... AS)
# ==================================================================
show("15. CTE: department stats", engine.sql("""
    WITH dept_stats AS (
        SELECT dept, AVG(salary) AS avg_salary, COUNT(*) AS cnt
        FROM employees WHERE active = TRUE GROUP BY dept
    )
    SELECT dept, avg_salary, cnt FROM dept_stats ORDER BY avg_salary DESC
"""))


# ==================================================================
# Window functions
# ==================================================================
show("16. Window: ROW_NUMBER by dept", engine.sql("""
    SELECT name, dept, salary,
        ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rank
    FROM employees WHERE active = TRUE
"""))

show("17. Window: RANK + running SUM", engine.sql("""
    SELECT name, salary,
        RANK() OVER (ORDER BY salary DESC) AS salary_rank,
        SUM(salary) OVER (ORDER BY salary DESC) AS running_total
    FROM employees WHERE active = TRUE LIMIT 5
"""))


# ==================================================================
# UPDATE
# ==================================================================
engine.sql("UPDATE employees SET salary = 100000 WHERE name = 'Charlie'")
show("18. After UPDATE Charlie salary", engine.sql(
    "SELECT name, salary FROM employees WHERE name = 'Charlie'"
))


# ==================================================================
# DELETE
# ==================================================================
engine.sql("DELETE FROM employees WHERE active = FALSE")
show("19. After DELETE inactive", engine.sql(
    "SELECT COUNT(*) AS remaining FROM employees"
))


# ==================================================================
# Transactions (requires persistent engine)
# ==================================================================
print("\n--- 20. Transactions ---")
import tempfile, os
txn_engine = Engine(db_path=os.path.join(tempfile.mkdtemp(), "txn_test.db"))
txn_engine.sql("""
    CREATE TABLE txn_test (id SERIAL PRIMARY KEY, val INTEGER NOT NULL)
""")
txn_engine.sql("INSERT INTO txn_test (val) VALUES (100)")
txn_engine.sql("BEGIN")
txn_engine.sql("UPDATE txn_test SET val = 200 WHERE id = 1")
txn_engine.sql("SAVEPOINT sp1")
txn_engine.sql("UPDATE txn_test SET val = 999 WHERE id = 1")
txn_engine.sql("ROLLBACK TO SAVEPOINT sp1")
txn_engine.sql("COMMIT")
result = txn_engine.sql("SELECT val FROM txn_test WHERE id = 1")
print(f"  val after txn: {result.rows[0]['val']}")
print("  (ROLLBACK TO SAVEPOINT reversed the 999 update)")


# ==================================================================
# Views
# ==================================================================
engine.sql("""
    CREATE VIEW senior_staff AS
    SELECT name, dept, salary FROM employees
    WHERE role IN ('manager', 'senior') AND active = TRUE
""")
show("21. SELECT from view", engine.sql(
    "SELECT * FROM senior_staff ORDER BY salary DESC"
))


# ==================================================================
# Prepared statements
# ==================================================================
engine.sql("PREPARE find_by_dept(text) AS SELECT name, salary FROM employees WHERE dept = $1")
show("22. EXECUTE prepared(Engineering)", engine.sql(
    "EXECUTE find_by_dept('Engineering')"
))
show("23. EXECUTE prepared(Sales)", engine.sql(
    "EXECUTE find_by_dept('Sales')"
))
engine.sql("DEALLOCATE find_by_dept")
print("\n  Prepared statement deallocated.")


# ==================================================================
# ANALYZE + EXPLAIN
# ==================================================================
engine.sql("ANALYZE employees")
print("\n--- 24. ANALYZE employees ---")
print("  Column statistics collected.")

result = engine.sql("EXPLAIN SELECT * FROM employees WHERE dept = 'Engineering'")
print("\n--- 25. EXPLAIN ---")
for row in result.rows:
    print(f"  {row['plan']}")


print("\n" + "=" * 70)
print("All standard SQL examples completed successfully.")
print("=" * 70)
