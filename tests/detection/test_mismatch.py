"""Tests for mismatch analysis: exact calculations and failure behaviour."""

from __future__ import annotations

import pytest

from backend.detection import StateEvidence, analyse_mismatch


def records(pairs: list[tuple[bool, float]]) -> tuple[StateEvidence, ...]:
    """Build observations from ``(matched, probability)`` pairs."""
    return tuple(
        StateEvidence(
            index=index,
            basis="Z",
            expected_bit=0,
            probability_expected=probability,
            matched=matched,
        )
        for index, (matched, probability) in enumerate(pairs)
    )


def test_exact_mismatch_calculation() -> None:
    analysis = analyse_mismatch(records([(True, 1.0)] * 6 + [(False, 0.5)] * 2))
    assert analysis.n_total == 8
    assert analysis.n_valid == 8
    assert analysis.n_mismatch == 2
    assert analysis.mismatch_rate == pytest.approx(2 / 8)
    assert analysis.defined is True
    assert analysis.rate_estimate is not None
    assert analysis.rate_estimate.successes == 2


def test_all_matching_gives_zero_rate() -> None:
    analysis = analyse_mismatch(records([(True, 1.0)] * 4))
    assert analysis.mismatch_rate == 0.0
    assert analysis.n_mismatch == 0
    assert analysis.defined is True


def test_all_mismatching_gives_unit_rate() -> None:
    analysis = analyse_mismatch(records([(False, 0.0)] * 4))
    assert analysis.mismatch_rate == 1.0
    assert analysis.rate_estimate is not None
    assert analysis.rate_estimate.upper == 1.0


def test_zero_denominator_is_undefined_not_zero() -> None:
    analysis = analyse_mismatch(())
    assert analysis.n_valid == 0
    assert analysis.mismatch_rate is None
    assert analysis.rate_estimate is None
    assert analysis.defined is False
    assert any("undefined" in note for note in analysis.notes)


def test_malformed_observations_are_excluded_and_counted() -> None:
    malformed = (
        StateEvidence(index=0, basis=None, expected_bit=0, probability_expected=1.0, matched=True),
        StateEvidence(index=1, basis="Z", expected_bit=7, probability_expected=1.0, matched=True),
        StateEvidence(index=2, basis="Z", expected_bit=0, probability_expected=float("nan"), matched=True),
        StateEvidence(index=3, basis="Z", expected_bit=0, probability_expected=2.0, matched=True),
        StateEvidence(index=4, basis="Z", expected_bit=0, probability_expected=1.0, matched=None),
    )
    analysis = analyse_mismatch(records([(True, 1.0), (False, 0.4)]) + malformed)
    assert analysis.n_total == 7
    assert analysis.n_malformed == 5
    assert analysis.n_valid == 2
    assert analysis.n_mismatch == 1
    assert analysis.mismatch_rate == pytest.approx(0.5)
    assert any("malformed" in note for note in analysis.notes)


def test_missing_observations_are_reported_against_the_declared_count() -> None:
    analysis = analyse_mismatch(records([(True, 1.0)] * 3), declared_state_count=8)
    assert analysis.n_missing == 5
    assert analysis.n_valid == 3
    assert analysis.mismatch_rate == 0.0
    assert any("no observation" in note for note in analysis.notes)


def test_declared_count_smaller_than_supplied_is_not_treated_as_missing() -> None:
    analysis = analyse_mismatch(records([(True, 1.0)] * 5), declared_state_count=3)
    assert analysis.n_missing == 0
    assert analysis.n_valid == 5


def test_malformed_records_never_flip_the_rate() -> None:
    """Excluding malformed data must not silently improve or worsen the rate."""
    clean = records([(False, 0.2), (True, 1.0)])
    with_junk = clean + (
        StateEvidence(index=99, basis="Z", expected_bit=0, probability_expected=1.0, matched=None),
    )
    assert analyse_mismatch(clean).mismatch_rate == analyse_mismatch(with_junk).mismatch_rate


def test_analysis_serializes() -> None:
    payload = analyse_mismatch(records([(True, 1.0), (False, 0.3)])).to_dict()
    assert payload["mismatch_rate"] == pytest.approx(0.5)
    assert payload["rate_estimate"]["trials"] == 2
    assert payload["defined"] is True
