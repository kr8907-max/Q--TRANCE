"""Schemas for the signing-session lifecycle.

The session is the API's unit of orchestration. It carries only what the protocol
treats as public material: the message, the declared identities, the session
identifier, the nonce and the binding metadata. The reference construction has no
secret key, and nothing here adds one.
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
from backend.protocol import DEFAULT_STATE_COUNT, MAX_STATE_COUNT, PROTOCOL_VERSION


class SessionCreateRequest(ApiModel):
    """Request body for ``POST /sessions``."""

    message: str = Field(
        min_length=1,
        max_length=ABSOLUTE_MAX_MESSAGE_CHARS,
        description=(
            "Message the signer is asked to sign. The accepted length follows the "
            "application's configured message bound."
        ),
    )
    signer_id: Identifier = Field(
        description="Signer identity, validated with the protocol's own rule."
    )
    verifier_id: Identifier = Field(
        description="Verifier identity, validated with the protocol's own rule."
    )
    state_count: int = Field(
        default=DEFAULT_STATE_COUNT,
        ge=1,
        le=MAX_STATE_COUNT,
        description=(
            "Number of signature states. Bounded by the reference protocol's "
            f"maximum signature length of {MAX_STATE_COUNT} states."
        ),
    )
    protocol_version: ProtocolVersion = Field(
        default=PROTOCOL_VERSION,
        description="Reference protocol version, validated with the protocol's own rule.",
    )

    @field_validator("message")
    @classmethod
    def _configured_message_bound(cls, value: str, info) -> str:
        return configured_limit(value, info, "max_message_chars")


class SessionView(ApiModel):
    """The public view of one session."""

    session_id: str
    nonce: str
    protocol_version: str
    protocol_status: str = Field(description="The M2 protocol's own session status.")
    lifecycle: str = Field(
        description="API orchestration lifecycle: CREATED, SIGNED, VERIFIED, REJECTED or EXPIRED."
    )
    state_count: int
    message_hash: str
    message_binding: str
    created_at: str
    signer_id: str
    verifier_id: str
    history: List[str] = Field(description="Lifecycle states this session has passed through.")


class SessionSignResponse(ApiModel):
    """Result of signing a session: the reference transcript, plus its hash."""

    session_id: str
    lifecycle: str
    protocol_status: str
    transcript: Dict[str, Any] = Field(
        description="Serialized reference transcript, produced by the M2 signer."
    )
    transcript_hash: str
    state_count: int
    signer_id: str
    verifier_id: str
    created_at: str
    history: List[str]


class SessionSummary(ApiModel):
    """Compact session listing entry."""

    session_id: str
    lifecycle: str
    protocol_status: str
    signer_id: str
    verifier_id: str
    state_count: int
    created_at: str
    has_transcript: bool
    transcript_hash: Optional[str] = None


class SessionListResponse(ApiModel):
    """Response for ``GET /sessions``."""

    sessions: List[SessionSummary]
    total: int
