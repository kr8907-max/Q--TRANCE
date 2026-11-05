"""Schemas for verification.

The response mirrors :class:`backend.protocol.models.VerificationResult` field for
field. The API adds no verdict of its own: it reports what the M2 verifier
decided, and the boolean breakdown is kept rather than collapsed into a single
``accepted`` flag, because *which* check failed is the useful part.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from backend.api.config import ABSOLUTE_MAX_MESSAGE_CHARS
from backend.api.schemas.common import (
    ApiModel,
    Identifier,
    ProtocolVersion,
    configured_limit,
)


class VerifierContextIn(ApiModel):
    """The verifying party's declared context."""

    verifier_id: Identifier = Field(
        description="Verifier identity, validated with the protocol's own rule."
    )
    expected_protocol_version: Optional[ProtocolVersion] = Field(
        default=None,
        description="Protocol version the verifier expects. Defaults to the transcript's.",
    )


class VerificationResultView(ApiModel):
    """The protocol's verification result, unchanged.

    Shared by ``POST /verify`` and by the simulation endpoint, which embeds the
    same structure: both report the same M2 object and neither reinterprets it.
    """

    accepted: bool
    session_valid: bool
    message_valid: bool
    transcript_valid: bool
    state_sequence_valid: bool
    measurement_valid: bool
    errors: List[str]
    warnings: List[str]
    state_count: int
    mismatch_count: int
    basis_counts: Dict[str, int]
    measurement_summary: Dict[str, int]


class VerificationRequest(ApiModel):
    """Request body for ``POST /verify``."""

    message: str = Field(
        min_length=1,
        max_length=ABSOLUTE_MAX_MESSAGE_CHARS,
        description=(
            "Message the transcript is expected to bind. The accepted length "
            "follows the application's configured message bound."
        ),
    )
    transcript: Dict[str, Any] = Field(
        description="Serialized reference transcript to verify."
    )
    verifier_context: VerifierContextIn
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional. When supplied, the verification outcome is recorded against "
            "that session and drives its lifecycle. Verification itself does not "
            "depend on the API having seen the session."
        ),
    )

    @field_validator("message")
    @classmethod
    def _configured_message_bound(cls, value: str, info) -> str:
        return configured_limit(value, info, "max_message_chars")


class VerificationResponse(VerificationResultView):
    """Verification result plus the API's optional session bookkeeping."""

    session_id: Optional[str] = Field(
        default=None, description="Present only when the request named a session."
    )
    lifecycle: Optional[str] = Field(
        default=None, description="Session lifecycle after this verification."
    )
    note: str = Field(
        default=(
            "A verification decision is a consistency result about one transcript. "
            "It is not a security verdict."
        ),
        description="Fixed qualifier carried by every verification response.",
    )
