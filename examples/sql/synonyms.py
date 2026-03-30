#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Synonym search examples using dual (index/search) analyzers.

Demonstrates:
  - Index-time synonym expansion: indexing "car" creates postings for
    "car" AND "automobile", so searching either term finds the document.
  - Search-time synonym expansion: searching "automobile" expands to
    "automobile OR car" at query time without re-indexing.
  - Separate index/search analyzers per field (Elasticsearch pattern).
  - SQL set_table_analyzer() with phase parameter.
  - File-based synonyms (Solr/Elasticsearch format).
  - Catalog persistence of field-to-analyzer mappings.
"""

import os
import tempfile

from uqa.engine import Engine


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    cols = [c for c in result.columns if c not in ("_doc_id", "_score")]
    if not cols:
        cols = result.columns
    header = "  " + " | ".join(f"{c:<25}" for c in cols)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = [str(row.get(c, ""))[:25].ljust(25) for c in cols]
        print("  " + " | ".join(vals))


engine = Engine()

print("=" * 70)
print("Synonym Search Examples")
print("=" * 70)


# ==================================================================
# 1. Setup: product catalog
# ==================================================================
print("\n--- 1. Setup ---")

engine.sql("""
    CREATE TABLE products (
        id   INT PRIMARY KEY,
        name TEXT,
        body TEXT
    )
""")

engine.sql("CREATE INDEX idx_products_gin ON products USING gin (body)")

engine.sql("""
    INSERT INTO products (id, name, body) VALUES
        (1, 'Sedan',    'A comfortable car for daily commuting'),
        (2, 'SUV',      'A spacious vehicle for family trips'),
        (3, 'Roadster', 'A fast automobile with sporty handling'),
        (4, 'Minivan',  'A large van for big families'),
        (5, 'Coupe',    'A sleek auto with two doors'),
        (6, 'Truck',    'A heavy-duty pickup for hauling cargo')
""")
print("  Inserted 6 products.")


# ==================================================================
# 2. Without synonyms: exact term match only
# ==================================================================
print("\n--- 2. Without synonyms: text_match('car') ---")

result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'car')
    ORDER BY _score DESC
""")
show("Exact match for 'car'", result)
print("  -> Only finds 'car', misses 'vehicle', 'automobile', 'auto'")


# ==================================================================
# 3. Create analyzers: one for indexing, one for searching
# ==================================================================
print("\n--- 3. Create dual analyzers ---")

# Index analyzer: standard tokenization + lowercasing (no synonyms)
engine.sql("""
    SELECT * FROM create_analyzer('product_index', '{
        "tokenizer": {"type": "standard"},
        "token_filters": [{"type": "lowercase"}]
    }')
""")
print("  Created 'product_index' (index-time, no synonyms)")

# Search analyzer: standard tokenization + lowercasing + synonyms
engine.sql("""
    SELECT * FROM create_analyzer('product_search', '{
        "tokenizer": {"type": "standard"},
        "token_filters": [
            {"type": "lowercase"},
            {"type": "synonym", "synonyms": {
                "car": ["automobile", "vehicle", "auto"],
                "fast": ["quick", "speedy"],
                "big": ["large", "spacious"]
            }}
        ]
    }')
""")
print("  Created 'product_search' (search-time, with synonyms)")


# ==================================================================
# 4. Assign analyzers to the 'body' field with separate phases
# ==================================================================
print("\n--- 4. Assign analyzers to products.body ---")

result = engine.sql("""
    SELECT * FROM set_table_analyzer('products', 'body', 'product_index', 'index')
""")
print(f"  {result.rows[0]['set_table_analyzer']}")

result = engine.sql("""
    SELECT * FROM set_table_analyzer('products', 'body', 'product_search', 'search')
""")
print(f"  {result.rows[0]['set_table_analyzer']}")


# ==================================================================
# 5. Re-index documents with the index analyzer
# ==================================================================
print("\n--- 5. Re-index with index analyzer ---")

# Drop and recreate with index analyzer active
engine.sql("DROP TABLE products")
engine.sql("""
    CREATE TABLE products (
        id   INT PRIMARY KEY,
        name TEXT,
        body TEXT
    )
""")
engine.sql("CREATE INDEX idx_products_gin ON products USING gin (body)")
# Re-assign analyzers
engine.set_table_analyzer("products", "body", "product_index", phase="index")
engine.set_table_analyzer("products", "body", "product_search", phase="search")

