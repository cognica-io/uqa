#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Text analysis pipeline examples using SQL table functions.

Demonstrates:
  - create_analyzer(): define custom analyzers via SQL
  - drop_analyzer(): remove custom analyzers
  - list_analyzers(): enumerate available analyzers
  - Full-text search with custom analyzers
  - Analyzer persistence with db_path
"""

import json
import os
import tempfile

from uqa.engine import Engine


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    # Filter out internal posting-list columns
    cols = [c for c in result.columns if c not in ("_doc_id", "_score")]
    if not cols:
        cols = result.columns
    header = "  " + " | ".join(f"{c:<30}" for c in cols)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = [str(row.get(c, ""))[:30].ljust(30) for c in cols]
        print("  " + " | ".join(vals))


engine = Engine()

print("=" * 70)
print("Text Analysis SQL Examples")
print("=" * 70)


# ==================================================================
# 1. List built-in analyzers
# ==================================================================
show("1. list_analyzers()", engine.sql("SELECT * FROM list_analyzers()"))


# ==================================================================
# 2. Create a custom analyzer via SQL
# ==================================================================
print("\n--- 2. create_analyzer() ---")

# Standard tokenizer + lowercase + stop word removal
config = {
    "tokenizer": {"type": "standard"},
    "token_filters": [
        {"type": "lowercase"},
        {"type": "stop", "language": "english"},
    ],
    "char_filters": [],
}

result = engine.sql(
    f"SELECT * FROM create_analyzer('search_analyzer', '{json.dumps(config)}')"
)
print(f"  {result.rows[0]['create_analyzer']}")


# ==================================================================
# 3. Create a stemming analyzer
# ==================================================================
print("\n--- 3. create_analyzer() with stemming ---")

stem_config = {
    "tokenizer": {"type": "standard"},
    "token_filters": [
        {"type": "lowercase"},
        {"type": "stop", "language": "english"},
        {"type": "porter_stem"},
    ],
    "char_filters": [],
}

result = engine.sql(
    f"SELECT * FROM create_analyzer('stem_analyzer', '{json.dumps(stem_config)}')"
)
print(f"  {result.rows[0]['create_analyzer']}")


# ==================================================================
# 4. Create an autocomplete analyzer
# ==================================================================
print("\n--- 4. create_analyzer() for autocomplete ---")

autocomplete_config = {
    "tokenizer": {"type": "standard"},
    "token_filters": [
        {"type": "lowercase"},
        {"type": "edge_ngram", "min_gram": 2, "max_gram": 10},
    ],
    "char_filters": [],
}

result = engine.sql(
    f"SELECT * FROM create_analyzer('autocomplete', '{json.dumps(autocomplete_config)}')"
)
print(f"  {result.rows[0]['create_analyzer']}")


# ==================================================================
# 5. Create an HTML-aware analyzer
# ==================================================================
print("\n--- 5. create_analyzer() for HTML content ---")

html_config = {
    "tokenizer": {"type": "standard"},
    "token_filters": [
        {"type": "lowercase"},
        {"type": "stop", "language": "english"},
    ],
    "char_filters": [
        {"type": "html_strip"},
    ],
}

result = engine.sql(
    f"SELECT * FROM create_analyzer('html_analyzer', '{json.dumps(html_config)}')"
)
print(f"  {result.rows[0]['create_analyzer']}")


# ==================================================================
# 6. Verify all registered analyzers
# ==================================================================
show(
    "6. All analyzers after registration", engine.sql("SELECT * FROM list_analyzers()")
)


# ==================================================================
# 7. Full-text search with default analyzer
# ==================================================================
print("\n--- 7. Full-text search setup ---")

engine.sql("""
    CREATE TABLE articles (
        id SERIAL PRIMARY KEY,
        title TEXT,
        body TEXT,
        category TEXT
    )
