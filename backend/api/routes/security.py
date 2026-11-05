"""Security-analysis endpoints.

These expose the M6 interpretation layer. Every response carries an explicit
assessment block rather than a verdict, and the observability response keeps the
per-threat breakdown instead of collapsing it into "covered".

There is no endpoint here that answers "is this secure".
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import configured_body
from backend.api.schemas.security import (
    AnalyzeRequest,
    AnalyzeResponse,
    AssumptionsQuery,
    AssumptionsResponse,
    CompositionResponse,
    ObservabilityResponse,
)
from backend.api.services import security_service

router = APIRouter(prefix="/security", tags=["security"])


AnalyzeBody = Annotated[AnalyzeRequest, Depends(configured_body(AnalyzeRequest))]


@router.get(
    "/assumptions",
    response_model=AssumptionsResponse,
    summary="Assumption register",
    description=(
        "Returns the assumptions the finite-sample results depend on, each with a "
        "status, its evidence and the consequence of violating it. The register "
        "depends on the channel and the measurement mode, which is why both are "
        "parameters."
    ),
)
def assumptions(query: Annotated[AssumptionsQuery, Query()]) -> AssumptionsResponse:
    payload = security_service.assumptions_view(
        noise_type=query.noise_type, measurement_mode=query.measurement_mode
    )
    return AssumptionsResponse(**payload)


@router.get(
    "/observability",
    response_model=ObservabilityResponse,
    summary="Threat-observability matrix",
    description=(
        "Reports what each modelled threat looks like to each layer: quantum "
        "disturbance, protocol anomaly, authorization evidence, replay evidence and "
        "detector visibility. A threat the quantum detector cannot see is reported "
        "as requiring a classical control, not as undetectable."
    ),
)
def observability() -> ObservabilityResponse:
    return ObservabilityResponse(**security_service.observability_view())


@router.get(
    "/composition",
    response_model=CompositionResponse,
    summary="Composition assessment",
    description=(
        "Reports each milestone as a component with its unresolved dependency. "
        "formal_composition_theorem_present is false: the components were evaluated "
        "individually and nothing here claims they compose into a secure system."
    ),
)
def composition() -> CompositionResponse:
    return CompositionResponse(**security_service.composition_view())


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Check statements against the forbidden-claim register",
    description=(
        "Runs the M6 interpretation checker over caller-supplied sentences and "
        "returns the verdict for each, together with the forbidden-claim register "
        "and the banned terminology. The checker is a blunt guard-rail with "
        "clause-level negation handling, not a completeness guarantee."
    ),
)
def analyze(request: AnalyzeBody) -> AnalyzeResponse:
    return AnalyzeResponse(**security_service.analyze_view(request))
