#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Paper 5: Index-Aware Bayesian Calibration of Vector Scores."""

from __future__ import annotations

import math

import numpy as np
import pytest

from uqa.scoring.background_distribution import BackgroundDistribution
from uqa.scoring.distance_gmm import DistanceGMM
from uqa.scoring.vector_calibrator import VectorCalibrator
from uqa.scoring.vector_fallback import VectorFallbackEstimator
from uqa.scoring.weighted_kde import WeightedKDE

# ------------------------------------------------------------------
# BackgroundDistribution
# ------------------------------------------------------------------


def _make_bg(
    mu: float = 0.5, sigma: float = 0.1, n: int = 1000
) -> BackgroundDistribution:
    """Helper: create a BackgroundDistribution from synthetic samples."""
    rng = np.random.RandomState(42)
    return BackgroundDistribution(samples=rng.normal(mu, sigma, size=n))


class TestBackgroundDistribution:
    def test_kde_pdf_positive(self):
        bg = _make_bg(0.5, 0.1)
        assert bg.pdf(0.5) > 0
        assert bg.pdf(0.0) > 0

    def test_pdf_peak_at_mean(self):
        bg = _make_bg(0.5, 0.1)
        assert bg.pdf(0.5) > bg.pdf(0.3)
        assert bg.pdf(0.5) > bg.pdf(0.7)

    def test_log_pdf_consistent(self):
        bg = _make_bg(0.5, 0.1)
        for d in [0.1, 0.3, 0.5, 0.7, 0.9]:
            assert abs(bg.log_pdf(d) - math.log(bg.pdf(d))) < 1e-10

    def test_batch_matches_scalar(self):
        bg = _make_bg(0.4, 0.15)
        distances = np.array([0.1, 0.3, 0.5, 0.7])
        batch = bg.pdf_batch(distances)
        for i, d in enumerate(distances):
            assert abs(batch[i] - bg.pdf(d)) < 1e-10

    def test_serialisation_roundtrip(self):
        bg = _make_bg(0.42, 0.13)
        restored = BackgroundDistribution.from_dict(bg.to_dict())
        assert abs(restored.mu - bg.mu) < 1e-10
        assert abs(restored.sigma - bg.sigma) < 1e-10

    def test_from_distance_sample(self):
        rng = np.random.RandomState(42)
        sample = rng.normal(0.5, 0.1, size=1000)
        bg = BackgroundDistribution.from_distance_sample(sample)
        assert abs(bg.mu - 0.5) < 0.02
        assert abs(bg.sigma - 0.1) < 0.02


# ------------------------------------------------------------------
# WeightedKDE
# ------------------------------------------------------------------


class TestWeightedKDE:
    def test_uniform_weights_basic(self):
        distances = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        weights = np.ones(5)
        kde = WeightedKDE(distances, weights)
        # PDF should be positive in the data range.
        assert kde.pdf(0.3) > 0

    def test_weighted_shifts_peak(self):
        distances = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
        # Weight only the close documents.
        weights_close = np.array([1.0, 1.0, 1.0, 0.0, 0.0])
        kde_close = WeightedKDE(distances, weights_close)
        # Weight only the far documents.
        weights_far = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
        kde_far = WeightedKDE(distances, weights_far)
        # Close-weighted KDE should peak near 0.2.
        assert kde_close.pdf(0.2) > kde_far.pdf(0.2)
        # Far-weighted KDE should peak near 0.85.
        assert kde_far.pdf(0.85) > kde_close.pdf(0.85)

    def test_bandwidth_positive(self):
        distances = np.array([0.1, 0.2, 0.3])
        weights = np.ones(3)
        kde = WeightedKDE(distances, weights)
        assert kde.bandwidth > 0

    def test_batch_matches_scalar(self):
        distances = np.array([0.2, 0.4, 0.6, 0.8])
        weights = np.array([1.0, 0.8, 0.5, 0.2])
        kde = WeightedKDE(distances, weights)
        query_points = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        batch = kde.pdf_batch(query_points)
        for i, d in enumerate(query_points):
            assert abs(batch[i] - kde.pdf(d)) < 1e-10

    def test_zero_weights_excluded(self):
        distances = np.array([0.1, 0.5, 0.9])
        weights = np.array([1.0, 0.0, 0.0])
        kde = WeightedKDE(distances, weights)
        # Only d=0.1 contributes; PDF should peak there.
        assert kde.pdf(0.1) > kde.pdf(0.9)

    def test_custom_bandwidth(self):
        distances = np.array([0.1, 0.2, 0.3])
        weights = np.ones(3)
        kde = WeightedKDE(distances, weights, bandwidth=0.05)
        assert kde.bandwidth == 0.05


