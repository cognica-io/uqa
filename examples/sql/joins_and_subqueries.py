#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""JOINs, subqueries, set operations, and derived tables.

Demonstrates:
  - INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL OUTER JOIN, CROSS JOIN
  - Subquery in FROM (derived table)
  - INSERT INTO ... SELECT
  - UNION / INTERSECT / EXCEPT (with ALL variants)
  - WITH RECURSIVE (recursive CTE)
  - Multiple FROM tables (implicit cross join)
  - CREATE TABLE AS SELECT
"""

from uqa.engine import Engine

engine = Engine()


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<15}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = [str(row.get(c, ""))[:15].ljust(15) for c in result.columns]
        print("  " + " | ".join(vals))


print("=" * 70)
print("JOINs, Subqueries & Set Operations")
print("=" * 70)


# ==================================================================
# Setup: related tables
# ==================================================================
engine.sql("""
    CREATE TABLE departments (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        budget INTEGER NOT NULL,
        location TEXT NOT NULL
    )
""")
engine.sql("""INSERT INTO departments (name, budget, location) VALUES
    ('Engineering', 5000000, 'Seoul'),
    ('Sales',       3000000, 'Busan'),
    ('Marketing',   2000000, 'Seoul'),
    ('Research',    4000000, 'Daejeon')
""")

engine.sql("""
    CREATE TABLE employees (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        dept_id INTEGER,
        salary INTEGER NOT NULL,
        hire_year INTEGER NOT NULL
    )
""")
engine.sql("""INSERT INTO employees (name, dept_id, salary, hire_year) VALUES
    ('Alice',   1, 150000, 2015),
    ('Bob',     1, 130000, 2018),
    ('Charlie', 2, 120000, 2019),
    ('Diana',   2, 110000, 2020),
    ('Eve',     3, 105000, 2021),
    ('Frank',   NULL, 95000, 2022),
    ('Grace',   1, 140000, 2016)
""")

engine.sql("""
    CREATE TABLE projects (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        lead_id INTEGER NOT NULL,
        dept_id INTEGER NOT NULL,
        status TEXT NOT NULL
    )
""")
engine.sql("""INSERT INTO projects (name, lead_id, dept_id, status) VALUES
    ('Atlas',    1, 1, 'active'),
    ('Beacon',   3, 2, 'active'),
    ('Compass',  2, 1, 'completed'),
    ('Delta',    5, 3, 'active'),
    ('Echo',     7, 1, 'planning')
""")

engine.sql("""
    CREATE TABLE salary_grades (
        id SERIAL PRIMARY KEY,
        grade TEXT NOT NULL,
        min_salary INTEGER NOT NULL,
        max_salary INTEGER NOT NULL
    )
""")
engine.sql("""INSERT INTO salary_grades (grade, min_salary, max_salary) VALUES
    ('Junior',  80000, 110000),
    ('Mid',     110001, 135000),
    ('Senior',  135001, 160000)
""")

print("\n  Tables created: departments, employees, projects, salary_grades")


# ==================================================================
# 1. INNER JOIN
# ==================================================================
show(
    "1. INNER JOIN: employees with departments",
    engine.sql("""
    SELECT e.name, d.name AS dept, e.salary
    FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    ORDER BY e.salary DESC
"""),
)


# ==================================================================
# 2. LEFT JOIN (includes employees without department)
# ==================================================================
show(
    "2. LEFT JOIN: all employees, even unassigned",
    engine.sql("""
    SELECT e.name, COALESCE(d.name, '(none)') AS dept, e.salary
    FROM employees e
    LEFT JOIN departments d ON e.dept_id = d.id
    ORDER BY e.name
"""),
)


# ==================================================================
# 3. RIGHT JOIN (includes departments without employees)
# ==================================================================
show(
    "3. RIGHT JOIN: all departments, even empty",
    engine.sql("""
    SELECT COALESCE(e.name, '(vacant)') AS employee, d.name AS dept
    FROM employees e
    RIGHT JOIN departments d ON e.dept_id = d.id
    ORDER BY d.name, e.name
