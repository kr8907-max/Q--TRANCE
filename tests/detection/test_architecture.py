"""Architecture guards for the detection layer.

The dependency direction is the point of the milestone::

    quantum -> protocol -> noise / attacks -> observable experiment data
                                                    |
                                                    v
                                               detection
                                                    |
                                                    v
                                    future calibration / security analysis

Detection may sit *above* observable experiment data and must not depend on the
attack side in either direction.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
DETECTION_DIR = BACKEND / "detection"



ALLOWED_TOP_LEVEL = (
    "__future__",
    "dataclasses",
    "enum",
    "scipy",
    "typing",
)


ALLOWED_BACKEND_PREFIXES = ("backend.detection", "backend.protocol")


def _python_files(directory: pathlib.Path) -> list[pathlib.Path]:
    return sorted(directory.rglob("*.py"))


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                modules.add(node.module)
    return modules


def test_detection_depends_only_on_the_protocol_layer_and_the_standard_library() -> None:
    offenders = []
    for path in _python_files(DETECTION_DIR):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root == "backend":
                if not module.startswith(ALLOWED_BACKEND_PREFIXES):
                    offenders.append(f"{path.name}: {module}")
                continue
            if root not in ALLOWED_TOP_LEVEL:
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


@pytest.mark.parametrize("layer", ["quantum", "protocol", "noise", "attacks", "simulation"])
def test_no_lower_layer_imports_detection(layer: str) -> None:
    """Detection must never become a dependency of anything beneath it."""
    offenders = []
    for path in _python_files(BACKEND / layer):
        for module in _imported_modules(path):
            if module == "backend.detection" or module.startswith("backend.detection."):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_detection_does_not_import_the_quantum_layer_directly() -> None:
    """Detection reads observations, not state vectors."""
    offenders = []
    for path in _python_files(DETECTION_DIR):
        for module in _imported_modules(path):
            if module == "backend.quantum" or module.startswith("backend.quantum."):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_detection_modules_are_all_importable() -> None:
    import importlib

    import backend.detection as detection

    for name in (
        "models",
        "statistics",
        "mismatch",
        "disturbance",
        "fidelity",
        "consistency",
        "authorization",
        "replay",
        "features",
        "evidence",
        "decision",
        "engine",
    ):
        module = importlib.import_module(f"backend.detection.{name}")
        assert module.__name__ == f"backend.detection.{name}"
    assert detection.ObservableDetectionInput is not None


def test_detection_has_no_web_or_ml_dependency() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(DETECTION_DIR)
    ).lower()
    for forbidden in (
        "sklearn",
        "tensorflow",
        "torch",
        "keras",
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
    ):
        assert forbidden not in text, forbidden


def test_detection_uses_no_pickle_or_eval() -> None:
    offenders = []
    for path in _python_files(DETECTION_DIR):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in {"eval", "exec", "compile"}:
                offenders.append(f"{path.name}: {node.id}")
            if isinstance(node, ast.Import) and any(
                alias.name == "pickle" for alias in node.names
            ):
                offenders.append(f"{path.name}: import pickle")
            if isinstance(node, ast.ImportFrom) and node.module == "pickle":
                offenders.append(f"{path.name}: from pickle")
    assert offenders == [], offenders


def test_the_detection_layer_depends_on_no_web_or_ml_stack() -> None:
    """M4 adds no dependency: scipy is already pinned by M1.

    Originally written as an assertion about ``requirements.txt``. That cannot
    survive a later milestone adding its own dependency -- Milestone 7
    legitimately added the FastAPI stack for the API layer -- so the rule is
    checked where it was always meant to hold: the *detection layer* imports none
    of these.
    """
    forbidden = (
        "fastapi",
        "uvicorn",
        "starlette",
        "pydantic",
        "sklearn",
        "torch",
        "tensorflow",
        "sqlalchemy",
    )
    offenders: list[str] = []
    for path in DETECTION_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0].lower() in forbidden:
                    offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders

    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "scipy" in requirements


def test_detection_does_not_persist_state_to_disk() -> None:
    """M4 uses in-memory replay state only; there is no database yet."""
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(DETECTION_DIR)
    ).lower()
    for forbidden in ("sqlite", "open(", "pickle", "shelve", "redis"):
        assert forbidden not in text, forbidden
    assert "in-memory" in text


def test_the_detection_package_is_not_pulled_in_by_importing_attacks() -> None:
    """Belt and braces: importing the attack layer must not import detection."""
    script = (
        "import sys\n"
        "import backend.attacks\n"
        "leaked = [n for n in sys.modules if n.startswith('backend.detection')]\n"
        "print('LEAKED:' + ','.join(sorted(leaked)))\n"
    )
    import os
    import subprocess

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    leaked = completed.stdout.split("LEAKED:", 1)[1].strip()
    assert leaked == "", leaked
