"""Protocol-integrity negative tests (A-G) and malformed-input handling.

These tests demonstrate that the message/session/transcript binding actually
works. They are **not** attack simulations: no noise model, no channel
tampering, no impersonation behaviour and no threshold classification is
involved. Each case tampers with protocol data and asserts that verification
fails for a stated reason.

A note on "resealing"
---------------------
For every field except ``transcript_hash`` the test tampers with the value *and*
recomputes the transcript hash, exactly as an attacker who knows the public
canonicalization could. Without resealing, the transcript-hash check would catch
everything and the test would prove nothing about the binding. Resealing forces
the failure to come from the binding/consistency logic itself.
"""

from __future__ import annotations

import copy

import pytest

from backend.protocol import (
    STATE_ALPHABET,
    VerifierContext,
    compute_transcript_hash,
    state_for_identifier,
    transcript_from_dict,
    TranscriptValidationError,
    verify,
)
from backend.protocol.models import ProtocolValidationError

from tests.protocol.conftest import MESSAGE, OTHER_MESSAGE, VERIFIER_ID


@pytest.fixture(scope="module")
def context() -> VerifierContext:
    return VerifierContext(verifier_id=VERIFIER_ID)


def reseal(data: dict) -> dict:
    """Recompute the transcript hash, as an attacker with public code could."""
    payload = {key: value for key, value in data.items() if key != "transcript_hash"}
    payload["transcript_hash"] = compute_transcript_hash(payload)
    return payload


def assert_rejected(result, *, reason: str | None = None) -> None:
    assert not result.accepted
    assert result.verification_errors
    if reason is not None:
        joined = " | ".join(result.verification_errors)
        assert reason in joined, joined







def test_a_modified_message_is_rejected(transcript, context) -> None:
    result = verify(transcript, OTHER_MESSAGE, context)
    assert_rejected(result)
    assert not result.message_valid
    assert not result.state_sequence_valid


def test_a_message_differing_by_one_character_is_rejected(transcript, context) -> None:
    result = verify(transcript, MESSAGE + " ", context)
    assert_rejected(result)
    assert not result.message_valid







def test_b_session_id_modified_is_rejected(transcript, context) -> None:
    data = copy.deepcopy(transcript.to_dict())
    data["session_id"] = "d" * 32
    result = verify(reseal(data), MESSAGE, context)
    assert_rejected(result, reason="message_binding")
    assert result.transcript_valid
    assert not result.message_valid
    assert not result.state_sequence_valid







def test_c_nonce_modified_is_rejected(transcript, context) -> None:
    data = copy.deepcopy(transcript.to_dict())
    data["nonce"] = "e" * 64
    result = verify(reseal(data), MESSAGE, context)
    assert_rejected(result, reason="message_binding")
    assert result.transcript_valid
    assert not result.message_valid







def test_d_protocol_version_modified_is_rejected(transcript, context) -> None:
    data = copy.deepcopy(transcript.to_dict())
    data["protocol_version"] = "RQDS-TP-9.9"
    result = verify(reseal(data), MESSAGE, context)
    assert_rejected(result, reason="protocol_version")
    assert not result.session_valid


def test_d_protocol_version_tamper_also_breaks_the_binding(transcript, context) -> None:
    """Even if the verifier spoke that version, the binding would fail."""
    data = copy.deepcopy(transcript.to_dict())
    data["protocol_version"] = "RQDS-TP-1.1"
    permissive = VerifierContext(
        verifier_id=VERIFIER_ID, expected_protocol_version="RQDS-TP-1.1"
    )
    result = verify(reseal(data), MESSAGE, permissive)
    assert_rejected(result)
    assert not result.message_valid







def test_e_transcript_hash_modified_is_rejected(transcript, context) -> None:
    data = copy.deepcopy(transcript.to_dict())
    data["transcript_hash"] = "0" * 64
    result = verify(data, MESSAGE, context)
    assert_rejected(result, reason="transcript_hash")
    assert not result.transcript_valid


def test_e_any_field_tampered_without_resealing_is_rejected(transcript, context) -> None:
    """The transcript hash covers every field, so a stale hash always fails."""
    for field, replacement in (
        ("nonce", "f" * 64),
        ("signer_id", "mallory"),
        ("created_at", "2020-01-01T00:00:00+00:00"),
        ("message_hash", "a" * 64),
        ("verification_metadata", {"basis_policy": "other"}),
    ):
        data = copy.deepcopy(transcript.to_dict())
        data[field] = replacement
        result = verify(data, MESSAGE, context)
        assert_rejected(result, reason="transcript_hash")
        assert not result.transcript_valid