engine.sql("""
    INSERT INTO products (id, name, body) VALUES
        (1, 'Sedan',    'A comfortable car for daily commuting'),
        (2, 'SUV',      'A spacious vehicle for family trips'),
        (3, 'Roadster', 'A fast automobile with sporty handling'),
        (4, 'Minivan',  'A large van for big families'),
        (5, 'Coupe',    'A sleek auto with two doors'),
        (6, 'Truck',    'A heavy-duty pickup for hauling cargo')
""")
print("  Re-indexed 6 products with 'product_index' analyzer.")


# ==================================================================
# 6. Search-time synonym expansion
# ==================================================================
print("\n--- 6. Search-time synonym expansion ---")

# "car" expands to "car OR automobile OR vehicle OR auto" at search time
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'car')
    ORDER BY _score DESC
""")
show("text_match('car') with synonyms", result)
print("  -> Now finds 'car', 'vehicle', 'automobile', AND 'auto'!")

# "fast" expands to "fast OR quick OR speedy"
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'fast')
    ORDER BY _score DESC
""")
show("text_match('fast') with synonyms", result)

# "big" expands to "big OR large OR spacious"
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'big')
    ORDER BY _score DESC
""")
show("text_match('big') with synonyms", result)


# ==================================================================
# 7. Multi-term query with synonyms
# ==================================================================
print("\n--- 7. Multi-term query ---")

result = engine.sql("""
    SELECT name, body, _score FROM products
    WHERE text_match(body, 'fast car')
    ORDER BY _score DESC
""")
show("text_match('fast car') with synonyms", result)
print(
    "  -> Expands to (fast OR quick OR speedy) UNION (car OR automobile OR vehicle OR auto)"
)


# ==================================================================
# 8. BM25 scored search with synonyms
# ==================================================================
print("\n--- 8. Bayesian BM25 scored ---")

result = engine.sql("""
    SELECT name, _score AS relevance FROM products
    WHERE bayesian_match(body, 'automobile')
    ORDER BY relevance DESC
""")
show("bayesian_match('automobile')", result)


# ==================================================================
# 9. Hybrid: synonym text search + filter
# ==================================================================
print("\n--- 9. Synonym search + filter ---")

result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'car') AND id <= 3
    ORDER BY _score DESC
""")
show("text_match('car') AND id <= 3", result)


# ==================================================================
# 10. Verify index analyzer is unaffected (no synonyms in index)
# ==================================================================
print("\n--- 10. Verify: index analyzer has no synonyms ---")

idx_analyzer = engine.get_table_analyzer("products", "body", phase="index")
search_analyzer = engine.get_table_analyzer("products", "body", phase="search")

print(f"  Index analyzer tokens for 'car':  {idx_analyzer.analyze('car')}")
print(f"  Search analyzer tokens for 'car': {search_analyzer.analyze('car')}")
print(
    "  -> Index produces ['car'], search produces ['car', 'automobile', 'vehicle', 'auto']"
)


# ==================================================================
# 11. Index-time synonym expansion (alternative strategy)
# ==================================================================
print("\n--- 11. Index-time synonym expansion ---")

engine.sql("""
    SELECT * FROM create_analyzer('idx_with_syn', '{
        "tokenizer": {"type": "standard"},
        "token_filters": [
            {"type": "lowercase"},
            {"type": "synonym", "synonyms": {
                "car": ["automobile", "vehicle"]
            }}
        ]
    }')
""")

engine.sql("DROP TABLE products")
engine.sql("""
    CREATE TABLE products (
        id   INT PRIMARY KEY,
        name TEXT,
        body TEXT
    )
""")
engine.sql("CREATE INDEX idx_products_gin ON products USING gin (body)")
engine.set_table_analyzer("products", "body", "idx_with_syn", phase="index")
# No search-time synonyms needed: all variants are already in the index

engine.sql("""
    INSERT INTO products (id, name, body) VALUES
        (1, 'Sedan',    'A comfortable car for daily commuting'),
        (2, 'SUV',      'A spacious vehicle for family trips'),
        (3, 'Roadster', 'A fast automobile with sporty handling'),
        (4, 'Minivan',  'A large van for big families'),
        (5, 'Coupe',    'A sleek auto with two doors'),
        (6, 'Truck',    'A heavy-duty pickup for hauling cargo')
""")
print("  Re-indexed with index-time synonyms.")

# Now a simple search for "automobile" finds documents that contained "car"
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'automobile')
    ORDER BY _score DESC
