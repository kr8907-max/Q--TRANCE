"""Validation of the security-analysis query parameters.

``GET /security/assumptions`` used to take ``noise_type`` and ``measurement_mode``
as unconstrained strings. Both select *which* register is resolved, so an
arbitrary value travelled into the security layer, where the register reported it
as an APPROXIMATE homogeneity assumption (for the channel) or a VIOLATED
``recognised_measurement_mode`` assumption (for the mode) rather than the request
being refused.

The accepted sets are the domains the simulation and security layers already
define -- the same constants the simulation and calibration request schemas
validate against -- so the API does not carry a second copy of either list.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from backend.api import ApiSettings, ApiStore, create_app
from backend.api.schemas.security import AssumptionsQuery
from backend.api.services import security_service
from backend.noise import VALID_NOISE_TYPES
from backend.simulation import MEASUREMENT_MODES

SCHEMA_MODULE = pathlib.Path("backend/api/schemas/security.py")
ROUTE_MODULE = pathlib.Path("backend/api/routes/security.py")

PATH = "/api/v1/security/assumptions"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    return TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore()),
        raise_server_exceptions=False,
    )







@pytest.mark.parametrize("value", VALID_NOISE_TYPES)
def test_every_known_channel_is_accepted(client, value: str) -> None:
    response = client.get(PATH, params={"noise_type": value})
    assert response.status_code == 200
    assert response.json()["noise_type"] == value


@pytest.mark.parametrize("value", MEASUREMENT_MODES)
def test_every_known_measurement_mode_is_accepted(client, value: str) -> None:
    response = client.get(PATH, params={"measurement_mode": value})
    assert response.status_code == 200
    assert response.json()["measurement_mode"] == value


def test_a_combination_of_valid_values_is_accepted(client) -> None:
    response = client.get(
        PATH, params={"noise_type": "bit_flip", "measurement_mode": "projective-analytic"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["noise_type"] == "bit_flip"
    assert body["measurement_mode"] == "projective-analytic"
    assert body["assumptions"]







@pytest.mark.parametrize(
    "value",
    ["not-a-channel", "depolarising", "DEPOLARIZING", "Depolarizing", "", " depolarizing "],
)
def test_an_unsupported_channel_is_refused(client, value: str) -> None:
    assert client.get(PATH, params={"noise_type": value}).status_code == 422


@pytest.mark.parametrize(
    "value",
    ["not-a-mode", "projective_analytic", "SAMPLED", "Sampled", "", " sampled "],
)
def test_an_unsupported_measurement_mode_is_refused(client, value: str) -> None:
    assert client.get(PATH, params={"measurement_mode": value}).status_code == 422


def test_one_invalid_parameter_refuses_the_whole_request(client) -> None:
    assert client.get(PATH, params={"noise_type": "nope", "measurement_mode": "sampled"}).status_code == 422
    assert client.get(PATH, params={"noise_type": "depolarizing", "measurement_mode": "nope"}).status_code == 422
    assert client.get(PATH, params={"noise_type": "nope", "measurement_mode": "nope"}).status_code == 422


def test_an_invalid_value_never_reaches_the_security_service(monkeypatch, client) -> None:
    """The rejection is at the API boundary, not inside the analysis."""
    calls = []

    def spy(**kwargs):
        calls.append(kwargs)
        raise AssertionError("the security service must not be reached")

    monkeypatch.setattr(security_service, "assumptions_view", spy)
    assert client.get(PATH, params={"noise_type": "nope"}).status_code == 422
    assert client.get(PATH, params={"measurement_mode": "nope"}).status_code == 422
    assert calls == []







def test_omitting_both_parameters_keeps_the_documented_defaults(client) -> None:
    body = client.get(PATH).json()
    assert body["noise_type"] == "depolarizing"
    assert body["measurement_mode"] == "sampled"


def test_the_validated_values_are_the_domains_own(client) -> None:
    """The register for a valid value is exactly the domain's register."""
    from backend.security import reference_assumptions, summarise_assumptions

    body = client.get(PATH, params={"noise_type": "phase_flip", "measurement_mode": "sampled"}).json()
    register = reference_assumptions(noise_type="phase_flip", measurement_mode="sampled")
    assert [item["key"] for item in body["assumptions"]] == [
        item.key for item in register.assumptions
    ]
    assert body["summary"] == dict(summarise_assumptions(register)["summary"])
    assert body["note"] == summarise_assumptions(register)["note"]


def test_the_query_model_defaults_match_the_published_contract() -> None:
    assert AssumptionsQuery().noise_type == "depolarizing"
    assert AssumptionsQuery().measurement_mode == "sampled"


def test_the_openapi_parameters_keep_their_shape(client) -> None:
    spec = client.get("/openapi.json").json()
    params = {
        p["name"]: p for p in spec["paths"][PATH]["get"]["parameters"]
    }
    assert sorted(params) == ["measurement_mode", "noise_type"]
    for name, default in (("noise_type", "depolarizing"), ("measurement_mode", "sampled")):
        param = params[name]
        assert param["in"] == "query"
        assert param["required"] is False
        assert param["schema"]["type"] == "string"
        assert param["schema"]["default"] == default

        assert "One of:" in param["description"]







def test_the_api_does_not_keep_a_second_copy_of_either_domain() -> None:
    """The accepted sets must come from the domain constants, not be re-listed."""
    tree = ast.parse(SCHEMA_MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
    assert "VALID_NOISE_TYPES" in imported
    assert "MEASUREMENT_MODES" in imported

    source = SCHEMA_MODULE.read_text(encoding="utf-8")

    assert '"bit_phase_flip"' not in source
    assert '"projective-analytic"' not in source


def test_the_route_does_not_import_the_domain_directly() -> None:
    """The API-layer boundary holds: validation lives in the schema module."""
    tree = ast.parse(ROUTE_MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(("backend.noise", "backend.simulation")), (
                f"the security route imports {node.module} directly"
            )
