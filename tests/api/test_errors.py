"""Error envelope, correlation identifiers and security controls."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api import ApiSettings, ApiStore, create_app
from backend.api.context import REQUEST_ID_HEADER


def test_not_found_uses_the_envelope(client) -> None:
    response = client.get("/api/v1/sessions/nope")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]
    assert error["request_id"]
    assert error["details"]["resource"] == "session"


def test_validation_failure_uses_the_envelope(client) -> None:
    response = client.post("/api/v1/sessions", json={"message": ""})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "UNPROCESSABLE_ENTITY"
    assert error["details"]["errors"]

    for item in error["details"]["errors"]:
        assert isinstance(item["loc"], list)
        assert isinstance(item["msg"], str)


def test_a_wrong_method_is_reported_consistently(client) -> None:
    response = client.delete("/api/v1/sessions")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_an_unhandled_exception_becomes_a_generic_500(lenient_client, monkeypatch) -> None:
    import backend.api.services.session_service as session_service

    def _explode(*args, **kwargs):
        raise RuntimeError("boom: a detail that must not reach the client")

    monkeypatch.setattr(session_service, "create", _explode)
    response = lenient_client.post(
        "/api/v1/sessions",
        json={"message": "m", "signer_id": "a", "verifier_id": "b"},
    )
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"

    assert "boom" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text







def test_every_response_carries_a_request_id(client) -> None:
    for path in ("/health", "/api/v1/sessions", "/api/v1/security/composition"):
        response = client.get(path)
        assert response.headers.get(REQUEST_ID_HEADER), path


def test_a_safe_caller_request_id_is_echoed(client) -> None:
    response = client.get("/health", headers={REQUEST_ID_HEADER: "caller-123"})
    assert response.headers[REQUEST_ID_HEADER] == "caller-123"


def test_an_unsafe_caller_request_id_is_replaced(client) -> None:
    response = client.get(
        "/health", headers={REQUEST_ID_HEADER: "bad id with spaces and \n newline"}
    )
    value = response.headers[REQUEST_ID_HEADER]
    assert value != "bad id with spaces and \n newline"
    assert " " not in value and "\n" not in value


def test_error_responses_carry_the_request_id(client) -> None:
    response = client.get("/api/v1/sessions/nope", headers={REQUEST_ID_HEADER: "trace-1"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-1"
    assert response.json()["error"]["request_id"] == "trace-1"


def _explode_creation(monkeypatch) -> None:
    import backend.api.services.session_service as session_service

    def _explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(session_service, "create", _explode)


def test_an_unhandled_error_echoes_the_caller_correlation_id(
    lenient_client, monkeypatch
) -> None:
    """A 500 must still be correlatable.

    The unhandled-exception handler runs above RequestContextMiddleware -- the
    exception escapes it -- so the identifier has to come from the request scope
    rather than the request context. Before that, a 500 carried neither the
    header nor a body identifier while the log line carried both.
    """
    _explode_creation(monkeypatch)
    response = lenient_client.post(
        "/api/v1/sessions",
        json={"message": "m", "signer_id": "a", "verifier_id": "b"},
        headers={REQUEST_ID_HEADER: "trace-500"},
    )

    assert response.status_code == 500
    assert response.headers.get(REQUEST_ID_HEADER) == "trace-500"
    assert response.json()["error"]["request_id"] == "trace-500"


def test_an_unhandled_error_generates_an_id_when_none_was_sent(
    lenient_client, monkeypatch
) -> None:
    _explode_creation(monkeypatch)
    response = lenient_client.post(
        "/api/v1/sessions",
        json={"message": "m", "signer_id": "a", "verifier_id": "b"},
    )

    assert response.status_code == 500
    header = response.headers.get(REQUEST_ID_HEADER)
    assert header
    assert response.json()["error"]["request_id"] == header


def test_the_500_log_line_and_the_response_share_one_id(
    lenient_client, monkeypatch, caplog
) -> None:
    import logging

    _explode_creation(monkeypatch)
    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        response = lenient_client.post(
            "/api/v1/sessions",
            json={"message": "m", "signer_id": "a", "verifier_id": "b"},
            headers={REQUEST_ID_HEADER: "trace-shared"},
        )

    assert response.status_code == 500


    records = _request_records(caplog)
    assert records, "expected an access-log record for the failure"
    assert records[-1].request_id == "trace-shared"
    assert records[-1].outcome == "error"
    assert response.json()["error"]["request_id"] == "trace-shared"







def test_an_oversized_body_is_refused_before_handling() -> None:
    app = create_app(
        settings=ApiSettings(environment="test", max_request_bytes=64),
        store=ApiStore(),
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/security/analyze",
        content=b"x" * 4096,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "PAYLOAD_TOO_LARGE"
    assert error["details"]["limit_bytes"] == 64







def test_cors_allows_a_configured_origin(client) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_does_not_allow_an_unconfigured_origin(client) -> None:
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert response.headers.get("access-control-allow-origin") is None


def test_a_wildcard_origin_must_be_requested_explicitly() -> None:
    import pytest

    with pytest.raises(ValueError, match="wildcard"):
        ApiSettings.from_environment({"SIH26141_API_CORS_ORIGINS": "*"})


def test_a_wildcard_origin_can_be_accepted_deliberately() -> None:
    settings = ApiSettings.from_environment(
        {"SIH26141_API_CORS_ORIGINS": "*", "SIH26141_API_ALLOW_WILDCARD_CORS": "1"}
    )
    assert settings.cors_is_wildcard is True


def test_credentials_are_not_allowed_with_the_default_origins(client) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-credentials") is None






API_LOGGER = "sih26141.api"

SESSION_PAYLOAD = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}


def _request_records(caplog) -> list:
    return [
        record
        for record in caplog.records
        if record.name == API_LOGGER and record.getMessage() == "request"
    ]


def test_the_access_log_records_the_request_shape(client, caplog) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        client.post("/api/v1/sessions", json=SESSION_PAYLOAD)

    records = _request_records(caplog)
    assert records, "expected an access-log record"
    record = records[-1]
    assert record.method == "POST"
    assert record.route == "/sessions"
    assert record.status_code == 201
    assert isinstance(record.duration_ms, float)
    assert record.outcome == "ok"
    assert record.request_id


def test_the_access_log_records_the_session_a_request_is_about(client, caplog) -> None:
    import logging

    session_id = client.post("/api/v1/sessions", json=SESSION_PAYLOAD).json()["session_id"]

    for path in (f"/api/v1/sessions/{session_id}", f"/api/v1/sessions/{session_id}/sign"):
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=API_LOGGER):
            client.get(path) if path.endswith(session_id) else client.post(path)
        records = _request_records(caplog)
        assert records, path
        assert records[-1].session_id == session_id, path


def test_the_access_log_records_a_session_named_in_the_body(client, caplog) -> None:
    """``/verify`` names its session in the body, so the route binds the scope."""
    import logging

    session_id = client.post("/api/v1/sessions", json=SESSION_PAYLOAD).json()["session_id"]
    signed = client.post(f"/api/v1/sessions/{session_id}/sign").json()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        client.post(
            "/api/v1/verify",
            json={
                "message": SESSION_PAYLOAD["message"],
                "transcript": signed["transcript"],
                "verifier_context": {"verifier_id": "bob"},
                "session_id": session_id,
            },
        )
    records = _request_records(caplog)
    assert records, "expected an access-log record"
    assert records[-1].session_id == session_id


def test_the_access_log_omits_the_session_when_none_was_named(client, caplog) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        client.get("/health")
    records = _request_records(caplog)
    assert records
    assert getattr(records[-1], "session_id", None) is None


def test_the_access_log_does_not_carry_message_content(client, caplog) -> None:
    import logging

    marker = "MARKER-DO-NOT-LOG-98765"
    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        client.post(
            "/api/v1/sessions", json={**SESSION_PAYLOAD, "message": f"transfer {marker}"}
        )
    assert caplog.text
    assert marker not in caplog.text


def test_the_access_log_does_not_carry_attack_labels(client, caplog) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        client.post(
            "/api/v1/simulations/evaluation",
            json={
                "state_count": 8,
                "attack": {"attack_type": "channel_tampering", "fraction": 0.5, "seed": 1},
            },
        )
    assert caplog.text

    assert "channel_tampering" not in caplog.text
    assert "is_malicious" not in caplog.text


def test_the_access_log_does_not_carry_a_rejected_request_body(client, caplog) -> None:
    import logging

    marker = "REJECTED-BODY-MARKER-55555"
    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        response = client.post("/api/v1/sessions", json={"message": marker})
    assert response.status_code == 422
    assert caplog.text
    assert marker not in caplog.text


def test_an_unhandled_error_is_logged_without_the_body(
    lenient_client, caplog, monkeypatch
) -> None:
    import logging

    import backend.api.services.session_service as session_service

    marker = "EXPLODING-BODY-MARKER-31337"

    def _explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(session_service, "create", _explode)
    with caplog.at_level(logging.INFO, logger=API_LOGGER):
        response = lenient_client.post(
            "/api/v1/sessions", json={**SESSION_PAYLOAD, "message": marker}
        )
    assert response.status_code == 500
    assert marker not in caplog.text
