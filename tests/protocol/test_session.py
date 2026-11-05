"""Tests for session creation and identifier generation."""

from __future__ import annotations

import re

import pytest

from backend.protocol import (
    DEFAULT_STATE_COUNT,
    NONCE_BYTES,
    PROTOCOL_VERSION,
    SESSION_ID_BYTES,
    ProtocolValidationError,
    SessionStatus,
    compute_message_binding,
    compute_message_hash,
    create_session,
)
from backend.protocol.session import (
    new_nonce,
    new_session_id,
    session_binding,
    session_with_status,
    utc_now_iso,
)

HEX_SESSION = re.compile(r"^[0-9a-f]{%d}$" % (SESSION_ID_BYTES * 2))
HEX_NONCE = re.compile(r"^[0-9a-f]{%d}$" % (NONCE_BYTES * 2))
ISO_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00$")


def test_session_id_is_hex_of_the_expected_length() -> None:
    session_id = new_session_id()
    assert HEX_SESSION.match(session_id), session_id
    assert len(session_id) == SESSION_ID_BYTES * 2


def test_nonce_is_hex_of_the_expected_length() -> None:
    nonce = new_nonce()
    assert HEX_NONCE.match(nonce), nonce
    assert len(nonce) == NONCE_BYTES * 2


def test_generated_identifiers_are_unique() -> None:
    """Uniqueness is the property that matters, not any particular value."""
    session_ids = {new_session_id() for _ in range(512)}
    nonces = {new_nonce() for _ in range(512)}
    assert len(session_ids) == 512
    assert len(nonces) == 512


def test_identifiers_do_not_collide_across_kinds() -> None:
    for _ in range(64):
        assert new_session_id() != new_nonce()


def test_utc_now_iso_shape() -> None:
    assert ISO_UTC.match(utc_now_iso())


def test_create_session_populates_every_required_field() -> None:
    session = create_session("hello", signer_id="alice", verifier_id="bob")
    for field in (
        "session_id",
        "nonce",
        "message",
        "message_hash",
        "signer_id",
        "verifier_id",
        "protocol_version",
        "state_count",
        "state_sequence_metadata",
        "created_at",
        "status",
    ):
        assert hasattr(session, field), field
    assert session.protocol_version == PROTOCOL_VERSION
    assert session.state_count == DEFAULT_STATE_COUNT
    assert session.status is SessionStatus.CREATED
    assert session.message == "hello"
    assert session.message_hash == compute_message_hash("hello")


def test_identifiers_are_injectable_for_deterministic_tests() -> None:
    session = create_session(
        "hello",
        signer_id="alice",
        verifier_id="bob",
        session_id_factory=lambda: "f" * 32,
        nonce_factory=lambda: "e" * 64,
        clock=lambda: "2026-01-02T03:04:05+00:00",
    )
    assert session.session_id == "f" * 32
    assert session.nonce == "e" * 64
    assert session.created_at == "2026-01-02T03:04:05+00:00"


def test_default_identifiers_differ_between_sessions() -> None:
    first = create_session("hello", signer_id="alice", verifier_id="bob")
    second = create_session("hello", signer_id="alice", verifier_id="bob")
    assert first.session_id != second.session_id
    assert first.nonce != second.nonce


def test_message_is_normalised_to_nfc() -> None:
    composed = create_session("caf\u00e9", signer_id="alice", verifier_id="bob")
    decomposed = create_session("cafe\u0301", signer_id="alice", verifier_id="bob")
    assert composed.message == decomposed.message
    assert composed.message_hash == decomposed.message_hash


def test_session_binding_matches_the_binding_function() -> None:
    session = create_session("hello", signer_id="alice", verifier_id="bob")
    assert session_binding(session) == compute_message_binding(
        protocol_version=session.protocol_version,
        session_id=session.session_id,
        nonce=session.nonce,
        message=session.message,
    )


def test_session_carries_no_state_sequence() -> None:
    """The session must not be the source of truth for the state sequence."""
    session = create_session("hello", signer_id="alice", verifier_id="bob")
    payload = session.to_dict()
    assert "states" not in payload
    assert "state_sequence" not in payload

    assert "alphabet" in session.state_sequence_metadata
    assert "states" not in session.state_sequence_metadata


def test_session_with_status_returns_a_copy() -> None:
    session = create_session("hello", signer_id="alice", verifier_id="bob")
    signed = session_with_status(session, SessionStatus.SIGNED)
    assert signed.status is SessionStatus.SIGNED
    assert session.status is SessionStatus.CREATED
    assert signed.session_id == session.session_id


@pytest.mark.parametrize("bad_message", ["", 5, None, b"bytes"])
def test_invalid_message_is_rejected(bad_message) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(bad_message, signer_id="alice", verifier_id="bob")


@pytest.mark.parametrize("bad_id", ["", "with space", "!!", "a" * 129, 7])
def test_invalid_identifiers_are_rejected(bad_id) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session("hello", signer_id=bad_id, verifier_id="bob")
    with pytest.raises(ProtocolValidationError):
        create_session("hello", signer_id="alice", verifier_id=bad_id)


@pytest.mark.parametrize("bad_count", [0, -1, True, 1.5, "4", 10_000])
def test_invalid_state_count_is_rejected(bad_count) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(
            "hello", signer_id="alice", verifier_id="bob", state_count=bad_count
        )


@pytest.mark.parametrize("bad_version", ["", "1.0", "RQDS-TP-1", "rqds-tp-1.0", 3])
def test_invalid_protocol_version_is_rejected(bad_version) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(
            "hello",
            signer_id="alice",
            verifier_id="bob",
            protocol_version=bad_version,
        )


@pytest.mark.parametrize(
    "bad_id", ["", "a" * 31, "A" * 32, "g" * 32, "z" * 64, "a" * 33]
)
def test_malformed_injected_session_id_is_rejected(bad_id) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(
            "hello",
            signer_id="alice",
            verifier_id="bob",
            session_id_factory=lambda: bad_id,
        )


@pytest.mark.parametrize("bad_nonce", ["", "b" * 63, "B" * 64, "q" * 64])
def test_malformed_injected_nonce_is_rejected(bad_nonce) -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(
            "hello",
            signer_id="alice",
            verifier_id="bob",
            nonce_factory=lambda: bad_nonce,
        )


def test_malformed_clock_is_rejected() -> None:
    with pytest.raises(ProtocolValidationError):
        create_session(
            "hello",
            signer_id="alice",
            verifier_id="bob",
            clock=lambda: "2026-01-02 03:04:05",
        )
