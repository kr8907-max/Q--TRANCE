"""The security path's settings dependency, and what it still controls.

``settings`` used to be threaded through all four security endpoints and all four
security-service functions even though nothing read it. Security analysis is
derived from ``backend.security``, which has no API-configuration dependency at
all, so the parameter was redundant plumbing.

One endpoint is different: ``POST /security/analyze`` validates its body through
``configured_body``, which resolves the application's settings itself to apply
``max_statements_per_request``. That dependency must survive, so the guards here
assert the precise shape -- no settings *parameter*, but the configured-body
dependency intact -- rather than "no settings anywhere".
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.services import security_service

from .conftest import configured_client

SECURITY_MODULES = (
    pathlib.Path("backend/api/routes/security.py"),
    pathlib.Path("backend/api/services/security_service.py"),
)

SERVICE_FUNCTIONS = (
    "assumptions_view",
    "observability_view",
    "composition_view",
    "analyze_view",
)

READ_ROUTES = (
    "GET /security/assumptions",
    "GET /security/observability",
    "GET /security/composition",
)

ALL_ROUTES = READ_ROUTES + ("POST /security/analyze",)


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


def _security_routes() -> dict:
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return {
        f"{sorted(route.methods)[0]} {route.path}": route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.security"
    }







@pytest.mark.parametrize("name", ALL_ROUTES)
def test_no_security_route_declares_a_settings_parameter(name: str) -> None:
    parameters = list(inspect.signature(_security_routes()[name].endpoint).parameters)
    assert "settings" not in parameters, f"{name}: {parameters}"


@pytest.mark.parametrize("name", READ_ROUTES)
def test_a_security_read_endpoint_does_not_resolve_the_settings_provider(name: str) -> None:
    """The read-only security endpoints have nothing to configure."""
    assert get_settings not in _dependency_calls(_security_routes()[name])


def test_the_analyze_endpoint_still_resolves_settings_for_the_configured_body() -> None:
    """Removing the parameter must not remove the configured statement bound."""
    route = _security_routes()["POST /security/analyze"]
    assert get_settings in _dependency_calls(route), (
        "POST /security/analyze no longer resolves the settings provider, so the "
        "configured statement limit would not be applied"
    )


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the checks above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


@pytest.mark.parametrize("name", SERVICE_FUNCTIONS)
def test_a_security_service_function_takes_no_settings_argument(name: str) -> None:
    parameters = list(inspect.signature(getattr(security_service, name)).parameters)
    assert "settings" not in parameters, f"{name}: {parameters}"


def test_the_security_service_no_longer_imports_settings() -> None:
    tree = ast.parse(SECURITY_MODULES[1].read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "backend.api.config" not in modules
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    assert "ApiSettings" not in names


def test_no_security_module_mentions_settings_at_all() -> None:
    """Neither security module may reference the name, in any form."""
    offenders = []
    for path in SECURITY_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.arg):
                name = node.arg
            elif isinstance(node, ast.keyword):
                name = node.arg
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "settings" in node.value:
                    offenders.append(f"{path}: string literal mentions settings")
            if name == "settings":
                offenders.append(f"{path}:{getattr(node, 'lineno', '?')} references settings")
    assert offenders == [], offenders







def test_a_lowered_statement_limit_is_still_enforced() -> None:
    strict = configured_client(max_statements_per_request=2)
    assert strict.post(
        "/api/v1/security/analyze", json={"statements": ["a", "b"]}
    ).status_code == 200
    assert strict.post(
        "/api/v1/security/analyze", json={"statements": ["a", "b", "c"]}
    ).status_code == 422


def test_the_published_security_paths_are_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    )
    spec = client.get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path.startswith("/api/v1/security")
    }
    assert published == {
        "/api/v1/security/assumptions": ["get"],
        "/api/v1/security/observability": ["get"],
        "/api/v1/security/composition": ["get"],
        "/api/v1/security/analyze": ["post"],
    }
