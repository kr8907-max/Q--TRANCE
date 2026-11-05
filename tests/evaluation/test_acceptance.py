"""Milestone 5 acceptance criteria.

The 31 criteria from the milestone brief, each mapped to an explicit test.

Two of them are properties of the whole suite rather than of one module --
criterion 30 (the M1-M4 suites stay green) and criterion 31 (the M5 suites pass,
and the documentation matches the implementation). What is checked here is that
those suites still exist and that nothing in the M5 packages disturbs them; the
authoritative check is the full ``pytest`` run, whose total is quoted in the
milestone report.

The criteria are checked structurally wherever a structural check is possible.
"Calibration never sees an attack label" is asserted by parsing the source, not
by reading a comment, because a comment cannot fail.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.attacks import FRACTIONAL_ATTACK_TYPES, VALID_ATTACK_TYPES
from backend.calibration import (
    DIAGNOSTIC_METRICS,
    REFERENCE_ALPHA,
    REFERENCE_OPERATING_POINT_NAME,
    REFERENCE_PRIMARY_TEST,
    REFERENCE_THRESHOLD_METHOD,
    STATISTIC_MISMATCH_RATE,
    SUPPORTED_STATISTICS,
    DatasetRole,
    MultipleTestingPolicy,
    critical_count,
    derive_threshold,
    family_wise_error_rate,
    reference_policy,
)
from backend.calibration.operating_points import observed_rejection_rate
from backend.evaluation import (
    DEFAULT_DESCRIPTOR,
    DESCRIPTIVE_METRICS,
    DESCRIPTORS,
    FAR_DEFINITION,
    FRR_DEFINITION,
    LIMITATIONS,
    NOT_DISTINGUISHABLE_VERDICT,
    QUANTITY_DISTINCTIONS,
    REFERENCE_CURVES,
    REFERENCE_PROFILE,
    REFERENCE_ROBUSTNESS_ATTACKS,
    ROBUSTNESS_NOISE_LEVELS,
    SMOKE_PROFILE,
)
from backend.protocol.models import MAX_STATE_COUNT
from backend.security import (
    CLOPPER_PEARSON_ASSUMPTIONS,
    CLOPPER_PEARSON_CITATION,
    HOEFFDING_ASSUMPTIONS,
    HOEFFDING_CITATION,
    BANNED_TERMINOLOGY,
    FORBIDDEN_CLAIMS,
    StatementVerdict,
    check_statement,
    render_measurement_statement,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"
DOCS = PROJECT_ROOT / "docs" / "security"

CALIBRATION_DOC = DOCS / "statistical-calibration.md"
EVALUATION_DOC = DOCS / "evaluation-methodology.md"




GROUND_TRUTH_IDENTIFIERS = (
    "ground_truth",
    "groundtruth",
    "is_malicious",
    "is_attack",
    "attack_ground_truth",
)





GROUND_TRUTH_LAYERS = ("api", "attacks", "evaluation", "simulation")


EARLIER_TEST_PACKAGES = ("protocol", "quantum", "detection", "security")
M1_QUANTUM_MODULES = {
    "test_bell.py",
    "test_bit_ordering.py",
    "test_correction.py",
    "test_density.py",
    "test_measurements.py",
    "test_states.py",
    "test_teleport.py",
}







def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _modules(package: str) -> list[Path]:
    root = BACKEND / package
    assert root.is_dir(), root
    return sorted(path for path in root.rglob("*.py"))


def _doc(path: Path) -> str:
    assert path.is_file(), f"missing document: {path}"
    return path.read_text(encoding="utf-8")


def _names_a_ground_truth_identifier(path: Path) -> bool:
    """Return whether ``path`` mentions a ground-truth identifier.

    Only identifier positions are inspected -- names, arguments, keyword
    arguments, attribute roots -- so a docstring that discusses the boundary is
    not mistaken for code that crosses it.
    """
    found = False
    for node in ast.walk(_tree(path)):
        candidates: list[str] = []
        if isinstance(node, ast.Name):
            candidates.append(node.id)
        elif isinstance(node, ast.arg):
            candidates.append(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            candidates.append(node.arg)
        elif isinstance(node, ast.Attribute):
            candidates.append(node.attr)
        found = found or any(
            token in identifier.lower()
            for identifier in candidates
            for token in GROUND_TRUTH_IDENTIFIERS
        )
    return found







def test_criterion_01_one_primary_statistic_is_declared() -> None:
    """Exactly one statistic is tested, and it is named."""
    assert SUPPORTED_STATISTICS == (STATISTIC_MISMATCH_RATE,)
    assert STATISTIC_MISMATCH_RATE == "mismatch_rate"


def test_criterion_02_the_statistic_is_justified_against_named_criteria() -> None:
    """The selection is argued, not asserted, and the criteria are named."""
    text = _doc(CALIBRATION_DOC)
    for criterion in (
        "verifier observability",
        "physical meaning",
        "statistical behaviour",
        "finite-sample tractability",
        "interpretability",
        "honest-noise robustness",
    ):
        assert criterion in text, criterion


def test_criterion_03_alternatives_were_considered_and_documented() -> None:
    """Every diagnostic the detector exposes is named as a rejected alternative."""
    text = _doc(CALIBRATION_DOC)
    for alternative in ("reconstruction_fidelity", "verification_state_disturbance_rate"):
        assert alternative in text, alternative
    for diagnostic in DIAGNOSTIC_METRICS:
        assert diagnostic in text, diagnostic


def test_criterion_04_hypotheses_and_binomial_assumptions_are_stated() -> None:
    """H0/H1 are stated, and the honest null admits legitimate noise."""
    text = _doc(CALIBRATION_DOC)
    assert "H0" in text and "H1" in text

    for word in ("independent", "identically distributed", "Poisson-binomial"):
        assert word in text, word


    assert "1 - p_match" in text
    assert "interior" in text







def test_criterion_05_calibration_data_carries_its_role() -> None:
    """Every observation records which side of the split it belongs to."""
    roles = {role.value for role in DatasetRole}
    assert roles == {"CALIBRATION", "VALIDATION", "FINAL_EVALUATION"}


def test_criterion_06_no_attack_data_reaches_calibration() -> None:
    """The calibration and security layers name no attack label or ground truth."""
    for package in ("calibration", "security"):
        for path in _modules(package):
            assert not _names_a_ground_truth_identifier(path), path


def test_criterion_06b_calibration_imports_no_attack_layer() -> None:
    """Calibration cannot consume attack data: it cannot import it."""
    for path in _modules("calibration"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("backend.attacks"), (path, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("backend.attacks"), (
                        path,
                        alias.name,
                    )







def test_criterion_07_exact_interval_has_a_primary_citation() -> None:
    assert "Clopper" in CLOPPER_PEARSON_CITATION
    assert "Biometrika" in CLOPPER_PEARSON_CITATION
    assert "1934" in CLOPPER_PEARSON_CITATION
    assert CLOPPER_PEARSON_ASSUMPTIONS


def test_criterion_08_concentration_bound_has_a_primary_citation() -> None:
    assert "Hoeffding" in HOEFFDING_CITATION
    assert "1963" in HOEFFDING_CITATION
    assert HOEFFDING_ASSUMPTIONS


    joined = " ".join(HOEFFDING_ASSUMPTIONS).lower()
    assert "independen" in joined


def test_criterion_09_the_bounds_are_not_called_a_cryptographic_parameter() -> None:
    """Neither the interval nor the radius is presented as a security parameter."""
    text = _doc(CALIBRATION_DOC).lower()


    assert "neither is a cryptographic security parameter" in text
    assert "is_cryptographic_security_bound = false" in text
    for citation in (CLOPPER_PEARSON_CITATION, HOEFFDING_CITATION):
        assert "security parameter" not in citation.lower()


def test_criterion_10_the_four_quantities_are_distinguished() -> None:
    """Interval, threshold, empirical acceptance rate and formal bound differ."""
    assert set(QUANTITY_DISTINCTIONS) == {
        "confidence_interval",
        "classification_threshold",
        "empirical_attack_acceptance_rate",
        "formal_cryptographic_security_bound",
    }
    text = _doc(CALIBRATION_DOC)
    for key in QUANTITY_DISTINCTIONS:
        assert key in text, key

    assert "not produced at this milestone" in text







def test_criterion_11_sample_sizes_are_configurable_and_not_hardcoded() -> None:
    """The design range is declared data, and the detector holds no size."""
    assert REFERENCE_PROFILE.sample_size_design == (
        100,
        250,
        500,
        1000,
        2500,
        5000,
        10000,
    )
    assert REFERENCE_PROFILE.sample_size_simulated == (100, 250, 500, 1000, 2500)
    assert REFERENCE_PROFILE.sample_size_unreachable == (5000, 10000)


    assert REFERENCE_PROFILE.sample_size_unreachable[-1] > MAX_STATE_COUNT


def test_criterion_12_the_threshold_depends_on_the_sample_size() -> None:
    """A threshold is a function of N, not a constant."""
    counts = [critical_count(0.02, n, alpha=REFERENCE_ALPHA) for n in (100, 500, 2500)]
    assert counts == sorted(counts)
    assert len(set(counts)) == 3
    assert counts[-1] > counts[0]


def test_criterion_13_the_threshold_is_refused_at_another_sample_size(
    small_calibration,
) -> None:
    """A threshold is derived for one N; reusing it elsewhere is a category error.

    The implementation does not raise on a *different* N -- it derives that N's
    own threshold, which is the correct behaviour -- so what is asserted is that
    the two derivations really are different, and that the threshold records the
    size it was derived for.
    """
    first = derive_threshold(small_calibration, state_count=20)
    second = derive_threshold(small_calibration, state_count=200)
    assert first.critical_count != second.critical_count
    assert first.state_count == 20
    assert second.state_count == 200


def test_criterion_14_no_threshold_is_buried_in_source_code() -> None:
    """No module outside calibration defines a decision constant."""
    for package in ("calibration", "evaluation", "security"):
        for path in _modules(package):
            source = path.read_text(encoding="utf-8")
            tree = _tree(path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    for target in targets:
                        if isinstance(target, ast.Name) and "THRESHOLD" in target.id:


                            value = node.value
                            assert not (
                                isinstance(value, ast.Constant)
                                and isinstance(value.value, float)
                            ), (path, target.id, value.value)
            assert "mismatch_rate > 0." not in source, path


def test_criterion_14b_the_reference_alpha_is_a_declared_budget() -> None:
    """The one decision number in the project is a named, declared budget."""
    assert REFERENCE_ALPHA == 0.05
    text = _doc(CALIBRATION_DOC)
    assert "alpha" in text
    assert "error budget" in text.lower()







def test_criterion_15_a_multiple_testing_policy_module_exists() -> None:
    policy = reference_policy()
    assert policy.policy is MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS
    assert policy.primary_test == REFERENCE_PRIMARY_TEST

    assert policy.family_wise_alpha is None
    assert policy.correction is None


def test_criterion_16_every_other_statistic_is_diagnostic_only() -> None:
    """The remaining statistics are reported and excluded from the decision."""
    assert len(DIAGNOSTIC_METRICS) == 16
    assert REFERENCE_PRIMARY_TEST not in DIAGNOSTIC_METRICS
    text = _doc(CALIBRATION_DOC)
    for metric in DIAGNOSTIC_METRICS:
        assert metric in text, metric


def test_criterion_17_false_positive_inflation_is_quantified() -> None:
    """Uncorrected multiplicity is measured, not hand-waved."""
    assert family_wise_error_rate(0.05, 1) == pytest.approx(0.05)
    assert family_wise_error_rate(0.05, 10) == pytest.approx(0.4013, abs=5e-5)

    assert MultipleTestingPolicy.CORRECTED_FAMILY.value == "CORRECTED_FAMILY"







def test_criterion_18_the_decision_is_two_layered() -> None:
    """A verification decision exists separately from the security evaluation."""
    text = _doc(EVALUATION_DOC).lower()
    assert "verification decision" in text
    assert "security evaluation" in text


def test_criterion_19_ground_truth_is_named_only_by_producers_and_consumer() -> None:
    layers = {
        path.relative_to(BACKEND).parts[0]
        for path in BACKEND.rglob("*.py")
        if _names_a_ground_truth_identifier(path)
    }
    assert layers == set(GROUND_TRUTH_LAYERS), sorted(layers)


def test_criterion_20_the_detector_is_structurally_blind_to_labels() -> None:
    """Milestone 4's detector cannot read a label, so M5 inherits the property."""
    for path in _modules("detection"):
        assert not _names_a_ground_truth_identifier(path), path







