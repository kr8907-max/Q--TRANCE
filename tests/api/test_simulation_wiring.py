"""The simulation path's settings dependency, and what it still controls.

``settings`` used to be threaded through both simulation routes and
``simulation_service.run_simulation`` even though nothing read it. Simulation is
bounded by the request schema instead: both routes validate their body through
``configured_body``, which resolves the application's settings itself to apply
``max_shot_count`` and ``max_message_chars``.

So the routes *still* resolve the settings provider -- through
``configured_body`` -- and a blanket "no settings anywhere" guard would silently
break those limits. These guards assert the precise shape: no settings
*parameter*, but the configured-body dependency intact.

The simulation output schema is untouched: the operational route still carries no
ground truth, and the evaluation route still carries the labelled block.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.services import simulation_service

from .conftest import configured_client

SIMULATION_MODULES = (
    pathlib.Path("backend/api/routes/simulations.py"),
    pathlib.Path("backend/api/services/simulation_service.py"),
)

ROUTES = ("POST /simulations", "POST /simulations/evaluation")

BASE = {
    "state_count": 8,
    "shot_count": 1,
    "random_seed": 11,
    "measurement_mode": "sampled",
    "noise": {"noise_type": "depolarizing", "noise_strength": 0.02},
    "attack": {"attack_type": "channel_tampering", "fraction": 0.5, "seed": 3},
}


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


def _simulation_routes() -> dict:
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return {
        f"{sorted(route.methods)[0]} {route.path}": route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.simulations"
    }







@pytest.mark.parametrize("name", ROUTES)
def test_no_simulation_route_declares_a_settings_parameter(name: str) -> None:
    parameters = list(inspect.signature(_simulation_routes()[name].endpoint).parameters)
    assert "settings" not in parameters, f"{name}: {parameters}"


@pytest.mark.parametrize("name", ROUTES)
def test_a_simulation_route_still_resolves_settings_for_the_configured_body(
    name: str,
) -> None:
    """Removing the parameter must not remove the configured shot/message bounds."""
    assert get_settings in _dependency_calls(_simulation_routes()[name]), (
        f"{name} no longer resolves the settings provider, so the configured "
        "shot and message limits would not be applied"
    )


def test_the_dependency_check_can_detect_a_settings_use() -> None:
    """Guard the guard: the checks above must be able to see ``get_settings``."""
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route for route in _iter_api_routes(app) if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the checks are vacuous"


def test_the_simulation_service_takes_no_settings_argument() -> None:
    parameters = list(inspect.signature(simulation_service.run_simulation).parameters)
    assert parameters == ["request", "include_ground_truth"], parameters


def test_the_simulation_service_no_longer_imports_settings() -> None:
    tree = ast.parse(SIMULATION_MODULES[1].read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "backend.api.config" not in modules
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    assert "ApiSettings" not in names


def test_no_simulation_module_mentions_settings_at_all() -> None:
    """Neither simulation module may reference the name, in any form."""
    offenders = []
    for path in SIMULATION_MODULES:
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







def test_a_lowered_shot_limit_is_still_enforced() -> None:
    strict = configured_client(max_shot_count=2, max_message_chars=64)
    assert strict.post(
        "/api/v1/simulations", json={**BASE, "shot_count": 2}
    ).status_code == 200
    assert strict.post(
        "/api/v1/simulations", json={**BASE, "shot_count": 3}
    ).status_code == 422


def test_a_lowered_message_limit_is_still_enforced() -> None:
    strict = configured_client(max_message_chars=8)
    assert strict.post(
        "/api/v1/simulations", json={**BASE, "message": "x" * 8}
    ).status_code == 200
    assert strict.post(
        "/api/v1/simulations", json={**BASE, "message": "x" * 9}
    ).status_code == 422


def test_the_published_simulation_paths_are_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    )
    spec = client.get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if "/simulations" in path
    }
    assert published == {
        "/api/v1/simulations": ["post"],
        "/api/v1/simulations/evaluation": ["post"],
    }







def test_the_operational_response_still_carries_no_ground_truth(client) -> None:
    body = client.post("/api/v1/simulations", json=BASE).json()
    assert "ground_truth" not in body
    assert body["observable_only"] is True
    assert body["states"] and body["verification"]["state_count"] == 8


def test_the_evaluation_response_still_carries_labelled_ground_truth(client) -> None:
    body = client.post("/api/v1/simulations/evaluation", json=BASE).json()
    truth = body["ground_truth"]
    assert body["observable_only"] is False
    assert truth["label"] == "evaluation ground truth; not observable operational output"
    assert truth["is_malicious"] is True
    assert truth["scenario_id"] == "api-scenario"
    assert truth["noise"] == {"noise_type": "depolarizing", "noise_strength": 0.02}
    assert truth["attack"]["attack_type"] == "channel_tampering"
    assert truth["attack"]["fraction"] == 0.5
    assert truth["attack"]["targeted_indices"] == [0, 2, 3, 7]
    assert truth["notes"]
