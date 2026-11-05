"""Reference QDS protocol layer (Milestone 2).

This package builds the *reference prototype* signing and verification workflow
on top of the verified M1 quantum core. It contains protocol semantics only:
sessions, message binding, reference state derivation, transcripts, signing and
verification.

What is deliberately absent
---------------------------
There is no attack engine, no threat detector, no threshold calibration, no
noise model, no machine learning, no API and no frontend. Later milestones add
those; this one establishes the semantics they will exercise.

Layering
--------
``backend.protocol`` may import ``backend.quantum``. ``backend.quantum`` must
never import ``backend.protocol``, and does not.

Module map
----------
``canonical``      deterministic canonical serialization and SHA-256 digests
``models``         frozen dataclasses, enums, version constants, validators
``binding``        message hash and the canonical message/session binding
``encoding``       the replaceable message-binding -> state-sequence mapping
``session``        session creation and CSPRNG identifier generation
``transcript``     transcript construction, hashing, serialization, validation
``signer``         the signing workflow (calls the M1 teleportation engine)
``verifier``       the verification workflow (reconstructs expectations itself)
``reference_qds``  top-level facade and protocol description
"""

from backend.protocol.reference_qds import (
    ACCEPTED_TRANSCRIPT_VERSIONS,
    ALPHABET_SIZE,
    BINDING_DOMAIN,
    CANONICAL_HASH_ALGORITHM,
    DEFAULT_SIMULATOR_SEED,
    DEFAULT_STATE_COUNT,
    MAX_STATE_COUNT,
    MEASUREMENT_TOLERANCE,
    NONCE_BYTES,
    PROTOCOL_VERSION,
    SESSION_ID_BYTES,
    STATE_ALPHABET,
    STREAM_DOMAIN,
    TRANSCRIPT_VERSION,
    VERIFICATION_POLICY_METADATA,
    CanonicalTypeError,
    ProtocolError,
    ProtocolValidationError,
    ReferenceVerifier,
    Session,
    SessionStatus,
    SignatureState,
    SigningResult,
    StateMeasurement,
    TeleportationBranch,
    Transcript,
    TranscriptValidationError,
    VerificationResult,
    VerifierContext,
    binding_preimage,
    build_transcript,
    canonical_bytes,
    canonical_digest,
    canonical_json,
    compute_message_binding,
    compute_message_hash,
    compute_transcript_hash,
    create_session,
    derive_alphabet_indices,
    derive_state_sequence,
    describe_protocol,
    hash_bytes,
    is_transcript_hash_valid,
    measure_state_in_basis,
    new_nonce,
    new_session_id,
    sequence_metadata,
    session_binding,
    sign,
    sign_session,
    state_for_identifier,
    teleport_signature_state,
    transcript_from_dict,
    transcript_from_json,
    transcript_to_dict,
    transcript_to_json,
    utc_now_iso,
    verify,
    verify_state_measurement,
)

__all__ = [
    "ACCEPTED_TRANSCRIPT_VERSIONS",
    "ALPHABET_SIZE",
    "BINDING_DOMAIN",
    "CANONICAL_HASH_ALGORITHM",
    "DEFAULT_SIMULATOR_SEED",
    "DEFAULT_STATE_COUNT",
    "MAX_STATE_COUNT",
    "MEASUREMENT_TOLERANCE",
    "NONCE_BYTES",
    "PROTOCOL_VERSION",
    "SESSION_ID_BYTES",
    "STATE_ALPHABET",
    "STREAM_DOMAIN",
    "TRANSCRIPT_VERSION",
    "VERIFICATION_POLICY_METADATA",
    "CanonicalTypeError",
    "ProtocolError",
    "ProtocolValidationError",
    "ReferenceVerifier",
    "Session",
    "SessionStatus",
    "SignatureState",
    "SigningResult",
    "StateMeasurement",
    "TeleportationBranch",
    "Transcript",
    "TranscriptValidationError",
    "VerificationResult",
    "VerifierContext",
    "binding_preimage",
    "build_transcript",
    "canonical_bytes",
    "canonical_digest",
    "canonical_json",
    "compute_message_binding",
    "compute_message_hash",
    "compute_transcript_hash",
    "create_session",
    "derive_alphabet_indices",
    "derive_state_sequence",
    "describe_protocol",
    "hash_bytes",
    "is_transcript_hash_valid",
    "measure_state_in_basis",
    "new_nonce",
    "new_session_id",
    "sequence_metadata",
    "session_binding",
    "sign",
    "sign_session",
    "state_for_identifier",
    "teleport_signature_state",
    "transcript_from_dict",
    "transcript_from_json",
    "transcript_to_dict",
    "transcript_to_json",
    "utc_now_iso",
    "verify",
    "verify_state_measurement",
]
