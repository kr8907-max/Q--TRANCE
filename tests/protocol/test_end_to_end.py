"""End-to-end reference workflow tests.

The flow under test is the one the milestone defines::

    message -> session -> binding -> state sequence -> teleportation
            -> transcript -> serialize -> deserialize -> verify -> result
"""

from __future__ import annotations

import numpy as np
from qiskit.quantum_info import Statevector

from backend.protocol import (
    DEFAULT_STATE_COUNT,
    PROTOCOL_VERSION,
    SessionStatus,
    VerifierContext,
    create_session,
    describe_protocol,
    sign,
    transcript_from_json,
    transcript_to_json,
    verify,
)
from backend.quantum.bell import bell_amplitudes_exact, bell_circuit
from backend.quantum.measure import run_counts
from backend.quantum.states import EIGENSTATE_LABELS, get_eigenstate

from tests.protocol.conftest import MESSAGE, SIGNER_ID, VERIFIER_ID


SMALL = 4
VERIFY_CONTEXT = VerifierContext(verifier_id=VERIFIER_ID)


def test_ideal_signature_verifies_through_a_serialization_round_trip() -> None:
    """The acceptance criterion: sign, serialize, deserialize, verify."""
    result = sign(
        MESSAGE, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID, state_count=SMALL
    )
    assert result.session.status is SessionStatus.SIGNED

    wire = transcript_to_json(result.transcript)
    received = transcript_from_json(wire)

    outcome = verify(received, MESSAGE, VERIFY_CONTEXT)
    assert outcome.accepted, outcome.verification_errors
    assert outcome.measurement_summary["matched"] == SMALL
    assert outcome.mismatch_count == 0


def test_reference_configuration_verifies() -> None:
    """The same flow at the documented default state count."""
    result = sign(MESSAGE, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID)
    assert result.transcript.state_count == DEFAULT_STATE_COUNT

    outcome = verify(
        transcript_from_json(transcript_to_json(result.transcript)),
        MESSAGE,
        VERIFY_CONTEXT,
    )
    assert outcome.accepted, outcome.verification_errors
    assert outcome.state_count == DEFAULT_STATE_COUNT


def test_two_independent_sessions_both_verify() -> None:
    """Independent sessions of the same message must each verify."""
    for _ in range(2):
        result = sign(
            MESSAGE, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID, state_count=2
        )
        assert verify(result.transcript, MESSAGE, VERIFY_CONTEXT).accepted


def test_changing_only_the_nonce_changes_the_state_sequence() -> None:
    """This is what makes the nonce load-bearing rather than decorative."""
    shared = dict(
        signer_id=SIGNER_ID,
        verifier_id=VERIFIER_ID,
        state_count=8,
        session_id_factory=lambda: "a" * 32,
        clock=lambda: "2026-09-12T17:00:00+00:00",
    )
    first = sign(
        MESSAGE,
        session=create_session(MESSAGE, nonce_factory=lambda: "b" * 64, **shared),
    )
    second = sign(
        MESSAGE,
        session=create_session(MESSAGE, nonce_factory=lambda: "c" * 64, **shared),
    )

    assert first.transcript.message_binding != second.transcript.message_binding
    assert first.transcript.states != second.transcript.states
    assert verify(first.transcript, MESSAGE, VERIFY_CONTEXT).accepted
    assert verify(second.transcript, MESSAGE, VERIFY_CONTEXT).accepted


def test_changing_only_the_session_id_changes_the_state_sequence() -> None:
    shared = dict(
        signer_id=SIGNER_ID,
        verifier_id=VERIFIER_ID,
        state_count=8,
        nonce_factory=lambda: "b" * 64,
        clock=lambda: "2026-09-12T17:00:00+00:00",
    )
    first = sign(
        MESSAGE,
        session=create_session(MESSAGE, session_id_factory=lambda: "a" * 32, **shared),
    )
    second = sign(
        MESSAGE,
        session=create_session(MESSAGE, session_id_factory=lambda: "d" * 32, **shared),
    )
    assert first.transcript.states != second.transcript.states


def test_protocol_description_makes_no_security_claim() -> None:
    description = describe_protocol()
    assert description["protocol_version"] == PROTOCOL_VERSION
    assert description["formal_security_claim"] is False
    assert description["standardized"] is False
    assert description["kind"] == "reference-prototype-construction"


def test_verification_result_carries_no_threshold_statistics() -> None:
    """M2 exposes raw counts only: no rates, no thresholds, no attack labels."""
    result = sign(
        MESSAGE, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID, state_count=2
    )
    payload = verify(result.transcript, MESSAGE, VERIFY_CONTEXT).to_dict()
    for forbidden in (
        "false_positive",
        "false_negative",
        "threshold",
        "attack",
        "detected",
        "confidence",
        "score",
        "rate",
    ):
        assert not any(forbidden in key for key in payload), forbidden


def test_m1_quantum_core_is_unaffected_by_m2() -> None:
    """Cheap regression guard that M2 did not disturb the verified M1 core."""
    assert len(EIGENSTATE_LABELS) == 6
    for label in EIGENSTATE_LABELS:
        state = get_eigenstate(label)
        assert np.isclose(np.linalg.norm(state.vector), 1.0, atol=1e-12)
    produced = np.asarray(Statevector(bell_circuit()).data, dtype=complex)
    assert np.allclose(produced, bell_amplitudes_exact(), atol=1e-12)


def test_m1_sampling_still_reproduces() -> None:
    circuit = bell_circuit()
    circuit.measure_all()
    assert run_counts(circuit, shots=500, seed_simulator=2024) == run_counts(
        circuit, shots=500, seed_simulator=2024
    )
