"""Tests for the feature extraction layer and its declared catalog."""

from __future__ import annotations

import pytest

from backend.detection import (
    FEATURE_CATALOG,
    DetectionFeatures,
    StateEvidence,
    analyse_basis_statistics,
)
from tests.detection.conftest import detection_input, features_for, make_transcript, valid_input


def test_catalog_covers_every_declared_feature() -> None:
    """Every catalogued feature must exist on the feature record, and vice versa."""
    declared = set(FEATURE_CATALOG)
    fields = set(DetectionFeatures.__dataclass_fields__)
    structural = {
        "mismatch",
        "disturbance",
        "fidelity",
        "basis",
        "redundancies",
        "notes",
    }
    assert declared == fields - structural


def test_every_descriptor_is_complete() -> None:
    for name, descriptor in FEATURE_CATALOG.items():
        assert descriptor.name == name
        for attribute in ("definition", "source", "meaning", "range", "failure_behaviour"):
            value = getattr(descriptor, attribute)
            assert isinstance(value, str) and value.strip(), (name, attribute)


def test_extracted_features_are_populated_for_a_valid_input() -> None:
    from backend.detection import ReplayRegistry

    replay = ReplayRegistry().check(session_id="a" * 32, nonce="b" * 64)
    features = features_for(valid_input(), replay=replay)
    for name in FEATURE_CATALOG:
        if name == "cross_verifier_disagreement":
            assert getattr(features, name) is None
            continue
        assert getattr(features, name) is not None, name
    assert features.nonce_freshness_state is True


def test_basis_statistics_count_and_rate_correctly() -> None:
    states = (
        StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=1.0, matched=True),
        StateEvidence(index=1, basis="Z", expected_bit=0, probability_expected=0.5, matched=False),
        StateEvidence(index=2, basis="X", expected_bit=0, probability_expected=1.0, matched=True),
        StateEvidence(index=3, basis="X", expected_bit=0, probability_expected=1.0, matched=True),
    )
    stats = analyse_basis_statistics(states)
    assert stats.observed_bases == ("X", "Z")
    assert stats.counts == {"Z": 2, "X": 2}
    assert stats.distribution == {"X": pytest.approx(0.5), "Z": pytest.approx(0.5)}
    assert stats.mismatch_counts == {"Z": 1}
    assert stats.mismatch_rates["Z"] == pytest.approx(0.5)
    assert stats.mismatch_rates["X"] == pytest.approx(0.0)
    assert stats.disturbance_counts == {"Z": 1}
    assert stats.disturbed_bases == ("Z",)


def test_basis_statistics_ignore_malformed_records() -> None:
    stats = analyse_basis_statistics(
        (
            StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=1.0, matched=True),
            StateEvidence(index=1, basis=None, expected_bit=0, probability_expected=1.0, matched=True),
        )
    )
    assert stats.counts == {"Z": 1}
    assert sum(stats.distribution.values()) == pytest.approx(1.0)


def test_basis_statistics_are_empty_without_usable_observations() -> None:
    stats = analyse_basis_statistics(())
    assert stats.observed_bases == ()
    assert stats.counts == {}
    assert stats.distribution == {}


def test_cross_verifier_disagreement_is_reported_as_unavailable() -> None:
    """The M2/M3 data model records one verifier per session, so no comparison exists."""
    descriptor = FEATURE_CATALOG["cross_verifier_disagreement"]
    assert descriptor.range == "always None at Milestone 4"
    assert "one verifier" in descriptor.failure_behaviour


def test_redundancies_are_declared_for_identical_signals() -> None:
    features = features_for(valid_input())
    assert "reconstruction_fidelity" in features.redundancies
    assert "verification_state_disturbance_rate" in features.redundancies
    assert any("no composite score" in note for note in features.notes)


def test_no_composite_score_feature_exists() -> None:
    fields = set(DetectionFeatures.__dataclass_fields__)
    for forbidden in ("security_score", "threat_score", "risk_score", "confidence"):
        assert forbidden not in fields


def test_features_serialize() -> None:
    features = features_for(detection_input(make_transcript()[1]))
    payload = features.to_dict()
    assert set(FEATURE_CATALOG) <= set(payload)
    assert payload["cross_verifier_disagreement"] is None
    assert payload["mismatch_rate"] == pytest.approx(0.0)
