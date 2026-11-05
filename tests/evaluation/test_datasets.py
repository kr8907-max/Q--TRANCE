"""Dataset construction, and the roles that keep the three sets apart.

The calibration dataset is honest-only *by construction*: the function that
builds it configures no attack, and the record type it produces has no field an
attack label could occupy. These tests pin that, and pin the seed bookkeeping
that makes "independent" a property of the code rather than a claim.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import DatasetRole
from backend.evaluation.datasets import (
    DEFAULT_CALIBRATION_CONFIDENCE,
    SEED_BLOCK_SIZE,
    assert_disjoint_seeds,
    build_calibration_dataset,
    honest_observation,
)







def test_an_honest_observation_is_a_calibration_record(small_scenario) -> None:
    observation = honest_observation(
        small_scenario,
        seed=11,
        experiment_id="obs-test",
        dataset_role=DatasetRole.CALIBRATION,
        noise_type="depolarizing",
        noise_strength=0.0,
    )
    observation.validate()
    assert observation.random_seed == 11
    assert observation.experiment_id == "obs-test-s11"
    assert observation.dataset_role is DatasetRole.CALIBRATION
    assert observation.n_valid <= observation.state_count


def test_an_honest_observation_records_the_verifiers_own_match_probabilities(
    small_scenario,
) -> None:


    observation = honest_observation(
        small_scenario,
        seed=12,
        experiment_id="obs-test",
        dataset_role=DatasetRole.CALIBRATION,
        noise_type="depolarizing",
        noise_strength=0.05,
    )
    assert len(observation.analytic_match_probabilities) == observation.state_count
    assert all(0.0 <= value <= 1.0 for value in observation.analytic_match_probabilities)


def test_an_honest_observation_with_an_evaluation_role_is_refused(
    small_scenario,
) -> None:



    observation = honest_observation(
        small_scenario,
        seed=13,
        experiment_id="obs-test",
        dataset_role=DatasetRole.FINAL_EVALUATION,
        noise_type="depolarizing",
        noise_strength=0.0,
    )
    with pytest.raises(ValueError, match="CALIBRATION"):
        observation.validate()


def test_an_honest_observation_is_reproducible(small_scenario) -> None:
    kwargs = dict(
        seed=99,
        experiment_id="obs-test",
        dataset_role=DatasetRole.CALIBRATION,
        noise_type="depolarizing",
        noise_strength=0.02,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    first = honest_observation(small_scenario, **kwargs)
    second = honest_observation(small_scenario, **kwargs)
    assert first.n_mismatch == second.n_mismatch
    assert first.mismatch_rate == second.mismatch_rate
    assert first.analytic_match_probabilities == second.analytic_match_probabilities







def test_the_calibration_dataset_has_the_declared_shape(small_scenario) -> None:
    config, observations = build_calibration_dataset(
        small_scenario,
        config_id="ds-test",
        seed_start=100,
        session_count=3,
        noise_type="depolarizing",
        noise_strength=0.02,
    )
    assert config.dataset_role is DatasetRole.CALIBRATION
    assert config.state_count == small_scenario.state_count
    assert config.session_count == 3
    assert config.seed_range() == (100, 102)
    assert len(observations) == 3
    assert [o.random_seed for o in observations] == [100, 101, 102]
    for observation in observations:
        observation.validate()


def test_the_dataset_honours_and_records_the_size_overrides(small_scenario) -> None:
    config, observations = build_calibration_dataset(
        small_scenario,
        config_id="ds-test",
        seed_start=0,
        session_count=2,
        state_count=12,
        measurement_mode="projective-analytic",
        shot_count=3,
    )
    assert config.state_count == 12
    assert config.measurement_mode == "projective-analytic"
    assert config.shot_count == 3
    assert all(o.state_count == 12 for o in observations)


def test_a_calibration_dataset_cannot_be_built_with_another_role(
    small_scenario,
) -> None:
    with pytest.raises(ValueError, match="CALIBRATION"):
        build_calibration_dataset(
            small_scenario,
            config_id="ds-test",
            seed_start=0,
            session_count=2,
            dataset_role=DatasetRole.VALIDATION,
        )


def test_the_calibration_config_uses_the_declared_confidence(small_scenario) -> None:
    config, _ = build_calibration_dataset(
        small_scenario, config_id="ds-test", seed_start=0, session_count=1
    )
    assert config.confidence == pytest.approx(DEFAULT_CALIBRATION_CONFIDENCE)
    assert DEFAULT_CALIBRATION_CONFIDENCE == pytest.approx(0.95)


def test_the_dataset_carries_no_attack_information(small_scenario) -> None:


    _, observations = build_calibration_dataset(
        small_scenario,
        config_id="ds-test",
        seed_start=0,
        session_count=2,
        noise_type="depolarizing",
        noise_strength=0.02,
    )
    for observation in observations:
        payload = observation.to_dict()
        for forbidden in ("attack", "is_malicious", "ground_truth", "fraction"):
            assert forbidden not in payload, forbidden


def test_the_calibration_dataset_is_reproducible(small_scenario) -> None:
    first_config, first = build_calibration_dataset(
        small_scenario,
        config_id="ds-test",
        seed_start=500,
        session_count=2,
        noise_strength=0.02,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    second_config, second = build_calibration_dataset(
        small_scenario,
        config_id="ds-test",
        seed_start=500,
        session_count=2,
        noise_strength=0.02,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    assert first_config.fingerprint() == second_config.fingerprint()
    assert [o.n_mismatch for o in first] == [o.n_mismatch for o in second]







def test_disjoint_seed_blocks_pass() -> None:
    assert_disjoint_seeds(
        [
            ("calibration", tuple(range(0, 10))),
            ("evaluation", tuple(range(SEED_BLOCK_SIZE, SEED_BLOCK_SIZE + 10))),
        ]
    )


def test_overlapping_seed_blocks_are_refused() -> None:
    with pytest.raises(ValueError, match="appears in both"):
        assert_disjoint_seeds(
            [
                ("calibration", tuple(range(0, 10))),
                ("evaluation", tuple(range(5, 15))),
            ]
        )


def test_a_seed_shared_by_the_same_label_is_allowed() -> None:


    assert_disjoint_seeds(
        [
            ("calibration", (1, 2, 3)),
            ("calibration", (3, 4, 5)),
        ]
    )


def test_no_datasets_is_vacuously_disjoint() -> None:
    assert_disjoint_seeds([])


def test_the_seed_block_size_is_declared_and_large_enough() -> None:

    assert SEED_BLOCK_SIZE >= 100_000
