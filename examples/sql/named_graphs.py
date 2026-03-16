#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Named graph examples via SQL.

Demonstrates:
  - Creating named graphs and adding data via Python API
  - Traverse via SQL on named graphs
  - RPQ via SQL on named graphs (transitive closure with Kleene star)
  - Centrality algorithms (PageRank, HITS, Betweenness) on named graphs
  - Cypher queries on named graphs
  - Temporal traverse on named graphs
  - Graph isolation via SQL
  - Graph algebra followed by SQL queries
  - Per-table graph vs named graph with same SQL syntax
  - Backward compatibility with 'graph:name' prefix
"""

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# ======================================================================
# Data setup: two named graphs -- social and professional
# ======================================================================

engine = Engine()

# Create a backing table for per-table graph usage later
engine.sql("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
for i, name in enumerate(["Alice", "Bob", "Carol", "Diana", "Eve"], 1):
    engine.sql(f"INSERT INTO people VALUES ({i}, '{name}')")

# Create named graphs
engine.create_graph("social")
engine.create_graph("professional")

gs = engine.graph_store

# -- Social graph: friendship network --
social_vertices = [
    Vertex(1, "person", {"name": "Alice", "age": 30}),
    Vertex(2, "person", {"name": "Bob", "age": 25}),
    Vertex(3, "person", {"name": "Carol", "age": 35}),
    Vertex(4, "person", {"name": "Diana", "age": 28}),
    Vertex(5, "person", {"name": "Eve", "age": 32}),
]
for v in social_vertices:
    gs.add_vertex(v, graph="social")

social_edges = [
    Edge(1, 1, 2, "knows"),
    Edge(2, 2, 3, "knows"),
    Edge(3, 1, 3, "knows"),
    Edge(4, 3, 4, "knows"),
    Edge(5, 4, 5, "knows"),
    Edge(6, 1, 5, "follows"),
]
for e in social_edges:
    gs.add_edge(e, graph="social")

# -- Professional graph: mentorship network --
prof_vertices = [
    Vertex(1, "person", {"name": "Alice", "role": "director"}),
    Vertex(2, "person", {"name": "Bob", "role": "senior"}),
    Vertex(3, "person", {"name": "Carol", "role": "senior"}),
    Vertex(6, "person", {"name": "Frank", "role": "junior"}),
    Vertex(7, "person", {"name": "Grace", "role": "junior"}),
]
for v in prof_vertices:
    gs.add_vertex(v, graph="professional")

prof_edges = [
    Edge(10, 1, 2, "mentors"),
    Edge(11, 1, 3, "mentors"),
    Edge(12, 2, 6, "mentors"),
    Edge(13, 3, 7, "mentors"),
    Edge(14, 2, 3, "collaborates"),
]
for e in prof_edges:
    gs.add_edge(e, graph="professional")


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
                vals.append(f"{v:<15,.4f}")
            else:
                vals.append(str(v)[:15].ljust(15))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Named Graph SQL Examples")
print("=" * 70)


# ==================================================================
# 1. Create Named Graph + Add Data
# ==================================================================
print("\n" + "=" * 70)
print("1. Create Named Graph + Add Data")
print("=" * 70)
print(
    f"  Social graph: {len(gs.vertices_in_graph('social'))} vertices, "
    f"{len(gs.edges_in_graph('social'))} edges"
)
print(
    f"  Professional graph: {len(gs.vertices_in_graph('professional'))} vertices, "
    f"{len(gs.edges_in_graph('professional'))} edges"
)


# ==================================================================
# 2. Traverse via SQL
# ==================================================================
show(
    "2. Traverse social/knows from Alice (2 hops)",
    engine.sql("SELECT name, age FROM traverse(1, 'knows', 2, 'social')"),
)


# ==================================================================
# 3. RPQ via SQL
# ==================================================================
show(
    "3. RPQ knows* from Alice in social (transitive closure)",
    engine.sql("SELECT name FROM rpq('knows*', 1, 'social')"),
)


# ==================================================================
# 4. Centrality via SQL
# ==================================================================
show(
    "4a. PageRank on social graph",
    engine.sql(
        "SELECT name, _score FROM pagerank(0.85, 100, 1e-6, 'social') ORDER BY _score DESC"
    ),
)

show(
    "4b. HITS on social graph",
    engine.sql(
        "SELECT name, _score FROM hits(100, 1e-6, 'social') ORDER BY _score DESC"
    ),
)

show(
    "4c. Betweenness centrality on social graph",
    engine.sql("SELECT name, _score FROM betweenness('social') ORDER BY _score DESC"),
)


# ==================================================================
# 5. Cypher on Named Graph
# ==================================================================
show(
    "5. Cypher: MATCH (a)-[:knows]->(b) on social",
    engine.sql("""
        SELECT * FROM cypher('social', $$
            MATCH (a)-[:knows]->(b) RETURN a.name AS src, b.name AS dst
        $$) AS (src agtype, dst agtype)
    """),
)


# ==================================================================
# 6. Temporal Traverse on Named Graph
# ==================================================================
# Add temporal edges to a new named graph
engine.create_graph("temporal_net")
temporal_vertices = [
    Vertex(100, "dev", {"name": "Alice"}),
    Vertex(101, "dev", {"name": "Bob"}),
    Vertex(102, "dev", {"name": "Carol"}),
]
for v in temporal_vertices:
    gs.add_vertex(v, graph="temporal_net")

temporal_edges = [
    Edge(100, 100, 101, "knows", {"valid_from": 1, "valid_to": 6}),
    Edge(101, 100, 102, "knows", {"valid_from": 3, "valid_to": 12}),
    Edge(102, 101, 102, "knows", {"valid_from": 5, "valid_to": 10}),
]
for e in temporal_edges:
    gs.add_edge(e, graph="temporal_net")

show(
    "6. Temporal traverse at timestamp 4 (2-hop knows) on temporal_net",
    engine.sql(
        "SELECT name FROM temporal_traverse(100, 'knows', 2, 4.0, 'temporal_net')"
    ),
)


# ==================================================================
# 7. Graph Isolation via SQL
# ==================================================================
print("\n" + "=" * 70)
print("7. Graph Isolation via SQL")
print("=" * 70)

r_social = engine.sql("SELECT name FROM traverse(1, 'knows', 2, 'social')")
social_names = sorted(row["name"] for row in r_social.rows)
print(f"  Social/knows from Alice: {', '.join(social_names)}")

r_prof = engine.sql("SELECT name FROM traverse(1, 'mentors', 2, 'professional')")
prof_names = sorted(row["name"] for row in r_prof.rows)
print(f"  Professional/mentors from Alice: {', '.join(prof_names)}")


# ==================================================================
# 8. Graph Algebra then SQL
# ==================================================================
print("\n" + "=" * 70)
print("8. Graph Algebra then SQL")
print("=" * 70)

gs.union_graphs("social", "professional", "combined")
show(
    "8. Traverse combined graph (knows, 2 hops from Alice)",
    engine.sql("SELECT name FROM traverse(1, 'knows', 2, 'combined')"),
)


# ==================================================================
# 9. Per-Table Graph vs Named Graph
# ==================================================================
print("\n" + "=" * 70)
print("9. Per-Table Graph vs Named Graph")
print("=" * 70)

# Add graph data to the per-table graph store
table_gs = engine.get_graph_store("people")
for v in social_vertices:
    table_gs.add_vertex(v, graph="people")
for e in social_edges:
    table_gs.add_edge(e, graph="people")

# Both use the same traverse() SQL syntax -- just pass the name
show(
    "9a. Per-table graph: traverse people",
    engine.sql("SELECT name FROM traverse(1, 'knows', 1, 'people')"),
)

show(
    "9b. Named graph: traverse social",
    engine.sql("SELECT name FROM traverse(1, 'knows', 1, 'social')"),
)


# ==================================================================
# 10. Backward Compatibility: 'graph:' Prefix
# ==================================================================
print("\n" + "=" * 70)
print("10. Backward Compatibility: 'graph:' Prefix")
print("=" * 70)

# The legacy 'graph:social' prefix is still accepted
show(
    "10. Legacy prefix: traverse with 'graph:social'",
    engine.sql("SELECT name FROM traverse(1, 'knows', 1, 'graph:social')"),
)


print("\n" + "=" * 70)
print("All named graph SQL examples completed successfully.")
print("=" * 70)
