"""Detection endpoint.

Observable input only, by construction. The request schema has no field for an
attack type, an attack fraction, a noise strength or any ground-truth metadata,
and unknown fields are refused rather than ignored. A caller cannot reach the
detector with the answer already in hand.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import StoreDep, configured_body
from backend.api.schemas.common import ApiErrorResponse
from backend.api.schemas.detection import DetectionRequest, DetectionResponse
from backend.api.services import detection_service

router = APIRouter(tags=["detection"])


DetectionBody = Annotated[
    DetectionRequest, Depends(configured_body(DetectionRequest))
]


@router.post(
    "/detect",
    response_model=DetectionResponse,
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": "The observable input was refused by the detector.",
        }
    },
    summary="Detect over observable evidence",
    description=(
        "Runs the M4 detector over observable input and returns its structured "
        "evidence: the overall status, the findings with their evidence items, the "
        "diagnostic statistics and the explanation. The detector never receives an "
        "attack label, and the response says so in its security_assessment block."
    ),
)
def detect(
    request: DetectionBody, store: StoreDep
) -> DetectionResponse:
    payload = detection_service.detect_request(store, request)
    return DetectionResponse(**payload)
