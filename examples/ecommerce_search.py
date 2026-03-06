"""Example 2: E-Commerce Product Search
========================================

A product search engine demonstrating:
- Text search with BM25 relevance scoring
- Structured field filtering (price, category, rating)
- Faceted navigation (brand, category counts)
- Aggregation (average price, min/max rating)
- Boolean queries (include/exclude categories)
- Hierarchical data (nested product specs)

Scenario: An online electronics store where users search for products
with keyword queries, apply filters, and explore facets.
"""

from __future__ import annotations

import numpy as np

from uqa.engine import Engine
from uqa.core.types import (
    Between,
    Edge,
    Equals,
    GreaterThan,
    GreaterThanOrEqual,
    InSet,
    LessThanOrEqual,
    Vertex,
)


def build_product_database() -> Engine:
    """Build an e-commerce product database."""
    engine = Engine(vector_dimensions=16, max_elements=1000)
    rng = np.random.RandomState(42)

    products = [
        {
            "doc_id": 1,
            "name": "wireless noise cancelling headphones premium edition",
            "description": "over ear wireless headphones with active noise cancelling "
                           "bluetooth connectivity 30 hour battery life premium sound quality",
            "category": "audio",
            "brand": "SoundMax",
            "price": 299.99,
            "rating": 4.7,
            "in_stock": True,
        },
        {
            "doc_id": 2,
            "name": "budget wireless earbuds with microphone",
            "description": "compact wireless earbuds with built-in microphone for calls "
                           "bluetooth true wireless design 8 hour battery life",
            "category": "audio",
            "brand": "ValueTech",
            "price": 39.99,
            "rating": 4.1,
            "in_stock": True,
        },
        {
            "doc_id": 3,
            "name": "professional studio monitor headphones",
            "description": "wired studio headphones for professional audio monitoring "
                           "flat frequency response 50mm drivers detachable cable",
            "category": "audio",
            "brand": "ProAudio",
            "price": 179.99,
            "rating": 4.8,
            "in_stock": True,
        },
        {
            "doc_id": 4,
            "name": "ultra slim laptop 14 inch display",
            "description": "lightweight ultra slim laptop with 14 inch ips display "
                           "16gb ram 512gb ssd fast processor for productivity",
            "category": "computers",
            "brand": "TechBook",
            "price": 899.99,
            "rating": 4.5,
            "in_stock": True,
        },
        {
            "doc_id": 5,
            "name": "gaming laptop high performance 16 inch",
            "description": "gaming laptop with dedicated graphics card 16 inch display "
                           "32gb ram 1tb ssd rgb keyboard advanced cooling system",
            "category": "computers",
            "brand": "GameForce",
            "price": 1499.99,
            "rating": 4.6,
            "in_stock": False,
        },
        {
            "doc_id": 6,
            "name": "wireless mechanical keyboard compact",
            "description": "compact 75 percent wireless mechanical keyboard with "
                           "hot-swappable switches bluetooth and usb-c connectivity "
                           "rgb backlighting programmable keys",
            "category": "peripherals",
            "brand": "KeyCraft",
            "price": 89.99,
            "rating": 4.4,
            "in_stock": True,
        },
        {
            "doc_id": 7,
            "name": "ergonomic wireless mouse vertical design",
            "description": "ergonomic vertical wireless mouse designed to reduce wrist "
                           "strain adjustable dpi bluetooth and usb receiver",
            "category": "peripherals",
            "brand": "ErgoTech",
            "price": 49.99,
            "rating": 4.3,
            "in_stock": True,
        },
        {
            "doc_id": 8,
            "name": "4k ultra hd monitor 27 inch",
            "description": "professional 27 inch 4k uhd ips monitor with wide color gamut "
                           "usb-c connectivity 60hz refresh rate adjustable stand",
            "category": "monitors",
            "brand": "ViewPro",
            "price": 449.99,
            "rating": 4.6,
            "in_stock": True,
        },
        {
            "doc_id": 9,
            "name": "portable bluetooth speaker waterproof",
            "description": "portable wireless bluetooth speaker with waterproof design "
                           "360 degree sound 12 hour battery life compact for travel",
            "category": "audio",
            "brand": "SoundMax",
            "price": 69.99,
            "rating": 4.2,
            "in_stock": True,
        },
        {
            "doc_id": 10,
            "name": "usb-c docking station multi-port hub",
            "description": "usb-c docking station with hdmi displayport ethernet usb-a "
                           "ports sd card reader 100w power delivery for laptops",
            "category": "accessories",
            "brand": "TechBook",
            "price": 129.99,
            "rating": 4.0,
            "in_stock": True,
        },
        {
            "doc_id": 11,
            "name": "noise cancelling wireless earbuds premium",
            "description": "premium true wireless earbuds with hybrid active noise "
                           "cancelling transparency mode spatial audio 24 hour battery "
                           "with charging case wireless charging",
            "category": "audio",
            "brand": "SoundMax",
            "price": 249.99,
            "rating": 4.5,
            "in_stock": True,
        },
        {
            "doc_id": 12,
            "name": "curved gaming monitor 32 inch 165hz",
            "description": "curved 32 inch gaming monitor 2k resolution 165hz refresh "
                           "rate 1ms response time hdr support freesync compatible",
            "category": "monitors",
            "brand": "GameForce",
            "price": 379.99,
            "rating": 4.7,
            "in_stock": True,
        },
    ]

    for product in products:
        doc_id = product.pop("doc_id")
        embedding = rng.randn(16).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
        engine.add_document(doc_id, product, embedding)

    return engine


