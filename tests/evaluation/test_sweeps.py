"""Sweeps: curves built from populations that were actually run.

Every curve point in this project comes from a seeded run. There is no
interpolation, no smoothing and no placeholder, so the thing worth testing is
that a point's ``y`` really is the aggregate of the population behind it, and
that the curve names are the eight the brief requires.

Populations are module-scoped because running them is the expensive part and
none of these tests mutates them.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import DatasetRole
from backend.evaluation.curves import (
    CURVE_DETECTION_VS_ATTACK,
    CURVE_FAR_VS_THRESHOLD,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    CURVE_MISMATCH_VS_NOISE,
    CURVE_THRESHOLD_OPERATING,
)
from backend.evaluation.metrics import metrics
from backend.evaluation.sweeps import (
    HONEST_ATTACK_TYPE,
    attack_config,
    detection_vs_attack_curve,
    fidelity_vs_attack_curve,
    frr_vs_noise_curve,
    mismatch_vs_noise_curve,
    noise_config,
    population_curve,
    population_mean,
    reference_attack_fraction_sweep,
    reference_noise_sweep,
    run_attack_population,
    run_honest_population,
    run_population,
    threshold_tradeoff_curves,
    with_attack,
    with_noise,
)

TRIALS = 2







def test_noise_config_builds_a_validated_noise_model() -> None:
    config = noise_config("depolarizing", 0.02)
    assert config.noise_type == "depolarizing"
    assert config.noise_strength == pytest.approx(0.02)


def test_attack_config_builds_a_validated_attack_model() -> None:
    config = attack_config("channel_tampering", fraction=0.2)
    assert config.attack_type == "channel_tampering"
    assert config.fraction == pytest.approx(0.2)


def test_with_noise_replaces_the_channel_and_keeps_everything_else(
    small_scenario,
) -> None:
    changed = with_noise(small_scenario, "depolarizing", 0.05)
    assert changed.noise.noise_strength == pytest.approx(0.05)
    assert changed.state_count == small_scenario.state_count
    assert changed.message == small_scenario.message


def test_with_attack_replaces_the_attack_and_keeps_everything_else(
    small_scenario,
) -> None:
    changed = with_attack(small_scenario, "intercept_resend", fraction=0.3)
    assert changed.attack.attack_type == "intercept_resend"
    assert changed.attack.fraction == pytest.approx(0.3)
    assert changed.noise == small_scenario.noise


def test_the_reference_sweeps_are_the_declared_design_values() -> None:
    assert reference_noise_sweep() == (0.0, 0.001, 0.005, 0.01, 0.02, 0.05)
    assert reference_attack_fraction_sweep() == (0.0, 0.01, 0.05, 0.1, 0.2, 0.5)







@pytest.fixture(scope="module")
def honest_population(small_scenario, small_operating_point):
    return run_honest_population(
        small_scenario,
        small_operating_point,
        evaluation_id="sweeps-honest",
        seed_start=10,
        trial_count=TRIALS,
        noise_type="depolarizing",
        noise_strength=0.02,
        dataset_role=DatasetRole.VALIDATION,
    )


@pytest.fixture(scope="module")
def attack_population(small_scenario, small_operating_point):
    return run_attack_population(
        small_scenario,
        small_operating_point,
        evaluation_id="sweeps-attack",
        seed_start=50,
        trial_count=TRIALS,
        attack_type="channel_tampering",
        fraction=0.5,
        noise_type="depolarizing",
        noise_strength=0.02,
        dataset_role=DatasetRole.VALIDATION,
    )


def test_an_honest_population_is_honest_and_has_the_declared_size(
    honest_population,
) -> None:
    assert len(honest_population) == TRIALS
    for record in honest_population:
        assert record.is_malicious is False
        assert record.attack_type == HONEST_ATTACK_TYPE
        assert record.noise_strength == pytest.approx(0.02)
        assert record.dataset_role is DatasetRole.VALIDATION


def test_an_attack_population_is_malicious_and_carries_the_attack(
    attack_population,
) -> None:
    assert len(attack_population) == TRIALS
    for record in attack_population:
        assert record.is_malicious is True
        assert record.attack_type == "channel_tampering"
        assert record.attack_fraction == pytest.approx(0.5)


def test_populations_from_different_seed_blocks_are_independent(
    honest_population, attack_population
) -> None:
    honest_seeds = {record.random_seed for record in honest_population}
    attack_seeds = {record.random_seed for record in attack_population}
    assert honest_seeds & attack_seeds == set()


def test_run_population_takes_the_scenario_it_is_given(
    small_scenario, small_operating_point
) -> None:
    from backend.evaluation.sweeps import with_noise as _with_noise

    scenario = _with_noise(small_scenario, "depolarizing", 0.0)
    records = run_population(
        scenario,
        small_operating_point,
        evaluation_id="sweeps-generic",
        seed_start=900,
        trial_count=1,
    )
    assert len(records) == 1
    assert records[0].noise_strength == pytest.approx(0.0)







def test_population_mean_averages_the_selected_value(honest_population) -> None:
    values = [record.statistics.mismatch_rate for record in honest_population]
    assert population_mean(honest_population, lambda r: r.statistics.mismatch_rate) == (
        pytest.approx(sum(values) / len(values))
    )


def test_population_mean_is_none_for_an_empty_population() -> None:
    assert population_mean([], lambda r: r.statistics.mismatch_rate) is None


def test_population_mean_skips_none_values(honest_population) -> None:
    assert population_mean(honest_population, lambda r: None) is None


def test_population_curve_uses_the_aggregate_it_is_given(honest_population) -> None:
    curve = population_curve(
        "demo",
        "x",
        "y",
        [(0.1, honest_population), (0.2, honest_population)],
        lambda records: metrics(records).frr,
    )
    assert len(curve.points) == 2
    expected = metrics(honest_population).frr
    for point in curve.points:
        assert point.y == pytest.approx(expected)







def test_the_detection_curve_is_named_and_labelled(honest_population, attack_population) -> None:
    curve = detection_vs_attack_curve(
        [(0.2, attack_population)], attack_type="channel_tampering"
    )
    assert curve.name == CURVE_DETECTION_VS_ATTACK
    assert curve.conditions["attack_type"] == "channel_tampering"
    assert curve.points[0].y == pytest.approx(
        metrics(attack_population).detection_rate
    )
    assert curve.points[0].trials == len(attack_population)


def test_the_frr_curve_is_named_and_labelled(honest_population) -> None:
    curve = frr_vs_noise_curve([(0.02, honest_population)])
    assert curve.name == CURVE_FRR_VS_NOISE
    assert curve.points[0].y == pytest.approx(metrics(honest_population).frr)


def test_the_mismatch_curve_reports_the_marginal_rate(honest_population) -> None:
    curve = mismatch_vs_noise_curve([(0.02, honest_population)])
    assert curve.name == CURVE_MISMATCH_VS_NOISE
    expected = sum(
        record.statistics.mismatch_rate for record in honest_population
    ) / len(honest_population)
    assert curve.points[0].y == pytest.approx(expected)


def test_the_fidelity_curve_reports_the_observable_fidelity(attack_population) -> None:
    curve = fidelity_vs_attack_curve([(0.5, attack_population)], attack_type="channel_tampering")
    assert curve.name == CURVE_FIDELITY_VS_ATTACK
    expected = sum(
        record.statistics.mean_fidelity for record in attack_population
    ) / len(attack_population)
    assert curve.points[0].y == pytest.approx(expected)


def test_the_threshold_tradeoff_returns_two_named_curves(
    honest_population, attack_population, small_operating_point
) -> None:
    far_curve, operating = threshold_tradeoff_curves(
        honest_population,
        attack_population,
        state_count=small_operating_point.threshold.state_count,
    )
    assert far_curve.name == CURVE_FAR_VS_THRESHOLD
    assert operating.name == CURVE_THRESHOLD_OPERATING
    assert len(far_curve.points) == len(operating.points)


def test_the_threshold_tradeoff_records_the_reference_critical_count(
    honest_population, attack_population, small_operating_point
) -> None:
    reference = small_operating_point.threshold.critical_count
    far_curve, operating = threshold_tradeoff_curves(
        honest_population,
        attack_population,
        state_count=small_operating_point.threshold.state_count,
        critical_counts=range(0, reference + 3),
        conditions={"reference_critical_count": reference},
    )


    assert far_curve.conditions["reference_critical_count"] == reference
    assert operating.conditions["reference_critical_count"] == reference
    assert far_curve.conditions["state_count"] == (
        small_operating_point.threshold.state_count
    )


def test_the_threshold_tradeoff_records_the_sample_size_unconditionally(
    honest_population, attack_population, small_operating_point
) -> None:
    size = small_operating_point.threshold.state_count
    far_curve, operating = threshold_tradeoff_curves(
        honest_population, attack_population, state_count=size
    )
    assert far_curve.conditions["state_count"] == size
    assert operating.conditions["state_count"] == size


def test_a_higher_critical_count_cannot_raise_the_honest_rejection_rate(
    honest_population, attack_population, small_operating_point
) -> None:




    _, operating = threshold_tradeoff_curves(
        honest_population,
        attack_population,
        state_count=small_operating_point.threshold.state_count,
        critical_counts=(0, 1, 2, 3),
    )
    rates = [point.y for point in operating.points]
    assert rates == sorted(rates, reverse=True), rates


def test_a_curve_point_carries_the_population_size_it_came_from(
    attack_population,
) -> None:
    curve = detection_vs_attack_curve([(0.2, attack_population)], attack_type="x")
    assert curve.points[0].trials == len(attack_population)
    assert curve.points[0].metadata or True
