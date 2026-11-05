"""Tests for the replay registry and replay evidence.

Replay is a protocol/session identity property, so these tests never touch a
quantum state: the registry is exercised on identifiers alone.
"""

from __future__ import annotations

import pytest

from backend.detection import (
    EvidenceCategory,
    ReplayEvidence,
    ReplayRegistry,
    detect,
)
from tests.detection.conftest import detection_input, make_transcript, valid_input


def test_a_fresh_session_is_not_flagged() -> None:
    registry = ReplayRegistry()
    evidence = registry.check(session_id="s1", nonce="n1", transcript_hash="h1")
    assert evidence.available is True
    assert evidence.any_reuse is False
    assert evidence.first_observation is True
    assert evidence.session_reused is False
    assert evidence.nonce_reused is False
    assert evidence.transcript_reused is False


def test_repeated_session_is_flagged() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    evidence = registry.observe(session_id="s1", nonce="n2", transcript_hash="h2")
    assert evidence.session_reused is True
    assert evidence.nonce_reused is False
    assert evidence.transcript_reused is False
    assert evidence.first_observation is False


def test_repeated_nonce_is_flagged() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    evidence = registry.observe(session_id="s2", nonce="n1", transcript_hash="h2")
    assert evidence.nonce_reused is True
    assert evidence.session_reused is False
    assert evidence.transcript_reused is False


def test_repeated_transcript_is_flagged() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    evidence = registry.observe(session_id="s2", nonce="n2", transcript_hash="h1")
    assert evidence.transcript_reused is True
    assert evidence.session_reused is False
    assert evidence.nonce_reused is False


def test_check_is_pure_and_observe_records() -> None:
    """``check`` must not change the answer for the next question."""
    registry = ReplayRegistry()
    first = registry.check(session_id="s1", nonce="n1", transcript_hash="h1")
    second = registry.check(session_id="s1", nonce="n1", transcript_hash="h1")
    assert first.any_reuse is False
    assert second.any_reuse is False
    assert len(registry) == 0

    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    assert len(registry) == 1
    assert registry.check(session_id="s1", nonce="n1", transcript_hash="h1").any_reuse


def test_reset_empties_the_ledger() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    assert len(registry) == 1
    registry.reset()
    assert len(registry) == 0
    assert registry.snapshot() == {
        "sessions": frozenset(),
        "nonces": frozenset(),
        "transcripts": frozenset(),
    }
    assert registry.check(session_id="s1", nonce="n1", transcript_hash="h1").any_reuse is False


def test_malformed_input_is_safe_and_never_recorded() -> None:
    registry = ReplayRegistry()
    for bad in (None, "", 17, [], {}, True):
        evidence = registry.check(session_id=bad, nonce=bad, transcript_hash=bad)
        assert evidence.available is False
        assert evidence.first_observation is None
        assert evidence.any_reuse is False
        assert evidence.reason is not None
        registry.record(session_id=bad, nonce=bad, transcript_hash=bad)
    assert len(registry) == 0


def test_partially_malformed_input_checks_only_what_is_available() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce=None, transcript_hash="h1")
    evidence = registry.check(session_id=None, nonce=None, transcript_hash="h1")
    assert evidence.available is True
    assert evidence.transcript_reused is True
    assert evidence.observed_session_id is None


def test_snapshot_exposes_the_ledger_immutably() -> None:
    registry = ReplayRegistry()
    registry.observe(session_id="s1", nonce="n1", transcript_hash="h1")
    snapshot = registry.snapshot()
    assert snapshot["sessions"] == frozenset({"s1"})
    assert snapshot["nonces"] == frozenset({"n1"})
    assert snapshot["transcripts"] == frozenset({"h1"})


def test_detector_reports_replay_only_on_the_second_event() -> None:
    _, transcript = make_transcript()
    detection = detection_input(transcript)
    registry = ReplayRegistry()

    first = detect(detection, replay_registry=registry, consume=True)
    assert first.overall_status.value == "CLEAR"
    assert first.findings == ()

    second = detect(detection, replay_registry=registry, consume=True)
    assert second.overall_status.value == "INTEGRITY_VIOLATION"
    findings = second.findings_for(EvidenceCategory.REPLAY)
    assert len(findings) == 1
    assert findings[0].blocking is True
    assert findings[0].observed_values["reused_identifiers"] == [
        "session_id",
        "nonce",
        "transcript_hash",
    ]


def test_detector_is_side_effect_free_by_default() -> None:
    detection = valid_input()
    registry = ReplayRegistry()
    for _ in range(3):
        result = detect(detection, replay_registry=registry)
        assert result.overall_status.value == "CLEAR"
    assert len(registry) == 0


def test_without_a_registry_replay_evidence_is_unavailable_not_absent() -> None:
    result = detect(valid_input())
    assert result.features.nonce_freshness_state is None
    assert result.overall_status.value == "CLEAR"
    assert any(
        "replay history" in note for note in result.features.notes
    )


def test_replay_finding_never_cites_quantum_evidence() -> None:
    _, transcript = make_transcript()
    detection = detection_input(transcript)
    registry = ReplayRegistry()
    detect(detection, replay_registry=registry, consume=True)
    finding = detect(detection, replay_registry=registry, consume=True).findings_for(
        EvidenceCategory.REPLAY
    )[0]
    assert "nonce_freshness_state" in finding.source_metrics
    assert all(
        "disturbance" not in metric and "fidelity" not in metric
        for metric in finding.source_metrics
    )
    assert any("no quantum disturbance" in note for note in finding.notes)


def test_evidence_serializes() -> None:
    evidence = ReplayRegistry().check(session_id="s1", nonce="n1", transcript_hash="h1")
    payload = evidence.to_dict()
    assert isinstance(evidence, ReplayEvidence)
    assert payload["available"] is True
    assert payload["any_reuse"] is False
