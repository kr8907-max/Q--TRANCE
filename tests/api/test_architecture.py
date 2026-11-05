"""Architecture guards for the API layer.

These are the tests that make "the API orchestrates, it does not reimplement"
checkable rather than aspirational:

* the API never imports the quantum stack, so it cannot be doing quantum maths;
* nothing outside the API imports the API, so the dependency direction is one-way;
* each service is shown to reference the domain entry point it is supposed to
  delegate to;
* no dynamic execution and no ML.
"""

from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
API_ROOT = REPO_ROOT / "backend" / "api"
BACKEND_ROOT = REPO_ROOT / "backend"


FORBIDDEN_API_IMPORTS = ("qiskit", "qiskit_aer")


ML_IMPORTS = ("sklearn", "scikit_learn", "tensorflow", "torch", "keras", "xgboost")


FORBIDDEN_CALLS = ("eval", "exec", "compile", "__import__")


def _api_modules() -> list:
    return sorted(API_ROOT.rglob("*.py"))



REQUIRED_MODULES = (
    "app.py",
    "config.py",
    "context.py",
    "dependencies.py",
    "errors.py",
    "middleware.py",
    "store.py",
    "version.py",
)


def test_the_module_lists_are_not_empty_so_the_rules_are_not_vacuous() -> None:
    """Every rule below iterates one of these lists.

    Pointing API_ROOT at a directory that does not exist made five of the rules
    pass while checking nothing, which was verified by injection. An empty or
    truncated list is the failure mode a negative rule cannot detect on its own,
    so it is asserted explicitly here.
    """
    modules = _api_modules()
    assert len(modules) >= 30, f"only {len(modules)} API modules found"
    names = {path.name for path in modules}
    for required in REQUIRED_MODULES:
        assert required in names, required

    assert len(sorted((API_ROOT / "services").rglob("*.py"))) >= 8
    assert len(sorted((API_ROOT / "routes").rglob("*.py"))) >= 9
    assert len(sorted((API_ROOT / "schemas").rglob("*.py"))) >= 9


def _imports(tree: ast.AST) -> list:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_the_api_never_imports_the_quantum_stack() -> None:
    offenders = []
    for path in _api_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imports(tree):
            root = module.split(".")[0]
            if root in FORBIDDEN_API_IMPORTS:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
    assert not offenders, f"the API imports the quantum stack: {offenders}"


def test_nothing_outside_the_api_imports_the_api() -> None:
    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if API_ROOT in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imports(tree):
            if module == "backend.api" or module.startswith("backend.api."):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
    assert not offenders, f"the dependency direction is violated: {offenders}"


def test_the_api_uses_no_dynamic_execution() -> None:
    offenders = []
    for path in _api_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {node.func.id}")
    assert not offenders, f"the API uses dynamic execution: {offenders}"


def test_the_api_imports_no_machine_learning_library() -> None:
    offenders = []
    for path in _api_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imports(tree):
            if module.split(".")[0] in ML_IMPORTS:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
    assert not offenders, f"the API imports ML: {offenders}"


def test_the_api_does_not_import_pickle() -> None:
    offenders = []
    for path in _api_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(module.split(".")[0] == "pickle" for module in _imports(tree)):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"the API imports pickle: {offenders}"







DELEGATIONS = (
    ("session_service.py", "backend.protocol", "create_session"),
    ("session_service.py", "backend.protocol", "sign_session"),
    ("verification_service.py", "backend.protocol", "verify"),
    ("simulation_service.py", "backend.simulation", "run_scenario"),
    ("detection_service.py", "backend.detection", "detect"),
    ("calibration_service.py", "backend.calibration", "estimate_baseline"),
    ("calibration_service.py", "backend.calibration", "build_operating_point"),
    ("evaluation_service.py", "backend.evaluation", "run_benchmark"),
    ("security_service.py", "backend.security", "check_statement"),
    ("security_service.py", "backend.security", "reference_assumptions"),
    ("security_service.py", "backend.security", "matrix_summary"),
    ("security_service.py", "backend.security", "composition_summary"),
)


def test_every_service_delegates_to_a_domain_entry_point() -> None:
    services = API_ROOT / "services"
    missing = []
    for filename, package, symbol in DELEGATIONS:
        path = services / filename
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        if symbol not in text:
            missing.append(f"{filename} does not reference {symbol} ({package})")
    assert not missing, missing


