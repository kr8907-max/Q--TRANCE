"""Request correlation, payload limits and structured access logging.

Three concerns, all of them cross-cutting, so they live in one middleware rather
than being repeated in every route:

1. **Correlation.** Every request gets an identifier, either taken from a safe
   caller-supplied ``X-Request-ID`` or freshly generated. It is returned in the
   response header and included in every log line for that request.
2. **Payload bound.** A request whose declared body exceeds the configured limit
   is refused before any handler runs, so a single request cannot ask the API to
   buffer unbounded input.
3. **Access log.** One structured record per request, with the fields needed to
   correlate a report with a request: method, route, status, duration and the
   session the request was about.

The log record deliberately excludes request bodies and message contents.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.api.config import ApiSettings
from backend.api.context import (
    REQUEST_ID_HEADER,
    REQUEST_ID_SCOPE_KEY,
    current_request_id,
    new_request_id,
    reset_request_id,
    sanitise_request_id,
    session_id_for,
    set_request_id,
)
from backend.api.errors import ErrorCode, error_response

logger = logging.getLogger("sih26141.api")


_LOGGING_SETUP_LOCK = threading.Lock()


_LOG_FIELDS = (
    "request_id",
    "method",
    "route",
    "path",
    "status_code",
    "duration_ms",
    "session_id",
    "outcome",
    "error_type",
)


class JsonLogFormatter(logging.Formatter):
    """Render a log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Attach the structured handler to the API logger, once.

    Idempotent, and guarded by a lock: building two application objects
    concurrently must not install the handler twice, or every log line would be
    emitted twice.
    """
    api_logger = logging.getLogger("sih26141.api")
    api_logger.setLevel(level)
    with _LOGGING_SETUP_LOCK:
        if not any(isinstance(h.formatter, JsonLogFormatter) for h in api_logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(JsonLogFormatter())
            api_logger.addHandler(handler)
    return api_logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id, enforce the payload bound, and log the request."""

    def __init__(self, app: Any, *, settings: ApiSettings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = sanitise_request_id(request.headers.get(REQUEST_ID_HEADER))
        if request_id is None:
            request_id = new_request_id()
        request_token = set_request_id(request_id)


        request.scope[REQUEST_ID_SCOPE_KEY] = request_id
        started = time.perf_counter()

        try:
            oversize = self._declared_length(request)
            if oversize is not None:
                response = error_response(
                    413,
                    ErrorCode.PAYLOAD_TOO_LARGE,
                    f"request body exceeds the {self._settings.max_request_bytes} byte limit",
                    details={
                        "declared_bytes": oversize,
                        "limit_bytes": self._settings.max_request_bytes,
                    },
                )
                response.headers[REQUEST_ID_HEADER] = request_id
                self._log(request, response, started, outcome="payload_too_large")
                return response

            try:
                response = await call_next(request)
            except Exception as exc:
                self._log(
                    request,
                    None,
                    started,
                    outcome="error",
                    error_type=type(exc).__name__,
                )
                raise

            response.headers[REQUEST_ID_HEADER] = request_id
            self._log(request, response, started)
            return response
        finally:
            reset_request_id(request_token)

    def _declared_length(self, request: Request) -> Optional[int]:
        """Return the declared body length when it is missing or too large.

        Only the declared ``Content-Length`` is consulted. Reading the body here
        would consume the stream the route needs; a client that omits the header
        is bounded by the server's own limits instead.
        """
        raw = request.headers.get("content-length")
        if raw is None:
            return None
        try:
            length = int(raw)
        except ValueError:
            return -1
        if length < 0 or length > self._settings.max_request_bytes:
            return length
        return None

    def _log(
        self,
        request: Request,
        response: Optional[Response],
        started: float,
        *,
        outcome: str = "ok",
        error_type: Optional[str] = None,
    ) -> None:
        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or request.url.path
        status_code = getattr(response, "status_code", None)
        if outcome == "ok" and status_code is not None and status_code >= 400:
            outcome = "client_error" if status_code < 500 else "server_error"
        logger.info(
            "request",
            extra={
                "request_id": current_request_id(),
                "method": request.method,
                "route": route_path,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "session_id": session_id_for(request.scope),
                "outcome": outcome,
                "error_type": error_type,
            },
        )
