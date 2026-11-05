"""Orchestration for the signing-session lifecycle.

Thin by design. It calls the M2 session constructor and the M2 signer, then
records what they returned. No protocol logic is reimplemented here: the binding,
the state sequence, the transcript and its hash are all produced by
:mod:`backend.protocol`.

The simulator seed is fixed
---------------------------
Signing runs the reference signer, whose quantum branches are drawn from a
seeded generator. The API pins that seed, so signing the same session twice
yields the same transcript. The protocol documents this randomness as simulator
randomness that carries no security meaning, which is exactly why pinning it is
safe and why a caller is not offered a knob for it.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.api.config import ApiSettings
from backend.api.schemas.session import SessionCreateRequest
from backend.api.store import ApiStore, SessionLifecycle, SessionRecord
from backend.protocol import (
    Session,
    create_session,
    session_binding,
    sign_session,
)


API_SIGNING_SIMULATOR_SEED = 0


def create(store: ApiStore, request: SessionCreateRequest) -> SessionRecord:
    """Create a reference session and register it as CREATED."""
    session = create_session(
        request.message,
        signer_id=request.signer_id,
        verifier_id=request.verifier_id,
        state_count=request.state_count,
        protocol_version=request.protocol_version,
    )
    return store.add_session(SessionRecord(session=session))


def sign(store: ApiStore, session_id: str, settings: ApiSettings) -> SessionRecord:
    """Sign a CREATED session and move it to SIGNED.

    Signing runs outside the lock, because it is the expensive part. The result
    is published by the store in a single critical section that also validates
    the CREATED -> SIGNED transition, so of two requests racing to sign the same
    session exactly one wins and the other is refused with a 409. Publishing the
    transition and the signature together also means a reader never sees
    ``lifecycle == SIGNED`` while ``protocol_status`` still says ``created``.
    """
    record = store.get_session(session_id, ttl_seconds=settings.session_ttl_seconds)
    result = sign_session(record.session, simulator_seed=API_SIGNING_SIMULATOR_SEED)
    return store.publish_signing(
        session_id,
        session=result.session,
        transcript=_transcript_dict(result.transcript),
        transcript_hash=str(result.transcript.transcript_hash),
        ttl_seconds=settings.session_ttl_seconds,
    )


def expire(store: ApiStore, session_id: str, settings: ApiSettings) -> SessionRecord:
    """Move a session to EXPIRED."""
    return store.transition(
        session_id, SessionLifecycle.EXPIRED, ttl_seconds=settings.session_ttl_seconds
    )


def _transcript_dict(transcript: Any) -> Dict[str, Any]:
    from backend.protocol import transcript_to_dict

    return dict(transcript_to_dict(transcript))


def session_view(record: SessionRecord) -> Dict[str, Any]:
    """Return the public view of a session."""
    session: Session = record.session
    return {
        "session_id": record.session_id,
        "nonce": session.nonce,
        "protocol_version": session.protocol_version,
        "protocol_status": session.status.value,
        "lifecycle": record.lifecycle.value,
        "state_count": session.state_count,
        "message_hash": session.message_hash,
        "message_binding": session_binding(session),
        "created_at": session.created_at,
        "signer_id": session.signer_id,
        "verifier_id": session.verifier_id,
        "history": list(record.history),
    }


def sign_view(record: SessionRecord) -> Dict[str, Any]:
    """Return the response body for a signed session."""
    session: Session = record.session
    return {
        "session_id": record.session_id,
        "lifecycle": record.lifecycle.value,
        "protocol_status": session.status.value,
        "transcript": dict(record.transcript or {}),
        "transcript_hash": str(record.transcript_hash or ""),
        "state_count": session.state_count,
        "signer_id": session.signer_id,
        "verifier_id": session.verifier_id,
        "created_at": session.created_at,
        "history": list(record.history),
    }


def summary(record: SessionRecord) -> Dict[str, Any]:
    """Return a compact listing entry for a session."""
    session: Session = record.session
    return {
        "session_id": record.session_id,
        "lifecycle": record.lifecycle.value,
        "protocol_status": session.status.value,
        "signer_id": session.signer_id,
        "verifier_id": session.verifier_id,
        "state_count": session.state_count,
        "created_at": session.created_at,
        "has_transcript": record.transcript is not None,
        "transcript_hash": record.transcript_hash,
    }


def listing(store: ApiStore) -> List[Dict[str, Any]]:
    """Return listing entries for every known session."""
    return [summary(record) for record in store.list_sessions()]
