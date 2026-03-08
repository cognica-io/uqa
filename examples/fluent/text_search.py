#!/usr/bin/env python3
"""Full-text search examples using the fluent QueryBuilder API.

Demonstrates:
  - Term search with BM25 scoring
  - Multi-term boolean queries (AND, OR, NOT)
  - Bayesian BM25 calibrated probabilities
  - Filter + text search combinations
  - Faceted search
  - Aggregation over search results
"""

from uqa.core.types import Between, Equals, GreaterThanOrEqual, InSet, LessThan
from uqa.engine import Engine

# ======================================================================
# Data setup: 10 tech news articles
# ======================================================================

engine = Engine()

articles = [
    (1, {
        "title": "transformer architecture revolutionizes nlp",
        "body": "the transformer model uses self attention mechanisms to process "
                "sequential data without recurrence enabling massive parallelism",
        "category": "nlp",
        "year": 2017,
        "citations": 90000,
    }),
    (2, {
        "title": "bert pre-training deep bidirectional transformers",
        "body": "bert introduces masked language modeling and next sentence prediction "
                "for pre-training deep bidirectional transformer representations",
        "category": "nlp",
        "year": 2019,
        "citations": 75000,
    }),
    (3, {
        "title": "graph attention networks for node classification",
        "body": "graph attention networks apply attention mechanisms to graph structured "
                "data enabling weighted aggregation of neighbor features",
        "category": "graph",
        "year": 2018,
        "citations": 15000,
    }),
    (4, {
        "title": "vision transformer image recognition at scale",
        "body": "vision transformer splits images into patches and processes them "
                "with a standard transformer encoder achieving strong results",
        "category": "cv",
        "year": 2021,
        "citations": 25000,
    }),
    (5, {
        "title": "scaling language models methods and insights",
        "body": "scaling laws show predictable improvement in language model performance "
                "as compute data and parameters increase following power law curves",
        "category": "nlp",
        "year": 2020,
        "citations": 8000,
    }),
    (6, {
        "title": "diffusion models beat generative adversarial networks",
        "body": "denoising diffusion probabilistic models achieve higher image quality "
                "than gans with more stable training and better mode coverage",
        "category": "cv",
        "year": 2021,
        "citations": 12000,
    }),
    (7, {
        "title": "reinforcement learning from human feedback",
        "body": "rlhf trains language models to follow instructions by combining "
                "supervised fine tuning with reward modeling and ppo optimization",
        "category": "alignment",
        "year": 2022,
        "citations": 5000,
    }),
    (8, {
        "title": "efficient attention mechanisms for long sequences",
        "body": "linear attention and sparse attention patterns reduce the quadratic "
                "cost of self attention enabling processing of very long sequences",
        "category": "nlp",
        "year": 2020,
        "citations": 3000,
    }),
    (9, {
        "title": "multimodal learning with vision and language",
        "body": "contrastive learning aligns vision and language representations "
                "in a shared embedding space enabling zero shot transfer",
        "category": "multimodal",
        "year": 2021,
        "citations": 18000,
    }),
    (10, {
        "title": "neural architecture search automation",
        "body": "automated methods discover neural network architectures that match "
                "or exceed human designed models using search and optimization",
        "category": "automl",
        "year": 2019,
        "citations": 7000,
    }),
]

for doc_id, doc in articles:
    engine.add_document(doc_id, doc)

print("=" * 70)
print("Full-Text Search Examples (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. Basic term search
# ------------------------------------------------------------------
print("\n--- 1. Term search: 'attention' ---")
results = engine.query().term("attention").execute()
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']}")
print(f"  -> {len(results)} documents found")


# ------------------------------------------------------------------
# 2. BM25 scored search
# ------------------------------------------------------------------
print("\n--- 2. BM25 scored: 'transformer attention' ---")
q = engine.query().term("transformer").or_(engine.query().term("attention"))
results = q.score_bm25("transformer attention").execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] score={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 3. Bayesian BM25 (calibrated probability)
# ------------------------------------------------------------------
print("\n--- 3. Bayesian BM25: 'language model' ---")
q = engine.query().term("language").or_(engine.query().term("model"))
results = q.score_bayesian_bm25("language model").execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] P(rel)={entry.payload.score:.4f}  {doc['title']}")


