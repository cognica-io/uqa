#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph queries via SQL examples.

Demonstrates:
  - FROM traverse(start, label, hops): graph traversal as table source
  - FROM rpq(expr, start): regular path query as table source
  - Standard SQL aggregates over graph results (SUM, AVG, COUNT, MIN, MAX)
  - GROUP BY on vertex properties
  - ORDER BY, LIMIT on graph results
  - traverse_match() as WHERE signal
"""

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# ======================================================================
# Data setup: company org chart
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT
    )
""")

gs = engine.get_graph_store("employees")

# Employees
employees = [
    Vertex(
        1,
        "",
        {
            "name": "Alice",
            "role": "ceo",
            "dept": "Executive",
            "salary": 250000,
            "years": 15,
        },
    ),
    Vertex(
        2,
        "",
        {
            "name": "Bob",
            "role": "vp",
            "dept": "Engineering",
            "salary": 180000,
            "years": 12,
        },
    ),
    Vertex(
        3,
        "",
        {"name": "Carol", "role": "vp", "dept": "Sales", "salary": 170000, "years": 10},
    ),
    Vertex(
        4,
        "",
        {
            "name": "Dave",
            "role": "engineer",
            "dept": "Engineering",
            "salary": 130000,
            "years": 6,
        },
    ),
    Vertex(
        5,
        "",
        {
            "name": "Eve",
            "role": "engineer",
            "dept": "Engineering",
            "salary": 125000,
            "years": 4,
        },
    ),
    Vertex(
        6,
        "",
        {
            "name": "Frank",
            "role": "engineer",
            "dept": "Engineering",
            "salary": 120000,
            "years": 3,
        },
    ),
    Vertex(
        7,
        "",
        {
            "name": "Grace",
            "role": "sales",
            "dept": "Sales",
            "salary": 110000,
            "years": 5,
        },
    ),
    Vertex(
        8,
        "",
        {
            "name": "Hank",
            "role": "sales",
            "dept": "Sales",
            "salary": 105000,
            "years": 2,
        },
    ),
]
for v in employees:
    gs.add_vertex(v)

# Management edges
edges = [
    Edge(1, 1, 2, "manages"),
    Edge(2, 1, 3, "manages"),
    Edge(3, 2, 4, "manages"),
    Edge(4, 2, 5, "manages"),
    Edge(5, 2, 6, "manages"),
    Edge(6, 3, 7, "manages"),
    Edge(7, 3, 8, "manages"),
    # Mentorship edges
    Edge(10, 4, 5, "mentors"),
    Edge(11, 4, 6, "mentors"),
    Edge(12, 7, 8, "mentors"),
]
for e in edges:
    gs.add_edge(e)


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<15}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<15,.1f}")
            else:
                vals.append(str(v)[:15].ljust(15))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Graph SQL Examples")
print("=" * 70)


# ==================================================================
# FROM traverse(): basic graph traversal
# ==================================================================
show(
    "1. CEO's direct reports",
    engine.sql(
        "SELECT name, role, salary FROM traverse(1, 'manages', 1) "
        "WHERE name != 'Alice' ORDER BY salary DESC"
    ),
)

show(
    "2. Full org tree (3 hops)",
    engine.sql(
        "SELECT name, role, dept, salary FROM traverse(1, 'manages', 3) "
        "ORDER BY salary DESC"
    ),
)

show(
    "3. Bob's team (2 hops)",
    engine.sql(
        "SELECT name, role, years FROM traverse(2, 'manages', 2) ORDER BY years DESC"
    ),
)


# ==================================================================
# Aggregates over graph traversal
# ==================================================================
show(
    "4. SUM salary of Bob's team",
    engine.sql("SELECT SUM(salary) AS total_salary FROM traverse(2, 'manages', 2)"),
)

show(
    "5. AVG salary of Bob's team",
    engine.sql("SELECT AVG(salary) AS avg_salary FROM traverse(2, 'manages', 2)"),
)

