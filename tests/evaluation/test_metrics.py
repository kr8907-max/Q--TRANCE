"""The reported rates, and the two identities the convention forces.

The milestone brief defines FAR and FRR explicitly and warns against calling a
cryptographic forgery probability "FAR". These tests pin the definitions, the
``FPR = FRR`` / ``FNR = FAR`` identities, the ``None``-rather-than-zero rule for
an empty denominator, and the fact that precision/recall/F1/accuracy are
labelled descriptive rather than presented as security quantities.
"""

from __future__ import annotations

import pytest

from backend.evaluation.metrics import (
    DESCRIPTIVE_METRICS,
    FAR_DEFINITION,
    FRR_DEFINITION,
    describe_metrics,
    detection_rate,
    false_acceptance_rate,
    false_rejection_rate,
    metrics,
    metrics_by_attack_type,
    metrics_by_noise,
    metrics_from_matrix,
    summarise_population,
)
from backend.evaluation.models import ConfusionMatrix


def test_the_two_definitions_are_stated_and_qualified() -> None:
    assert "malicious trials accepted / malicious trials" in FAR_DEFINITION

    assert "not a cryptographic forgery probability" in FAR_DEFINITION
    assert "honest trials rejected / honest trials" in FRR_DEFINITION


def test_descriptive_metrics_are_named_as_such() -> None:
    assert DESCRIPTIVE_METRICS == ("precision", "recall", "f1", "accuracy")


def test_the_rates_are_the_documented_ratios() -> None:
    bundle = metrics_from_matrix(ConfusionMatrix(tp=8, fn=2, fp=1, tn=89))
    assert bundle.detection_rate == pytest.approx(0.8)
    assert bundle.specificity == pytest.approx(89 / 90)
    assert bundle.far == pytest.approx(0.2)
    assert bundle.frr == pytest.approx(1 / 90)
    assert bundle.precision == pytest.approx(8 / 9)
    assert bundle.accuracy == pytest.approx(97 / 100)


def test_fpr_equals_frr_and_fnr_equals_far() -> None:



    bundle = metrics_from_matrix(ConfusionMatrix(tp=7, fn=3, fp=4, tn=86))
    assert bundle.fpr == bundle.frr
    assert bundle.fnr == bundle.far
    assert bundle.tpr == bundle.detection_rate
    assert bundle.tnr == bundle.specificity


def test_specificity_is_one_minus_frr() -> None:
    bundle = metrics_from_matrix(ConfusionMatrix(tp=1, fn=1, fp=3, tn=7))
    assert bundle.specificity == pytest.approx(1.0 - bundle.frr)


def test_f1_is_the_harmonic_mean_of_precision_and_recall() -> None:
    bundle = metrics_from_matrix(ConfusionMatrix(tp=6, fn=4, fp=2, tn=8))
    expected = 2 * bundle.precision * bundle.recall / (bundle.precision + bundle.recall)
    assert bundle.f1 == pytest.approx(expected)
    assert bundle.recall == bundle.detection_rate


def test_an_empty_denominator_yields_none_not_zero() -> None:


    bundle = metrics_from_matrix(ConfusionMatrix(tp=3, fn=0, fp=0, tn=0))
    assert bundle.far == 0.0
    assert bundle.frr is None
    assert bundle.specificity is None


def test_a_perfect_looking_f1_can_hide_the_absence_of_any_honest_evidence() -> None:




    bundle = metrics_from_matrix(ConfusionMatrix(tp=3, fn=0, fp=0, tn=0))
    assert bundle.f1 == pytest.approx(1.0)
    assert bundle.accuracy == pytest.approx(1.0)
    assert bundle.matrix.honest == 0


def test_a_fully_empty_matrix_reports_every_rate_as_none() -> None:
    bundle = metrics_from_matrix(ConfusionMatrix())
    for name in (
        "detection_rate",
        "specificity",
        "fpr",
        "fnr",
        "far",
        "frr",
        "precision",
        "recall",
        "f1",
        "accuracy",
    ):
        assert getattr(bundle, name) is None, name


def test_an_empty_precision_denominator_yields_none() -> None:

    bundle = metrics_from_matrix(ConfusionMatrix(tp=0, fn=5, fp=0, tn=5))
    assert bundle.precision is None
    assert bundle.f1 is None
    assert bundle.accuracy == pytest.approx(0.5)







