"""The configured request limits, proven to be the ones actually enforced.

``test_bounds.py`` pins the *default* bounds at their edges. This module answers
a different question: when an application is built with a different
:class:`~backend.api.config.ApiSettings`, is that configuration the limit a
request meets?

Four limits are covered, each on the cheapest endpoint that shares its schema
field:

========================  =========================  =========================
setting                   field                      endpoint
========================  =========================  =========================
``max_message_chars``     message                    ``POST /api/v1/sessions``
``max_statements_per_request``  statements           ``POST /api/v1/security/analyze``
``max_shot_count``        shot_count                 ``POST /api/v1/simulations``
``max_calibration_sessions``    session_count         ``POST /api/v1/calibration/run``
========================  =========================  =========================

For each limit the same six properties are checked:

A. the default accepts a value at its boundary;
B. the default refuses a value above it;
C. a **lower** configured limit refuses a value the default would accept;
D. a **higher** configured limit accepts a value the default would refuse;
E. the override holds through the real FastAPI request path, not only when the
   schema is validated by hand;
F. no value from one application reaches another, and a request cannot change
   what a later request is validated against.

Property D is the one that separates a real override from a re-declared
constant: a limit that is merely *also* configurable in one direction still
fails it.
"""

from __future__ import annotations

import pytest

from backend.api import ApiSettings
from backend.api.schemas.security import AnalyzeRequest
from backend.api.schemas.session import SessionCreateRequest
from backend.api.schemas.simulation import SimulationRequest

from .conftest import configured_client

SESSION = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 4,
}


def _create(client, **overrides) -> int:
    return client.post("/api/v1/sessions", json={**SESSION, **overrides}).status_code


def _analyze(client, count: int) -> int:
    return client.post(
        "/api/v1/security/analyze", json={"statements": ["an honest sentence"] * count}
    ).status_code


def _simulate(client, shot_count: int) -> int:
    return client.post(
        "/api/v1/simulations", json={"state_count": 1, "shot_count": shot_count}
    ).status_code


def _calibrate(client, session_count: int) -> int:
    return client.post(
        "/api/v1/calibration/run",
        json={"state_count": 4, "session_count": session_count},
    ).status_code







def test_a_message_at_the_default_bound_is_accepted(client) -> None:
    assert _create(client, message="x" * 4096) == 201


def test_a_message_over_the_default_bound_is_refused(client) -> None:
    assert _create(client, message="x" * 4097) == 422


def test_a_lower_message_limit_is_enforced() -> None:
    lowered = configured_client(max_message_chars=16)
    assert _create(lowered, message="x" * 16) == 201
    assert _create(lowered, message="x" * 17) == 422


def test_a_higher_message_limit_is_enforced() -> None:
    raised = configured_client(max_message_chars=9000)
    assert _create(raised, message="x" * 9000) == 201
    assert _create(raised, message="x" * 9001) == 422


def test_the_message_limit_is_applied_to_the_verification_endpoint() -> None:
    lowered = configured_client(max_message_chars=8)
    body = {
        "message": "x" * 8,
        "transcript": {},
        "verifier_context": {"verifier_id": "bob"},
    }
    assert lowered.post("/api/v1/verify", json=body).status_code == 200
    body["message"] = "x" * 9
    assert lowered.post("/api/v1/verify", json=body).status_code == 422


def test_the_message_limit_is_applied_to_the_detection_endpoint() -> None:
    lowered = configured_client(max_message_chars=8)
    assert lowered.post("/api/v1/detect", json={"message": "x" * 8}).status_code == 200
    assert lowered.post("/api/v1/detect", json={"message": "x" * 9}).status_code == 422







def test_the_default_statement_limit_accepts_at_its_boundary(client) -> None:
    response = client.post(
        "/api/v1/security/analyze", json={"statements": ["an honest sentence"] * 50}
    )
    assert response.status_code == 200
    assert len(response.json()["checks"]) == 50


def test_the_default_statement_limit_refuses_above_its_boundary(client) -> None:
    assert _analyze(client, 51) == 422


def test_a_lower_statement_limit_is_enforced() -> None:
    lowered = configured_client(max_statements_per_request=3)
    assert _analyze(lowered, 3) == 200
    assert _analyze(lowered, 4) == 422


def test_a_higher_statement_limit_is_enforced() -> None:
    raised = configured_client(max_statements_per_request=120)
    response = raised.post(
        "/api/v1/security/analyze", json={"statements": ["an honest sentence"] * 120}
    )
    assert response.status_code == 200
    assert len(response.json()["checks"]) == 120
    assert _analyze(raised, 121) == 422







def test_a_shot_count_at_the_default_bound_is_accepted(client) -> None:
    assert _simulate(client, 1024) == 200


