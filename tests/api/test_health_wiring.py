"""Health and readiness wiring: the one that configures, and the one that does not.

``/health`` legitimately consumes ``settings.environment`` -- it reports which
environment the process is running in. ``/ready`` declared the same dependency and
never read it: readiness is decided by component importability and a store probe,
neither of which is configuration.

These guards assert that distinction explicitly, rather than a blanket "the health
module contains no settings" rule, which would either be false (``/health``) or
would push the environment field out of the response.
"""

from __future__ import annotations

import inspect

import pytest

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.routes.health import REQUIRED_COMPONENTS

HEALTH_ROUTES = ("GET /health", "GET /ready", "GET /version")


class _BrokenStore(ApiStore):
    """A store whose readiness probe fails."""

    def counts(self):
        raise RuntimeError("store unavailable for this test")


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


def _operational_routes() -> dict:
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return {
        f"{sorted(route.methods)[0]} {route.path}": route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.health"
    }


def _client(store=None, *, environment="test"):
    from fastapi.testclient import TestClient

    return TestClient(
        create_app(
            settings=ApiSettings(environment=environment),
            store=store if store is not None else ApiStore(),
        ),
        raise_server_exceptions=False,
    )







def test_the_ready_endpoint_does_not_resolve_the_settings_provider() -> None:
    """Readiness depends on imports and the store, not on configuration."""
    assert get_settings not in _dependency_calls(_operational_routes()["GET /ready"])


def test_the_health_endpoint_still_resolves_the_settings_provider() -> None:
    """``/health`` reports the configured environment, so it must keep settings."""
    assert get_settings in _dependency_calls(_operational_routes()["GET /health"]), (
        "/health no longer resolves the settings provider, so it could not report "
        "the configured environment"
    )


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the checks above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


def test_the_ready_endpoint_declares_no_settings_parameter() -> None:
    parameters = list(inspect.signature(_operational_routes()["GET /ready"].endpoint).parameters)
    assert parameters == ["store"], parameters


def test_the_health_endpoint_declares_a_settings_parameter() -> None:
    parameters = list(
        inspect.signature(_operational_routes()["GET /health"].endpoint).parameters
    )
    assert parameters == ["settings", "store"], parameters


def test_the_version_endpoint_takes_no_dependencies() -> None:
    parameters = list(
        inspect.signature(_operational_routes()["GET /version"].endpoint).parameters
    )
    assert parameters == [], parameters







@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_health_still_reports_the_configured_environment(environment: str) -> None:
    response = _client(environment=environment).get("/health")
    assert response.status_code == 200
    assert response.json()["environment"] == environment


def test_ready_still_reports_every_required_component() -> None:
    body = _client().get("/ready").json()
    assert body["ready"] is True
    names = [check["name"] for check in body["checks"]]
    assert names == [name for name, _ in REQUIRED_COMPONENTS] + ["store"]
    assert all(check["ok"] for check in body["checks"])


def test_the_ready_failure_path_still_reports_not_ready() -> None:
    """A store whose probe raises makes readiness false, not an error."""
    response = _client(store=_BrokenStore()).get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    store_check = next(c for c in body["checks"] if c["name"] == "store")
    assert store_check["ok"] is False
    assert "store unavailable" in store_check["detail"]


def test_the_published_operational_paths_are_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    spec = _client().get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path in ("/health", "/ready", "/version")
    }
    assert published == {
        "/health": ["get"],
        "/ready": ["get"],
        "/version": ["get"],
    }
