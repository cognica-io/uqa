#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Named graph examples using the fluent QueryBuilder API.

Demonstrates:
  - Graph lifecycle (create, has, names, drop)
  - Adding vertices/edges to named graphs
  - Graph isolation between named graphs
  - Cross-graph vertex sharing
  - Graph algebra (union, intersect, difference, copy)
  - Scoped traversal, pattern match, and RPQ
  - Property indexes on named graphs
  - Graph statistics per named graph
  - Semi-join / Anti-join with graph-sourced data
  - Category-theoretic functors (Graph <-> Relational roundtrip)
  - Adaptive log-odds fusion combining text + graph signals
"""

from __future__ import annotations

from uqa.core.functor import GraphToRelationalFunctor, RelationalToGraphFunctor
from uqa.core.types import Edge, Payload, PostingEntry, Vertex
from uqa.engine import Engine
from uqa.graph.index import EdgePropertyIndex, VertexPropertyIndex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    TraverseOperator,
)
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern, parse_rpq
from uqa.joins.semi import AntiJoinOperator, SemiJoinOperator
from uqa.operators.base import ExecutionContext, Operator
from uqa.operators.hybrid import AdaptiveLogOddsFusionOperator
from uqa.planner.cardinality import GraphStats

# ======================================================================
# Data setup
# ======================================================================

engine = Engine()

engine.sql("CREATE TABLE network (id INTEGER PRIMARY KEY, name TEXT)")

gs = engine.get_graph_store("network")

print("=" * 60)
print("Named Graph Examples (Fluent API)")
print("=" * 60)


# ==============================================================
# 1. Graph Lifecycle
# ==============================================================
print("\n" + "=" * 60)
print("1. Graph Lifecycle")
print("=" * 60)

engine.create_graph("social")
engine.create_graph("work")

print(f"  has_graph('social'): {engine.has_graph('social')}")
print(f"  has_graph('work'):   {engine.has_graph('work')}")
print(f"  has_graph('other'):  {engine.has_graph('other')}")

# graph_names from the underlying store
all_names = gs.graph_names()
print(f"  graph_names: {all_names}")

engine.drop_graph("work")
print(f"  After drop_graph('work'): {gs.graph_names()}")

# Recreate for later use
engine.create_graph("work")


# ==============================================================
# 2. Add Vertices/Edges to Named Graph
# ==============================================================
print("\n" + "=" * 60)
print("2. Add Vertices/Edges to Named Graph")
print("=" * 60)

social_vertices = [
    Vertex(1, "person", {"name": "Alice", "age": 30}),
    Vertex(2, "person", {"name": "Bob", "age": 25}),
    Vertex(3, "person", {"name": "Carol", "age": 35}),
    Vertex(4, "person", {"name": "Diana", "age": 28}),
]
for v in social_vertices:
    gs.add_vertex(v, graph="social")

social_edges = [
    Edge(1, 1, 2, "knows"),
    Edge(2, 2, 3, "knows"),
    Edge(3, 1, 3, "knows"),
    Edge(4, 3, 4, "knows"),
]
for e in social_edges:
    gs.add_edge(e, graph="social")

print(f"  Social vertices: {len(gs.vertices_in_graph('social'))}")
print(f"  Social edges:    {len(gs.edges_in_graph('social'))}")


# ==============================================================
# 3. Graph Isolation
# ==============================================================
print("\n" + "=" * 60)
print("3. Graph Isolation")
print("=" * 60)

work_vertices = [
    Vertex(10, "employee", {"name": "Xavier", "dept": "Engineering"}),
    Vertex(11, "employee", {"name": "Yuki", "dept": "Sales"}),
    Vertex(12, "employee", {"name": "Zara", "dept": "Engineering"}),
]
for v in work_vertices:
    gs.add_vertex(v, graph="work")

work_edges = [
    Edge(10, 10, 11, "reports_to"),
    Edge(11, 10, 12, "collaborates"),
]
for e in work_edges:
    gs.add_edge(e, graph="work")

print("  Social graph vertices:")
for v in gs.vertices_in_graph("social"):
    print(f"    [{v.vertex_id}] {v.properties['name']}")
print("  Work graph vertices:")
for v in gs.vertices_in_graph("work"):
    print(f"    [{v.vertex_id}] {v.properties['name']}")

# Verify isolation -- social neighbors should not include work vertices
social_neighbors = gs.neighbors(1, label="knows", graph="social")
print(f"  Alice's social neighbors: {sorted(social_neighbors)}")


# ==============================================================
# 4. Cross-Graph Vertex Sharing
# ==============================================================
print("\n" + "=" * 60)
print("4. Cross-Graph Vertex Sharing")
print("=" * 60)

# Add Alice (vertex 1) to the work graph as well
gs.add_vertex(Vertex(1, "person", {"name": "Alice", "age": 30}), graph="work")
gs.add_edge(Edge(20, 1, 10, "manages"), graph="work")

membership = gs.vertex_graphs(1)
print(f"  Alice (vertex 1) belongs to graphs: {sorted(membership)}")
print(f"  Social vertex count: {len(gs.vertices_in_graph('social'))}")
print(f"  Work vertex count:   {len(gs.vertices_in_graph('work'))}")


# ==============================================================
# 5. Graph Algebra
# ==============================================================
print("\n" + "=" * 60)
print("5. Graph Algebra")
print("=" * 60)

# Union
gs.union_graphs("social", "work", "merged")
merged_v = gs.vertices_in_graph("merged")
print(f"  union(social, work) -> 'merged': {len(merged_v)} vertices")
for v in merged_v:
    print(f"    [{v.vertex_id}] {v.properties['name']}")

# Intersect -- only shared vertices (Alice is in both)
gs.intersect_graphs("social", "work", "shared")
shared_v = gs.vertices_in_graph("shared")
print(f"  intersect(social, work) -> 'shared': {len(shared_v)} vertices")
for v in shared_v:
    print(f"    [{v.vertex_id}] {v.properties['name']}")

# Difference -- social minus work
gs.difference_graphs("social", "work", "social_only")
social_only_v = gs.vertices_in_graph("social_only")
print(f"  difference(social, work) -> 'social_only': {len(social_only_v)} vertices")
for v in social_only_v:
    print(f"    [{v.vertex_id}] {v.properties['name']}")

# Copy
gs.copy_graph("social", "backup")
backup_v = gs.vertices_in_graph("backup")
print(f"  copy(social) -> 'backup': {len(backup_v)} vertices")


# ==============================================================
# 6. Scoped Traversal
# ==============================================================
print("\n" + "=" * 60)
print("6. Scoped Traversal")
print("=" * 60)

ctx = ExecutionContext(graph_store=gs)

# Traverse social graph from Alice, 2 hops via 'knows'
traverse_op = TraverseOperator(1, graph="social", label="knows", max_hops=2)
result = traverse_op.execute(ctx)
print("  Traverse social/knows from Alice (2 hops):")
for entry in sorted(result, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(
            f"    [{entry.doc_id}] {v.properties['name']} (score={entry.payload.score:.2f})"
        )

# Traverse work graph from Alice, 1 hop via 'manages'
traverse_work = TraverseOperator(1, graph="work", label="manages", max_hops=1)
result_work = traverse_work.execute(ctx)
print("  Traverse work/manages from Alice (1 hop):")
for entry in sorted(result_work, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['name']}")


# ==============================================================
# 7. Scoped Pattern Match
# ==============================================================
print("\n" + "=" * 60)
print("7. Scoped Pattern Match")
print("=" * 60)

pattern = GraphPattern(
    vertex_patterns=[
        VertexPattern("a"),
        VertexPattern("b"),
        VertexPattern("c"),
    ],
    edge_patterns=[
        EdgePattern("a", "b", "knows"),
        EdgePattern("b", "c", "knows"),
    ],
)
pm_op = PatternMatchOperator(pattern, graph="social")
pm_result = pm_op.execute(ctx)
print(f"  Pattern a-knows->b-knows->c in social: {len(pm_result)} matches")
for entry in pm_result:
    fields = entry.payload.fields
    a = gs.get_vertex(fields.get("a", 0))
    b = gs.get_vertex(fields.get("b", 0))
    c = gs.get_vertex(fields.get("c", 0))
    if a and b and c:
        print(
            f"    {a.properties['name']} -> "
            f"{b.properties['name']} -> "
            f"{c.properties['name']}"
        )


# ==============================================================
# 8. Scoped RPQ
# ==============================================================
print("\n" + "=" * 60)
print("8. Scoped RPQ")
print("=" * 60)

path_expr = parse_rpq("knows*")
rpq_op = RegularPathQueryOperator(path_expr, graph="social", start_vertex=1)
rpq_result = rpq_op.execute(ctx)
print("  RPQ knows* from Alice in social graph:")
for entry in sorted(rpq_result, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['name']}")


# ==============================================================
# 9. Property Indexes
# ==============================================================
print("\n" + "=" * 60)
print("9. Property Indexes")
print("=" * 60)

# Vertex property index on 'age' and 'name' in social graph
vp_idx = VertexPropertyIndex.build(gs, graph="social", properties=["age", "name"])
print(f"  VertexPropertyIndex has 'age': {vp_idx.has_property('age')}")
print(f"  VertexPropertyIndex has 'name': {vp_idx.has_property('name')}")

# Equality lookup
alice_ids = vp_idx.lookup_eq("name", "Alice")
print(f"  lookup_eq('name', 'Alice'): vertex IDs = {alice_ids}")

# Range lookup on age
age_25_30 = vp_idx.lookup_range("age", 25, 30)
print(f"  lookup_range('age', 25, 30): vertex IDs = {sorted(age_25_30)}")

# Edge property index -- add weights to social edges for this demo
gs.add_edge(Edge(30, 1, 2, "trusts", {"weight": 0.9}), graph="social")
gs.add_edge(Edge(31, 2, 3, "trusts", {"weight": 0.7}), graph="social")
gs.add_edge(Edge(32, 3, 4, "trusts", {"weight": 0.5}), graph="social")

ep_idx = EdgePropertyIndex.build(gs, graph="social", properties=["weight"])
print(f"  EdgePropertyIndex has 'weight': {ep_idx.has_property('weight')}")
high_weight = ep_idx.lookup_range("weight", 0.8, 1.0)
print(f"  lookup_range('weight', 0.8, 1.0): edge IDs = {sorted(high_weight)}")


# ==============================================================
# 10. Graph Statistics
# ==============================================================
print("\n" + "=" * 60)
print("10. Graph Statistics")
print("=" * 60)

stats = GraphStats.from_graph_store(gs, graph="social")
print(f"  Vertices: {stats.num_vertices}")
print(f"  Edges:    {stats.num_edges}")
print(f"  Avg out-degree: {stats.avg_out_degree:.2f}")
print(f"  Vertex label counts: {stats.vertex_label_counts}")
print(f"  Label degree map: {dict(sorted(stats.label_degree_map.items()))}")
print(f"  Degree distribution: {dict(sorted(stats.degree_distribution.items()))}")


# ==============================================================
# 11. Semi-Join / Anti-Join
# ==============================================================
print("\n" + "=" * 60)
print("11. Semi-Join / Anti-Join")
print("=" * 60)

# Use traverse results as left/right operands for semi/anti join.
# Left: all people reachable from Alice via knows (social)
# Right: all people in work graph reachable from Alice via manages


class _PostingListOp(Operator):
    """Wraps a graph operator to produce a PostingList for join operators."""

    def __init__(self, graph_op: object) -> None:
        self._graph_op = graph_op

    def execute(self, context: ExecutionContext):
        from uqa.core.posting_list import PostingList

        gpl = self._graph_op.execute(context)  # type: ignore[union-attr]
        entries = [PostingEntry(e.doc_id, Payload(score=e.payload.score)) for e in gpl]
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats):
        return 1.0


left_op = _PostingListOp(TraverseOperator(1, graph="social", label="knows", max_hops=2))
right_op = _PostingListOp(
    TraverseOperator(1, graph="work", label="manages", max_hops=2)
)

semi = SemiJoinOperator(left_op, right_op)
semi_result = semi.execute(ctx)
print(f"  Semi-join (social knows SEMI work manages): {len(semi_result)} entries")
for entry in semi_result:
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['name']}")

anti = AntiJoinOperator(left_op, right_op)
anti_result = anti.execute(ctx)
print(f"  Anti-join (social knows ANTI work manages): {len(anti_result)} entries")
for entry in anti_result:
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['name']}")


# ==============================================================
# 12. Category-Theoretic Functors
# ==============================================================
print("\n" + "=" * 60)
print("12. Category-Theoretic Functors")
print("=" * 60)

# Graph -> Relational functor
g2r = GraphToRelationalFunctor()
traverse_social = TraverseOperator(1, graph="social", label="knows", max_hops=2)
gpl = traverse_social.execute(ctx)
relational_pl = g2r.map_object(gpl)
print(
    f"  GraphToRelational: {len(gpl)} graph entries -> {len(relational_pl)} relational entries"
)
for entry in sorted(relational_pl, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(
            f"    [{entry.doc_id}] {v.properties['name']} score={entry.payload.score:.2f}"
        )

# Relational -> Graph functor
r2g = RelationalToGraphFunctor(edge_label="connected")
graph_pl = r2g.map_object(relational_pl)
print(
    f"  RelationalToGraph: {len(relational_pl)} relational -> {len(graph_pl)} graph entries"
)

# Roundtrip: Graph -> Relational -> Graph preserves entry count
roundtrip = r2g.map_object(g2r.map_object(gpl))
print(
    f"  Roundtrip preserves count: {len(gpl)} -> {len(roundtrip)} (equal={len(gpl) == len(roundtrip)})"
)


# ==============================================================
# 13. Adaptive Fusion
# ==============================================================
print("\n" + "=" * 60)
print("13. Adaptive Fusion")
print("=" * 60)

# Combine a text-like signal with a graph traversal signal.
# We simulate a text signal using a PostingList operator.


class _FixedScoreOp(Operator):
    """Operator returning fixed scores for given doc IDs."""

    def __init__(self, scores: dict[int, float]) -> None:
        self._scores = scores

    def execute(self, context: ExecutionContext):
        from uqa.core.posting_list import PostingList

        entries = [
            PostingEntry(did, Payload(score=s))
            for did, s in sorted(self._scores.items())
        ]
        return PostingList.from_sorted(entries)

    def cost_estimate(self, stats):
        return 1.0


# Simulated text signal -- Alice and Carol score high
text_signal = _FixedScoreOp({1: 0.85, 2: 0.40, 3: 0.78, 4: 0.30})

# Graph signal -- traverse from Alice via knows (2 hops)
graph_signal = _PostingListOp(
    TraverseOperator(1, graph="social", label="knows", max_hops=2)
)

fusion_op = AdaptiveLogOddsFusionOperator(
    signals=[text_signal, graph_signal],
    base_alpha=0.5,
)
fused = fusion_op.execute(ctx)
print("  Adaptive fusion (text + graph) results:")
for entry in sorted(fused, key=lambda e: -e.payload.score):
    v = gs.get_vertex(entry.doc_id)
    name = v.properties["name"] if v else f"doc_{entry.doc_id}"
    print(f"    [{entry.doc_id}] {name} fused_score={entry.payload.score:.4f}")


print("\n" + "=" * 60)
print("All named graph examples (fluent API) completed successfully.")
print("=" * 60)
