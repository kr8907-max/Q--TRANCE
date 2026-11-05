"""Verification endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.api.context import bind_session_id
from backend.api.dependencies import SettingsDep, StoreDep, configured_body
from backend.api.schemas.common import ApiErrorResponse
from backend.api.schemas.verification import VerificationRequest, VerificationResponse
from backend.api.services import verification_service

router = APIRouter(tags=["verification"])


VerificationBody = Annotated[
    VerificationRequest, Depends(configured_body(VerificationRequest))
]


@router.post(
    "/verify",
    response_model=VerificationResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Named session not found."},
        409: {
            "model": ApiErrorResponse,
            "description": (
                "The named session is not SIGNED, so its outcome cannot be recorded. "
                "Re-issue the request without session_id to obtain the verification "
                "result alone."
            ),
        },
    },
    summary="Verify a transcript",
    description=(
        "Runs the M2 verifier and returns its structured result unchanged: the "
        "individual validity flags, the errors and the warnings, plus the raw "
        "counts. A transcript with malformed content is not an HTTP error -- it "
        "comes back as a 200 with accepted=false, because that is what the "
        "protocol's verifier decides. Only a transcript that is not a JSON object "
        "at all is a 422."
    ),
)
def verify_transcript(
    request: VerificationBody,
    http_request: Request,
    store: StoreDep,
    settings: SettingsDep,
) -> VerificationResponse:



    bind_session_id(http_request.scope, request.session_id)
    payload = verification_service.verify_request(store, request, settings)
    return VerificationResponse(**payload)
