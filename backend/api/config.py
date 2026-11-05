"""Runtime configuration for the API boundary.

Configuration is read from the environment rather than hard-coded into routes, so
the same application object can be run in development and in a locked-down
deployment without editing code.

Two deliberate security choices live here:

* **CORS is never silently wildcarded.** ``*`` has to be asked for explicitly,
  because this prototype has no authentication and a wildcard origin would let
  any web page read every response.
* **Every input bound is a named setting.** Request size, message length, state
  count and shot count are capped so that a single request cannot ask the API to
  do unbounded work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


ENV_CORS_ORIGINS = "SIH26141_API_CORS_ORIGINS"


ENV_ENVIRONMENT = "SIH26141_API_ENVIRONMENT"


ENV_ALLOW_WILDCARD_CORS = "SIH26141_API_ALLOW_WILDCARD_CORS"


DEFAULT_DEVELOPMENT_ORIGINS: Tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _parse_origins(raw: Optional[str]) -> Optional[Tuple[str, ...]]:
    if raw is None:
        return None
    origins = tuple(part.strip() for part in raw.split(",") if part.strip())
    return origins
















ABSOLUTE_MAX_MESSAGE_CHARS = 1_048_576


ABSOLUTE_MAX_STATEMENTS_PER_REQUEST = 4_096


ABSOLUTE_MAX_SHOT_COUNT = 65_536


ABSOLUTE_MAX_CALIBRATION_SESSIONS = 4_096


@dataclass(frozen=True)
class ApiSettings:
    """Immutable API settings.

    Constructed once per application; nothing here is mutated at request time.
    """

    environment: str = "development"
    cors_origins: Tuple[str, ...] = DEFAULT_DEVELOPMENT_ORIGINS


    max_request_bytes: int = 1_048_576
    max_message_chars: int = 4096
    max_statements_per_request: int = 50
    max_shot_count: int = 1024
    max_calibration_sessions: int = 64









    session_ttl_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        """Refuse a configured limit above its static ceiling.

        The schemas declare a stationary bound (see the absolute ceilings above)
        and the validators apply the configured one on top of it. A setting above
        its ceiling would make the static bound the effective limit, silently
        ignoring the configuration -- so it is refused at construction instead,
        where the mistake is visible, rather than at the first request.
        """
        ceilings = {
            "max_message_chars": ABSOLUTE_MAX_MESSAGE_CHARS,
            "max_statements_per_request": ABSOLUTE_MAX_STATEMENTS_PER_REQUEST,
            "max_shot_count": ABSOLUTE_MAX_SHOT_COUNT,
            "max_calibration_sessions": ABSOLUTE_MAX_CALIBRATION_SESSIONS,
        }
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if value < 1:
                raise ValueError(f"{name} must be at least 1, got {value!r}")
            if value > ceiling:
                raise ValueError(
                    f"{name}={value} exceeds the absolute ceiling of {ceiling} "
                    f"that the request schemas are built around"
                )

    @property
    def cors_is_wildcard(self) -> bool:
        return "*" in self.cors_origins

    @classmethod
    def from_environment(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "ApiSettings":
        """Build settings from ``environ`` (defaults to ``os.environ``)."""
        env = os.environ if environ is None else environ
        raw = env.get(ENV_CORS_ORIGINS)
        parsed = _parse_origins(raw)
        allow_wildcard = str(env.get(ENV_ALLOW_WILDCARD_CORS, "")).strip().lower() in _TRUTHY
        origins = DEFAULT_DEVELOPMENT_ORIGINS if parsed is None else parsed





        if "*" in origins and not allow_wildcard:
            raise ValueError(
                f"{ENV_CORS_ORIGINS} contains '*'. A wildcard origin is refused "
                f"by default because this API has no authentication. Set "
                f"{ENV_ALLOW_WILDCARD_CORS}=1 to accept it deliberately."
            )

        return cls(
            environment=str(env.get(ENV_ENVIRONMENT, "development")).strip() or "development",
            cors_origins=origins,
        )
