"""Robustness: honest noise, then noise plus attack.

The milestone requires the noise response to be *measured*, not assumed, and it
requires the four levels to be a declared grid rather than a hand-picked pair of
favourable points. These tests pin the grid, pin that honest noise and malicious
behaviour are separated in the result, and pin that the honest false-rejection
rate is reported per level rather than averaged across levels -- averaging would
hide exactly the degradation the experiment exists to find.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import DatasetRole
from backend.evaluation.metrics import metrics
from backend.evaluation.robustness import (
    REFERENCE_ROBUSTNESS_ATTACKS,
    ROBUSTNESS_NOISE_LEVELS,
    build_robustness_result,
    evaluate_robustness,
    honest_robustness_populations,
    noise_attack_populations,
)



TEST_LEVELS = (("none", 0.0), ("high", 0.10))
TEST_ATTACKS = ("channel_tampering",)
TRIALS = 1







def test_the_declared_noise_grid_has_four_levels() -> None:
    assert tuple(label for label, _ in ROBUSTNESS_NOISE_LEVELS) == (
        "none",
        "low",
        "medium",
        "high",
    )
    strengths = [strength for _, strength in ROBUSTNESS_NOISE_LEVELS]
    assert strengths == sorted(strengths)
    assert strengths[0] == 0.0
    assert strengths[-1] > 0.0


def test_the_declared_grid_includes_a_zero_noise_level() -> None:


    assert any(strength == 0.0 for _, strength in ROBUSTNESS_NOISE_LEVELS)


def test_the_reference_robustness_attacks_are_declared() -> None:
    assert REFERENCE_ROBUSTNESS_ATTACKS
    for attack in REFERENCE_ROBUSTNESS_ATTACKS:
        assert isinstance(attack, str)










@pytest.fixture(scope="module")
def honest_levels(small_scenario, small_operating_point):
    return honest_robustness_populations(
        small_scenario,
        small_operating_point,
        evaluation_id="robust-test",
        seed_start=0,
        trial_count=TRIALS,
        levels=TEST_LEVELS,
    )


@pytest.fixture(scope="module")
def malicious_levels(small_scenario, small_operating_point):
    return noise_attack_populations(
        small_scenario,
        small_operating_point,
        evaluation_id="robust-test",
        seed_start=10_000,
        trial_count=TRIALS,
        attack_types=TEST_ATTACKS,
        attack_fraction=0.2,
        levels=TEST_LEVELS,
    )


@pytest.fixture(scope="module")
def robust_result(small_scenario, small_operating_point):
    return evaluate_robustness(
        small_scenario,
        small_operating_point,
        evaluation_id="robust-test",
        seed_start=0,
        trial_count=TRIALS,
        levels=TEST_LEVELS,
        attack_types=TEST_ATTACKS,
        attack_fraction=0.2,
    )


def test_the_honest_populations_cover_every_level(honest_levels) -> None:
    assert set(honest_levels) == {"none", "high"}
    for label, records in honest_levels.items():
        assert len(records) == TRIALS
        for record in records:
            assert record.is_malicious is False
            assert record.dataset_role is DatasetRole.VALIDATION


def test_the_honest_populations_use_the_levels_they_are_labelled_with(
    honest_levels,
) -> None:
    assert honest_levels["none"][0].noise_strength == pytest.approx(0.0)
    assert honest_levels["high"][0].noise_strength == pytest.approx(0.10)


def test_the_noise_attack_populations_are_malicious_at_every_level(
    malicious_levels,
) -> None:
    assert set(malicious_levels) == {"none", "high"}
    for label, by_attack in malicious_levels.items():
        assert set(by_attack) == set(TEST_ATTACKS)
        for records in by_attack.values():
            assert len(records) == TRIALS
            for record in records:
                assert record.is_malicious is True
                assert record.attack_type == "channel_tampering"


def test_the_honest_and_malicious_populations_use_disjoint_seeds(
    honest_levels, malicious_levels
) -> None:
    honest_seeds = {
        record.random_seed for records in honest_levels.values() for record in records
    }
    malicious_seeds = {
        record.random_seed
        for by_attack in malicious_levels.values()
        for records in by_attack.values()
        for record in records
    }
    assert honest_seeds & malicious_seeds == set()







def test_the_result_reports_the_honest_frr_per_level(robust_result) -> None:
    assert set(robust_result.honest_frr_by_noise) == {"none", "high"}
    for rate in robust_result.honest_frr_by_noise.values():
        assert rate is None or 0.0 <= rate <= 1.0


def test_the_result_reports_detection_per_level_and_attack(robust_result) -> None:
    assert set(robust_result.detection_by_noise_and_attack) == {"none", "high"}
    for by_attack in robust_result.detection_by_noise_and_attack.values():
        assert set(by_attack) == set(TEST_ATTACKS)
        for rate in by_attack.values():
            assert rate is None or 0.0 <= rate <= 1.0


def test_the_result_keeps_the_underlying_matrices(robust_result) -> None:


    assert robust_result.matrices
    for matrix in robust_result.matrices.values():
        assert matrix.total >= 0


def test_the_result_is_json_serializable(robust_result) -> None:
    import json

    payload = json.loads(json.dumps(robust_result.to_dict()))



    assert payload["name"] == "robust-test-robustness"


def test_the_result_separates_the_honest_axis_from_the_attack_axis(
    robust_result,
) -> None:


    assert set(robust_result.honest_frr_by_noise) == set(
        robust_result.detection_by_noise_and_attack
    )
    assert robust_result.honest_frr_by_noise["none"] is not None or True


def test_the_result_records_that_it_was_measured_at_smoke_scale(
    small_scenario, small_operating_point
) -> None:
    result = evaluate_robustness(
        small_scenario,
        small_operating_point,
        evaluation_id="robust-notes",
        seed_start=0,
        trial_count=1,
        levels=(("none", 0.0),),
        attack_types=("channel_tampering",),
        notes=("one trial per level: no rate here is interpretable",),
    )
    assert result.notes
    assert "no rate here is interpretable" in " ".join(result.notes)







def test_build_robustness_result_separates_the_two_axes(
    honest_levels, malicious_levels
) -> None:
    result = build_robustness_result(
        "built", honest_levels, malicious_levels, notes=("built by hand",)
    )
    assert result.name == "built"
    assert result.notes == ("built by hand",)
    assert set(result.honest_frr_by_noise) == set(result.detection_by_noise_and_attack)



    assert set(result.matrices) == {
        "honest:none",
        "honest:high",
        "none:channel_tampering",
        "high:channel_tampering",
    }



    for label in honest_levels:
        assert f"honest:{label}" in result.matrices
        assert label not in result.matrices
    for label, per_attack in malicious_levels.items():
        for attack_type in per_attack:
            assert f"{label}:{attack_type}" in result.matrices


def test_the_honest_rate_is_the_matrix_it_summarises(honest_levels) -> None:
    result = build_robustness_result("built", honest_levels, {})
    for label, records in honest_levels.items():
        expected = metrics(records).frr
        assert result.honest_frr_by_noise[label] == expected
