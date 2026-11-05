"""Data leakage: the calibration/evaluation split, enforced rather than promised.

A threshold fitted on the data it is then scored on will look better than it is.
The milestone therefore requires a split, and requires it to be a property of the
code rather than a convention. There are five independent guards, and these
tests exercise each one:

1. a calibration configuration refuses any role but ``CALIBRATION``;
2. a calibration observation refuses any role but ``CALIBRATION``;
3. an evaluation configuration refuses the ``CALIBRATION`` role;
4. the calibration record type has no field an attack label could occupy;
5. calibration and evaluation draw from disjoint seed blocks.

Guards 1-3 are checked here by trying to violate them; guard 4 is checked by
inspecting the type; guard 5 is checked by running the allocator the benchmark
uses and asserting the blocks do not intersect.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.calibration.models import (
    CalibrationConfig,
    CalibrationObservation,
    DatasetRole,
)
from backend.evaluation.datasets import (
    SEED_BLOCK_SIZE,
    assert_disjoint_seeds,
    build_calibration_dataset,
    honest_observation,
)
from backend.evaluation.models import EvaluationConfig, TrialRecord
from backend.evaluation.benchmark import SeedAllocator







def _config(**overrides) -> CalibrationConfig:
    base = dict(
        config_id="leak-test",
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=200,
        measurement_mode="sampled",
        shot_count=1,
        statistic="mismatch_rate",
        confidence=0.95,
        seed_start=0,
        session_count=10,
        dataset_role=DatasetRole.CALIBRATION,
    )
    base.update(overrides)
    return CalibrationConfig(**base)


@pytest.mark.parametrize(
    "role", [DatasetRole.VALIDATION, DatasetRole.FINAL_EVALUATION]
)
def test_a_calibration_config_refuses_an_evaluation_role(role) -> None:
    with pytest.raises(ValueError, match="CALIBRATION"):
        _config(dataset_role=role).validate()


@pytest.mark.parametrize(
    "role", [DatasetRole.VALIDATION, DatasetRole.FINAL_EVALUATION]
)
def test_a_calibration_observation_refuses_an_evaluation_role(role) -> None:
    with pytest.raises(ValueError, match="CALIBRATION"):
        CalibrationObservation(
            experiment_id="leak-test",
            random_seed=0,
            state_count=200,
            n_valid=200,
            n_mismatch=4,
            mismatch_rate=0.02,
            dataset_role=role,
        ).validate()


def test_the_builder_refuses_to_produce_a_mislabelled_calibration_dataset(
    small_scenario,
) -> None:
    with pytest.raises(ValueError, match="CALIBRATION"):
        build_calibration_dataset(
            small_scenario,
            config_id="leak-test",
            seed_start=0,
            session_count=1,
            dataset_role=DatasetRole.VALIDATION,
        )


def test_an_honest_observation_refuses_a_mislabelled_role(small_scenario) -> None:
    observation = honest_observation(
        small_scenario,
        seed=0,
        experiment_id="leak-test",
        dataset_role=DatasetRole.VALIDATION,
        noise_type="depolarizing",
        noise_strength=0.0,
    )
    with pytest.raises(ValueError, match="CALIBRATION"):
        observation.validate()







def test_an_evaluation_config_refuses_the_calibration_role() -> None:
    with pytest.raises(ValueError, match="calibration role"):
        EvaluationConfig(
            evaluation_id="leak-test",
            dataset_role=DatasetRole.CALIBRATION,
            state_count=200,
            measurement_mode="sampled",
            shot_count=1,
            seed_start=0,
            trial_count=5,
        ).validate()


@pytest.mark.parametrize(
    "role", [DatasetRole.VALIDATION, DatasetRole.FINAL_EVALUATION]
)
def test_an_evaluation_config_accepts_an_evaluation_role(role) -> None:
    config = EvaluationConfig(
        evaluation_id="leak-test",
        dataset_role=role,
        state_count=200,
        measurement_mode="sampled",
        shot_count=1,
        seed_start=0,
        trial_count=5,
    ).validate()
    assert config.seed_range() == (0, 4)


def test_the_two_config_types_disagree_about_the_calibration_role() -> None:


    with pytest.raises(ValueError):
        _config(dataset_role=DatasetRole.FINAL_EVALUATION).validate()
    with pytest.raises(ValueError):
        EvaluationConfig(
            evaluation_id="leak-test",
            dataset_role=DatasetRole.CALIBRATION,
            state_count=200,
            measurement_mode="sampled",
            shot_count=1,
            seed_start=0,
            trial_count=5,
        ).validate()







def test_the_calibration_record_cannot_carry_a_label() -> None:
    names = {field.name.lower() for field in dataclasses.fields(CalibrationObservation)}
    for forbidden in (
        "attack",
        "attack_type",
        "attack_fraction",
        "is_malicious",
        "malicious",
        "ground_truth",
        "label",
    ):
        assert forbidden not in names, forbidden


def test_the_observable_statistics_cannot_carry_a_label() -> None:


    from backend.evaluation.models import ObservableStatistics

    names = {
        field.name.lower() for field in dataclasses.fields(ObservableStatistics)
    }
    for forbidden in ("attack", "is_malicious", "ground_truth", "label", "malicious"):
        assert forbidden not in names, forbidden


def test_the_trial_record_does_carry_a_label() -> None:


    names = {field.name.lower() for field in dataclasses.fields(TrialRecord)}
    assert "is_malicious" in names
    assert "attack_type" in names







def test_the_benchmark_seed_allocator_hands_out_disjoint_blocks() -> None:
    allocator = SeedAllocator(start=0)
    calibration = allocator.take("calibration", 40)
    validation = allocator.take("validation", 12)
    final = allocator.take("final-evaluation", 12)

    blocks = {
        label: set(seeds) for label, seeds in allocator.allocations
    }
    assert set(blocks["calibration"]) & set(blocks["validation"]) == set()
    assert set(blocks["calibration"]) & set(blocks["final-evaluation"]) == set()
    assert set(blocks["validation"]) & set(blocks["final-evaluation"]) == set()


    allocator.verify_disjoint()
    assert calibration == 0
    assert validation > calibration
    assert final > validation


def test_the_allocator_refuses_an_empty_block() -> None:
    allocator = SeedAllocator()
    with pytest.raises(ValueError):
        allocator.take("empty", 0)


def test_the_allocator_leaves_a_gap_between_blocks() -> None:


    allocator = SeedAllocator(start=0, block=10)
    first = allocator.take("first", 3)
    second = allocator.take("second", 3)
    assert second > first + 3


def test_two_datasets_that_share_a_seed_are_caught() -> None:
    with pytest.raises(ValueError, match="not independent"):
        assert_disjoint_seeds(
            [
                ("calibration", range(0, SEED_BLOCK_SIZE)),
                ("final-evaluation", range(SEED_BLOCK_SIZE - 1, SEED_BLOCK_SIZE + 5)),
            ]
        )


def test_calibration_and_evaluation_use_different_blocks_by_construction() -> None:



    allocator = SeedAllocator(start=0)
    allocator.take("calibration", 120)
    allocator.take("final-evaluation-attack", 12)
    allocator.verify_disjoint()
