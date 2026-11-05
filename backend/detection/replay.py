"""Replay detection: protocol/session identity reuse.

Replay is not a quantum property
--------------------------------
A replayed transcript may carry perfectly undisturbed qubits, a valid hash, a
valid binding and a correct state sequence -- that is precisely what makes
replay worth modelling. Every single-event observable can be clean. What makes
the event a replay is that **the session identity was consumed before**.

The detector therefore derives replay evidence from the protocol/session
identity it can observe -- the session identifier, the nonce and the transcript
identity -- and never from quantum disturbance. Claiming a measurement
disturbance "detects replay" would be an unsupported attribution.

The registry
------------
:class:`ReplayRegistry` is a small in-memory ledger of consumed identities. It
is deliberately not a database and not persisted: Milestone 4 needs a clean,
deterministic, testable abstraction, and Milestone 5 or later can put a store
behind the same interface.

Properties the interface guarantees
-----------------------------------
deterministic
    The same sequence of calls produces the same evidence. No clocks, no
    randomness, no hash ordering dependence.
testable
    ``check`` is **pure** -- it reports what *would* happen and mutates nothing.
    ``observe`` records and returns the evidence that applied *before* the
    record. The two are separated so a test can ask "is this a replay?" without
    changing the answer for the next question.
resettable for experiments
    :meth:`ReplayRegistry.reset` empties the ledger, so a sweep can give each
    scenario a clean history.
safe under malformed input
    A missing or non-string identifier simply cannot be checked. It is reported
    as unavailable rather than being coerced into a value that might
    accidentally match, and it is never recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet

__all__ = ["ReplayEvidence", "ReplayRegistry"]


@dataclass(frozen=True)
class ReplayEvidence:
    """Structured replay finding for one verification event.

    ``nonce_reused``, ``session_reused`` and ``transcript_reused`` are reported
    **separately** because they are different observations: a fresh session that
    reuses an old nonce is not the same event as a whole transcript being
    resubmitted, and collapsing them would lose that distinction.

    ``first_observation`` is ``True`` when none of the checkable identifiers had
    been seen, and ``None`` when nothing could be checked.
    """

    available: bool
    nonce_reused: bool
    session_reused: bool
    transcript_reused: bool
    first_observation: bool | None
    observed_session_id: str | None
    observed_nonce: str | None
    observed_transcript_hash: str | None
    reason: str | None = None

    @property
    def any_reuse(self) -> bool:
        """Return whether any checkable identifier was reused."""
        return bool(
            self.available
            and (self.nonce_reused or self.session_reused or self.transcript_reused)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "nonce_reused": self.nonce_reused,
            "session_reused": self.session_reused,
            "transcript_reused": self.transcript_reused,
            "first_observation": self.first_observation,
            "observed_session_id": self.observed_session_id,
            "observed_nonce": self.observed_nonce,
            "observed_transcript_hash": self.observed_transcript_hash,
            "any_reuse": self.any_reuse,
            "reason": self.reason,
        }


def _checkable(value: Any) -> str | None:
    """Return ``value`` if it is a non-empty string, else ``None``."""
    if isinstance(value, str) and value:
        return value
    return None


class ReplayRegistry:
    """In-memory ledger of consumed session identities.

    Three independent index sets are kept, because the three identifiers answer
    three different questions. Recording an event adds each identifier that was
    actually supplied; nothing is invented for a missing one.
    """

    def __init__(self) -> None:
        self._sessions: set[str] = set()
        self._nonces: set[str] = set()
        self._transcripts: set[str] = set()
        self._events = 0



    def __len__(self) -> int:
        """Return the number of recorded events."""
        return self._events

    def snapshot(self) -> Dict[str, FrozenSet[str]]:
        """Return an immutable view of the ledger, for tests and reporting."""
        return {
            "sessions": frozenset(self._sessions),
            "nonces": frozenset(self._nonces),
            "transcripts": frozenset(self._transcripts),
        }



    def check(
        self,
        *,
        session_id: Any = None,
        nonce: Any = None,
        transcript_hash: Any = None,
    ) -> ReplayEvidence:
        """Report reuse without modifying the ledger.

        This is the method a detector calls during a side-effect-free
        detection pass.
        """
        session = _checkable(session_id)
        nonce_value = _checkable(nonce)
        transcript = _checkable(transcript_hash)

        if session is None and nonce_value is None and transcript is None:
            return ReplayEvidence(
                available=False,
                nonce_reused=False,
                session_reused=False,
                transcript_reused=False,
                first_observation=None,
                observed_session_id=None,
                observed_nonce=None,
                observed_transcript_hash=None,
                reason=(
                    "no session identifier, nonce or transcript identity was "
                    "observable, so replay state could not be established"
                ),
            )

        session_reused = session is not None and session in self._sessions
        nonce_reused = nonce_value is not None and nonce_value in self._nonces
        transcript_reused = transcript is not None and transcript in self._transcripts

        return ReplayEvidence(
            available=True,
            nonce_reused=nonce_reused,
            session_reused=session_reused,
            transcript_reused=transcript_reused,
            first_observation=not (session_reused or nonce_reused or transcript_reused),
            observed_session_id=session,
            observed_nonce=nonce_value,
            observed_transcript_hash=transcript,
            reason=None,
        )



    def record(
        self,
        *,
        session_id: Any = None,
        nonce: Any = None,
        transcript_hash: Any = None,
    ) -> None:
        """Record the identifiers that were supplied; ignore the rest."""
        session = _checkable(session_id)
        nonce_value = _checkable(nonce)
        transcript = _checkable(transcript_hash)
        if session is None and nonce_value is None and transcript is None:
            return
        if session is not None:
            self._sessions.add(session)
        if nonce_value is not None:
            self._nonces.add(nonce_value)
        if transcript is not None:
            self._transcripts.add(transcript)
        self._events += 1

    def observe(
        self,
        *,
        session_id: Any = None,
        nonce: Any = None,
        transcript_hash: Any = None,
    ) -> ReplayEvidence:
        """Return the reuse evidence and then record the event.

        The evidence describes the state *before* the record, so the first
        observation of an identity reports ``first_observation=True`` and the
        second reports the reuse.
        """
        evidence = self.check(
            session_id=session_id, nonce=nonce, transcript_hash=transcript_hash
        )
        self.record(
            session_id=session_id, nonce=nonce, transcript_hash=transcript_hash
        )
        return evidence

    def reset(self) -> None:
        """Empty the ledger so a new experiment starts with no history."""
        self._sessions.clear()
        self._nonces.clear()
        self._transcripts.clear()
        self._events = 0

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ReplayRegistry(events={self._events}, sessions={len(self._sessions)}, "
            f"nonces={len(self._nonces)}, transcripts={len(self._transcripts)})"
        )
