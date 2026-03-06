"""Example 3: Knowledge Graph Exploration
==========================================

A biomedical knowledge graph demonstrating:
- Graph traversal (BFS over relationship types)
- Pattern matching (find specific structural motifs)
- Regular path queries (transitive relationships)
- Cross-paradigm queries (graph + text + vector)
- Graph-enhanced document retrieval

Scenario: A biomedical researcher exploring drug-disease-gene relationships
using a knowledge graph combined with literature search.
"""

from __future__ import annotations

import numpy as np

from uqa.engine import Engine
from uqa.core.types import Edge, Equals, GreaterThanOrEqual, Vertex
from uqa.graph.pattern import EdgePattern, GraphPattern, VertexPattern


def build_biomedical_database() -> Engine:
    """Build a biomedical knowledge graph with associated literature."""
    engine = Engine(vector_dimensions=16, max_elements=1000)
    rng = np.random.RandomState(123)

    # --- Knowledge Graph Vertices ---
    # Drugs
    vertices = [
        Vertex(1,  {"type": "drug",    "name": "Aspirin",       "class": "NSAID"}),
        Vertex(2,  {"type": "drug",    "name": "Ibuprofen",     "class": "NSAID"}),
        Vertex(3,  {"type": "drug",    "name": "Metformin",     "class": "biguanide"}),
        Vertex(4,  {"type": "drug",    "name": "Insulin",       "class": "hormone"}),
        Vertex(5,  {"type": "drug",    "name": "Atorvastatin",  "class": "statin"}),
        # Diseases
        Vertex(6,  {"type": "disease", "name": "Inflammation",  "icd": "M79.3"}),
        Vertex(7,  {"type": "disease", "name": "Diabetes",      "icd": "E11"}),
        Vertex(8,  {"type": "disease", "name": "Heart Disease",  "icd": "I25"}),
        Vertex(9,  {"type": "disease", "name": "Pain",          "icd": "R52"}),
        Vertex(10, {"type": "disease", "name": "Hyperlipidemia", "icd": "E78"}),
        # Genes / Proteins
        Vertex(11, {"type": "gene", "name": "COX-2",    "symbol": "PTGS2"}),
        Vertex(12, {"type": "gene", "name": "AMPK",     "symbol": "PRKAA1"}),
        Vertex(13, {"type": "gene", "name": "HMG-CoA",  "symbol": "HMGCR"}),
        Vertex(14, {"type": "gene", "name": "TNF-alpha", "symbol": "TNF"}),
        Vertex(15, {"type": "gene", "name": "Insulin Receptor", "symbol": "INSR"}),
        # Pathways
        Vertex(16, {"type": "pathway", "name": "Inflammatory Response"}),
        Vertex(17, {"type": "pathway", "name": "Glucose Metabolism"}),
        Vertex(18, {"type": "pathway", "name": "Cholesterol Biosynthesis"}),
    ]
    for v in vertices:
        engine.add_graph_vertex(v)

    # --- Knowledge Graph Edges ---
    edges = [
        # Drug - treats -> Disease
        Edge(1,  1, 6,  "treats"),     # Aspirin treats Inflammation
        Edge(2,  1, 9,  "treats"),     # Aspirin treats Pain
        Edge(3,  2, 6,  "treats"),     # Ibuprofen treats Inflammation
        Edge(4,  2, 9,  "treats"),     # Ibuprofen treats Pain
        Edge(5,  3, 7,  "treats"),     # Metformin treats Diabetes
        Edge(6,  4, 7,  "treats"),     # Insulin treats Diabetes
        Edge(7,  5, 10, "treats"),     # Atorvastatin treats Hyperlipidemia
        Edge(8,  5, 8,  "treats"),     # Atorvastatin treats Heart Disease
        # Drug - targets -> Gene
        Edge(9,  1, 11, "targets"),    # Aspirin targets COX-2
        Edge(10, 2, 11, "targets"),    # Ibuprofen targets COX-2
        Edge(11, 3, 12, "targets"),    # Metformin targets AMPK
        Edge(12, 4, 15, "targets"),    # Insulin targets Insulin Receptor
        Edge(13, 5, 13, "targets"),    # Atorvastatin targets HMG-CoA
        # Gene - involved_in -> Pathway
        Edge(14, 11, 16, "involved_in"),  # COX-2 in Inflammatory Response
        Edge(15, 14, 16, "involved_in"),  # TNF-alpha in Inflammatory Response
        Edge(16, 12, 17, "involved_in"),  # AMPK in Glucose Metabolism
        Edge(17, 15, 17, "involved_in"),  # Insulin Receptor in Glucose Metabolism
        Edge(18, 13, 18, "involved_in"),  # HMG-CoA in Cholesterol Biosynthesis
        # Disease - associated_with -> Gene
        Edge(19, 6, 14, "associated_with"),  # Inflammation <-> TNF-alpha
        Edge(20, 6, 11, "associated_with"),  # Inflammation <-> COX-2
        Edge(21, 7, 15, "associated_with"),  # Diabetes <-> Insulin Receptor
        Edge(22, 7, 12, "associated_with"),  # Diabetes <-> AMPK
        Edge(23, 8, 13, "associated_with"),  # Heart Disease <-> HMG-CoA
        Edge(24, 10, 13, "associated_with"), # Hyperlipidemia <-> HMG-CoA
        # Disease - complicates -> Disease
        Edge(25, 7, 8,  "complicates"),  # Diabetes complicates Heart Disease
        Edge(26, 10, 8, "complicates"),  # Hyperlipidemia complicates Heart Disease
    ]
    for e in edges:
        engine.add_graph_edge(e)

    # --- Literature (documents associated with entities) ---
    papers = [
        {
            "doc_id": 101,
            "title": "aspirin and cardiovascular disease prevention",
            "abstract": "aspirin inhibits cox-2 and reduces inflammation markers "
                        "this review examines aspirin role in preventing cardiovascular "
                        "events and heart disease through anti-inflammatory mechanisms",
            "year": 2023,
            "entity_ids": "1,6,8,11",
        },
        {
            "doc_id": 102,
            "title": "metformin mechanism of action in diabetes",
            "abstract": "metformin activates ampk pathway improving glucose metabolism "
                        "and insulin sensitivity this study reveals new molecular targets "
                        "for diabetes treatment",
            "year": 2024,
            "entity_ids": "3,7,12",
        },
        {
            "doc_id": 103,
            "title": "statin therapy and cholesterol reduction",
            "abstract": "atorvastatin inhibits hmg-coa reductase reducing cholesterol "
                        "biosynthesis and lowering cardiovascular risk in patients "
                        "with hyperlipidemia and heart disease",
            "year": 2023,
            "entity_ids": "5,10,8,13",
        },
        {
            "doc_id": 104,
            "title": "tnf-alpha role in chronic inflammation",
            "abstract": "tnf-alpha is a key mediator of inflammatory response "
                        "targeting tnf-alpha with biological therapies shows promise "
                        "for treating chronic inflammation and autoimmune conditions",
            "year": 2024,
            "entity_ids": "6,14",
        },
        {
            "doc_id": 105,
            "title": "insulin receptor signaling in glucose homeostasis",
            "abstract": "insulin receptor activation triggers downstream signaling "
                        "cascades essential for glucose uptake and metabolism "
                        "disruption leads to diabetes and metabolic syndrome",
            "year": 2024,
            "entity_ids": "4,7,15",
        },
        {
            "doc_id": 106,
            "title": "nsaid comparison study aspirin vs ibuprofen",
            "abstract": "this clinical trial compares aspirin and ibuprofen for pain "
                        "and inflammation treatment both drugs target cox-2 enzyme "
                        "but differ in selectivity and side effect profiles",
            "year": 2023,
            "entity_ids": "1,2,9,6,11",
        },
        {
            "doc_id": 107,
            "title": "diabetes and heart disease comorbidity analysis",
            "abstract": "patients with diabetes face significantly elevated risk "
                        "of heart disease this population study examines shared "
                        "molecular pathways including ampk and cholesterol metabolism",
            "year": 2024,
            "entity_ids": "7,8,12,13",
        },
    ]

    for paper in papers:
        doc_id = paper.pop("doc_id")
        embedding = rng.randn(16).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
        engine.add_document(doc_id, paper, embedding)

    return engine