# ------------------------------------------------------------------
# DistanceGMM
# ------------------------------------------------------------------


class TestDistanceGMM:
    def test_two_component_separation(self):
        rng = np.random.RandomState(42)
        relevant = rng.normal(0.1, 0.02, size=30)
        background = rng.normal(0.5, 0.1, size=70)
        distances = np.concatenate([relevant, background])
        weights = np.concatenate([np.ones(30), np.zeros(70)])

        gmm = DistanceGMM(distances, weights, background_mu=0.5, background_sigma=0.1)
        # Relevant component should be near 0.1.
        assert abs(gmm.mu_r - 0.1) < 0.05
        assert gmm.sigma_r < 0.1

    def test_relevant_pdf_positive(self):
        distances = np.array([0.1, 0.2, 0.3, 0.5, 0.7])
        weights = np.array([1.0, 0.8, 0.5, 0.1, 0.0])
        gmm = DistanceGMM(distances, weights, background_mu=0.5, background_sigma=0.15)
        assert gmm.relevant_pdf(0.15) > 0

    def test_mixing_coefficient_in_unit_interval(self):
        distances = np.linspace(0.05, 0.95, 50)
        weights = np.concatenate([np.ones(20), np.zeros(30)])
        gmm = DistanceGMM(distances, weights, background_mu=0.5, background_sigma=0.2)
        assert 0.0 < gmm.mixing_coefficient < 1.0

    def test_log_pdf_consistent(self):
        distances = np.array([0.1, 0.2, 0.6, 0.8])
        weights = np.array([1.0, 0.9, 0.1, 0.0])
        gmm = DistanceGMM(distances, weights, background_mu=0.5, background_sigma=0.15)
        for d in [0.1, 0.3, 0.5]:
            pdf = gmm.relevant_pdf(d)
            log_pdf = gmm.relevant_log_pdf(d)
            assert abs(log_pdf - math.log(max(pdf, 1e-300))) < 1e-8

    def test_empty_distances(self):
        gmm = DistanceGMM(
            np.array([]),
            np.array([]),
            background_mu=0.5,
            background_sigma=0.1,
        )
        # Should not raise; returns default parameters.
        assert gmm.relevant_pdf(0.3) > 0


# ------------------------------------------------------------------
# VectorFallbackEstimator
# ------------------------------------------------------------------


class TestVectorFallbackEstimator:
    def test_distance_gap_binary(self):
        # Clear gap between 0.3 and 0.7.
        distances = np.array([0.1, 0.15, 0.2, 0.25, 0.3, 0.7, 0.8, 0.9])
        weights = VectorFallbackEstimator.distance_gap_weights(distances)
        assert len(weights) == len(distances)
        # First 5 should be 1, rest 0.
        np.testing.assert_array_equal(weights[:5], 1.0)
        np.testing.assert_array_equal(weights[5:], 0.0)

    def test_distance_gap_single(self):
        weights = VectorFallbackEstimator.distance_gap_weights(np.array([0.3]))
        assert len(weights) == 1
        assert weights[0] == 1.0

    def test_index_density_sparse_higher(self):
        cell_pops = {0: 10, 1: 100, 2: 1000}
        centroid_ids = np.array([0, 1, 2])
        weights = VectorFallbackEstimator.index_density_weights(
            cell_populations=cell_pops,
            centroid_ids=centroid_ids,
            total_vectors=1110,
            num_cells=3,
            gamma=1.0,
        )
        # Sparse cell (10) should get higher weight than dense (1000).
        assert weights[0] > weights[2]

    def test_index_density_all_equal(self):
        cell_pops = {0: 100, 1: 100, 2: 100}
        centroid_ids = np.array([0, 1, 2])
        weights = VectorFallbackEstimator.index_density_weights(
            cell_populations=cell_pops,
            centroid_ids=centroid_ids,
            total_vectors=300,
            num_cells=3,
        )
        # All cells equal -> all weights equal (should be 0.5).
        assert abs(weights[0] - 0.5) < 1e-10
        assert abs(weights[1] - 0.5) < 1e-10

    def test_cross_model_weights_range(self):
        sims = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
        weights = VectorFallbackEstimator.cross_model_weights(sims)
        np.testing.assert_array_less(-1e-10, weights)
        np.testing.assert_array_less(weights, 1.0 + 1e-10)
        # -1 -> 0, 0 -> 0.5, 1 -> 1
        assert abs(weights[0] - 0.0) < 1e-10
        assert abs(weights[2] - 0.5) < 1e-10
        assert abs(weights[4] - 1.0) < 1e-10