def test_f_state_metadata_modified_is_rejected(transcript, context) -> None:
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
    result = verify(reseal(data), MESSAGE, context)
    assert_rejected(result, reason="declared states do not match")
    assert result.transcript_valid
    assert result.message_valid
    assert not result.state_sequence_valid
    assert result.mismatch_count == 1


def test_f_state_index_swap_is_rejected(transcript, context) -> None:
    """Swapping two states keeps the multiset but breaks the sequence."""
    data = copy.deepcopy(transcript.to_dict())
    assert data["states"][0] != data["states"][1]
    data["states"][0], data["states"][1] = data["states"][1], data["states"][0]
    for position, state in enumerate(data["states"]):
        state["index"] = position
    result = verify(reseal(data), MESSAGE, context)
    assert_rejected(result)
    assert not result.state_sequence_valid


def test_f_branch_metadata_tamper_is_caught_by_the_transcript_hash(
    transcript, context
) -> None:
    """A branch tamper without resealing is caught by the hash.

    With a recomputed hash it is *not* caught, and that limitation is
    documented rather than papered over: in the ideal model the Pauli
    correction inverts every branch exactly, so the branch bits carry no
    independently checkable information. See
    ``docs/protocol/reference-qds.md`` ("Known limitations").
    """
    data = copy.deepcopy(transcript.to_dict())
    data["teleportation_branches"][0]["m0"] = 1 - data["teleportation_branches"][0]["m0"]
    result = verify(data, MESSAGE, context)
    assert_rejected(result, reason="transcript_hash")

    resealed = verify(reseal(data), MESSAGE, context)
    assert resealed.accepted







@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.pop("nonce"),
        lambda d: d.update(nonce="not-hex"),
        lambda d: d.update(session_id="short"),
        lambda d: d.update(state_count=True),
        lambda d: d.update(state_count=-1),
        lambda d: d.update(transcript_version=99),
        lambda d: d.update(protocol_version="nope"),
        lambda d: d.update(signer_id="!!!"),
        lambda d: d.update(states="x"),
        lambda d: d.update(states=d["states"][:1]),
        lambda d: d.update(teleportation_branches="x"),
        lambda d: d.update(verification_metadata={"x": [1]}),
        lambda d: d.update(created_at="whenever"),
        lambda d: d.update(extra="unknown"),
    ],
)
def test_g_malformed_transcript_is_rejected_not_accepted(
    transcript, context, mutation
) -> None:
    data = copy.deepcopy(transcript.to_dict())
    mutation(data)
    result = verify(data, MESSAGE, context)
    assert_rejected(result, reason="transcript validation failed")


@pytest.mark.parametrize("bad", [None, [], "text", 42, {"only": "one field"}])
def test_g_structurally_wrong_input_is_rejected(bad, context) -> None:
    result = verify(bad, MESSAGE, context)
    assert_rejected(result, reason="transcript validation failed")


def test_g_malformed_transcript_raises_on_strict_parsing(transcript) -> None:
    """Strict callers get an exception; the verifier gets a structured rejection."""
    data = copy.deepcopy(transcript.to_dict())
    data["nonce"] = "not-hex"
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_g_malformed_transcript_never_raises_from_verify(transcript, context) -> None:
    """verify() must never crash on untrusted input."""
    data = copy.deepcopy(transcript.to_dict())
    for field, bad in (
        ("nonce", "zz"),
        ("session_id", 5),
        ("state_count", 2.5),
        ("states", [{"index": 0}]),
    ):
        tampered = copy.deepcopy(data)
        tampered[field] = bad
        result = verify(tampered, MESSAGE, context)
        assert not result.accepted


def test_inconsistent_state_record_is_rejected(transcript, context) -> None:
    """A record whose fields contradict each other fails validation."""
    data = copy.deepcopy(transcript.to_dict())
    declared = data["states"][0]["state_identifier"]
    data["states"][0]["state_identifier"] = next(
        item for item in STATE_ALPHABET if item != declared
    )
    with pytest.raises(ProtocolValidationError):
        transcript_from_dict(data)


def test_verifier_rejects_its_own_wrong_identity(transcript, context) -> None:
    result = verify(transcript, MESSAGE, VerifierContext(verifier_id="mallory"))
    assert_rejected(result, reason="addressed to verifier")
    assert not result.session_valid
