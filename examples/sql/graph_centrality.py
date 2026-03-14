#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph centrality, bounded RPQ, and weighted path SQL examples.

Demonstrates:
  - graph_add_vertex / graph_add_edge: SQL graph mutation functions
  - pagerank(): PageRank centrality (WHERE signal and FROM table function)
  - hits(): HITS hub/authority scoring
  - betweenness(): Betweenness centrality
  - rpq('label{min,max}', start): Bounded regular path query
  - weighted_rpq('expr', start, 'prop', 'agg', threshold): Weighted path query
  - progressive_fusion(): Cascading multi-stage WAND fusion
  - Centrality + relational aggregation and fusion
  - Named graph support via 'graph:name' and Cypher
"""

from uqa.engine import Engine

# ======================================================================
# Data setup: citation network (100% SQL)
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        year INTEGER NOT NULL,
        field TEXT,
        citations INTEGER DEFAULT 0
    )
""")

engine.sql("""INSERT INTO papers (title, year, field, citations) VALUES
    ('Attention Is All You Need', 2017, 'nlp', 90000),
    ('BERT', 2019, 'nlp', 75000),
    ('Graph Attention Networks', 2018, 'graph', 15000),
    ('Vision Transformer', 2021, 'cv', 25000),
    ('GPT-3', 2020, 'nlp', 30000),
    ('Diffusion Models', 2021, 'cv', 12000),
    ('RLHF', 2022, 'alignment', 5000),
    ('Efficient Attention', 2020, 'nlp', 3000)
""")

# Add graph vertices via SQL
for i in range(1, 9):
    engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'paper', 'papers')")

# Add citation edges via SQL (with weight property)
citation_edges = [
    (1, 2, 1, "cites", "weight=5.0"),
    (2, 3, 1, "cites", "weight=3.0"),
    (3, 4, 1, "cites", "weight=4.0"),
    (4, 4, 3, "cites", "weight=2.0"),
    (5, 5, 1, "cites", "weight=4.5"),
    (6, 5, 2, "cites", "weight=3.5"),
    (7, 6, 4, "cites", "weight=2.5"),
    (8, 7, 5, "cites", "weight=3.0"),
    (9, 7, 2, "cites", "weight=2.0"),
    (10, 8, 1, "cites", "weight=4.0"),
]
for eid, src, tgt, label, props in citation_edges:
    engine.sql(
        f"SELECT * FROM graph_add_edge({eid}, {src}, {tgt}, '{label}', 'papers', '{props}')"
    )

# Named graph via Cypher (for named graph examples)
engine.sql("SELECT * FROM create_graph('citations')")
engine.sql("""
    SELECT * FROM cypher('citations', $$
        CREATE (a:Paper {vid: 1, title: 'Attention Is All You Need'})
        CREATE (b:Paper {vid: 2, title: 'BERT'})
        CREATE (c:Paper {vid: 3, title: 'GAT'})
        CREATE (d:Paper {vid: 4, title: 'ViT'})
        CREATE (e:Paper {vid: 5, title: 'GPT-3'})
        CREATE (f:Paper {vid: 6, title: 'Diffusion'})
        CREATE (g:Paper {vid: 7, title: 'RLHF'})
        CREATE (h:Paper {vid: 8, title: 'Efficient Attention'})
        CREATE (b)-[:cites {weight: 5.0}]->(a)
        CREATE (c)-[:cites {weight: 3.0}]->(a)
        CREATE (d)-[:cites {weight: 4.0}]->(a)
        CREATE (d)-[:cites {weight: 2.0}]->(c)
        CREATE (e)-[:cites {weight: 4.5}]->(a)
        CREATE (e)-[:cites {weight: 3.5}]->(b)
        CREATE (f)-[:cites {weight: 2.5}]->(d)
        CREATE (g)-[:cites {weight: 3.0}]->(e)
        CREATE (g)-[:cites {weight: 2.0}]->(b)
        CREATE (h)-[:cites {weight: 4.0}]->(a)
        RETURN a.title
    $$) AS (t agtype)
""")


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<25}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<25.4f}")
            else:
                vals.append(str(v)[:25].ljust(25))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Graph Centrality SQL Examples")
print("=" * 70)


# ==================================================================
# 1. FROM pagerank(): per-table graph centrality
# ==================================================================
show(
    "1. FROM pagerank(): per-table centrality",
    engine.sql("SELECT _doc_id, title, _score FROM pagerank() ORDER BY _score DESC"),
)


