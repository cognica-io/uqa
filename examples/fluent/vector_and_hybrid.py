#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Vector search and hybrid retrieval examples using the fluent QueryBuilder API.

Demonstrates:
  - KNN vector similarity search
  - Threshold-based vector search
  - Hybrid text + vector search
  - Vector exclusion (negative query vector)
  - Vector-conditioned facets
  - Semantic filter
  - Log-odds and probabilistic fusion
"""

import numpy as np

from uqa.core.types import Equals, GreaterThanOrEqual, LessThanOrEqual
from uqa.engine import Engine

# ======================================================================
# Data setup: 10 products with descriptions and embeddings
# ======================================================================

engine = Engine()

engine.sql("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        brand TEXT,
        price REAL,
        rating REAL,
        embedding VECTOR(8)
    )
""")

rng = np.random.RandomState(42)

products = [
    (1, {"name": "wireless noise cancelling headphones", "category": "audio",
         "brand": "SoundMax", "price": 299.99, "rating": 4.7}),
    (2, {"name": "bluetooth portable speaker waterproof", "category": "audio",
         "brand": "SoundMax", "price": 89.99, "rating": 4.3}),
    (3, {"name": "mechanical gaming keyboard rgb backlit", "category": "peripherals",
         "brand": "KeyTech", "price": 149.99, "rating": 4.5}),
    (4, {"name": "ergonomic wireless mouse silent click", "category": "peripherals",
         "brand": "KeyTech", "price": 49.99, "rating": 4.2}),
    (5, {"name": "ultrawide curved monitor 34 inch", "category": "displays",
         "brand": "ViewPro", "price": 599.99, "rating": 4.8}),
    (6, {"name": "portable external ssd 1tb usb c", "category": "storage",
         "brand": "DataFast", "price": 119.99, "rating": 4.6}),
    (7, {"name": "webcam 4k autofocus with microphone", "category": "peripherals",
         "brand": "ClearView", "price": 79.99, "rating": 4.1}),
    (8, {"name": "usb c docking station dual monitor", "category": "accessories",
         "brand": "HubMax", "price": 189.99, "rating": 4.4}),
    (9, {"name": "wireless earbuds active noise cancellation", "category": "audio",
         "brand": "SoundMax", "price": 199.99, "rating": 4.6}),
    (10, {"name": "gaming monitor 27 inch 144hz", "category": "displays",
          "brand": "ViewPro", "price": 449.99, "rating": 4.5}),
]

# Create embeddings: audio products clustered together, etc.
category_centers = {
    "audio": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0]),
    "peripherals": np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "displays": np.array([0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.5, 0.0]),
    "storage": np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.5]),
    "accessories": np.array([0.3, 0.3, 0.3, 0.3, 0.0, 0.0, 0.0, 0.0]),
}

for doc_id, doc in products:
    center = category_centers[doc["category"]]
    embedding = center + rng.randn(8) * 0.1
    embedding = embedding / np.linalg.norm(embedding)
    engine.add_document(doc_id, doc, table="products", embedding=embedding)

print("=" * 70)
print("Vector Search & Hybrid Retrieval Examples (Fluent API)")
print("=" * 70)


# ------------------------------------------------------------------
# 1. KNN search: find 3 products most similar to "audio" query
# ------------------------------------------------------------------
print("\n--- 1. KNN search: 3 nearest to audio query ---")
audio_query = category_centers["audio"] + rng.randn(8) * 0.05
audio_query = audio_query / np.linalg.norm(audio_query)

results = engine.query(table="products").knn(audio_query, k=3).execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] sim={entry.payload.score:.4f}  {doc['name']}")


# ------------------------------------------------------------------
# 2. Threshold-based vector search
# ------------------------------------------------------------------
print("\n--- 2. Threshold vector search: similarity > 0.5 ---")
results = engine.query(table="products").vector(audio_query, threshold=0.5).execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] sim={entry.payload.score:.4f}  {doc['name']}")


# ------------------------------------------------------------------
# 3. KNN + filter: top 5 under $200
# ------------------------------------------------------------------
print("\n--- 3. KNN + filter: top 5, price <= $200 ---")
results = (
    engine.query(table="products")
    .knn(audio_query, k=5)
    .filter("price", LessThanOrEqual(200.0))
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] sim={entry.payload.score:.4f}  "
          f"${doc['price']:.2f}  {doc['name']}")