def main() -> None:
    engine = build_product_database()

    print("=" * 70)
    print("UQA E-Commerce Product Search -- Realistic Examples")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Query 1: Basic product search
    # ------------------------------------------------------------------
    print("\n--- Query 1: Search for 'wireless headphones' ---")
    results = (
        engine.query()
        .term("wireless")
        .score_bm25("wireless headphones")
        .execute()
    )
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: -e.payload.score)[:5]:
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']}")
        print(f"           BM25 score: {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 2: Search + price filter
    # ------------------------------------------------------------------
    print("\n--- Query 2: 'wireless' products under $100 ---")
    results = (
        engine.query()
        .term("wireless")
        .filter("price", LessThanOrEqual(100.0))
        .execute()
    )
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']}")

    # ------------------------------------------------------------------
    # Query 3: Multi-filter -- category + price range + in stock
    # ------------------------------------------------------------------
    print("\n--- Query 3: Audio products, $50-$300, in stock ---")
    results = (
        engine.query()
        .filter("category", Equals("audio"))
        .filter("price", Between(50.0, 300.0))
        .filter("in_stock", Equals(True))
        .execute()
    )
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']} (rating: {doc['rating']})")

    # ------------------------------------------------------------------
    # Query 4: Boolean search -- (noise cancelling) but NOT (earbuds)
    # ------------------------------------------------------------------
    print("\n--- Query 4: 'noise' AND 'cancelling' but NOT 'earbuds' ---")
    q_noise = engine.query().term("noise")
    q_cancel = engine.query().term("cancelling")
    q_earbuds = engine.query().term("earbuds")

    results = q_noise.and_(q_cancel).and_(q_earbuds.not_()).execute()
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']}")

    # ------------------------------------------------------------------
    # Query 5: Faceted search -- category distribution
    # ------------------------------------------------------------------
    print("\n--- Query 5: Faceted search for 'wireless' by category ---")
    facets = (
        engine.query()
        .term("wireless")
        .facet("category")
    )
    print("Category distribution:")
    for cat, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # ------------------------------------------------------------------
    # Query 6: Faceted search -- brand distribution
    # ------------------------------------------------------------------
    print("\n--- Query 6: Brand distribution for 'wireless' ---")
    facets = (
        engine.query()
        .term("wireless")
        .facet("brand")
    )
    print("Brand distribution:")
    for brand, count in sorted(facets.counts.items(), key=lambda x: -x[1]):
        print(f"  {brand}: {count}")

    # ------------------------------------------------------------------
    # Query 7: Aggregation -- price statistics for audio products
    # ------------------------------------------------------------------
    print("\n--- Query 7: Price statistics for audio products ---")
    audio_query = engine.query().filter("category", Equals("audio"))

    avg_price = audio_query.aggregate("price", "avg")
    min_price = audio_query.aggregate("price", "min")
    max_price = audio_query.aggregate("price", "max")
    count = audio_query.aggregate("price", "count")

    print(f"  Audio products: {count.value}")
    print(f"  Average price:  ${avg_price.value:.2f}")
    print(f"  Min price:      ${min_price.value:.2f}")
    print(f"  Max price:      ${max_price.value:.2f}")

    # ------------------------------------------------------------------
    # Query 8: Highly rated OR cheap wireless products
    # ------------------------------------------------------------------
    print("\n--- Query 8: Wireless AND (rating >= 4.5 OR price < 50) ---")
    q_wireless = engine.query().term("wireless")
    q_high_rated = engine.query().filter("rating", GreaterThanOrEqual(4.5))
    q_cheap = engine.query().filter("price", LessThanOrEqual(50.0))

    results = q_wireless.and_(q_high_rated.or_(q_cheap)).execute()
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']} (rating: {doc['rating']})")

    # ------------------------------------------------------------------
    # Query 9: Search by multiple categories
    # ------------------------------------------------------------------
    print("\n--- Query 9: Products in 'audio' OR 'peripherals' with rating > 4.3 ---")
    results = (
        engine.query()
        .filter("category", InSet(frozenset({"audio", "peripherals"})))
        .filter("rating", GreaterThan(4.3))
        .execute()
    )
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: e.doc_id):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  [{doc['category']}] {doc['name']} (rating: {doc['rating']})")

    # ------------------------------------------------------------------
    # Query 10: Bayesian BM25 + filter pipeline
    # ------------------------------------------------------------------
    print("\n--- Query 10: 'bluetooth' search with Bayesian scoring, in stock ---")
    results = (
        engine.query()
        .term("bluetooth")
        .score_bayesian_bm25("bluetooth wireless audio")
        .filter("in_stock", Equals(True))
        .execute()
    )
    print(f"Found {len(results)} products:")
    for entry in sorted(results, key=lambda e: -e.payload.score):
        doc = engine.document_store.get(entry.doc_id)
        print(f"  ${doc['price']:>7.2f}  {doc['name']}")
        print(f"           P(relevant) = {entry.payload.score:.4f}")

    # ------------------------------------------------------------------
    # Query 11: Explain a complex query plan
    # ------------------------------------------------------------------
    print("\n--- Query 11: Query plan for 'wireless noise cancelling' ---")
    q1 = engine.query().term("wireless", field="description")
    q2 = engine.query().term("noise", field="description")
    plan = (
        q1.and_(q2)
        .filter("price", LessThanOrEqual(300.0))
        .explain()
    )
    print(plan)

    print("\n" + "=" * 70)
    print("All examples completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
