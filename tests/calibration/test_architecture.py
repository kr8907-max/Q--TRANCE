"""Structural enforcement of the milestone's isolation rules.

Two rules are load-bearing, and both are checkable by reading the source rather
than by trusting a reviewer.

**Rule 1 -- calibration never sees ground truth.** ``backend.calibration`` must
not import ``backend.attacks`` or ``backend.simulation``, and must not contain an
identifier that names an attack, a label or a ground-truth flag. The honest-only
property of the calibration dataset is then structural: the layer has no way to
express "this session was an attack", so no attack can influence a threshold.

**Rule 2 -- dependency direction is one-way.** Calibration sits between
detection and evaluation. It must not import ``backend.evaluation``, or the
"thresholds are fitted before anything is scored" ordering would become
circular.

Both are asserted by parsing the actual source with :mod:`ast`, so they hold for
every module in the package, including ones added later.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from backend.calibration import models as calibration_models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"


def _modules(package: str) -> list[Path]:
    root = BACKEND / package
    assert root.is_dir(), root
    return sorted(path for path in root.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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


def _identifiers(tree: ast.Module) -> set[str]:
    """Return every *code* identifier, deliberately excluding strings.

    Docstrings are allowed to discuss attacks -- that is how the isolation rule
    is documented. What is forbidden is a variable, argument, attribute, function
    or keyword argument named after one.
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


FORBIDDEN_IDENTIFIERS = (
    "attack",
    "attack_type",
    "attack_fraction",
    "attacks",
    "is_malicious",
    "malicious",
    "ground_truth",
    "groundtruth",
    "forgery",
    "replay",
    "label",
    "labels",
)







@pytest.mark.parametrize("path", _modules("calibration"), ids=lambda p: p.name)
def test_calibration_never_imports_attacks_or_simulation(path: Path) -> None:
    imported = _imported_modules(_tree(path))
    offenders = sorted(
        name
        for name in imported
        if name == "backend.attacks"
        or name.startswith("backend.attacks.")
        or name == "backend.simulation"
        or name.startswith("backend.simulation.")
    )
    assert not offenders, f"{path.name} imports {offenders}"


@pytest.mark.parametrize("path", _modules("calibration"), ids=lambda p: p.name)
def test_calibration_contains_no_ground_truth_identifier(path: Path) -> None:
    identifiers = {name.lower() for name in _identifiers(_tree(path))}
    offenders = sorted(identifiers & set(FORBIDDEN_IDENTIFIERS))
    assert not offenders, f"{path.name} names {offenders}"


@pytest.mark.parametrize(
    "record",
    [
        calibration_models.CalibrationConfig,
        calibration_models.CalibrationObservation,
    ],
)
def test_calibration_records_have_no_ground_truth_field(record) -> None:
    names = {field.name.lower() for field in dataclasses.fields(record)}
    offenders = sorted(
        name
        for name in names
        if any(token in name for token in FORBIDDEN_IDENTIFIERS)
    )
    assert not offenders, f"{record.__name__} carries {offenders}"


def test_no_attack_module_is_importable_from_the_calibration_package() -> None:


    import importlib
    import sys

    before = set(sys.modules)
    for path in _modules("calibration"):
        name = "backend.calibration." + path.stem
        importlib.import_module(name)
    imported = set(sys.modules) - before
    offenders = sorted(
        name for name in imported if name.startswith(("backend.attacks", "backend.simulation"))
    )
    assert not offenders, offenders







@pytest.mark.parametrize("path", _modules("calibration"), ids=lambda p: p.name)
def test_calibration_does_not_import_the_evaluation_layer(path: Path) -> None:
    imported = _imported_modules(_tree(path))
    offenders = sorted(
        name
        for name in imported
        if name == "backend.evaluation" or name.startswith("backend.evaluation.")
    )
    assert not offenders, f"{path.name} imports {offenders}"


@pytest.mark.parametrize("path", _modules("detection"), ids=lambda p: p.name)
def test_the_milestone_four_detector_never_imports_attacks_or_simulation(
    path: Path,
) -> None:


    imported = _imported_modules(_tree(path))
    offenders = sorted(
        name
        for name in imported
        if name == "backend.attacks"
        or name.startswith("backend.attacks.")
        or name == "backend.simulation"
        or name.startswith("backend.simulation.")
    )
    assert not offenders, f"{path.name} imports {offenders}"


@pytest.mark.parametrize("path", _modules("calibration"), ids=lambda p: p.name)
def test_calibration_depends_only_on_allowed_layers(path: Path) -> None:
    allowed_prefixes = (
        "backend.calibration",
        "backend.detection",
        "backend.protocol",
        "backend.quantum",
        "backend.noise",
    )
    imported = _imported_modules(_tree(path))
    backend_imports = {name for name in imported if name.startswith("backend.")}
    offenders = sorted(
        name
        for name in backend_imports
        if not any(name == p or name.startswith(p + ".") for p in allowed_prefixes)
    )
    assert not offenders, f"{path.name} imports {offenders}"


def test_the_calibration_package_declares_its_isolation_rule() -> None:

    doc = (BACKEND / "calibration" / "__init__.py").read_text(encoding="utf-8")
    assert "must never import" in doc
    assert "backend.attacks" in doc
    assert "backend.simulation" in doc
