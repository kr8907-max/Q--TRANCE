"""Evaluation endpoints.

This is the one family of endpoints that legitimately consumes ground truth,
because FAR and FRR cannot be computed without knowing which trials were
malicious. Every response says so: ``ground_truth_used`` is true and the
assessment block names the boundary.

The full benchmark artifact is megabytes, so it lives behind its own endpoint and
the default retrieval returns the summary.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from backend.api.dependencies import StoreDep
from backend.api.schemas.common import ApiErrorResponse
from backend.api.schemas.evaluation import (
    EvaluationArtifactResponse,
    EvaluationRunRequest,
    EvaluationSummary,
)
from backend.api.services import evaluation_service

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post(
    "/run",
    response_model=EvaluationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Run a benchmark profile",
    description=(
        "'smoke' is the small profile the test suite uses and returns quickly. "
        "'reference' is the full recorded benchmark and takes minutes: the API runs "
        "it synchronously, so a client should allow a long timeout. The response "
        "carries the per-attack confusion matrices, the honest false-rejection "
        "rates and the curve inventory."
    ),
)
def run_evaluation(
    request: EvaluationRunRequest, store: StoreDep
) -> EvaluationSummary:
    payload = evaluation_service.run_evaluation(store, request)
    return EvaluationSummary(**payload)


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationSummary,
    responses={
        404: {"model": ApiErrorResponse, "description": "No such evaluation."}
    },
    summary="Retrieve an evaluation summary",
    description=(
        "Returns the compact summary stored for an earlier run. Use the artifact "
        "endpoint when the full benchmark report is needed."
    ),
)
def get_evaluation(evaluation_id: str, store: StoreDep) -> EvaluationSummary:
    return EvaluationSummary(**evaluation_service.get_summary(store, evaluation_id))


@router.get(
    "/{evaluation_id}/artifact",
    response_model=EvaluationArtifactResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "No such evaluation."}
    },
    summary="Retrieve the full benchmark artifact",
    description=(
        "Returns the complete benchmark payload. This is large -- the reference "
        "profile is on the order of megabytes -- so request it deliberately and "
        "prefer the summary endpoint otherwise."
    ),
)
def get_evaluation_artifact(
    evaluation_id: str, store: StoreDep
) -> EvaluationArtifactResponse:
    payload = evaluation_service.get_artifact(store, evaluation_id)
    return EvaluationArtifactResponse(**payload)
