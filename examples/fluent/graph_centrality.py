#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph centrality, bounded RPQ, weighted paths, and indexing examples.

Demonstrates:
  - PageRank centrality scoring
  - HITS hub/authority scoring
  - Betweenness centrality
  - Bounded RPQ (e{min,max} syntax)
  - Weighted path queries with aggregate predicates
  - Subgraph index build and lookup
  - Incremental pattern matching with graph deltas
"""

from uqa.core.types import Edge, IndexStats, Vertex
from uqa.graph.centrality import (
    BetweennessCentralityOperator,
    HITSOperator,
    PageRankOperator,
)
from uqa.graph.incremental_match import GraphDelta, IncrementalPatternMatcher
from uqa.graph.index import SubgraphIndex
from uqa.graph.operators import (
    PatternMatchOperator,
    RegularPathQueryOperator,
    WeightedPathQueryOperator,
)
from uqa.graph.pattern import (
    EdgePattern,
    GraphPattern,
    VertexPattern,
    parse_rpq,
)
from uqa.graph.store import GraphStore
from uqa.operators.base import ExecutionContext

# ======================================================================
# Data setup: citation network
# ======================================================================

gs = GraphStore()
gs.create_graph("citations")

papers = [
    Vertex(
        1,
        "paper",
        {"title": "Attention Is All You Need", "year": 2017, "citations": 90000},
    ),
    Vertex(2, "paper", {"title": "BERT", "year": 2019, "citations": 75000}),
    Vertex(
        3,
        "paper",
        {"title": "Graph Attention Networks", "year": 2018, "citations": 15000},
    ),
    Vertex(
        4, "paper", {"title": "Vision Transformer", "year": 2021, "citations": 25000}
    ),
    Vertex(5, "paper", {"title": "GPT-3", "year": 2020, "citations": 30000}),
    Vertex(6, "paper", {"title": "Diffusion Models", "year": 2021, "citations": 12000}),
    Vertex(7, "paper", {"title": "RLHF", "year": 2022, "citations": 5000}),
    Vertex(
        8, "paper", {"title": "Efficient Attention", "year": 2020, "citations": 3000}
    ),
]
for v in papers:
    gs.add_vertex(v, graph="citations")

# Citation edges with weight = log(citations) and year metadata
edges = [
    Edge(1, 2, 1, "cites", {"weight": 5.0, "year": 2019}),  # BERT -> Attention
    Edge(2, 3, 1, "cites", {"weight": 3.0, "year": 2018}),  # GAT -> Attention
    Edge(3, 4, 1, "cites", {"weight": 4.0, "year": 2021}),  # ViT -> Attention
    Edge(4, 4, 3, "cites", {"weight": 2.0, "year": 2021}),  # ViT -> GAT
    Edge(5, 5, 1, "cites", {"weight": 4.5, "year": 2020}),  # GPT-3 -> Attention
    Edge(6, 5, 2, "cites", {"weight": 3.5, "year": 2020}),  # GPT-3 -> BERT
    Edge(7, 6, 4, "cites", {"weight": 2.5, "year": 2021}),  # Diffusion -> ViT
    Edge(8, 7, 5, "cites", {"weight": 3.0, "year": 2022}),  # RLHF -> GPT-3
    Edge(9, 7, 2, "cites", {"weight": 2.0, "year": 2022}),  # RLHF -> BERT
    Edge(10, 8, 1, "cites", {"weight": 4.0, "year": 2020}),  # Efficient -> Attention
]
for e in edges:
    gs.add_edge(e, graph="citations")

ctx = ExecutionContext(graph_store=gs)

print("=" * 70)
print("Graph Centrality, Bounded RPQ, and Indexing Examples")
print("=" * 70)


# ------------------------------------------------------------------
# 1. PageRank: identify most influential papers
# ------------------------------------------------------------------
print("\n--- 1. PageRank: paper influence ranking ---")
pr = PageRankOperator(
    damping=0.85, max_iterations=100, tolerance=1e-6, graph="citations"
)
results = pr.execute(ctx)
ranked = sorted(results, key=lambda e: e.payload.score, reverse=True)
for entry in ranked:
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(
            f"  [{entry.doc_id}] {v.properties['title']:<30} PR={entry.payload.score:.4f}"
        )


# ------------------------------------------------------------------
# 2. HITS: hub and authority scores
# ------------------------------------------------------------------
print("\n--- 2. HITS: papers as hubs and authorities ---")
hits = HITSOperator(max_iterations=100, tolerance=1e-6, graph="citations")
results = hits.execute(ctx)
print("  Top authorities (most-cited):")
by_auth = sorted(results, key=lambda e: e.payload.score, reverse=True)
for entry in by_auth[:4]:
    v = gs.get_vertex(entry.doc_id)
    if v:
        hub = entry.payload.fields.get("hub_score", 0)
        auth = entry.payload.fields.get("authority_score", 0)
        print(f"    {v.properties['title']:<30} auth={auth:.4f}  hub={hub:.4f}")


# ------------------------------------------------------------------
# 3. Betweenness centrality: bridge papers
# ------------------------------------------------------------------
print("\n--- 3. Betweenness centrality: bridge papers ---")
bc = BetweennessCentralityOperator(graph="citations")
results = bc.execute(ctx)
ranked = sorted(results, key=lambda e: e.payload.score, reverse=True)
for entry in ranked[:4]:
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(
            f"  [{entry.doc_id}] {v.properties['title']:<30} BC={entry.payload.score:.4f}"
        )


# ------------------------------------------------------------------
# 4. Cost estimates for centrality operators
# ------------------------------------------------------------------
print("\n--- 4. Cost estimates ---")
stats = IndexStats(total_docs=len(papers))
print(f"  PageRank cost:     {pr.cost_estimate(stats):>10.1f}")
print(f"  HITS cost:         {hits.cost_estimate(stats):>10.1f}")
print(f"  Betweenness cost:  {bc.cost_estimate(stats):>10.1f}")


# ------------------------------------------------------------------
# 5. Bounded RPQ: papers reachable in exactly 2-3 citation hops
# ------------------------------------------------------------------
print("\n--- 5. Bounded RPQ: cites{2,3} from Attention (paper 1) ---")
expr = parse_rpq("cites{2,3}")
rpq = RegularPathQueryOperator(expr, graph="citations", start_vertex=1)
results = rpq.execute(ctx)
# Note: edges go FROM citing TO cited, so start from a citing paper
# Let's start from RLHF (7) which cites papers that cite others
expr2 = parse_rpq("cites{1,2}")
rpq2 = RegularPathQueryOperator(expr2, graph="citations", start_vertex=7)
results2 = rpq2.execute(ctx)
print(f"  cites{{1,2}} from RLHF: {len(results2)} papers reachable")
for entry in sorted(results2, key=lambda e: e.doc_id):
    v = gs.get_vertex(entry.doc_id)
    if v:
        print(f"    [{entry.doc_id}] {v.properties['title']}")


# ------------------------------------------------------------------
# 6. Weighted path query: heaviest citation chains
# ------------------------------------------------------------------
print("\n--- 6. Weighted path: sum of citation weights from RLHF ---")
wop = WeightedPathQueryOperator(
    path_expr=parse_rpq("cites/cites"),
    graph="citations",
    weight_property="weight",
    aggregate_fn="sum",
    start_vertex=7,
)
results = wop.execute(ctx)
for entry in sorted(
    results, key=lambda e: e.payload.fields.get("path_weight", 0), reverse=True
):
    v = gs.get_vertex(entry.doc_id)
    if v:
        w = entry.payload.fields.get("path_weight", 0)
        print(f"  [{entry.doc_id}] {v.properties['title']:<30} total_weight={w:.1f}")


# ------------------------------------------------------------------
# 7. Weighted path with predicate: only strong citation chains
# ------------------------------------------------------------------
print("\n--- 7. Weighted path: only chains with total weight > 6.0 ---")
wop_filtered = WeightedPathQueryOperator(
    path_expr=parse_rpq("cites/cites"),
    graph="citations",
    weight_property="weight",
    aggregate_fn="sum",
    predicate=lambda w: w > 6.0,
    start_vertex=7,
)
results = wop_filtered.execute(ctx)
if not list(results):
    print("  (no paths with total weight > 6.0)")
else:
    for entry in results:
        v = gs.get_vertex(entry.doc_id)
        if v:
            w = entry.payload.fields.get("path_weight", 0)
            print(f"  [{entry.doc_id}] {v.properties['title']:<30} weight={w:.1f}")


# ------------------------------------------------------------------
# 8. Subgraph index: cache frequent patterns
# ------------------------------------------------------------------
print("\n--- 8. SubgraphIndex: pre-indexing citation patterns ---")
pattern = GraphPattern(
    [VertexPattern("a"), VertexPattern("b")],
    [EdgePattern("a", "b", "cites")],
)
idx = SubgraphIndex.build(gs, [pattern], graph_name="citations")
cached = idx.lookup(pattern)
print(f"  Cached {len(cached)} citation pair matches")
print(f"  Index has pattern: {idx.has_pattern(pattern)}")

# Use the index for fast pattern matching
ctx_indexed = ExecutionContext(graph_store=gs, subgraph_index=idx)
pm = PatternMatchOperator(pattern, graph="citations")
result = pm.execute(ctx_indexed)
print(f"  PatternMatch via cache: {len(result)} results (O(1) lookup)")

# Invalidation
idx.invalidate({"cites"})
print(f"  After invalidation: has_pattern = {idx.has_pattern(pattern)}")


# ------------------------------------------------------------------
# 9. Incremental pattern matching
# ------------------------------------------------------------------
print("\n--- 9. Incremental pattern matching ---")
pattern2 = GraphPattern(
    [VertexPattern("a"), VertexPattern("b")],
    [EdgePattern("a", "b", "cites")],
)
# Get initial matches
pm2 = PatternMatchOperator(pattern2, graph="citations")
initial_gpl = pm2.execute(ctx)
initial_matches = set()
for entry in initial_gpl:
    gp = initial_gpl.get_graph_payload(entry.doc_id)
    if gp:
        initial_matches.add(gp.subgraph_vertices)

matcher = IncrementalPatternMatcher(pattern2, initial_matches, graph_name="citations")
print(f"  Initial matches: {len(matcher.base_matches)}")

# Add a new citation edge: Efficient Attention (8) -> BERT (2)
new_eid = gs.next_edge_id()
gs.add_edge(Edge(new_eid, 8, 2, "cites", {"weight": 2.5}), graph="citations")
delta = GraphDelta(added_edge_ids={new_eid})
updated = matcher.update(gs, delta)
print(f"  After adding edge 8->2: {len(updated)} matches")

# The new edge should create a new match {8, 2}
new_match_found = any(frozenset({8, 2}).issubset(m) for m in updated)
print(f"  New (8, 2) match found: {new_match_found}")


print("\n" + "=" * 70)
print("All graph centrality and indexing examples completed successfully.")
print("=" * 70)
