"""Request-scoped context: the correlation identifier and the session reference.

Two different mechanisms, for a reason
--------------------------------------
The correlation identifier lives in a :class:`~contextvars.ContextVar`, because
the middleware sets it and the middleware reads it, both in the async context.

The session reference lives on the **request scope** instead. Route handlers here
are synchronous, so Starlette runs them in a worker thread, and a ContextVar
written inside that thread is discarded when it returns -- the middleware would
never observe it. The scope dictionary is shared between the middleware and the
route, so writing to it works.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any, Mapping, MutableMapping, Optional


REQUEST_ID_HEADER = "X-Request-ID"








REQUEST_ID_SCOPE_KEY = "sih26141.request_id"



SESSION_SCOPE_KEY = "sih26141.session_id"

_MAX_HEADER_CHARS = 128



_SAFE_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "-_.:"
)

_request_id: ContextVar[Optional[str]] = ContextVar("sih26141_request_id", default=None)


def new_request_id() -> str:
    """Return a fresh correlation identifier (128 bits, hex)."""
    return uuid.uuid4().hex


def sanitise_request_id(value: Optional[str]) -> Optional[str]:
    """Return ``value`` when it is a safe correlation id, otherwise ``None``.

    A caller-supplied id is echoed back to the caller and written to the access
    log, so it is accepted only when it is bounded and made of safe characters.
    """
    if not value:
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_HEADER_CHARS:
        return None
    if any(char not in _SAFE_ID_CHARS for char in candidate):
        return None
    return candidate


def current_request_id() -> Optional[str]:
    """Return the correlation identifier for the request being handled."""
    return _request_id.get()


def set_request_id(value: str):
    """Bind a correlation identifier; returns the reset token."""
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def request_id_for(scope: Mapping[str, Any]) -> Optional[str]:
    """Return the correlation identifier for a request, from the scope.

    Used by handlers that run outside the middleware's context.
    """
    value = scope.get(REQUEST_ID_SCOPE_KEY)
    return str(value) if value else None


def bind_session_id(scope: MutableMapping[str, Any], session_id: Optional[str]) -> None:
    """Record the session a request is about on the request scope.

    Used by routes that take the session from the body rather than the path.
    Routes whose session is a path parameter need not call this: the middleware
    reads ``scope['path_params']`` after routing.
    """
    if session_id:
        scope[SESSION_SCOPE_KEY] = str(session_id)


def session_id_for(scope: Mapping[str, Any]) -> Optional[str]:
    """Return the session a request was about, for the access log."""
    explicit = scope.get(SESSION_SCOPE_KEY)
    if explicit:
        return str(explicit)
    path_params = scope.get("path_params") or {}
    value = path_params.get("session_id")
    return str(value) if value else None
