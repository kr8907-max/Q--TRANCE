"""Orchestration for verification.

Calls :func:`backend.protocol.verify` and reports exactly what it returned.

Why there is no second validation layer
---------------------------------------
The M2 verifier already converts malformed transcript *content* into a structured
rejection (``accepted=False`` with a recorded error) instead of raising. Adding
another validator here would risk the two disagreeing, and the API would then be
publishing a different verdict from the protocol's own. So:

* schema-level malformation (a transcript that is not an object) is refused by
  request validation with a 422;
* content-level malformation comes back as a normal 200 whose ``accepted`` is
  false and whose ``errors`` say why.

Recording the outcome against a session is optional and additive. It never
changes the verification result.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.api.config import ApiSettings
from backend.api.schemas.verification import VerificationRequest
from backend.api.store import ApiStore
from backend.protocol import PROTOCOL_VERSION, VerifierContext, verify


VERIFICATION_NOTE = (
    "A verification decision is a consistency result about one transcript. "
    "It is not a security verdict."
)


def verify_request(
    store: ApiStore, request: VerificationRequest, settings: ApiSettings
) -> Dict[str, Any]:
    """Verify a transcript and, when asked, record the outcome on a session."""
    expected_version = request.verifier_context.expected_protocol_version
    if expected_version is None:
        expected_version = str(
            request.transcript.get("protocol_version", PROTOCOL_VERSION)
        )

    context = VerifierContext(
        verifier_id=request.verifier_context.verifier_id,
        expected_protocol_version=expected_version,
    )
    result = verify(request.transcript, request.message, context)

    payload: Dict[str, Any] = {
        "accepted": bool(result.accepted),
        "session_valid": bool(result.session_valid),
        "message_valid": bool(result.message_valid),
        "transcript_valid": bool(result.transcript_valid),
        "state_sequence_valid": bool(result.state_sequence_valid),
        "measurement_valid": bool(result.measurement_valid),
        "errors": list(result.verification_errors),
        "warnings": list(result.verification_warnings),
        "state_count": int(result.state_count),
        "mismatch_count": int(result.mismatch_count),
        "basis_counts": dict(result.basis_counts),
        "measurement_summary": dict(result.measurement_summary),
        "note": VERIFICATION_NOTE,
    }

    if request.session_id is not None:
        payload["session_id"] = request.session_id


        record = store.publish_verification(
            request.session_id,
            accepted=bool(result.accepted),
            verification=payload,
            ttl_seconds=settings.session_ttl_seconds,
        )
        payload["lifecycle"] = record.lifecycle.value

    return payload
