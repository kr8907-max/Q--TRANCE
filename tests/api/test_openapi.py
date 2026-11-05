"""OpenAPI schema validity and endpoint inventory."""

from __future__ import annotations

import pathlib

import pytest

from backend.api.version import API_PREFIX

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


EXPECTED_VERSIONED_PATHS = {
    "/api/v1/sessions",
    "/api/v1/sessions/{session_id}",
    "/api/v1/sessions/{session_id}/sign",
    "/api/v1/sessions/{session_id}/expire",
    "/api/v1/verify",
    "/api/v1/simulations",
    "/api/v1/simulations/evaluation",
    "/api/v1/detect",
    "/api/v1/calibration/run",
    "/api/v1/calibration/reference",
    "/api/v1/calibration/{calibration_id}",
    "/api/v1/evaluation/run",
    "/api/v1/evaluation/{evaluation_id}",
    "/api/v1/evaluation/{evaluation_id}/artifact",
    "/api/v1/security/assumptions",
    "/api/v1/security/observability",
    "/api/v1/security/composition",
    "/api/v1/security/analyze",
}


EXPECTED_ROOT_PATHS = {"/health", "/ready", "/version"}


@pytest.fixture(scope="module")
def schema() -> dict:
    """The generated OpenAPI document, from a module-scoped application."""
    from fastapi.testclient import TestClient

    from backend.api import ApiSettings, ApiStore, create_app

    client = TestClient(
        create_app(
            settings=ApiSettings(environment="test"), store=ApiStore()
        )
    )
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_the_schema_generates(schema) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]
    assert schema["info"]["version"]
    assert schema["info"]["description"]


def test_the_endpoint_inventory_is_exactly_as_declared(schema) -> None:
    assert set(schema["paths"]) == EXPECTED_VERSIONED_PATHS | EXPECTED_ROOT_PATHS
    assert len(schema["paths"]) == 21


def test_every_business_path_is_versioned(schema) -> None:
    for path in schema["paths"]:
        if path in EXPECTED_ROOT_PATHS:
            continue
        assert path.startswith(API_PREFIX + "/"), path


def test_operational_paths_are_not_versioned(schema) -> None:
    for path in EXPECTED_ROOT_PATHS:
        assert path in schema["paths"]
        assert not path.startswith(API_PREFIX)


def test_required_models_are_present(schema) -> None:
    components = schema["components"]["schemas"]
    for model in (
        "HealthResponse",
        "ReadyResponse",
        "VersionResponse",
        "ApiErrorResponse",
        "SessionCreateRequest",
        "SessionView",
        "SessionSignResponse",
        "VerificationRequest",
        "VerificationResponse",
        "SimulationRequest",
        "SimulationResponse",
        "SimulationEvaluationResponse",
        "DetectionRequest",
        "DetectionResponse",
        "CalibrationRunRequest",
        "CalibrationResponse",
        "ReferenceCalibrationResponse",
        "EvaluationRunRequest",
        "EvaluationSummary",
        "EvaluationArtifactResponse",
        "AssumptionsResponse",
        "ObservabilityResponse",
        "CompositionResponse",
        "AnalyzeRequest",
        "AnalyzeResponse",
    ):
        assert model in components, model


def test_the_ground_truth_models_are_separate(schema) -> None:
    components = schema["components"]["schemas"]
    operational = components["SimulationResponse"]["properties"]
    evaluation = components["SimulationEvaluationResponse"]["properties"]

    assert "ground_truth" not in operational
    assert "ground_truth" in evaluation


def test_the_detection_request_schema_carries_no_label(schema) -> None:
    properties = schema["components"]["schemas"]["DetectionRequest"]["properties"]
    for forbidden in ("attack_type", "attack_fraction", "noise_strength", "ground_truth"):
        assert forbidden not in properties, forbidden


def test_every_operation_is_documented(schema) -> None:
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), (path, method)
            assert operation.get("description"), (path, method)
            assert operation.get("responses"), (path, method)


def test_operations_declare_error_responses(schema) -> None:

    sessions = schema["paths"]["/api/v1/sessions/{session_id}"]["get"]
    assert "404" in sessions["responses"]
    assert sessions["responses"]["404"]["content"]["application/json"]["schema"]


def test_security_endpoints_are_tagged(schema) -> None:
    tags = {
        tag
        for operations in schema["paths"].values()
        for operation in operations.values()
        for tag in operation.get("tags", [])
    }
    assert {
        "operations",
        "sessions",
        "verification",
        "simulation",
        "detection",
        "calibration",
        "evaluation",
        "security",
    } <= tags


def test_the_schema_carries_the_security_caveats(schema) -> None:
    description = schema["info"]["description"]
    assert "does not claim" in description
    assert "assumption-conditioned" in description
    assert "lost on" in description








_DOC_PROSE_TOKENS = frozenset({"created", "signed", "true", "false", "null"})


def _documented_field_names() -> set:
    """Field names the API reference lists in its 'Key schemas' section."""
    import re

    text = (REPO_ROOT / "docs" / "api" / "api-reference.md").read_text(encoding="utf-8")
    section = text.split("## 5. Key schemas", 1)[1].split("## 6.", 1)[0]
    found = set()
    for token in re.findall(r"`([^`]+)`", section):
        for part in re.split(r"[,\s]+", token):
            part = part.strip()
            if re.fullmatch(r"[a-z][a-z0-9_]*", part):
                found.add(part)
    return found - _DOC_PROSE_TOKENS


def test_every_field_named_in_the_reference_document_exists(schema) -> None:
    """A renamed or removed field must not leave the document stale.

    The document is prose, so this checks the direction that matters: every field
    it tells a client to expect really is in a schema. Without it, a rename would
    silently invalidate the reference.
    """
    properties = set()
    for model in schema["components"]["schemas"].values():
        properties |= set(model.get("properties", {}) or {})

    documented = _documented_field_names()
    assert len(documented) > 50, "the extractor stopped finding fields"

    unknown = sorted(name for name in documented if name not in properties)
    assert not unknown, f"api-reference.md names fields that do not exist: {unknown}"


def test_the_operational_and_evaluation_models_differ_only_by_ground_truth(
    schema,
) -> None:
    """Pins the split the document describes in its 'Key schemas' section."""
    components = schema["components"]["schemas"]
    operational = set(components["SimulationResponse"]["properties"])
    evaluation = set(components["SimulationEvaluationResponse"]["properties"])
    assert evaluation - operational == {"ground_truth"}
    assert not operational - evaluation
