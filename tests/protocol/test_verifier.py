"""Tests for the verifier workflow and the quantum verification path."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from backend.protocol import (
    PROTOCOL_VERSION,
    STATE_ALPHABET,
    VerifierContext,
    derive_state_sequence,
    measure_state_in_basis,
    state_for_identifier,
    transcript_from_json,
    transcript_to_json,
    verify,
    verify_state_measurement,
)
from backend.protocol.models import TeleportationBranch
from backend.protocol.verifier import ReferenceVerifier
from backend.quantum.states import EIGENSTATE_LABELS, get_eigenstate

from tests.protocol.conftest import MESSAGE, VERIFIER_ID

BRANCHES = ((0, 0), (0, 1), (1, 0), (1, 1))


@pytest.fixture(scope="session")
def context() -> VerifierContext:
    return VerifierContext(verifier_id=VERIFIER_ID)







@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_measure_state_in_basis_is_one_for_the_matching_basis(label: str) -> None:
    """An eigenstate measured in its own basis is deterministic."""
    core = get_eigenstate(label)
    probability = measure_state_in_basis(
        core.vector, core.basis, int(core.eigenvalue)
    )
    assert np.isclose(probability, 1.0, atol=1e-12)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_measure_state_in_basis_is_one_half_for_a_foreign_basis(label: str) -> None:
    """An eigenstate measured in another basis is unbiased."""
    core = get_eigenstate(label)
    for basis in ("X", "Y", "Z"):
        if basis == core.basis:
            continue
        assert np.isclose(
            measure_state_in_basis(core.vector, basis, +1), 0.5, atol=1e-12
        )


def test_measure_state_in_basis_is_falsifiable() -> None:
    """The measurement path can actually fail, so it is not decorative.

    ``|0>`` is the ``+1`` eigenstate of ``Z`` but is unbiased in the ``X``
    basis, so the same expectation that holds in ``Z`` must fail in ``X``.
    """
    zero = get_eigenstate("|0>").vector
    assert np.isclose(measure_state_in_basis(zero, "Z", +1), 1.0, atol=1e-12)
    assert not np.isclose(measure_state_in_basis(zero, "X", +1), 1.0, atol=1e-9)
    assert not np.isclose(measure_state_in_basis(zero, "Z", -1), 1.0, atol=1e-9)


@pytest.mark.parametrize("identifier", STATE_ALPHABET)
@pytest.mark.parametrize("branch", BRANCHES)
def test_verify_state_measurement_succeeds_for_every_state_and_branch(
    identifier: str, branch: tuple
) -> None:
    """All six states must survive all four Bell branches."""
    state = state_for_identifier(identifier)
    m0, m1 = branch
    measurement = verify_state_measurement(
        state, TeleportationBranch(index=0, m0=m0, m1=m1)
    )
    assert measurement.matched, (identifier, branch, measurement.probability)
    assert np.isclose(measurement.probability, 1.0, atol=1e-12)


def test_ideal_model_recovers_the_state_for_every_branch() -> None:
    """Documented limitation, asserted rather than hidden.

    In the ideal model the Pauli correction inverts whichever branch occurred,
    so the received qubit always comes back to the expected state and the
    per-state measurement cannot fail. That is why ``measure_state_in_basis``
    is tested for falsifiability in its own right above, and why
    ``measurement_valid`` only becomes discriminating once a real channel
    (noise, tampering) is introduced in a later milestone.
    """
    for identifier in STATE_ALPHABET:
        state = state_for_identifier(identifier)
        for m0, m1 in BRANCHES:
            measurement = verify_state_measurement(
                state, TeleportationBranch(index=0, m0=m0, m1=m1)
            )
            assert np.isclose(measurement.probability, 1.0, atol=1e-12)







def test_legitimate_transcript_is_accepted(transcript, context) -> None:
    result = ReferenceVerifier().verify(transcript, MESSAGE, context)
    assert result.accepted, result.verification_errors
    assert result.transcript_valid
    assert result.session_valid
    assert result.message_valid
    assert result.state_sequence_valid
    assert result.measurement_valid
    assert result.verification_errors == ()


def test_verifier_accepts_a_transcript_object(transcript, context) -> None:
    assert verify(transcript, MESSAGE, context).accepted


def test_verifier_accepts_plain_transcript_data(transcript, context) -> None:
    assert verify(copy.deepcopy(transcript.to_dict()), MESSAGE, context).accepted


def test_verifier_accepts_a_deserialized_transcript(transcript, context) -> None:
    restored = transcript_from_json(transcript_to_json(transcript))
    assert verify(restored, MESSAGE, context).accepted


def test_verification_is_deterministic(transcript, context) -> None:
    first = ReferenceVerifier().verify(transcript, MESSAGE, context)
    second = ReferenceVerifier().verify(transcript, MESSAGE, context)
    assert first == second


def test_diagnostics_are_reported(transcript, context) -> None:
    result = verify(transcript, MESSAGE, context)
    assert result.state_count == transcript.state_count
    assert result.mismatch_count == 0
    assert sum(result.basis_counts.values()) == transcript.state_count
    assert set(result.basis_counts) <= {"X", "Y", "Z"}
    assert result.measurement_summary["checked"] == transcript.state_count
    assert result.measurement_summary["matched"] == transcript.state_count
    assert result.measurement_summary["mismatched"] == 0


def test_verification_always_warns_that_it_is_structural(transcript, context) -> None:
    """The result must never read as a formal security guarantee."""
    result = verify(transcript, MESSAGE, context)
    assert result.verification_warnings
    assert "not unforgeability" in " ".join(result.verification_warnings)


def test_result_is_serializable(transcript, context) -> None:
    payload = verify(transcript, MESSAGE, context).to_dict()
    assert payload["accepted"] is True
    assert isinstance(payload["verification_errors"], list)
    assert isinstance(payload["basis_counts"], dict)


def test_verifier_rejects_a_transcript_addressed_elsewhere(transcript) -> None:
    result = verify(transcript, MESSAGE, VerifierContext(verifier_id="eve"))
    assert not result.accepted
    assert not result.session_valid
    assert any("addressed to verifier" in error for error in result.verification_errors)


def test_verifier_rejects_an_unexpected_protocol_version(transcript) -> None:
    result = verify(
        transcript,
        MESSAGE,
        VerifierContext(verifier_id=VERIFIER_ID, expected_protocol_version="RQDS-TP-2.0"),
    )
    assert not result.accepted
    assert not result.session_valid
    assert any("protocol_version" in error for error in result.verification_errors)


def test_verifier_rejects_a_different_message(transcript, context) -> None:
    result = verify(transcript, MESSAGE + " ", context)
    assert not result.accepted
    assert not result.message_valid


def test_verifier_does_not_trust_the_signers_state_sequence(transcript, context) -> None:
    """The central separation requirement.

    A transcript whose declared states are internally consistent and correctly
    hashed, but which disagree with the sequence the verifier derives for
    itself, must be rejected on the state-sequence check alone.
    """
    data = copy.deepcopy(transcript.to_dict())
    declared = data["states"][0]["state_identifier"]
    replacement = next(item for item in STATE_ALPHABET if item != declared)
    template = state_for_identifier(replacement)
    data["states"][0] = {
        "index": 0,
        "basis": template.basis,
        "label": template.label,
        "eigenvalue": template.eigenvalue,
        "state_identifier": template.state_identifier,
    }


    from backend.protocol import compute_transcript_hash

    payload = {key: value for key, value in data.items() if key != "transcript_hash"}
    payload["transcript_hash"] = compute_transcript_hash(payload)

    result = verify(payload, MESSAGE, context)
    assert not result.accepted
    assert result.transcript_valid
    assert result.message_valid
    assert not result.state_sequence_valid
    assert result.mismatch_count == 1


def test_verifier_derives_the_same_sequence_the_signer_used(transcript) -> None:
    """Independent reconstruction must agree with the signer for a good transcript."""
    derived = derive_state_sequence(
        transcript.message_binding, transcript.state_count
    )
    assert derived == transcript.states


def test_protocol_version_constant_is_the_reference_version() -> None:
    assert PROTOCOL_VERSION == "RQDS-TP-1.0"
