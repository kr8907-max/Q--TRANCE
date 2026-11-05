"""Tests for verification-state disturbance analysis."""

from __future__ import annotations

import pytest

from backend.detection import (
    DEFAULT_MEASUREMENT_TOLERANCE,
    StateEvidence,
    analyse_disturbance,
    analyse_mismatch,
    is_disturbed,
)


def records(
    probabilities: list[float],
    *,
    matched: bool = True,
    mismatched_indices: set[int] | None = None,
) -> tuple[StateEvidence, ...]:
    """Build observations from projective probabilities.

    ``mismatched_indices`` marks individual states whose finite-shot outcome
    disagreed, so the mismatch and disturbance statistics can be made to differ
    deliberately.
    """
    mismatched = mismatched_indices or set()
    return tuple(
        StateEvidence(
            index=index,
            basis="Z",
            expected_bit=0,
            probability_expected=probability,
            matched=(not matched) if index in mismatched else matched,
        )
        for index, probability in enumerate(probabilities)
    )


def test_exact_disturbance_calculation() -> None:
    analysis = analyse_disturbance(records([1.0, 1.0, 1.0, 0.975, 0.5, 0.5]))
    assert analysis.n_verification_states == 6
    assert analysis.n_disturbed == 3
    assert analysis.n_undisturbed == 3
    assert analysis.disturbance_rate == pytest.approx(0.5)
    assert analysis.defined is True


def test_a_state_exactly_at_the_reference_is_not_disturbed() -> None:
    assert is_disturbed(
        StateEvidence(
            index=0,
            basis="Z",
            expected_bit=0,
            probability_expected=1.0,
            matched=True,
        )
    ) is False


def test_tolerance_defines_the_boundary() -> None:
    just_below = 1.0 - DEFAULT_MEASUREMENT_TOLERANCE * 2
    just_above = 1.0 - DEFAULT_MEASUREMENT_TOLERANCE / 2
    assert is_disturbed(
        StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=just_below, matched=True)
    ) is True
    assert is_disturbed(
        StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=just_above, matched=True)
    ) is False


def test_any_nonzero_channel_deviation_saturates_the_rate() -> None:
    """A documented property: D_v is a detection indicator, not a magnitude one.

    The reference expectation is exact, so a depolarizing probability of 0.001
    disturbs every state just as an attack on every state would. The magnitude
    lives in the fidelity, which is asserted separately.
    """
    analysis = analyse_disturbance(records([0.99925] * 8))
    assert analysis.disturbance_rate == 1.0


def test_zero_denominator_is_undefined() -> None:
    analysis = analyse_disturbance(())
    assert analysis.n_verification_states == 0
    assert analysis.disturbance_rate is None
    assert analysis.defined is False
    assert analysis.identical_to_mismatch is False


def test_malformed_observations_are_excluded() -> None:
    analysis = analyse_disturbance(
        records([1.0, 0.5])
        + (StateEvidence(index=9, basis="Z", expected_bit=0, probability_expected=None, matched=True),)
    )
    assert analysis.n_malformed == 1
    assert analysis.n_verification_states == 2
    assert analysis.disturbance_rate == pytest.approx(0.5)


def test_disturbance_and_mismatch_are_declared_identical_when_they_are() -> None:
    """Deterministic mode: 'outcome disagreed' and 'state disturbed' coincide."""
    observations = records([1.0, 0.9, 0.8], mismatched_indices={1, 2})
    mismatch = analyse_mismatch(observations)
    disturbance = analyse_disturbance(observations, mismatch=mismatch)
    assert mismatch.n_mismatch == 2
    assert disturbance.n_disturbed == 2
    assert disturbance.identical_to_mismatch is True
    assert any("one signal, not two" in note for note in disturbance.notes)


def test_disturbance_and_mismatch_are_declared_distinct_when_they_are() -> None:
    """A finite-shot outcome frequency need not track the analytic disturbance."""
    observations = (
        StateEvidence(index=0, basis="Z", expected_bit=0, probability_expected=0.975, matched=True),
        StateEvidence(index=1, basis="Z", expected_bit=0, probability_expected=0.975, matched=False),
    )
    mismatch = analyse_mismatch(observations)
    disturbance = analyse_disturbance(observations, mismatch=mismatch)
    assert disturbance.identical_to_mismatch is False
    assert disturbance.disturbance_rate == 1.0
    assert mismatch.mismatch_rate == pytest.approx(0.5)
    assert any("distinct statistics" in note for note in disturbance.notes)


def test_terminology_never_mentions_decoy_states() -> None:
    """The statistic is not called 'decoy disturbance': no decoy protocol exists.

    The word may appear only inside the disclaimer that forbids it, and no decoy
    parameter may be defined anywhere in the module.
    """
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "backend"
        / "detection"
        / "disturbance.py"
    ).read_text(encoding="utf-8")
    assert 'called "decoy disturbance"' in source
    for forbidden in (
        "decoy_strength",
        "decoy_intensity",
        "decoy_ratio",
        "decoy_probability",
        "decoy_state",
    ):
        assert forbidden not in source


def test_missing_declared_states_are_reported() -> None:
    analysis = analyse_disturbance(records([1.0] * 3), declared_state_count=8)
    assert analysis.n_missing == 5
    assert analysis.n_verification_states == 3
