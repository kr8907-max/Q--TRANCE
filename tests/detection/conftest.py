"""Shared helpers for the Milestone 4 detection tests.

Why the transcript is reconstructed here
---------------------------------------
``backend.simulation.ExperimentResult`` exposes the *observable* half of an
experiment, which deliberately does not carry the transcript -- and Milestone 4
must not modify Milestone 3 to add it. A real verifier holds the transcript it
received, so a detection input needs one; this module rebuilds it by replaying
the runner's own deterministic steps (pinned identifiers, derived seeds), using
only Milestone 2 and 3 public APIs.

The reconstruction is checked against the observable: the verification flags the
reconstructed transcript produces must match the flags in the observable, which
``tests/detection/test_separation.py`` asserts for a range of scenarios. If the
runner ever changes its pipeline, that assertion fails rather than the tests
silently testing a different artifact.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence, Tuple

import numpy as np
import pytest

from backend.attacks import (
    AttackContext,
    AuthorizationContext,
    build_attack_scenario,
)
from backend.detection import (
    ObservableDetectionInput,
    StateEvidence,
    VerificationEvidence,
)
from backend.noise import build_noise_channel
from backend.protocol.encoding import derive_state_sequence
from backend.protocol.models import (
    PROTOCOL_VERSION,
    Transcript,
    VerifierContext,
)
from backend.protocol.session import create_session, session_binding
from backend.protocol.signer import sign_session
from backend.quantum.density import projector
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import uncorrected_branch_states
from backend.simulation import ScenarioConfig, run_scenario
from backend.simulation.seed import derive_seed, generator

MESSAGE = "transfer 100 units to account 7"
SESSION_ID = "a" * 32
NONCE = "b" * 64
CREATED_AT = "2026-09-13T10:00:00+00:00"



BASE: Dict[str, Any] = dict(
    scenario_id="det",
    message=MESSAGE,
    signer_id="alice",
    verifier_id="bob",
    state_count=4,
    random_seed=7,
    session_id=SESSION_ID,
    nonce=NONCE,
    created_at=CREATED_AT,
)







def make_transcript(
    *,
    message: str = MESSAGE,
    signer_id: str = "alice",
    verifier_id: str = "bob",
    state_count: int = 4,
    protocol_version: str = PROTOCOL_VERSION,
    session_id: str = SESSION_ID,
    nonce: str = NONCE,
    created_at: str = CREATED_AT,
    seed: int = 1,
) -> Tuple[Any, Transcript]:
    """Build a deterministic session and its canonical transcript."""
    session = create_session(
        message,
        signer_id=signer_id,
        verifier_id=verifier_id,
        state_count=state_count,
        protocol_version=protocol_version,
        session_id_factory=lambda: session_id,
        nonce_factory=lambda: nonce,
        clock=lambda: created_at,
    )
    return session, sign_session(session, simulator_seed=seed).transcript


def observation_states(
    transcript: Transcript,
    *,
    probability: float = 1.0,
    matched: bool = True,
    matched_overrides: Dict[int, bool] | None = None,
    probability_overrides: Dict[int, float] | None = None,
) -> Tuple[StateEvidence, ...]:
    """Return per-state observations matching ``transcript``."""
    overrides = matched_overrides or {}
    probabilities = probability_overrides or {}
    return tuple(
        StateEvidence(
            index=state.index,
            basis=state.basis,
            expected_bit=0 if state.eigenvalue > 0 else 1,
            probability_expected=probabilities.get(state.index, probability),
            matched=overrides.get(state.index, matched),
        )
        for state in transcript.states
    )


def detection_input(
    transcript: Transcript,
    *,
    message: str | None = MESSAGE,
    states: Sequence[StateEvidence] | None = None,
    verifier_context_id: str | None = None,
    expected_protocol_version: str | None = None,
    payload: Dict[str, Any] | None = None,
    transcript_parse_error: str | None = None,
    verification: VerificationEvidence | None = None,
    **overrides: Any,
) -> ObservableDetectionInput:
    """Build a detection input from a transcript, deriving every identity field.

    ``overrides`` are applied last, so a test can replace any single field --
    the nonce, the declared hash, the authorized sets -- without restating the
    rest of the contract.
    """
    body = dict(payload) if payload is not None else transcript.to_dict()
    observed = tuple(states) if states is not None else observation_states(transcript)

    counts: Dict[str, int] = {}
    for record in observed:
        if isinstance(record.basis, str):
            counts[record.basis] = counts.get(record.basis, 0) + 1

    defaults: Dict[str, Any] = dict(
        session_id=body.get("session_id"),
        nonce=body.get("nonce"),
        protocol_version=body.get("protocol_version"),
        message_binding=body.get("message_binding"),
        declared_transcript_hash=body.get("transcript_hash"),
        signer_id=body.get("signer_id"),
        verifier_id=body.get("verifier_id"),
        created_at=body.get("created_at"),
        message=message,
        verifier_context_id=(
            verifier_context_id
            if verifier_context_id is not None
            else body.get("verifier_id")
        ),
        expected_protocol_version=(
            expected_protocol_version
            if expected_protocol_version is not None
            else body.get("protocol_version")
        ),
        authorized_signers=(str(body.get("signer_id")),),
        authorized_verifiers=(str(body.get("verifier_id")),),
        reported_signer_authorized=True,
        reported_verifier_authorized=True,
        transcript_payload=body,
        transcript_parse_error=transcript_parse_error,
        states=observed,
        declared_state_count=body.get("state_count"),
        measurement_mode="projective-analytic",
        basis_counts=counts,
        verification=(
            verification
            if verification is not None
            else VerificationEvidence(
                available=True,
                accepted=True,
                session_valid=True,
                message_valid=True,
                transcript_valid=True,
                state_sequence_valid=True,
                measurement_valid=True,
                errors=(),
                warnings=(),
                declared_mismatch_count=0,
                declared_basis_counts=counts,
                measurement_summary={
                    "checked": len(observed),
                    "matched": len(observed),
                    "mismatched": 0,
                },
            )
        ),
    )
    defaults.update(overrides)
    return ObservableDetectionInput(**defaults)


def valid_input(**overrides: Any) -> ObservableDetectionInput:
    """Return a fully valid, fully consistent detection input."""
    _, transcript = make_transcript()
    return detection_input(transcript, **overrides)







def reconstruct_transcript(
    config: ScenarioConfig,
) -> Tuple[Transcript, VerifierContext, Any]:
    """Rebuild the transcript the runner produced for ``config``.

    Mirrors ``ExperimentRunner.run`` steps 1-5 exactly. See the module docstring
    for why this is not taken from the experiment result.
    """
    session = create_session(
        config.message,
        signer_id=config.signer_id,
        verifier_id=config.verifier_id,
        state_count=config.state_count,
        protocol_version=config.protocol_version,
        session_id_factory=lambda: config.session_id,
        nonce_factory=lambda: config.nonce,
        clock=lambda: config.created_at,
    )
    transcript = sign_session(
        session, simulator_seed=derive_seed(config.random_seed, "signing")
    ).transcript
    verifier_context = VerifierContext(
        verifier_id=config.verifier_id,
        expected_protocol_version=config.protocol_version,
    )

    scenario = build_attack_scenario(config.attack)
    if scenario is None:
        return transcript, verifier_context, session

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

    outcome = scenario.apply(
        AttackContext(
            message=config.message,
            session=session,
            transcript=transcript,
            received_states=noisy_received,
            verifier_context=verifier_context,
            authorization=AuthorizationContext.from_session(session),
            rng=generator(config.random_seed, "attack", config.attack.attack_type),
        )
    )
    return outcome.transcript, outcome.verifier_context, session


def end_to_end_input(config: ScenarioConfig) -> ObservableDetectionInput:
    """Run ``config`` and adapt the observable half plus the transcript."""
    observable = run_scenario(config).observable
    transcript, verifier_context, _ = reconstruct_transcript(config)
    return ObservableDetectionInput.from_observable(
        observable,
        transcript=transcript,
        message=config.message,
        verifier_context=verifier_context,
    )


@pytest.fixture
def base_config() -> ScenarioConfig:
    """A plain, honest, noiseless scenario."""
    return ScenarioConfig(**BASE)


@pytest.fixture
def ideal_input(base_config: ScenarioConfig) -> ObservableDetectionInput:
    """Detection input for a noiseless, untampered experiment."""
    return end_to_end_input(base_config)


def features_for(
    detection: ObservableDetectionInput,
    **kwargs: Any,
) -> Any:
    """Return the extracted feature record for ``detection``."""
    from backend.detection import (
        analyse_authorization,
        analyse_consistency,
        extract_features,
    )

    return extract_features(
        detection,
        consistency=analyse_consistency(detection),
        authorization=analyse_authorization(detection),
        **kwargs,
    )







def reseal_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``payload`` with a correctly recomputed transcript hash.

    Tampering with a field and *not* re-sealing would trip the hash check first
    and hide the check under test, so every tamper helper re-seals.
    """
    from backend.protocol.transcript import compute_transcript_hash

    body = {key: value for key, value in payload.items() if key != "transcript_hash"}
    return {**body, "transcript_hash": compute_transcript_hash(body)}


