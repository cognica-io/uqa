#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Full-text search @@ operator examples.

Demonstrates:
  - column @@ 'term'               -- single term search
  - column @@ '"phrase"'            -- phrase search
  - column @@ 'a AND b'            -- boolean AND
  - column @@ 'a OR b'             -- boolean OR
  - column @@ 'NOT term'           -- boolean NOT
  - column @@ 'field:term'         -- field-specific search
  - _all @@ 'query'               -- all-field search
  - column @@ 'text AND emb:[...]' -- hybrid text + vector fusion
  - implicit AND, grouping, combined with relational filters
"""

import numpy as np

from uqa.engine import Engine

# ======================================================================
# Data setup
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE articles (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        embedding VECTOR(4)
    )
""")

rows = [
    (
        "database internals",
        "a guide to storage engines and distributed systems",
        [0.9, 0.1, 0.0, 0.0],
    ),
    (
        "full text search algorithms",
        "inverted index and BM25 scoring for information retrieval",
        [0.1, 0.9, 0.0, 0.0],
    ),
    (
        "wireless sensor networks",
        "low power communication protocols for IoT devices",
        [0.0, 0.0, 0.9, 0.1],
    ),
    (
        "deep learning fundamentals",
        "neural network architectures and training techniques",
        [0.0, 0.0, 0.1, 0.9],
    ),
    (
        "database query optimization",
        "cost-based optimizer and query planning for SQL engines",
        [0.8, 0.2, 0.0, 0.0],
    ),
    (
        "information retrieval systems",
        "ranking algorithms and relevance scoring for search engines",
        [0.2, 0.8, 0.0, 0.0],
    ),
]
for title, body, emb in rows:
    vec = np.array(emb, dtype=np.float32)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO articles (title, body, embedding) "
        f"VALUES ('{title}', '{body}', {arr})"
    )


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    for row in result.rows:
        parts = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                parts.append(f"{c}={v:.4f}")
            else:
                parts.append(f"{c}={v}")
        print("  " + "  ".join(parts))


print("=" * 70)
print("Full-Text Search @@ Operator Examples")
print("=" * 70)


# ==================================================================
# 1. Single term
# ==================================================================
show(
    "1. Single term: title @@ 'database'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE title @@ 'database'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 2. Phrase search
# ==================================================================
show(
    "2. Phrase: body @@ '\"information retrieval\"'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE body @@ '"information retrieval"'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 3. Boolean AND
# ==================================================================
show(
    "3. AND: title @@ 'database AND query'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE title @@ 'database AND query'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 4. Boolean OR
# ==================================================================
show(
    "4. OR: title @@ 'database OR wireless'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE title @@ 'database OR wireless'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 5. Boolean NOT
# ==================================================================
show(
    "5. NOT: title @@ 'NOT database'",
    engine.sql("""
    SELECT title FROM articles
    WHERE title @@ 'NOT database'
"""),
)


# ==================================================================
# 6. Implicit AND (adjacent terms)
# ==================================================================
show(
    "6. Implicit AND: title @@ 'full text'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE title @@ 'full text'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 7. Grouping with parentheses
# ==================================================================
show(
    "7. Grouping: title @@ '(database OR search) AND text'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE title @@ '(database OR search) AND text'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 8. All-field search with _all
# ==================================================================
show(
    "8. All-field: _all @@ 'engines'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE _all @@ 'engines'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 9. Field-specific within query string
# ==================================================================
show(
    "9. Field-specific: _all @@ 'title:database'",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE _all @@ 'title:database'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 10. Hybrid text + vector fusion
# ==================================================================
show(
    "10. Hybrid: body:search AND embedding:[0.1, 0.9, 0.0, 0.0]",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE _all @@ 'body:search AND embedding:[0.1, 0.9, 0.0, 0.0]'
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 11. Combined with relational filter
# ==================================================================
show(
    "11. @@ combined with id > 3",
    engine.sql("""
    SELECT id, title, _score FROM articles
    WHERE title @@ 'database' AND id > 3
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 12. ORDER BY _score DESC LIMIT
# ==================================================================
show(
    "12. Top-1 result",
    engine.sql("""
    SELECT title, _score FROM articles
    WHERE _all @@ 'engines'
    ORDER BY _score DESC
    LIMIT 1
"""),
)


print("\n" + "=" * 70)
print("All @@ full-text search examples completed successfully.")
print("=" * 70)