# ------------------------------------------------------------------
# VectorCalibrator
# ------------------------------------------------------------------


class TestVectorCalibrator:
    @pytest.fixture()
    def background(self):
        return _make_bg(0.5, 0.15)

    def test_returns_probabilities(self, background):
        cal = VectorCalibrator(background)
        distances = np.array([0.05, 0.1, 0.3, 0.5, 0.7, 0.9])
        weights = np.array([1.0, 0.9, 0.7, 0.3, 0.1, 0.0])
        probs = cal.calibrate(distances, weights)
        assert all(0 < p < 1 for p in probs)

    def test_monotonicity(self, background):
        """Closer distance should yield higher probability."""
        cal = VectorCalibrator(background)
        distances = np.array([0.05, 0.1, 0.2, 0.3, 0.4])
        weights = np.ones(5)
        probs = cal.calibrate(distances, weights)
        # Monotonically decreasing with distance.
        for i in range(len(probs) - 1):
            assert probs[i] >= probs[i + 1] - 1e-10

    def test_kde_vs_gmm_both_work(self, background):
        distances = np.array([0.05, 0.1, 0.2, 0.5, 0.8])
        weights = np.array([1.0, 0.8, 0.5, 0.1, 0.0])
        cal_kde = VectorCalibrator(background, estimation_method="kde")
        cal_gmm = VectorCalibrator(background, estimation_method="gmm")
        probs_kde = cal_kde.calibrate(distances, weights)
        probs_gmm = cal_gmm.calibrate(distances, weights)
        assert all(0 < p < 1 for p in probs_kde)
        assert all(0 < p < 1 for p in probs_gmm)

    def test_uniform_weights_fallback(self, background):
        cal = VectorCalibrator(background)
        distances = np.array([0.1, 0.3, 0.5])
        probs = cal.calibrate(distances, weights=None)
        assert all(0 < p < 1 for p in probs)

    def test_empty_distances(self, background):
        cal = VectorCalibrator(background)
        probs = cal.calibrate(np.array([]))
        assert len(probs) == 0

    def test_serialisation_roundtrip(self, background):
        cal = VectorCalibrator(background, estimation_method="gmm", base_rate=0.3)
        restored = VectorCalibrator.from_dict(cal.to_dict())
        assert restored.estimation_method == "gmm"
        assert restored.base_rate == 0.3
        assert restored.background.mu == background.mu

    def test_invalid_method_raises(self, background):
        with pytest.raises(ValueError):
            VectorCalibrator(background, estimation_method="invalid")

    def test_high_evidence_near_one(self, background):
        """Very close distance with strong weighting -> high probability."""
        cal = VectorCalibrator(background, base_rate=0.5)
        distances = np.array([0.01, 0.02, 0.03, 0.5, 0.6, 0.7, 0.8, 0.9])
        weights = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        probs = cal.calibrate(distances, weights)
        # First three should have high probability.
        assert probs[0] > 0.5

    def test_base_rate_effect(self, background):
        distances = np.array([0.3, 0.4, 0.5])
        weights = np.ones(3)
        cal_low = VectorCalibrator(background, base_rate=0.1)
        cal_high = VectorCalibrator(background, base_rate=0.9)
        probs_low = cal_low.calibrate(distances, weights)
        probs_high = cal_high.calibrate(distances, weights)
        # Higher base rate should yield higher probabilities.
        for pl, ph in zip(probs_low, probs_high):
            assert ph > pl


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

    def test_knn_calibrated_match_sql_function(self, engine):
        """knn_calibrated_match explicitly uses Paper 5 calibration."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE fuse_log_odds(
                text_match(title, 'doc'),
                knn_calibrated_match(embedding, $1, 10)
            )
            ORDER BY _score DESC
            LIMIT 5
        """,
            params=[qv],
        )
        assert len(result) > 0
        for row in result:
            assert 0.0 < row["_score"] < 1.0

    def test_knn_calibrated_standalone(self, engine):
        """knn_calibrated_match works outside fusion too."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        result = engine.sql(
            """
            SELECT title, _score FROM docs
            WHERE knn_calibrated_match(embedding, $1, 5)
            ORDER BY _score DESC
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

    def test_query_builder_knn_calibrated(self, engine):
        """QueryBuilder.knn_calibrated produces calibrated results."""
        rng = np.random.RandomState(99)
        qv = rng.randn(8).astype(np.float32)

        results = (
            engine.query("docs").knn_calibrated(qv, k=5, field="embedding").execute()
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

    Important: the test uses distance gap detection (Strategy 4.6.1)
    as importance weights to break the circularity of estimating f_R
    from the same distances being calibrated (Problem 4.1.1).
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
        """Retrieve top-K, calibrate, and return (naive_probs, cal_probs, labels)."""
        from uqa.scoring.calibration import CalibrationMetrics

        results = idx.search_knn(query, k)
        entries = list(results)

        result_labels = [label_map.get(e.doc_id, 0) for e in entries]
        similarities = np.array([e.payload.score for e in entries], dtype=np.float64)
        distances = 1.0 - similarities

        # Naive: P = (1 + cos) / 2.
        naive_probs = [(1.0 + s) / 2.0 for s in similarities]

        # Calibrated via likelihood ratio.
        bg_stats = idx.background_stats
        assert bg_stats is not None
        background = BackgroundDistribution.from_ivf_stats(*bg_stats)

        # Importance weights to break circularity (Section 4.6).
        if weight_source == "distance_gap":
            sorted_idx = np.argsort(distances)
            sorted_dists = distances[sorted_idx]
            sorted_w = VectorFallbackEstimator.distance_gap_weights(sorted_dists)
            weights = np.empty(len(distances), dtype=np.float64)
            weights[sorted_idx] = sorted_w
        elif weight_source == "density_prior":
            centroid_ids = np.array(
                [e.payload.fields.get("_centroid_id", -1) for e in entries],
                dtype=np.int64,
            )
            cell_pops = idx.cell_populations()
            weights = VectorFallbackEstimator.index_density_weights(
                cell_pops, centroid_ids, idx.total_vectors, idx.nlist
            )
        else:
            weights = np.ones(len(distances), dtype=np.float64)

        calibrator = VectorCalibrator(background, estimation_method=estimation_method)
        calibrated = calibrator.calibrate(distances, weights)
        cal_probs = [float(p) for p in calibrated]

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

        bg = BackgroundDistribution.from_ivf_stats(*idx.background_stats)
        calibrator = VectorCalibrator(bg)
        sims = np.array([e.payload.score for e in entries], dtype=np.float64)

        sorted_idx = np.argsort(1.0 - sims)
        sorted_dists = (1.0 - sims)[sorted_idx]
        sorted_w = VectorFallbackEstimator.distance_gap_weights(sorted_dists)
        weights = np.empty(len(sims), dtype=np.float64)
        weights[sorted_idx] = sorted_w

        calibrated = calibrator.calibrate(1.0 - sims, weights)

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
            .knn_calibrated(
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
            .knn_calibrated(
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
            .knn_calibrated(
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
                    .knn_calibrated(
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
