#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import struct

import numpy as np

from uqa.engine import Engine
from uqa.storage.catalog import Catalog, catalog_type_to_python
from uqa.storage.index_types import IndexDef, IndexType


def test_persistent_catalog_tables_store_index_metadata_and_vectors(tmp_path):
    db = str(tmp_path / "catalog_storage.db")
    vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"

    with Engine(db_path=db) as engine:
        engine.sql(
            "CREATE TABLE docs ("
            "id SERIAL PRIMARY KEY, "
            "title TEXT NOT NULL, "
            "body TEXT NOT NULL, "
            "emb VECTOR(3))"
        )
        engine.sql("CREATE INDEX idx_docs_body ON docs USING gin (body)")
        engine.sql("CREATE INDEX idx_docs_emb ON docs USING ivf (emb)")
        engine.sql(
            "INSERT INTO docs (title, body, emb) "
            f"VALUES ('hello', 'quick fox quick', {arr})"
        )

    conn = sqlite3.connect(db)
    try:
        assert (
            conn.execute(
                "SELECT value FROM _metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
            == "10"
        )

        table_row = conn.execute(
            "SELECT fts_fields, vector_fields, columns FROM _tables WHERE name = 'docs'"
        ).fetchone()
        assert table_row is not None
        assert json.loads(table_row[0]) == ["body"]
        assert json.loads(table_row[1]) == [{"field": "emb", "dimensions": 3}]

        columns = json.loads(table_row[2])
        by_name = {col["name"]: col for col in columns}
        assert by_name["id"]["ty"] == "Integer"
        assert by_name["id"]["auto_increment"] is True
        assert by_name["emb"]["ty"] == {"Vector": 3}

        body = conn.execute(
            "SELECT body FROM _documents WHERE table_name = 'docs' AND doc_id = 1"
        ).fetchone()[0]
        assert json.loads(body)["body"] == "quick fox quick"

        positions = conn.execute(
            "SELECT positions FROM _postings "
            "WHERE table_name = 'docs' AND field = 'body' AND term = 'quick'"
        ).fetchone()[0]
        assert struct.unpack("<II", positions) == (0, 2)

        assert (
            conn.execute(
                "SELECT length FROM _doc_lengths "
                "WHERE table_name = 'docs' AND doc_id = 1 AND field = 'body'"
            ).fetchone()[0]
            == 3
        )
        assert (
            conn.execute(
                "SELECT total_length FROM _field_stats "
                "WHERE table_name = 'docs' AND field = 'body'"
            ).fetchone()[0]
            == 3
        )

        stored_vec = conn.execute(
            "SELECT vector FROM _vectors "
            "WHERE table_name = 'docs' AND field = 'emb' "
            "AND doc_id = 1 AND vector_ordinal = 0"
        ).fetchone()[0]
        np.testing.assert_allclose(np.frombuffer(stored_vec, dtype=np.float32), vec)
    finally:
        conn.close()


def test_persistent_tables_round_trip_typed_values(tmp_path):
    db = str(tmp_path / "typed_values.db")

    with Engine(db_path=db) as engine:
        engine.sql(
            "CREATE TABLE rich ("
            "id SERIAL PRIMARY KEY, "
            "flag BOOLEAN, "
            "attrs JSONB, "
            "payload BYTEA, "
            "day DATE, "
            "clock TIME, "
            "clock_tz TIME WITH TIME ZONE, "
            "created TIMESTAMP, "
            "created_tz TIMESTAMP WITH TIME ZONE, "
            "emb VECTOR(2))"
        )
        engine.sql(
            "INSERT INTO rich "
            "(flag, attrs, payload, day, clock, clock_tz, created, created_tz, emb) "
            "VALUES ("
            "TRUE, "
            '\'{"kind":"doc","n":3}\'::jsonb, '
            "'hello'::bytea, "
            "'2026-05-24'::date, "
            "'09:30:15'::time, "
            "'09:30:15+09:00'::timetz, "
            "'2026-05-24T09:30:15'::timestamp, "
            "'2026-05-24T00:30:15+00:00'::timestamptz, "
            "ARRAY[1.0,0.0])"
        )

    conn = sqlite3.connect(db)
    try:
        table_row = conn.execute(
            "SELECT columns, vector_fields FROM _tables WHERE name = 'rich'"
        ).fetchone()
        assert table_row is not None

        columns = {col["name"]: col for col in json.loads(table_row[0])}
        assert columns["clock"]["ty"] == "Time"
        assert columns["clock_tz"]["ty"] == "TimeTz"
        assert columns["created"]["ty"] == "Timestamp"
        assert columns["created_tz"]["ty"] == "TimestampTz"
        assert columns["payload"]["ty"] == "Bytea"
        assert json.loads(table_row[1]) == [{"field": "emb", "dimensions": 2}]

        body = json.loads(
            conn.execute(
                "SELECT body FROM _documents WHERE table_name = 'rich' AND doc_id = 1"
            ).fetchone()[0]
        )
        assert body["flag"] is True
        assert body["attrs"] == {"kind": "doc", "n": 3}
        assert body["payload"] == {"$uqa_type": "document_blob", "field": "payload"}
        assert body["day"] == {"$uqa_type": "date", "days": 20597}
        assert body["clock"]["$uqa_type"] == "time"
        assert body["clock_tz"]["$uqa_type"] == "time_tz"
        assert body["created"]["$uqa_type"] == "timestamp"
        assert body["created_tz"]["$uqa_type"] == "timestamp_tz"

        blob = conn.execute(
            "SELECT bytes FROM _document_blobs "
            "WHERE table_name = 'rich' AND doc_id = 1 AND field_name = 'payload'"
        ).fetchone()[0]
        assert blob == b"hello"
    finally:
        conn.close()

    with Engine(db_path=db) as engine:
        row = engine.sql(
            "SELECT flag, attrs, payload, day, clock, clock_tz, created, created_tz "
            "FROM rich"
        ).rows[0]
        assert row["flag"] is True
        assert row["attrs"] == {"kind": "doc", "n": 3}
        assert row["payload"] == b"hello"
        assert row["day"] == dt.date(2026, 5, 24)
        assert row["clock"] == dt.time(9, 30, 15)
        assert row["clock_tz"] == dt.time(
            9, 30, 15, tzinfo=dt.timezone(dt.timedelta(hours=9))
        )
        assert row["created"] == dt.datetime(2026, 5, 24, 9, 30, 15)
        assert row["created_tz"] == dt.datetime(2026, 5, 24, 0, 30, 15, tzinfo=dt.UTC)


def test_tensor_column_writes_vector_ordinals_and_searches_best_chunk(tmp_path):
    db = str(tmp_path / "tensor_storage.db")

    with Engine(db_path=db) as engine:
        engine.sql(
            "CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, chunks TENSOR(2))"
        )
        engine.sql("CREATE INDEX idx_docs_chunks ON docs USING ivf (chunks)")
        engine.sql(
            "INSERT INTO docs (title, chunks) "
            "VALUES ('two chunks', ARRAY[ARRAY[0.0,1.0],ARRAY[1.0,0.0]])"
        )
        engine.sql(
            "INSERT INTO docs (title, chunks) VALUES ('weaker', ARRAY[ARRAY[0.8,0.6]])"
        )
        rows = engine.sql(
            "SELECT id FROM docs WHERE knn_match(chunks, ARRAY[1.0,0.0], 2)"
        ).rows
        assert [row["id"] for row in rows] == [1, 2]

    conn = sqlite3.connect(db)
    try:
        table_row = conn.execute(
            "SELECT columns, vector_fields FROM _tables WHERE name = 'docs'"
        ).fetchone()
        assert table_row is not None
        columns = {col["name"]: col for col in json.loads(table_row[0])}
        assert columns["chunks"]["ty"] == {"Tensor": 2}
        assert json.loads(table_row[1]) == [{"field": "chunks", "dimensions": 2}]

        rows = conn.execute(
            "SELECT doc_id, vector_ordinal, vector FROM _vectors "
            "WHERE table_name = 'docs' AND field = 'chunks' "
            "ORDER BY doc_id, vector_ordinal"
        ).fetchall()
        assert [(doc_id, ordinal) for doc_id, ordinal, _blob in rows] == [
            (1, 0),
            (1, 1),
            (2, 0),
        ]
        np.testing.assert_allclose(
            np.frombuffer(rows[0][2], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
        )
        np.testing.assert_allclose(
            np.frombuffer(rows[1][2], dtype=np.float32),
            np.array([1.0, 0.0], dtype=np.float32),
        )

        meta = conn.execute(
            "SELECT vector_count FROM _ivf_indexes "
            "WHERE table_name = 'docs' AND field = 'chunks'"
        ).fetchone()[0]
        assert meta == 3
    finally:
        conn.close()


def test_tensor_catalog_type_restores_as_tensor():
    assert catalog_type_to_python({"Tensor": 2}) == ("tensor", 2, None, None)


def test_engine_reads_canonical_document_and_posting_rows(tmp_path):
    db = str(tmp_path / "canonical_rows.db")
    cat = Catalog(db)
    cat.save_table_schema(
        "docs",
        [
            {
                "name": "id",
                "type_name": "integer",
                "primary_key": True,
                "not_null": True,
                "auto_increment": False,
                "default": None,
            },
            {
                "name": "title",
                "type_name": "text",
                "primary_key": False,
                "not_null": True,
                "auto_increment": False,
                "default": None,
            },
            {
                "name": "body",
                "type_name": "text",
                "primary_key": False,
                "not_null": True,
                "auto_increment": False,
                "default": None,
            },
        ],
    )
    cat.save_index(
        IndexDef(
            name="idx_docs_body",
            index_type=IndexType.GIN,
            table_name="docs",
            columns=("body",),
        )
    )
    cat.conn.execute(
        "INSERT INTO _documents (table_name, doc_id, body) VALUES (?, ?, ?)",
        ("docs", 7, json.dumps({"id": 7, "title": "raw", "body": "hello world"})),
    )
    cat.conn.execute(
        "INSERT INTO _postings "
        "(table_name, field, term, doc_id, positions) VALUES (?, ?, ?, ?, ?)",
        ("docs", "body", "hello", 7, struct.pack("<I", 0)),
    )
    cat.conn.execute(
        "INSERT INTO _doc_lengths (table_name, doc_id, field, length) "
        "VALUES (?, ?, ?, ?)",
        ("docs", 7, "body", 2),
    )
    cat.conn.execute(
        "INSERT INTO _field_stats (table_name, field, total_length) VALUES (?, ?, ?)",
        ("docs", "body", 2),
    )
    cat.conn.commit()
    cat.close()

    with Engine(db_path=db) as engine:
        rows = engine.sql("SELECT id, title FROM docs").rows
        assert rows == [{"id": 7, "title": "raw"}]

        matches = engine.sql(
            "SELECT id, title FROM docs WHERE text_match(body, 'hello')"
        ).rows
        assert matches == [{"id": 7, "title": "raw"}]
