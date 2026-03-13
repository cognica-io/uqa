#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the fluent QueryBuilder API."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture()
def engine():
    e = Engine()
    e.sql("""
        CREATE TABLE docs (
            id SERIAL PRIMARY KEY,
            title TEXT,
            body TEXT,
            year INTEGER,
            score REAL
        )
    """)
    e.sql("""INSERT INTO docs (title, body, year, score) VALUES
        ('attention is all you need', 'transformer model uses self attention', 2017, 9.5),
        ('bert pre-training', 'bidirectional encoder representations', 2019, 8.0),
        ('graph attention networks', 'attention on graph structured data', 2018, 7.5),
        ('vision transformer', 'image recognition with patches', 2021, 6.0),
        ('scaling language models', 'scaling laws for neural language models', 2020, 8.5)
    """)
    yield e
    e.close()


class TestExecuteArrow:
    def test_basic(self, engine: Engine) -> None:
        import pyarrow as pa

        table = engine.query(table="docs").term("graph", field="title").execute_arrow()
        assert isinstance(table, pa.Table)
        assert "_doc_id" in table.column_names
        assert "_score" in table.column_names
        assert table.num_rows >= 1

    def test_empty_result(self, engine: Engine) -> None:
        import pyarrow as pa

        table = (
            engine.query(table="docs")
            .term("xyznonexistent", field="title")
            .execute_arrow()
        )
        assert isinstance(table, pa.Table)
        assert table.num_rows == 0
        assert "_doc_id" in table.column_names
        assert "_score" in table.column_names

    def test_with_scoring(self, engine: Engine) -> None:
        table = (
            engine.query(table="docs")
            .term("graph", field="title")
            .score_bm25("graph")
            .execute_arrow()
        )
        scores = table.column("_score").to_pylist()
        assert all(s > 0 for s in scores)

    def test_column_types(self, engine: Engine) -> None:
        import pyarrow as pa

        table = engine.query(table="docs").term("graph", field="title").execute_arrow()
        assert table.column("_doc_id").type == pa.int64()
        assert table.column("_score").type == pa.float64()


class TestExecuteParquet:
    def test_basic(self, engine: Engine, tmp_path) -> None:
        import pyarrow.parquet as pq

        path = str(tmp_path / "fluent.parquet")
        (engine.query(table="docs").term("graph", field="title").execute_parquet(path))
        table = pq.read_table(path)
        assert table.num_rows >= 1
        assert "_doc_id" in table.column_names
        assert "_score" in table.column_names

    def test_roundtrip(self, engine: Engine, tmp_path) -> None:
        import pyarrow.parquet as pq

        path = str(tmp_path / "roundtrip.parquet")
        qb = engine.query(table="docs").term("graph", field="title")
        qb.execute_parquet(path)

        arrow_table = qb.execute_arrow()
        parquet_table = pq.read_table(path)

        assert arrow_table.num_rows == parquet_table.num_rows
        assert (
            arrow_table.column("_doc_id").to_pylist()
            == parquet_table.column("_doc_id").to_pylist()
        )

    def test_empty(self, engine: Engine, tmp_path) -> None:
        import pyarrow.parquet as pq

        path = str(tmp_path / "empty.parquet")
        (
            engine.query(table="docs")
            .term("xyznonexistent", field="title")
            .execute_parquet(path)
        )
        table = pq.read_table(path)
        assert table.num_rows == 0
