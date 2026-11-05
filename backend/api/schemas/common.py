"""Shared API schemas: the error envelope and the operational endpoints."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationInfo

from backend.protocol.models import IDENTIFIER_PATTERN, PROTOCOL_VERSION_PATTERN


class ApiModel(BaseModel):
    """Base class for every request and response schema.

    ``extra="forbid"`` is set on every model on purpose. Silently ignoring an
    unknown field is how a caller comes to believe the API accepted something it
    actually discarded -- which matters most for the detection endpoint, where an
    ignored field could be a hidden attack label.
    """

    model_config = ConfigDict(extra="forbid")


def configured_limit(value: Any, info: ValidationInfo, setting: str) -> Any:
    """Refuse ``value`` when it exceeds the limit named by ``setting``.

    Configuration owns the limits; a schema only says *which* configured limit a
    field answers to. A request body is validated twice:

    * **structural pass** -- FastAPI validates the raw JSON with no context. That
      pass enforces the shape of the request and the static field bounds, and it
      deliberately applies no configured limit, because it has no settings to
      read.
    * **configured pass** -- the API layer re-validates with the application's
      :class:`~backend.api.config.ApiSettings` in the validation context, and
      this is where the limit below is enforced.

    The double pass is what keeps the limit out of global state: the same schema
    class serves every application instance, and the instance's own settings
    decide the bound. ``setting`` is the ``ApiSettings`` attribute name, so a
    field and its setting cannot drift apart.

    A length is compared for strings and sequences; an integer is compared
    directly. ``None`` is passed through: whether a field is optional is a
    structural question, settled by the schema, not by configuration.
    """
    if value is None:
        return value
    settings = (info.context or {}).get("settings") if info.context else None
    if settings is None:
        return value
    limit = getattr(settings, setting)
    size = value if isinstance(value, int) else len(value)
    if size > limit:
        measured = "value" if isinstance(value, int) else "length"
        raise ValueError(
            f"{measured} {size} exceeds the configured maximum of {limit} that "
            f"the application's {setting} setting allows"
        )
    return value


def _check_identifier(value: str) -> str:
    """Refuse an identifier the protocol would refuse.

    The API validates against the protocol's own compiled pattern rather than a
    second copy of the rule. A looser schema would let a caller through and then
    have the protocol reject it, which surfaces as a 500 for what is really a
    client error.
    """
    if not IDENTIFIER_PATTERN.match(value):
        raise ValueError(
            f"malformed identifier {value!r}; the reference protocol requires "
            f"{IDENTIFIER_PATTERN.pattern}"
        )
    return value


def _check_protocol_version(value: str) -> str:
    """Refuse a protocol version the protocol would refuse. Same reasoning."""
    if not PROTOCOL_VERSION_PATTERN.match(value):
        raise ValueError(
            f"malformed protocol version {value!r}; the reference protocol "
            f"requires {PROTOCOL_VERSION_PATTERN.pattern}"
        )
    return value




Identifier = Annotated[str, AfterValidator(_check_identifier)]


ProtocolVersion = Annotated[str, AfterValidator(_check_protocol_version)]


class ServiceStatus(str, Enum):
    """Coarse service status."""

    OK = "ok"
    DEGRADED = "degraded"


class ApiErrorBody(ApiModel):
    """The body of the single error envelope."""

    code: str = Field(description="Machine-readable error code, e.g. NOT_FOUND.")
    message: str = Field(description="Human-readable explanation.")
    request_id: Optional[str] = Field(
        default=None, description="Correlation identifier, also in the X-Request-ID header."
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional structured detail; never a stack trace."
    )


class ApiErrorResponse(ApiModel):
    """Every non-2xx response has this shape."""

    error: ApiErrorBody


class HealthResponse(ApiModel):
    """Liveness payload. Cheap and deterministic; performs no simulation."""

    status: ServiceStatus
    api_version: str
    protocol_version: str
    application_version: Optional[str] = Field(
        default=None, description="Read from project metadata; null when it cannot be read."
    )
    environment: str = Field(description="Deployment label. Never a secret.")
    state: Dict[str, int] = Field(
        description="Counts of in-memory orchestration objects. Restart resets these."
    )


class VersionResponse(ApiModel):
    """Version inventory.

    ``api_version`` and ``protocol_version`` are independent: the first versions
    the HTTP contract, the second the QDS construction.
    """

    application_version: Optional[str] = None
    api_version: str
    protocol_version: str
    python_version: str
    packages: Dict[str, str] = Field(
        default_factory=dict, description="Installed versions, read from distribution metadata."
    )


class ReadyCheck(ApiModel):
    """One readiness probe."""

    name: str
    ok: bool
    detail: Optional[str] = None


class ReadyResponse(ApiModel):
    """Readiness payload. Probes component availability, never runs a simulation."""

    ready: bool
    checks: List[ReadyCheck]
