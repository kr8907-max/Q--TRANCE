"""Session creation for the reference QDS protocol.

Two kinds of randomness
-----------------------
The protocol uses randomness for two entirely different purposes, and this
module exists partly to keep them apart:

**Cryptographic randomness (protocol identifiers).**
``session_id`` and ``nonce`` are produced by :mod:`secrets`, i.e. by the
operating system's CSPRNG. They must be unpredictable and unique, they are
never derived from the message, and they are *not* reproducible. Nothing about
them depends on the simulator.

**Simulator randomness (reproducible experiments).**
The Aer simulator seed that governs the teleportation branch outcomes lives in
:mod:`backend.protocol.signer`. It is a plain integer, it is reproducible on
purpose, and it has no security meaning whatsoever. It is never mixed into
``session_id`` or ``nonce``.

Both are overridable by injection so that tests can control randomness
explicitly -- and *only* explicitly.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from backend.protocol.binding import compute_message_binding, compute_message_hash
from backend.protocol.encoding import sequence_metadata
from backend.protocol.models import (
    DEFAULT_STATE_COUNT,
    NONCE_BYTES,
    PROTOCOL_VERSION,
    SESSION_ID_BYTES,
    Session,
    SessionStatus,
    validate_created_at,
    validate_hex_digest,
    validate_identifier,
    validate_message,
    validate_protocol_version,
    validate_state_count,
)

__all__ = [
    "new_session_id",
    "new_nonce",
    "utc_now_iso",
    "session_binding",
    "create_session",
    "session_with_status",
]


def new_session_id() -> str:
    """Return a fresh 128-bit session identifier as lowercase hex."""
    return secrets.token_hex(SESSION_ID_BYTES)


def new_nonce() -> str:
    """Return a fresh 256-bit nonce as lowercase hex."""
    return secrets.token_hex(NONCE_BYTES)


def utc_now_iso() -> str:
    """Return the current UTC time as a second-resolution ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session_binding(session: Session) -> str:
    """Recompute the message binding of ``session`` from its own fields.

    The binding is a pure function of the session's protocol version, session
    identifier, nonce and message, so it is never stored as an independent
    field that could drift out of step with them.
    """
    return compute_message_binding(
        protocol_version=session.protocol_version,
        session_id=session.session_id,
        nonce=session.nonce,
        message=session.message,
    )


def create_session(
    message: str,
    *,
    signer_id: str,
    verifier_id: str,
    state_count: int = DEFAULT_STATE_COUNT,
    protocol_version: str = PROTOCOL_VERSION,
    session_id_factory: Callable[[], str] = new_session_id,
    nonce_factory: Callable[[], str] = new_nonce,
    clock: Callable[[], str] = utc_now_iso,
) -> Session:
    """Create a signing session for ``message``.

    Parameters
    ----------
    message:
        The message to be signed. Must be a non-empty string; it is normalised
        to NFC so that the binding is stable.
    signer_id, verifier_id:
        Identities of the two parties. Validated against a conservative
        identifier pattern.
    state_count:
        Number of reference states in the signature sequence.
    protocol_version:
        Reference protocol version to bind.
    session_id_factory, nonce_factory, clock:
        Injection points. The defaults are the real CSPRNG and the real clock;
        tests pass deterministic callables to make a session reproducible.

    The returned session is *not* the source of truth for the state sequence:
    the sequence is derived on demand from the message binding.
    """
    normalized_message = validate_message(message)
    validated_signer = validate_identifier(signer_id, "signer_id")
    validated_verifier = validate_identifier(verifier_id, "verifier_id")
    validated_count = validate_state_count(state_count)
    validated_version = validate_protocol_version(protocol_version, "protocol_version")

    session_id = validate_hex_digest(
        session_id_factory(), "session_id", SESSION_ID_BYTES
    )
    nonce = validate_hex_digest(nonce_factory(), "nonce", NONCE_BYTES)
    created_at = validate_created_at(clock())

    message_hash = compute_message_hash(normalized_message)
    binding = compute_message_binding(
        protocol_version=validated_version,
        session_id=session_id,
        nonce=nonce,
        message=normalized_message,
    )

    metadata: Dict[str, Any] = dict(
        sequence_metadata(validated_count, binding=binding)
    )

    return Session(
        session_id=session_id,
        nonce=nonce,
        message=normalized_message,
        message_hash=message_hash,
        signer_id=validated_signer,
        verifier_id=validated_verifier,
        protocol_version=validated_version,
        state_count=validated_count,
        state_sequence_metadata=metadata,
        created_at=created_at,
        status=SessionStatus.CREATED,
    )


def session_with_status(session: Session, status: SessionStatus) -> Session:
    """Return a copy of ``session`` with a different lifecycle status."""
    from dataclasses import replace

    return replace(session, status=status)
