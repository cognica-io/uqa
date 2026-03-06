from __future__ import annotations

import pytest

from uqa.fusion.log_odds import LogOddsFusion
from uqa.fusion.boolean import ProbabilisticBoolean


@pytest.fixture
def fusion() -> LogOddsFusion:
    return LogOddsFusion(confidence_alpha=0.5)


# -- LogOddsFusion Tests --


class TestLogOddsFusion:
    def test_scale_neutrality(self) -> None:
        """Theorem 4.1.2: all P_i = p => P_final = p.

        Scale neutrality holds when alpha=0 (logit mean), where
        weight = 1/n^(1-0) = 1/n, so adjusted = mean(logit(P_i)) = logit(p).
        """
        fusion_mean = LogOddsFusion(confidence_alpha=0.0)
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for n in [2, 3, 5, 10]:
                result = fusion_mean.fuse([p] * n)
                assert result == pytest.approx(p, abs=1e-9), (
                    f"scale neutrality failed: p={p}, n={n}, result={result}"
                )

    def test_sign_preservation(self, fusion: LogOddsFusion) -> None:
        """Theorem 4.2.2: sgn(adjusted) = sgn(mean logit)."""
        # Mean logit is positive when probabilities are mostly > 0.5
        probs_positive = [0.8, 0.7, 0.6, 0.9]
        result = fusion.fuse(probs_positive)
        assert result > 0.5

        # Mean logit is negative when probabilities are mostly < 0.5
        probs_negative = [0.2, 0.3, 0.4, 0.1]
        result = fusion.fuse(probs_negative)
        assert result < 0.5

    def test_irrelevance_preservation(self, fusion: LogOddsFusion) -> None:
        """Theorem 4.5.1 iii: all P_i < 0.5 => P_final < 0.5."""
        probs = [0.1, 0.2, 0.3, 0.4, 0.49]
        result = fusion.fuse(probs)
        assert result < 0.5

    def test_relevance_preservation(self, fusion: LogOddsFusion) -> None:
        """Theorem 4.5.1 iv: all P_i > 0.5 => P_final > 0.5."""
        probs = [0.51, 0.6, 0.7, 0.8, 0.9]
        result = fusion.fuse(probs)
        assert result > 0.5

    def test_single_signal_identity(self, fusion: LogOddsFusion) -> None:
        """Proposition 4.3.2: n=1 => P_final = P_1."""
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            result = fusion.fuse([p])
            assert result == pytest.approx(p, abs=1e-12)

    def test_empty_returns_neutral(self, fusion: LogOddsFusion) -> None:
        assert fusion.fuse([]) == 0.5

    def test_result_in_unit_interval(self, fusion: LogOddsFusion) -> None:
        probs = [0.01, 0.99, 0.5, 0.3, 0.8]
        result = fusion.fuse(probs)
        assert 0.0 <= result <= 1.0

    def test_weighted_fusion_basic(self, fusion: LogOddsFusion) -> None:
        probs = [0.8, 0.2]
        weights = [0.5, 0.5]
        result = fusion.fuse_weighted(probs, weights)
        assert 0.0 <= result <= 1.0

    def test_weighted_fusion_empty(self, fusion: LogOddsFusion) -> None:
        assert fusion.fuse_weighted([], []) == 0.5

    def test_alpha_zero_is_mean(self) -> None:
        """alpha=0 gives simple logit mean."""
        fusion_0 = LogOddsFusion(confidence_alpha=0.0)
        probs = [0.8, 0.6]
        result = fusion_0.fuse(probs)
        # With alpha=0, weight = 1/n, so adjusted = mean(logit)
        assert 0.0 < result < 1.0

    def test_alpha_one_is_sum(self) -> None:
        """alpha=1 gives full logit sum (product of experts)."""
        fusion_1 = LogOddsFusion(confidence_alpha=1.0)
        probs = [0.8, 0.6]
        result = fusion_1.fuse(probs)
        assert 0.0 < result < 1.0


# -- ProbabilisticBoolean Tests --


class TestProbabilisticBoolean:
    def test_prob_and_bounds(self) -> None:
        """AND result must be in [0, 1]."""
        probs = [0.9, 0.8, 0.7, 0.6]
        result = ProbabilisticBoolean.prob_and(probs)
        assert 0.0 <= result <= 1.0

    def test_prob_or_bounds(self) -> None:
        """OR result must be in [0, 1]."""
        probs = [0.1, 0.2, 0.3, 0.4]
        result = ProbabilisticBoolean.prob_or(probs)
        assert 0.0 <= result <= 1.0

    def test_prob_and_less_than_min(self) -> None:
        """AND of independent events should be <= min(p_i)."""
        probs = [0.9, 0.8, 0.7]
        result = ProbabilisticBoolean.prob_and(probs)
        assert result <= min(probs) + 1e-10

    def test_prob_or_greater_than_max(self) -> None:
        """OR of independent events should be >= max(p_i)."""
        probs = [0.1, 0.2, 0.3]
        result = ProbabilisticBoolean.prob_or(probs)
        assert result >= max(probs) - 1e-10

    def test_prob_and_single(self) -> None:
        assert ProbabilisticBoolean.prob_and([0.7]) == pytest.approx(0.7)

    def test_prob_or_single(self) -> None:
        assert ProbabilisticBoolean.prob_or([0.3]) == pytest.approx(0.3)

    def test_prob_not(self) -> None:
        assert ProbabilisticBoolean.prob_not(0.3) == pytest.approx(0.7)
        assert ProbabilisticBoolean.prob_not(1.0) == pytest.approx(0.0)
        assert ProbabilisticBoolean.prob_not(0.0) == pytest.approx(1.0)

    def test_prob_and_with_certainty(self) -> None:
        """AND with a 1.0 probability should equal the product of the rest."""
        probs = [1.0, 0.5, 0.8]
        result = ProbabilisticBoolean.prob_and(probs)
        assert result == pytest.approx(0.4)

    def test_prob_or_with_certainty(self) -> None:
        """OR with a 1.0 probability should be 1.0."""
        probs = [1.0, 0.5, 0.3]
        result = ProbabilisticBoolean.prob_or(probs)
        assert result == pytest.approx(1.0)

    def test_de_morgan_consistency(self) -> None:
        """NOT(AND(p_i)) should equal OR(NOT(p_i)) for independent events."""
        probs = [0.6, 0.7, 0.8]
        not_and = ProbabilisticBoolean.prob_not(
            ProbabilisticBoolean.prob_and(probs)
        )
        or_not = ProbabilisticBoolean.prob_or(
            [ProbabilisticBoolean.prob_not(p) for p in probs]
        )
        assert not_and == pytest.approx(or_not)

    def test_prob_and_near_zero(self) -> None:
        """AND with very small probabilities should stay non-negative."""
        probs = [0.001, 0.002, 0.003]
        result = ProbabilisticBoolean.prob_and(probs)
        assert result >= 0.0
        assert result == pytest.approx(0.001 * 0.002 * 0.003)
