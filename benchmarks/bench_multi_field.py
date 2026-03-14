#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Benchmarks for multi-field Bayesian BM25 scoring.

Covers MultiFieldBayesianScorer and MultiFieldSearchOperator.
"""

from __future__ import annotations

import numpy as np
import pytest

from benchmarks.data.generators import BenchmarkDataGenerator
from uqa.core.types import IndexStats
from uqa.engine import Engine
from uqa.scoring.bayesian_bm25 import BayesianBM25Params
from uqa.scoring.multi_field import MultiFieldBayesianScorer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_index_stats(total_docs: int = 10000) -> IndexStats:
    return IndexStats(
        total_docs=total_docs,
        avg_doc_length=100.0,
        _doc_freqs={("body", "term"): total_docs // 10},
    )


def _make_field_configs(
    n_fields: int,
) -> list[tuple[str, BayesianBM25Params, float]]:
    """Create field configurations with equal weights."""
    fields = [f"field_{i}" for i in range(n_fields)]
    return [(f, BayesianBM25Params(), 1.0) for f in fields]


# ---------------------------------------------------------------------------
# MultiFieldBayesianScorer
# ---------------------------------------------------------------------------


class TestMultiFieldScorer:
    @pytest.mark.parametrize("n_fields", [2, 3, 5])
    def test_score_document(self, benchmark, n_fields: int) -> None:
        stats = _make_index_stats()
        configs = _make_field_configs(n_fields)
        scorer = MultiFieldBayesianScorer(configs, stats)

        tf_per_field = {f"field_{i}": 5 for i in range(n_fields)}
        dl_per_field = {f"field_{i}": 120 for i in range(n_fields)}
        df_per_field = {f"field_{i}": 1000 for i in range(n_fields)}

        benchmark(scorer.score_document, 1, tf_per_field, dl_per_field, df_per_field)

    @pytest.mark.parametrize("n_fields", [2, 5])
    def test_score_batch(self, benchmark, n_fields: int) -> None:
        stats = _make_index_stats()
        configs = _make_field_configs(n_fields)
        scorer = MultiFieldBayesianScorer(configs, stats)

        rng = np.random.default_rng(42)
        n_docs = 1000
        tfs = rng.integers(1, 20, size=(n_docs, n_fields))
        dls = rng.integers(50, 200, size=(n_docs, n_fields))
        dfs = rng.integers(100, 5000, size=n_fields)

        field_names = [f"field_{i}" for i in range(n_fields)]

        def score_all() -> float:
            total = 0.0
            for d in range(n_docs):
                tf_map = {field_names[i]: int(tfs[d, i]) for i in range(n_fields)}
                dl_map = {field_names[i]: int(dls[d, i]) for i in range(n_fields)}
                df_map = {field_names[i]: int(dfs[i]) for i in range(n_fields)}
                total += scorer.score_document(d, tf_map, dl_map, df_map)
            return total

        benchmark(score_all)


# ---------------------------------------------------------------------------
# MultiFieldSearchOperator
# ---------------------------------------------------------------------------


class TestMultiFieldOperator:
    @pytest.mark.parametrize("n_fields", [2, 3])
    def test_execute(self, benchmark, n_fields: int) -> None:
        e = Engine()
        field_names = [f"field_{i}" for i in range(n_fields)]
        columns = ", ".join(f"{f} TEXT" for f in field_names)
        e.sql(f"CREATE TABLE docs (id INTEGER, {columns})")

        gen = BenchmarkDataGenerator(scale_factor=1, seed=42)
        docs = gen.documents()[:200]
        for i, doc in enumerate(docs):
            values = ", ".join(f"'{doc['body']}'" for _ in range(n_fields))
            e.sql(f"INSERT INTO docs VALUES ({i + 1}, {values})")

        from uqa.operators.multi_field import MultiFieldSearchOperator

        op = MultiFieldSearchOperator(
            fields=field_names,
            query="term_000000",
            weights=[1.0] * n_fields,
        )

        table = e._tables["docs"]
        from uqa.operators.base import ExecutionContext

        ctx = ExecutionContext(
            document_store=table.document_store,
            inverted_index=table.inverted_index,
        )

        result = benchmark(op.execute, ctx)
        assert len(result) >= 0
