"""The experiment runner.

Pipeline
--------
::

    scenario config
        |
        v
    1. session                 (M2 create_session; CSPRNG or pinned identifiers)
    2. signing                 (M2 sign_session; M1 teleportation engine)
    3. ideal received qubits   (M1 exact branch decomposition -> density matrices)
    4. honest noise            (backend.noise channel applied to every state)
    5. attack                  (backend.attacks scenario, or the honest baseline)
    6. verification            (M2 verify with the ACTUAL received states)
    7. per-state measurement   (M2 verify_state_measurement, same actual states)
        |
        v
    ExperimentResult(observable=..., ground_truth=...)

Steps 4 and 5 are independent, which is what makes "honest noise + malicious
disturbance" a first-class experiment rather than a special case: either, both
or neither can be configured.

There is no branch anywhere in this module that reads an attack type and changes
what the runner does with the result. An attack is applied to real material, and
the ordinary verification path then runs on whatever came out.

Runtime
-------
The runner records ``runtime_seconds`` only when it actually measures it
(``measure_runtime=True``), using :func:`time.perf_counter`. No runtime number in
this project is estimated or extrapolated.
"""

from __future__ import annotations

import time
from typing import Iterable, Tuple

import numpy as np

from backend.attacks import (
    AttackContext,
    AuthorizationContext,
    build_attack_scenario,
)
from backend.noise import build_noise_channel, trace_distance
from backend.protocol.encoding import derive_state_sequence
from backend.protocol.models import VerifierContext
from backend.protocol.session import create_session, session_binding
from backend.protocol.signer import sign_session
from backend.protocol.verifier import verify, verify_state_measurement
from backend.quantum.density import projector
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import uncorrected_branch_states

from backend.simulation.results import (
    AuthorizationObservations,
    ExperimentResult,
    GroundTruthMetadata,
    ObservableExperimentData,
    StateObservation,
)
from backend.simulation.scenario import ScenarioConfig
from backend.simulation.seed import derive_seed, generator

__all__ = [
    "ExperimentRunner",
    "run_scenario",
    "run_sweep",
]


class ExperimentRunner:
    """Runs one scenario end to end and returns observable + ground truth."""

    def __init__(self, config: ScenarioConfig, *, measure_runtime: bool = False) -> None:
        self._config = config.validate()
        self._measure_runtime = bool(measure_runtime)

    @property
    def config(self) -> ScenarioConfig:
        return self._config

    def run(self) -> ExperimentResult:
        started = time.perf_counter() if self._measure_runtime else None
        config = self._config




        session_id_factory = (
            _constant(config.session_id)
            if config.session_id is not None
            else _default_session_id
        )
        nonce_factory = (
            _constant(config.nonce) if config.nonce is not None else _default_nonce
        )
        clock = (
            _constant(config.created_at)
            if config.created_at is not None
            else _default_clock
        )
        session = create_session(
            config.message,
            signer_id=config.signer_id,
            verifier_id=config.verifier_id,
            state_count=config.state_count,
            protocol_version=config.protocol_version,
            session_id_factory=session_id_factory,
            nonce_factory=nonce_factory,
            clock=clock,
        )


        signed = sign_session(
            session, simulator_seed=derive_seed(config.random_seed, "signing")
        )
        transcript = signed.transcript




        expected_states = derive_state_sequence(
            session_binding(session), config.state_count
        )
        ideal_received = tuple(
            projector(
                uncorrected_branch_states(get_eigenstate(state.label).vector)[
                    (branch.m0, branch.m1)
                ]
            )
            for state, branch in zip(expected_states, transcript.teleportation_branches)
        )


        channel = build_noise_channel(config.noise)
        noisy_received = tuple(channel.apply(state) for state in ideal_received)


        authorization = AuthorizationContext.from_session(
            session, extra_verifiers=config.extra_authorized_verifiers
        )
        verifier_context = VerifierContext(
            verifier_id=config.verifier_id,
            expected_protocol_version=config.protocol_version,
        )
        scenario = build_attack_scenario(config.attack)
        if scenario is None:
            final_received = noisy_received
            final_transcript = transcript
            final_verifier_context = verifier_context
            final_authorization = authorization
            attack_ground_truth = {"attack_type": "none", "is_attack": False}
        else:
            outcome = scenario.apply(
                AttackContext(
                    message=config.message,
                    session=session,
                    transcript=transcript,
                    received_states=noisy_received,
                    verifier_context=verifier_context,
                    authorization=authorization,
                    rng=generator(
                        config.random_seed, "attack", config.attack.attack_type
                    ),
                )
            )
            final_received = outcome.received_states
            final_transcript = outcome.transcript
            final_verifier_context = outcome.verifier_context
            final_authorization = outcome.authorization
            attack_ground_truth = {**dict(outcome.ground_truth), "is_attack": True}


        verification = verify(
            final_transcript,
            config.message,
            final_verifier_context,
            received_states=final_received,
        )


        observations = tuple(
            _observe_state(
                expected,
                branch,
                final_received[index],
                config,
            )
            for index, (expected, branch) in enumerate(
                zip(expected_states, final_transcript.teleportation_branches)
            )
        )

        mismatch_count = sum(1 for item in observations if not item.matched)
        basis_counts: dict[str, int] = {}
        for item in observations:
            basis_counts[item.basis] = basis_counts.get(item.basis, 0) + 1

        disturbance = float(
            np.mean(
                [
                    trace_distance(ideal, actual)
                    for ideal, actual in zip(ideal_received, final_received)
                ]
            )
        )

        runtime = None
        if started is not None:
            runtime = time.perf_counter() - started

        observable = ObservableExperimentData(
            scenario_id=config.scenario_id,
            protocol_version=config.protocol_version,
            state_count=config.state_count,
            states=observations,
            basis_counts=basis_counts,
            mismatch_count=mismatch_count,
            mismatch_proportion=mismatch_count / config.state_count,
            mean_channel_disturbance=disturbance,
            verification=verification,
            authorization=AuthorizationObservations(
                presented_signer=final_transcript.signer_id,
                presented_verifier=final_transcript.verifier_id,
                authorized_signers=tuple(sorted(final_authorization.authorized_signers)),
                authorized_verifiers=tuple(
                    sorted(final_authorization.authorized_verifiers)
                ),
                signer_authorized=final_authorization.signer_authorized(
                    final_transcript.signer_id
                ),
                verifier_authorized=final_authorization.verifier_authorized(
                    final_transcript.verifier_id
                ),
            ),
            simulator_seed=config.random_seed,
            measurement_mode=config.measurement_mode,
            runtime_seconds=runtime,
        )

        ground_truth = GroundTruthMetadata(
            scenario_id=config.scenario_id,
            is_malicious=scenario is not None,
            noise=config.noise.to_dict(),
            attack=attack_ground_truth,
            notes=(
                "observable data contains no attack type, attack parameter or "
                "noise strength",
                f"scenario fingerprint {config.fingerprint()}",
            ),
        )
        return ExperimentResult(observable=observable, ground_truth=ground_truth)


