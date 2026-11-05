"""Reference QDS protocol construction -- top-level facade.

This module is the entry point for the milestone-2 reference prototype. It
re-exports the stable surface of the protocol layer and provides the two
end-to-end operations, :func:`sign` and :func:`verify`.

Status of this construction
---------------------------
This milestone implements a **modular reference protocol construction used for
simulation, attack modelling and threat-detection research**.

It is **not**:

* the official Egreen Quanta protocol, or any other named protocol;
* a standardized QDS protocol;
* formally proven information-theoretically secure;
* a complete formal QDS protocol.

The SIH specification calls for a teleportation-based QDS-oriented framework
but does not fully specify a complete formal QDS protocol, so what is
implemented here is a reference construction that establishes the protocol
semantics later milestones will attack and evaluate.

Layering
--------
``reference_qds`` -> ``backend.protocol`` -> ``backend.quantum``

The dependency direction never reverses: ``backend.quantum`` imports nothing
from ``backend.protocol``, and the protocol layer imports nothing from any
future attack, noise, detection, API or frontend module. The protocol remains
fully usable with no attack engine installed.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.protocol.binding import (
    BINDING_DOMAIN,
    binding_preimage,
    compute_message_binding,
    compute_message_hash,
)
from backend.protocol.canonical import (
    CANONICAL_HASH_ALGORITHM,
    CanonicalTypeError,
    canonical_bytes,
    canonical_digest,
    canonical_json,
    hash_bytes,
)
from backend.protocol.encoding import (
    ALPHABET_SIZE,
    STATE_ALPHABET,
    STREAM_DOMAIN,
    derive_alphabet_indices,
    derive_state_sequence,
    sequence_metadata,
    state_for_identifier,
)
from backend.protocol.models import (
    ACCEPTED_TRANSCRIPT_VERSIONS,
    DEFAULT_STATE_COUNT,
    MAX_STATE_COUNT,
    NONCE_BYTES,
    PROTOCOL_VERSION,
    SESSION_ID_BYTES,
    TRANSCRIPT_VERSION,
    ProtocolError,
    ProtocolValidationError,
    Session,
    SessionStatus,
    SignatureState,
    SigningResult,
    TeleportationBranch,
    Transcript,
    TranscriptValidationError,
    VerificationResult,
    VerifierContext,
)
from backend.protocol.session import (
    create_session,
    new_nonce,
    new_session_id,
    session_binding,
    utc_now_iso,
)
from backend.protocol.signer import (
    DEFAULT_SIMULATOR_SEED,
    VERIFICATION_POLICY_METADATA,
    sign,
    sign_session,
    teleport_signature_state,
)
from backend.protocol.transcript import (
    build_transcript,
    compute_transcript_hash,
    is_transcript_hash_valid,
    transcript_from_dict,
    transcript_from_json,
    transcript_to_dict,
    transcript_to_json,
)
from backend.protocol.verifier import (
    MEASUREMENT_TOLERANCE,
    ReferenceVerifier,
    StateMeasurement,
    measure_state_in_basis,
    verify,
    verify_state_measurement,
)

__all__ = [

    "PROTOCOL_VERSION",
    "TRANSCRIPT_VERSION",
    "ACCEPTED_TRANSCRIPT_VERSIONS",
    "DEFAULT_STATE_COUNT",
    "MAX_STATE_COUNT",
    "SESSION_ID_BYTES",
    "NONCE_BYTES",
    "DEFAULT_SIMULATOR_SEED",
    "BINDING_DOMAIN",
    "STREAM_DOMAIN",
    "STATE_ALPHABET",
    "ALPHABET_SIZE",
    "MEASUREMENT_TOLERANCE",
    "CANONICAL_HASH_ALGORITHM",
    "VERIFICATION_POLICY_METADATA",

    "ProtocolError",
    "ProtocolValidationError",
    "TranscriptValidationError",
    "CanonicalTypeError",

    "Session",
    "SessionStatus",
    "SignatureState",
    "TeleportationBranch",
    "Transcript",
    "SigningResult",
    "VerificationResult",
    "VerifierContext",
    "StateMeasurement",

    "canonical_json",
    "canonical_bytes",
    "canonical_digest",
    "hash_bytes",

    "new_session_id",
    "new_nonce",
    "utc_now_iso",
    "session_binding",
    "create_session",

    "compute_message_hash",
    "compute_message_binding",
    "binding_preimage",

    "derive_state_sequence",
    "derive_alphabet_indices",
    "sequence_metadata",
    "state_for_identifier",

    "build_transcript",
    "compute_transcript_hash",
    "is_transcript_hash_valid",
    "transcript_to_dict",
    "transcript_to_json",
    "transcript_from_dict",
    "transcript_from_json",

    "sign",
    "sign_session",
    "teleport_signature_state",

    "verify",
    "ReferenceVerifier",
    "measure_state_in_basis",
    "verify_state_measurement",

    "describe_protocol",
]


def describe_protocol() -> Dict[str, Any]:
    """Return a machine-readable description of this reference construction."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "transcript_version": TRANSCRIPT_VERSION,
        "kind": "reference-prototype-construction",
        "formal_security_claim": False,
        "standardized": False,
        "state_alphabet": list(STATE_ALPHABET),
        "default_state_count": DEFAULT_STATE_COUNT,
        "binding_domain": BINDING_DOMAIN,
        "stream_domain": STREAM_DOMAIN,
        "hash_algorithm": CANONICAL_HASH_ALGORITHM,
    }