show(
    "6. COUNT of full org",
    engine.sql("SELECT COUNT(*) AS headcount FROM traverse(1, 'manages', 3)"),
)

show(
    "7. Salary range of full org",
    engine.sql(
        "SELECT MIN(salary) AS lowest, MAX(salary) AS highest "
        "FROM traverse(1, 'manages', 3)"
    ),
)


# ==================================================================
# GROUP BY on graph results
# ==================================================================
show(
    "8. Headcount by role",
    engine.sql(
        "SELECT role, COUNT(*) AS cnt, AVG(salary) AS avg_sal "
        "FROM traverse(1, 'manages', 3) GROUP BY role ORDER BY avg_sal DESC"
    ),
)

show(
    "9. Dept summary",
    engine.sql(
        "SELECT dept, COUNT(*) AS cnt, SUM(salary) AS total "
        "FROM traverse(1, 'manages', 3) GROUP BY dept"
    ),
)


# ==================================================================
# WHERE filter on graph results
# ==================================================================
show(
    "10. Engineers only",
    engine.sql(
        "SELECT name, salary, years FROM traverse(1, 'manages', 3) "
        "WHERE role = 'engineer' ORDER BY salary DESC"
    ),
)

show(
    "11. Salary > 120000",
    engine.sql(
        "SELECT name, role, salary FROM traverse(1, 'manages', 3) "
        "WHERE salary > 120000 ORDER BY salary DESC"
    ),
)


# ==================================================================
# LIMIT on graph results
# ==================================================================
show(
    "12. Top 3 earners in org",
    engine.sql(
        "SELECT name, role, salary FROM traverse(1, 'manages', 3) "
        "ORDER BY salary DESC LIMIT 3"
    ),
)


# ==================================================================
# FROM rpq(): regular path queries
# ==================================================================
show(
    "13. RPQ: manages* from CEO",
    engine.sql(
        "SELECT name, role, salary FROM rpq('manages*', 1) ORDER BY salary DESC"
    ),
)

show(
    "14. RPQ: manages/mentors from Bob",
    engine.sql("SELECT name, role FROM rpq('manages/mentors', 2)"),
)


# ==================================================================
# RPQ with aggregates
# ==================================================================
show(
    "15. RPQ aggregate: total salary via manages*",
    engine.sql(
        "SELECT SUM(salary) AS total, AVG(salary) AS average, COUNT(*) AS cnt "
        "FROM rpq('manages*', 1)"
    ),
)


# ==================================================================
# traverse_match: graph reachability as WHERE signal
# ==================================================================

# Create a SQL table to combine with graph queries
engine.sql("""
    CREATE TABLE reviews (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        rating REAL NOT NULL,
        comment TEXT
    )
""")
engine.sql("""INSERT INTO reviews (employee_id, rating, comment) VALUES
    (1, 4.9, 'exceptional leadership'),
    (2, 4.7, 'strong technical vision'),
    (3, 4.5, 'excellent client relations'),
    (4, 4.8, 'outstanding engineer'),
    (5, 4.3, 'solid contributor'),
    (6, 4.1, 'growing quickly'),
    (7, 4.6, 'top sales performer'),
    (8, 3.9, 'needs development')
""")

# Add management edges to the reviews table's graph store so that
# traverse_match can discover reachable rows.  Review doc_ids 1-8
# correspond to employee vertices 1-8.
for e in edges:
    if e.label == "manages":
        engine.add_graph_edge(e, table="reviews")

show(
    "16. Reviews + traverse_match (Bob's team)",
    engine.sql(
        "SELECT employee_id, rating, comment FROM reviews "
        "WHERE traverse_match(2, 'manages', 2) ORDER BY rating DESC"
    ),
)


print("\n" + "=" * 70)
print("All graph SQL examples completed successfully.")
print("=" * 70)
