"""The observable-only harness, and the ordering that keeps it label-free.

The single most important property in Milestone 5 is that the decision is
computed from the observable half **before** the ground-truth half is touched. If
that ordering were reversed, a decision could in principle depend on a label, and
every number in the report would be suspect.

The ordering is not asserted by reading the source. A spy object records the
order in which the two halves are actually accessed during a real call, and the
test asserts that the decision came first.
"""

from __future__ import annotations

import inspect

import pytest

from backend.calibration.models import DatasetRole
from backend.evaluation.harness import (
    NONCE_BYTES,
    SESSION_ID_BYTES,
    build_trial_record,
    decide_observable,
    deterministic_session_identifiers,
    observable_statistics,
    run_trial,
    run_trials,
    scenario_for_trial,
    state_evidence,
)
from backend.evaluation.models import EvaluationConfig
from backend.simulation import run_scenario







class _AccessSpy:
    """Wraps a finished result and records which half was read, and when."""

    def __init__(self, result, order: list[str]) -> None:
        self._result = result
        self._order = order

    @property
    def observable(self):
        self._order.append("observable")
        return self._result.observable

    @property
    def ground_truth(self):
        self._order.append("ground_truth")
        return self._result.ground_truth


def test_the_decision_is_computed_before_ground_truth_is_read(
    small_scenario, small_operating_point, monkeypatch
) -> None:
    import backend.evaluation.harness as harness

    result = run_scenario(small_scenario)
    order: list[str] = []

    original = harness.decide_observable

    def _recording_decide(point, statistics):
        order.append("decision")
        return original(point, statistics)

    monkeypatch.setattr(harness, "decide_observable", _recording_decide)

    record = build_trial_record(
        _AccessSpy(result, order),
        small_operating_point,
        experiment_id="order-test",
        dataset_role=DatasetRole.VALIDATION,
    )

    assert "decision" in order, order
    assert "ground_truth" in order, order
    assert order.index("decision") < order.index("ground_truth"), order

    assert record.experiment_id == "order-test"
    assert record.dataset_role is DatasetRole.VALIDATION


def test_the_decision_path_takes_no_argument_that_could_carry_a_label() -> None:



    parameters = set(inspect.signature(decide_observable).parameters)
    assert parameters == {"point", "statistics"}


def test_observable_statistics_takes_only_the_observable_half() -> None:
    parameters = set(inspect.signature(observable_statistics).parameters)
    assert parameters == {"observable"}







def test_observable_statistics_agrees_with_the_detector(small_scenario) -> None:


    from backend.detection import analyse_mismatch

    observable = run_scenario(small_scenario).detector_view()
    statistics = observable_statistics(observable)
    detector = analyse_mismatch(state_evidence(observable))

    assert statistics.n_valid == detector.n_valid
    assert statistics.n_mismatch == detector.n_mismatch
    assert statistics.mismatch_rate == detector.mismatch_rate


def test_observable_statistics_populates_the_diagnostic_fields(small_scenario) -> None:
    observable = run_scenario(small_scenario).detector_view()
    statistics = observable_statistics(observable)
    assert statistics.measurement_mode == "sampled"
    assert statistics.mean_fidelity is not None
    assert statistics.basis_counts
    assert statistics.per_basis_mismatch_rates

    assert statistics.basis_mismatch_dispersion is not None


def test_the_dispersion_descriptor_is_the_range_of_per_basis_rates(
    make_statistics,
) -> None:
    statistics = make_statistics(per_basis={"Z": 0.01, "X": 0.05, "Y": 0.02})
    assert statistics.basis_mismatch_dispersion == pytest.approx(0.04)


def test_the_dispersion_descriptor_is_undefined_without_basis_rates() -> None:
    from backend.evaluation.models import ObservableStatistics

    statistics = ObservableStatistics(
        n_valid=10,
        n_mismatch=1,
        mismatch_rate=0.1,
        disturbance_rate=0.1,
        mean_fidelity=0.9,
        minimum_fidelity=0.9,
        measurement_mode="sampled",
        basis_counts={},
        per_basis_mismatch_rates={},
        per_basis_disturbance_rates={},
    )
    assert statistics.basis_mismatch_dispersion is None







def test_the_derived_identifiers_have_the_protocol_sizes() -> None:
    session_id, nonce, created_at = deterministic_session_identifiers(0)
    assert len(session_id) == SESSION_ID_BYTES * 2
    assert len(nonce) == NONCE_BYTES * 2
    assert session_id == session_id.lower()
    assert created_at.endswith("+00:00")


def test_the_derived_identifiers_are_reproducible() -> None:
    assert deterministic_session_identifiers(7) == deterministic_session_identifiers(7)


