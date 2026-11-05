"""The assumption register.

Every statistical statement in this project rests on assumptions, and the
honest way to report a bound is to say which ones. These tests pin that the
register is populated, that the status vocabulary distinguishes "exact" from
"approximate" rather than collapsing them, that the homogeneity assumption is
downgraded for the channels it does not hold for, and that the register records
the two invariants the whole milestone depends on -- honest-only calibration and
a label-free decision.
"""

from __future__ import annotations

import pytest

from backend.security.assumptions import (
    EXACT_STATUSES,
    REFERENCE_ASSUMPTIONS,
    WEAK_STATUSES,
    assumption_dict,
    reference_assumptions,
    summarise_assumptions,
)
from backend.security.models import AssumptionStatus


def test_the_status_vocabulary_separates_exact_from_approximate() -> None:
    assert AssumptionStatus.EXACT in EXACT_STATUSES
    assert AssumptionStatus.SATISFIED in EXACT_STATUSES


    assert AssumptionStatus.APPROXIMATE in WEAK_STATUSES
    assert AssumptionStatus.NOT_VERIFIED in WEAK_STATUSES
    assert AssumptionStatus.VIOLATED in WEAK_STATUSES
    assert not (set(EXACT_STATUSES) & set(WEAK_STATUSES))


def test_every_assumption_states_its_consequence_if_violated() -> None:
    for assumption in REFERENCE_ASSUMPTIONS:
        assert assumption.key
        assert assumption.statement
        assert assumption.consequence_if_violated
        assert assumption.status in set(AssumptionStatus)


def test_the_register_records_the_calibration_and_decision_invariants() -> None:
    keys = {assumption.key for assumption in REFERENCE_ASSUMPTIONS}
    for required in (
        "calibration_is_honest_only",
        "calibration_and_evaluation_are_disjoint",
        "no_label_reaches_the_decision",
        "single_primary_statistical_test",
        "finite_sample_bound_is_not_a_security_parameter",
    ):
        assert required in keys, required


def test_the_finite_sample_bound_assumption_points_at_the_type_guard() -> None:
    by_key = {assumption.key: assumption for assumption in REFERENCE_ASSUMPTIONS}
    assumption = by_key["finite_sample_bound_is_not_a_security_parameter"]
    assert assumption.status is AssumptionStatus.EXACT


    assert "raises if constructed with True" in assumption.evidence







def test_the_reference_register_is_populated() -> None:
    register = reference_assumptions()
    assert len(register.assumptions) == len(REFERENCE_ASSUMPTIONS)
    assert all(assumption.statement for assumption in register.assumptions)


def test_the_assumptions_that_rest_on_published_results_cite_them() -> None:




    by_key = {assumption.key: assumption for assumption in REFERENCE_ASSUMPTIONS}
    assert "Clopper" in by_key["independence_within_session"].citation
    assert "Clopper" in by_key["homogeneous_mismatch_probability"].citation
    assert "Hoeffding" in by_key[
        "finite_sample_bound_is_not_a_security_parameter"
    ].citation


def test_an_assumption_without_a_citation_is_a_project_invariant() -> None:



    for assumption in REFERENCE_ASSUMPTIONS:
        if assumption.citation is None:
            assert assumption.evidence, assumption.key


def test_the_reference_register_has_no_violated_assumption() -> None:
    summary = summarise_assumptions(reference_assumptions())
    assert summary["summary"]["violated"] == 0


def test_the_reference_register_is_mostly_exact() -> None:
    summary = summarise_assumptions(reference_assumptions())
    assert summary["summary"]["exact"] >= 10
    assert summary["summary"]["approximate"] == 0


def test_the_non_adaptive_attack_assumption_is_weak() -> None:


    summary = summarise_assumptions(reference_assumptions())
    assert "attacks_are_non_adaptive" in summary["weaker_than_exact"]


    by_key = {a.key: a for a in REFERENCE_ASSUMPTIONS}
    assert by_key["attacks_are_non_adaptive"].status is AssumptionStatus.SATISFIED


def test_the_homogeneity_assumption_is_exact_for_a_depolarizing_channel() -> None:


    register = reference_assumptions(noise_type="depolarizing", measurement_mode="sampled")
    by_key = {assumption.key: assumption for assumption in register.assumptions}
    assert by_key["homogeneous_mismatch_probability"].status is AssumptionStatus.EXACT


@pytest.mark.parametrize("noise_type", ["bit_flip", "phase_flip", "bit_phase_flip"])
def test_the_homogeneity_assumption_is_approximate_for_flip_channels(
    noise_type: str,
) -> None:



    register = reference_assumptions(noise_type=noise_type, measurement_mode="sampled")
    by_key = {assumption.key: assumption for assumption in register.assumptions}
    assert by_key["homogeneous_mismatch_probability"].status is (
        AssumptionStatus.APPROXIMATE
    )


def test_a_flip_channel_makes_the_summary_report_a_weaker_assumption() -> None:
    summary = summarise_assumptions(reference_assumptions(noise_type="bit_flip"))
    assert summary["summary"]["approximate"] >= 1
    assert "homogeneous_mismatch_probability" in summary["by_status"]["approximate"]


def test_the_register_reflects_the_measurement_mode() -> None:
    analytic = reference_assumptions(measurement_mode="projective-analytic")
    sampled = reference_assumptions(measurement_mode="sampled")
    by_key = {
        mode: {a.key: a for a in register.assumptions}
        for mode, register in (
            ("projective-analytic", analytic),
            ("sampled", sampled),
        )
    }
    key = "measurement_mode_is_the_operational_definition"



    evidence = by_key["sampled"][key].evidence
    assert "projective-analytic" in evidence
    assert "sampled" in evidence

    assert analytic.assumptions == sampled.assumptions


def test_the_summary_counts_partition_the_register() -> None:
    summary = summarise_assumptions(reference_assumptions())
    counted = sum(summary["summary"].values())
    assert counted == len(REFERENCE_ASSUMPTIONS)
    assert set(summary["summary"]) == {status.value for status in AssumptionStatus}


def test_the_summary_explains_what_approximate_means() -> None:
    summary = summarise_assumptions(reference_assumptions())
    assert "not a synonym for 'satisfied'" in summary["note"]


def test_assumption_dict_serialises_every_field() -> None:
    payload = assumption_dict(REFERENCE_ASSUMPTIONS[0])
    for key in (
        "key",
        "statement",
        "status",
        "evidence",
        "consequence_if_violated",
        "citation",
    ):
        assert key in payload
    assert payload["status"] == REFERENCE_ASSUMPTIONS[0].status.value


def test_the_assumption_keys_are_unique() -> None:
    keys = [assumption.key for assumption in REFERENCE_ASSUMPTIONS]
    assert len(set(keys)) == len(keys)
