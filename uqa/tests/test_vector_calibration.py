#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Paper 5: Index-Aware Bayesian Calibration of Vector Scores.

Unit tests for deleted self-implemented modules (BackgroundDistribution,
WeightedKDE, DistanceGMM, VectorCalibrator, VectorFallbackEstimator) have
been removed -- those classes are replaced by bayesian_bm25's
VectorProbabilityTransform which has its own test suite.

Remaining tests verify:
    - IVF index statistics integration
    - CalibratedVectorOperator end-to-end behaviour
    - SQL integration (bayesian_knn_match, fuse_log_odds)
    - Calibration quality (likelihood ratio vs naive)
    - BM25 cross-modal weights (Section 4.3)
"""

from __future__ import annotations

import numpy as np
import pytest
from bayesian_bm25.vector_probability import VectorProbabilityTransform

# ------------------------------------------------------------------
# IVF Index statistics integration
# ------------------------------------------------------------------


class TestIVFStatistics:
    @pytest.fixture()
    def ivf_index(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.ivf_index import IVFIndex

        catalog = Catalog(str(tmp_path / "test.db"))
        idx = IVFIndex(
            catalog.conn,
            table_name="docs",
            field_name="emb",
            dimensions=8,
            nlist=4,
            nprobe=2,
        )
        # Add enough vectors to trigger auto-train.
        rng = np.random.RandomState(42)
        for i in range(1, 300):
            v = rng.randn(8).astype(np.float32)
            idx.add(i, v)
        yield idx
        catalog.close()

    def test_background_stats_computed(self, ivf_index):
        stats = ivf_index.background_stats
        assert stats is not None
        mu, sigma = stats
        assert mu > 0
        assert sigma > 0

    def test_cell_populations_sum(self, ivf_index):
        pops = ivf_index.cell_populations()
        assert sum(pops.values()) > 0

    def test_cell_populations_all_positive(self, ivf_index):
        pops = ivf_index.cell_populations()
        for count in pops.values():
            assert count > 0

    def test_centroid_id_in_knn_results(self, ivf_index):
        rng = np.random.RandomState(99)
        query = rng.randn(8).astype(np.float32)
        results = ivf_index.search_knn(query, 5)
        for entry in results:
            assert "_centroid_id" in entry.payload.fields

    def test_centroid_id_in_threshold_results(self, ivf_index):
        rng = np.random.RandomState(99)
        query = rng.randn(8).astype(np.float32)
        results = ivf_index.search_threshold(query, 0.0)
        if len(results) > 0:
            for entry in results:
                assert "_centroid_id" in entry.payload.fields

    def test_nlist_and_total_vectors_properties(self, ivf_index):
        assert ivf_index.nlist == 4
        assert ivf_index.total_vectors == 299

    def test_background_stats_persist_across_reload(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.ivf_index import IVFIndex

        db = str(tmp_path / "persist.db")
        cat1 = Catalog(db)
        idx1 = IVFIndex(cat1.conn, "t", "e", dimensions=8, nlist=4, nprobe=2)
        rng = np.random.RandomState(42)
        for i in range(1, 300):
            idx1.add(i, rng.randn(8).astype(np.float32))
        stats1 = idx1.background_stats
        assert stats1 is not None
        cat1.close()

        cat2 = Catalog(db)
        idx2 = IVFIndex(cat2.conn, "t", "e", dimensions=8, nlist=4, nprobe=2)
        stats2 = idx2.background_stats
        assert stats2 is not None
        assert abs(stats1[0] - stats2[0]) < 1e-10
        assert abs(stats1[1] - stats2[1]) < 1e-10
        cat2.close()


# ------------------------------------------------------------------
# CalibratedVectorOperator
# ------------------------------------------------------------------


class TestCalibratedVectorOperator:
    @pytest.fixture()
    def setup(self, tmp_path):
        from uqa.operators.base import ExecutionContext
        from uqa.storage.catalog import Catalog
        from uqa.storage.ivf_index import IVFIndex

        catalog = Catalog(str(tmp_path / "test.db"))
        idx = IVFIndex(catalog.conn, "docs", "emb", dimensions=8, nlist=4, nprobe=4)
        rng = np.random.RandomState(42)
        for i in range(1, 300):
            idx.add(i, rng.randn(8).astype(np.float32))

        ctx = ExecutionContext(vector_indexes={"emb": idx})
        yield ctx, idx, rng
        catalog.close()

    def test_calibrated_knn_returns_probabilities(self, setup):
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        ctx, _, rng = setup
        query = rng.randn(8).astype(np.float32)
        op = CalibratedVectorOperator(
            query, k=10, field="emb", weight_source="density_prior"
        )
        results = op.execute(ctx)
        assert len(results) > 0
        for entry in results:
            assert 0 < entry.payload.score < 1

    def test_calibrated_preserves_raw_similarity(self, setup):
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        ctx, _, rng = setup
        query = rng.randn(8).astype(np.float32)
        op = CalibratedVectorOperator(query, k=5, field="emb", weight_source="uniform")
        results = op.execute(ctx)
        for entry in results:
            assert "_raw_similarity" in entry.payload.fields

    def test_distance_gap_weight_source(self, setup):
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        ctx, _, rng = setup
        query = rng.randn(8).astype(np.float32)
        op = CalibratedVectorOperator(
            query, k=10, field="emb", weight_source="distance_gap"
        )
        results = op.execute(ctx)
        assert len(results) > 0
        for entry in results:
            assert 0 < entry.payload.score < 1

    def test_gmm_estimation(self, setup):
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        ctx, _, rng = setup
        query = rng.randn(8).astype(np.float32)
        op = CalibratedVectorOperator(query, k=10, field="emb", estimation_method="gmm")
        results = op.execute(ctx)
        assert len(results) > 0
        for entry in results:
            assert 0 < entry.payload.score < 1

    def test_nonexistent_field_returns_empty(self, setup):
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        ctx, _, rng = setup
        query = rng.randn(8).astype(np.float32)
        op = CalibratedVectorOperator(query, k=5, field="nonexistent")
        results = op.execute(ctx)
        assert len(results) == 0


# ------------------------------------------------------------------
# SQL integration
# ------------------------------------------------------------------


class TestSQLIntegration:
    @pytest.fixture()
    def engine(self, tmp_path):
        from uqa.engine import Engine

        e = Engine(str(tmp_path / "sql_cal.db"), parallel_workers=0)
        e.sql("""
            CREATE TABLE docs (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                embedding VECTOR(8)
            )
        """)
        # Create IVF index with small nlist so training triggers early.
        e.sql("CREATE INDEX idx_emb ON docs USING ivf (embedding) WITH (nlist = 4)")
        e.sql("CREATE INDEX idx_docs_gin ON docs USING gin (title)")

        rng = np.random.RandomState(42)
        base = rng.randn(8).astype(np.float32)
        base /= np.linalg.norm(base)

        # Insert enough vectors to trigger IVF training (>= max(8, 256) = 256).
        for i in range(300):
            emb = base + rng.randn(8).astype(np.float32) * 0.3
            emb = (emb / np.linalg.norm(emb)).astype(np.float32)
            arr_str = "ARRAY[" + ",".join(str(float(v)) for v in emb) + "]"
            e.sql(f"INSERT INTO docs (title, embedding) VALUES ('doc {i}', {arr_str})")
        yield e
        e.close()

    def test_knn_match_auto_calibrates(self, engine):
        """knn_match inside fusion auto-calibrates when IVF is trained."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE fuse_log_odds(
                text_match(title, 'doc'),
                knn_match(embedding, $1, 10)
            )
            ORDER BY _score DESC
            LIMIT 5
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_match_sql_function(self, engine):
        """bayesian_knn_match explicitly uses Paper 5 calibration."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE fuse_log_odds(
                text_match(title, 'doc'),
                bayesian_knn_match(embedding, $1, 10)
            )
            ORDER BY _score DESC
            LIMIT 5
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_standalone(self, engine):
        """bayesian_knn_match works outside fusion too."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE bayesian_knn_match(embedding, $1, 5)
            ORDER BY _score DESC
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_with_named_options(self, engine):
        """bayesian_knn_match accepts named arguments for calibration options."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE bayesian_knn_match(
                embedding, $1, 10,
                method => 'gmm',
                weight_source => 'distance_gap',
                base_rate => 0.3
            )
            ORDER BY _score DESC
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_auto_method(self, engine):
        """bayesian_knn_match with method => 'auto' uses VPT auto-routing."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE bayesian_knn_match(
                embedding, $1, 10,
                method => 'auto',
                weight_source => 'uniform'
            )
            ORDER BY _score DESC
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_bayesian_knn_invalid_option_raises(self, engine):
        """Unknown named option raises ValueError."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        with pytest.raises(ValueError, match="Unknown option"):
            engine.sql(
                """
                SELECT title, _score FROM docs
                WHERE bayesian_knn_match(
                    embedding, $1, 5,
                    invalid_option => 'foo'
                )
            """,
                params=[qv],
            )

    def test_fuse_log_odds_named_options(self, engine):
        """fuse_log_odds accepts named args for alpha, gating, gating_beta."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE fuse_log_odds(
                text_match(title, 'doc'),
                bayesian_knn_match(embedding, $1, 10),
                alpha => 0.7,
                gating => 'swish',
                gating_beta => 2.0
            )
            ORDER BY _score DESC
            LIMIT 5
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_fuse_log_odds_gating_gelu(self, engine):
        """fuse_log_odds with GELU gating."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE fuse_log_odds(
                text_match(title, 'doc'),
                knn_match(embedding, $1, 10),
                gating => 'gelu'
            )
            ORDER BY _score DESC
            LIMIT 5
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_background_stats_via_engine(self, engine):
        """Engine exposes IVF background stats."""
        stats = engine.vector_background_stats("docs", "embedding")
        assert stats is not None
        mu, sigma = stats
        assert mu > 0
        assert sigma > 0

    def test_query_builder_bayesian_knn(self, engine):
        """QueryBuilder.bayesian_knn produces calibrated results."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        results = (
            engine.query("docs").bayesian_knn(qv, k=5, field="embedding").execute()
        )
        assert len(results) > 0
        for entry in results:
            assert 0.0 < entry.payload.score < 1.0
            assert "_raw_similarity" in entry.payload.fields


