"""In-memory application state for the API.

What lives here, and what does not
----------------------------------
This module holds **API orchestration state only**:

* the lifecycle of a reference signing session (created, signed, verified,
  rejected, expired);
* the transcripts produced for those sessions;
* calibration and evaluation summaries produced by earlier requests;
* one shared :class:`~backend.detection.replay.ReplayRegistry`.

It holds no domain logic. Thresholds, decisions, transcripts and evidence are all
produced by the M1-M6 packages; this module only remembers what they returned.

Restart loses everything
------------------------
The stores are plain dictionaries behind a lock. There is deliberately no
database: the milestone brief asks for prototype orchestration, and introducing a
database would add a dependency and an operational surface that the API does not
need yet. A process restart therefore discards every session, calibration and
evaluation. The endpoints document this, and the replay registry in particular is
a session-state mechanism rather than a persistent replay-prevention system.

Concurrency
-----------
The application object is shared, so two requests can touch the same record at
the same time. Every mutation and every read goes through one re-entrant lock,
and a result is *published* through the store rather than assigned to a record
the caller already holds -- so a reader cannot observe a half-updated record, such
as a transcript whose hash has not been attached yet.

The lock is held for short, non-blocking critical sections only. Expensive work
-- signing, scenario simulation, benchmark runs -- happens outside it, and only
the publication of the result takes the lock. A slow request therefore cannot
serialise the whole API.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from backend.api.errors import conflict, not_found
from backend.detection.replay import ReplayRegistry


class SessionLifecycle(str, Enum):
    """Application-level lifecycle of a signing session.

    This is **not** a replacement for the protocol's own
    :class:`~backend.protocol.models.SessionStatus`, which models the state of
    the protocol object. A protocol session is ``created`` or ``signed``; the
    lifecycle below additionally records what the *application* did with it.
    """

    CREATED = "CREATED"
    SIGNED = "SIGNED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"



ALLOWED_TRANSITIONS: Mapping[SessionLifecycle, frozenset] = {
    SessionLifecycle.CREATED: frozenset(
        {SessionLifecycle.SIGNED, SessionLifecycle.EXPIRED}
    ),
    SessionLifecycle.SIGNED: frozenset(
        {SessionLifecycle.VERIFIED, SessionLifecycle.REJECTED, SessionLifecycle.EXPIRED}
    ),
    SessionLifecycle.VERIFIED: frozenset({SessionLifecycle.EXPIRED}),
    SessionLifecycle.REJECTED: frozenset({SessionLifecycle.EXPIRED}),
    SessionLifecycle.EXPIRED: frozenset(),
}


TERMINAL_LIFECYCLES = frozenset({SessionLifecycle.EXPIRED})


@dataclass
class SessionRecord:
    """One orchestrated signing session."""

    session: Any
    lifecycle: SessionLifecycle = SessionLifecycle.CREATED
    transcript: Optional[Dict[str, Any]] = None
    transcript_hash: Optional[str] = None
    verification: Optional[Dict[str, Any]] = None
    history: List[str] = field(default_factory=list)
    stored_at: float = field(default_factory=time.monotonic)

    @property
    def session_id(self) -> str:
        return str(self.session.session_id)

class ApiStore:
    """Thread-safe in-memory store for the API's orchestration state."""

    def __init__(self, *, replay_registry: Optional[ReplayRegistry] = None) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, SessionRecord] = {}
        self._calibrations: Dict[str, Dict[str, Any]] = {}
        self._evaluations: Dict[str, Dict[str, Any]] = {}
        self._replay_registry = replay_registry or ReplayRegistry()



    @property
    def lock(self) -> threading.RLock:
        """The store's re-entrant lock.

        Exposed so a service can hold it around a read-modify-write on shared
        state that spans more than one call (for example a replay check followed
        by a replay consume). Hold it only around short, non-blocking work.
        """
        return self._lock

    @property
    def replay_registry(self) -> ReplayRegistry:
        """The shared M4 replay registry.

        Reused rather than reimplemented: replay evidence must come from the same
        ledger the detection engine already understands.
        """
        return self._replay_registry



    def add_session(self, record: SessionRecord) -> SessionRecord:
        with self._lock:
            existing = self._sessions.get(record.session_id)
            if existing is not None:
                raise conflict(
                    "a session with this id already exists",
                    session_id=record.session_id,
                )
            record.history.append(record.lifecycle.value)
            self._sessions[record.session_id] = record
            return record

    def get_session(self, session_id: str, *, ttl_seconds: Optional[int] = None) -> SessionRecord:
        """Return the record, applying automatic expiry when one is configured."""
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise not_found("session", session_id)
            self._apply_ttl(record, ttl_seconds)
            return record

    def list_sessions(self) -> List[SessionRecord]:
        with self._lock:
            return list(self._sessions.values())

    def transition(
        self,
        session_id: str,
        target: SessionLifecycle,
        *,
        ttl_seconds: Optional[int] = None,
    ) -> SessionRecord:
        """Move a session to ``target``, refusing an illegal transition."""
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise not_found("session", session_id)
            self._apply_ttl(record, ttl_seconds)
            self._require_transition(record, target, session_id)
            record.lifecycle = target
            record.history.append(target.value)
            return record

    def _require_transition(
        self, record: SessionRecord, target: SessionLifecycle, session_id: str
    ) -> None:
        allowed = ALLOWED_TRANSITIONS[record.lifecycle]
        if target not in allowed:
            raise conflict(
                f"cannot move session from {record.lifecycle.value} to {target.value}",
                session_id=session_id,
                current=record.lifecycle.value,
                requested=target.value,
                allowed=sorted(item.value for item in allowed),
            )

    def _apply_ttl(self, record: SessionRecord, ttl_seconds: Optional[int]) -> None:
        if ttl_seconds is None:
            return
        if record.lifecycle in TERMINAL_LIFECYCLES:
            return
        if time.monotonic() - record.stored_at >= float(ttl_seconds):
            record.lifecycle = SessionLifecycle.EXPIRED
            record.history.append(SessionLifecycle.EXPIRED.value)

    def publish_signing(
        self,
        session_id: str,
        *,
        session: Any,
        transcript: Dict[str, Any],
        transcript_hash: str,
        ttl_seconds: Optional[int] = None,
    ) -> SessionRecord:
        """Move CREATED -> SIGNED and attach the signature, in one critical section.

        Signing is expensive and runs outside the lock; this call takes the lock
        only to publish the result. Doing the transition *and* the attachment
        together matters: the lifecycle and the protocol status are two views of
        the same event, and a reader must never observe one without the other.

        The transition is validated here, so of two requests that race to sign the
        same session exactly one succeeds and the other is refused with a 409.
        """
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise not_found("session", session_id)
            self._apply_ttl(record, ttl_seconds)
            self._require_transition(record, SessionLifecycle.SIGNED, session_id)
            record.lifecycle = SessionLifecycle.SIGNED
            record.history.append(SessionLifecycle.SIGNED.value)
            record.session = session
            record.transcript = dict(transcript)
            record.transcript_hash = transcript_hash
            return record

    def publish_verification(
        self,
        session_id: str,
        *,
        accepted: bool,
        verification: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> SessionRecord:
        """Move SIGNED -> VERIFIED or REJECTED and record the result, atomically."""
        target = (
            SessionLifecycle.VERIFIED if accepted else SessionLifecycle.REJECTED
        )
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise not_found("session", session_id)
            self._apply_ttl(record, ttl_seconds)
            self._require_transition(record, target, session_id)
            record.lifecycle = target
            record.history.append(target.value)
            record.verification = dict(verification)
            return record



    def put_calibration(self, calibration_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._calibrations[calibration_id] = payload

    def get_calibration(self, calibration_id: str) -> Dict[str, Any]:
        with self._lock:
            payload = self._calibrations.get(calibration_id)
            if payload is None:
                raise not_found("calibration", calibration_id)
            return payload



    def put_evaluation(self, evaluation_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._evaluations[evaluation_id] = payload

    def get_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        with self._lock:
            payload = self._evaluations.get(evaluation_id)
            if payload is None:
                raise not_found("evaluation", evaluation_id)
            return payload



    def reset(self) -> None:
        """Drop all orchestration state, including replay history."""
        with self._lock:
            self._sessions.clear()
            self._calibrations.clear()
            self._evaluations.clear()




            self._replay_registry.reset()

    def counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                "sessions": len(self._sessions),
                "calibrations": len(self._calibrations),
                "evaluations": len(self._evaluations),
            }
