#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Incremental graph maintenance via GraphDelta.

Demonstrates:
  - GraphDelta: building batched mutations
  - engine.apply_graph_delta() -- atomic delta application
  - Path index build + automatic invalidation after delta
  - VersionedGraphStore rollback
"""

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.delta import GraphDelta

# ======================================================================
# Data setup: named graph for social network
# ======================================================================

engine = Engine()

graph = engine.create_graph("social")

# -- Build initial graph with GraphDelta --

print("=" * 70)
print("Incremental Graph Maintenance (GraphDelta)")
print("=" * 70)


# ==================================================================
# 1. Build initial graph with GraphDelta
# ==================================================================
print("\n--- 1. Build initial graph with GraphDelta ---")

delta = GraphDelta()
delta.add_vertex(Vertex(1, "person", {"name": "Alice", "role": "engineer"}))
delta.add_vertex(Vertex(2, "person", {"name": "Bob", "role": "manager"}))
delta.add_vertex(Vertex(3, "person", {"name": "Carol", "role": "engineer"}))
delta.add_vertex(Vertex(4, "person", {"name": "Diana", "role": "designer"}))

delta.add_edge(Edge(1, 1, 2, "reports_to"))
delta.add_edge(Edge(2, 3, 2, "reports_to"))
delta.add_edge(Edge(3, 1, 3, "collaborates"))

print(f"  Delta has {len(delta)} operations")
print(f"  Affected vertex IDs: {sorted(delta.affected_vertex_ids())}")
print(f"  Affected edge labels: {sorted(delta.affected_edge_labels())}")

version = engine.apply_graph_delta("social", delta)
print(f"  Applied delta -> version {version}")
print(f"  Graph now has {len(graph._vertices)} vertices, {len(graph._edges)} edges")


# ==================================================================
# 2. engine.apply_graph_delta: add more vertices and edges
# ==================================================================
print("\n--- 2. Apply second delta: add new members ---")

delta2 = GraphDelta()
delta2.add_vertex(Vertex(5, "person", {"name": "Eve", "role": "intern"}))
delta2.add_vertex(Vertex(6, "person", {"name": "Frank", "role": "engineer"}))
delta2.add_edge(Edge(4, 5, 1, "reports_to"))
delta2.add_edge(Edge(5, 6, 2, "reports_to"))
delta2.add_edge(Edge(6, 1, 6, "mentors"))

version = engine.apply_graph_delta("social", delta2)
print(f"  Applied delta -> version {version}")
print(f"  Graph now has {len(graph._vertices)} vertices, {len(graph._edges)} edges")

# Verify the new vertices exist
for vid in (5, 6):
    v = graph.get_vertex(vid)
    if v:
        print(f"  Vertex {vid}: {v.properties['name']} ({v.properties['role']})")


# ==================================================================
# 3. Path index build + automatic invalidation after delta
# ==================================================================
print("\n--- 3. Path index build + invalidation ---")

engine.build_path_index("social", [["reports_to"], ["reports_to", "reports_to"]])
path_idx = engine.get_path_index("social")
print(f"  Path index built: {path_idx is not None}")

# Query the path index: who reports_to Bob (vertex 2)?
if path_idx is not None:
    pairs = path_idx.lookup(["reports_to"])
    reporters_to_bob = sorted(end for start, end in pairs if end == 2)
    print(f"  Vertices with 'reports_to' edge to Bob: {reporters_to_bob}")

    two_hop = path_idx.lookup(["reports_to", "reports_to"])
    print(f"  2-hop 'reports_to' pairs: {len(two_hop)}")

# Apply a delta that affects the indexed label
print("  Applying delta with 'reports_to' edge...")
delta3 = GraphDelta()
delta3.add_edge(Edge(7, 4, 2, "reports_to"))
engine.apply_graph_delta("social", delta3)

# Path index should be invalidated
path_idx_after = engine.get_path_index("social")
print(f"  Path index after delta: {path_idx_after}")
print("  (Path index was automatically invalidated because 'reports_to' was affected)")


# ==================================================================
# 4. Rebuild path index after invalidation
# ==================================================================
print("\n--- 4. Rebuild path index ---")

engine.build_path_index("social", [["reports_to"]])
rebuilt_idx = engine.get_path_index("social")
if rebuilt_idx is not None:
    pairs = rebuilt_idx.lookup(["reports_to"])
    print(f"  'reports_to' pairs after rebuild: {len(pairs)}")
    for start, end in sorted(pairs):
        s = graph.get_vertex(start)
        e = graph.get_vertex(end)
        if s and e:
            print(f"    {s.properties['name']} -> {e.properties['name']}")


# ==================================================================
# 5. VersionedGraphStore rollback
# ==================================================================
print("\n--- 5. VersionedGraphStore rollback ---")

# Create a fresh graph for rollback demonstration
rollback_graph = engine.create_graph("rollback_demo")

# Apply initial delta
delta_a = GraphDelta()
delta_a.add_vertex(Vertex(1, "node", {"name": "A"}))
delta_a.add_vertex(Vertex(2, "node", {"name": "B"}))
delta_a.add_edge(Edge(1, 1, 2, "link"))
engine.apply_graph_delta("rollback_demo", delta_a)

versioned = engine._versioned_graphs["rollback_demo"]
print(f"  Version after first delta: {versioned.version}")
print(f"  Vertices: {len(rollback_graph._vertices)}")

# Apply second delta
delta_b = GraphDelta()
delta_b.add_vertex(Vertex(3, "node", {"name": "C"}))
delta_b.add_edge(Edge(2, 2, 3, "link"))
engine.apply_graph_delta("rollback_demo", delta_b)
print(f"  Version after second delta: {versioned.version}")
print(f"  Vertices: {len(rollback_graph._vertices)}")

# Rollback to version 1
versioned.rollback(to_version=1)
print("  After rollback to version 1:")
print(f"    Version: {versioned.version}")
print(f"    Vertices: {len(rollback_graph._vertices)}")
print(f"    Vertex 3 exists: {rollback_graph.get_vertex(3) is not None}")


# ==================================================================
# 6. Delta with edge removal
# ==================================================================
print("\n--- 6. Delta with edge removal ---")

removal_delta = GraphDelta()
removal_delta.remove_edge(1)  # Remove the link edge
engine.apply_graph_delta("rollback_demo", removal_delta)
print("  Removed edge 1 from rollback_demo")
print(f"  Edges remaining: {len(rollback_graph._edges)}")


print("\n" + "=" * 70)
print("All graph delta examples completed successfully.")
print("=" * 70)
