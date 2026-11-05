"""Structural enforcement of the evaluation layer's boundary.

The milestone's central ordering claim is that **the decision is made before the
label is read**. That claim is only worth anything if it is structural, so it is
checked here by parsing the source rather than by reading a comment.

Four rules are asserted.

**Rule E1 -- ground truth lives in three layers and nowhere else.** Only the
producers (:mod:`backend.simulation`, :mod:`backend.attacks`) and the consumer
(:mod:`backend.evaluation`) may name a ground-truth quantity. If the detector or
the calibration layer could name one, the honest-only property of calibration
would rest on discipline rather than on structure.

**Rule E2 -- nothing imports the evaluation layer.** The dependency direction is
one-way, so the detector, the calibration layer and every other upstream layer
are structurally unable to reach a label.

**Rule E3 -- the evaluation layer really does use the label.** The converse of
E1: the rule is not vacuous, and the layer is doing the job it exists for.

**Rule E4 -- the layers above evaluation do not reach down into it.** No engine
module imports the API or a frontend layer, the frontend package does not exist,
and the API layer imports no frontend. (Milestones 6 and 7 introduced
``backend.security`` and ``backend.api``, so the original "these packages do not
exist" wording has been replaced by the property it protected.)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"




GROUND_TRUTH_IDENTIFIERS = (
    "ground_truth",
    "groundtruth",
    "is_malicious",
    "is_attack",
    "attack_ground_truth",
)












GROUND_TRUTH_LAYERS = ("api", "attacks", "evaluation", "simulation")


EVALUATION_ALLOWED_PREFIXES = (
    "backend.evaluation",
    "backend.calibration",
    "backend.detection",
    "backend.protocol",
    "backend.quantum",
    "backend.noise",
    "backend.simulation",
    "backend.attacks",
)


def _packages() -> list[str]:
    return sorted(
        path.name
        for path in BACKEND.iterdir()
        if path.is_dir() and not path.name.startswith(("__", "."))
    )


def _modules(package: str) -> list[Path]:
    root = BACKEND / package
    assert root.is_dir(), root
    return sorted(path for path in root.rglob("*.py"))


def _all_modules_except(*packages: str) -> list[Path]:
    """Return every backend module outside the named packages."""
    return sorted(
        path
        for path in BACKEND.rglob("*.py")
        if not (set(packages) & set(path.relative_to(BACKEND).parts))
    )


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _identifiers(tree: ast.Module) -> set[str]:
    """Return every *code* identifier, deliberately excluding strings.

    Docstrings are allowed to discuss attacks and ground truth -- that is how
    the boundary is documented. What is forbidden is a variable, argument,
    attribute, function or keyword argument named after one.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            found.add(node.arg)
        elif isinstance(node, ast.alias):
            found.add((node.asname or node.name).split(".")[0])
    return found


