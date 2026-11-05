"""Tests for quantum and channel anomaly evidence.

These are the statistical findings. The assertions are about what the evidence
*says*, not about what caused it: no test in this module claims an attack type.
"""

from __future__ import annotations

import pytest

from backend.attacks import AttackConfig
from backend.detection import (
    DetectorParameters,
    EvidenceCategory,
    StateEvidence,
    detect,
)
from backend.noise import NoiseConfig
from backend.simulation import ScenarioConfig
from tests.detection.conftest import (
    BASE,
    detection_input,
    end_to_end_input,
    make_transcript,
)


def noisy(**overrides: object) -> ScenarioConfig:
    return ScenarioConfig(**{**BASE, "noise": NoiseConfig("depolarizing", 0.05), **overrides})







def test_ideal_session_is_clear() -> None:
    result = detect(end_to_end_input(ScenarioConfig(**BASE)))
    assert result.overall_status.value == "CLEAR"
    assert result.findings == ()
    assert result.protocol_valid is True
    assert result.features.mismatch_rate == 0.0
    assert result.features.verification_state_disturbance_rate == 0.0
    assert result.features.reconstruction_fidelity == pytest.approx(1.0, abs=1e-9)


def test_honest_noise_is_reported_as_a_channel_anomaly_only() -> None:
    """Noise must not be dressed up as a protocol problem, nor called an attack."""
    result = detect(end_to_end_input(noisy()))
    assert result.overall_status.value == "QUANTUM_ANOMALY"
    assert result.protocol_valid is True
    assert result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)
    for category in (
        EvidenceCategory.TRANSCRIPT_INTEGRITY,
        EvidenceCategory.CONSISTENCY_ANOMALY,
        EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
        EvidenceCategory.REPLAY,
        EvidenceCategory.SIGNER_AUTHORIZATION,
        EvidenceCategory.VERIFIER_AUTHORIZATION,
    ):
        assert result.findings_for(category) == ()


def test_disturbance_evidence_reports_magnitude_and_affected_bases() -> None:
    config = noisy(
        attack=AttackConfig(
            "intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"}
        )
    )
    result = detect(end_to_end_input(config))
    finding = result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)[0]
    assert finding.severity.value == "UNCALIBRATED"
    assert finding.calibration.value == "UNCALIBRATED"
    assert finding.blocking is False
    assert finding.observed_values["disturbed_state_count"] > 0
    assert finding.observed_values["mean_fidelity"] < 1.0
    assert finding.observed_values["affected_bases"]
    assert "does not distinguish those causes" in finding.explanation
    assert finding.source_metrics == (
        "verification_state_disturbance_rate",
        "reconstruction_fidelity",
    )


def test_low_fidelity_is_visible_and_separate_from_the_rate() -> None:
    config = noisy(
        attack=AttackConfig(
            "channel_tampering", 1.0, seed=3, parameters={"pauli": "X"}
        )
    )
    result = detect(end_to_end_input(config))
    assert result.features.reconstruction_fidelity < 0.9
    assert result.features.fidelity.analytic_min_fidelity <= result.features.reconstruction_fidelity
    assert result.features.mismatch.defined


def test_basis_specific_anomaly_is_reported() -> None:
    """A disturbance confined to one basis must be reported as confined."""
    _, transcript = make_transcript()
    target = transcript.states[0].basis
    states = tuple(
        StateEvidence(
            index=state.index,
            basis=state.basis,
            expected_bit=0 if state.eigenvalue > 0 else 1,
            probability_expected=(0.5 if state.basis == target else 1.0),
            matched=(state.basis != target),
        )
        for state in transcript.states
    )
    result = detect(detection_input(transcript, states=states))
    finding = result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)[0]
    assert finding.observed_values["affected_bases"] == [target]
    assert target in finding.explanation
    undisturbed = {
        basis: rate
        for basis, rate in finding.observed_values["per_basis_disturbance_rates"].items()
        if basis != target
    }
    assert all(rate == 0.0 for rate in undisturbed.values())







def test_deterministic_mode_reports_one_anomaly_not_two() -> None:
    """In deterministic mode mismatch and disturbance are one signal."""
    result = detect(end_to_end_input(noisy()))
    assert result.features.disturbance.identical_to_mismatch is True
    assert result.findings_for(EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY) == ()
    assert "verification_state_disturbance_rate" in result.features.redundancies
    assert any(
        "one signal" in note for note in result.features.redundancies.values()
    )