def test_metrics_agrees_with_the_matrix_it_is_built_from(make_record) -> None:
    records = [
        make_record(malicious=True, rejected=True),
        make_record(malicious=True, rejected=False),
        make_record(malicious=False, rejected=False),
        make_record(malicious=False, rejected=False),
    ]
    assert metrics(records).to_dict() == metrics_from_matrix(
        ConfusionMatrix(tp=1, fn=1, tn=2)
    ).to_dict()


def test_the_three_convenience_rates_match_the_bundle(make_record) -> None:
    records = [
        make_record(malicious=True, rejected=True),
        make_record(malicious=True, rejected=False),
        make_record(malicious=False, rejected=True),
        make_record(malicious=False, rejected=False),
    ]
    bundle = metrics(records)
    assert detection_rate(records) == bundle.detection_rate
    assert false_acceptance_rate(records) == bundle.far
    assert false_rejection_rate(records) == bundle.frr


def test_the_convenience_rates_are_none_on_empty_input() -> None:
    assert detection_rate([]) is None
    assert false_acceptance_rate([]) is None
    assert false_rejection_rate([]) is None


def test_metrics_by_attack_type_is_keyed_by_attack(make_record) -> None:
    records = [
        make_record(malicious=True, rejected=True, attack_type="replay"),
        make_record(malicious=True, rejected=False, attack_type="replay"),
        make_record(malicious=False, rejected=False),
    ]
    grouped = metrics_by_attack_type(records)
    assert grouped["replay"].detection_rate == pytest.approx(0.5)
    assert grouped["none"].detection_rate is None


def test_metrics_by_noise_is_keyed_by_noise_cell(make_record) -> None:
    records = [
        make_record(malicious=True, rejected=True, noise_strength=0.0),
        make_record(malicious=True, rejected=False, noise_strength=0.1),
    ]
    grouped = metrics_by_noise(records)
    assert grouped["depolarizing@0"].detection_rate == pytest.approx(1.0)
    assert grouped["depolarizing@0.1"].detection_rate == pytest.approx(0.0)







def test_a_population_summary_reports_the_observable_spread(make_record) -> None:
    records = [
        make_record(malicious=False, rejected=False, n_mismatch=2, seed=1),
        make_record(malicious=False, rejected=False, n_mismatch=6, seed=2),
    ]
    summary = summarise_population(records, "honest")
    assert summary.label == "honest"
    assert summary.trials == 2
    assert summary.mean_mismatch_rate == pytest.approx((2 / 200 + 6 / 200) / 2)
    assert summary.minimum_mismatch_rate == pytest.approx(2 / 200)
    assert summary.maximum_mismatch_rate == pytest.approx(6 / 200)


def test_a_population_summary_uses_the_basis_dispersion_descriptor(make_record) -> None:
    records = [
        make_record(
            malicious=True,
            rejected=True,
            per_basis={"Z": 0.01, "X": 0.05, "Y": 0.01},
            seed=1,
        ),
        make_record(
            malicious=True,
            rejected=True,
            per_basis={"Z": 0.02, "X": 0.04, "Y": 0.02},
            seed=2,
        ),
    ]
    summary = summarise_population(records, "tampering")
    assert summary.mean_basis_dispersion == pytest.approx((0.04 + 0.02) / 2)
    assert summary.minimum_basis_dispersion == pytest.approx(0.02)
    assert summary.maximum_basis_dispersion == pytest.approx(0.04)


def test_an_empty_population_summarises_to_none() -> None:
    summary = summarise_population([], "nothing")
    assert summary.trials == 0
    assert summary.mean_mismatch_rate is None
    assert summary.mean_basis_dispersion is None
    assert summary.mean_fidelity is None


def test_describe_metrics_serialises_and_flags_descriptive_fields() -> None:
    described = describe_metrics(metrics_from_matrix(ConfusionMatrix(tp=1, tn=1)))
    assert described["matrix"]["total"] == 2
    assert set(described["descriptive_only"]) == set(DESCRIPTIVE_METRICS)

    assert "far" in described and "frr" in described