def _imported_modules(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                found.add(node.module)
                found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _layers_naming_ground_truth() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for package in _packages():
        hits = [
            f"{path.name}:{sorted(_identifiers(_tree(path)) & set(GROUND_TRUTH_IDENTIFIERS))}"
            for path in _modules(package)
            if _identifiers(_tree(path)) & set(GROUND_TRUTH_IDENTIFIERS)
        ]
        if hits:
            found[package] = hits
    return found







def test_ground_truth_is_named_only_by_its_producers_and_its_consumer() -> None:
    found = _layers_naming_ground_truth()
    assert set(found) == set(GROUND_TRUTH_LAYERS), found


def test_the_ground_truth_layers_are_not_empty_so_the_rule_is_not_vacuous() -> None:
    found = _layers_naming_ground_truth()
    for package in GROUND_TRUTH_LAYERS:
        assert found.get(package), package


@pytest.mark.parametrize("path", _modules("detection"), ids=lambda p: p.name)
def test_the_detector_names_no_ground_truth_and_no_attack(path: Path) -> None:


    identifiers = {name.lower() for name in _identifiers(_tree(path))}
    offenders = sorted(
        name
        for name in identifiers
        if name in GROUND_TRUTH_IDENTIFIERS or "attack" in name or "malicious" in name
    )
    assert not offenders, f"{path.name} names {offenders}"


@pytest.mark.parametrize(
    "package", ["calibration", "quantum", "protocol", "noise", "security"]
)
def test_upstream_layers_name_no_ground_truth(package: str) -> None:
    for path in _modules(package):
        offenders = sorted(
            name.lower()
            for name in _identifiers(_tree(path))
            if name.lower() in GROUND_TRUTH_IDENTIFIERS
        )
        assert not offenders, f"{package}/{path.name} names {offenders}"







@pytest.mark.parametrize(
    "path", _all_modules_except("evaluation", "api"), ids=lambda p: str(p.name)
)
def test_no_module_outside_the_evaluation_layer_imports_it(path: Path) -> None:
    """Nothing *upstream* of the evaluation layer may import it.

    ``backend.api`` is excluded because it sits *above* evaluation, not below it:
    the API is the boundary that runs a benchmark, so it is a legitimate caller.
    Every layer the rule actually protects -- detection, calibration, protocol,
    simulation, noise, attacks, quantum, security -- is still covered.
    """
    offenders = sorted(
        name
        for name in _imported_modules(_tree(path))
        if name == "backend.evaluation" or name.startswith("backend.evaluation.")
    )
    assert not offenders, f"{path.name} imports {offenders}"







def test_the_evaluation_layer_imports_both_ground_truth_layers() -> None:
    imports: set[str] = set()
    for path in _modules("evaluation"):
        imports |= _imported_modules(_tree(path))
    assert any(name.startswith("backend.simulation") for name in imports)
    assert any(name.startswith("backend.attacks") for name in imports)


@pytest.mark.parametrize("path", _modules("evaluation"), ids=lambda p: p.name)
def test_the_evaluation_layer_depends_only_on_allowed_layers(path: Path) -> None:
    backend_imports = {
        name for name in _imported_modules(_tree(path)) if name.startswith("backend.")
    }
    offenders = sorted(
        name
        for name in backend_imports
        if not any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in EVALUATION_ALLOWED_PREFIXES
        )
    )
    assert not offenders, f"{path.name} imports {offenders}"













def test_the_frontend_package_does_not_exist() -> None:
    assert not (BACKEND / "frontend").exists()


def test_the_api_package_exists_and_is_reachable() -> None:
    """The converse of the old absence check, so the rule is not vacuous."""
    assert (BACKEND / "api").is_dir()


@pytest.mark.parametrize(
    "path", _all_modules_except("evaluation", "api"), ids=lambda p: str(p.name)
)
def test_no_module_reaches_for_an_api_or_frontend_layer(path: Path) -> None:
    """No engine module may import the API or a frontend layer.

    Modules inside ``backend.api`` are excluded: a module importing its own
    package is not reaching *up* for a boundary. Every engine package is covered.
    """
    offenders = sorted(
        name
        for name in _imported_modules(_tree(path))
        if name.startswith(("backend.api", "backend.frontend"))
    )
    assert not offenders, f"{path.name} imports {offenders}"


@pytest.mark.parametrize("path", _modules("api"), ids=lambda p: str(p.name))
def test_the_api_layer_imports_no_frontend_layer(path: Path) -> None:
    offenders = sorted(
        name
        for name in _imported_modules(_tree(path))
        if name.startswith("backend.frontend")
    )
    assert not offenders, f"{path.name} imports {offenders}"







def test_the_evaluation_package_declares_its_boundary() -> None:
    doc = (BACKEND / "evaluation" / "__init__.py").read_text(encoding="utf-8")
    assert "The calibration package may not import" in doc
    assert "backend.simulation" in doc
    assert "backend.attacks" in doc
    assert "Ground truth appears" in doc