def tamper_state_identifier(
    payload: Dict[str, Any], index: int = 0
) -> Dict[str, Any]:
    """Replace one declared state identifier with a different valid one."""
    from backend.protocol.encoding import STATE_ALPHABET

    body = {
        key: value for key, value in payload.items() if key != "transcript_hash"
    }
    states = [dict(state) for state in body["states"]]
    current = states[index]["state_identifier"]
    replacement = next(item for item in STATE_ALPHABET if item != current)
    states[index]["state_identifier"] = replacement
    body["states"] = states
    return reseal_payload(body)


def tamper_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Change the declared state-sequence metadata without touching the states."""
    body = {
        key: value for key, value in payload.items() if key != "transcript_hash"
    }
    metadata = dict(body["state_sequence_metadata"])
    metadata["derivation"] = "declared-but-not-the-real-derivation"
    body["state_sequence_metadata"] = metadata
    return reseal_payload(body)


def with_declared_state_count(
    payload: Dict[str, Any], state_count: int
) -> Dict[str, Any]:
    """Set a different declared state count, keeping the artifact self-consistent."""
    body = {
        key: value for key, value in payload.items() if key != "transcript_hash"
    }
    body["state_count"] = state_count
    metadata = dict(body["state_sequence_metadata"])
    metadata["state_count"] = state_count
    body["state_sequence_metadata"] = metadata
    return reseal_payload(body)