# ------------------------------------------------------------------
# 4. Boolean AND: documents mentioning both 'attention' and 'graph'
# ------------------------------------------------------------------
print("\n--- 4. Boolean AND: 'attention' AND 'graph' ---")
results = (
    engine.query().term("attention")
    .and_(engine.query().term("graph"))
    .execute()
)
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']}")


# ------------------------------------------------------------------
# 5. Boolean OR: 'diffusion' OR 'generative'
# ------------------------------------------------------------------
print("\n--- 5. Boolean OR: 'diffusion' OR 'generative' ---")
results = (
    engine.query().term("diffusion")
    .or_(engine.query().term("generative"))
    .execute()
)
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']}")


# ------------------------------------------------------------------
# 6. Boolean NOT: 'attention' but NOT 'graph'
# ------------------------------------------------------------------
print("\n--- 6. Boolean NOT: 'attention' NOT 'graph' ---")
attention = engine.query().term("attention")
not_graph = engine.query().term("graph").not_()
results = attention.and_(not_graph).execute()
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']}")


# ------------------------------------------------------------------
# 7. Filter: category = 'nlp'
# ------------------------------------------------------------------
print("\n--- 7. Filter: category = 'nlp' ---")
results = engine.query().filter("category", Equals("nlp")).execute()
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']})")


# ------------------------------------------------------------------
# 8. Text + filter: 'attention' in NLP papers only
# ------------------------------------------------------------------
print("\n--- 8. Text + filter: 'attention' AND category='nlp' ---")
results = (
    engine.query().term("attention")
    .filter("category", Equals("nlp"))
    .execute()
)
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']}")


# ------------------------------------------------------------------
# 9. Range filter: year BETWEEN 2020 AND 2022
# ------------------------------------------------------------------
print("\n--- 9. Range filter: year BETWEEN 2020 AND 2022 ---")
results = engine.query().filter("year", Between(2020, 2022)).execute()
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']})")


# ------------------------------------------------------------------
# 10. Multi-value filter: category IN ('cv', 'multimodal')
# ------------------------------------------------------------------
print("\n--- 10. Multi-value: category IN ('cv', 'multimodal') ---")
results = (
    engine.query()
    .filter("category", InSet(frozenset(["cv", "multimodal"])))
    .execute()
)
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']} [{doc['category']}]")


# ------------------------------------------------------------------
# 11. Chained filters: nlp + recent + high citation
# ------------------------------------------------------------------
print("\n--- 11. Chained: category='nlp' AND year>=2019 AND citations>=8000 ---")
results = (
    engine.query()
    .filter("category", Equals("nlp"))
    .filter("year", GreaterThanOrEqual(2019))
    .filter("citations", GreaterThanOrEqual(8000))
    .execute()
)
for entry in results:
    doc = engine.document_store.get(entry.doc_id)
    print(f"  [{entry.doc_id}] {doc['title']} ({doc['year']}, {doc['citations']:,} cit)")


# ------------------------------------------------------------------
# 12. Faceted search: distribution by category
# ------------------------------------------------------------------
print("\n--- 12. Faceted search: category distribution ---")
facets = engine.query().filter("year", GreaterThanOrEqual(2020)).facet("category")
for category, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
    print(f"  {category:>12}: {count}")


# ------------------------------------------------------------------
# 13. Aggregation: citation statistics for NLP papers
# ------------------------------------------------------------------
print("\n--- 13. Aggregation: NLP citation statistics ---")
nlp_query = engine.query().filter("category", Equals("nlp"))
for fn in ("count", "sum", "avg", "min", "max"):
    result = nlp_query.aggregate("citations", fn)
    if isinstance(result.value, float):
        print(f"  {fn:>5}: {result.value:,.1f}")
    else:
        print(f"  {fn:>5}: {result.value:,}")


# ------------------------------------------------------------------
# 14. Query plan explanation
# ------------------------------------------------------------------
print("\n--- 14. EXPLAIN: 'transformer' scored search ---")
q = engine.query().term("transformer")
plan = q.score_bm25("transformer").explain()
print(f"  {plan}")


print("\n" + "=" * 70)
print("All text search examples completed successfully.")
print("=" * 70)
