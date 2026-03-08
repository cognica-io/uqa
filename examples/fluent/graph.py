#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph query examples using the fluent QueryBuilder API.

Demonstrates:
  - Graph traversal (BFS with label and hop filters)
  - Vertex aggregation (sum, avg, min, max, count)
  - Regular path queries (RPQ) with Kleene star
  - Graph pattern matching (subgraph isomorphism)
  - Graph indexes (LabelIndex, NeighborhoodIndex, PathIndex)
  - Graph statistics and cardinality estimation
"""

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.index import LabelIndex, NeighborhoodIndex, PathIndex
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern
from uqa.planner.cardinality import CardinalityEstimator, GraphStats

# ======================================================================
# Data setup: company org chart
# ======================================================================

engine = Engine()
gs = engine.graph_store

# -- Vertices: employees --
employees = [
    Vertex(1, {"name": "Alice", "role": "ceo", "salary": 250000, "years": 15}),
    Vertex(2, {"name": "Bob", "role": "vp_eng", "salary": 180000, "years": 12}),
    Vertex(3, {"name": "Carol", "role": "vp_sales", "salary": 170000, "years": 10}),
    Vertex(4, {"name": "Dave", "role": "engineer", "salary": 130000, "years": 6}),
    Vertex(5, {"name": "Eve", "role": "engineer", "salary": 125000, "years": 4}),
    Vertex(6, {"name": "Frank", "role": "engineer", "salary": 120000, "years": 3}),
    Vertex(7, {"name": "Grace", "role": "sales", "salary": 110000, "years": 5}),
    Vertex(8, {"name": "Hank", "role": "sales", "salary": 105000, "years": 2}),
]

# -- Vertices: departments, projects, skills --
departments = [
    Vertex(101, {"name": "Engineering", "budget": 2000000}),
    Vertex(102, {"name": "Sales", "budget": 1500000}),
]
projects = [
    Vertex(201, {"name": "Project Alpha", "status": "active"}),
    Vertex(202, {"name": "Project Beta", "status": "active"}),
    Vertex(203, {"name": "Project Gamma", "status": "completed"}),
]
skills = [
    Vertex(301, {"name": "Python"}),
    Vertex(302, {"name": "Rust"}),
    Vertex(303, {"name": "SQL"}),
]

for v in employees + departments + projects + skills:
    gs.add_vertex(v)

# -- Edges --
edges = [
    # Management hierarchy
    Edge(1, 1, 2, "manages"), Edge(2, 1, 3, "manages"),
    Edge(3, 2, 4, "manages"), Edge(4, 2, 5, "manages"),
    Edge(5, 2, 6, "manages"), Edge(6, 3, 7, "manages"),
    Edge(7, 3, 8, "manages"),
    # Department membership
    Edge(10, 2, 101, "belongs_to"), Edge(11, 4, 101, "belongs_to"),
    Edge(12, 5, 101, "belongs_to"), Edge(13, 6, 101, "belongs_to"),
    Edge(14, 3, 102, "belongs_to"), Edge(15, 7, 102, "belongs_to"),
    Edge(16, 8, 102, "belongs_to"),
    # Project assignments
    Edge(20, 4, 201, "works_on"), Edge(21, 5, 201, "works_on"),
    Edge(22, 5, 202, "works_on"), Edge(23, 6, 202, "works_on"),
    Edge(24, 6, 203, "works_on"),
    # Skills
    Edge(30, 4, 301, "has_skill"), Edge(31, 4, 303, "has_skill"),
    Edge(32, 5, 301, "has_skill"), Edge(33, 5, 302, "has_skill"),
    Edge(34, 6, 302, "has_skill"), Edge(35, 6, 303, "has_skill"),
]
for e in edges:
    gs.add_edge(e)

print("=" * 70)
print("Graph Query Examples (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. Direct reports: 1-hop traversal from CEO
# ------------------------------------------------------------------
print("\n--- 1. Direct reports of CEO (1-hop 'manages') ---")
results = engine.query().traverse(1, "manages", max_hops=1).execute()
for entry in results:
    v = gs.get_vertex(entry.doc_id)
    if v and entry.doc_id != 1:
        print(f"  {v.properties['name']} ({v.properties['role']})")


# ------------------------------------------------------------------
# 2. Full org tree: multi-hop traversal
# ------------------------------------------------------------------
print("\n--- 2. Full org tree (3-hop 'manages' from CEO) ---")
results = engine.query().traverse(1, "manages", max_hops=3).execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        props = v.properties
        salary = f"${props['salary']:,}" if 'salary' in props else "N/A"
        print(f"  [{entry.doc_id:>3}] {props['name']:<10} {props.get('role', 'N/A'):<12} {salary}")


# ------------------------------------------------------------------
# 3. Vertex aggregation: salary statistics
# ------------------------------------------------------------------
print("\n--- 3. Salary stats for Bob's team (VP Eng -> reports) ---")
team = engine.query().traverse(2, "manages", max_hops=2)
for fn in ("sum", "avg", "min", "max", "count"):
    result = team.vertex_aggregate("salary", fn)
    if fn == "count":
        print(f"  {fn:>5}: {result.value}")
    else:
        print(f"  {fn:>5}: ${result.value:,.0f}")


# ------------------------------------------------------------------
# 4. RPQ: transitive management chain (Kleene star)
# ------------------------------------------------------------------
print("\n--- 4. RPQ: manages* from Alice (transitive closure) ---")
results = engine.query().rpq("manages*", start=1).execute()
print(f"  {len(results)} vertices reachable")
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v and "name" in v.properties:
        print(f"  [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 5. RPQ: management then skill chain
# ------------------------------------------------------------------
print("\n--- 5. RPQ: manages/has_skill from Bob ---")
results = engine.query().rpq("manages/has_skill", start=2).execute()
for entry in sorted(results, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"  [{entry.doc_id}] {v.properties['name']}")


# ------------------------------------------------------------------
# 6. Pattern matching: manager -> engineer -> project
# ------------------------------------------------------------------
print("\n--- 6. Pattern: manager -manages-> engineer -works_on-> project ---")
pattern = GraphPattern(
    vertex_patterns=[
        VertexPattern("mgr"), VertexPattern("eng"), VertexPattern("proj"),
    ],
    edge_patterns=[
        EdgePattern("mgr", "eng", "manages"),
        EdgePattern("eng", "proj", "works_on"),
    ],
)
results = engine.query().match_pattern(pattern).execute()
print(f"  {len(results)} pattern matches found")
for entry in results:
    bindings = entry.payload.fields.get("_bindings", {})
    mgr = gs.get_vertex(bindings.get("mgr", 0))
    eng = gs.get_vertex(bindings.get("eng", 0))
    proj = gs.get_vertex(bindings.get("proj", 0))
    if mgr and eng and proj:
        print(f"  {mgr.properties['name']} -> {eng.properties['name']} "
              f"-> {proj.properties['name']}")


# ------------------------------------------------------------------
# 7. Pattern matching: engineer with specific skill on active project
# ------------------------------------------------------------------
print("\n--- 7. Pattern: engineer -has_skill-> Python, engineer -works_on-> project ---")
pattern = GraphPattern(
    vertex_patterns=[
        VertexPattern("eng"), VertexPattern("skill"), VertexPattern("proj"),
    ],
    edge_patterns=[
        EdgePattern("eng", "skill", "has_skill"),
        EdgePattern("eng", "proj", "works_on"),
    ],
)
results = engine.query().match_pattern(pattern).execute()
for entry in results:
    bindings = entry.payload.fields.get("_bindings", {})
    eng = gs.get_vertex(bindings.get("eng", 0))
    skill = gs.get_vertex(bindings.get("skill", 0))
    proj = gs.get_vertex(bindings.get("proj", 0))
    if eng and skill and proj:
        print(f"  {eng.properties['name']} [{skill.properties['name']}] "
              f"-> {proj.properties['name']} ({proj.properties.get('status', '?')})")


# ------------------------------------------------------------------
# 8. LabelIndex: edge statistics
# ------------------------------------------------------------------
print("\n--- 8. LabelIndex: edge counts by label ---")
label_idx = LabelIndex.build(gs)
for label in ("manages", "belongs_to", "works_on", "has_skill"):
    edge_ids = label_idx.edges_by_label(label)
    print(f"  {label:>12}: {len(edge_ids)} edges")


# ------------------------------------------------------------------
# 9. NeighborhoodIndex: pre-computed 2-hop neighborhoods
# ------------------------------------------------------------------
print("\n--- 9. NeighborhoodIndex: Bob's 2-hop neighborhood ---")
nbr_idx = NeighborhoodIndex.build(gs, max_hops=2)
neighbors = nbr_idx.neighbors(2, hops=2)
print(f"  {len(neighbors)} vertices within 2 hops:")
for vid in sorted(neighbors):
    v = gs.get_vertex(vid)
    if v:
        print(f"    [{vid}] {v.properties.get('name', '?')}")


# ------------------------------------------------------------------
# 10. PathIndex: pre-computed labeled paths
# ------------------------------------------------------------------
print("\n--- 10. PathIndex: 'manages' paths from Alice ---")
path_idx = PathIndex.build(gs, label_sequences=[["manages"], ["manages", "manages"]])
pairs_1 = path_idx.lookup(["manages"])
pairs_2 = path_idx.lookup(["manages", "manages"])
# Filter to paths starting from Alice (vertex 1)
from_alice_1 = sorted(end for start, end in pairs_1 if start == 1)
from_alice_2 = sorted(end for start, end in pairs_2 if start == 1)
print(f"  1-hop manages from Alice: {len(from_alice_1)} targets")
for vid in from_alice_1:
    v = gs.get_vertex(vid)
    if v:
        print(f"    Alice -> {v.properties['name']}")
print(f"  2-hop manages from Alice: {len(from_alice_2)} targets")
for vid in from_alice_2:
    v = gs.get_vertex(vid)
    if v:
        print(f"    Alice -> ... -> {v.properties['name']}")


# ------------------------------------------------------------------
# 11. GraphStats and CardinalityEstimator
# ------------------------------------------------------------------
print("\n--- 11. Graph statistics ---")
stats = GraphStats.from_graph_store(gs)
print(f"  Vertices: {stats.num_vertices}")
print(f"  Edges: {stats.num_edges}")
print(f"  Avg out-degree: {stats.avg_out_degree:.2f}")
print(f"  Edge density: {stats.edge_density():.6f}")
for label, count in sorted(stats.label_counts.items()):
    sel = stats.label_selectivity(label)
    print(f"    {label:>12}: {count} edges (selectivity: {sel:.3f})")


# ------------------------------------------------------------------
# 12. Engineering team: traverse from VP Eng + aggregate
# ------------------------------------------------------------------
print("\n--- 12. Engineering team analysis (Bob's reports) ---")
eng_team = engine.query().traverse(2, "manages", max_hops=2)
results = eng_team.execute()
members = []
for entry in results:
    v = gs.get_vertex(entry.doc_id)
    if v and "salary" in v.properties and entry.doc_id != 2:
        members.append(v)
print(f"  Direct reports: {len(members)}")
for m in sorted(members, key=lambda v: v.properties["salary"], reverse=True):
    p = m.properties
    print(f"    {p['name']:<10} {p['role']:<12} ${p['salary']:>9,}  ({p['years']} yr)")


print("\n" + "=" * 70)
print("All graph query examples completed successfully.")
print("=" * 70)