def test_sampled_mode_reports_both_because_they_differ() -> None:
    config = ScenarioConfig(
        **{
            **BASE,
            "measurement_mode": "sampled",
            "shot_count": 1024,
            "noise": NoiseConfig("depolarizing", 0.05),
            "attack": AttackConfig(
                "intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"}
            ),
        }
    )
    result = detect(end_to_end_input(config))
    assert result.features.disturbance.identical_to_mismatch is False
    assert result.features.mismatch.n_mismatch > 0
    outcome = result.findings_for(EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY)
    assert len(outcome) == 1
    assert outcome[0].calibration.value == "UNCALIBRATED"
    assert outcome[0].observed_values["measurement_mode"] == "sampled"
    assert result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)
    assert result.overall_status.value == "QUANTUM_ANOMALY"







def disturbed_input():
    _, transcript = make_transcript()
    states = tuple(
        StateEvidence(
            index=state.index,
            basis=state.basis,
            expected_bit=0 if state.eigenvalue > 0 else 1,
            probability_expected=0.9,
            matched=False,
        )
        for state in transcript.states
    )
    return detection_input(transcript, states=states)


def test_without_a_reference_the_severity_is_uncalibrated() -> None:
    finding = detect(disturbed_input()).findings_for(EvidenceCategory.CHANNEL_ANOMALY)[0]
    assert finding.severity.value == "UNCALIBRATED"
    assert finding.calibration.value == "UNCALIBRATED"
    assert finding.comparison_values == {}


def test_a_reference_above_the_observation_suppresses_the_finding() -> None:
    parameters = DetectorParameters(reference_disturbance_rate=1.0)
    result = detect(disturbed_input(), parameters=parameters)
    assert result.findings_for(EvidenceCategory.CHANNEL_ANOMALY) == ()


def test_a_reference_excluded_by_the_sample_gives_a_high_severity() -> None:
    parameters = DetectorParameters(reference_disturbance_rate=0.1)
    finding = detect(disturbed_input(), parameters=parameters).findings_for(
        EvidenceCategory.CHANNEL_ANOMALY
    )[0]
    assert finding.severity.value == "HIGH"
    assert finding.calibration.value == "CALIBRATED"
    assert finding.comparison_values["reference_disturbance_rate"] == 0.1


def test_a_reference_inside_the_interval_gives_a_moderate_severity() -> None:
    parameters = DetectorParameters(reference_disturbance_rate=0.5)
    finding = detect(disturbed_input(), parameters=parameters).findings_for(
        EvidenceCategory.CHANNEL_ANOMALY
    )[0]
    assert finding.severity.value == "MODERATE"
    assert finding.calibration.value == "CALIBRATED"







def test_ideal_noisy_and_noisy_attacked_are_all_processable() -> None:
    """The detector must accept all three without knowing which produced which."""
    configs = {
        "ideal": ScenarioConfig(**BASE),
        "noisy": noisy(),
        "noisy_attacked": noisy(
            attack=AttackConfig(
                "channel_tampering", 0.5, seed=3, parameters={"pauli": "X"}
            )
        ),
    }
    for label, config in configs.items():
        result = detect(end_to_end_input(config))
        assert result.overall_status.value in {"CLEAR", "QUANTUM_ANOMALY"}, label
        assert result.protocol_valid is True, label
        assert result.diagnostic_statistics()["sample_size"] == BASE["state_count"], label


def test_noise_is_never_classified_as_an_attack() -> None:
    """No finding may attribute the observation to an attack."""
    import json

    result = detect(end_to_end_input(noisy()))
    assert result.findings, "a noisy session must produce evidence"
    for finding in result.findings:
        assert "ATTACK" not in finding.category.value
        blob = (
            finding.explanation
            + " "
            + json.dumps(finding.observed_values, default=str)
        ).lower()
        for forbidden in (
            "attack detected",
            "detected an attack",
            "is an attack",
            "confirms an attack",
            "intercept-resend detected",
            "attack confirmed",
        ):
            assert forbidden not in blob, forbidden

    assert any(
        "does not distinguish those causes" in finding.explanation
        for finding in result.findings
    )