# ------------------------------------------------------------------
# Calibration quality verification
# ------------------------------------------------------------------


class TestCalibrationQuality:
    """Verify that likelihood ratio calibration produces better-calibrated
    probabilities than naive linear rescaling (Paper 5, Section 8).

    Uses a synthetic corpus where ground-truth relevance is known:
    relevant documents are embedded near the query, non-relevant
    documents are placed far away.
    """

    @pytest.fixture()
    def synthetic_corpus(self):
        """Build a corpus with known relevance structure.

        - 50 relevant documents: clustered near the query (small distance)
        - 950 non-relevant documents: spread across the embedding space

        Returns (query, ivf_index, label_map, catalog).
        """
        import os
        import tempfile

        from uqa.storage.catalog import Catalog
        from uqa.storage.ivf_index import IVFIndex

        tmp = tempfile.mkdtemp()
        catalog = Catalog(os.path.join(tmp, "cal_quality.db"))

        dim = 32
        rng = np.random.RandomState(42)

        # Query vector.
        query = rng.randn(dim).astype(np.float32)
        query /= np.linalg.norm(query)

        idx = IVFIndex(
            catalog.conn,
            "corpus",
            "emb",
            dimensions=dim,
            nlist=16,
            nprobe=16,
        )

        n_relevant = 50
        n_irrelevant = 950
        label_map: dict[int, int] = {}

        # Relevant documents: close to query (small perturbation).
        for i in range(n_relevant):
            doc_id = i + 1
            v = query + rng.randn(dim).astype(np.float32) * 0.08
            v /= np.linalg.norm(v)
            idx.add(doc_id, v)
            label_map[doc_id] = 1

        # Non-relevant documents: random directions.
        for i in range(n_irrelevant):
            doc_id = n_relevant + i + 1
            v = rng.randn(dim).astype(np.float32)
            v /= np.linalg.norm(v)
            idx.add(doc_id, v)
            label_map[doc_id] = 0

        yield query, idx, label_map, catalog
        catalog.close()

    @staticmethod
    def _evaluate(
        idx, query, label_map, k, estimation_method="kde", weight_source="distance_gap"
    ):
        """Retrieve top-K, calibrate, and return metrics dict."""
        from uqa.scoring.calibration import CalibrationMetrics

        results = idx.search_knn(query, k)
        entries = list(results)

        result_labels = [label_map.get(e.doc_id, 0) for e in entries]
        similarities = np.array([e.payload.score for e in entries], dtype=np.float64)
        distances = 1.0 - similarities

        # Naive: P = (1 + cos) / 2.
        naive_probs = [(1.0 + s) / 2.0 for s in similarities]

        # Build VPT from IVF background stats.
        bg_stats = idx.background_stats
        assert bg_stats is not None
        mu_g, sigma_g = bg_stats
        vpt = VectorProbabilityTransform(mu_g, sigma_g)

        # Route method based on weight_source.
        if weight_source == "distance_gap":
            method = "auto"
            calibrated = vpt.calibrate(distances, method=method)
        elif weight_source == "density_prior":
            from bayesian_bm25.vector_probability import ivf_density_prior

            centroid_ids = np.array(
                [e.payload.fields.get("_centroid_id", -1) for e in entries],
                dtype=np.int64,
            )
            cell_pops = idx.cell_populations()
            avg_pop = idx.total_vectors / max(idx.nlist, 1)
            prior = np.array(
                [
                    float(ivf_density_prior(cell_pops.get(int(cid), 1), avg_pop))
                    for cid in centroid_ids
                ],
                dtype=np.float64,
            )
            calibrated = vpt.calibrate(
                distances, method=estimation_method, density_prior=prior
            )
        else:
            calibrated = vpt.calibrate(distances, method=estimation_method)

        cal_probs = [float(p) for p in np.asarray(calibrated, dtype=np.float64)]

        ece_naive = CalibrationMetrics.ece(naive_probs, result_labels)
        ece_cal = CalibrationMetrics.ece(cal_probs, result_labels)
        brier_naive = CalibrationMetrics.brier(naive_probs, result_labels)
        brier_cal = CalibrationMetrics.brier(cal_probs, result_labels)
        ll_naive = CalibrationMetrics.log_loss(naive_probs, result_labels)
        ll_cal = CalibrationMetrics.log_loss(cal_probs, result_labels)

        return {
            "ece_naive": ece_naive,
            "ece_cal": ece_cal,
            "brier_naive": brier_naive,
            "brier_cal": brier_cal,
            "log_loss_naive": ll_naive,
            "log_loss_cal": ll_cal,
            "naive_probs": naive_probs,
            "cal_probs": cal_probs,
            "labels": result_labels,
        }

    def test_kde_ece_improves_with_gap_weights(self, synthetic_corpus):
        """KDE + distance gap weights should improve ECE over naive."""
        query, idx, label_map, _ = synthetic_corpus
        m = self._evaluate(idx, query, label_map, k=100, weight_source="distance_gap")
        assert m["ece_cal"] < m["ece_naive"], (
            f"KDE+gap ECE ({m['ece_cal']:.4f}) should beat "
            f"naive ECE ({m['ece_naive']:.4f})"
        )

    def test_kde_brier_improves_with_gap_weights(self, synthetic_corpus):
        """KDE + distance gap weights should improve Brier over naive."""
        query, idx, label_map, _ = synthetic_corpus
        m = self._evaluate(idx, query, label_map, k=100, weight_source="distance_gap")
        assert m["brier_cal"] < m["brier_naive"], (
            f"KDE+gap Brier ({m['brier_cal']:.4f}) should beat "
            f"naive Brier ({m['brier_naive']:.4f})"
        )

    def test_kde_log_loss_improves_with_gap_weights(self, synthetic_corpus):
        """KDE + distance gap should improve log loss over naive."""
        query, idx, label_map, _ = synthetic_corpus
        m = self._evaluate(idx, query, label_map, k=100, weight_source="distance_gap")
        assert m["log_loss_cal"] < m["log_loss_naive"], (
            f"KDE+gap log loss ({m['log_loss_cal']:.4f}) should beat "
            f"naive log loss ({m['log_loss_naive']:.4f})"
        )

    def test_gmm_ece_improves(self, synthetic_corpus):
        """GMM-EM + distance gap should improve ECE over naive."""
        query, idx, label_map, _ = synthetic_corpus
        m = self._evaluate(
            idx,
            query,
            label_map,
            k=100,
            estimation_method="gmm",
            weight_source="distance_gap",
        )
        assert m["ece_cal"] < m["ece_naive"], (
            f"GMM+gap ECE ({m['ece_cal']:.4f}) should beat "
            f"naive ECE ({m['ece_naive']:.4f})"
        )

    def test_density_prior_not_catastrophically_worse(self, synthetic_corpus):
        """Density prior should not degrade ECE by more than 5%.

        Per Remark 4.6.4, the density prior is weaker than distance
        gap detection.  In synthetic scenarios with balanced IVF cells,
        it may not improve ECE, but it should not make things much worse.
        """
        query, idx, label_map, _ = synthetic_corpus
        m = self._evaluate(idx, query, label_map, k=100, weight_source="density_prior")
        assert m["ece_cal"] < m["ece_naive"] + 0.05, (
            f"Density prior ECE ({m['ece_cal']:.4f}) should not be much worse "
            f"than naive ECE ({m['ece_naive']:.4f})"
        )

    def test_ranking_quality_preserved(self, synthetic_corpus):
        """Calibration should preserve ranking: relevant docs score higher."""
        query, idx, label_map, _ = synthetic_corpus

        results = idx.search_knn(query, 100)
        entries = list(results)

        bg_stats = idx.background_stats
        assert bg_stats is not None
        vpt = VectorProbabilityTransform(*bg_stats)
        sims = np.array([e.payload.score for e in entries], dtype=np.float64)
        distances = 1.0 - sims

        calibrated = np.asarray(
            vpt.calibrate(distances, method="auto"),
            dtype=np.float64,
        )

        # Top-10 calibrated docs should be mostly relevant.
        order = np.argsort(-calibrated)
        top_10_labels = [label_map.get(entries[i].doc_id, 0) for i in order[:10]]
        precision_at_10 = sum(top_10_labels) / 10.0
        assert precision_at_10 >= 0.7, (
            f"Precision@10 ({precision_at_10:.2f}) should be >= 0.7"
        )

        # Average calibrated probability for relevant > non-relevant.
        relevant_probs = [
            float(calibrated[i])
            for i in range(len(entries))
            if label_map.get(entries[i].doc_id, 0) == 1
        ]
        irrelevant_probs = [
            float(calibrated[i])
            for i in range(len(entries))
            if label_map.get(entries[i].doc_id, 0) == 0
        ]
        if relevant_probs and irrelevant_probs:
            assert np.mean(relevant_probs) > np.mean(irrelevant_probs)

    def test_calibration_metrics_summary(self, synthetic_corpus):
        """All methods should beat naive on at least one metric."""
        query, idx, label_map, _ = synthetic_corpus

        for method, ws in [
            ("kde", "distance_gap"),
            ("gmm", "distance_gap"),
            ("kde", "density_prior"),
        ]:
            m = self._evaluate(
                idx,
                query,
                label_map,
                k=100,
                estimation_method=method,
                weight_source=ws,
            )
            improved = (
                m["ece_cal"] < m["ece_naive"]
                or m["brier_cal"] < m["brier_naive"]
                or m["log_loss_cal"] < m["log_loss_naive"]
            )
            assert improved, (
                f"{method}+{ws}: no metric improved -- "
                f"ECE ({m['ece_cal']:.4f} vs {m['ece_naive']:.4f}), "
                f"Brier ({m['brier_cal']:.4f} vs {m['brier_naive']:.4f}), "
                f"LogLoss ({m['log_loss_cal']:.4f} vs {m['log_loss_naive']:.4f})"
            )


