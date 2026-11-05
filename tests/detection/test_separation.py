"""Attack-label independence and detector isolation.

This module encodes the architectural requirement the milestone exists to
establish: the detector must produce the same result for the same observable
data whatever the hidden ground truth was, and must not be able to see that
ground truth in the first place.

Three independent lines of defence are tested here:

1. **Structural** -- the input contract has no field that could carry a label.
2. **Static** -- no module under ``backend/detection`` imports the attack,
   noise or simulation packages.
3. **Runtime** -- importing the detection package does not put
   ``backend.attacks`` into ``sys.modules``, checked in a fresh interpreter so
   the answer cannot be contaminated by whatever the test session already
   imported.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys

import pytest

from backend.attacks import AttackConfig
from backend.detection import ObservableDetectionInput, detect
from backend.noise import NoiseConfig
from backend.protocol import VerifierContext, verify
from backend.simulation import ScenarioConfig, run_scenario
from tests.detection.conftest import (
    BASE,
    end_to_end_input,
    reconstruct_transcript,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DETECTION_DIR = REPO_ROOT / "backend" / "detection"





FORBIDDEN_IMPORTS = ("backend.attacks", "backend.noise", "backend.simulation")


FORBIDDEN_FIELD_NAMES = (
    "attack_type",
    "attack_fraction",
    "attack_name",
    "attack",
    "ground_truth",
    "is_malicious",
    "noise_type",
    "noise_strength",
    "scenario_id",
    "simulator_seed",
    "mean_channel_disturbance",
)


def _detection_modules() -> list[pathlib.Path]:
    return sorted(DETECTION_DIR.rglob("*.py"))


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







@pytest.mark.parametrize("forbidden", FORBIDDEN_FIELD_NAMES)
def test_input_contract_has_no_ground_truth_field(forbidden: str) -> None:
    assert forbidden not in ObservableDetectionInput.__dataclass_fields__


def test_input_serialization_contains_no_ground_truth_field() -> None:
    payload = end_to_end_input(ScenarioConfig(**BASE)).to_dict()
    serialized = json.dumps(payload, default=str)
    for forbidden in FORBIDDEN_FIELD_NAMES:
        assert forbidden not in serialized, forbidden


def test_the_adapter_ignores_scenario_identity_even_when_it_leaks_a_parameter() -> None:
    """M3 scenario identifiers can encode the attack fraction, so they are ignored."""

    class Observable:
        """Minimal duck-typed observable carrying a leaky scenario identifier."""

        scenario_id = "base-attack-0.5"
        protocol_version = "RQDS-TP-1.0"
        state_count = 0
        states = ()
        basis_counts = {}
        mismatch_count = 0
        mismatch_proportion = 0.0
        mean_channel_disturbance = 0.75
        simulator_seed = 12345
        measurement_mode = "projective-analytic"
        verification = None
        authorization = None

    detection = ObservableDetectionInput.from_observable(Observable())
    assert detection.to_dict()["observed_state_count"] == 0
    serialized = json.dumps(detection.to_dict(), default=str)
    assert "attack" not in serialized
    assert "0.5" not in serialized
    assert "12345" not in serialized
    assert "0.75" not in serialized







@pytest.mark.parametrize("forbidden", FORBIDDEN_IMPORTS)
def test_detection_source_never_imports_the_attack_side(forbidden: str) -> None:
    offenders = []
    for path in _detection_modules():
        for module in _imported_modules(path):
            if module == forbidden or module.startswith(forbidden + "."):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def _identifiers(path: pathlib.Path) -> set[str]:
    """Return every identifier-like token in ``path``, via AST.

    Text greps match docstrings, and every docstring in this package names the
    ground-truth type in order to forbid it. Identifiers are what matter.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def test_detection_source_contains_no_attack_label_reads() -> None:
    """No identifier or exact string literal may name a ground-truth concept."""
    tokens = (
        "GroundTruthMetadata",
        "attack_type",
        "is_malicious",
        "attack_fraction",
        "attack_name",
    )
    offenders = []
    for path in _detection_modules():
        names = _identifiers(path)
        for token in tokens:
            if token in names:
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], offenders


def test_detection_source_has_no_ml_dependency() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in _detection_modules()
    ).lower()
    for forbidden in (
        "sklearn",
        "tensorflow",
        "torch",
        "keras",
        "fastapi",
        "uvicorn",
        "pydantic",
    ):
        assert forbidden not in text, forbidden







