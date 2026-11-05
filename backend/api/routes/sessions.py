"""Signing-session endpoints.

Lifecycle
---------
``POST /sessions`` creates a session as ``CREATED``. ``POST /sessions/{id}/sign``
moves it to ``SIGNED``. Verification (``POST /verify`` with a ``session_id``)
moves it to ``VERIFIED`` or ``REJECTED``. ``POST /sessions/{id}/expire`` moves it
to ``EXPIRED``. Every other transition is refused with a 409, so a session cannot
skip a step or move twice.

This lifecycle is an application concern. It does not replace the protocol's own
session status, which is reported separately as ``protocol_status``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import SettingsDep, StoreDep, configured_body
from backend.api.schemas.common import ApiErrorResponse
from backend.api.schemas.session import (
    SessionCreateRequest,
    SessionListResponse,
    SessionSignResponse,
    SessionSummary,
    SessionView,
)
from backend.api.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


SessionCreateBody = Annotated[
    SessionCreateRequest, Depends(configured_body(SessionCreateRequest))
]

_NOT_FOUND = {404: {"model": ApiErrorResponse, "description": "No such session."}}
_CONFLICT = {
    409: {
        "model": ApiErrorResponse,
        "description": "The session is not in a state that allows this transition.",
    }
}


@router.post(
    "",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reference signing session",
    description=(
        "Creates a session with the M2 session constructor. Returns the public "
        "session material: identifier, nonce, binding metadata and status. The "
        "reference construction has no secret key, so nothing secret exists to "
        "leak."
    ),
)
def create_session(
    request: SessionCreateBody, store: StoreDep
) -> SessionView:
    record = session_service.create(store, request)
    return SessionView(**session_service.session_view(record))


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions",
    description=(
        "Lists the sessions this process knows about. The store is in memory, so "
        "a restart returns an empty list."
    ),
)
def list_sessions(store: StoreDep) -> SessionListResponse:
    entries = [SessionSummary(**item) for item in session_service.listing(store)]
    return SessionListResponse(sessions=entries, total=len(entries))


@router.get(
    "/{session_id}",
    response_model=SessionView,
    responses={**_NOT_FOUND},
    summary="Get one session",
    description=(
        "Returns one session's public view, including its lifecycle history. The "
        "store is in memory, so a session created before a restart is not found."
    ),
)
def get_session(session_id: str, store: StoreDep, settings: SettingsDep) -> SessionView:
    record = store.get_session(session_id, ttl_seconds=settings.session_ttl_seconds)
    return SessionView(**session_service.session_view(record))


@router.post(
    "/{session_id}/sign",
    response_model=SessionSignResponse,
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Sign a session",
    description=(
        "Runs the M2 signer over the session and returns the serialized reference "
        "transcript and its hash. Signing is deterministic: the signer's simulator "
        "seed is fixed, so the same session yields the same transcript."
    ),
)
def sign_session(
    session_id: str, store: StoreDep, settings: SettingsDep
) -> SessionSignResponse:
    record = session_service.sign(store, session_id, settings)
    return SessionSignResponse(**session_service.sign_view(record))


@router.post(
    "/{session_id}/expire",
    response_model=SessionView,
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Expire a session",
    description=(
        "Moves a session to EXPIRED explicitly. Automatic expiry is disabled by "
        "default so that lifecycle behaviour is never a surprise; it can be "
        "enabled with the session TTL setting."
    ),
)
def expire_session(
    session_id: str, store: StoreDep, settings: SettingsDep
) -> SessionView:
    record = session_service.expire(store, session_id, settings)
    return SessionView(**session_service.session_view(record))