def test_the_services_import_only_domain_packages() -> None:
    """No service may import another service's concern, nor the routes."""
    offenders = []
    for path in sorted((API_ROOT / "services").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imports(tree):
            if module.startswith("backend.api.routes"):
                offenders.append(f"{path.name}: {module}")
    assert not offenders, f"a service imports routes: {offenders}"





CONFIGURED_LIMIT_FIELDS = (
    "max_message_chars",
    "max_statements_per_request",
    "max_shot_count",
    "max_calibration_sessions",
)


def test_no_schema_reads_a_limit_from_a_module_level_constant() -> None:
    """A schema field bound must not come from a module-level settings object.

    A bound baked into a class body is fixed at import time, so every application
    would enforce the same value no matter what it was configured with -- which is
    the defect this rule exists to keep from coming back. Reading the *absolute
    ceiling* is fine and expected: that is a structural constant, not a
    configuration.

    The settings module itself is checked too. A module-level ``ApiSettings``
    instance would be a second place a limit could be read from, and the one that
    is easiest to reach by accident.
    """
    offenders = []
    for path in sorted((API_ROOT / "schemas").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "DEFAULT_SETTINGS" in source:
            offenders.append(f"{path.name} references DEFAULT_SETTINGS")
        for field in CONFIGURED_LIMIT_FIELDS:
            if f"DEFAULT_SETTINGS.{field}" in source:
                offenders.append(f"{path.name}: DEFAULT_SETTINGS.{field}")

    config_source = (API_ROOT / "config.py").read_text(encoding="utf-8")
    assert "DEFAULT_SETTINGS" not in config_source, (
        "config.py still defines a module-level default settings object; the "
        "active settings must come from the application"
    )
    assert not offenders, (
        "a schema reads a configured limit from a module-level default instead of "
        f"the active settings: {offenders}"
    )


def test_every_configured_limit_field_is_declared_by_a_schema_validator() -> None:
    """Each limit is enforced by a schema validator, so it has a single owner.

    This is the positive half of the rule above: it is not enough that the
    constant is absent, the field has to answer to the setting by name somewhere.
    Checking the name appears next to a validator call keeps the setting and the
    field from drifting apart.
    """
    offenders = []
    for path in sorted((API_ROOT / "schemas").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for field in CONFIGURED_LIMIT_FIELDS:
            if f'"{field}"' in source and "configured_limit" not in source:
                offenders.append(f"{path.name}: {field} with no configured_limit")
    assert not offenders, offenders


def test_every_request_body_is_a_configured_body() -> None:
    """A route's body parameter must resolve to the settings-aware dependency.

    A route that declared the bare schema would still validate structure, but the
    configured pass would never run, so the application's limits would silently
    not apply. Resolving the annotations is how that is caught: an annotation the
    framework cannot evaluate would fail here rather than at request time.
    """
    import importlib
    import typing

    offenders = []
    checked = 0
    for module_name in (
        "sessions",
        "verification",
        "simulations",
        "detection",
        "calibration",
        "security",
    ):
        module = importlib.import_module(f"backend.api.routes.{module_name}")
        for name in dir(module):
            handler = getattr(module, name)
            if not callable(handler) or not hasattr(handler, "__annotations__"):
                continue
            if getattr(handler, "__module__", None) != module.__name__:
                continue
            try:
                hints = typing.get_type_hints(handler, include_extras=True)
            except Exception as exc:  # pragma: no cover - the failure this guards
                offenders.append(f"{module_name}.{name}: unresolvable ({exc})")
                continue
            body = hints.get("request")
            if body is None:
                continue
            checked += 1
            origin = typing.get_origin(body)
            metadata = getattr(body, "__metadata__", ())
            if origin is not typing.Annotated or not metadata or not any(
                "configured_" in repr(item) for item in metadata
            ):
                offenders.append(f"{module_name}.{name}: bare schema body")


    assert checked >= 6, f"only {checked} request bodies inspected"
    assert not offenders, f"a route body bypasses the configured pass: {offenders}"


def test_routes_do_not_import_domain_packages_directly() -> None:
    """Routes go through the service layer, not straight to the engines."""
    offenders = []
    for path in sorted((API_ROOT / "routes").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imports(tree):
            root = module.split(".")[:2]
            if root in (["backend", "protocol"], ["backend", "simulation"],
                        ["backend", "detection"], ["backend", "calibration"],
                        ["backend", "evaluation"], ["backend", "security"],
                        ["backend", "quantum"], ["backend", "noise"],
                        ["backend", "attacks"]):
                offenders.append(f"{path.name}: {module}")
    assert not offenders, f"a route imports a domain package directly: {offenders}"


def test_the_store_reuses_the_m4_replay_registry() -> None:
    text = (API_ROOT / "store.py").read_text(encoding="utf-8")
    assert "from backend.detection.replay import ReplayRegistry" in text

    assert "class ReplayRegistry" not in text
    assert "def _check_reuse" not in text


def test_no_route_or_service_is_async_so_the_event_loop_is_never_blocked() -> None:
    """Handlers must be synchronous so FastAPI offloads them to its thread pool.

    Every handler calls blocking engine code -- quantum simulation, detection,
    calibration, a benchmark run. Declaring one ``async def`` would run it on the
    event loop instead, and a multi-second benchmark would stall every other
    request in the process, including /health.

    The middleware is deliberately exempt: it must be async to await call_next.
    """
    offenders = []
    for package in ("routes", "services"):
        for path in sorted((API_ROOT / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    offenders.append(f"{path.name}:{node.lineno} {node.name}")
    assert not offenders, f"these handlers would block the event loop: {offenders}"


def test_the_middleware_is_async() -> None:
    """The converse, so the exemption above cannot be over-applied."""
    tree = ast.parse((API_ROOT / "middleware.py").read_text(encoding="utf-8"))
    dispatch = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "dispatch"
    ]
    assert len(dispatch) == 1


def test_the_api_defines_no_hashing_or_teleportation() -> None:
    """A duplicate primitive would show up as a def with one of these names."""
    banned = {
        "compute_message_hash",
        "compute_message_binding",
        "compute_transcript_hash",
        "derive_state_sequence",
        "teleport_signature_state",
        "apply_pauli_correction",
        "build_noise_channel",
        "derive_threshold",
        "critical_count",
        "clopper_pearson_bound",
        "confusion_matrix",
        "check_statement",
    }
    offenders = []
    for path in _api_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in banned:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {node.name}")
    assert not offenders, f"the API reimplements domain logic: {offenders}"
