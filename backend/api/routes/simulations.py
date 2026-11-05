"""Simulation endpoints.

Two routes, two schemas, and the split is the point
---------------------------------------------------
``POST /simulations`` returns observable output only. Its response model has no
ground-truth field at all, so an operational response cannot carry an attack
label even by accident.

``POST /simulations/evaluation`` returns the same observable output *plus*
ground truth. It exists because evaluation genuinely needs the label, and it is
separate because a caller who wants to know whether an attack happened should
have to say so explicitly rather than read it off a normal simulation response.

Making the split structural rather than a flag means the operational path cannot
be widened into an evaluation path by a request body.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import configured_body
from backend.api.schemas.common import ApiErrorResponse
from backend.api.schemas.simulation import (
    SimulationEvaluationResponse,
    SimulationRequest,
    SimulationResponse,
)
from backend.api.services import simulation_service

router = APIRouter(prefix="/simulations", tags=["simulation"])


SimulationBody = Annotated[
    SimulationRequest, Depends(configured_body(SimulationRequest))
]

_REFUSED = {
    400: {
        "model": ApiErrorResponse,
        "description": (
            "The scenario configuration was refused by the noise, attack or "
            "scenario module."
        ),
    }
}

_RUN_DESCRIPTION = (
    "Executes one M3 scenario and returns the observable experiment data: the "
    "per-state observations, the mismatch counts, the verification result and the "
    "authorization observations. Deterministic for a given seed. No ground truth "
    "is returned, and this response model has no field that could carry it."
)


@router.post(
    "",
    response_model=SimulationResponse,
    responses={**_REFUSED},
    summary="Run a scenario (observable output only)",
    description=_RUN_DESCRIPTION,
)
def run_simulation(request: SimulationBody) -> SimulationResponse:
    payload = simulation_service.run_simulation(request)
    return SimulationResponse(**payload)


@router.post(
    "/evaluation",
    response_model=SimulationEvaluationResponse,
    responses={**_REFUSED},
    summary="Run a scenario as an evaluation artifact (includes ground truth)",
    description=(
        _RUN_DESCRIPTION
        + " This variant additionally returns the simulator's ground truth, "
        "including the hidden attack label. It is evaluation material: the label "
        "describes what the simulator did, not what a detector could conclude."
    ),
)
def run_simulation_evaluation(
    request: SimulationBody,
) -> SimulationEvaluationResponse:
    payload = simulation_service.run_simulation(
        request, include_ground_truth=True
    )
    return SimulationEvaluationResponse(**payload)