""")
show("text_match('automobile') with index-time expansion", result)
print(
    "  -> 'car' was expanded to 'automobile' at index time, so 'automobile' matches it"
)


# ==================================================================
# 12. File-based synonyms
# ==================================================================
print("\n--- 12. File-based synonyms ---")

# Create a Solr/Elasticsearch-format synonym file
syn_file = os.path.join(tempfile.mkdtemp(), "synonyms.txt")
with open(syn_file, "w") as f:
    f.write("# Vehicle synonyms (bidirectional)\n")
    f.write("car, automobile, vehicle, auto\n")
    f.write("\n")
    f.write("# Speed synonyms (explicit, one-directional)\n")
    f.write("fast => quick, speedy, rapid\n")
    f.write("big => large, spacious\n")
print(f"  Created synonym file: {syn_file}")

import json

config = json.dumps(
    {
        "tokenizer": {"type": "standard"},
        "token_filters": [
            {"type": "lowercase"},
            {"type": "synonym", "synonyms_path": syn_file},
        ],
    }
)

engine.sql(f"SELECT * FROM create_analyzer('file_search', '{config}')")
print("  Created 'file_search' analyzer from synonym file")

# Plain index analyzer (no stemming) to match the search analyzer's tokenization
engine.sql("""
    SELECT * FROM create_analyzer('file_index', '{
        "tokenizer": {"type": "standard"},
        "token_filters": [{"type": "lowercase"}]
    }')
""")
print("  Created 'file_index' analyzer (plain, no stemming)")

engine.sql("DROP TABLE products")
engine.sql("""
    CREATE TABLE products (
        id   INT PRIMARY KEY,
        name TEXT,
        body TEXT
    )
""")
engine.sql("CREATE INDEX idx_products_gin ON products USING gin (body)")
engine.set_table_analyzer("products", "body", "file_index", phase="index")
engine.set_table_analyzer("products", "body", "file_search", phase="search")

engine.sql("""
    INSERT INTO products (id, name, body) VALUES
        (1, 'Sedan',    'A comfortable car for daily commuting'),
        (2, 'SUV',      'A spacious vehicle for family trips'),
        (3, 'Roadster', 'A fast automobile with sporty handling'),
        (4, 'Coupe',    'A sleek auto with two doors')
""")
print("  Indexed 4 products.")

# Bidirectional: "automobile" expands to all variants
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'automobile')
    ORDER BY _score DESC
""")
show("text_match('automobile') with file-based synonyms", result)
print("  -> Equivalent synonyms: 'automobile' finds car, vehicle, auto too")

# Explicit: "fast" expands to quick, speedy, rapid
result = engine.sql("""
    SELECT name, body FROM products
    WHERE text_match(body, 'big')
    ORDER BY _score DESC
""")
show("text_match('big') with file-based synonyms", result)
print("  -> Explicit mapping: 'big' expands to large, spacious")


# ==================================================================
# 13. Catalog persistence
# ==================================================================
print("\n--- 13. Catalog persistence ---")

db_path = os.path.join(tempfile.mkdtemp(), "synonyms.db")

with Engine(db_path=db_path) as e1:
    e1.sql("""
        SELECT * FROM create_analyzer('persist_search', '{
            "tokenizer": {"type": "standard"},
            "token_filters": [
                {"type": "lowercase"},
                {"type": "synonym", "synonyms": {"car": ["auto"]}}
            ]
        }')
    """)
    e1.sql("CREATE TABLE items (id INT, desc_ TEXT)")
    e1.set_table_analyzer("items", "desc_", "persist_search", phase="search")
    e1.sql("INSERT INTO items (id, desc_) VALUES (1, 'buy a new auto today')")
    print("  Session 1: created analyzer, table, and assigned search analyzer.")

with Engine(db_path=db_path) as e2:
    # Verify analyzer binding survived restart
    a = e2.get_table_analyzer("items", "desc_", phase="search")
    tokens = a.analyze("car")
    print(f"  Session 2: search analyzer for 'car' -> {tokens}")
    assert "auto" in tokens
    print("  Persistence verified!")

# Clean up
from uqa.analysis.analyzer import drop_analyzer

for name in [
    "product_index",
    "product_search",
    "idx_with_syn",
    "file_index",
    "file_search",
    "persist_search",
]:
    try:
        drop_analyzer(name)
    except ValueError:
        pass

print()
print("=" * 70)
print("All synonym search examples completed successfully.")
print("=" * 70)
