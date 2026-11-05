"""Tests for fidelity analysis and its declared redundancy."""

from __future__ import annotations

import pytest

from backend.detection import StateEvidence, analyse_fidelity


def records(probabilities: list[float], *, matched: bool = True) -> tuple[StateEvidence, ...]:
    return tuple(
        StateEvidence(
            index=index,
            basis="Z",
            expected_bit=0,
            probability_expected=probability,
            matched=matched,
        )
        for index, probability in enumerate(probabilities)
    )


def test_analytic_mean_and_minimum_fidelity() -> None:
    analysis = analyse_fidelity(records([1.0, 0.9, 0.8]), measurement_mode="projective-analytic")
    assert analysis.analytic_mean_fidelity == pytest.approx(0.9)
    assert analysis.analytic_min_fidelity == pytest.approx(0.8)
    assert analysis.mean_mismatch_probability == pytest.approx(0.1)
    assert analysis.defined is True


def test_ideal_session_has_unit_fidelity() -> None:
    analysis = analyse_fidelity(records([1.0] * 4), measurement_mode="projective-analytic")
    assert analysis.analytic_mean_fidelity == pytest.approx(1.0)
    assert analysis.mean_mismatch_probability == pytest.approx(0.0)


def test_no_sampled_frequency_in_deterministic_mode() -> None:
    analysis = analyse_fidelity(records([1.0, 0.5]), measurement_mode="projective-analytic")
    assert analysis.sampled_match_frequency is None
    assert analysis.sampled_match_count is None
    assert any("deterministic" in note for note in analysis.notes)


def test_sampled_frequency_is_reported_only_in_sampled_mode() -> None:
    observations = (
        StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=0.975, matched=True),
        StateEvidence(index=1, basis="Z", expected_bit=0, probability_expected=0.975, matched=True),
        StateEvidence(index=2, basis="Z", expected_bit=0, probability_expected=0.975, matched=False),
        StateEvidence(index=3, basis="Z", expected_bit=0, probability_expected=0.975, matched=False),
    )
    analysis = analyse_fidelity(observations, measurement_mode="sampled")
    assert analysis.sampled_match_count == 2
    assert analysis.sampled_match_frequency == pytest.approx(0.5)

    assert analysis.analytic_mean_fidelity == pytest.approx(0.975)
    assert any("estimator" in note for note in analysis.notes)


def test_redundancy_with_the_projective_match_probability_is_declared() -> None:
    analysis = analyse_fidelity(records([1.0, 0.5]), measurement_mode="sampled")
    assert any(
        "one number, not two" in note for note in analysis.notes
    )
    assert any("not the mismatch rate" in note for note in analysis.notes)


def test_undefined_without_usable_observations() -> None:
    analysis = analyse_fidelity(
        (StateEvidence(index=0, basis=None, expected_bit=0, probability_expected=None, matched=None),),
        measurement_mode="sampled",
    )
    assert analysis.defined is False
    assert analysis.analytic_mean_fidelity is None
    assert analysis.sampled_match_frequency is None
    assert analysis.n_malformed == 1


def test_serializes() -> None:
    payload = analyse_fidelity(records([1.0]), measurement_mode="sampled").to_dict()
    assert payload["analytic_mean_fidelity"] == pytest.approx(1.0)
    assert payload["sampled_match_frequency"] == pytest.approx(1.0)