def test_a_shot_count_over_the_default_bound_is_refused(client) -> None:
    assert _simulate(client, 1025) == 422


def test_a_lower_shot_limit_is_enforced() -> None:
    lowered = configured_client(max_shot_count=2)
    assert _simulate(lowered, 2) == 200
    assert _simulate(lowered, 3) == 422


def test_a_higher_shot_limit_is_enforced() -> None:
    raised = configured_client(max_shot_count=4096)
    assert _simulate(raised, 4096) == 200
    assert _simulate(raised, 4097) == 422


def test_the_lower_shot_limit_also_applies_to_calibration() -> None:
    lowered = configured_client(max_shot_count=2)
    body = {"state_count": 4, "session_count": 1, "shot_count": 2}
    assert lowered.post("/api/v1/calibration/run", json=body).status_code == 201
    body["shot_count"] = 3
    assert lowered.post("/api/v1/calibration/run", json=body).status_code == 422







def test_a_session_count_at_the_default_bound_is_accepted(client) -> None:
    assert _calibrate(client, 64) == 201


def test_a_session_count_over_the_default_bound_is_refused(client) -> None:
    assert _calibrate(client, 65) == 422


def test_a_lower_calibration_session_limit_is_enforced() -> None:
    lowered = configured_client(max_calibration_sessions=2)
    assert _calibrate(lowered, 2) == 201
    assert _calibrate(lowered, 3) == 422


def test_a_higher_calibration_session_limit_is_enforced() -> None:
    raised = configured_client(max_calibration_sessions=80)
    assert _calibrate(raised, 80) == 201
    assert _calibrate(raised, 81) == 422







def test_a_lowered_limit_is_reported_by_the_endpoint_itself() -> None:
    """The refusal comes from the configured pass, not from a route-local check.

    A route that special-cased the limit would have to duplicate the message the
    schema produces. Asserting on the schema's own wording shows the boundary is
    enforced once, where every endpoint sharing the field gets it.
    """
    lowered = configured_client(max_message_chars=16)
    response = lowered.post(
        "/api/v1/sessions", json={**SESSION, "message": "x" * 17}
    )
    assert response.status_code == 422
    rendered = response.text
    assert "max_message_chars" in rendered
    assert "17" in rendered and "16" in rendered


def test_the_error_envelope_is_unchanged_by_a_configured_refusal() -> None:
    """A configured override must not invent a new error shape."""
    lowered = configured_client(max_message_chars=16)
    response = lowered.post("/api/v1/sessions", json={**SESSION, "message": "x" * 17})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert body["error"]["request_id"]







@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sessions",
        "/api/v1/verify",
        "/api/v1/simulations",
        "/api/v1/detect",
        "/api/v1/calibration/run",
        "/api/v1/security/analyze",
    ],
)
def test_an_absent_body_is_a_422_on_every_configured_route(client, path: str) -> None:
    """A missing payload must stay a client error.

    The configured pass wraps the body in a dependency. If that dependency
    declared the body with a default, an absent or null payload would resolve to
    ``None`` and fail inside the dependency, turning a malformed request into a
    500. This pins the framework's own 422 for it.
    """
    assert client.post(path).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sessions",
        "/api/v1/verify",
        "/api/v1/simulations",
        "/api/v1/detect",
        "/api/v1/calibration/run",
        "/api/v1/security/analyze",
    ],
)
def test_a_null_body_is_a_422_on_every_configured_route(client, path: str) -> None:
    assert client.post(path, json=None).status_code == 422


