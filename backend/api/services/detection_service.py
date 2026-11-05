"""Orchestration for detection.

Builds an :class:`~backend.detection.models.ObservableDetectionInput` from
observable fields only, then calls :func:`backend.detection.detect`.

There is no path from this service to an attack label. The request schema has no
such field, the domain input type has no such field, and the M4 package is
architecturally forbidden from importing the attack modules. The only thing this
service does is translate between the two typed representations.

Locking
-------
Detection consults the shared replay ledger, and with ``consume_replay`` it also
writes to it. That read-modify-write is guarded by the store lock so two
concurrent requests cannot both see an event as fresh. Detection is a cheap
analysis over the state list, so holding the lock across it does not serialise
anything expensive -- no scenario simulation is ever run under this lock.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.api.errors import ApiError, ErrorCode
from backend.api.schemas.detection import DetectionRequest
from backend.api.store import ApiStore
from backend.detection import (
    DetectionInputError,
    ObservableDetectionInput,
    StateEvidence,
    VerificationEvidence,
    detect,
)


DETECTION_LIMITATIONS = (
    "the detector consumes observable input only; no attack label reaches it",
    "a finding is evidence of inconsistency with the calibrated honest model, "
    "not attribution of a cause",
    "detection is not a security verdict: a CLEAR status does not establish that "
    "a session is honest, because an adversary can produce consistent observations",
    "no formal forgery bound and no universal detection guarantee is produced here",
)


def build_detection_input(request: DetectionRequest) -> ObservableDetectionInput:
    """Translate the typed request into the M4 input type."""
    return ObservableDetectionInput(
        session_id=request.session_id,
        nonce=request.nonce,
        protocol_version=request.protocol_version,
        message_binding=request.message_binding,
        declared_transcript_hash=request.declared_transcript_hash,
        signer_id=request.signer_id,
        verifier_id=request.verifier_id,
        created_at=request.created_at,
        message=request.message,
        verifier_context_id=request.verifier_context_id,
        expected_protocol_version=request.expected_protocol_version,
        authorized_signers=tuple(request.authorized_signers),
        authorized_verifiers=tuple(request.authorized_verifiers),
        reported_signer_authorized=request.reported_signer_authorized,
        reported_verifier_authorized=request.reported_verifier_authorized,
        transcript_payload=(
            None if request.transcript_payload is None else dict(request.transcript_payload)
        ),
        transcript_parse_error=request.transcript_parse_error,
        states=tuple(
            StateEvidence(**state.model_dump()) for state in request.states
        ),
        declared_state_count=request.declared_state_count,
        measurement_mode=request.measurement_mode,
        basis_counts=dict(request.basis_counts),
        verification=VerificationEvidence(**request.verification.model_dump()),
    )


def detect_request(
    store: ApiStore, request: DetectionRequest
) -> Dict[str, Any]:
    """Run the detector over observable input and return its result."""
    detection_input = build_detection_input(request)

    try:
        with store.lock:
            result = detect(
                detection_input,
                replay_registry=store.replay_registry,
                consume=request.consume_replay,
            )
    except DetectionInputError as exc:
        raise ApiError(
            ErrorCode.BAD_REQUEST,
            f"the detection input was refused: {exc}",
            details={"reason": str(exc)},
        ) from exc

    payload = result.to_dict()
    payload["security_assessment"] = {
        "status": "evidence_only",
        "formal_proof_present": False,
        "ground_truth_used": False,
        "limitations": list(DETECTION_LIMITATIONS),
    }
    return payload
