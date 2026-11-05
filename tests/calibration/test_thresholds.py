"""Threshold derivation: sample-size dependence, traceability, and the guard.

The property the milestone cares about most is that a threshold is **not** a
constant. Every assertion about sample-size dependence is therefore about
``k_crit(N)`` and ``k_crit(N)/N`` moving in the right direction, not about any
particular value being right.

The mathematical expectations used here are computed with ``scipy.stats.binom``
inside the test, independently of the implementation's own call, so a change to
the implementation that broke the formula would fail rather than agree with
itself.
"""

from __future__ import annotations

import pytest
from scipy import stats

from backend.calibration.baseline import estimate_baseline
from backend.calibration.confidence import upper_bound
from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    CalibrationConfig,
    CalibrationObservation,
    DatasetRole,
    ThresholdConfig,
)
from backend.calibration.thresholds import (
    REFERENCE_THRESHOLD_METHOD,
    critical_count,
    derive_threshold,
    derive_threshold_table,
    expected_false_rejection_rate,
    rejection_probability,
)

ALPHA = 0.05


def _observation(seed: int, n_mismatch: int, n_valid: int) -> CalibrationObservation:
    return CalibrationObservation(
        experiment_id=f"obs-{seed}",
        random_seed=seed,
        state_count=n_valid,
        n_valid=n_valid,
        n_mismatch=n_mismatch,
        mismatch_rate=n_mismatch / n_valid,
        dataset_role=DatasetRole.CALIBRATION,
        analytic_match_probabilities=(0.99,) * n_valid,
        mean_fidelity=0.99,
    )


def _calibration(state_count: int, rate: float, sessions: int = 40):
    """Return a calibration result whose pooled rate is about ``rate``."""
    mismatches = round(rate * state_count)
    config = CalibrationConfig(
        config_id="t",
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=state_count,
        measurement_mode="sampled",
        shot_count=1,
        statistic=STATISTIC_MISMATCH_RATE,
        confidence=0.95,
        seed_start=0,
        session_count=sessions,
        dataset_role=DatasetRole.CALIBRATION,
    ).validate()
    observations = [
        _observation(index, mismatches, state_count) for index in range(sessions)
    ]
    return estimate_baseline(config, observations)







def test_critical_count_is_the_binomial_quantile() -> None:
    p_upper, n, alpha = 0.011, 500, 0.025
    expected = int(stats.binom.ppf(1.0 - alpha, n, p_upper))
    assert critical_count(p_upper, n, alpha=alpha) == expected


def test_critical_count_is_monotone_in_the_upper_bound() -> None:
    counts = [critical_count(p, 500, alpha=0.025) for p in (0.001, 0.01, 0.05, 0.2)]
    assert counts == sorted(counts)


def test_critical_count_is_monotone_in_the_sample_size() -> None:
    counts = [critical_count(0.01, n, alpha=0.025) for n in (100, 250, 500, 1000)]
    assert counts == sorted(counts)


def test_critical_count_with_a_zero_upper_bound_is_zero() -> None:


    assert critical_count(0.0, 500, alpha=0.025) == 0


def test_critical_count_never_exceeds_the_sample_size() -> None:
    assert critical_count(1.0, 50, alpha=0.5) == 50


@pytest.mark.parametrize("bad_alpha", [0.0, 1.0, -0.1, 1.5])
def test_invalid_alpha_is_refused(bad_alpha: float) -> None:
    with pytest.raises(ValueError):
        critical_count(0.01, 100, alpha=bad_alpha)


@pytest.mark.parametrize("bad_n", [0, -5, True, 1.5])
def test_invalid_sample_size_is_refused(bad_n) -> None:
    with pytest.raises(ValueError):
        critical_count(0.01, bad_n, alpha=0.025)


@pytest.mark.parametrize("bad_p", [-0.1, 1.1])
def test_invalid_upper_bound_is_refused(bad_p: float) -> None:
    with pytest.raises(ValueError):
        critical_count(bad_p, 100, alpha=0.025)







def test_rejection_probability_is_the_upper_binomial_tail() -> None:
    expected = float(1.0 - stats.binom.cdf(11, 500, 0.02))
    assert rejection_probability(0.02, 500, 11) == pytest.approx(expected, abs=1e-15)


def test_rejection_probability_rises_with_the_alternative_rate() -> None:
    rates = [rejection_probability(p, 500, 11) for p in (0.01, 0.02, 0.05, 0.2)]
    assert rates == sorted(rates)


def test_rejection_probability_never_exceeds_one() -> None:
    assert 0.0 <= rejection_probability(1.0, 100, 0) <= 1.0


def test_expected_false_rejection_rate_at_the_bound_is_bounded_by_alpha() -> None:


    for n in (100, 250, 500, 1000):
        critical = critical_count(0.01, n, alpha=0.025)
        assert expected_false_rejection_rate(0.01, n, critical) <= 0.025 + 1e-9