def main() -> None:
    engine = build_biomedical_database()

    print("=" * 70)
    print("UQA Biomedical Knowledge Graph -- Realistic Examples")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Query 1: What does Aspirin treat? (1-hop traversal)
    # ------------------------------------------------------------------
    print("\n--- Query 1: What does Aspirin (vertex 1) treat? ---")
    results = engine.query().traverse(start=1, label="treats", max_hops=1).execute()
    target_ids = results.doc_ids - {1}
    for vid in sorted(target_ids):
        v = engine.graph_store.get_vertex(vid)
        if v:
            print(f"  -> {v.properties['name']} ({v.properties['type']})")

    # ------------------------------------------------------------------
    # Query 2: Which genes does Aspirin target?
    # ------------------------------------------------------------------
    print("\n--- Query 2: What does Aspirin (vertex 1) target? ---")
    results = engine.query().traverse(start=1, label="targets", max_hops=1).execute()
    target_ids = results.doc_ids - {1}
    for vid in sorted(target_ids):
        v = engine.graph_store.get_vertex(vid)
        if v:
            print(f"  -> {v.properties['name']} ({v.properties.get('symbol', '')})")

    # ------------------------------------------------------------------
    # Query 3: Full drug profile -- 1-hop from Aspirin (all edge types)
    # ------------------------------------------------------------------
    print("\n--- Query 3: Full Aspirin profile (all relationships, 1 hop) ---")
    results = engine.query().traverse(start=1, label=None, max_hops=1).execute()
    related_ids = results.doc_ids - {1}
    for vid in sorted(related_ids):
        v = engine.graph_store.get_vertex(vid)
        if v:
            print(f"  -> [{v.properties['type']}] {v.properties['name']}")

    # ------------------------------------------------------------------
    # Query 4: 2-hop from Diabetes -- what is connected?
    # (Diabetes -> Genes -> Pathways, Diabetes -> Drugs <- ...)
    # ------------------------------------------------------------------
    print("\n--- Query 4: 2-hop neighborhood of Diabetes (vertex 7) ---")
    results = engine.query().traverse(start=7, label=None, max_hops=2).execute()
    related_ids = results.doc_ids - {7}
    for vid in sorted(related_ids):
        v = engine.graph_store.get_vertex(vid)
        if v:
            print(f"  -> [{v.properties['type']}] {v.properties['name']}")

    # ------------------------------------------------------------------
    # Query 5: RPQ -- find drug->gene->pathway chains
    # (drug targets gene, gene involved_in pathway)
    # ------------------------------------------------------------------
    print("\n--- Query 5: RPQ -- Drug -> Gene -> Pathway chains ---")
    print("    targets/involved_in")
    results = engine.query().rpq("targets/involved_in").execute()
    print(f"Pathway endpoints reachable from drug-targeted genes:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        v = engine.graph_store.get_vertex(entry.doc_id)
        if v and v.properties.get("type") == "pathway":
            print(f"  -> [{entry.doc_id}] {v.properties['name']}")

    # ------------------------------------------------------------------
    # Query 6: RPQ -- transitive disease complications
    # (complicates chain of any length)
    # ------------------------------------------------------------------
    print("\n--- Query 6: RPQ -- What does Diabetes complicate (transitively)? ---")
    print("    complicates/complicates*  (from vertex 7 = Diabetes)")
    results = engine.query().rpq("complicates/complicates*", start=7).execute()
    print(f"Reachable disease endpoints via complication chains:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        v = engine.graph_store.get_vertex(entry.doc_id)
        if v and v.properties.get("type") == "disease":
            print(f"  -> [{entry.doc_id}] {v.properties['name']}")

    # ------------------------------------------------------------------
    # Query 7: Pattern match -- find all (Drug)-[treats]->(Disease)
    #          where Drug targets a Gene associated_with that Disease
    # ------------------------------------------------------------------
    print("\n--- Query 7: Drugs with known mechanism for their treated disease ---")
    print("    Pattern: (drug)-[targets]->(gene)<-[associated_with]-(disease)")
    print("             AND (drug)-[treats]->(disease)")
    pattern = GraphPattern(
        vertex_patterns=[
            VertexPattern("drug", [lambda v: v.properties.get("type") == "drug"]),
            VertexPattern("gene", [lambda v: v.properties.get("type") == "gene"]),
            VertexPattern("disease", [lambda v: v.properties.get("type") == "disease"]),
        ],
        edge_patterns=[
            EdgePattern("drug", "gene", "targets"),
            EdgePattern("disease", "gene", "associated_with"),
            EdgePattern("drug", "disease", "treats"),
        ],
    )
    results = engine.query().match_pattern(pattern).execute()
    print(f"Found {len(results)} mechanistic drug-disease links:")

    # ------------------------------------------------------------------
    # Query 8: Text search -- find papers about inflammation
    # ------------------------------------------------------------------
    print("\n--- Query 8: Papers about 'inflammation' ---")
    results = (
        engine.query()
        .term("inflammation")
        .score_bayesian_bm25("inflammation treatment")
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] {doc['title']}")
        print(f"       P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 9: Cross-paradigm -- graph + text
    # Find drugs that treat Heart Disease AND have related papers
    # about cholesterol
    # ------------------------------------------------------------------
    print("\n--- Query 9: Cross-paradigm (graph + text) ---")
    print("    Drugs treating Heart Disease (vertex 8)")
    print("    AND papers about 'cholesterol'")

    # Graph: what treats Heart Disease?
    graph_results = (
        engine.query()
        .traverse(start=8, label="treats", max_hops=1)
    )

    # Text: papers about cholesterol
    text_results = (
        engine.query()
        .term("cholesterol")
        .score_bayesian_bm25("cholesterol")
    )

    fused = (
        engine.query()
        .fuse_log_odds(graph_results, text_results, alpha=0.5)
        .execute()
    )
    print(f"Fused results ({len(fused)} entries):")
    for entry in sorted(fused, key=lambda e: -e.payload.score):
        # Check if it's a graph vertex or a document
        v = engine.graph_store.get_vertex(entry.doc_id)
        doc = engine.document_store.get(entry.doc_id)
        if v:
            print(f"  [vertex {entry.doc_id}] {v.properties['name']} "
                  f"({v.properties['type']}) score={entry.payload.score:.4f}")
        if doc:
            print(f"  [doc {entry.doc_id}] {doc['title']} "
                  f"score={entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 10: Recent papers about diabetes
    # ------------------------------------------------------------------
    print("\n--- Query 10: Recent papers (2024+) about 'diabetes' ---")
    results = (
        engine.query()
        .term("diabetes")
        .filter("year", GreaterThanOrEqual(2024))
        .score_bayesian_bm25("diabetes treatment")
        .execute()
    )
    print(f"Found {len(results)} papers:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{entry.doc_id}] ({doc['year']}) {doc['title']}")
        print(f"       P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 11: Faceted search -- papers by year
    # ------------------------------------------------------------------
    print("\n--- Query 11: Paper distribution by year ---")
    facets = (
        engine.query()
        .term("disease")
        .facet("year")
    )
    print("Year distribution:")
    for year, count in sorted(facets.counts.items()):
        print(f"  {year}: {count} paper(s)")

    print("\n" + "=" * 70)
    print("All examples completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
