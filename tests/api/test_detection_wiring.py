"""The detection path's settings dependency, and what it still controls.

``settings`` used to be threaded through the detection route and the detection
service even though nothing read it. Detection is bounded by the request schema
instead: ``POST /detect`` validates its body through ``configured_body``, which
resolves the application's settings itself. The route parameter was redundant
plumbing, not the mechanism.

That distinction matters here. The route *does* still resolve the settings
provider -- through ``configured_body``, which applies ``max_message_chars`` --
so a guard that simply asserted "no settings anywhere" would silently break the
configured limit. These tests assert the precise shape: no settings *parameter*,
but the configured-body dependency intact.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.services import detection_service

from .conftest import configured_client

DETECTION_MODULES = (
    pathlib.Path("backend/api/routes/detection.py"),
    pathlib.Path("backend/api/services/detection_service.py"),
)


def _observable(**overrides) -> dict:
    payload = {
        "session_id": "s-1",
        "nonce": "n-1",
        "protocol_version": "RQDS-TP-1.0",
        "signer_id": "alice",
        "verifier_id": "bob",
        "authorized_signers": ["alice"],
        "authorized_verifiers": ["bob"],
        "states": [
            {
                "index": i,
                "basis": "Z",
                "expected_bit": 0,
                "probability_expected": 1.0,
                "matched": True,
            }
            for i in range(4)
        ],
        "declared_state_count": 4,
        "measurement_mode": "sampled",
        "basis_counts": {"Z": 4},
        "verification": {"available": True, "accepted": True},
    }
    payload.update(overrides)
    return payload


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


def _detect_route():
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    routes = [
        route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.detection"
    ]
    assert len(routes) == 1, f"expected 1 detection route, found {len(routes)}"
    return routes[0]







def test_the_detect_route_declares_no_settings_parameter() -> None:
    parameters = list(inspect.signature(_detect_route().endpoint).parameters)
    assert parameters == ["request", "store"], parameters


def test_the_detect_route_still_resolves_settings_for_the_configured_body() -> None:
    """Removing the parameter must not remove the configured message limit.

    ``configured_body`` resolves the settings provider itself; that dependency is
    the mechanism that applies ``max_message_chars`` and must survive.
    """
    assert get_settings in _dependency_calls(_detect_route()), (
        "POST /detect no longer resolves the settings provider, so the configured "
        "message limit would not be applied"
    )


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the check above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


def test_the_detection_service_takes_no_settings_argument() -> None:
    parameters = list(inspect.signature(detection_service.detect_request).parameters)
    assert parameters == ["store", "request"], parameters


def test_the_detection_service_no_longer_imports_settings() -> None:
    tree = ast.parse(DETECTION_MODULES[1].read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "backend.api.config" not in modules
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    assert "ApiSettings" not in names


def test_no_detection_module_mentions_settings_at_all() -> None:
    """Neither detection module may reference the name, in any form."""
    offenders = []
    for path in DETECTION_MODULES:
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







def test_a_lowered_message_limit_is_still_enforced() -> None:
    strict = configured_client(max_message_chars=8)
    assert strict.post("/api/v1/detect", json=_observable(message="x" * 8)).status_code == 200
    assert strict.post("/api/v1/detect", json=_observable(message="x" * 9)).status_code == 422


def test_the_published_detect_path_is_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    )
    spec = client.get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path.endswith("/detect")
    }
    assert published == {"/api/v1/detect": ["post"]}
