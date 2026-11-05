"""Operational endpoints: /health, /ready, /version."""

from __future__ import annotations

from backend.api.version import API_PREFIX, API_VERSION


def test_health_reports_status_and_versions(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == API_VERSION
    assert body["protocol_version"]
    assert body["environment"] == "test"
    assert body["state"] == {"sessions": 0, "calibrations": 0, "evaluations": 0}


def test_health_is_unversioned(client) -> None:


    assert client.get("/health").status_code == 200
    assert client.get(f"{API_PREFIX}/health").status_code == 404


def test_health_reflects_in_memory_state(client) -> None:
    client.post(
        "/api/v1/sessions",
        json={"message": "m", "signer_id": "a", "verifier_id": "b", "state_count": 4},
    )
    assert client.get("/health").json()["state"]["sessions"] == 1


def test_health_exposes_no_secret(client) -> None:
    body = client.get("/health").json()
    joined = " ".join(str(value) for value in body.values()).lower()
    for forbidden in ("secret", "password", "token", "key", "credential"):
        assert forbidden not in joined


def test_ready_reports_every_required_component(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    names = {check["name"] for check in body["checks"]}
    assert {
        "protocol",
        "simulation",
        "detection",
        "calibration",
        "evaluation",
        "security",
        "store",
    } <= names
    assert all(check["ok"] for check in body["checks"])


def test_version_reports_real_versions(client) -> None:
    body = client.get("/version").json()
    assert body["api_version"] == API_VERSION
    assert body["protocol_version"]
    assert body["python_version"].startswith("3.")

    assert "qiskit" in body["packages"]
    assert all(isinstance(value, str) and value for value in body["packages"].values())


def test_application_version_comes_from_project_metadata(client) -> None:

    body = client.get("/version").json()
    assert body["application_version"] == "0.1.0"


def test_health_ready_and_version_run_no_simulation(client, monkeypatch) -> None:
    """The cheap endpoints must stay cheap."""
    import backend.simulation as simulation

    def _explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("an operational endpoint executed a scenario")

    monkeypatch.setattr(simulation, "run_scenario", _explode)
    for path in ("/health", "/ready", "/version"):
        assert client.get(path).status_code == 200, path


def test_health_does_not_read_the_benchmark_artifact(client, monkeypatch) -> None:
    """Liveness must not depend on a large artifact being present."""
    import backend.api.services.calibration_service as calibration_service

    def _explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("an operational endpoint read the benchmark artifact")

    monkeypatch.setattr(calibration_service, "load_reference_artifact", _explode)
    for path in ("/health", "/ready", "/version"):
        assert client.get(path).status_code == 200, path
