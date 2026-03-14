#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Advanced graph features via the fluent QueryBuilder API.

Demonstrates:
  - .temporal_traverse() -- temporal-aware graph traversal
  - .message_passing() -- GNN-style neighbor aggregation
  - Path index build + RPQ acceleration
  - Graph delta operations via Engine
"""

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.delta import GraphDelta

# ======================================================================
# Data setup: social network with temporal edges
# ======================================================================

engine = Engine()

engine.sql("CREATE TABLE network (id INTEGER PRIMARY KEY, name TEXT)")

gs = engine.get_graph_store("network")

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
# Timestamps represent months (1-12)
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
    # Non-"follows" edges for variety
    Edge(10, 1, 4, "mentors", {"valid_from": 1, "valid_to": 12}),
    Edge(11, 2, 5, "mentors", {"valid_from": 3, "valid_to": 10}),
]
for e in edges:
    gs.add_edge(e)

print("=" * 70)
print("Advanced Graph Features (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. temporal_traverse: point-in-time at month 2
# ------------------------------------------------------------------
print("\n--- 1. Temporal traverse: Alice at month 2 (1-hop 'follows') ---")
results = (
    engine.query(table="network")
    .temporal_traverse(1, "follows", max_hops=1, timestamp=2.0)
    .execute()
)
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"  [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 2. temporal_traverse: point-in-time at month 7 (deeper traversal)
# ------------------------------------------------------------------
print("\n--- 2. Temporal traverse: Alice at month 7 (2-hop 'follows') ---")
results = (
    engine.query(table="network")
    .temporal_traverse(1, "follows", max_hops=2, timestamp=7.0)
    .execute()
)
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"  [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 3. temporal_traverse: range query (months 3-6)
# ------------------------------------------------------------------
print("\n--- 3. Temporal range: Alice, months 3-6 (2-hop 'follows') ---")
results = (
    engine.query(table="network")
    .temporal_traverse(1, "follows", max_hops=2, time_range=(3.0, 6.0))
    .execute()
)
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"  [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 4. temporal_traverse: comparison across time points
# ------------------------------------------------------------------
print("\n--- 4. Temporal comparison: Alice's reach at different months ---")
for month in (1, 4, 7, 10):
    results = (
        engine.query(table="network")
        .temporal_traverse(1, "follows", max_hops=2, timestamp=float(month))
        .execute()
    )
    reachable = []
    for entry in sorted(results, key=lambda e: e.doc_id):
        v = gs.get_vertex(entry.doc_id)
        if v and entry.doc_id != 1:
            reachable.append(v.properties["name"])
    print(f"  Month {month:>2}: {', '.join(reachable) if reachable else '(none)'}")


# ------------------------------------------------------------------
# 5. message_passing: GNN aggregation with 'influence' property
# ------------------------------------------------------------------
print("\n--- 5. message_passing: 2-layer mean aggregation on 'influence' ---")
results = (
    engine.query(table="network")
    .message_passing(k_layers=2, aggregation="mean", property_name="influence")
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(
            f"  [{entry.doc_id}] score={entry.payload.score:.4f}  "
            f"{v.properties['name']} (influence={v.properties['influence']})"
        )


# ------------------------------------------------------------------
# 6. message_passing: comparison of aggregation strategies
# ------------------------------------------------------------------
print("\n--- 6. message_passing: mean vs sum vs max ---")
for agg in ("mean", "sum", "max"):
    results = (
        engine.query(table="network")
        .message_passing(k_layers=1, aggregation=agg, property_name="influence")
        .execute()
    )
    top = sorted(results, key=lambda e: e.payload.score, reverse=True)[:3]
    print(f"\n  {agg} aggregation (top 3):")
    for entry in top:
        v = gs.get_vertex(entry.doc_id)
        if v:
            print(f"    score={entry.payload.score:.4f}  {v.properties['name']}")


# ------------------------------------------------------------------
# 7. Path index build + RPQ acceleration
# ------------------------------------------------------------------
print("\n--- 7. Path index + RPQ ---")

# Create a named graph for path index demonstration
named_graph = engine.create_graph("team")
for v in vertices:
    named_graph.add_vertex(v)
for e in edges:
    named_graph.add_edge(e)

engine.build_path_index("team", [["follows"], ["follows", "follows"]])
path_idx = engine.get_path_index("team")
print(f"  Path index built: {path_idx is not None}")

if path_idx is not None:
    # Query 1-hop follows
    pairs_1 = path_idx.lookup(["follows"])
    from_alice = sorted(end for start, end in pairs_1 if start == 1)
    print(f"  1-hop 'follows' from Alice: {from_alice}")
    for vid in from_alice:
        v = named_graph.get_vertex(vid)
        if v:
            print(f"    -> {v.properties['name']}")

    # Query 2-hop follows
    pairs_2 = path_idx.lookup(["follows", "follows"])
    from_alice_2 = sorted(end for start, end in pairs_2 if start == 1)
    print(f"  2-hop 'follows' from Alice: {from_alice_2}")
    for vid in from_alice_2:
        v = named_graph.get_vertex(vid)
        if v:
            print(f"    -> ... -> {v.properties['name']}")

# RPQ via fluent API (uses standard graph store, not path index)
print("\n  RPQ: follows* from Alice:")
results = engine.query(table="network").rpq("follows*", start=1).execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 8. Graph delta operations
# ------------------------------------------------------------------
print("\n--- 8. Graph delta operations ---")

# Build a delta
delta = GraphDelta()
delta.add_vertex(Vertex(7, "person", {"name": "Grace", "influence": 0.8}))
delta.add_edge(Edge(12, 1, 7, "follows", {"valid_from": 1, "valid_to": 12}))
delta.add_edge(Edge(13, 7, 3, "follows", {"valid_from": 6, "valid_to": 12}))

print(f"  Delta: {len(delta)} operations")
print(f"  Affected labels: {sorted(delta.affected_edge_labels())}")

version = engine.apply_graph_delta("team", delta)
print(f"  Applied to 'team' graph -> version {version}")
print(f"  Graph now has {len(named_graph._vertices)} vertices")

# Check path index invalidation
path_idx_after = engine.get_path_index("team")
print(f"  Path index after delta: {path_idx_after}")
print("  (Invalidated because 'follows' label was affected)")

# Rebuild path index
engine.build_path_index("team", [["follows"]])
rebuilt_idx = engine.get_path_index("team")
if rebuilt_idx:
    pairs = rebuilt_idx.lookup(["follows"])
    from_grace = sorted(end for start, end in pairs if start == 7)
    print(f"  After rebuild: Grace follows -> {from_grace}")


# ------------------------------------------------------------------
# 9. Versioned graph rollback
# ------------------------------------------------------------------
print("\n--- 9. Versioned graph rollback ---")

versioned = engine._versioned_graphs.get("team")
if versioned:
    print(f"  Current version: {versioned.version}")
    print(f"  Vertex 7 (Grace) exists: {named_graph.get_vertex(7) is not None}")

    versioned.rollback(to_version=0)
    print("  After rollback to version 0:")
    print(f"    Version: {versioned.version}")
    print(f"    Vertex 7 (Grace) exists: {named_graph.get_vertex(7) is not None}")


print("\n" + "=" * 70)
print("All advanced graph examples completed successfully.")
print("=" * 70)