"""),
)


# ==================================================================
# 4. FULL OUTER JOIN
# ==================================================================
show(
    "4. FULL OUTER JOIN: all employees + all departments",
    engine.sql("""
    SELECT
        COALESCE(e.name, '(vacant)') AS employee,
        COALESCE(d.name, '(none)') AS dept
    FROM employees e
    FULL OUTER JOIN departments d ON e.dept_id = d.id
    ORDER BY dept, employee
"""),
)


# ==================================================================
# 5. CROSS JOIN
# ==================================================================
show(
    "5. CROSS JOIN: employees x salary grades (first 8)",
    engine.sql("""
    SELECT e.name, g.grade, g.min_salary, g.max_salary
    FROM employees e
    CROSS JOIN salary_grades g
    ORDER BY e.name, g.min_salary
    LIMIT 8
"""),
)


# ==================================================================
# 6. Non-equality JOIN: salary-to-grade mapping
# ==================================================================
show(
    "6. Non-equality JOIN: salary grade lookup",
    engine.sql("""
    SELECT e.name, e.salary, g.grade
    FROM employees e
    INNER JOIN salary_grades g
        ON e.salary >= g.min_salary AND e.salary <= g.max_salary
    ORDER BY e.salary DESC
"""),
)


# ==================================================================
# 7. Self-JOIN via multiple FROM tables
# ==================================================================
show(
    "7. Multiple FROM: employees in same department",
    engine.sql("""
    SELECT e1.name AS employee1, e2.name AS employee2
    FROM employees e1, employees e2
    WHERE e1.dept_id = e2.dept_id
      AND e1.name < e2.name
    ORDER BY e1.name
"""),
)


# ==================================================================
# 8. Multi-table JOIN: employee -> department -> project
# ==================================================================
show(
    "8. Multi-table JOIN: employees leading projects",
    engine.sql("""
    SELECT e.name AS lead, d.name AS dept, p.name AS project, p.status
    FROM projects p
    INNER JOIN employees e ON p.lead_id = e.id
    INNER JOIN departments d ON p.dept_id = d.id
    ORDER BY p.name
"""),
)


# ==================================================================
# 9. Subquery in FROM (derived table)
# ==================================================================
show(
    "9. Derived table: department salary stats",
    engine.sql("""
    SELECT dept_stats.dept, dept_stats.headcount, dept_stats.avg_salary
    FROM (
        SELECT d.name AS dept,
               COUNT(*) AS headcount,
               AVG(e.salary) AS avg_salary
        FROM employees e
        INNER JOIN departments d ON e.dept_id = d.id
        GROUP BY d.name
    ) AS dept_stats
    WHERE dept_stats.headcount >= 2
    ORDER BY dept_stats.avg_salary DESC
"""),
)


# ==================================================================
# 10. INSERT INTO ... SELECT
# ==================================================================
engine.sql("""
    CREATE TABLE senior_employees (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        dept TEXT,
        salary INTEGER NOT NULL
    )
""")
engine.sql("""
    INSERT INTO senior_employees (name, dept, salary)
    SELECT e.name, d.name, e.salary
    FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    WHERE e.salary >= 130000
""")
show(
    "10. INSERT INTO ... SELECT result",
    engine.sql("SELECT name, dept, salary FROM senior_employees ORDER BY salary DESC"),
)


# ==================================================================
# 11. UNION
# ==================================================================
show(
    "11. UNION: engineering + sales employees",
    engine.sql("""
    SELECT e.name, d.name AS dept FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    WHERE d.name = 'Engineering'
    UNION
    SELECT e.name, d.name AS dept FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    WHERE d.name = 'Sales'
    ORDER BY dept, name
"""),
)


# ==================================================================
# 12. UNION ALL (preserves duplicates)
# ==================================================================
show(
    "12. UNION ALL: project leads + high earners (may overlap)",
    engine.sql("""
    SELECT e.name FROM employees e
    INNER JOIN projects p ON p.lead_id = e.id
    UNION ALL
    SELECT name FROM employees WHERE salary >= 130000
    ORDER BY name
"""),
)


# ==================================================================
# 13. INTERSECT: employees who are BOTH project leads AND high earners
# ==================================================================
show(
    "13. INTERSECT: project leads who earn >= 130000",
    engine.sql("""
    SELECT e.name FROM employees e
    INNER JOIN projects p ON p.lead_id = e.id
    INTERSECT
    SELECT name FROM employees WHERE salary >= 130000
    ORDER BY name
