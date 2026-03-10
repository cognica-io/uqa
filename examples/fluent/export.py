#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Arrow and Parquet export examples using the fluent QueryBuilder API.

Demonstrates:
  - execute_arrow(): query results as a pyarrow.Table (zero-copy)
  - execute_parquet(): write query results to a Parquet file
  - BM25 scoring with Arrow export
  - Round-trip: Parquet write -> read back via pyarrow
"""

import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from uqa.engine import Engine


engine = Engine()

print("=" * 70)
print("Fluent API Arrow / Parquet Export Examples")
print("=" * 70)


# ==================================================================
# 1. Set up test data
# ==================================================================
print("\n--- 1. Setup ---")

engine.sql("""
    CREATE TABLE articles (
        id SERIAL PRIMARY KEY,
        title TEXT,
        body TEXT,
        category TEXT,
        year INTEGER
    )
""")

engine.sql("""INSERT INTO articles (title, body, category, year) VALUES
    ('The Transformer Architecture',
     'The transformer model uses self attention to process sequences',
     'nlp', 2017),
    ('Graph Neural Networks',
     'Graph networks apply attention mechanisms to structured data',
     'graph', 2018),
    ('Scaling Language Models',
     'Scaling laws show predictable improvement in language model performance',
     'nlp', 2020),
    ('Vision Transformer',
     'Vision transformers split images into patches and process them with attention',
     'cv', 2021),
    ('Reinforcement Learning from Human Feedback',
     'RLHF trains language models to follow human instructions via reward modeling',
     'alignment', 2022)
""")

print("  Inserted 5 articles.")


# ==================================================================
# 2. execute_arrow() -- basic text search
# ==================================================================
print("\n--- 2. execute_arrow() ---")

table = (
    engine.query(table="articles")
    .term("attention", field="body")
    .execute_arrow()
)

print(f"  Type: {type(table).__name__}")
print(f"  Rows: {table.num_rows}")
print(f"  Columns: {table.column_names}")
print(f"  doc_ids: {table.column('_doc_id').to_pylist()}")


# ==================================================================
# 3. BM25 scoring -> Arrow
# ==================================================================
print("\n--- 3. BM25 scoring -> Arrow ---")

table = (
    engine.query(table="articles")
    .term("attention", field="body")
    .score_bm25("attention")
    .execute_arrow()
)

print(f"  Rows: {table.num_rows}")
print(f"  Scores: {table.column('_score').to_pylist()}")
print(f"  Max score: {pa.compute.max(table.column('_score')).as_py():.4f}")


# ==================================================================
# 4. Bayesian BM25 scoring -> Arrow
# ==================================================================
print("\n--- 4. Bayesian BM25 -> Arrow ---")

table = (
    engine.query(table="articles")
    .term("transformer", field="body")
    .score_bayesian_bm25("transformer")
    .execute_arrow()
)

print(f"  Rows: {table.num_rows}")
print(f"  Scores (P(relevant)): {table.column('_score').to_pylist()}")


# ==================================================================
# 5. execute_parquet() -- write to file
# ==================================================================
print("\n--- 5. execute_parquet() ---")

parquet_dir = tempfile.mkdtemp()
parquet_path = os.path.join(parquet_dir, "search_results.parquet")

(
    engine.query(table="articles")
    .term("attention", field="body")
    .score_bm25("attention")
    .execute_parquet(parquet_path)
)

file_size = os.path.getsize(parquet_path)
print(f"  Written to: {parquet_path}")
print(f"  File size: {file_size} bytes")


# ==================================================================
# 6. Parquet round-trip
# ==================================================================
print("\n--- 6. Parquet round-trip ---")

restored = pq.read_table(parquet_path)
print(f"  Rows: {restored.num_rows}")
print(f"  Columns: {restored.column_names}")
print(f"  doc_ids: {restored.column('_doc_id').to_pylist()}")
print(f"  Scores: {restored.column('_score').to_pylist()}")


# ==================================================================
# 7. Empty result -> Arrow
# ==================================================================
print("\n--- 7. Empty result ---")

table = (
    engine.query(table="articles")
    .term("xyznonexistent", field="body")
    .execute_arrow()
)

print(f"  Rows: {table.num_rows}")
print(f"  Columns: {table.column_names}")
print(f"  Schema:")
for field in table.schema:
    print(f"    {field.name}: {field.type}")


# ==================================================================
# 8. Arrow compute on search results
# ==================================================================
print("\n--- 8. Arrow compute on search results ---")

table = (
    engine.query(table="articles")
    .term("language", field="body")
    .score_bm25("language")
    .execute_arrow()
)

scores = table.column("_score")
print(f"  Matching docs: {table.num_rows}")
print(f"  Scores: {scores.to_pylist()}")
print(f"  Mean score: {pa.compute.mean(scores).as_py():.4f}")
print(f"  Std dev: {pa.compute.stddev(scores).as_py():.4f}")


print("\n" + "=" * 70)
print("All fluent API export examples completed successfully.")
print("=" * 70)
