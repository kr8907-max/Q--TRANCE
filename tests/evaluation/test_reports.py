"""The report payload and its Markdown rendering.

The report is the artefact a reader sees, so it is where an overclaim would do
the most damage. These tests pin that the definitions travel with the numbers,
that the four quantities are distinguished, that the limitations are printed,
and that the rendered text passes the interpretation layer's own forbidden-claim
check rather than merely being written carefully by hand.
"""

from __future__ import annotations

import json

import pytest

from backend.calibration.models import (
    DatasetRole,
    OperatingPoint,
    ThresholdConfig,
    ThresholdResult,
)
from backend.evaluation.curves import build_curve
from backend.evaluation.metrics import metrics_from_matrix
from backend.evaluation.models import (
    ConfusionMatrix,
    CurvePoint,
    PopulationSummary,
    DiscriminationResult,
    RobustnessResult,
)
from backend.evaluation.reports import (
    LIMITATIONS,
    QUANTITY_DISTINCTIONS,
    attack_report,
    build_report,
    curve_report,
    discrimination_report,
    render_markdown,
    robustness_report,
    write_json,
    write_markdown,
)
from backend.security.interpretation import check_statement
from backend.security.models import StatementVerdict







def _operating_point() -> OperatingPoint:
    threshold = ThresholdResult(
        state_count=200,
        p_upper=0.0143,
        critical_count=10,
        threshold_rate=0.05,
        config=ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.5),
        calibration_fingerprint="a" * 64,
        calibration_session_count=24,
        calibration_total_valid=4800,
        calibration_total_mismatch=48,
        calibration_pooled_rate=0.01,
        calibration_role=DatasetRole.CALIBRATION,
    )
    return OperatingPoint(
        name="m5-reference",
        threshold=threshold,
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=200,
        measurement_mode="sampled",
        shot_count=1,
        calibration_seed_start=0,
        calibration_seed_end=23,
        observed_calibration_frr=0.0,
        notes=("reference operating point",),
    )


def _curves():
    return {
        "detection_probability_vs_attack_intensity": build_curve(
            "detection_probability_vs_attack_intensity",
            "attack fraction",
            "detection probability",
            [CurvePoint(x=0.1, y=0.5, trials=8), CurvePoint(x=0.2, y=0.9, trials=8)],
        )
    }


def _attack_metrics():
    return {
        "intercept_resend": metrics_from_matrix(ConfusionMatrix(tp=9, fn=1)),
        "none": metrics_from_matrix(ConfusionMatrix(tn=10)),
    }


def _robustness() -> RobustnessResult:
    return RobustnessResult(
        name="m5-robustness",
        honest_frr_by_noise={"none": 0.0, "medium": 0.1},
        detection_by_noise_and_attack={
            "none": {"intercept_resend": 1.0},
            "medium": {"intercept_resend": 0.9},
        },
        matrices={"none": ConfusionMatrix(tp=1)},
    )


def _discrimination() -> DiscriminationResult:
    honest = PopulationSummary(
        label="honest",
        trials=8,
        mean_mismatch_rate=0.02,
        minimum_mismatch_rate=0.01,
        maximum_mismatch_rate=0.03,
        mean_basis_dispersion=0.02,
        minimum_basis_dispersion=0.01,
        maximum_basis_dispersion=0.03,
        mean_fidelity=0.99,
    )
    malicious = PopulationSummary(
        label="channel_tampering",
        trials=8,
        mean_mismatch_rate=0.021,
        minimum_mismatch_rate=0.011,
        maximum_mismatch_rate=0.031,
        mean_basis_dispersion=0.06,
        minimum_basis_dispersion=0.05,
        maximum_basis_dispersion=0.07,
        mean_fidelity=0.97,
    )
    return DiscriminationResult(
        honest_label="honest",
        malicious_label="channel_tampering",
        honest_marginal=0.02,
        malicious_marginal=0.021,
        marginal_gap=0.001,
        matched=True,
        descriptor="basis_mismatch_dispersion",
        honest_descriptor=honest,
        malicious_descriptor=malicious,
        distinguishable=True,
        criterion="range non-overlap",
        verdict="distinguishable on [basis_mismatch_dispersion]",
        honest_rejection_rate=0.1,
        malicious_rejection_rate=0.9,
        descriptor_separation_rate=1.0,
    )







def test_the_limitations_are_present_and_cover_the_required_caveats() -> None:
    assert len(LIMITATIONS) == 10
    blob = " ".join(LIMITATIONS)
    for required in (
        "reference prototype",
        "classical protocol controls",
        "does not prove identity",
        "no formal forgery bound",
        "finite-shot",
        "not attribution",
        "empirical",
        "one sample size",
        "No joint acceptance region",
        "No machine learning",
    ):
        assert required in blob, required


def test_the_four_quantities_are_distinguished() -> None:
    assert set(QUANTITY_DISTINCTIONS) == {
        "confidence_interval",
        "classification_threshold",
        "empirical_attack_acceptance_rate",
        "formal_cryptographic_security_bound",
    }

    assert "NOT produced" in QUANTITY_DISTINCTIONS["formal_cryptographic_security_bound"]


def test_the_limitations_do_not_use_banned_terminology() -> None:
    for item in LIMITATIONS:
        assert "decoy" not in item.lower()







def test_curve_report_adds_the_evidence_behind_each_curve() -> None:
    payload = curve_report(_curves())
    entry = payload["detection_probability_vs_attack_intensity"]
    assert entry["total_trials"] == 16
    assert len(entry["points"]) == 2


