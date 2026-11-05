"""Tests for the signer workflow."""

from __future__ import annotations

import pytest

from backend.protocol import (
    DEFAULT_SIMULATOR_SEED,
    PROTOCOL_VERSION,
    STATE_ALPHABET,
    ProtocolValidationError,
    SessionStatus,
    SigningResult,
    derive_state_sequence,
    sign,
    sign_session,
    teleport_signature_state,
    transcript_from_json,
    transcript_to_json,
)
from backend.protocol.session import session_binding

from tests.protocol.conftest import (
    MESSAGE,
    NONCE,
    OTHER_MESSAGE,
    SESSION_ID,
    SIGNER_ID,
    STATE_COUNT,
    VERIFIER_ID,
)


def test_signing_returns_a_session_and_a_transcript(signed) -> None:
    assert isinstance(signed, SigningResult)
    assert signed.session is not None
    assert signed.transcript is not None


def test_session_is_marked_signed(signed) -> None:
    assert signed.session.status is SessionStatus.SIGNED


def test_transcript_matches_the_session(signed) -> None:
    session = signed.session
    transcript = signed.transcript
    assert transcript.session_id == session.session_id
    assert transcript.nonce == session.nonce
    assert transcript.message_hash == session.message_hash
    assert transcript.signer_id == session.signer_id
    assert transcript.verifier_id == session.verifier_id
    assert transcript.protocol_version == session.protocol_version
    assert transcript.state_count == session.state_count
    assert transcript.created_at == session.created_at
    assert transcript.message_binding == session_binding(session)


def test_transcript_has_one_branch_per_state(transcript) -> None:
    assert len(transcript.teleportation_branches) == transcript.state_count
    for position, branch in enumerate(transcript.teleportation_branches):
        assert branch.index == position
        assert branch.m0 in (0, 1)
        assert branch.m1 in (0, 1)


def test_transcript_states_match_the_derived_sequence(transcript) -> None:
    expected = derive_state_sequence(transcript.message_binding, transcript.state_count)
    assert transcript.states == expected


def test_all_state_identifiers_are_from_the_alphabet(transcript) -> None:
    assert all(
        state.state_identifier in STATE_ALPHABET for state in transcript.states
    )


def test_signing_is_deterministic_for_a_fixed_seed(session) -> None:
    first = sign_session(session, simulator_seed=7)
    second = sign_session(session, simulator_seed=7)
    assert first.transcript == second.transcript


def test_state_sequence_is_independent_of_the_simulator_seed(session) -> None:
    """The signature states come from the message binding, not the simulator."""
    first = sign_session(session, simulator_seed=0)
    second = sign_session(session, simulator_seed=12345)
    assert first.transcript.states == second.transcript.states
    assert first.transcript.message_binding == second.transcript.message_binding


def test_default_seed_is_documented_and_fixed() -> None:
    assert DEFAULT_SIMULATOR_SEED == 0


def test_sign_creates_a_session_when_none_is_supplied() -> None:
    result = sign(
        MESSAGE, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID, state_count=2
    )
    assert result.transcript.state_count == 2
    assert result.session.session_id != SESSION_ID
    assert len(result.transcript.states) == 2


def test_sign_rejects_a_session_for_a_different_message(session) -> None:
    with pytest.raises(ProtocolValidationError):
        sign(
            OTHER_MESSAGE,
            signer_id=SIGNER_ID,
            verifier_id=VERIFIER_ID,
            session=session,
        )


def test_signature_does_not_depend_on_the_message_being_short() -> None:
    long_message = "x" * 5000
    result = sign(
        long_message, signer_id=SIGNER_ID, verifier_id=VERIFIER_ID, state_count=2
    )
    assert result.transcript.message_hash
    assert len(result.transcript.states) == 2


def test_unicode_message_is_supported() -> None:
    result = sign(
        "virement de 100 \u20ac \u2014 caf\u00e9",
        signer_id=SIGNER_ID,
        verifier_id=VERIFIER_ID,
        state_count=2,
    )
    restored = transcript_from_json(transcript_to_json(result.transcript))
    assert restored == result.transcript


def test_transcript_survives_serialization(signed) -> None:
    text = transcript_to_json(signed.transcript)
    assert transcript_from_json(text) == signed.transcript


def test_protocol_version_is_recorded(signed) -> None:
    assert signed.transcript.protocol_version == PROTOCOL_VERSION


def test_recorded_branches_are_valid_bell_outcomes(transcript) -> None:
    observed = {
        (branch.m0, branch.m1) for branch in transcript.teleportation_branches
    }
    assert observed <= {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert observed


def test_recorded_branches_faithfully_report_the_m1_engine(transcript) -> None:
    """Re-running the engine with the documented seed reproduces the record.

    This checks that the transcript *records* what the M1 teleportation engine
    actually produced (with the documented per-state seeding) rather than
    storing a fabricated value.
    """
    for state in transcript.states:
        reproduced = teleport_signature_state(
            state, simulator_seed=DEFAULT_SIMULATOR_SEED + state.index
        )
        assert reproduced == transcript.teleportation_branches[state.index]


def test_signer_does_not_import_attack_or_detection_modules() -> None:
    import backend.protocol.signer as signer_module

    with open(signer_module.__file__, encoding="utf-8") as handle:
        source = handle.read()
    for forbidden in ("backend.attacks", "backend.detection", "backend.noise"):
        assert forbidden not in source


def test_state_count_matches_the_session(signed) -> None:
    assert signed.transcript.state_count == STATE_COUNT
    assert len(signed.transcript.states) == STATE_COUNT


def test_session_nonce_is_not_regenerated_by_signing(signed) -> None:
    """The nonce is part of the binding and must be carried through unchanged."""
    assert signed.transcript.nonce == NONCE