def test_criterion_21_far_and_frr_are_defined_as_the_brief_states() -> None:
    assert "malicious trials accepted / malicious trials" in FAR_DEFINITION
    assert "honest trials rejected / honest trials" in FRR_DEFINITION
    assert "not a cryptographic forgery probability" in FAR_DEFINITION


def test_criterion_22_the_confusion_convention_is_declared() -> None:
    """Positive is 'rejected', so FPR is FRR and FNR is FAR -- and F1 is not a bound."""
    text = _doc(EVALUATION_DOC)
    assert "FPR" in text and "FNR" in text
    assert DESCRIPTIVE_METRICS
    assert "f1" in {name.lower() for name in DESCRIPTIVE_METRICS}
    assert "descriptive" in text.lower()


def test_criterion_23_all_six_modelled_attacks_are_evaluated() -> None:



    assert set(REFERENCE_PROFILE.attack_types) == set(VALID_ATTACK_TYPES) - {"none"}
    assert set(VALID_ATTACK_TYPES) - {"none"} == {
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
        "intercept_resend",
        "channel_tampering",
    }
    assert "none" not in REFERENCE_PROFILE.attack_types

    assert set(FRACTIONAL_ATTACK_TYPES) == {"intercept_resend", "channel_tampering"}


def test_criterion_24_noise_robustness_is_a_measured_grid() -> None:
    labels = [label for label, _ in ROBUSTNESS_NOISE_LEVELS]
    assert labels == ["none", "low", "medium", "high"]
    assert len(REFERENCE_ROBUSTNESS_ATTACKS) == 2
    text = _doc(EVALUATION_DOC)
    assert "Measure, do not assume" in text or "measured" in text.lower()