def test_different_seeds_give_different_identifiers() -> None:
    identifiers = {deterministic_session_identifiers(seed)[:2] for seed in range(50)}
    assert len(identifiers) == 50


def test_scenario_for_trial_pins_everything_the_runner_would_randomise(
    small_scenario,
) -> None:
    pinned = scenario_for_trial(small_scenario, 42)
    session_id, nonce, created_at = deterministic_session_identifiers(42)
    assert pinned.session_id == session_id
    assert pinned.nonce == nonce
    assert pinned.created_at == created_at
    assert pinned.random_seed == 42


def test_scenario_for_trial_keeps_the_rest_of_the_configuration(small_scenario) -> None:
    pinned = scenario_for_trial(small_scenario, 3, scenario_id="renamed")
    assert pinned.scenario_id == "renamed"
    assert pinned.state_count == small_scenario.state_count
    assert pinned.measurement_mode == small_scenario.measurement_mode
    assert pinned.message == small_scenario.message







def test_an_honest_trial_is_labelled_honest(small_scenario, small_operating_point) -> None:
    record = run_trial(
        small_scenario,
        small_operating_point,
        seed=1,
        experiment_id="harness-test",
    )
    assert record.is_malicious is False
    assert record.attack_type == "none"
    assert record.attack_fraction == 0.0
    assert record.dataset_role is DatasetRole.VALIDATION
    assert record.state_count == small_scenario.state_count


def test_a_trial_decision_matches_applying_the_point_to_its_statistics(
    small_scenario, small_operating_point
) -> None:
    record = run_trial(
        small_scenario, small_operating_point, seed=2, experiment_id="harness-test"
    )
    expected = small_operating_point.decide(
        n_mismatch=record.statistics.n_mismatch,
        n_valid=record.statistics.n_valid,
    )
    assert record.decision.rejected == expected.rejected
    assert record.decision.observed_count == expected.observed_count


def test_a_trial_is_reproducible(small_scenario, small_operating_point) -> None:
    first = run_trial(
        small_scenario, small_operating_point, seed=5, experiment_id="harness-test"
    )
    second = run_trial(
        small_scenario, small_operating_point, seed=5, experiment_id="harness-test"
    )
    assert first.statistics.to_dict() == second.statistics.to_dict()
    assert first.decision.to_dict() == second.decision.to_dict()
    assert first.scenario_fingerprint == second.scenario_fingerprint


def test_different_seeds_give_different_scenarios(
    small_scenario, small_operating_point
) -> None:
    first = run_trial(
        small_scenario, small_operating_point, seed=1, experiment_id="harness-test"
    )
    second = run_trial(
        small_scenario, small_operating_point, seed=2, experiment_id="harness-test"
    )
    assert first.scenario_fingerprint != second.scenario_fingerprint


def test_the_trial_record_carries_the_observable_diagnostics(
    small_scenario, small_operating_point
) -> None:
    record = run_trial(
        small_scenario, small_operating_point, seed=3, experiment_id="harness-test"
    )
    diagnostics = record.decision.diagnostics
    for key in (
        "disturbance_rate",
        "mean_fidelity",
        "minimum_fidelity",
        "basis_mismatch_dispersion",
        "per_basis_mismatch_rates",
    ):
        assert key in diagnostics, key


def test_run_trials_uses_the_configs_seeds_and_role(
    small_scenario, small_operating_point
) -> None:
    config = EvaluationConfig(
        evaluation_id="harness-batch",
        dataset_role=DatasetRole.VALIDATION,
        state_count=small_scenario.state_count,
        measurement_mode=small_scenario.measurement_mode,
        shot_count=small_scenario.shot_count,
        seed_start=100,
        trial_count=3,
    )
    records = run_trials(small_scenario, small_operating_point, config=config)
    assert len(records) == 3
    assert [record.random_seed for record in records] == [100, 101, 102]
    assert all(record.dataset_role is DatasetRole.VALIDATION for record in records)
    assert all(record.experiment_id == "harness-batch" for record in records)


def test_run_trials_refuses_a_calibration_role(
    small_scenario, small_operating_point
) -> None:
    config = EvaluationConfig(
        evaluation_id="harness-batch",
        dataset_role=DatasetRole.CALIBRATION,
        state_count=small_scenario.state_count,
        measurement_mode=small_scenario.measurement_mode,
        shot_count=small_scenario.shot_count,
        seed_start=0,
        trial_count=2,
    )
    with pytest.raises(ValueError, match="calibration role"):
        run_trials(small_scenario, small_operating_point, config=config)