def test_a_malformed_json_body_is_a_422(client) -> None:
    response = client.post(
        "/api/v1/sessions",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


def test_an_unknown_field_is_still_refused_under_a_configured_limit() -> None:
    """``extra="forbid"`` must survive the configured pass.

    The second validation runs on the dumped payload, so an unknown field that
    the first pass admitted would have to be refused again here. It is refused in
    the first pass, and this checks the combined behaviour a caller sees.
    """
    client = configured_client(max_message_chars=16)
    response = client.post(
        "/api/v1/sessions", json={**SESSION, "message": "x", "unexpected": 1}
    )
    assert response.status_code == 422







def test_two_applications_keep_their_own_limits() -> None:
    strict = configured_client(max_message_chars=8)
    relaxed = configured_client(max_message_chars=9000)

    assert _create(strict, message="x" * 9) == 422
    assert _create(relaxed, message="x" * 9) == 201

    assert _create(strict, message="x" * 9) == 422
    assert _create(relaxed, message="x" * 9001) == 422


def test_every_limit_is_isolated_between_two_applications() -> None:
    """All four limits, both directions, in one process."""
    strict = configured_client(
        max_message_chars=8,
        max_statements_per_request=1,
        max_shot_count=1,
        max_calibration_sessions=1,
    )
    relaxed = configured_client(
        max_message_chars=9000,
        max_statements_per_request=100,
        max_shot_count=4096,
        max_calibration_sessions=80,
    )


    assert _create(strict, message="x" * 9) == 422
    assert _create(relaxed, message="x" * 9) == 201

    assert _analyze(strict, 2) == 422
    assert _analyze(relaxed, 2) == 200

    assert _simulate(strict, 2) == 422
    assert _simulate(relaxed, 2) == 200

    assert _calibrate(strict, 2) == 422
    assert _calibrate(relaxed, 2) == 201


    assert _create(strict, message="x" * 9) == 422
    assert _analyze(strict, 2) == 422
    assert _simulate(strict, 2) == 422
    assert _calibrate(strict, 2) == 422


def test_a_request_does_not_change_the_limit_a_later_request_meets() -> None:
    client = configured_client(max_message_chars=16)
    for _ in range(3):
        assert _create(client, message="x" * 16) == 201
        assert _create(client, message="x" * 17) == 422







@pytest.mark.parametrize(
    "field,ceiling",
    [
        ("max_message_chars", 1_048_576),
        ("max_statements_per_request", 4_096),
        ("max_shot_count", 65_536),
        ("max_calibration_sessions", 4_096),
    ],
)
def test_a_limit_above_its_static_ceiling_is_refused(field: str, ceiling: int) -> None:
    """A setting the schemas could not honour is refused where it is set.

    Each request field keeps a static maximum so OpenAPI describes the type. If a
    setting were allowed above that maximum, the static bound would silently
    become the real limit. Refusing it at construction makes that a startup error
    instead of a bound that quietly ignores its configuration.
    """
    with pytest.raises(ValueError):
        ApiSettings(**{field: ceiling + 1})


@pytest.mark.parametrize(
    "field",
    [
        "max_message_chars",
        "max_statements_per_request",
        "max_shot_count",
        "max_calibration_sessions",
    ],
)
def test_a_non_positive_limit_is_refused(field: str) -> None:
    for value in (0, -1):
        with pytest.raises(ValueError):
            ApiSettings(**{field: value})


def test_each_limit_may_be_set_to_its_ceiling() -> None:
    settings = ApiSettings(
        max_message_chars=1_048_576,
        max_statements_per_request=4_096,
        max_shot_count=65_536,
        max_calibration_sessions=4_096,
    )
    assert settings.max_message_chars == 1_048_576







def test_a_schema_built_directly_applies_no_configured_limit() -> None:
    """A model constructed with no settings enforces structure, not configuration.

    This is the documented behaviour of ``configured_limit``: with nothing in the
    validation context the field is left to the schema's static bound. It keeps
    the request models usable on their own -- and it is exactly the reason the
    API layer performs the configured pass, rather than relying on construction.
    """
    instance = SessionCreateRequest(**{**SESSION, "message": "x" * 9000})
    assert len(instance.message) == 9000


def test_a_schema_validated_with_settings_applies_the_configured_limit() -> None:
    """The same model, given settings, does enforce the limit."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SessionCreateRequest.model_validate(
            {**SESSION, "message": "x" * 9000},
            context={"settings": ApiSettings(max_message_chars=16)},
        )

    accepted = SessionCreateRequest.model_validate(
        {**SESSION, "message": "x" * 16},
        context={"settings": ApiSettings(max_message_chars=16)},
    )
    assert len(accepted.message) == 16


def test_every_configured_field_enforces_its_limit_at_the_schema_level() -> None:
    """The other three fields also respond to a settings-bearing validation.

    ``/sessions`` covers ``max_message_chars`` above; the remaining three fields
    live on their own schemas, so they are validated here directly to show the
    limit is a property of the model rather than of one route.
    """
    from pydantic import ValidationError

    strict = ApiSettings(
        max_statements_per_request=1,
        max_shot_count=1,
        max_calibration_sessions=1,
    )

    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(
            {"statements": ["a", "b"]}, context={"settings": strict}
        )
    assert (
        AnalyzeRequest.model_validate({"statements": ["a"]}, context={"settings": strict})
        .statements
        == ["a"]
    )

    with pytest.raises(ValidationError):
        SimulationRequest.model_validate({"shot_count": 2}, context={"settings": strict})
    assert (
        SimulationRequest.model_validate({"shot_count": 1}, context={"settings": strict})
        .shot_count
        == 1
    )

    from backend.api.schemas.calibration import CalibrationRunRequest

    with pytest.raises(ValidationError):
        CalibrationRunRequest.model_validate(
            {"session_count": 2}, context={"settings": strict}
        )
    assert (
        CalibrationRunRequest.model_validate(
            {"session_count": 1}, context={"settings": strict}
        ).session_count
        == 1
    )
