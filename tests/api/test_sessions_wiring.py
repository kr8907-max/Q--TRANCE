"""Session creation's settings wiring, versus the lifecycle routes that need it.

``POST /sessions`` declared a ``settings`` parameter and never read it. Creation
does not consume configuration: the message bound is applied by
``configured_body``, which resolves the application's settings itself, and the
session material comes from the protocol constructor.

The other three session routes are different: ``get_session``, ``sign_session``
and ``expire_session`` genuinely consume ``session_ttl_seconds``, so their
settings dependency is legitimate and must survive. These guards assert that
distinction rather than a blanket rule.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.services import session_service

SESSIONS_MODULE = pathlib.Path("backend/api/routes/sessions.py")
SERVICE_MODULE = pathlib.Path("backend/api/services/session_service.py")

CREATE = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}

LIFECYCLE_ROUTES = (
    "GET /sessions/{session_id}",
    "POST /sessions/{session_id}/sign",
    "POST /sessions/{session_id}/expire",
)


def _dependency_calls(route) -> set:
    calls, stack = set(), [route.dependant]
    while stack:
        d = stack.pop()
        if d.call is not None:
            calls.add(d.call)
        stack.extend(d.dependencies)
    return calls


def _iter_api_routes(container):
    for route in getattr(container, "routes", []):
        if hasattr(route, "dependant") and hasattr(route, "endpoint"):
            yield route
        elif hasattr(route, "original_router"):
            yield from _iter_api_routes(route.original_router)
        elif hasattr(route, "routes"):
            yield from _iter_api_routes(route)


def _session_routes() -> dict:
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return {
        f"{sorted(route.methods)[0]} {route.path}": route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.sessions"
    }


def _client(**settings_kwargs):
    from fastapi.testclient import TestClient

    return TestClient(
        create_app(
            settings=ApiSettings(environment="test", **settings_kwargs), store=ApiStore()
        ),
        raise_server_exceptions=False,
    )







def test_the_create_session_route_declares_no_settings_parameter() -> None:
    parameters = list(inspect.signature(_session_routes()["POST /sessions"].endpoint).parameters)
    assert parameters == ["request", "store"], parameters


def test_the_create_session_route_still_resolves_settings_for_the_configured_body() -> None:
    """The message bound must survive the parameter removal.

    ``configured_body`` resolves the settings provider itself; that dependency is
    the mechanism that applies ``max_message_chars`` to the creation body.
    """
    assert get_settings in _dependency_calls(_session_routes()["POST /sessions"]), (
        "POST /sessions no longer resolves the settings provider, so the configured "
        "message limit would not be applied"
    )







@pytest.mark.parametrize("name", LIFECYCLE_ROUTES)
def test_a_lifecycle_route_still_declares_a_settings_parameter(name: str) -> None:
    parameters = list(inspect.signature(_session_routes()[name].endpoint).parameters)
    assert "settings" in parameters, f"{name}: {parameters}"


@pytest.mark.parametrize("name", LIFECYCLE_ROUTES)
def test_a_lifecycle_route_still_resolves_the_settings_provider(name: str) -> None:
    assert get_settings in _dependency_calls(_session_routes()[name]), name


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the checks above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


def test_the_signature_guard_is_not_trivially_true() -> None:
    """Non-vacuity for the signature guard.

    ``test_the_create_session_route_declares_no_settings_parameter`` asserts the
    *absence* of a parameter. Applied to a route that genuinely takes settings the
    same predicate must fire, which is what shows the assertion is meaningful
    rather than always-true. (A live reintroduction of the dependency on
    ``create_session`` was also verified out-of-band to fail that guard.)
    """
    parameters = list(
        inspect.signature(_session_routes()["GET /sessions/{session_id}"].endpoint).parameters
    )
    assert "settings" in parameters, parameters







def test_the_session_service_create_takes_no_settings_argument() -> None:
    parameters = list(inspect.signature(session_service.create).parameters)
    assert parameters == ["store", "request"], parameters


def test_the_session_service_still_consumes_the_ttl_setting_where_it_should() -> None:
    """``sign`` and ``expire`` read ``session_ttl_seconds``; that must not change."""
    tree = ast.parse(SERVICE_MODULE.read_text(encoding="utf-8"))
    readers = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            readers[node.name] = [
                n.lineno
                for n in ast.walk(node)
                if isinstance(n, ast.Attribute) and n.attr == "session_ttl_seconds"
            ]
    assert readers["create"] == []
    assert readers["sign"], "sign no longer reads session_ttl_seconds"
    assert readers["expire"], "expire no longer reads session_ttl_seconds"







def test_a_lowered_message_limit_is_still_enforced() -> None:
    strict = _client(max_message_chars=16)
    assert strict.post("/api/v1/sessions", json={**CREATE, "message": "x" * 16}).status_code == 201
    assert strict.post("/api/v1/sessions", json={**CREATE, "message": "x" * 17}).status_code == 422


def test_the_ttl_setting_still_expires_a_session() -> None:
    """The legitimate setting still changes runtime behaviour."""
    ttl = _client(session_ttl_seconds=0)
    session = ttl.post("/api/v1/sessions", json=CREATE).json()
    body = ttl.get(f"/api/v1/sessions/{session['session_id']}").json()
    assert body["lifecycle"] == "EXPIRED"
    assert body["history"] == ["CREATED", "EXPIRED"]


def test_the_published_session_paths_are_unchanged() -> None:
    spec = _client().get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path.startswith("/api/v1/sessions")
    }
    assert published == {
        "/api/v1/sessions": ["get", "post"],
        "/api/v1/sessions/{session_id}": ["get"],
        "/api/v1/sessions/{session_id}/sign": ["post"],
        "/api/v1/sessions/{session_id}/expire": ["post"],
    }