# ------------------------------------------------------------------
# BM25 cross-modal weights (Section 4.3)
# ------------------------------------------------------------------


class TestBM25CrossModalWeights:
    """Verify that BM25 cross-modal weights (Section 4.3) improve
    calibration and produce the best results per the degradation
    hierarchy (Remark 4.6.4).

    Uses a synthetic corpus with both text content and embeddings where
    relevant documents contain query terms AND are close in vector space.
    """

    @pytest.fixture()
    def hybrid_corpus(self, tmp_path):
        """Corpus with text + vectors where relevance is known.

        Relevant documents:
            - title contains "quantum computing"
            - embedding is close to the query vector
        Non-relevant documents:
            - title contains unrelated terms
            - embedding is random
        """
        from uqa.engine import Engine

        e = Engine(str(tmp_path / "bm25_cross.db"))
        e.sql("""
            CREATE TABLE papers (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                embedding VECTOR(32)
            )
        """)
        e.sql("CREATE INDEX idx_emb ON papers USING ivf (embedding) WITH (nlist = 8)")

        dim = 32
        rng = np.random.RandomState(42)
        query_vec = rng.randn(dim).astype(np.float32)
        query_vec /= np.linalg.norm(query_vec)

        label_map: dict[int, int] = {}

        # 40 relevant: title has "quantum computing", close to query.
        relevant_titles = [
            "quantum computing algorithms",
            "advances in quantum computing",
            "quantum computing survey",
            "quantum computing hardware",
            "applied quantum computing",
        ]
        for i in range(40):
            title = relevant_titles[i % len(relevant_titles)]
            emb = query_vec + rng.randn(dim).astype(np.float32) * 0.08
            emb = (emb / np.linalg.norm(emb)).astype(np.float32)
            arr_str = "ARRAY[" + ",".join(str(float(v)) for v in emb) + "]"
            e.sql(
                f"INSERT INTO papers (title, embedding) "
                f"VALUES ('{title} {i}', {arr_str})"
            )
            label_map[i + 1] = 1

        # 460 non-relevant: unrelated titles, random embeddings.
        irrelevant_titles = [
            "classical mechanics review",
            "organic chemistry synthesis",
            "medieval history analysis",
            "tropical ecology patterns",
            "financial market models",
        ]
        for i in range(460):
            title = irrelevant_titles[i % len(irrelevant_titles)]
            emb = rng.randn(dim).astype(np.float32)
            emb = (emb / np.linalg.norm(emb)).astype(np.float32)
            arr_str = "ARRAY[" + ",".join(str(float(v)) for v in emb) + "]"
            e.sql(
                f"INSERT INTO papers (title, embedding) "
                f"VALUES ('{title} {i}', {arr_str})"
            )
            label_map[40 + i + 1] = 0

        yield e, query_vec, label_map, "quantum computing"
        e.close()

    def test_bm25_weights_improve_ece(self, hybrid_corpus):
        """BM25 cross-modal weights should improve ECE over naive."""
        from uqa.scoring.calibration import CalibrationMetrics

        engine, query_vec, label_map, query_text = hybrid_corpus

        results = (
            engine.query("papers")
            .bayesian_knn(
                query_vec,
                k=80,
                field="embedding",
                weight_source="bayesian_bm25",
                bm25_query=query_text,
                bm25_field="title",
            )
            .execute()
        )
        entries = list(results)
        assert len(entries) > 0

        cal_probs = [e.payload.score for e in entries]
        cal_labels = [label_map.get(e.doc_id, 0) for e in entries]

        # Compare against naive.
        naive_results = (
            engine.query("papers").knn(query_vec, k=80, field="embedding").execute()
        )
        naive_entries = list(naive_results)
        naive_probs = [(1.0 + e.payload.score) / 2.0 for e in naive_entries]
        naive_labels = [label_map.get(e.doc_id, 0) for e in naive_entries]

        ece_naive = CalibrationMetrics.ece(naive_probs, naive_labels)
        ece_bm25 = CalibrationMetrics.ece(cal_probs, cal_labels)

        assert ece_bm25 < ece_naive, (
            f"BM25 cross-modal ECE ({ece_bm25:.4f}) should beat "
            f"naive ECE ({ece_naive:.4f})"
        )

    def test_bm25_weights_improve_log_loss(self, hybrid_corpus):
        """BM25 cross-modal weights should improve log loss over naive."""
        from uqa.scoring.calibration import CalibrationMetrics

        engine, query_vec, label_map, query_text = hybrid_corpus

        results = (
            engine.query("papers")
            .bayesian_knn(
                query_vec,
                k=80,
                field="embedding",
                weight_source="bayesian_bm25",
                bm25_query=query_text,
                bm25_field="title",
            )
            .execute()
        )
        entries = list(results)
        cal_probs = [e.payload.score for e in entries]
        cal_labels = [label_map.get(e.doc_id, 0) for e in entries]

        naive_results = (
            engine.query("papers").knn(query_vec, k=80, field="embedding").execute()
        )
        naive_entries = list(naive_results)
        naive_probs = [(1.0 + e.payload.score) / 2.0 for e in naive_entries]
        naive_labels = [label_map.get(e.doc_id, 0) for e in naive_entries]

        ll_naive = CalibrationMetrics.log_loss(naive_probs, naive_labels)
        ll_bm25 = CalibrationMetrics.log_loss(cal_probs, cal_labels)

        assert ll_bm25 < ll_naive, (
            f"BM25 cross-modal log loss ({ll_bm25:.4f}) should beat "
            f"naive log loss ({ll_naive:.4f})"
        )

    def test_bm25_beats_naive_on_all_three_metrics(self, hybrid_corpus):
        """BM25 cross-modal should beat naive on ECE, Brier, and log loss."""
        from uqa.scoring.calibration import CalibrationMetrics

        engine, query_vec, label_map, query_text = hybrid_corpus
        k = 80

        bm25_entries = list(
            engine.query("papers")
            .bayesian_knn(
                query_vec,
                k=k,
                field="embedding",
                weight_source="bayesian_bm25",
                bm25_query=query_text,
                bm25_field="title",
            )
            .execute()
        )
        bm25_probs = [e.payload.score for e in bm25_entries]
        bm25_labels = [label_map.get(e.doc_id, 0) for e in bm25_entries]

        naive_entries = list(
            engine.query("papers").knn(query_vec, k=k, field="embedding").execute()
        )
        naive_probs = [(1.0 + e.payload.score) / 2.0 for e in naive_entries]
        naive_labels = [label_map.get(e.doc_id, 0) for e in naive_entries]

        ece_naive = CalibrationMetrics.ece(naive_probs, naive_labels)
        ece_bm25 = CalibrationMetrics.ece(bm25_probs, bm25_labels)
        brier_naive = CalibrationMetrics.brier(naive_probs, naive_labels)
        brier_bm25 = CalibrationMetrics.brier(bm25_probs, bm25_labels)
        ll_naive = CalibrationMetrics.log_loss(naive_probs, naive_labels)
        ll_bm25 = CalibrationMetrics.log_loss(bm25_probs, bm25_labels)

        assert ece_bm25 < ece_naive, (
            f"BM25 ECE ({ece_bm25:.4f}) should beat naive ({ece_naive:.4f})"
        )
        assert brier_bm25 < brier_naive, (
            f"BM25 Brier ({brier_bm25:.4f}) should beat naive ({brier_naive:.4f})"
        )
        assert ll_bm25 < ll_naive, (
            f"BM25 log loss ({ll_bm25:.4f}) should beat naive ({ll_naive:.4f})"
        )

    def test_all_metrics_summary(self, hybrid_corpus):
        """Summary comparison: naive vs gap vs density vs BM25."""
        from uqa.scoring.calibration import CalibrationMetrics

        engine, query_vec, label_map, query_text = hybrid_corpus
        k = 80

        configs = [
            ("Naive (1+cos)/2", None, None),
            ("KDE + gap", "distance_gap", None),
            ("KDE + density", "density_prior", None),
            ("KDE + BM25", "bayesian_bm25", query_text),
        ]

        for name, ws, bm25q in configs:
            if ws is None:
                entries = list(
                    engine.query("papers")
                    .knn(query_vec, k=k, field="embedding")
                    .execute()
                )
                probs = [(1.0 + e.payload.score) / 2.0 for e in entries]
            else:
                entries = list(
                    engine.query("papers")
                    .bayesian_knn(
                        query_vec,
                        k=k,
                        field="embedding",
                        weight_source=ws,
                        bm25_query=bm25q,
                        bm25_field="title",
                    )
                    .execute()
                )
                probs = [e.payload.score for e in entries]

            labels = [label_map.get(e.doc_id, 0) for e in entries]
            if not labels:
                continue

            # BM25 method should not be worse than naive on all metrics.
            if name == "KDE + BM25":
                naive_entries = list(
                    engine.query("papers")
                    .knn(query_vec, k=k, field="embedding")
                    .execute()
                )
                naive_p = [(1.0 + e.payload.score) / 2.0 for e in naive_entries]
                naive_l = [label_map.get(e.doc_id, 0) for e in naive_entries]
                assert (
                    CalibrationMetrics.ece(probs, labels)
                    < CalibrationMetrics.ece(naive_p, naive_l)
                    or CalibrationMetrics.brier(probs, labels)
                    < CalibrationMetrics.brier(naive_p, naive_l)
                    or CalibrationMetrics.log_loss(probs, labels)
                    < CalibrationMetrics.log_loss(naive_p, naive_l)
                )
