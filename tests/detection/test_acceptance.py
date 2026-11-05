"""Milestone 4 acceptance criteria.

The 23 criteria from the milestone brief, each mapped to an explicit test.
Criterion 20 (M1+M2+M3 regression stays green) and criterion 21 (M4 tests pass)
are properties of the whole suite; what is checked here is that the suites still
exist and that the detection package does not disturb them.
"""

from __future__ import annotations

import ast
import json
import pathlib
from typing import Set

import pytest

from backend.attacks import AttackConfig
from backend.detection import (
    FEATURE_CATALOG,
    DetectionResult,
    DetectorParameters,
    EvidenceCategory,
    ObservableDetectionInput,
    StateEvidence,
    ThreatEvidence,
    analyse_authorization,
    analyse_consistency,
    analyse_disturbance,
    analyse_fidelity,
    analyse_mismatch,
    detect,
    extract_features,
)
from backend.noise import NoiseConfig
from backend.simulation import ScenarioConfig, run_scenario
from tests.detection.conftest import (
    BASE,
    detection_input,
    end_to_end_input,
    make_transcript,
    tamper_state_identifier,
    valid_input,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DETECTION_DIR = REPO_ROOT / "backend" / "detection"



def test_criterion_01_observable_detection_input_contract_exists() -> None:
    detection = valid_input()
    assert isinstance(detection, ObservableDetectionInput)
    expected = (
        "session_id",
        "nonce",
        "protocol_version",
        "message_binding",
        "declared_transcript_hash",
        "signer_id",
        "verifier_id",
        "created_at",
        "verifier_context_id",
        "authorized_signers",
        "authorized_verifiers",
        "transcript_payload",
        "states",
        "declared_state_count",
        "verification",
    )
    for field in expected:
        assert field in ObservableDetectionInput.__dataclass_fields__, field
    assert ObservableDetectionInput.from_observable is not None



def test_criterion_02_feature_extraction_exists() -> None:
    detection = valid_input()
    features = extract_features(
        detection,
        consistency=analyse_consistency(detection),
        authorization=analyse_authorization(detection),
    )
    assert len(FEATURE_CATALOG) >= 14
    assert features.mismatch_rate == 0.0



def test_criterion_03_mismatch_analysis_exists() -> None:
    analysis = analyse_mismatch(
        (StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=1.0, matched=False),)
    )
    assert analysis.mismatch_rate == 1.0



def test_criterion_04_verification_state_disturbance_exists() -> None:
    analysis = analyse_disturbance(
        (StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=0.5, matched=True),)
    )
    assert analysis.disturbance_rate == 1.0
    assert analysis.n_verification_states == 1



def test_criterion_05_fidelity_analysis_exists() -> None:
    analysis = analyse_fidelity(
        (StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=0.8, matched=True),),
        measurement_mode="projective-analytic",
    )
    assert analysis.analytic_mean_fidelity == pytest.approx(0.8)



def test_criterion_06_transcript_integrity_evidence_exists() -> None:
    result = detect(valid_input(declared_transcript_hash="f" * 64))
    assert result.findings_for(EvidenceCategory.TRANSCRIPT_INTEGRITY)



def test_criterion_07_replay_evidence_exists() -> None:
    from backend.detection import ReplayRegistry

    detection = valid_input()
    registry = ReplayRegistry()
    detect(detection, replay_registry=registry, consume=True)
    result = detect(detection, replay_registry=registry, consume=True)
    assert result.findings_for(EvidenceCategory.REPLAY)



def test_criterion_08_signer_authorization_evidence_exists() -> None:
    result = detect(valid_input(signer_id="eve", authorized_signers=("alice",)))
    assert result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)



def test_criterion_09_verifier_authorization_evidence_exists() -> None:
    result = detect(
        valid_input(
            verifier_id="mallory",
            verifier_context_id="mallory",
            authorized_verifiers=("bob",),
        )
    )
    assert result.findings_for(EvidenceCategory.VERIFIER_AUTHORIZATION)



def test_criterion_10_quantum_and_channel_anomaly_evidence_exists() -> None:
    config = ScenarioConfig(
        **{
            **BASE,
            "noise": NoiseConfig("depolarizing", 0.05),
            "attack": AttackConfig(
                "intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"}
            ),
        }
    )
    result = detect(end_to_end_input(config))
    assert result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)
    assert result.overall_status.value == "QUANTUM_ANOMALY"



def test_criterion_11_forgery_related_verification_evidence_exists() -> None:

    _, transcript = make_transcript()
    payload = tamper_state_identifier(transcript.to_dict(), index=0)
    tampered = detect(detection_input(transcript, payload=payload))
    assert tampered.findings_for(EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY)


    forged = ScenarioConfig(
        **{
            **BASE,
            "attack": AttackConfig(
                "forgery", 0.0, seed=1, parameters={"mode": "rebind_only"}
            ),
        }
    )
    result = detect(end_to_end_input(forged))
    assert result.findings_for(EvidenceCategory.TRANSCRIPT_INTEGRITY)
    assert result.overall_status.value == "INTEGRITY_VIOLATION"



def test_criterion_12_structured_threat_evidence_exists() -> None:
    finding = detect(valid_input(declared_transcript_hash="f" * 64)).findings[0]
    assert isinstance(finding, ThreatEvidence)
    for field in (
        "finding_id",
        "category",
        "severity",
        "calibration",
        "strength",
        "evidence_items",
        "observed_values",
        "comparison_values",
        "explanation",
        "source_metrics",
        "session_reference",
        "timestamp",
        "blocking",
    ):
        assert field in ThreatEvidence.__dataclass_fields__, field



