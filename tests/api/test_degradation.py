"""Error and degradation paths.

A coverage sweep of the API suite showed the happy paths at 100% but a cluster of
error branches never executed: the calibration measurement-mode validator, the
400 paths for detection and simulation, the conflict and not-found guards in the
store, the oversize-body branch for a malformed ``Content-Length``, and every
place the reference-artifact reader is allowed to return nothing.

These are exactly the paths that matter when something goes wrong, so they are
tested directly rather than left to chance.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.api import ApiSettings, ApiStore, create_app
from backend.api.context import sanitise_request_id
from backend.api.errors import ApiError, ErrorCode
from backend.api.store import SessionLifecycle, SessionRecord
from backend.protocol import create_session

SESSION = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}







def test_an_unknown_measurement_mode_is_refused_by_calibration(client) -> None:

    response = client.post(
        "/api/v1/calibration/run",
        json={"state_count": 20, "session_count": 1, "measurement_mode": "made-up"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNPROCESSABLE_ENTITY"


@pytest.mark.parametrize("value", ["", "x" * 129, "has spaces", "new\nline"])
def test_unsafe_correlation_ids_are_rejected(value: str) -> None:
    assert sanitise_request_id(value) is None


def test_a_safe_correlation_id_is_kept() -> None:
    assert sanitise_request_id("abc-123_4.5:6") == "abc-123_4.5:6"


def test_an_empty_correlation_id_falls_back_to_a_generated_one(client) -> None:
    response = client.get("/health", headers={"X-Request-ID": ""})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_an_overlong_correlation_id_falls_back_to_a_generated_one(client) -> None:
    response = client.get("/health", headers={"X-Request-ID": "x" * 200})
    assert response.headers["X-Request-ID"] != "x" * 200
    assert len(response.headers["X-Request-ID"]) <= 128







def test_a_detection_input_error_becomes_a_400(client, monkeypatch) -> None:
    import backend.api.services.detection_service as detection_service
    from backend.detection import DetectionInputError

    def _refuse(*args, **kwargs):
        raise DetectionInputError("the state list is inconsistent")

    monkeypatch.setattr(detection_service, "detect", _refuse)
    response = client.post("/api/v1/detect", json={"states": []})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"
    assert "inconsistent" in error["details"]["reason"]


def test_a_scenario_the_runner_refuses_becomes_a_400(client, monkeypatch) -> None:
    import backend.api.services.simulation_service as simulation_service
    from backend.protocol import ProtocolError

    def _refuse(*args, **kwargs):
        raise ProtocolError("the runner refused this scenario")

    monkeypatch.setattr(simulation_service, "run_scenario", _refuse)
    response = client.post("/api/v1/simulations", json={"state_count": 8})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"
    assert error["details"]["error_type"] == "ProtocolError"


def test_an_out_of_range_noise_strength_is_refused_by_schema(client) -> None:
    response = client.post(
        "/api/v1/simulations",
        json={"noise": {"noise_type": "depolarizing", "noise_strength": 9.0}},
    )
    assert response.status_code == 422













CLIENT_ERROR_CASES = [
    (
        "malformed protocol version",
        "POST",
        "/api/v1/sessions",
        {"message": "m", "signer_id": "a", "verifier_id": "b", "protocol_version": "nonsense"},
    ),
    (
        "identity longer than the protocol allows",
        "POST",
        "/api/v1/sessions",
        {"message": "m", "signer_id": "s" * 200, "verifier_id": "b"},
    ),
    (
        "identity the protocol pattern rejects",
        "POST",
        "/api/v1/sessions",
        {"message": "m", "signer_id": "-leading-dash", "verifier_id": "b"},
    ),
    (
        "attack fraction on a non-fractional attack",
        "POST",
        "/api/v1/simulations",
        {"state_count": 4, "attack": {"attack_type": "forgery", "fraction": 0.5}},
    ),
    (
        "unknown replay mode",
        "POST",
        "/api/v1/simulations",
        {
            "state_count": 4,
            "attack": {"attack_type": "replay", "parameters": {"replay_mode": "bogus"}},
        },
    ),
    ("unknown noise type", "POST", "/api/v1/simulations", {"noise": {"noise_type": "bogus"}}),
    ("unknown attack type", "POST", "/api/v1/simulations", {"attack": {"attack_type": "bogus"}}),
    (
        "unknown measurement mode",
        "POST",
        "/api/v1/simulations",
        {"measurement_mode": "bogus"},
    ),
    (
        "malformed extra authorized verifier",
        "POST",
        "/api/v1/simulations",
        {"state_count": 4, "extra_authorized_verifiers": ["not valid"]},
    ),
    ("unknown calibration noise type", "POST", "/api/v1/calibration/run", {"noise_type": "bogus"}),
    (
        "unknown calibration statistic",
        "POST",
        "/api/v1/calibration/run",
        {"statistic": "bogus"},
    ),
    (
        "malformed expected protocol version",
        "POST",
        "/api/v1/verify",
        {
            "message": "m",
            "transcript": {},
            "verifier_context": {"verifier_id": "b", "expected_protocol_version": "junk"},
        },
    ),
    ("unknown evaluation profile", "POST", "/api/v1/evaluation/run", {"profile": "bogus"}),
]


@pytest.mark.parametrize(
    "label,method,path,payload",
    CLIENT_ERROR_CASES,
    ids=[case[0] for case in CLIENT_ERROR_CASES],
)
def test_client_input_never_produces_a_server_error(
    lenient_client, label: str, method: str, path: str, payload: dict
) -> None:
    """A rejected client request must be a 4xx, never a 5xx.

    ``lenient_client`` does not re-raise server exceptions, so a crash inside a
    handler surfaces here as a 500 rather than as a test error.
    """
    response = lenient_client.request(method, path, json=payload)
    assert 400 <= response.status_code < 500, (
        f"{label} answered {response.status_code}: {response.text[:200]}"
    )


def test_a_garbage_transcript_is_a_verdict_not_a_server_error(lenient_client) -> None:
    """The protocol turns malformed content into accepted=false, not a crash."""
    response = lenient_client.post(
        "/api/v1/verify",
        json={
            "message": "m",
            "transcript": {"garbage": True},
            "verifier_context": {"verifier_id": "b"},
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is False







def test_the_store_refuses_a_duplicate_session_id() -> None:
    store = ApiStore()
    session = create_session("m", signer_id="a", verifier_id="b", state_count=4)
    store.add_session(SessionRecord(session=session))

    with pytest.raises(ApiError) as caught:
        store.add_session(SessionRecord(session=session))
    assert caught.value.code is ErrorCode.CONFLICT
    assert caught.value.details["session_id"] == session.session_id


def test_publishing_to_an_unknown_session_is_not_found() -> None:
    store = ApiStore()
    session = create_session("m", signer_id="a", verifier_id="b", state_count=4)

    with pytest.raises(ApiError) as signing:
        store.publish_signing(
            session.session_id, session=session, transcript={}, transcript_hash="h"
        )
    assert signing.value.code is ErrorCode.NOT_FOUND

    with pytest.raises(ApiError) as verifying:
        store.publish_verification(session.session_id, accepted=True, verification={})
    assert verifying.value.code is ErrorCode.NOT_FOUND


def test_publishing_after_a_reset_is_not_found() -> None:
    """The window between reading a session and publishing its signature."""
    store = ApiStore()
    session = create_session("m", signer_id="a", verifier_id="b", state_count=4)
    store.add_session(SessionRecord(session=session))
    store.reset()

    with pytest.raises(ApiError) as caught:
        store.publish_signing(
            session.session_id, session=session, transcript={}, transcript_hash="h"
        )
    assert caught.value.code is ErrorCode.NOT_FOUND


def test_ttl_does_not_touch_a_terminal_session() -> None:
    store = ApiStore()
    session = create_session("m", signer_id="a", verifier_id="b", state_count=4)
    record = store.add_session(SessionRecord(session=session))
    store.transition(session.session_id, SessionLifecycle.EXPIRED)


    store.get_session(session.session_id, ttl_seconds=0)
    assert record.history == ["CREATED", "EXPIRED"]







def test_a_malformed_content_length_is_treated_as_oversize() -> None:
    from fastapi.testclient import TestClient

    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    response = TestClient(app).post(
        "/api/v1/security/analyze",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"







def test_settings_from_an_empty_environment_use_the_development_origins() -> None:
    settings = ApiSettings.from_environment({})
    assert settings.environment == "development"
    assert settings.cors_origins == ApiSettings().cors_origins
    assert settings.cors_is_wildcard is False


def test_settings_read_the_environment_label() -> None:
    settings = ApiSettings.from_environment({"SIH26141_API_ENVIRONMENT": "staging"})
    assert settings.environment == "staging"


def test_settings_parse_a_comma_separated_origin_list() -> None:
    settings = ApiSettings.from_environment(
        {"SIH26141_API_CORS_ORIGINS": "https://a.example, https://b.example"}
    )
    assert settings.cors_origins == ("https://a.example", "https://b.example")







def test_the_artifact_reader_returns_none_when_the_file_is_missing(monkeypatch) -> None:
    import backend.api.services.calibration_service as calibration_service

    calibration_service.load_reference_artifact.cache_clear()
    monkeypatch.setattr(
        calibration_service, "REFERENCE_ARTIFACT", pathlib.Path("does-not-exist.json")
    )
    assert calibration_service.load_reference_artifact() is None
    calibration_service.load_reference_artifact.cache_clear()


def test_reference_calibration_degrades_without_the_artifact(
    client, monkeypatch
) -> None:
    import backend.api.services.calibration_service as calibration_service

    monkeypatch.setattr(calibration_service, "load_reference_artifact", lambda: None)
    body = client.get("/api/v1/calibration/reference").json()

    assert body["recorded_operating_point"] is None
    assert body["provenance"]["available"] is False
    assert body["methodology"]
    assert body["security_assessment"]["formal_proof_present"] is False


def test_the_allowed_statement_example_is_absent_without_the_artifact(
    client, monkeypatch
) -> None:
    import backend.api.services.security_service as security_service

    monkeypatch.setattr(security_service, "load_reference_artifact", lambda: None)
    body = client.post("/api/v1/security/analyze", json={"statements": []}).json()


    assert body["allowed_statement_example"] is None


def test_the_allowed_statement_example_is_absent_when_the_attack_row_is_missing(
    client, monkeypatch
) -> None:
    import backend.api.services.security_service as security_service

    monkeypatch.setattr(
        security_service,
        "load_reference_artifact",
        lambda: {"operating_point": {"state_count": 500}, "attack_evaluation": {"by_attack_type": {}}},
    )
    body = client.post("/api/v1/security/analyze", json={"statements": []}).json()
    assert body["allowed_statement_example"] is None







def test_application_version_is_none_without_pyproject(monkeypatch, tmp_path) -> None:
    import backend.api.version as version

    monkeypatch.setattr(version, "_REPO_ROOT", tmp_path)
    assert version._pyproject_version() is None


def test_application_version_is_none_for_a_malformed_pyproject(
    monkeypatch, tmp_path
) -> None:
    import backend.api.version as version

    (tmp_path / "pyproject.toml").write_text("this is not toml [[[", encoding="utf-8")
    monkeypatch.setattr(version, "_REPO_ROOT", tmp_path)
    assert version._pyproject_version() is None


def test_application_version_falls_back_to_the_pyproject_declaration() -> None:
    import backend.api.version as version


    assert version._distribution_version("sih26141") is None
    assert version.application_version() == "0.1.0"