def _observe_state(
    expected, branch, received_state, config: ScenarioConfig
) -> StateObservation:
    """Measure one received qubit exactly as the verifier would.

    Both modes use M2's :func:`~backend.protocol.verifier.verify_state_measurement`
    for the physics, so they cannot disagree about the underlying probability.
    They differ only in how the *outcome* is obtained:

    * ``"projective-analytic"`` -- deterministic; the outcome is the expected
      eigenvalue when the projective probability is within tolerance of 1.
    * ``"sampled"`` -- ``shot_count`` finite-shot draws from the Born rule,
      using a generator seeded from ``(random_seed, "measurement", state index)``.
    """
    measurement = verify_state_measurement(
        expected, branch, received_state=received_state
    )
    if config.measurement_mode != "sampled":
        return StateObservation(
            index=measurement.index,
            basis=measurement.basis,
            expected_bit=measurement.expected_bit,
            probability_expected=measurement.probability,
            matched=measurement.matched,
        )

    probability = min(1.0, max(0.0, measurement.probability))
    rng = generator(config.random_seed, "measurement", "state", str(expected.index))
    successes = int(rng.binomial(config.shot_count, probability))
    sampled_bit = (
        measurement.expected_bit
        if successes * 2 >= config.shot_count
        else 1 - measurement.expected_bit
    )
    return StateObservation(
        index=measurement.index,
        basis=measurement.basis,
        expected_bit=measurement.expected_bit,
        probability_expected=measurement.probability,
        matched=sampled_bit == measurement.expected_bit,
    )


def run_scenario(
    config: ScenarioConfig, *, measure_runtime: bool = False
) -> ExperimentResult:
    """Convenience wrapper: build a runner and run one scenario."""
    return ExperimentRunner(config, measure_runtime=measure_runtime).run()


def run_sweep(
    configs: Iterable[ScenarioConfig], *, measure_runtime: bool = False
) -> Tuple[ExperimentResult, ...]:
    """Run every configuration and return the results in order."""
    return tuple(
        run_scenario(config, measure_runtime=measure_runtime) for config in configs
    )











def _default_session_id() -> str:
    from backend.protocol.session import new_session_id

    return new_session_id()


def _default_nonce() -> str:
    from backend.protocol.session import new_nonce

    return new_nonce()


def _default_clock() -> str:
    from backend.protocol.session import utc_now_iso

    return utc_now_iso()


def _constant(value: str):
    """Return a factory that always yields ``value``."""

    def factory() -> str:
        return value

    return factory