""")

engine.sql("CREATE INDEX idx_articles_gin ON articles USING gin (title, body)")

engine.sql("""INSERT INTO articles (title, body, category) VALUES
    ('The Transformer Architecture',
     'The transformer model uses self attention to process sequences without recurrence',
     'nlp'),
    ('Graph Neural Networks',
     'Graph networks apply attention mechanisms to structured data representations',
     'graph'),
    ('Scaling Language Models',
     'Scaling laws show the predictable improvement in language model performance',
     'nlp'),
    ('Computer Vision with Transformers',
     'Vision transformers split images into patches and process them with attention',
     'cv'),
    ('Reinforcement Learning',
     'RLHF trains language models to follow human instructions via reward modeling',
     'alignment')
""")

show(
    "7a. text_search default analyzer",
    engine.sql(
        "SELECT title, _score AS relevance "
        "FROM text_search('transformer attention', 'body', 'articles') "
        "ORDER BY relevance DESC"
    ),
)


# ==================================================================
# 8. Assign custom analyzer to a field
# ==================================================================
print("\n--- 8. Assign analyzer to table field ---")

# Use Python API to assign the stemming analyzer to the 'body' field
from uqa.analysis import get_analyzer

engine.set_table_analyzer("articles", "body", "stem_analyzer")
stem = get_analyzer("stem_analyzer")
print("  Assigned 'stem_analyzer' to articles.body")
print(f"  'stem_analyzer' pipeline: {stem.analyze('transformers are running')}")


# ==================================================================
# 9. Re-index with new analyzer (insert new documents)
# ==================================================================
print("\n--- 9. New documents indexed with stemming ---")

engine.sql("""INSERT INTO articles (title, body, category) VALUES
    ('Transformers in Production',
     'Running transformer models efficiently requires optimized inference',
     'engineering'),
    ('Attention Mechanisms Survey',
     'Various attention mechanisms have been proposed for different applications',
     'survey')
""")

# The new documents are indexed with the stem analyzer.
# Searching for 'run' will match 'running' because both stem to 'run'.
show(
    "9a. Search 'run' (stems to match 'running')",
    engine.sql("SELECT id, title FROM articles WHERE id >= 6 ORDER BY id"),
)


# ==================================================================
# 10. Drop custom analyzers
# ==================================================================
print("\n--- 10. Drop analyzers ---")

for name in ["search_analyzer", "stem_analyzer", "autocomplete", "html_analyzer"]:
    result = engine.sql(f"SELECT * FROM drop_analyzer('{name}')")
    print(f"  {result.rows[0]['drop_analyzer']}")

show("10a. Remaining analyzers", engine.sql("SELECT * FROM list_analyzers()"))


# ==================================================================
# 11. Analyzer persistence (SQLite catalog)
# ==================================================================
print("\n--- 11. Analyzer Persistence ---")

db_path = os.path.join(tempfile.mkdtemp(), "analysis_test.db")

# Session 1: create analyzer and persist
with Engine(db_path=db_path) as e1:
    config = {
        "tokenizer": {"type": "standard"},
        "token_filters": [{"type": "lowercase"}, {"type": "porter_stem"}],
        "char_filters": [],
    }
    e1.create_analyzer("persistent_stemmer", config)
    print("  Session 1: created 'persistent_stemmer'")

    # Create a table and index some data
    e1.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
    e1.sql("CREATE INDEX idx_docs_gin ON docs USING gin (content)")
    e1.sql("INSERT INTO docs (content) VALUES ('The runners are running')")
    print("  Session 1: inserted test document")

# Clean from global registry to prove catalog restore works
from uqa.analysis.analyzer import _custom_analyzers

_custom_analyzers.pop("persistent_stemmer", None)

# Session 2: reopen and verify analyzer was restored
with Engine(db_path=db_path) as e2:
    restored = get_analyzer("persistent_stemmer")
    tokens = restored.analyze("The runners are running")
    print("  Session 2: restored 'persistent_stemmer'")
    print(f"  Session 2: analyze('The runners are running') -> {tokens}")
    assert "run" in tokens  # 'runners' and 'running' both stem to 'run'
    print("  Persistence verified!")

# Clean up
_custom_analyzers.pop("persistent_stemmer", None)


print("\n" + "=" * 70)
print("All text analysis SQL examples completed successfully.")
print("=" * 70)
