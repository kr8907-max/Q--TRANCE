"""Shared builders for the evaluation tests.

Most of the evaluation layer is *counting*: it takes trials that have already
been decided and aggregates them. Those tests do not need a simulator, a
threshold or a quantum circuit, so the builders here construct
:class:`~backend.evaluation.models.TrialRecord` objects directly.

That is deliberate. A counting test that ran a real circuit would be slow and
would fail for the wrong reason. The tests that *do* need a real run (the
harness ordering guard, the sweeps, the discrimination experiment) build a
small operating point from a real scenario in their own module.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    DatasetRole,
    VerificationDecision,
)
from backend.evaluation.confusion import HONEST_ATTACK_TYPE
from backend.evaluation.models import ObservableStatistics, TrialRecord


CRITICAL_COUNT = 10

SAMPLE_SIZE = 200


def _make_statistics(
    n_valid: int = SAMPLE_SIZE,
    n_mismatch: int = 4,
    *,
    per_basis: dict | None = None,
    mean_fidelity: float = 0.99,
    minimum_fidelity: float | None = None,
    measurement_mode: str = "sampled",
) -> ObservableStatistics:
    rate = (n_mismatch / n_valid) if n_valid else None
    if per_basis is None:
        per_basis = {"Z": rate or 0.0, "X": rate or 0.0, "Y": rate or 0.0}
    return ObservableStatistics(
        n_valid=n_valid,
        n_mismatch=n_mismatch,
        mismatch_rate=rate,
        disturbance_rate=rate,
        mean_fidelity=mean_fidelity,
        minimum_fidelity=mean_fidelity if minimum_fidelity is None else minimum_fidelity,
        measurement_mode=measurement_mode,
        basis_counts={"Z": n_valid, "X": 0, "Y": 0},
        per_basis_mismatch_rates=dict(per_basis),
        per_basis_disturbance_rates=dict(per_basis),
    )


def _make_decision(
    rejected: bool,
    *,
    n_mismatch: int = 4,
    sample_size: int = SAMPLE_SIZE,
    critical_count: int = CRITICAL_COUNT,
) -> VerificationDecision:
    rate = (n_mismatch / sample_size) if sample_size else None
    return VerificationDecision(
        rejected=rejected,
        statistic=STATISTIC_MISMATCH_RATE,
        observed_rate=rate,
        observed_count=int(n_mismatch),
        sample_size=int(sample_size),
        threshold_rate=critical_count / sample_size if sample_size else 0.0,
        critical_count=int(critical_count),
        operating_point="m5-test",
        explanation="synthetic decision",
        decision_basis=(
            f"{STATISTIC_MISMATCH_RATE} > {critical_count} "
            f"(critical count for n={sample_size})",
            "one primary statistical test; no other statistic enters the decision",
        ),
    )


def _make_record(
    *,
    malicious: bool,
    rejected: bool,
    attack_type: str | None = None,
    attack_fraction: float | None = None,
    noise_type: str = "depolarizing",
    noise_strength: float = 0.0,
    seed: int = 0,
    state_count: int = SAMPLE_SIZE,
    n_mismatch: int = 4,
    per_basis: dict | None = None,
    mean_fidelity: float = 0.99,
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
    experiment_id: str | None = None,
) -> TrialRecord:
    if attack_type is None:
        attack_type = "channel_tampering" if malicious else HONEST_ATTACK_TYPE
    if attack_fraction is None:
        attack_fraction = 0.2 if malicious else 0.0
    statistics = _make_statistics(
        n_valid=state_count,
        n_mismatch=n_mismatch,
        per_basis=per_basis,
        mean_fidelity=mean_fidelity,
    )
    return TrialRecord(
        experiment_id=experiment_id or f"trial-{seed:04d}",
        random_seed=seed,
        scenario_fingerprint=f"fingerprint-{seed:04d}",
        dataset_role=dataset_role,
        is_malicious=malicious,
        attack_type=attack_type,
        attack_fraction=float(attack_fraction),
        noise_type=noise_type,
        noise_strength=float(noise_strength),
        state_count=int(state_count),
        statistics=statistics,
        decision=_make_decision(
            rejected, n_mismatch=n_mismatch, sample_size=state_count
        ),
    )


@pytest.fixture
def make_statistics():
    """Return the statistics builder."""
    return _make_statistics


@pytest.fixture
def make_decision():
    """Return the decision builder."""
    return _make_decision


@pytest.fixture
def make_record():
    """Return the trial-record builder."""
    return _make_record







TEST_MESSAGE = "transfer 100 units to account 7"





TEST_STATE_COUNT = 20


TEST_CALIBRATION_SESSIONS = 8


TEST_NOISE_STRENGTH = 0.02


@pytest.fixture(scope="session")
def small_scenario():
    """Return a small, fully pinned scenario configuration.

    Identifiers are pinned so the fixture is reproducible; the harness derives
    its own per-trial identities anyway, but pinning keeps a direct
    ``run_scenario`` reproducible too.
    """
    from backend.simulation import ScenarioConfig

    return ScenarioConfig(
        scenario_id="eval-test-base",
        message=TEST_MESSAGE,
        signer_id="alice",
        verifier_id="bob",
        state_count=TEST_STATE_COUNT,
        shot_count=1,
        random_seed=0,
        measurement_mode="sampled",
        session_id="0" * 32,
        nonce="1" * 64,
        created_at="2026-01-01T00:00:00+00:00",
    ).validate()


@pytest.fixture(scope="session")
def small_operating_point(small_scenario):
    """Return a real operating point calibrated on a small honest dataset.

    Session-scoped because building it runs scenarios, and every run-backed test
    should pay that cost once rather than per test.
    """
    from backend.calibration.baseline import estimate_baseline
    from backend.calibration.operating_points import build_reference_operating_point
    from backend.evaluation.datasets import build_calibration_dataset

    config, observations = build_calibration_dataset(
        small_scenario,
        config_id="eval-test-calibration",
        seed_start=0,
        session_count=TEST_CALIBRATION_SESSIONS,
        noise_type="depolarizing",
        noise_strength=TEST_NOISE_STRENGTH,
    )
    calibration = estimate_baseline(config, observations)
    return build_reference_operating_point(calibration)


@pytest.fixture(scope="session")
def small_calibration(small_scenario):
    """Return the calibration result behind :func:`small_operating_point`."""
    from backend.calibration.baseline import estimate_baseline
    from backend.evaluation.datasets import build_calibration_dataset

    config, observations = build_calibration_dataset(
        small_scenario,
        config_id="eval-test-calibration",
        seed_start=0,
        session_count=TEST_CALIBRATION_SESSIONS,
        noise_type="depolarizing",
        noise_strength=TEST_NOISE_STRENGTH,
    )
    return estimate_baseline(config, observations)















TINY_BENCHMARK_STATE_COUNT = 30


@pytest.fixture(scope="session")
def tiny_benchmark_profile():
    """Return a minimal benchmark profile covering every benchmark section."""
    from backend.evaluation.benchmark import BenchmarkProfile, sample_size_plan

    return BenchmarkProfile(
        name="m5-test-tiny",
        description="a minimal profile; no number it produces is interpretable",
        state_count=TINY_BENCHMARK_STATE_COUNT,
        calibration_sessions=4,
        evaluation_trials=1,
        measurement_mode="sampled",
        shot_count=1,
        reference_noise_strength=TEST_NOISE_STRENGTH,
        attack_types=("channel_tampering",),
        attack_fraction=0.20,
        attack_fractions=(0.20,),
        noise_type="depolarizing",
        noise_strengths=(0.0, TEST_NOISE_STRENGTH),
        sample_size_design=(TINY_BENCHMARK_STATE_COUNT,),
        sample_size_plan=sample_size_plan(
            (TINY_BENCHMARK_STATE_COUNT,),
            calibration_budget=120,
            fixed_trials=1,
            min_calibration_sessions=4,
            max_calibration_sessions=4,
        ),
        sample_size_calibration_sessions=0,
        robustness_levels=(("none", 0.0),),
        robustness_trials=1,
        robustness_attack_fraction=0.20,
        discrimination_trials=1,




        discrimination_noise_strengths=(0.0, TEST_NOISE_STRENGTH),
        discrimination_attack_fractions=(0.50,),
        notes=("tiny profile: no number here is interpretable",),
    )
