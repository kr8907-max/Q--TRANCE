"""Threat bounds: exceedance, separation, and prediction.

These tests verify that the M6 threat-bound functions are deterministic,
mathematically sound, and never conflate a confidence interval with a security
parameter.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import ThresholdResult, ThresholdConfig, DatasetRole
from backend.security.threat_bounds import (
    ThresholdExceedance,
    StatisticalSeparation,
    HonestPrediction,
    threshold_exceedance,
    statistical_separation,
    honest_prediction,
    exceedance_probability,
)


def _make_threshold(
    state_count: int = 100,
    critical_count: int = 3,
    p_upper: float = 0.02,
) -> ThresholdResult:
    """Return a minimal threshold for testing."""
    return ThresholdResult(
        state_count=state_count,
        p_upper=p_upper,
        critical_count=critical_count,
        threshold_rate=critical_count / state_count,
        config=ThresholdConfig(),
        calibration_fingerprint="test",
        calibration_session_count=10,
        calibration_total_valid=1000,
        calibration_total_mismatch=10,
        calibration_pooled_rate=0.01,
        calibration_role=DatasetRole.CALIBRATION,
    )







def test_exceeds_when_count_is_strictly_greater() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    result = threshold_exceedance(4, 100, t)
    assert result.exceeds is True
    assert result.margin == 1
    assert result.margin_rate == pytest.approx(0.01)


def test_does_not_exceed_at_exact_critical_count() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    result = threshold_exceedance(3, 100, t)
    assert result.exceeds is False
    assert result.margin == 0
    assert result.margin_rate == pytest.approx(0.0)


def test_negative_margin_when_below_threshold() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    result = threshold_exceedance(1, 100, t)
    assert result.exceeds is False
    assert result.margin == -2
    assert result.margin_rate == pytest.approx(-0.02)


def test_threshold_exceedance_refuses_wrong_sample_size() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    with pytest.raises(ValueError, match="derived for N=100"):
        threshold_exceedance(4, 200, t)


def test_threshold_exceedance_serialises() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    result = threshold_exceedance(5, 100, t)
    payload = result.to_dict()
    assert payload["exceeds"] is True
    assert payload["margin"] == 2
    assert payload["margin_rate"] == pytest.approx(0.02)
    assert isinstance(payload["notes"], list)







def test_positive_separation_exceeds_honest_bound() -> None:
    result = statistical_separation(0.05, 0.02)
    assert result.separation_rate == pytest.approx(0.03)
    assert "exceeds" in result.conclusion.lower()
    assert "not a forgery bound" in result.conclusion.lower()


def test_negative_separation_is_within_bound() -> None:
    result = statistical_separation(0.01, 0.02)
    assert result.separation_rate == pytest.approx(-0.01)
    assert "within" in result.conclusion.lower()
    assert "not a proof of honesty" in result.conclusion.lower()


def test_zero_separation_is_at_boundary() -> None:
    result = statistical_separation(0.02, 0.02)
    assert result.separation_rate == pytest.approx(0.0)
    assert "boundary" in result.conclusion.lower()


def test_statistical_separation_serialises() -> None:
    result = statistical_separation(0.05, 0.02, notes=("test note",))
    payload = result.to_dict()
    assert payload["observed_rate"] == pytest.approx(0.05)
    assert payload["honest_upper"] == pytest.approx(0.02)
    assert payload["separation_rate"] == pytest.approx(0.03)
    assert "test note" in payload["notes"]







def test_prediction_interval_is_within_sample_size() -> None:
    t = _make_threshold(state_count=100, critical_count=3, p_upper=0.02)
    pred = honest_prediction(t, confidence=0.95)
    assert 0 <= pred.predicted_min_mismatch <= pred.predicted_max_mismatch <= 100
    assert pred.sample_size == 100
    assert pred.confidence == pytest.approx(0.95)


def test_prediction_interval_is_within_sample_bounds() -> None:
    t = _make_threshold(state_count=500, critical_count=10, p_upper=0.0108)
    pred = honest_prediction(t, confidence=0.95)
    assert 0 <= pred.predicted_min_mismatch <= pred.predicted_max_mismatch <= 500
    assert pred.confidence == pytest.approx(0.95)


def test_prediction_interval_serialises() -> None:
    t = _make_threshold(state_count=100, critical_count=3)
    pred = honest_prediction(t)
    payload = pred.to_dict()
    assert payload["sample_size"] == 100
    assert isinstance(payload["notes"], list)


def test_prediction_upper_end_matches_the_threshold_critical_count() -> None:





    t = _make_threshold(state_count=500, critical_count=10, p_upper=0.0108)
    pred = honest_prediction(t, confidence=0.95)
    assert pred.predicted_max_mismatch == t.critical_count

    assert 0 <= pred.predicted_min_mismatch <= pred.predicted_max_mismatch <= 500







def test_exceedance_probability_is_small_when_count_exceeds_critical() -> None:


    p = exceedance_probability(6, 100, 0.02)
    assert 0.0 < p < 0.05


def test_exceedance_probability_is_large_when_count_is_low() -> None:
    p = exceedance_probability(1, 100, 0.02)
    assert p > 0.5


def test_exceedance_probability_is_one_at_zero() -> None:
    assert exceedance_probability(0, 100, 0.02) == pytest.approx(1.0)


def test_exceedance_probability_raises_on_invalid_counts() -> None:
    with pytest.raises(ValueError):
        exceedance_probability(5, 3, 0.02)







def test_no_bound_is_marked_as_cryptographic() -> None:



    from backend.security.models import FiniteSizeBound, BoundKind, BoundSidedness

    bound = FiniteSizeBound(
        kind=BoundKind.EXACT_CLOPPER_PEARSON,
        sidedness=BoundSidedness.UPPER,
        statistic="mismatch_rate",
        sample_size=100,
        successes=2,
        confidence=0.95,
        lower=0.0,
        upper=0.05,
        point_estimate=0.02,
        method="test",
        citation="test",
        assumptions=(),
    )
    assert bound.is_cryptographic_security_bound is False
    assert bound.to_dict()["is_cryptographic_security_bound"] is False
