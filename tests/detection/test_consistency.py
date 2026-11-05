"""Tests for transcript and session integrity analysis.

These are protocol-structure checks, so the assertions are about the artifact --
the hash, the binding, the version, the addressing, the counts -- and never
about a qubit.
"""

from __future__ import annotations

import pytest

from backend.detection import (
    EvidenceCategory,
    analyse_consistency,
    detect,
)
from backend.protocol.models import PROTOCOL_VERSION
from tests.detection.conftest import (
    MESSAGE,
    detection_input,
    make_transcript,
    reseal_payload,
    tamper_metadata,
    tamper_state_identifier,
    valid_input,
    with_declared_state_count,
)


def test_a_valid_transcript_produces_no_violation() -> None:
    report = analyse_consistency(valid_input())
    assert report.violations == ()
    assert report.protocol_valid is True
    assert report.transcript_hash_valid is True
    assert report.message_binding_valid is True
    assert report.protocol_version_valid is True
    assert report.session_addressing_valid is True
    assert report.state_count_declared_matches_list is True
    assert report.state_count_declared_matches_observed is True
    assert report.state_sequence_metadata_consistent is True
    assert report.declared_state_sequence_matches_derivation is True


def test_invalid_transcript_hash_is_detected() -> None:
    detection = valid_input(declared_transcript_hash="f" * 64)
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is False
    assert report.protocol_valid is False
    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.TRANSCRIPT_INTEGRITY)
    assert len(findings) == 1
    assert findings[0].blocking is True


def test_modified_message_breaks_the_binding() -> None:
    detection = valid_input(message="a different transfer entirely")
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is True
    assert report.message_binding_valid is False
    result = detect(detection)
    assert result.overall_status.value == "INTEGRITY_VIOLATION"
    assert result.findings_for(EvidenceCategory.TRANSCRIPT_INTEGRITY)


def test_modified_nonce_breaks_the_binding() -> None:
    _, transcript = make_transcript()
    payload = reseal_payload({**transcript.to_dict(), "nonce": "c" * 64})
    detection = detection_input(transcript, payload=payload)
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is True
    assert report.message_binding_valid is False


def test_modified_session_identifier_breaks_the_binding() -> None:
    _, transcript = make_transcript()
    payload = reseal_payload({**transcript.to_dict(), "session_id": "d" * 32})
    detection = detection_input(transcript, payload=payload)
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is True
    assert report.message_binding_valid is False


def test_protocol_version_mismatch_is_detected() -> None:
    _, transcript = make_transcript(protocol_version="RQDS-TP-9.9")
    detection = detection_input(transcript)
    report = analyse_consistency(detection)
    assert report.observed_protocol_version == "RQDS-TP-9.9"
    assert report.protocol_version_valid is False
    assert report.message_binding_valid is True
    result = detect(detection)
    assert result.findings_for(EvidenceCategory.CONSISTENCY_ANOMALY)


def test_a_transcript_for_another_verifier_is_detected() -> None:
    _, transcript = make_transcript()
    detection = detection_input(transcript, verifier_context_id="carol")
    report = analyse_consistency(detection)
    assert report.session_addressing_valid is False
    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.CONSISTENCY_ANOMALY)
    assert any(
        item.observed_values.get("transcript_verifier_id") == "bob" for item in findings
    )


def test_declared_state_count_against_the_declared_list_is_detected() -> None:
    _, transcript = make_transcript()
    payload = with_declared_state_count(transcript.to_dict(), 9)
    detection = detection_input(transcript, payload=payload)
    report = analyse_consistency(detection)
    assert report.state_count_declared_matches_list is False
    assert report.protocol_valid is False


def test_declared_state_count_against_the_observations_is_detected() -> None:
    detection = valid_input(declared_state_count=99)
    report = analyse_consistency(detection)
    assert report.state_count_declared_matches_observed is False
    result = detect(detection)
    assert result.findings_for(EvidenceCategory.CONSISTENCY_ANOMALY)


def test_declared_state_sequence_that_contradicts_the_derivation_is_detected() -> None:
    """The 'unexpected state sequence' evidence: the artifact is otherwise intact."""
    _, transcript = make_transcript()
    payload = tamper_state_identifier(transcript.to_dict(), index=0)
    detection = detection_input(transcript, payload=payload)
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is True
    assert report.message_binding_valid is True
    assert report.state_sequence_metadata_consistent is True
    assert report.declared_state_sequence_matches_derivation is False

    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY)
    assert len(findings) == 1
    assert findings[0].severity.value == "HIGH"
    assert "does not correspond to this message" in findings[0].explanation


def test_tampered_sequence_metadata_is_detected() -> None:
    _, transcript = make_transcript()
    payload = tamper_metadata(transcript.to_dict())
    detection = detection_input(transcript, payload=payload)
    report = analyse_consistency(detection)
    assert report.transcript_hash_valid is True
    assert report.state_sequence_metadata_consistent is False
    assert report.declared_state_sequence_matches_derivation is True


def test_malformed_transcript_is_reported_as_a_finding_not_an_exception() -> None:
    detection = valid_input(
        transcript_payload=None,
        transcript_parse_error="transcript is missing fields ['nonce']",
    )
    report = analyse_consistency(detection)
    assert report.transcript_parse_ok is False
    assert report.protocol_valid is False
    assert any("could not be parsed" in violation for violation in report.violations)

    result = detect(detection)
    findings = result.findings_for(EvidenceCategory.TRANSCRIPT_INTEGRITY)
    assert len(findings) == 1
    assert result.overall_status.value == "INTEGRITY_VIOLATION"


def test_missing_transcript_yields_unavailable_not_a_violation() -> None:
    detection = valid_input(transcript_payload=None, transcript_parse_error=None)
    report = analyse_consistency(detection)
    assert report.transcript_supplied is False
    assert report.violations == ()
    assert report.protocol_valid is True
    assert any("no transcript was supplied" in note for note in report.notes)


def test_unparseable_protocol_identity_is_reported_without_raising() -> None:
    detection = valid_input(
        session_id=None,
        nonce=None,
        protocol_version=None,
        message_binding=None,
        declared_transcript_hash=None,
        signer_id=None,
        verifier_id=None,
        created_at=None,
    )
    report = analyse_consistency(detection)
    assert report.protocol_valid is False
    joined = " | ".join(report.violations)
    assert "message_binding" in joined
    assert "protocol version" in joined
    assert "transcript_hash" in joined


def test_report_serializes() -> None:
    payload = analyse_consistency(valid_input()).to_dict()
    assert payload["protocol_valid"] is True
    assert payload["violations"] == []
    assert payload["expected_protocol_versions"] == [PROTOCOL_VERSION]


@pytest.mark.parametrize(
    "field, value",
    [
        ("declared_transcript_hash", "not-hex"),
        ("protocol_version", "nonsense"),
    ],
)
def test_odd_field_values_never_raise(field: str, value: str) -> None:
    report = analyse_consistency(valid_input(**{field: value}))
    assert isinstance(report.violations, tuple)