# ==================================================================
# 2. FROM pagerank() on named graph
# ==================================================================
show(
    "2. FROM pagerank('graph:citations'): named graph",
    engine.sql(
        "SELECT _doc_id, _score FROM pagerank('graph:citations') "
        "ORDER BY _score DESC LIMIT 4"
    ),
)


# ==================================================================
# 3. FROM hits(): HITS scoring
# ==================================================================
show(
    "3. FROM hits(): hub/authority scores",
    engine.sql("SELECT _doc_id, title, _score FROM hits() ORDER BY _score DESC"),
)


# ==================================================================
# 4. FROM betweenness(): bridge papers
# ==================================================================
show(
    "4. FROM betweenness(): bridge detection",
    engine.sql(
        "SELECT _doc_id, title, _score FROM betweenness() ORDER BY _score DESC LIMIT 4"
    ),
)


# ==================================================================
# 5. WHERE pagerank(): centrality as scored filter
# ==================================================================
show(
    "5. WHERE pagerank() AND year >= 2019",
    engine.sql("""
    SELECT title, year, _score FROM papers
    WHERE pagerank() AND year >= 2019
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 6. Aggregation over centrality results
# ==================================================================
show(
    "6. AVG PageRank by research field",
    engine.sql("""
    SELECT field, COUNT(*) AS cnt, AVG(_score) AS avg_pr
    FROM pagerank()
    GROUP BY field
    ORDER BY avg_pr DESC
"""),
)


# ==================================================================
# 7. Fusion: text + centrality
# ==================================================================
show(
    "7. fuse_log_odds: text + pagerank",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention transformer'),
        pagerank()
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 8. Fusion with gating
# ==================================================================
show(
    "8. fuse_log_odds + relu gating",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE fuse_log_odds(
        text_match(title, 'attention'),
        pagerank(),
        'relu'
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 9. Bounded RPQ: 1-2 hops
# ==================================================================
show(
    "9. rpq('cites{1,2}', 7): bounded from RLHF",
    engine.sql("SELECT _doc_id, title FROM rpq('cites{1,2}', 7)"),
)


# ==================================================================
# 10. Bounded RPQ: exactly 2 hops
# ==================================================================
show(
    "10. rpq('cites{2,2}', 7): exactly 2 hops",
    engine.sql("SELECT _doc_id, title FROM rpq('cites{2,2}', 7)"),
)


# ==================================================================
# 11. Bounded vs Kleene reachability
# ==================================================================
print("\n--- 11. Reachability: bounded vs Kleene ---")
for expr in ("cites{1,1}", "cites{1,2}", "cites{1,3}", "cites*"):
    result = engine.sql(f"SELECT COUNT(*) AS cnt FROM rpq('{expr}', 7)")
    cnt = result.rows[0]["cnt"] if result.rows else 0
    print(f"  rpq('{expr}', 7): {cnt} papers")


# ==================================================================
# 12. Bounded RPQ + aggregation
# ==================================================================
show(
    "12. AVG citations within 2 hops of RLHF",
    engine.sql(
        "SELECT COUNT(*) AS cnt, AVG(citations) AS avg_cit FROM rpq('cites{1,2}', 7)"
    ),
)


# ==================================================================
# 13. Weighted RPQ: sum weights
# ==================================================================
show(
    "13. weighted_rpq: sum weights from RLHF",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE weighted_rpq('cites/cites', 7, 'weight', 'sum')
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 14. Weighted RPQ: with threshold
# ==================================================================
show(
    "14. weighted_rpq: threshold > 6.0",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE weighted_rpq('cites/cites', 7, 'weight', 'sum', 6.0)
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 15. Progressive fusion
# ==================================================================
show(
    "15. progressive_fusion: text then graph",
    engine.sql("""
    SELECT title, _score FROM papers
    WHERE progressive_fusion(
        text_match(title, 'attention'),
        traverse_match(1, 'cites', 2),
        5,
        pagerank(),
        3
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 16. Named graph centrality comparison
# ==================================================================
print("\n--- 16. Centrality comparison (named graph, top 3) ---")
for measure in ("pagerank", "hits", "betweenness"):
    result = engine.sql(
        f"SELECT _doc_id, _score FROM {measure}('graph:citations') "
        f"ORDER BY _score DESC LIMIT 3"
    )
    print(f"\n  {measure}():")
    for row in result.rows:
        print(f"    vertex {row['_doc_id']}: score={row['_score']:.4f}")


print("\n" + "=" * 70)
print("All graph centrality SQL examples completed successfully.")
print("=" * 70)
