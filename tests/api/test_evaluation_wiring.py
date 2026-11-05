"""The evaluation path has no settings dependency, and still behaves the same.

``settings`` used to be threaded through the evaluation endpoints and the
evaluation service even though nothing read it. Evaluation is bounded by the
benchmark profile a caller selects, so there is no application configuration for
that path to consume; the parameter was leftover plumbing from the initial API
integration.

These tests pin the cleaned-up wiring: the endpoints do not resolve the settings
provider, the service takes no settings argument, and the profile still controls
the trial count. The behavioural equivalence itself is covered by the existing
evaluation tests plus the recorded before/after API snapshot.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from backend.api import ApiSettings, ApiStore
from backend.api.app import create_app
from backend.api.dependencies import get_settings
from backend.api.schemas.evaluation import EvaluationRunRequest
from backend.api.services import evaluation_service
from backend.evaluation import REFERENCE_PROFILE, SMOKE_PROFILE

EVALUATION_MODULES = (
    pathlib.Path("backend/api/routes/evaluation.py"),
    pathlib.Path("backend/api/services/evaluation_service.py"),
)


def _dependency_calls(route) -> set:
    """Every callable FastAPI resolves while serving ``route``."""
    calls = set()
    stack = [route.dependant]
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


def _evaluation_routes():
    """The evaluation endpoints as wired into a real application.

    Selected by the handler's own module rather than by its path, so a route in
    another router that merely mentions "evaluation" in its path is not counted.
    """
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    return [
        route
        for route in _iter_api_routes(app)
        if getattr(route.endpoint, "__module__", None) == "backend.api.routes.evaluation"
    ]







def test_the_evaluation_endpoints_do_not_resolve_the_settings_provider() -> None:
    """No evaluation route may pull ``get_settings`` into its dependency graph."""
    routes = _evaluation_routes()
    assert len(routes) == 3, f"expected 3 evaluation routes, found {len(routes)}"

    offenders = [
        route.path for route in routes if get_settings in _dependency_calls(route)
    ]
    assert offenders == [], f"evaluation routes still depend on settings: {offenders}"


def test_the_settings_provider_is_still_used_by_the_routes_that_need_it() -> None:
    """Guard the guard: the check above must be able to detect a settings use.

    If ``_dependency_calls`` could never see ``get_settings``, the test above
    would pass for every route and prove nothing.
    """
    app = create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    dependents = [
        route
        for route in _iter_api_routes(app)
        if get_settings in _dependency_calls(route)
    ]
    assert dependents, "no route resolves get_settings, so the check is vacuous"


def test_the_evaluation_service_takes_no_settings_argument() -> None:
    parameters = list(inspect.signature(evaluation_service.run_evaluation).parameters)
    assert parameters == ["store", "request"], parameters


def test_the_evaluation_service_no_longer_imports_settings() -> None:
    tree = ast.parse(EVALUATION_MODULES[1].read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[-1] for alias in node.names)
    assert "ApiSettings" not in imported
    assert "backend.api.config" not in {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def test_no_evaluation_module_mentions_settings_at_all() -> None:
    """Neither evaluation module may reference the name, in any form."""
    offenders = []
    for path in EVALUATION_MODULES:
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







def test_the_profile_map_still_names_both_profiles() -> None:
    assert evaluation_service._PROFILES == {
        "smoke": SMOKE_PROFILE,
        "reference": REFERENCE_PROFILE,
    }


def test_the_smoke_profile_still_controls_the_trial_count(evaluation_run) -> None:
    """The reported trial count is the profile's, and no setting influences it."""
    configuration = evaluation_run["configuration"]
    assert configuration["profile"] == SMOKE_PROFILE.name
    assert configuration["evaluation_trials"] == SMOKE_PROFILE.evaluation_trials


def test_the_reference_profile_is_selected_and_forwarded_unchanged(monkeypatch) -> None:
    """The reference profile reaches the harness untouched, with no settings.

    ``run_benchmark`` is stubbed so the selection path is proved without paying
    for the full reference benchmark.
    """
    seen = []

    def fake_run_benchmark(profile):
        seen.append(profile)
        return {"report": {}, "markdown": None}

    monkeypatch.setattr(evaluation_service, "run_benchmark", fake_run_benchmark)
    evaluation_service.run_evaluation(
        ApiStore(), EvaluationRunRequest(profile="reference")
    )
    assert seen == [REFERENCE_PROFILE]


def test_the_published_evaluation_paths_are_unchanged() -> None:
    """Removing a dependency parameter must not change the published contract."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(settings=ApiSettings(environment="test"), store=ApiStore())
    )
    spec = client.get("/openapi.json").json()
    published = {
        path: sorted(methods)
        for path, methods in spec["paths"].items()
        if path.startswith("/api/v1/evaluation")
    }
    assert published == {
        "/api/v1/evaluation/run": ["post"],
        "/api/v1/evaluation/{evaluation_id}": ["get"],
        "/api/v1/evaluation/{evaluation_id}/artifact": ["get"],
    }
