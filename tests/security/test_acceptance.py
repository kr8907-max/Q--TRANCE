"""Milestone 3 acceptance criteria.

These are the 24 criteria from the M3 brief, mapped to explicit tests.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Set

import numpy as np
import pytest

from backend.attacks import AttackConfig, VALID_ATTACK_TYPES, build_attack_scenario
from backend.noise import (
    BitFlipChannel,
    BitPhaseFlipChannel,
    DepolarizingChannel,
    NoiseConfig,
    PhaseFlipChannel,
    build_noise_channel,
)
from backend.protocol import VerifierContext, verify
from backend.quantum.density import projector
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import uncorrected_branch_states
from backend.security import FORBIDDEN_PATTERNS, StatementVerdict, check_statement
from backend.simulation import ScenarioConfig, run_scenario, sweep_noise

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BASE = dict(
    scenario_id="acc",
    message="transfer 100 units to account 7",
    signer_id="alice",
    verifier_id="bob",
    state_count=8,
    random_seed=7,
    session_id="a" * 32,
    nonce="b" * 64,
    created_at="2026-09-13T10:00:00+00:00",
)







def test_criterion_01_channel_abstraction() -> None:
    ch = build_noise_channel(NoiseConfig("none", 0.0))
    assert ch is not None
    assert hasattr(ch, "apply")
    assert hasattr(ch, "probabilities")







def test_criterion_02_depolarizing() -> None:
    ch = DepolarizingChannel(0.1)
    rho = np.eye(2, dtype=complex) / 2
    assert ch.apply(rho) is not None


def test_criterion_03_bit_flip() -> None:
    ch = BitFlipChannel(0.1)
    rho = np.eye(2, dtype=complex) / 2
    assert ch.apply(rho) is not None


def test_criterion_04_phase_flip() -> None:
    ch = PhaseFlipChannel(0.1)
    rho = np.eye(2, dtype=complex) / 2
    assert ch.apply(rho) is not None


def test_criterion_05_bit_phase_flip() -> None:
    ch = BitPhaseFlipChannel(0.1)
    rho = np.eye(2, dtype=complex) / 2
    assert ch.apply(rho) is not None







def test_criterion_06_noise_validation() -> None:
    for bad in (-0.1, 1.1):
        with pytest.raises(Exception):
            DepolarizingChannel(bad)







def test_criterion_07_baseline_experiments() -> None:
    base = ScenarioConfig(**{**BASE, "noise": NoiseConfig("depolarizing", 0.0)})
    for cfg in sweep_noise(base, (0.0, 0.001, 0.005, 0.01, 0.02, 0.05)):
        res = run_scenario(cfg)
        assert res.observable is not None







def test_criterion_08_forgery() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("forgery", 0.0, seed=1, parameters={"mode": "rebind_only"})}
    )
    res = run_scenario(cfg)
    assert res.observable.verification.accepted is False


def test_criterion_09_impersonation() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("impersonation", 0.0, seed=1, parameters={"presented_signer": "eve"})}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.attack["attack_type"] == "impersonation"


def test_criterion_10_unauthorized_verification() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("unauthorized_verification", 0.0, seed=1, parameters={"presented_verifier": "mallory"})}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.attack["attack_type"] == "unauthorized_verification"


def test_criterion_11_replay() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("replay", 0.0, seed=1)}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.attack["attack_type"] == "replay"


def test_criterion_12_intercept_resend() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"})}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.attack["attack_type"] == "intercept_resend"
    assert res.observable.mean_channel_disturbance > 0.0


def test_criterion_13_channel_tampering() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.attack["attack_type"] == "channel_tampering"







def test_criterion_14_independent_config() -> None:
    cfg = ScenarioConfig(
        **{**BASE,
           "noise": NoiseConfig("depolarizing", 0.05),
           "attack": AttackConfig("channel_tampering", 0.2, seed=3, parameters={"pauli": "Z"})}
    )
    res = run_scenario(cfg)
    assert res.ground_truth.noise is not None
    assert res.ground_truth.attack is not None







def test_criterion_15_observable_ground_truth_split() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})}
    )
    res = run_scenario(cfg)
    o = res.observable.to_dict()
    gt = res.ground_truth.to_dict()

    assert "attack_type" not in o
    assert "is_malicious" not in o

    assert "attack_type" in gt or "attack" in gt







def test_criterion_16_no_detection_logic_in_milestone_3() -> None:
    """The Milestone 3 layers contain no detection logic.

    Milestone 4 legitimately introduces ``backend.detection``, so the original
    "no detection package exists anywhere" form of this guard is obsolete. The
    property it was protecting is preserved instead: the Milestone 3 layers
    (noise, attacks, simulation) must neither import detection nor define a
    detection entry point. The import analysis is AST-based because a text grep
    also matches docstrings, guard lists and identifiers.
    """
    detection_entry_points = {"detect", "run_detection", "analyse_threats"}
    offenders: Set[str] = set()

    for layer in ("noise", "attacks", "simulation"):
        directory = REPO_ROOT / "backend" / layer
        assert directory.is_dir(), f"missing Milestone 3 layer: {layer}"
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("backend.detection"):
                            offenders.add(f"{layer}/{path.name}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if (node.module or "").startswith("backend.detection"):
                        offenders.add(f"{layer}/{path.name}: from {node.module}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in detection_entry_points:
                        offenders.add(f"{layer}/{path.name}: def {node.name}")

    assert not offenders, f"detection logic in Milestone 3: {sorted(offenders)}"







def test_criterion_17_no_detection_imports() -> None:
    forbidden: Set[str] = set()
    attack_dir = REPO_ROOT / "backend" / "attacks"
    for path in attack_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "from backend.detection" in text or "import backend.detection" in text:
            forbidden.add(str(path))
    assert not forbidden, f"attack modules import detection: {forbidden}"







def test_criterion_18_reproducibility() -> None:
    cfg = ScenarioConfig(
        **{**BASE, "attack": AttackConfig("intercept_resend", 0.3, seed=7, parameters={"eve_basis": "random"})}
    )
    a = run_scenario(cfg)
    b = run_scenario(cfg)
    assert a.observable.to_dict() == b.observable.to_dict()







def test_criterion_19_20_21_test_suites_exist() -> None:
    assert (REPO_ROOT / "tests" / "quantum").exists()
    assert (REPO_ROOT / "tests" / "protocol").exists()
    assert (REPO_ROOT / "tests" / "security").exists()







def test_criterion_22_documentation_exists() -> None:
    assert (REPO_ROOT / "docs" / "security" / "noise-and-channel.md").exists()
    assert (REPO_ROOT / "docs" / "security" / "attack-models.md").exists()







def test_criterion_23_no_unsupported_claims() -> None:
    """Criterion 23: no unsupported security claim in M3 code or in the docs.

    Negation is decided by the interpretation layer's own ``check_statement``, so
    the project has exactly one implementation of "is this claim negated?". An
    earlier version of this test used a +/-200-character window around each
    phrase, which excused a forbidden claim whenever any negation cue appeared
    anywhere nearby -- including in an unrelated clause or an earlier sentence.
    That contradicts the guard's documented rule: a negation governs only its own
    clause.
    """
    found: Set[str] = set()




    for directory in ("noise", "attacks", "simulation"):
        for path in (REPO_ROOT / "backend" / directory).rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for pattern, _reason in FORBIDDEN_PATTERNS:
                if pattern in text:
                    found.add(f"{path}: {pattern!r}")




    forbidden_patterns = {pattern for pattern, _ in FORBIDDEN_PATTERNS}
    for path in (REPO_ROOT / "docs" / "security").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for violation in check_statement(text).violations:
            if violation in forbidden_patterns:
                found.add(f"{path}: {violation!r}")

    assert not found, f"unsupported security claims found: {found}"





@pytest.mark.parametrize(
    "statement",
    [
        "The system provides composable security.",
        "The protocol is device-independent secure.",
        "The system provides deterministic finite-shot acceptance.",
    ],
)
def test_criterion_23_a_bare_overclaim_is_forbidden(statement: str) -> None:
    assert check_statement(statement).verdict is StatementVerdict.FORBIDDEN, statement


def test_criterion_23_an_explicitly_negated_claim_is_allowed() -> None:


    statement = "The prototype does not establish composable security."
    assert check_statement(statement).verdict is StatementVerdict.ALLOWED, statement


def test_criterion_23_a_distant_negation_does_not_excuse_a_claim() -> None:


    statement = (
        "No composable security theorem was proven at this milestone. "
        "The components were evaluated individually, the analysis is conditional "
        "on the assumption register throughout, and no proof was given that they "
        "compose. The system provides composable security."
    )
    result = check_statement(statement)
    assert result.verdict is StatementVerdict.FORBIDDEN, result.violations
    assert "composable security" in result.violations







def test_criterion_24_no_ml() -> None:

    ml_imports = ["sklearn", "tensorflow", "torch", "keras"]
    found: Set[str] = set()
    for path in (REPO_ROOT / "backend").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for kw in ml_imports:
            if kw in text:
                found.add(f"{path}: {kw!r}")
    assert not found, f"ML imports found: {found}"