def test_derived_threshold_is_traceable_to_its_calibration() -> None:
    calibration = _calibration(500, 0.01)
    threshold = derive_threshold(calibration)
    assert threshold.state_count == 500
    assert threshold.config.method == REFERENCE_THRESHOLD_METHOD
    assert threshold.calibration_role is DatasetRole.CALIBRATION
    assert threshold.calibration_session_count == calibration.session_count
    assert threshold.calibration_total_valid == calibration.total_valid
    assert threshold.calibration_total_mismatch == calibration.total_mismatch
    assert threshold.calibration_pooled_rate == calibration.pooled_rate
    assert threshold.calibration_fingerprint == calibration.config.fingerprint()
    assert threshold.threshold_rate == pytest.approx(
        threshold.critical_count / threshold.state_count, abs=1e-15
    )



    expected = upper_bound(
        calibration.total_mismatch,
        calibration.total_valid,
        confidence=1.0 - threshold.config.calibration_alpha,
    ).upper
    assert threshold.p_upper == pytest.approx(expected, abs=1e-15)
    assert threshold.p_upper > calibration.pooled_rate


def test_the_even_split_makes_p_upper_coincide_with_the_two_sided_upper_end() -> None:





    calibration = _calibration(500, 0.01)
    threshold = derive_threshold(
        calibration,
        config=ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.5),
    )
    assert threshold.config.calibration_alpha == pytest.approx(0.025, abs=1e-15)
    assert threshold.p_upper == pytest.approx(
        calibration.interval.upper, abs=1e-15
    )


    uneven = derive_threshold(
        calibration,
        config=ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.2),
    )
    assert uneven.p_upper != pytest.approx(calibration.interval.upper, abs=1e-12)
    assert uneven.p_upper > threshold.p_upper


def test_threshold_rate_falls_as_the_sample_size_grows() -> None:



    calibration = _calibration(500, 0.01)
    table = derive_threshold_table(calibration, [100, 250, 500, 1000, 2500, 5000])
    rates = [item.threshold_rate for item in table]
    assert rates == sorted(rates, reverse=True)
    counts = [item.critical_count for item in table]
    assert counts == sorted(counts)


def test_the_same_threshold_cannot_be_reused_at_another_size() -> None:
    threshold = derive_threshold(_calibration(500, 0.01))
    assert threshold.rejects(threshold.critical_count, 500) is False
    assert threshold.rejects(threshold.critical_count + 1, 500) is True
    with pytest.raises(ValueError, match="not defined for"):
        threshold.rejects(5, 250)


def test_a_threshold_can_be_derived_for_another_size_from_the_same_calibration() -> None:
    calibration = _calibration(500, 0.01)
    small = derive_threshold(calibration, state_count=100)
    large = derive_threshold(calibration, state_count=5000)
    assert small.state_count == 100
    assert large.state_count == 5000
    assert small.threshold_rate > large.threshold_rate


def test_threshold_config_validation() -> None:
    config = ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.5).validate()
    assert config.calibration_alpha == pytest.approx(0.025, abs=1e-15)
    assert config.evaluation_alpha == pytest.approx(0.025, abs=1e-15)

    assert config.calibration_alpha + config.evaluation_alpha == pytest.approx(
        config.alpha, abs=1e-15
    )


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 2.0])
def test_threshold_config_refuses_invalid_alpha(alpha: float) -> None:
    with pytest.raises(ValueError):
        ThresholdConfig(alpha=alpha).validate()


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1, 1.5])
def test_threshold_config_refuses_an_invalid_split(fraction: float) -> None:
    with pytest.raises(ValueError):
        ThresholdConfig(calibration_alpha_fraction=fraction).validate()


def test_the_two_halves_of_the_budget_pull_the_threshold_in_opposite_directions() -> None:





    calibration = _calibration(500, 0.01)

    conservative_bound = derive_threshold(
        calibration, config=ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.1)
    )
    generous_bound = derive_threshold(
        calibration, config=ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.9)
    )
    assert generous_bound.p_upper < conservative_bound.p_upper

    strict_quantile = derive_threshold(
        calibration, config=ThresholdConfig(alpha=0.02, calibration_alpha_fraction=0.5)
    )
    loose_quantile = derive_threshold(
        calibration, config=ThresholdConfig(alpha=0.20, calibration_alpha_fraction=0.5)
    )


    assert loose_quantile.config.evaluation_alpha > strict_quantile.config.evaluation_alpha


def test_a_larger_evaluation_alpha_lowers_the_critical_count() -> None:



    p_upper, n = 0.0115, 500
    counts = [critical_count(p_upper, n, alpha=a) for a in (0.005, 0.025, 0.10)]
    assert counts == sorted(counts, reverse=True)
    assert counts[-1] < counts[0]


def test_the_threshold_config_is_recorded_in_the_result() -> None:
    config = ThresholdConfig(alpha=0.10, calibration_alpha_fraction=0.25)
    threshold = derive_threshold(_calibration(500, 0.01), config=config)
    assert threshold.config.alpha == 0.10
    assert threshold.config.calibration_alpha_fraction == 0.25
    assert threshold.to_dict()["config"]["alpha"] == 0.10
