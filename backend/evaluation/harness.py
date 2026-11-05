"""The observable-only experiment harness.

What this module is for
-----------------------
It runs Milestone 3 scenarios, converts the **observable half** of each result
into the Milestone 4 statistics, applies the calibration operating point, and
only afterwards attaches ground truth. It is the single place in Milestone 5
where experiment results and labels meet, and the meeting is deliberately
one-way and ordered.

The ordering, made structural
-----------------------------
::

    run_scenario(config)
        |
        +-- observable   -----------------------+
        |                                       |
        |                     observable_statistics(observable)
        |                                       |
        |                          decide_observable(point, statistics)
        |                                       |
        +-- ground_truth -------------------> build_trial_record(...)

``decide_observable`` receives an :class:`~backend.evaluation.models.ObservableStatistics`
and an operating point. It has no parameter that could carry a label, and it
does not receive the :class:`~backend.simulation.ExperimentResult`. The record
that does carry the label is built afterwards, from the already-computed
decision. A test can therefore assert the ordering by monkeypatching, and a
reviewer can check it by reading the two signatures.

Reproducibility
---------------
The runner uses the operating system CSPRNG for ``session_id`` and ``nonce``
when a scenario does not pin them, which is correct for the protocol and fatal
for a reproducible benchmark. This harness therefore derives pinned identifiers
*deterministically from the trial seed*, so a trial is fully reproducible while
still looking like an independent session.

Why M4's own analysis functions are called
------------------------------------------
``D_m`` could be recomputed here in three lines, and doing so would be a quiet
fork of the Milestone 4 definition. The harness instead calls
:func:`~backend.detection.analyse_mismatch`,
:func:`~backend.detection.analyse_disturbance`,
:func:`~backend.detection.analyse_fidelity` and
:func:`~backend.detection.analyse_basis_statistics` on the state evidence, so
the number the evaluation scores is provably the number the detector reports.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

from backend.calibration.models import (
    DatasetRole,
    OperatingPoint,
    VerificationDecision,
)
from backend.detection import (
    StateEvidence,
    analyse_basis_statistics,
    analyse_disturbance,
    analyse_fidelity,
    analyse_mismatch,
)
from backend.simulation import ScenarioConfig, run_scenario
from backend.simulation.seed import generator

from backend.evaluation.models import (
    EvaluationConfig,
    ObservableStatistics,
    TrialRecord,
)

__all__ = [
    "SESSION_ID_BYTES",
    "NONCE_BYTES",
    "TRIAL_SEED_DOMAIN",
    "state_evidence",
    "observable_statistics",
    "decide_observable",
    "deterministic_session_identifiers",
    "scenario_for_trial",
    "run_trial",
    "run_trials",
    "build_trial_record",
]


SESSION_ID_BYTES = 16


NONCE_BYTES = 32



TRIAL_SEED_DOMAIN = "m5-evaluation"


_TIMESTAMP_ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)







def state_evidence(observable: Any) -> Tuple[StateEvidence, ...]:
    """Return the Milestone 4 state evidence for an observable record.

    Pure: it reads ``observable.states`` and nothing else.
    """
    return tuple(
        StateEvidence.from_observation(item)
        for item in (getattr(observable, "states", ()) or ())
    )


def observable_statistics(observable: Any) -> ObservableStatistics:
    """Summarise the observable half of an experiment.

    Every statistic is produced by Milestone 4's own analysis functions, so the
    evaluation cannot drift from the detector's definitions. Nothing here reads
    a label, and the argument type has no label to read.
    """
    states = state_evidence(observable)
    mode = str(getattr(observable, "measurement_mode", "unknown") or "unknown")

    mismatch = analyse_mismatch(states)
    disturbance = analyse_disturbance(states, mismatch=mismatch)
    fidelity = analyse_fidelity(states, measurement_mode=mode)
    basis = analyse_basis_statistics(states)

    return ObservableStatistics(
        n_valid=int(mismatch.n_valid),
        n_mismatch=int(mismatch.n_mismatch),
        mismatch_rate=mismatch.mismatch_rate,
        disturbance_rate=disturbance.disturbance_rate,
        mean_fidelity=fidelity.analytic_mean_fidelity,
        minimum_fidelity=fidelity.analytic_min_fidelity,
        measurement_mode=mode,
        basis_counts=dict(basis.counts),
        per_basis_mismatch_rates=dict(basis.mismatch_rates),
        per_basis_disturbance_rates=dict(basis.disturbance_rates),
    )


def decide_observable(
    point: OperatingPoint, statistics: ObservableStatistics
) -> VerificationDecision:
    """Apply the operating point to observable statistics.

    Layer A of the dual-layer decision. The other statistics travel in the
    ``diagnostics`` field, which
    :meth:`~backend.calibration.models.VerificationDecision.to_dict` records and
    which the decision rule does not read -- see
    :mod:`backend.calibration.multiple_testing`.
    """
    return point.decide(
        n_mismatch=statistics.n_mismatch,
        n_valid=statistics.n_valid,
        diagnostics={
            "disturbance_rate": statistics.disturbance_rate,
            "mean_fidelity": statistics.mean_fidelity,
            "minimum_fidelity": statistics.minimum_fidelity,
            "basis_mismatch_dispersion": statistics.basis_mismatch_dispersion,
            "per_basis_mismatch_rates": dict(statistics.per_basis_mismatch_rates),
        },
    )







def deterministic_session_identifiers(seed: int) -> Tuple[str, str, str]:
    """Return ``(session_id, nonce, created_at)`` derived from ``seed``.

    Derived rather than drawn so that a benchmark trial is reproducible. The
    values are *simulator* randomness in the sense of
    :mod:`backend.protocol.session`: they make an experiment repeatable and
    carry no security meaning, which is exactly why a benchmark may pin them.
    """
    rng = generator(int(seed), TRIAL_SEED_DOMAIN, "session")
    session_id = bytes(rng.bytes(SESSION_ID_BYTES)).hex()
    nonce = bytes(rng.bytes(NONCE_BYTES)).hex()
    offset = int(seed) % 86_400
    created_at = (_TIMESTAMP_ORIGIN + timedelta(seconds=offset)).isoformat(
        timespec="seconds"
    )
    return session_id, nonce, created_at


def scenario_for_trial(
    base: ScenarioConfig,
    seed: int,
    *,
    scenario_id: str | None = None,
) -> ScenarioConfig:
    """Return ``base`` with a fresh seed and deterministically pinned identities."""
    session_id, nonce, created_at = deterministic_session_identifiers(seed)
    return base.with_changes(
        scenario_id=scenario_id or base.scenario_id,
        random_seed=int(seed),
        session_id=session_id,
        nonce=nonce,
        created_at=created_at,
    )







def build_trial_record(
    result: Any,
    point: OperatingPoint,
    *,
    experiment_id: str,
    dataset_role: DatasetRole,
    scenario_fingerprint: str = "",
) -> TrialRecord:
    """Build one trial record from a finished experiment.

    The decision is computed from the observable half *before* the ground-truth
    half is touched, and the label fields are read only in the final
    construction step.
    """
    observable = result.observable


    statistics = observable_statistics(observable)
    decision = decide_observable(point, statistics)


    truth = result.ground_truth
    attack = dict(getattr(truth, "attack", {}) or {})
    noise = dict(getattr(truth, "noise", {}) or {})

    return TrialRecord(
        experiment_id=experiment_id,
        random_seed=int(getattr(observable, "simulator_seed", 0)),
        scenario_fingerprint=scenario_fingerprint,
        dataset_role=dataset_role,
        is_malicious=bool(getattr(truth, "is_malicious", False)),
        attack_type=str(attack.get("attack_type", "none")),
        attack_fraction=float(attack.get("fraction", 0.0) or 0.0),
        noise_type=str(noise.get("noise_type", "none")),
        noise_strength=float(noise.get("noise_strength", 0.0) or 0.0),
        state_count=int(getattr(observable, "state_count", statistics.n_valid)),
        statistics=statistics,
        decision=decision,
    )


def run_trial(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    seed: int,
    experiment_id: str,
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> TrialRecord:
    """Run one scenario and return its trial record."""
    scenario = scenario_for_trial(
        base, seed, scenario_id=f"{experiment_id}-s{int(seed)}"
    )
    result = run_scenario(scenario)
    return build_trial_record(
        result,
        point,
        experiment_id=experiment_id,
        dataset_role=dataset_role,
        scenario_fingerprint=scenario.fingerprint(),
    )


def run_trials(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    config: EvaluationConfig,
) -> Tuple[TrialRecord, ...]:
    """Run ``config.trial_count`` independent trials over the configured seeds.

    Each trial gets a fresh seed, a fresh derived session identifier and a fresh
    scenario identifier, so the trials are independent draws rather than
    repeated views of one run.
    """
    config.validate()
    records = []
    for offset in range(config.trial_count):
        seed = config.seed_start + offset
        records.append(
            run_trial(
                base,
                point,
                seed=seed,
                experiment_id=config.evaluation_id,
                dataset_role=config.dataset_role,
            )
        )
    return tuple(records)