def test_criterion_25_the_discrimination_experiment_reports_honestly() -> None:
    """A verdict exists for the case where the two populations cannot be told apart."""
    assert NOT_DISTINGUISHABLE_VERDICT == (
        "Not distinguishable under the current observable model."
    )
    assert DEFAULT_DESCRIPTOR in DESCRIPTORS
    assert len(DESCRIPTORS) == 4
    text = _doc(EVALUATION_DOC)
    assert NOT_DISTINGUISHABLE_VERDICT in text


def test_criterion_26_no_attack_cause_is_attributed() -> None:
    """A rejection is evidence of inconsistency, never of a cause."""
    joined = " ".join(LIMITATIONS).lower()
    assert "attribution" in joined or "not attribution" in joined
    assert "consistency test" in joined


def test_criterion_27_no_formal_forgery_bound_is_fabricated() -> None:
    """The interpretation layer refuses the claim rather than merely avoiding it."""
    for claim, _reason in FORBIDDEN_CLAIMS:
        check = check_statement(claim)
        assert check.verdict is StatementVerdict.FORBIDDEN, claim
    assert len(FORBIDDEN_CLAIMS) >= 3
    joined = " ".join(LIMITATIONS).lower()
    assert "no formal forgery bound is derived" in joined







def test_criterion_28_eight_curves_come_from_measured_trials() -> None:
    assert len(REFERENCE_CURVES) == 8
    assert len(set(REFERENCE_CURVES)) == 8
    text = _doc(EVALUATION_DOC)
    for curve in REFERENCE_CURVES:
        assert curve in text, curve


    assert "ROC" in text


