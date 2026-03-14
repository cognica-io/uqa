#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Temporal graph traversal and GNN features via SQL.

Demonstrates:
  - temporal_traverse(start, label, hops, timestamp) -- point-in-time traversal
  - temporal_traverse(start, label, hops, from_ts, to_ts) -- range traversal
  - message_passing(k_layers, agg, property) -- GNN aggregation
  - graph_embedding(dims, k_layers) -- structural embeddings
"""

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# ======================================================================
# Data setup: social network with temporal edges
# ======================================================================

engine = Engine()

engine.sql("""CREATE TABLE social (id SERIAL PRIMARY KEY, name TEXT)""")

# Insert placeholder rows so that doc_ids 1-6 exist in the table
names = ["Alice", "Bob", "Carol", "Diana", "Eve", "Frank"]
for name in names:
    engine.sql(f"INSERT INTO social (name) VALUES ('{name}')")

gs = engine.get_graph_store("social")

# -- Vertices with properties --
vertices = [
    Vertex(1, "person", {"name": "Alice", "influence": 0.9}),
    Vertex(2, "person", {"name": "Bob", "influence": 0.7}),
    Vertex(3, "person", {"name": "Carol", "influence": 0.5}),
    Vertex(4, "person", {"name": "Diana", "influence": 0.6}),
    Vertex(5, "person", {"name": "Eve", "influence": 0.3}),
    Vertex(6, "person", {"name": "Frank", "influence": 0.4}),
]
for v in vertices:
    gs.add_vertex(v)

# -- Temporal edges with valid_from/valid_to timestamps --
# Timestamps represent months (e.g., 1 = Jan, 6 = Jun, 12 = Dec)
edges = [
    Edge(1, 1, 2, "follows", {"valid_from": 1, "valid_to": 12}),
    Edge(2, 1, 3, "follows", {"valid_from": 3, "valid_to": 9}),
    Edge(3, 2, 3, "follows", {"valid_from": 1, "valid_to": 6}),
    Edge(4, 2, 4, "follows", {"valid_from": 6, "valid_to": 12}),
    Edge(5, 3, 4, "follows", {"valid_from": 1, "valid_to": 12}),
    Edge(6, 3, 5, "follows", {"valid_from": 4, "valid_to": 8}),
    Edge(7, 4, 5, "follows", {"valid_from": 7, "valid_to": 12}),
    Edge(8, 4, 6, "follows", {"valid_from": 1, "valid_to": 5}),
    Edge(9, 5, 6, "follows", {}),  # No temporal constraint -- always valid
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
                vals.append(f"{v:<15.4f}")
            else:
                vals.append(str(v)[:15].ljust(15))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Temporal Graph and GNN Examples (SQL)")
print("=" * 70)


# ==================================================================
# 1. temporal_traverse: point-in-time at month 2
# ==================================================================
show(
    "1. Temporal traverse from Alice at month 2 (1-hop 'follows')",
    engine.sql(
        "SELECT name FROM temporal_traverse(1, 'follows', 1, 2)"
    ),
)


# ==================================================================
# 2. temporal_traverse: point-in-time at month 7
# ==================================================================
show(
    "2. Temporal traverse from Alice at month 7 (2-hop 'follows')",
    engine.sql(
        "SELECT name FROM temporal_traverse(1, 'follows', 2, 7)"
    ),
)


# ==================================================================
# 3. temporal_traverse: point-in-time at month 1 vs month 10
# ==================================================================
print("\n--- 3. Comparison: month 1 vs month 10 (2-hop from Alice) ---")
for month in (1, 10):
    result = engine.sql(
        f"SELECT name FROM temporal_traverse(1, 'follows', 2, {month})"
    )
    reachable = [row["name"] for row in result.rows]
    print(f"  Month {month:>2}: {', '.join(reachable)}")


# ==================================================================
# 4. temporal_traverse: range traversal (months 3-6)
# ==================================================================
show(
    "4. Range traversal from Alice, months 3-6 (2-hop 'follows')",
    engine.sql(
        "SELECT name FROM temporal_traverse(1, 'follows', 2, 3, 6)"
    ),
)


# ==================================================================
# 5. temporal_traverse: range traversal (months 7-12)
# ==================================================================
show(
    "5. Range traversal from Bob, months 7-12 (2-hop 'follows')",
    engine.sql(
        "SELECT name FROM temporal_traverse(2, 'follows', 2, 7, 12)"
    ),
)


# ==================================================================
# 6. message_passing: GNN aggregation with 'influence' property
# ==================================================================
show(
    "6. message_passing(2, 'mean', 'influence') -- 2-layer mean aggregation",
    engine.sql("""
    SELECT name, _score FROM social
    WHERE message_passing(2, 'mean', 'influence')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 7. message_passing: sum aggregation
# ==================================================================
show(
    "7. message_passing(1, 'sum', 'influence') -- 1-layer sum aggregation",
    engine.sql("""
    SELECT name, _score FROM social
    WHERE message_passing(1, 'sum', 'influence')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 8. message_passing: max aggregation
# ==================================================================
show(
    "8. message_passing(1, 'max', 'influence') -- 1-layer max aggregation",
    engine.sql("""
    SELECT name, _score FROM social
    WHERE message_passing(1, 'max', 'influence')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 9. graph_embedding: structural embeddings (8 dimensions)
# ==================================================================
print("\n--- 9. graph_embedding(8, 2) -- 8-dim structural embeddings ---")
result = engine.sql("""
    SELECT _doc_id FROM social
    WHERE graph_embedding(8, 2)
""")
print(f"  Computed embeddings for {len(result.rows)} vertices")
for row in result.rows:
    vid = row["_doc_id"]
    v = gs.get_vertex(vid)
    if v:
        print(f"  [{vid}] {v.properties['name']}")


# ==================================================================
# 10. Comparison: different message_passing aggregation strategies
# ==================================================================
print("\n--- 10. Comparison: mean vs sum vs max (2-layer) ---")
for agg in ("mean", "sum", "max"):
    result = engine.sql(f"""
        SELECT name, _score FROM social
        WHERE message_passing(2, '{agg}', 'influence')
        ORDER BY _score DESC LIMIT 3
    """)
    print(f"\n  {agg} aggregation (top 3):")
    for row in result.rows:
        print(f"    score={row['_score']:.4f}  {row['name']}")


print("\n" + "=" * 70)
print("All temporal graph and GNN examples completed successfully.")
print("=" * 70)
