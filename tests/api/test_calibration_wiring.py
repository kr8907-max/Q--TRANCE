"""The calibration path's settings dependency, and what it still controls.

``settings`` used to be threaded through the calibration routes and the
calibration service even though nothing read it. Calibration is bounded by the
request schema instead: ``POST /calibration/run`` validates its body through
``configured_body``, which resolves the application's settings itself. The route
parameter was redundant plumbing, not the mechanism.

These tests pin the cleaned-up wiring -- and, just as importantly, that the
configured limits still reach calibration through ``configured_body``.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.services import calibration_service

from .conftest import configured_client

CALIBRATION_MODULES = (
    pathlib.Path("backend/api/routes/calibration.py"),
    pathlib.Path("backend/api/services/calibration_service.py"),
)

VALID = {"state_count": 20, "session_count": 2, "seed_start": 0}


def _dependency_calls(route) -> set:
    """Every callable FastAPI resolves while serving ``route``."""
    calls, stack = set(), [route.dependant]
    while stack:
        dependant = stack.pop()
        if dependant.call is not None:
            calls.add(dependant.call)
        stack.extend(dependant.dependencies)
    return calls


def _iter_api_routes(container):
    """Every APIRoute reachable from ``container``, through included routers."""
    for route in getattr(container, "routes", []):
        if hasattr(route, "dependant") and hasattr(route, "endpoint"):
            yield route
        elif hasattr(route, "original_router"):
            yield from _iter_api_routes(route.original_router)
        elif hasattr(route, "routes"):
            yield from _iter_api_routes(route)


def _calibration_routes():
    """The calibration endpoints as wired into a real application."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return {
        f"{sorted(route.methods)[0]} {route.path}": route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.calibration"
    }







def test_the_calibration_read_endpoints_do_not_resolve_the_settings_provider() -> None:
    """The read-only calibration endpoints have nothing to configure."""
    routes = _calibration_routes()
    assert len(routes) == 3, f"expected 3 calibration routes, found {sorted(routes)}"

    offenders = [
        name
        for name, route in routes.items()
        if name != "POST /calibration/run" and get_settings in _dependency_calls(route)
    ]
    assert offenders == [], f"calibration read routes still depend on settings: {offenders}"


def test_the_calibration_run_endpoint_still_resolves_the_settings_provider() -> None:
    """Removing the redundant parameter must not remove the configured limits.

    ``POST /calibration/run`` validates its body through ``configured_body``,
    which resolves the application's settings itself. That dependency is the
    mechanism that applies ``max_calibration_sessions`` and ``max_shot_count``,
    so it must survive this cleanup.
    """
    route = _calibration_routes()["POST /calibration/run"]
    assert get_settings in _dependency_calls(route), (
        "POST /calibration/run no longer resolves the settings provider, so the "
        "configured calibration limits would not be applied"
    )


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the check above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


def test_the_calibration_service_takes_no_settings_argument() -> None:
    assert list(inspect.signature(calibration_service.run_calibration).parameters) == [
        "store",
        "request",
    ]
    assert list(inspect.signature(calibration_service.reference_description).parameters) == []


def test_the_calibration_service_no_longer_imports_settings() -> None:
    tree = ast.parse(CALIBRATION_MODULES[1].read_text(encoding="utf-8"))
    modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert "backend.api.config" not in modules
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    assert "ApiSettings" not in names


def test_no_calibration_module_mentions_settings_at_all() -> None:
    """Neither calibration module may reference the name, in any form."""
    offenders = []
    for path in CALIBRATION_MODULES:
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







def test_a_lowered_session_limit_is_still_enforced() -> None:
    """The limit is configuration, and it still refuses above its value."""
    strict = configured_client(max_calibration_sessions=2)
    refused = strict.post(
        "/api/v1/calibration/run", json={**VALID, "session_count": 3}
    )
    assert refused.status_code == 422


def test_a_lowered_shot_limit_is_still_enforced() -> None:
    strict = configured_client(max_shot_count=4)
    refused = strict.post("/api/v1/calibration/run", json={**VALID, "shot_count": 4096})
    assert refused.status_code == 422


def test_the_published_calibration_paths_are_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    )
    spec = client.get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path.startswith("/api/v1/calibration")
    }
    assert published == {
        "/api/v1/calibration/run": ["post"],
        "/api/v1/calibration/reference": ["get"],
        "/api/v1/calibration/{calibration_id}": ["get"],
    }
