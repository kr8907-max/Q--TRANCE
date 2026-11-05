"""The canonical transcript: construction, hashing, serialization, validation.

The transcript is the artifact a verifier receives. It is the *only* thing that
crosses the boundary between the two parties, so its format is normative.

Transcript hash
---------------
::

    transcript_hash = SHA256( canonical_bytes( transcript.payload() ) )

where ``payload()`` is every transcript field **except** ``transcript_hash``
itself. The digest therefore covers the protocol version, the session
identifier, the nonce, the timestamp, the message hash, the message binding,
both identities, the state count, the declared sequence metadata, every
declared signature state, every teleportation branch record and the
verification metadata. Changing any of them changes the hash.

Serialization
-------------
``transcript_to_json`` emits the canonical encoding from
:mod:`backend.protocol.canonical`: UTF-8, NFC-normalised strings, object keys
sorted by code point, no insignificant whitespace. Two equal transcripts always
serialize to the same bytes, and the bytes are stable across runs, machines and
locales.

Parsing is strict
-----------------
``transcript_from_dict`` validates *every* field: closed key sets, exact types,
hex formats, identifier patterns, timestamp shape, count consistency, index
consistency, and full mutual consistency of each state's basis, label,
eigenvalue and symbolic identifier. It rejects unknown fields rather than
ignoring them, because the schema is versioned: adding a field requires bumping
``transcript_version``. Nothing is evaluated as code and ``pickle`` is never
used.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Tuple

from backend.protocol.canonical import canonical_bytes, canonical_json, hash_bytes
from backend.protocol.encoding import (
    STATE_ALPHABET,
    identifier_for_label,
)
from backend.protocol.models import (
    ACCEPTED_TRANSCRIPT_VERSIONS,
    NONCE_BYTES,
    SESSION_ID_BYTES,
    ProtocolValidationError,
    SignatureState,
    TeleportationBranch,
    Transcript,
    TranscriptValidationError,
    require_int,
    require_mapping,
    validate_created_at,
    validate_hex_digest,
    validate_identifier,
    validate_protocol_version,
    validate_state_count,
)
from backend.quantum.measure import VALID_BASES
from backend.quantum.states import EIGENSTATE_LABELS, get_eigenstate

__all__ = [
    "TRANSCRIPT_FIELDS",
    "build_transcript",
    "compute_transcript_hash",
    "transcript_to_dict",
    "transcript_to_json",
    "transcript_from_dict",
    "transcript_from_json",
    "is_transcript_hash_valid",
]


TRANSCRIPT_FIELDS = frozenset(
    {
        "transcript_version",
        "protocol_version",
        "session_id",
        "nonce",
        "created_at",
        "message_hash",
        "message_binding",
        "signer_id",
        "verifier_id",
        "state_count",
        "state_sequence_metadata",
        "states",
        "teleportation_branches",
        "verification_metadata",
        "transcript_hash",
    }
)

_SEQUENCE_METADATA_FIELDS = frozenset(
    {
        "derivation",
        "stream_domain",
        "alphabet",
        "alphabet_size",
        "nibble_accept_limit",
        "state_count",
        "binding_digest_length",
    }
)







def compute_transcript_hash(payload: Dict[str, Any]) -> str:
    """Return the lowercase hex SHA-256 of the canonical transcript payload."""
    return hash_bytes(canonical_bytes(payload))


def build_transcript(
    *,
    transcript_version: int,
    protocol_version: str,
    session_id: str,
    nonce: str,
    created_at: str,
    message_hash: str,
    message_binding: str,
    signer_id: str,
    verifier_id: str,
    state_count: int,
    state_sequence_metadata: Dict[str, Any],
    states: Iterable[SignatureState],
    teleportation_branches: Iterable[TeleportationBranch],
    verification_metadata: Dict[str, Any],
) -> Transcript:
    """Assemble a transcript and compute its hash.

    The hash is computed over the payload, so the returned transcript is
    self-consistent by construction.
    """
    draft = Transcript(
        transcript_version=transcript_version,
        protocol_version=protocol_version,
        session_id=session_id,
        nonce=nonce,
        created_at=created_at,
        message_hash=message_hash,
        message_binding=message_binding,
        signer_id=signer_id,
        verifier_id=verifier_id,
        state_count=state_count,
        state_sequence_metadata=dict(state_sequence_metadata),
        states=tuple(states),
        teleportation_branches=tuple(teleportation_branches),
        verification_metadata=dict(verification_metadata),
        transcript_hash="",
    )
    return replace(
        draft, transcript_hash=compute_transcript_hash(draft.payload())
    )


def is_transcript_hash_valid(transcript: Transcript) -> bool:
    """Return ``True`` when ``transcript_hash`` matches the transcript content."""
    return transcript.transcript_hash == compute_transcript_hash(transcript.payload())







def transcript_to_dict(transcript: Transcript) -> Dict[str, Any]:
    """Return the transcript as plain data, including the hash."""
    return transcript.to_dict()


def transcript_to_json(transcript: Transcript) -> str:
    """Return the canonical JSON text of ``transcript``."""
    return canonical_json(transcript_to_dict(transcript))


def transcript_from_dict(data: Any) -> Transcript:
    """Validate ``data`` and return a :class:`Transcript`.

    Raises :class:`TranscriptValidationError` for anything that does not match
    the schema, including malformed field values. Unknown fields are rejected.

    The shared field validators in :mod:`backend.protocol.models` raise the more
    general :class:`~backend.protocol.models.ProtocolValidationError`; this
    function normalises them so callers have exactly one exception type to
    handle at the transcript boundary.
    """
    try:
        return _parse_transcript(data)
    except TranscriptValidationError:
        raise
    except ProtocolValidationError as exc:
        raise TranscriptValidationError(str(exc)) from exc


def _parse_transcript(data: Any) -> Transcript:
    if not isinstance(data, dict):
        raise TranscriptValidationError(
            f"transcript must be an object, got {type(data).__name__}"
        )

    missing = sorted(TRANSCRIPT_FIELDS - set(data))
    if missing:
        raise TranscriptValidationError(f"transcript is missing fields {missing}")
    unknown = sorted(set(data) - TRANSCRIPT_FIELDS)
    if unknown:
        raise TranscriptValidationError(
            f"transcript has unknown fields {unknown} (the schema is closed; "
            f"bump transcript_version to extend it)"
        )

    transcript_version = require_int(data["transcript_version"], "transcript_version")
    if transcript_version not in ACCEPTED_TRANSCRIPT_VERSIONS:
        raise TranscriptValidationError(
            f"unsupported transcript_version {transcript_version}; this build "
            f"accepts {list(ACCEPTED_TRANSCRIPT_VERSIONS)}"
        )

    protocol_version = validate_protocol_version(
        data["protocol_version"], "protocol_version"
    )
    session_id = validate_hex_digest(data["session_id"], "session_id", SESSION_ID_BYTES)
    nonce = validate_hex_digest(data["nonce"], "nonce", NONCE_BYTES)
    created_at = validate_created_at(data["created_at"])
    message_hash = validate_hex_digest(data["message_hash"], "message_hash", 32)
    message_binding = validate_hex_digest(
        data["message_binding"], "message_binding", 32
    )
    signer_id = validate_identifier(data["signer_id"], "signer_id")
    verifier_id = validate_identifier(data["verifier_id"], "verifier_id")
    state_count = validate_state_count(data["state_count"])
    transcript_hash = validate_hex_digest(data["transcript_hash"], "transcript_hash", 32)

    state_sequence_metadata = _validate_sequence_metadata(data["state_sequence_metadata"])
    verification_metadata = _validate_verification_metadata(data["verification_metadata"])

    states = _validate_states(data["states"], state_count)
    branches = _validate_branches(data["teleportation_branches"], state_count)

    if state_sequence_metadata["state_count"] != state_count:
        raise TranscriptValidationError(
            "state_sequence_metadata.state_count does not match state_count"
        )

    return Transcript(
        transcript_version=transcript_version,
        protocol_version=protocol_version,
        session_id=session_id,
        nonce=nonce,
        created_at=created_at,
        message_hash=message_hash,
        message_binding=message_binding,
        signer_id=signer_id,
        verifier_id=verifier_id,
        state_count=state_count,
        state_sequence_metadata=state_sequence_metadata,
        states=states,
        teleportation_branches=branches,
        verification_metadata=verification_metadata,
        transcript_hash=transcript_hash,
    )


def transcript_from_json(text: Any) -> Transcript:
    """Parse canonical JSON text into a validated :class:`Transcript`."""
    if not isinstance(text, str):
        raise TranscriptValidationError(
            f"transcript JSON must be a str, got {type(text).__name__}"
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TranscriptValidationError(f"transcript is not valid JSON: {exc}") from exc
    return transcript_from_dict(data)







def _validate_sequence_metadata(value: Any) -> Dict[str, Any]:
    metadata = require_mapping(value, "state_sequence_metadata")
    missing = sorted(_SEQUENCE_METADATA_FIELDS - set(metadata))
    if missing:
        raise TranscriptValidationError(
            f"state_sequence_metadata is missing fields {missing}"
        )
    unknown = sorted(set(metadata) - _SEQUENCE_METADATA_FIELDS)
    if unknown:
        raise TranscriptValidationError(
            f"state_sequence_metadata has unknown fields {unknown}"
        )
    if not isinstance(metadata["derivation"], str):
        raise TranscriptValidationError("state_sequence_metadata.derivation must be str")
    if not isinstance(metadata["stream_domain"], str):
        raise TranscriptValidationError(
            "state_sequence_metadata.stream_domain must be str"
        )
    alphabet = metadata["alphabet"]
    if not isinstance(alphabet, list) or not all(
        isinstance(item, str) for item in alphabet
    ):
        raise TranscriptValidationError(
            "state_sequence_metadata.alphabet must be a list of strings"
        )
    if alphabet != list(STATE_ALPHABET):
        raise TranscriptValidationError(
            f"state_sequence_metadata.alphabet {alphabet} is not the canonical "
            f"alphabet {list(STATE_ALPHABET)}"
        )
    require_int(metadata["alphabet_size"], "state_sequence_metadata.alphabet_size")
    require_int(
        metadata["nibble_accept_limit"],
        "state_sequence_metadata.nibble_accept_limit",
    )
    require_int(metadata["state_count"], "state_sequence_metadata.state_count")
    require_int(
        metadata["binding_digest_length"],
        "state_sequence_metadata.binding_digest_length",
    )
    return metadata


def _validate_verification_metadata(value: Any) -> Dict[str, Any]:
    metadata = require_mapping(value, "verification_metadata")
    for key, item in metadata.items():
        if not isinstance(item, (str, int, bool)) and item is not None:
            raise TranscriptValidationError(
                f"verification_metadata.{key}: expected str, int, bool or null, "
                f"got {type(item).__name__}"
            )
    return metadata


def _validate_states(value: Any, state_count: int) -> Tuple[SignatureState, ...]:
    if not isinstance(value, list):
        raise TranscriptValidationError(
            f"states: expected a list, got {type(value).__name__}"
        )
    if len(value) != state_count:
        raise TranscriptValidationError(
            f"states: expected {state_count} entries, got {len(value)}"
        )

    states: List[SignatureState] = []
    for position, raw in enumerate(value):
        state = SignatureState.from_dict(raw)
        where = f"states[{position}]"
        if state.index != position:
            raise TranscriptValidationError(
                f"{where}: index {state.index} does not match position {position}"
            )
        if state.basis not in VALID_BASES:
            raise TranscriptValidationError(
                f"{where}: unknown basis {state.basis!r}; expected one of "
                f"{list(VALID_BASES)}"
            )
        if state.label not in EIGENSTATE_LABELS:
            raise TranscriptValidationError(
                f"{where}: unknown state label {state.label!r}"
            )
        if state.eigenvalue not in (1, -1):
            raise TranscriptValidationError(
                f"{where}: eigenvalue must be +1 or -1, got {state.eigenvalue}"
            )
        if state.state_identifier not in STATE_ALPHABET:
            raise TranscriptValidationError(
                f"{where}: invalid state identifier {state.state_identifier!r}; "
                f"expected one of {list(STATE_ALPHABET)}"
            )

        canonical = get_eigenstate(state.label)
        if (
            canonical.basis != state.basis
            or int(canonical.eigenvalue) != state.eigenvalue
            or identifier_for_label(state.label) != state.state_identifier
        ):
            raise TranscriptValidationError(
                f"{where}: label {state.label!r}, basis {state.basis!r}, "
                f"eigenvalue {state.eigenvalue} and identifier "
                f"{state.state_identifier!r} are not mutually consistent"
            )
        states.append(state)
    return tuple(states)


def _validate_branches(value: Any, state_count: int) -> Tuple[TeleportationBranch, ...]:
    if not isinstance(value, list):
        raise TranscriptValidationError(
            f"teleportation_branches: expected a list, got {type(value).__name__}"
        )
    if len(value) != state_count:
        raise TranscriptValidationError(
            f"teleportation_branches: expected {state_count} entries, got "
            f"{len(value)}"
        )
    branches: List[TeleportationBranch] = []
    for position, raw in enumerate(value):
        branch = TeleportationBranch.from_dict(raw)
        if branch.index != position:
            raise TranscriptValidationError(
                f"teleportation_branches[{position}]: index {branch.index} does not "
                f"match position {position}"
            )
        branches.append(branch)
    return tuple(branches)