"""),
)


# ==================================================================
# 14. EXCEPT: project leads who are NOT high earners
# ==================================================================
show(
    "14. EXCEPT: project leads earning < 130000",
    engine.sql("""
    SELECT e.name FROM employees e
    INNER JOIN projects p ON p.lead_id = e.id
    EXCEPT
    SELECT name FROM employees WHERE salary >= 130000
    ORDER BY name
"""),
)


# ==================================================================
# 15. WITH RECURSIVE: management hierarchy
# ==================================================================
engine.sql("""
    CREATE TABLE org_chart (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        manager_id INTEGER
    )
""")
engine.sql("""INSERT INTO org_chart (name, manager_id) VALUES
    ('CEO',   NULL),
    ('VP1',   1),
    ('VP2',   1),
    ('Dir1',  2),
    ('Dir2',  2),
    ('Mgr1',  4),
    ('Mgr2',  5)
""")

show(
    "15. WITH RECURSIVE: full org tree from CEO",
    engine.sql("""
    WITH RECURSIVE org_tree AS (
        SELECT id, name, manager_id, 1 AS depth
        FROM org_chart
        WHERE manager_id IS NULL
        UNION ALL
        SELECT o.id, o.name, o.manager_id, t.depth + 1
        FROM org_chart o
        INNER JOIN org_tree t ON o.manager_id = t.id
    )
    SELECT name, depth FROM org_tree ORDER BY depth, name
"""),
)


# ==================================================================
# 16. CREATE TABLE AS SELECT
# ==================================================================
engine.sql("""
    CREATE TABLE dept_summary AS
    SELECT d.name AS dept,
           COUNT(*) AS headcount,
           SUM(e.salary) AS total_salary,
           AVG(e.salary) AS avg_salary
    FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    GROUP BY d.name
""")
show(
    "16. CREATE TABLE AS SELECT",
    engine.sql(
        "SELECT dept, headcount, total_salary, avg_salary "
        "FROM dept_summary ORDER BY total_salary DESC"
    ),
)


# ==================================================================
# 17. Chained UNION with ORDER BY and LIMIT
# ==================================================================
show(
    "17. Chained UNION with LIMIT",
    engine.sql("""
    SELECT name, 'engineering' AS source FROM employees WHERE dept_id = 1
    UNION ALL
    SELECT name, 'sales' AS source FROM employees WHERE dept_id = 2
    UNION ALL
    SELECT name, 'marketing' AS source FROM employees WHERE dept_id = 3
    ORDER BY name
    LIMIT 5
"""),
)


# ==================================================================
# 18. Correlated subquery: employees earning above department average
# ==================================================================
show(
    "18. Correlated subquery: above dept avg salary",
    engine.sql("""
    SELECT e.name, e.salary, d.name AS dept
    FROM employees e
    INNER JOIN departments d ON e.dept_id = d.id
    WHERE e.salary > (
        SELECT AVG(e2.salary) FROM employees e2
        WHERE e2.dept_id = e.dept_id
    )
    ORDER BY e.salary DESC
"""),
)


# ==================================================================
# 19. EXISTS subquery: departments with active projects
# ==================================================================
show(
    "19. EXISTS: departments with active projects",
    engine.sql("""
    SELECT d.name AS dept, d.budget
    FROM departments d
    WHERE EXISTS (
        SELECT 1 FROM projects p
        WHERE p.dept_id = d.id AND p.status = 'active'
    )
    ORDER BY d.budget DESC
"""),
)


# ==================================================================
# 20. Scalar subquery: employee count per department inline
# ==================================================================
show(
    "20. Scalar subquery: department + employee count",
    engine.sql("""
    SELECT d.name AS dept,
           d.budget,
           (SELECT COUNT(*) FROM employees e WHERE e.dept_id = d.id) AS headcount
    FROM departments d
    ORDER BY headcount DESC
"""),
)


print("\n" + "=" * 70)
print("All JOIN/subquery/set operation examples completed successfully.")
print("=" * 70)
