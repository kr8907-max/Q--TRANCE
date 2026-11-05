"""Strongly typed models for the reference QDS protocol.

Everything the protocol passes around is an explicit, frozen dataclass or a
string-valued enum. There is no "bag of fields" dictionary anywhere in the
core: dictionaries appear only at the serialization boundary, where they are
produced and validated by explicit ``to_dict`` / ``from_dict`` pairs.

Scope
-----
This module defines *protocol semantics only* -- sessions, signature states,
transcripts and verification outcomes. It contains no quantum code, no attack
code, no noise model and no threshold logic. It imports nothing from
``backend.quantum``; the quantum layer is used by :mod:`backend.protocol.signer`
and :mod:`backend.protocol.verifier`, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Tuple

__all__ = [
    "PROTOCOL_VERSION",
    "TRANSCRIPT_VERSION",
    "ACCEPTED_TRANSCRIPT_VERSIONS",
    "PROTOCOL_VERSION_PATTERN",
    "IDENTIFIER_PATTERN",
    "SESSION_ID_BYTES",
    "NONCE_BYTES",
    "DEFAULT_STATE_COUNT",
    "MAX_STATE_COUNT",
    "ProtocolError",
    "ProtocolValidationError",
    "TranscriptValidationError",
    "SessionStatus",
    "SignatureState",
    "TeleportationBranch",
    "Session",
    "Transcript",
    "SigningResult",
    "VerificationResult",
    "VerifierContext",
    "require_exact_keys",
    "require_int",
    "require_bit",
    "require_str",
    "require_mapping",
    "validate_identifier",
    "validate_protocol_version",
    "validate_hex_digest",
    "validate_state_count",
    "validate_message",
    "validate_created_at",
]




PROTOCOL_VERSION = "RQDS-TP-1.0"




TRANSCRIPT_VERSION = 1
ACCEPTED_TRANSCRIPT_VERSIONS: Tuple[int, ...] = (TRANSCRIPT_VERSION,)


PROTOCOL_VERSION_PATTERN = re.compile(r"^RQDS-TP-[0-9]+\.[0-9]+$")



IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


SESSION_ID_BYTES = 16
NONCE_BYTES = 32





DEFAULT_STATE_COUNT = 16
MAX_STATE_COUNT = 4096

_ISO_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?\+00:00$"
)


class ProtocolError(Exception):
    """Base class for reference-protocol failures."""


class ProtocolValidationError(ProtocolError, ValueError):
    """Raised when protocol input fails a structural or semantic check."""


class TranscriptValidationError(ProtocolValidationError):
    """Raised when a serialized transcript does not match the schema."""


class SessionStatus(str, Enum):
    """Lifecycle state of a signing session."""

    CREATED = "created"
    SIGNED = "signed"


@dataclass(frozen=True)
class SignatureState:
    """One element of the reference signature-state sequence.

    The record is *symbolic*: it names one of the six Pauli eigenstates rather
    than carrying amplitudes. ``docs/protocol/reference-qds.md`` explains why
    floating-point statevectors never appear in a transcript.
    """

    index: int
    basis: str
    label: str
    eigenvalue: int
    state_identifier: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "basis": self.basis,
            "label": self.label,
            "eigenvalue": self.eigenvalue,
            "state_identifier": self.state_identifier,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SignatureState":
        if not isinstance(data, dict):
            raise TranscriptValidationError(
                f"signature state must be an object, got {type(data).__name__}"
            )
        expected = {"index", "basis", "label", "eigenvalue", "state_identifier"}
        require_exact_keys(data, expected, "signature state")
        return cls(
            index=require_int(data["index"], "signature state.index"),
            basis=require_str(data["basis"], "signature state.basis"),
            label=require_str(data["label"], "signature state.label"),
            eigenvalue=require_int(data["eigenvalue"], "signature state.eigenvalue"),
            state_identifier=require_str(
                data["state_identifier"], "signature state.state_identifier"
            ),
        )


@dataclass(frozen=True)
class TeleportationBranch:
    """Alice's two public Bell-measurement bits for one teleported state.

    In a teleportation protocol these bits are public: they are the classical
    information the sender must transmit for the receiver to undo the
    by-product operators. They are recorded for auditability and so that later
    milestones can model channel tampering.
    """

    index: int
    m0: int
    m1: int

    def to_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "m0": self.m0, "m1": self.m1}

    @classmethod
    def from_dict(cls, data: Any) -> "TeleportationBranch":
        if not isinstance(data, dict):
            raise TranscriptValidationError(
                f"teleportation branch must be an object, got {type(data).__name__}"
            )
        require_exact_keys(data, {"index", "m0", "m1"}, "teleportation branch")
        return cls(
            index=require_int(data["index"], "teleportation branch.index"),
            m0=require_bit(data["m0"], "teleportation branch.m0"),
            m1=require_bit(data["m1"], "teleportation branch.m1"),
        )


@dataclass(frozen=True)
class Session:
    """A signing session: the message plus the metadata bound to it.

    The session deliberately holds no key material and no generated state
    sequence. The state sequence is *derived* on demand from the binding (see
    :mod:`backend.protocol.encoding`), so the session is not the only source of
    truth for it.
    """

    session_id: str
    nonce: str
    message: str
    message_hash: str
    signer_id: str
    verifier_id: str
    protocol_version: str
    state_count: int
    state_sequence_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: SessionStatus = SessionStatus.CREATED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "nonce": self.nonce,
            "message": self.message,
            "message_hash": self.message_hash,
            "signer_id": self.signer_id,
            "verifier_id": self.verifier_id,
            "protocol_version": self.protocol_version,
            "state_count": self.state_count,
            "state_sequence_metadata": dict(self.state_sequence_metadata),
            "created_at": self.created_at,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class Transcript:
    """The canonical, auditable record produced by signing.

    The transcript is the artifact a verifier receives. It is fully described
    by its canonical serialization; ``transcript_hash`` covers every other
    field.
    """

    transcript_version: int
    protocol_version: str
    session_id: str
    nonce: str
    created_at: str
    message_hash: str
    message_binding: str
    signer_id: str
    verifier_id: str
    state_count: int
    state_sequence_metadata: Dict[str, Any]
    states: Tuple[SignatureState, ...]
    teleportation_branches: Tuple[TeleportationBranch, ...]
    verification_metadata: Dict[str, Any]
    transcript_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Return the full transcript as plain data, including the hash."""
        return {**self.payload(), "transcript_hash": self.transcript_hash}

    def payload(self) -> Dict[str, Any]:
        """Return the transcript data *excluding* ``transcript_hash``.

        This is the exact object whose canonical digest is stored in
        ``transcript_hash``.
        """
        return {
            "transcript_version": self.transcript_version,
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "message_hash": self.message_hash,
            "message_binding": self.message_binding,
            "signer_id": self.signer_id,
            "verifier_id": self.verifier_id,
            "state_count": self.state_count,
            "state_sequence_metadata": dict(self.state_sequence_metadata),
            "states": [state.to_dict() for state in self.states],
            "teleportation_branches": [
                branch.to_dict() for branch in self.teleportation_branches
            ],
            "verification_metadata": dict(self.verification_metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Transcript":
        """Build a transcript from plain data, validating every field.

        Raises :class:`TranscriptValidationError` on any structural problem.
        The stored ``transcript_hash`` is *not* recomputed here -- integrity is
        the verifier's job (see :mod:`backend.protocol.transcript`).
        """
        from backend.protocol.transcript import transcript_from_dict

        return transcript_from_dict(data)


@dataclass(frozen=True)
class SigningResult:
    """What the signer returns: the session and its canonical transcript."""

    session: Session
    transcript: Transcript


@dataclass(frozen=True)
class VerifierContext:
    """What the verifier knows independently of the transcript.

    ``verifier_id`` is the identity the verifier believes it has, and
    ``expected_protocol_version`` is the version it is willing to speak. Both
    are supplied by the caller rather than read out of the transcript, so a
    transcript cannot talk the verifier into a different protocol.

    The *transcript schema* version is not repeated here: it is enforced once,
    by the parser in :mod:`backend.protocol.transcript`, so there is a single
    authority for it.
    """

    verifier_id: str
    expected_protocol_version: str = PROTOCOL_VERSION


@dataclass(frozen=True)
class VerificationResult:
    """Structured outcome of reference verification.

    ``accepted`` is true only when every individual validity flag is true and
    no error was recorded. The diagnostics are raw counts for later milestones;
    this milestone performs **no** threshold-based classification of any kind.
    """

    accepted: bool
    session_valid: bool
    message_valid: bool
    transcript_valid: bool
    state_sequence_valid: bool
    measurement_valid: bool
    verification_errors: Tuple[str, ...]
    verification_warnings: Tuple[str, ...]
    state_count: int = 0
    mismatch_count: int = 0
    basis_counts: Dict[str, int] = field(default_factory=dict)
    measurement_summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "session_valid": self.session_valid,
            "message_valid": self.message_valid,
            "transcript_valid": self.transcript_valid,
            "state_sequence_valid": self.state_sequence_valid,
            "measurement_valid": self.measurement_valid,
            "verification_errors": list(self.verification_errors),
            "verification_warnings": list(self.verification_warnings),
            "state_count": self.state_count,
            "mismatch_count": self.mismatch_count,
            "basis_counts": dict(self.basis_counts),
            "measurement_summary": dict(self.measurement_summary),
        }








def require_exact_keys(data: Dict[str, Any], expected: set, where: str) -> None:
    missing = sorted(expected - set(data))
    if missing:
        raise TranscriptValidationError(f"{where}: missing required fields {missing}")
    unknown = sorted(set(data) - expected)
    if unknown:
        raise TranscriptValidationError(
            f"{where}: unknown fields {unknown} (schema is closed; bump "
            f"transcript_version to extend it)"
        )


def require_int(value: Any, where: str) -> int:
    """Return ``value`` if it is an ``int`` and not a ``bool``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TranscriptValidationError(
            f"{where}: expected int, got {type(value).__name__}"
        )
    return value


def require_bit(value: Any, where: str) -> int:
    """Return ``value`` if it is exactly ``0`` or ``1``."""
    number = require_int(value, where)
    if number not in (0, 1):
        raise TranscriptValidationError(f"{where}: expected 0 or 1, got {number}")
    return number


def require_str(value: Any, where: str) -> str:
    """Return ``value`` if it is a ``str``."""
    if not isinstance(value, str):
        raise TranscriptValidationError(
            f"{where}: expected str, got {type(value).__name__}"
        )
    return value


def require_mapping(value: Any, where: str) -> Dict[str, Any]:
    """Return ``value`` if it is an object with ``str`` keys."""
    if not isinstance(value, dict):
        raise TranscriptValidationError(
            f"{where}: expected an object, got {type(value).__name__}"
        )
    for key in value:
        if not isinstance(key, str):
            raise TranscriptValidationError(
                f"{where}: object keys must be strings, got {type(key).__name__}"
            )
    return value


def validate_identifier(value: Any, where: str) -> str:
    """Validate a signer/verifier identifier."""
    text = require_str(value, where)
    if not IDENTIFIER_PATTERN.match(text):
        raise ProtocolValidationError(
            f"{where}: malformed identifier {text!r}; expected "
            f"{IDENTIFIER_PATTERN.pattern}"
        )
    return text


def validate_protocol_version(value: Any, where: str) -> str:
    """Validate a protocol version string."""
    text = require_str(value, where)
    if not PROTOCOL_VERSION_PATTERN.match(text):
        raise ProtocolValidationError(
            f"{where}: malformed protocol version {text!r}; expected "
            f"{PROTOCOL_VERSION_PATTERN.pattern}"
        )
    return text


def validate_hex_digest(value: Any, where: str, expected_bytes: int) -> str:
    """Validate a lowercase hex digest of a fixed byte length."""
    text = require_str(value, where)
    if len(text) != expected_bytes * 2:
        raise ProtocolValidationError(
            f"{where}: expected {expected_bytes * 2} hex characters, got {len(text)}"
        )
    if any(character not in "0123456789abcdef" for character in text):
        raise ProtocolValidationError(
            f"{where}: expected lowercase hex, got {text!r}"
        )
    return text


def validate_state_count(value: Any, where: str = "state_count") -> int:
    """Validate the number of reference states in a session."""
    number = require_int(value, where)
    if not 1 <= number <= MAX_STATE_COUNT:
        raise ProtocolValidationError(
            f"{where}: must lie in [1, {MAX_STATE_COUNT}], got {number}"
        )
    return number


def validate_message(value: Any, where: str = "message") -> str:
    """Validate the message being signed."""
    from backend.protocol.canonical import normalize_string

    text = require_str(value, where)
    normalized = normalize_string(text)
    if not normalized:
        raise ProtocolValidationError(f"{where}: must not be empty")
    return normalized


def validate_created_at(value: Any, where: str = "created_at") -> str:
    """Validate a UTC ISO-8601 timestamp produced by this package."""
    text = require_str(value, where)
    if not _ISO_UTC_PATTERN.match(text):
        raise ProtocolValidationError(
            f"{where}: expected a UTC ISO-8601 timestamp, got {text!r}"
        )
    return text