def test_attack_report_scopes_every_far_claim() -> None:
    payload = attack_report(_attack_metrics(), attack_fraction={"intercept_resend": 0.2})
    assert payload["by_attack_type"]["intercept_resend"]["attack_fraction"] == 0.2
    scope = payload["by_attack_type"]["intercept_resend"]["far_scope"]
    assert "empirical acceptance rate" in scope
    assert "not a cryptographic forgery probability" in scope

    assert payload["by_attack_type"]["none"]["attack_fraction"] is None
    assert payload["by_attack_type"]["none"]["detection_rate"] is None


def test_attack_report_states_what_counts_as_malicious() -> None:
    payload = attack_report(_attack_metrics())
    statement = payload["what_counts_as_malicious"]
    for attack in (
        "forgery",
        "impersonation",
        "unauthorized verification",
        "replay",
        "intercept-resend",
        "channel tampering",
    ):
        assert attack in statement
    assert "Honest trials are never malicious" in statement


def test_robustness_report_carries_a_reading_guide() -> None:
    payload = robustness_report(_robustness())
    assert payload["honest_frr_by_noise"]["medium"] == pytest.approx(0.1)
    assert "honest_frr_by_noise" in payload["reading"]


def test_discrimination_report_carries_a_reading_guide() -> None:
    payload = discrimination_report([_discrimination()])
    assert len(payload) == 1
    assert payload[0]["matched"] is True
    assert "separation the marginal rate does not provide" in payload[0]["reading"]







def _report() -> dict:
    return build_report(
        operating_point=_operating_point(),
        calibration=_operating_point().threshold.to_dict(),
        curves=_curves(),
        attack_metrics=_attack_metrics(),
        robustness=_robustness(),
        discrimination=[_discrimination()],
        sample_size={"design": [100, 250, 500]},
        attack_fractions={"intercept_resend": 0.2},
        provenance={"seed_base": 0},
    )


def test_the_report_carries_its_definitions_next_to_its_numbers() -> None:
    report = _report()
    assert report["milestone"] == "M5"
    definitions = report["definitions"]
    assert "not a cryptographic forgery probability" in definitions["far"]
    assert definitions["descriptive_metrics"] == [
        "precision",
        "recall",
        "f1",
        "accuracy",
    ]
    assert set(definitions["quantity_distinctions"]) == set(QUANTITY_DISTINCTIONS)
    assert "FPR equals FRR" in definitions["positive_class"]


def test_the_report_records_the_multiple_comparison_policy() -> None:
    policy = _report()["multiple_comparison_policy"]
    assert policy["family_wise_alpha"] is None
    assert policy["correction"] is None
    assert policy["primary_test"] == "mismatch_rate_against_calibrated_threshold"
    assert policy["diagnostic_metrics"]
    assert all(
        entry["part_of_decision"] is False
        for entry in policy["diagnostics"].values()
    )


def test_optional_sections_are_absent_when_not_supplied() -> None:
    report = build_report(
        operating_point=_operating_point(),
        calibration={},
        curves={},
        attack_metrics={},
    )
    assert "robustness" not in report
    assert "discrimination" not in report
    assert "sample_size" not in report
    assert report["provenance"] == {}


def test_the_report_is_json_serializable() -> None:
    payload = json.dumps(_report())
    assert json.loads(payload)["milestone"] == "M5"







def test_the_rendered_report_says_the_point_is_specified_not_optimised() -> None:
    text = render_markdown(_report())
    assert "Reference operating point" in text
    assert "specified" in text
    assert "not optimised" in text
    assert "no claim of optimality is made" in text


def test_the_rendered_report_prints_the_definitions_and_the_limitations() -> None:
    text = render_markdown(_report())
    assert "not a cryptographic forgery probability" in text
    assert "four quantities that must not be conflated" in text
    assert "reference prototype" in text
    assert "No machine learning" in text


def test_the_rendered_report_marks_undefined_rates_as_na() -> None:
    report = build_report(
        operating_point=_operating_point(),
        calibration={},
        curves={},
        attack_metrics={"none": metrics_from_matrix(ConfusionMatrix(tn=4))},
    )
    text = render_markdown(report)
    assert "n/a" in text


def test_the_rendered_report_passes_the_interpretation_layers_own_check() -> None:



    text = render_markdown(_report())
    result = check_statement(text)
    assert result.verdict is StatementVerdict.ALLOWED, result.violations
    assert result.violations == ()


def test_the_interpretation_checker_really_does_reject_the_forbidden_claims() -> None:


    for forbidden in (
        "This proves the protocol is information-theoretically secure.",
        "This is a formal forgery bound.",
        "The framework detects all quantum attacks.",
    ):
        result = check_statement(forbidden)
        assert result.verdict is StatementVerdict.FORBIDDEN, forbidden


def test_the_rendered_report_does_not_use_banned_terminology() -> None:
    text = render_markdown(_report()).lower()
    assert "decoy" not in text


def test_the_rendered_report_has_no_unrendered_placeholder() -> None:
    text = render_markdown(_report())
    for placeholder in ("TODO", "FIXME", "XXX", "<placeholder>"):
        assert placeholder not in text







def test_write_json_round_trips(tmp_path) -> None:
    path = tmp_path / "report.json"
    written = write_json(_report(), str(path))
    assert written == str(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["milestone"] == "M5"


def test_write_markdown_round_trips(tmp_path) -> None:
    path = tmp_path / "report.md"
    written = write_markdown(render_markdown(_report()), str(path))
    assert written == str(path)
    assert "Milestone 5 report" in path.read_text(encoding="utf-8")
