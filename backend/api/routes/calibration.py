"""Calibration endpoints.

``POST /calibration/run`` is the only expensive calibration path and it runs only
when asked. ``GET /calibration/reference`` describes the reference methodology
and reports the operating point recorded in the committed benchmark artifact.

Nothing here recalibrates as a side effect of another request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import StoreDep, configured_body
from backend.api.schemas.calibration import (
    CalibrationResponse,
    CalibrationRunRequest,
    ReferenceCalibrationResponse,
)
from backend.api.schemas.common import ApiErrorResponse
from backend.api.services import calibration_service

router = APIRouter(prefix="/calibration", tags=["calibration"])


CalibrationRunBody = Annotated[
    CalibrationRunRequest, Depends(configured_body(CalibrationRunRequest))
]


@router.post(
    "/run",
    response_model=CalibrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": "The calibration configuration was refused.",
        }
    },
    summary="Derive a threshold from honest-only data",
    description=(
        "Builds an honest-only calibration dataset, estimates the baseline and "
        "derives the operating point, using the M5 implementations. The threshold "
        "is valid only at the sample size, measurement mode, shot count and channel "
        "it was derived for; the response records all of them. The result is stored "
        "in memory and lost on restart."
    ),
)
def run_calibration(
    request: CalibrationRunBody, store: StoreDep
) -> CalibrationResponse:
    payload = calibration_service.run_calibration(store, request)
    return CalibrationResponse(**payload)


@router.get(
    "/reference",
    response_model=ReferenceCalibrationResponse,
    summary="Reference methodology and recorded operating point",
    description=(
        "Reports the reference threshold method, the error budget split and, when "
        "the committed benchmark artifact is present, the operating point recorded "
        "for it. The API reads the recorded point rather than recomputing it."
    ),
)
def reference_calibration() -> ReferenceCalibrationResponse:
    payload = calibration_service.reference_description()
    return ReferenceCalibrationResponse(**payload)


@router.get(
    "/{calibration_id}",
    response_model=CalibrationResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "No such calibration."}
    },
    summary="Retrieve a stored calibration",
    description="Returns a calibration produced earlier in this process. Lost on restart.",
)
def get_calibration(
    calibration_id: str, store: StoreDep
) -> CalibrationResponse:
    payload = store.get_calibration(calibration_id)
    return CalibrationResponse(**payload)
