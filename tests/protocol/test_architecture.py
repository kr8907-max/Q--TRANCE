"""Architecture and scope guards for the M2 protocol layer.

These tests encode requirements that are easy to violate accidentally and hard
to notice: the dependency direction, the absence of attack/detection/noise/ML
code, and the absence of threshold logic.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROTOCOL_DIR = REPO_ROOT / "backend" / "protocol"
QUANTUM_DIR = REPO_ROOT / "backend" / "quantum"


def _python_files(directory: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in directory.rglob("*.py"))


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


def test_quantum_layer_does_not_import_the_protocol_layer() -> None:
    """The dependency direction is one way: protocol -> quantum, never back."""
    offenders = []
    for path in _python_files(QUANTUM_DIR):
        for module in _imported_modules(path):
            if module == "backend.protocol" or module.startswith("backend.protocol."):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


@pytest.mark.parametrize(
    "forbidden",
    [
        "backend.attacks",
        "backend.detection",
        "backend.noise",
        "backend.security",
        "backend.api",
        "backend.frontend",
    ],
)
def test_protocol_layer_does_not_import_future_modules(forbidden: str) -> None:
    offenders = []
    for path in _python_files(PROTOCOL_DIR):
        for module in _imported_modules(path):
            if module == forbidden or module.startswith(forbidden + "."):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_protocol_layer_has_no_third_party_dependencies_beyond_the_core() -> None:
    """The protocol layer uses the standard library, the quantum stack and M1."""
    allowed_prefixes = (
        "__future__",
        "backend",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "re",
        "secrets",
        "typing",
        "unicodedata",
        "numpy",
        "qiskit",
    )
    offenders = []
    for path in _python_files(PROTOCOL_DIR):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root not in allowed_prefixes:
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_no_attack_or_detection_code_exists_in_the_protocol_layer() -> None:
    """No attack, detection, noise, ML or threshold implementation anywhere."""
    forbidden_tokens = (
        "intercept",
        "resend",
        "impersonat",
        "tamper_detection",
        "replay_detect",
        "noise_model",
        "depolariz",
        "amplitude_damping",
        "threshold_calibrat",
        "false_positive",
        "false_negative",
        "attack_label",
        "classifier",
        "sklearn",
        "tensorflow",
        "torch",
        "fastapi",
        "uvicorn",
        "pydantic",
    )
    offenders = []
    for path in _python_files(PROTOCOL_DIR):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], offenders


def test_protocol_layer_has_no_ml_or_web_dependencies() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(PROTOCOL_DIR)
    ).lower()
    for forbidden in ("sklearn", "tensorflow", "torch", "fastapi", "pydantic"):
        assert forbidden not in text, forbidden


def test_protocol_layer_has_no_attack_or_noise_dependencies() -> None:
    """The protocol layer source must not import attacks, detection or noise.

    The protocol must remain fully usable on its own even though M3 has
    introduced those packages elsewhere in the repository.
    """
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(PROTOCOL_DIR)
    )
    for forbidden in ("backend.attacks", "backend.detection", "backend.noise"):
        assert forbidden not in text, f"protocol layer imports {forbidden}"

    from backend.protocol import VerifierContext, sign, verify

    result = sign(
        "architecture probe", signer_id="alice", verifier_id="bob", state_count=2
    )
    outcome = verify(
        result.transcript, "architecture probe", VerifierContext(verifier_id="bob")
    )
    assert outcome.accepted


def test_no_pickle_or_eval_in_the_protocol_layer() -> None:
    """Unsafe deserialization must not appear anywhere."""
    offenders = []
    for path in _python_files(PROTOCOL_DIR):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
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


def test_protocol_modules_are_all_importable() -> None:
    import importlib

    import backend.protocol as protocol

    for name in (
        "canonical",
        "models",
        "binding",
        "encoding",
        "session",
        "transcript",
        "signer",
        "verifier",
        "reference_qds",
    ):
        module = importlib.import_module(f"backend.protocol.{name}")
        assert module.__name__ == f"backend.protocol.{name}"
    assert protocol.PROTOCOL_VERSION


def test_the_protocol_layer_depends_on_no_web_or_ml_stack() -> None:
    """M2 adds no dependency: no pydantic, no FastAPI, no ML library.

    This was originally written as an assertion about ``requirements.txt``. That
    cannot survive a later milestone adding its own dependency -- Milestone 7
    legitimately added the FastAPI stack for the API layer -- so the rule is now
    checked where it was always meant to hold: the *protocol layer* imports none
    of these, so the protocol package stays dependency-light whatever the API
    layer needs.
    """
    forbidden = ("fastapi", "uvicorn", "starlette", "pydantic", "sklearn",
                 "torch", "tensorflow", "keras")
    offenders: list[str] = []
    for path in PROTOCOL_DIR.rglob("*.py"):
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
    assert not offenders, offenders