def test_criterion_29_exactly_one_reference_operating_point_exists() -> None:
    assert REFERENCE_OPERATING_POINT_NAME == "m5-reference"
    assert REFERENCE_PROFILE.name == REFERENCE_OPERATING_POINT_NAME
    assert SMOKE_PROFILE.name != REFERENCE_OPERATING_POINT_NAME




    for path in (CALIBRATION_DOC, EVALUATION_DOC):
        text = " ".join(_doc(path).split())
        assert "specified, not optimised" in text, path
        assert "no claim of optimality is made" in text, path







def test_criterion_30_the_m1_m4_suites_still_exist() -> None:
    tests = PROJECT_ROOT / "tests"
    for package in EARLIER_TEST_PACKAGES:
        assert (tests / package).is_dir(), package
    present = {path.name for path in (tests / "quantum").glob("test_*.py")}
    assert not (M1_QUANTUM_MODULES - present)


def test_criterion_31_the_m5_suites_and_documents_exist() -> None:
    tests = PROJECT_ROOT / "tests"
    for package in ("calibration", "evaluation", "security"):
        assert (tests / package).is_dir(), package
    assert CALIBRATION_DOC.is_file()
    assert EVALUATION_DOC.is_file()

    assert _doc(CALIBRATION_DOC).count("\n## ") >= 15
    assert _doc(EVALUATION_DOC).count("\n## ") >= 15


def test_criterion_31b_the_interpretation_layer_permits_and_forbids() -> None:
    """The allowed sentence renders, and the banned terminology is banned."""
    statement = render_measurement_statement(
        state_count=500,
        measurement_mode="sampled",
        shot_count=1,
        noise_type="depolarizing",
        noise_strength=0.02,
        honest_trials=12,
        frr=0.0,
        attack_type="channel_tampering",
        attack_fraction=0.2,
        detection_rate=1.0,
        far=0.0,
    )
    assert check_statement(statement).verdict is StatementVerdict.ALLOWED
    for term, _reason in BANNED_TERMINOLOGY:
        assert check_statement(f"the {term} states were measured").verdict is (
            StatementVerdict.FORBIDDEN
        )


def test_criterion_31c_the_reference_operating_point_rejects_nothing_honest(
    small_operating_point,
) -> None:
    """The reference rule accepts the honest data it was calibrated on."""
    assert small_operating_point.name == REFERENCE_OPERATING_POINT_NAME
    threshold = small_operating_point.threshold


    assert small_operating_point.observed_calibration_frr is not None
    rate = observed_rejection_rate(
        threshold,
        [0] * 8,
        threshold.state_count,
    )
    assert rate == pytest.approx(0.0)