def test_criterion_13_structured_detection_result_exists() -> None:
    result = detect(valid_input())
    assert isinstance(result, DetectionResult)
    for field in ("protocol_valid", "findings", "overall_status", "explanation"):
        assert field in DetectionResult.__dataclass_fields__, field
    assert result.overall_status.value in {
        "CLEAR",
        "INTEGRITY_VIOLATION",
        "AUTHORIZATION_VIOLATION",
        "QUANTUM_ANOMALY",
        "MULTIPLE_FINDINGS",
    }



def test_criterion_14_detector_never_imports_attack_ground_truth() -> None:
    offenders: Set[str] = set()
    for path in DETECTION_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(("backend.attacks", "backend.simulation")):
                        offenders.add(f"{path.name}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(("backend.attacks", "backend.simulation")):
                    offenders.add(f"{path.name}: {module}")
                for alias in node.names:
                    if alias.name == "GroundTruthMetadata":
                        offenders.add(f"{path.name}: {alias.name}")
    assert offenders == set(), offenders



def test_criterion_15_detector_never_reads_attack_labels() -> None:
    names = ("attack_type", "attack_fraction", "attack_name", "is_malicious")
    offenders: Set[str] = set()
    for path in DETECTION_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in names:
                offenders.add(f"{path.name}: {node.id}")
            if isinstance(node, ast.Attribute) and node.attr in names:
                offenders.add(f"{path.name}: {node.attr}")
            if isinstance(node, ast.Constant) and node.value in names:
                offenders.add(f"{path.name}: {node.value!r}")
    assert offenders == set(), offenders



def test_criterion_16_same_observable_different_truth_same_result() -> None:
    noise = NoiseConfig("depolarizing", 0.05)
    honest = ScenarioConfig(**{**BASE, "noise": noise})
    zero_effect = ScenarioConfig(
        **{
            **BASE,
            "noise": noise,
            "attack": AttackConfig(
                "channel_tampering", 0.0, seed=9, parameters={"pauli": "X"}
            ),
        }
    )
    assert run_scenario(honest).observable.to_dict() == run_scenario(zero_effect).observable.to_dict()
    assert run_scenario(honest).ground_truth.is_malicious is False
    assert run_scenario(zero_effect).ground_truth.is_malicious is True
    assert json.dumps(detect(end_to_end_input(honest)).to_dict(), sort_keys=True) == (
        json.dumps(detect(end_to_end_input(zero_effect)).to_dict(), sort_keys=True)
    )



def test_criterion_17_honest_noise_is_processable_without_attack_knowledge() -> None:
    configs = (
        ScenarioConfig(**BASE),
        ScenarioConfig(**{**BASE, "noise": NoiseConfig("depolarizing", 0.05)}),
        ScenarioConfig(
            **{
                **BASE,
                "noise": NoiseConfig("depolarizing", 0.05),
                "attack": AttackConfig(
                    "channel_tampering", 0.5, seed=3, parameters={"pauli": "X"}
                ),
            }
        ),
    )
    for config in configs:
        result = detect(end_to_end_input(config))
        assert isinstance(result, DetectionResult)
        assert result.protocol_valid is True



def test_criterion_18_no_arbitrary_final_thresholds() -> None:
    """The only numeric defaults are a numerical definition and a confidence."""
    defaults = DetectorParameters()
    assert defaults.reference_mismatch_rate is None
    assert defaults.reference_disturbance_rate is None
    assert defaults.reference_fidelity is None

    literals: Set[str] = set()
    for path in DETECTION_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, float):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            literals.add(f"{path.name}:{target.id}")
    assert literals == {"statistics.py:DEFAULT_CONFIDENCE"}, literals


    _, transcript = make_transcript()
    states = tuple(
        StateEvidence(
            index=state.index,
            basis=state.basis,
            expected_bit=0 if state.eigenvalue > 0 else 1,
            probability_expected=0.5,
            matched=False,
        )
        for state in transcript.states
    )
    result = detect(detection_input(transcript, states=states))
    assert result.findings
    for finding in result.findings:
        assert finding.calibration.value == "UNCALIBRATED"
        assert finding.severity.value == "UNCALIBRATED"



def test_criterion_19_no_ml_exists() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in DETECTION_DIR.rglob("*.py")
    ).lower()
    for forbidden in ("sklearn", "tensorflow", "torch", "keras"):
        assert forbidden not in text, forbidden



def test_criterion_20_earlier_suites_still_exist() -> None:
    for name in ("quantum", "protocol", "security"):
        directory = REPO_ROOT / "tests" / name
        assert directory.is_dir()
        assert list(directory.rglob("test_*.py")), name



def test_criterion_21_m4_tests_exist() -> None:
    directory = REPO_ROOT / "tests" / "detection"
    assert directory.is_dir()
    assert len(list(directory.rglob("test_*.py"))) >= 10



def test_criterion_22_documentation_matches_implementation() -> None:
    from tests.detection.test_documentation import assert_documentation_matches

    assert_documentation_matches()



def test_criterion_23_no_unsupported_security_claims() -> None:
    forbidden_phrases = [
        "unconditional security",
        "always detected",
        "all attacks are covered",
        "formal cryptographic proof",
        "guarantees detection",
        "detects all attacks",
        "proves the identity",
    ]
    found: Set[str] = set()
    for path in DETECTION_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            if phrase in text:
                found.add(f"{path}: {phrase!r}")
    documentation = REPO_ROOT / "docs" / "security" / "detection-engine.md"
    text = documentation.read_text(encoding="utf-8").lower()
    for phrase in forbidden_phrases:
        if phrase in text:
            found.add(f"{documentation}: {phrase!r}")
    assert not found, found
