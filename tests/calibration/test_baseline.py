"""The honest null model, its homogeneity diagnostic, and honest-only estimation.

The numbers asserted here come from the channel algebra rather than from a
recorded run, so the tolerances are machine epsilon (``abs=1e-15``) where the
arithmetic is exact and stated explicitly where it is not.
"""

from __future__ import annotations

import pytest
from scipy import stats

from backend.calibration.baseline import (
    DEFAULT_PROJECTIVE_TOLERANCE,
    build_homogeneity_diagnostic,
    estimate_baseline,
    implied_mismatch_probability,
)
from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    CalibrationConfig,
    CalibrationObservation,
    DatasetRole,
)


def _config(**overrides) -> CalibrationConfig:
    payload = dict(
        config_id="test",
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=4,
        measurement_mode="sampled",
        shot_count=1,
        statistic=STATISTIC_MISMATCH_RATE,
        confidence=0.95,
        seed_start=0,
        session_count=2,
        dataset_role=DatasetRole.CALIBRATION,
    )
    payload.update(overrides)
    return CalibrationConfig(**payload).validate()


def _observation(seed: int, n_mismatch: int, *, n_valid: int = 4, **overrides):
    payload = dict(
        experiment_id=f"obs-{seed}",
        random_seed=seed,
        state_count=n_valid,
        n_valid=n_valid,
        n_mismatch=n_mismatch,
        mismatch_rate=n_mismatch / n_valid,
        dataset_role=DatasetRole.CALIBRATION,
        timestamp="2026-01-01T00:00:00+00:00",
        analytic_match_probabilities=(0.99,) * n_valid,
        mean_fidelity=0.99,
        per_basis_mismatch_rates={"Z": 0.0, "X": 0.0, "Y": 0.0},
    )
    payload.update(overrides)
    return CalibrationObservation(**payload)







def test_projective_mode_implies_a_deterministic_zero_or_one() -> None:



    assert (
        implied_mismatch_probability(
            1.0, measurement_mode="projective-analytic", shot_count=1
        )
        == 0.0
    )
    assert (
        implied_mismatch_probability(
            0.99, measurement_mode="projective-analytic", shot_count=1
        )
        == 1.0
    )
    assert (
        implied_mismatch_probability(
            1.0 - DEFAULT_PROJECTIVE_TOLERANCE / 2.0,
            measurement_mode="projective-analytic",
            shot_count=1,
        )
        == 0.0
    )


@pytest.mark.parametrize("q", [0.0, 0.25, 0.5, 0.75, 0.99, 1.0])
def test_single_shot_sampled_mode_is_exactly_one_minus_q(q: float) -> None:

    assert implied_mismatch_probability(
        q, measurement_mode="sampled", shot_count=1
    ) == pytest.approx(1.0 - q, abs=1e-15)


