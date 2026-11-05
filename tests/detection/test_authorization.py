"""Tests for signer and verifier authorization evidence.

The two checks are tested separately and asserted to be separate: the milestone
requires that they are not merged into a single "identity mismatch".
"""

from __future__ import annotations

import pytest

from backend.detection import (
    EvidenceCategory,
    analyse_authorization,
    detect,
)
from tests.detection.conftest import detection_input, make_transcript, valid_input


def test_authorized_signer_and_verifier_produce_no_finding() -> None:
    detection = valid_input()
    report = analyse_authorization(detection)
    assert report.signer.authorized is True
    assert report.verifier.authorized is True
    assert report.signer.violated is False
    assert report.verifier.violated is False
    result = detect(detection)
    assert result.findings == ()
    assert result.overall_status.value == "CLEAR"


def test_unauthorized_signer_is_detected_as_a_signer_finding() -> None:
    detection = valid_input(
        signer_id="eve",
        authorized_signers=("alice",),
    )
    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)
    assert len(findings) == 1
    assert result.findings_for(EvidenceCategory.VERIFIER_AUTHORIZATION) == ()
    assert result.overall_status.value == "AUTHORIZATION_VIOLATION"

    finding = findings[0]
    assert finding.severity.value == "CRITICAL"
    assert finding.blocking is True
    assert finding.observed_values["presented_signer"] == "eve"
    assert finding.comparison_values["authorized_signers"] == ["alice"]
    assert "eve" in finding.explanation
    assert "not among the authorised signer identities" in finding.explanation


def test_unauthorized_verifier_is_detected_as_a_verifier_finding() -> None:
    detection = valid_input(
        verifier_id="mallory",
        verifier_context_id="mallory",
        authorized_verifiers=("bob",),
    )
    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.VERIFIER_AUTHORIZATION)
    assert len(findings) == 1
    assert result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION) == ()

    finding = findings[0]
    assert finding.observed_values["presented_verifier"] == "mallory"
    assert "mallory" in finding.explanation
    assert "verifier" in finding.explanation


def test_the_two_violations_are_reported_separately() -> None:
    detection = valid_input(
        signer_id="eve",
        verifier_id="mallory",
        verifier_context_id="mallory",
        authorized_signers=("alice",),
        authorized_verifiers=("bob",),
    )
    result = detect(detection)
    assert len(result.findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)) == 1
    assert len(result.findings_for(EvidenceCategory.VERIFIER_AUTHORIZATION)) == 1
    assert result.overall_status.value == "AUTHORIZATION_VIOLATION"
    assert result.protocol_valid is True


def test_authorization_is_recomputed_not_trusted() -> None:
    """A recorded flag that disagrees with the membership test is surfaced."""
    detection = valid_input(
        signer_id="eve",
        authorized_signers=("alice",),
        reported_signer_authorized=True,
    )
    report = analyse_authorization(detection)
    assert report.signer.authorized is False
    assert report.signer.reported_authorized is True
    assert report.signer.reported_agrees is False
    assert any("disagrees with the recomputed" in note for note in report.notes)


def test_identity_is_not_claimed_to_be_proven() -> None:
    report = analyse_authorization(valid_input())
    assert any("not proof of identity" in note for note in report.notes)
    assert any("quantum measurement" in note for note in report.notes)


def test_missing_identity_yields_unavailable_not_a_violation() -> None:
    _, transcript = make_transcript()
    payload = {**transcript.to_dict(), "signer_id": None}
    detection = detection_input(transcript, signer_id=None, payload=payload)
    report = analyse_authorization(detection)
    assert report.signer.authorized is None
    assert report.signer.violated is False
    assert "could not be established" in report.signer.reason
    assert detect(detection).findings_for(EvidenceCategory.SIGNER_AUTHORIZATION) == ()


def test_missing_authorized_set_yields_unavailable_not_a_violation() -> None:
    detection = valid_input(authorized_signers=())
    report = analyse_authorization(detection)
    assert report.signer.authorized is None
    assert report.signer.violated is False
    assert "no authorised signer identities were supplied" in report.signer.reason


def test_authorization_findings_never_cite_quantum_metrics() -> None:
    detection = valid_input(signer_id="eve", authorized_signers=("alice",))
    finding = detect(detection).findings_for(EvidenceCategory.SIGNER_AUTHORIZATION)[0]
    assert finding.source_metrics == ("signer_authorization_validity",)
    assert "not proof of identity" in finding.explanation


@pytest.mark.parametrize(
    "role, category",
    [
        ("signer", EvidenceCategory.SIGNER_AUTHORIZATION),
        ("verifier", EvidenceCategory.VERIFIER_AUTHORIZATION),
    ],
)
def test_check_serializes_with_its_role(role: str, category: EvidenceCategory) -> None:
    detection = valid_input(
        signer_id="eve",
        authorized_signers=("alice",),
        verifier_id="mallory",
        verifier_context_id="mallory",
        authorized_verifiers=("bob",),
    )
    report = analyse_authorization(detection)
    payload = report.to_dict()
    check = payload[role]
    assert check["role"] == role
    assert check["authorized"] is False
    assert check["violated"] is True
    assert detect(detection).findings_for(category)
