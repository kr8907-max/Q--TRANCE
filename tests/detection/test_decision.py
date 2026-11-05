"""Tests for the decision model."""

from __future__ import annotations

import json

import pytest

from backend.detection import (
    DetectionResult,
    EvidenceCategory,
    StateEvidence,
    detect,
)
from tests.detection.conftest import detection_input, make_transcript, valid_input


def disturbed_input(**overrides: object):
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
    return detection_input(transcript, states=states, **overrides)


def test_clear_session() -> None:
    result = detect(valid_input())
    assert isinstance(result, DetectionResult)
    assert result.overall_status.value == "CLEAR"
    assert result.protocol_valid is True
    assert result.findings == ()
    assert result.blocking_findings() == ()
    assert "No protocol, authorization or measurement evidence deviated" in result.explanation


def test_integrity_violation() -> None:
    result = detect(valid_input(declared_transcript_hash="f" * 64))
    assert result.overall_status.value == "INTEGRITY_VIOLATION"
    assert result.protocol_valid is False
    assert result.blocking_findings()


def test_authorization_violation_does_not_break_protocol_validity() -> None:
    """Authorization is a policy axis, not a protocol-structure property."""
    result = detect(valid_input(signer_id="eve", authorized_signers=("alice",)))
    assert result.overall_status.value == "AUTHORIZATION_VIOLATION"
    assert result.protocol_valid is True
    assert result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)


def test_quantum_anomaly() -> None:
    result = detect(disturbed_input())
    assert result.overall_status.value == "QUANTUM_ANOMALY"
    assert result.protocol_valid is True
    assert result.blocking_findings() == ()


def test_multiple_findings_when_two_families_are_present() -> None:
    result = detect(
        disturbed_input(signer_id="eve", authorized_signers=("alice",))
    )
    assert result.overall_status.value == "MULTIPLE_FINDINGS"
    assert result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)
    assert result.findings_for(EvidenceCategory.CHANNEL_ANOMALY)
    assert len(result.categories()) >= 2


def test_finding_identifiers_are_deterministic_and_ordered() -> None:
    first = detect(disturbed_input(signer_id="eve", authorized_signers=("alice",)))
    second = detect(disturbed_input(signer_id="eve", authorized_signers=("alice",)))
    assert [item.finding_id for item in first.findings] == [
        item.finding_id for item in second.findings
    ]
    assert first.findings[0].finding_id == "SIGNER_AUTHORIZATION-01"
    assert all(item.finding_id for item in first.findings)


def test_diagnostic_statistics_carry_no_decision() -> None:
    statistics = detect(disturbed_input()).diagnostic_statistics()
    assert statistics["mismatch_rate"] == 1.0
    assert statistics["mismatch_interval"]["trials"] == 4
    assert statistics["disturbance_rate"] == 1.0
    assert statistics["sample_size"] == 4
    assert statistics["multiple_testing_handling"] == "not implemented at Milestone 4"
    for forbidden in ("status", "verdict", "decision", "threshold", "accept", "reject"):
        assert forbidden not in statistics


def test_no_security_score_is_produced() -> None:
    """No key anywhere in the result may be a score."""

    def keys(value: object):
        if isinstance(value, dict):
            for key, item in value.items():
                yield str(key)
                yield from keys(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from keys(item)

    payload = detect(disturbed_input()).to_dict()
    offenders = [key for key in keys(payload) if "score" in key.lower()]
    assert offenders == [], offenders


def test_result_serializes_completely() -> None:
    payload = detect(valid_input()).to_dict()
    assert payload["overall_status"] == "CLEAR"
    assert payload["protocol_valid"] is True
    assert payload["finding_count"] == 0
    assert "diagnostic_statistics" in payload
    assert any("observable evidence only" in note for note in payload["notes"])
    assert any("no security score" in note for note in payload["notes"])


def test_result_is_frozen() -> None:
    result = detect(valid_input())
    with pytest.raises(Exception):
        result.overall_status = None  # type: ignore[misc]


def test_findings_for_unknown_category_is_empty() -> None:
    result = detect(valid_input())
    assert result.findings_for(EvidenceCategory.REPLAY) == ()
    assert result.categories() == ()


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"declared_transcript_hash": "f" * 64}, "INTEGRITY_VIOLATION"),
        ({"signer_id": "eve", "authorized_signers": ("alice",)}, "AUTHORIZATION_VIOLATION"),
    ],
)
def test_status_is_categorical_not_percentage(overrides: dict, expected: str) -> None:
    """The status names a family; it never reports how close a number came."""
    result = detect(valid_input(**overrides))
    assert result.overall_status.value == expected