# ------------------------------------------------------------------
# 4. Hybrid text + vector: 'wireless' AND similar to audio
# ------------------------------------------------------------------
print("\n--- 4. Hybrid: term 'wireless' AND KNN(audio, k=5) ---")
text_q = engine.query(table="products").term("wireless")
vec_q = engine.query(table="products").knn(audio_query, k=5)
results = text_q.and_(vec_q).execute()
for entry in results:
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] {doc['name']} [${doc['price']:.2f}]")


# ------------------------------------------------------------------
# 5. Vector exclusion: find audio-like but NOT peripherals-like
# ------------------------------------------------------------------
print("\n--- 5. Vector exclusion: audio-like, excluding peripherals ---")
peripherals_query = category_centers["peripherals"]
peripherals_query = peripherals_query / np.linalg.norm(peripherals_query)

results = (
    engine.query(table="products")
    .knn(audio_query, k=5)
    .vector_exclude(peripherals_query, threshold=0.3)
    .execute()
)
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] sim={entry.payload.score:.4f}  "
          f"{doc['name']} [{doc['category']}]")


# ------------------------------------------------------------------
# 6. Vector-conditioned facets: category distribution near audio
# ------------------------------------------------------------------
print("\n--- 6. Vector facets: categories among audio-similar docs ---")
facets = engine.query(table="products").vector_facet("category", audio_query, threshold=0.3)
for cat, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
    print(f"  {cat:>15}: {count}")


# ------------------------------------------------------------------
# 7. Log-odds fusion: text relevance + vector similarity
# ------------------------------------------------------------------
print("\n--- 7. Log-odds fusion: 'monitor' text + display vector ---")
display_query = category_centers["displays"] + rng.randn(8) * 0.05
display_query = display_query / np.linalg.norm(display_query)

text_signal = engine.query(table="products").term("monitor").score_bayesian_bm25("monitor")
vec_signal = engine.query(table="products").knn(display_query, k=5)

fused = engine.query(table="products").fuse_log_odds(text_signal, vec_signal, alpha=0.6)
results = fused.execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] fused={entry.payload.score:.4f}  {doc['name']}")


# ------------------------------------------------------------------
# 8. Probabilistic AND: high confidence matches
# ------------------------------------------------------------------
print("\n--- 8. Prob AND: 'wireless' text AND audio vector ---")
text_signal = engine.query(table="products").term("wireless").score_bayesian_bm25("wireless")
vec_signal = engine.query(table="products").vector(audio_query, threshold=0.3)

results = engine.query(table="products").fuse_prob_and(text_signal, vec_signal).execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True):
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] P(and)={entry.payload.score:.4f}  {doc['name']}")


# ------------------------------------------------------------------
# 9. Probabilistic OR: broader recall
# ------------------------------------------------------------------
print("\n--- 9. Prob OR: 'gaming' text OR peripherals vector ---")
text_signal = engine.query(table="products").term("gaming").score_bayesian_bm25("gaming")
vec_signal = engine.query(table="products").vector(peripherals_query, threshold=0.3)

results = engine.query(table="products").fuse_prob_or(text_signal, vec_signal).execute()
for entry in sorted(results, key=lambda e: e.payload.score, reverse=True)[:5]:
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] P(or)={entry.payload.score:.4f}  {doc['name']}")


# ------------------------------------------------------------------
# 10. Multi-signal fusion: text + vector + filter pipeline
# ------------------------------------------------------------------
print("\n--- 10. Pipeline: fusion -> filter(rating >= 4.5) ---")
text_signal = engine.query(table="products").term("monitor").score_bayesian_bm25("monitor")
vec_signal = engine.query(table="products").knn(display_query, k=5)

results = (
    engine.query(table="products")
    .fuse_log_odds(text_signal, vec_signal)
    .filter("rating", GreaterThanOrEqual(4.5))
    .execute()
)
for entry in results:
    doc = engine.get_document(entry.doc_id, table="products")
    print(f"  [{entry.doc_id}] {doc['name']} (rating: {doc['rating']})")


# ------------------------------------------------------------------
# 11. Aggregation over vector search results
# ------------------------------------------------------------------
print("\n--- 11. Aggregation: avg price of audio-similar products ---")
vec_results = engine.query(table="products").knn(audio_query, k=5)
avg_price = vec_results.aggregate("price", "avg")
print(f"  Average price: ${avg_price.value:.2f}")

min_price = vec_results.aggregate("price", "min")
max_price = vec_results.aggregate("price", "max")
print(f"  Price range: ${min_price.value:.2f} - ${max_price.value:.2f}")


print("\n" + "=" * 70)
print("All vector/hybrid search examples completed successfully.")
print("=" * 70)