@pytest.mark.parametrize("shots", [2, 3, 8, 1024])
def test_multi_shot_sampled_mode_matches_the_majority_vote_tail(shots: int) -> None:
    q = 0.9
    expected = float(stats.binom.cdf((shots + 1) // 2 - 1, shots, q))
    assert implied_mismatch_probability(
        q, measurement_mode="sampled", shot_count=shots
    ) == pytest.approx(expected, abs=1e-15)


def test_many_shots_suppress_the_implied_mismatch_probability() -> None:


    assert implied_mismatch_probability(
        0.99, measurement_mode="sampled", shot_count=1024
    ) == pytest.approx(0.0, abs=1e-12)


def test_a_fair_overlap_gives_a_fair_coin_for_odd_shot_counts() -> None:


    for shots in (1, 3, 5, 1023):
        assert implied_mismatch_probability(
            0.5, measurement_mode="sampled", shot_count=shots
        ) == pytest.approx(0.5, abs=1e-12)


def test_an_even_shot_count_makes_the_majority_tie_break_slightly_asymmetric() -> None:




    shots = 1024
    expected = float(stats.binom.cdf(shots // 2 - 1, shots, 0.5))
    observed = implied_mismatch_probability(
        0.5, measurement_mode="sampled", shot_count=shots
    )
    assert observed == pytest.approx(expected, abs=1e-15)
    assert observed < 0.5


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_out_of_range_probabilities_are_refused(bad: float) -> None:
    with pytest.raises(ValueError):
        implied_mismatch_probability(bad, measurement_mode="sampled", shot_count=1)


@pytest.mark.parametrize("bad_shots", [0, -1, True, 1.5])
def test_invalid_shot_counts_are_refused(bad_shots) -> None:
    with pytest.raises(ValueError):
        implied_mismatch_probability(
            0.5, measurement_mode="sampled", shot_count=bad_shots
        )







def test_identical_probabilities_are_homogeneous() -> None:
    diagnostic = build_homogeneity_diagnostic([0.01, 0.01, 0.01, 0.01])
    assert diagnostic.homogeneous is True
    assert diagnostic.spread == 0.0
    assert diagnostic.state_count == 4
    assert diagnostic.mean == pytest.approx(0.01, abs=1e-15)


def test_differing_probabilities_are_not_homogeneous() -> None:
    diagnostic = build_homogeneity_diagnostic([0.0, 0.01, 0.05])
    assert diagnostic.homogeneous is False
    assert diagnostic.minimum == 0.0
    assert diagnostic.maximum == 0.05
    assert diagnostic.spread == pytest.approx(0.05, abs=1e-15)
    assert any("Poisson-binomial" in note for note in diagnostic.notes)


def test_empty_diagnostic_is_undefined_not_homogeneous() -> None:
    diagnostic = build_homogeneity_diagnostic([])
    assert diagnostic.homogeneous is None
    assert diagnostic.mean is None
    assert diagnostic.state_count == 0







def test_pooled_rate_is_the_total_mismatch_share() -> None:
    config = _config()
    result = estimate_baseline(config, [_observation(0, 1), _observation(1, 0)])
    assert result.total_valid == 8
    assert result.total_mismatch == 1
    assert result.pooled_rate == pytest.approx(1 / 8, abs=1e-15)
    assert result.session_count == 2


def test_interval_and_upper_bound_are_present_and_ordered() -> None:
    config = _config()
    result = estimate_baseline(config, [_observation(0, 1), _observation(1, 0)])
    assert result.interval is not None
    assert result.upper_bound is not None
    assert result.interval.lower <= result.pooled_rate <= result.interval.upper
    assert result.upper_bound.lower == 0.0


    assert result.upper_bound.upper < result.interval.upper


def test_an_empty_dataset_is_refused() -> None:
    with pytest.raises(ValueError):
        estimate_baseline(_config(), [])


def test_an_observation_with_a_different_role_is_refused() -> None:



    rogue = _observation(0, 0, dataset_role=DatasetRole.FINAL_EVALUATION)
    with pytest.raises(ValueError, match="CALIBRATION"):
        rogue.validate()
    with pytest.raises(ValueError, match="CALIBRATION"):
        estimate_baseline(_config(), [rogue])


def test_an_observation_with_a_different_sample_size_is_refused() -> None:
    rogue = _observation(0, 0, n_valid=8)
    with pytest.raises(ValueError, match="state_count"):
        estimate_baseline(_config(), [rogue])


def test_a_non_calibration_configuration_is_refused() -> None:
    with pytest.raises(ValueError):
        CalibrationConfig(
            config_id="x",
            protocol_version="RQDS-TP-1.0",
            noise_type="depolarizing",
            noise_strength=0.0,
            state_count=4,
            measurement_mode="sampled",
            shot_count=1,
            statistic=STATISTIC_MISMATCH_RATE,
            confidence=0.95,
            seed_start=0,
            session_count=1,
            dataset_role=DatasetRole.VALIDATION,
        ).validate()


def test_mismatch_rate_must_agree_with_the_counts() -> None:
    with pytest.raises(ValueError, match="mismatch_rate"):
        _observation(0, 1, mismatch_rate=0.75).validate()


def test_notes_record_that_the_baseline_is_honest_only() -> None:
    result = estimate_baseline(_config(), [_observation(0, 0)])
    assert any("honest sessions only" in note for note in result.notes)
    assert any("Bernoulli" in note for note in result.notes)