def test_importing_detection_does_not_import_attacks() -> None:
    script = (
        "import sys\n"
        "import backend.detection\n"
        "leaked = sorted(\n"
        "    name for name in sys.modules\n"
        "    if name.startswith(('backend.attacks', 'backend.noise', 'backend.simulation'))\n"
        ")\n"
        "print('LEAKED:' + ','.join(leaked))\n"
    )
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
    assert "LEAKED:" in completed.stdout
    leaked = completed.stdout.split("LEAKED:", 1)[1].strip()
    assert leaked == "", f"importing backend.detection pulled in {leaked}"







def _identical_observable_pair() -> tuple[ScenarioConfig, ScenarioConfig]:
    """Two configurations with byte-identical observables and different truth.

    Both use the same honest noise and the same pinned identifiers and seed.
    The second configures an attack that touches **no** state (``fraction=0``),
    so it modifies nothing -- yet its ground truth says an attack ran.
    """
    noise = NoiseConfig("depolarizing", 0.05)
    honest = ScenarioConfig(**{**BASE, "noise": noise})
    zero_effect_attack = ScenarioConfig(
        **{
            **BASE,
            "noise": noise,
            "attack": AttackConfig(
                "channel_tampering", 0.0, seed=9, parameters={"pauli": "X"}
            ),
        }
    )
    return honest, zero_effect_attack


def test_the_pair_really_has_identical_observables_and_different_truth() -> None:
    """Guard: the independence test below must not pass vacuously."""
    honest, attacked = _identical_observable_pair()
    honest_result = run_scenario(honest)
    attacked_result = run_scenario(attacked)

    assert honest_result.observable.to_dict() == attacked_result.observable.to_dict()
    assert honest_result.ground_truth.is_malicious is False
    assert attacked_result.ground_truth.is_malicious is True
    assert honest_result.ground_truth.attack["attack_type"] == "none"
    assert attacked_result.ground_truth.attack["attack_type"] == "channel_tampering"


def test_identical_observable_data_gives_identical_detector_results() -> None:
    honest, attacked = _identical_observable_pair()
    first = detect(end_to_end_input(honest))
    second = detect(end_to_end_input(attacked))

    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
    assert first.overall_status is second.overall_status
    assert [item.finding_id for item in first.findings] == [
        item.finding_id for item in second.findings
    ]


def test_a_second_pair_with_a_different_zero_effect_attack_also_matches() -> None:
    noise = NoiseConfig("depolarizing", 0.05)
    honest = ScenarioConfig(**{**BASE, "noise": noise})
    other = ScenarioConfig(
        **{
            **BASE,
            "noise": noise,
            "attack": AttackConfig(
                "intercept_resend", 0.0, seed=4, parameters={"eve_basis": "Z"}
            ),
        }
    )
    assert run_scenario(honest).observable.to_dict() == run_scenario(other).observable.to_dict()
    assert run_scenario(other).ground_truth.is_malicious is True
    assert json.dumps(detect(end_to_end_input(honest)).to_dict(), sort_keys=True) == (
        json.dumps(detect(end_to_end_input(other)).to_dict(), sort_keys=True)
    )







@pytest.mark.parametrize(
    "attack",
    [
        None,
        AttackConfig("forgery", 0.0, seed=1, parameters={"mode": "rebind_only"}),
        AttackConfig("impersonation", 0.0, seed=1, parameters={"presented_signer": "eve"}),
    ],
)
def test_reconstructed_transcript_reproduces_the_observable_verification(
    attack: AttackConfig | None,
) -> None:
    """Guards the test helper: the rebuilt transcript must be the real one.

    If the runner's pipeline ever changes, this fails instead of the detection
    tests silently analysing a different artifact.
    """
    config = ScenarioConfig(**{**BASE, "attack": attack} if attack else BASE)
    observable = run_scenario(config).observable
    transcript, verifier_context, _ = reconstruct_transcript(config)
    recomputed = verify(
        transcript,
        config.message,
        VerifierContext(
            verifier_id=verifier_context.verifier_id,
            expected_protocol_version=verifier_context.expected_protocol_version,
        ),
    )
    assert recomputed.accepted == observable.verification.accepted
    assert recomputed.session_valid == observable.verification.session_valid
    assert recomputed.message_valid == observable.verification.message_valid
    assert recomputed.transcript_valid == observable.verification.transcript_valid
    assert recomputed.state_sequence_valid == observable.verification.state_sequence_valid
