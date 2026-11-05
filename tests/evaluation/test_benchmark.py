"""The benchmark entry point, exercised at smoke scale.

The recorded benchmark is far too expensive for a test suite, so these tests run
:data:`~backend.evaluation.benchmark.SMOKE_PROFILE` instead. That profile
measures the same things at a scale that finishes in well under a minute, and
none of its numbers are reported anywhere.

What is pinned here is *structure and provenance*, not the values: that every
declared section is present, that the seed blocks the run used are disjoint, that
the transpile cache is declared rather than silent, and that the declared
sample-size design range is reported honestly -- including the part of it the
reference protocol cannot simulate.
"""

from __future__ import annotations

import json

import pytest

from backend.calibration.operating_points import REFERENCE_OPERATING_POINT_NAME
from backend.attacks.base import FRACTIONAL_ATTACK_TYPES
from backend.protocol.models import MAX_STATE_COUNT

from backend.evaluation.benchmark import (
    REFERENCE_PROFILE,
    REFERENCE_SAMPLE_SIZE_DESIGN,
    SMOKE_PROFILE,
    attack_fraction_for,
    benchmark_base_scenario,
    partition_sample_sizes,
    run_benchmark,
    sample_size_plan,
)
from backend.evaluation.curves import (
    CURVE_CALIBRATION_DISTRIBUTION,
    CURVE_DETECTION_VS_ATTACK,
    CURVE_DETECTION_VS_SAMPLE_SIZE,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    CURVE_MISMATCH_VS_NOISE,
)
from backend.evaluation.robustness import REFERENCE_ROBUSTNESS_ATTACKS
from backend.evaluation.sweeps import attack_config



REFERENCE_CURVE_KEYS = {
    CURVE_DETECTION_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    "far_vs_threshold",
    CURVE_DETECTION_VS_SAMPLE_SIZE,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_MISMATCH_VS_NOISE,
    CURVE_CALIBRATION_DISTRIBUTION,
    "threshold_operating_curve",
}


@pytest.fixture(scope="module")
def smoke_run():
    """Run the smoke benchmark once for the whole module."""
    return run_benchmark(SMOKE_PROFILE)


@pytest.fixture(scope="module")
def report(smoke_run):
    return smoke_run["report"]


@pytest.fixture(scope="module")
def markdown(smoke_run):
    return smoke_run["markdown"]







def test_the_smoke_profile_is_not_the_reported_profile() -> None:

    assert SMOKE_PROFILE.name != REFERENCE_PROFILE.name
    assert REFERENCE_PROFILE.name == "m5-reference"
    assert "not reported" in SMOKE_PROFILE.description


def test_the_reference_profile_declares_the_full_design_sample_size_range() -> None:
    assert REFERENCE_PROFILE.sample_size_design == REFERENCE_SAMPLE_SIZE_DESIGN
    assert REFERENCE_SAMPLE_SIZE_DESIGN == (100, 250, 500, 1000, 2500, 5000, 10000)


def test_the_reference_profile_separates_what_it_simulates_from_what_it_declares() -> None:



    assert REFERENCE_PROFILE.sample_size_simulated == (100, 250, 500, 1000, 2500)
    assert REFERENCE_PROFILE.sample_size_unreachable == (5000, 10000)
    assert all(size <= MAX_STATE_COUNT for size in REFERENCE_PROFILE.sample_size_simulated)


def test_the_reference_profile_says_the_protocol_bound_was_not_widened() -> None:
    joined = " ".join(REFERENCE_PROFILE.notes)
    assert str(MAX_STATE_COUNT) in joined
    assert "not widened" in joined or "not be widened" in joined


def test_the_reference_profile_declares_a_zero_noise_level_and_a_strictly_higher_one() -> None:
    strengths = REFERENCE_PROFILE.noise_strengths
    assert strengths[0] == 0.0
    assert list(strengths) == sorted(strengths)
    assert strengths[-1] > 0.0


def test_the_reference_profile_is_the_single_shot_sampled_configuration() -> None:


    assert REFERENCE_PROFILE.measurement_mode == "sampled"
    assert REFERENCE_PROFILE.shot_count == 1
    assert any("interior" in note for note in REFERENCE_PROFILE.notes)


def test_the_reference_profile_covers_the_six_named_attacks() -> None:
    assert set(REFERENCE_PROFILE.attack_types) == {
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
        "intercept_resend",
        "channel_tampering",
    }














@pytest.mark.parametrize("attack_type", REFERENCE_PROFILE.attack_types)
def test_every_declared_attack_type_accepts_the_intensity_the_benchmark_gives_it(
    attack_type: str,
) -> None:
    intensity = attack_fraction_for(attack_type, REFERENCE_PROFILE.attack_fraction)
    attack_config(attack_type, fraction=intensity)


def test_whole_session_attacks_are_given_a_zero_intensity() -> None:
    whole_session = set(REFERENCE_PROFILE.attack_types) - set(FRACTIONAL_ATTACK_TYPES)



    assert whole_session == {
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
    }
    for attack_type in sorted(whole_session):
        assert attack_fraction_for(attack_type, REFERENCE_PROFILE.attack_fraction) == 0.0


def test_fractional_attacks_keep_the_declared_intensity() -> None:
    assert set(FRACTIONAL_ATTACK_TYPES) == {"intercept_resend", "channel_tampering"}
    for attack_type in FRACTIONAL_ATTACK_TYPES:
        assert attack_fraction_for(attack_type, 0.2) == pytest.approx(0.2)


def test_the_intensity_helper_would_reject_the_naive_global_fraction() -> None:


    with pytest.raises(Exception):
        attack_config("forgery", fraction=REFERENCE_PROFILE.attack_fraction)


def test_benchmark_base_scenario_reflects_the_profile() -> None:
    scenario = benchmark_base_scenario(SMOKE_PROFILE)
    assert scenario.state_count == SMOKE_PROFILE.state_count
    assert scenario.shot_count == SMOKE_PROFILE.shot_count
    assert scenario.measurement_mode == SMOKE_PROFILE.measurement_mode
    assert scenario.scenario_id == f"{SMOKE_PROFILE.name}-base"







def test_partition_sample_sizes_splits_the_declared_reference_design() -> None:
    reachable, unreachable = partition_sample_sizes(REFERENCE_SAMPLE_SIZE_DESIGN)
    assert reachable == (100, 250, 500, 1000, 2500)
    assert unreachable == (5000, 10000)


def test_partition_sample_sizes_is_exhaustive_and_order_preserving() -> None:
    reachable, unreachable = partition_sample_sizes(REFERENCE_SAMPLE_SIZE_DESIGN)


    assert sorted(reachable + unreachable) == sorted(REFERENCE_SAMPLE_SIZE_DESIGN)
    assert set(reachable) & set(unreachable) == set()


def test_partition_sample_sizes_uses_the_protocol_bound_by_default() -> None:
    reachable, unreachable = partition_sample_sizes((1, MAX_STATE_COUNT, MAX_STATE_COUNT + 1))
    assert reachable == (1, MAX_STATE_COUNT)
    assert unreachable == (MAX_STATE_COUNT + 1,)


@pytest.mark.parametrize("size", [MAX_STATE_COUNT + 1, 5000, 10000])
def test_the_sample_size_plan_refuses_a_size_above_the_protocol_bound(size: int) -> None:
    with pytest.raises(ValueError) as excinfo:
        sample_size_plan(
            (size,),
            calibration_budget=100,
            fixed_trials=1,
            min_calibration_sessions=1,
            max_calibration_sessions=1,
        )
    message = str(excinfo.value)


    assert str(MAX_STATE_COUNT) in message
    assert "partition_sample_sizes" in message


def test_the_sample_size_plan_accepts_the_protocol_boundary() -> None:
    plans = sample_size_plan(
        (1, MAX_STATE_COUNT),
        calibration_budget=100,
        fixed_trials=1,
        min_calibration_sessions=1,
        max_calibration_sessions=1,
    )
    assert [plan.state_count for plan in plans] == [1, MAX_STATE_COUNT]


def test_the_sample_size_plan_holds_the_trial_count_fixed() -> None:


    plans = sample_size_plan(
        (10, 100, 1000),
        calibration_budget=600,
        fixed_trials=7,
        min_calibration_sessions=2,
        max_calibration_sessions=20,
    )
    assert {plan.trials for plan in plans} == {7}

    sessions = [plan.calibration_sessions for plan in plans]
    assert sessions == sorted(sessions, reverse=True)







def test_the_report_is_json_serializable(report) -> None:
    assert json.loads(json.dumps(report)) == report


def test_the_report_carries_every_expected_section(report) -> None:
    assert report["milestone"] == "M5"
    for key in (
        "title",
        "operating_point",
        "calibration",
        "definitions",
        "multiple_comparison_policy",
        "curves",
        "attack_evaluation",
        "limitations",
        "robustness",
        "discrimination",
        "sample_size",
        "provenance",
    ):
        assert key in report, key


def test_the_provenance_names_the_profile_and_the_environment(report) -> None:
    provenance = report["provenance"]
    assert provenance["profile"] == SMOKE_PROFILE.name
    assert provenance["protocol_version"]
    assert provenance["python"]
    assert provenance["platform"]
    assert provenance["scenario_count"] > 0
    assert provenance["runtime_seconds"] > 0.0
    assert "measured" in provenance["runtime_note"]


def test_the_provenance_records_disjoint_seed_blocks(report) -> None:
    blocks = report["provenance"]["seed_blocks"]
    assert blocks
    ranges = []
    for block in blocks:
        first = block["first_seed"]
        ranges.append((first, first + block["count"]))
    for index, (low, high) in enumerate(ranges):
        for other_low, other_high in ranges[index + 1 :]:
            assert high <= other_low or other_high <= low, (low, high, other_low, other_high)

    assert sum(block["count"] for block in blocks) == report["provenance"]["scenario_count"]


def test_the_provenance_declares_the_transpile_cache_rather_than_hiding_it(report) -> None:
    cache = report["provenance"]["transpile_cache"]
    assert cache["enabled_during_run"] is True



    assert cache["stats"]["lookups"] == SMOKE_PROFILE.total_planned_states


    assert cache["stats"]["misses"] == 6
    assert cache["stats"]["entries"] == 6
    assert cache["stats"]["hit_rate"] is not None
    assert "never stores outcomes" in cache["note"]


    assert "enabled=False" in cache["note"]


def test_the_report_states_the_measurement_configuration_and_why(report) -> None:
    configuration = report["measurement_configuration"]
    assert configuration["measurement_mode"] == SMOKE_PROFILE.measurement_mode
    assert configuration["shot_count"] == SMOKE_PROFILE.shot_count
    assert configuration["reference_noise"]["noise_type"] == SMOKE_PROFILE.noise_type
    assert configuration["reference_noise"]["noise_strength"] == pytest.approx(
        SMOKE_PROFILE.reference_noise_strength
    )
    why = configuration["why"]
    assert "interior" in why
    assert "projective-analytic" in why and "sampled" in why


def test_the_report_names_the_reference_operating_point(report) -> None:
    assert report["reference_operating_point_name"] == REFERENCE_OPERATING_POINT_NAME
    assert report["operating_point"]["name"] == REFERENCE_OPERATING_POINT_NAME


def test_the_report_defines_far_and_frr_and_separates_the_four_quantities(report) -> None:
    definitions = report["definitions"]
    assert "malicious trials accepted / malicious trials" in definitions["far"]
    assert "honest trials rejected / honest trials" in definitions["frr"]
    distinctions = definitions["quantity_distinctions"]
    assert set(distinctions) == {
        "confidence_interval",
        "classification_threshold",
        "empirical_attack_acceptance_rate",
        "formal_cryptographic_security_bound",
    }
    assert "NOT produced" in distinctions["formal_cryptographic_security_bound"]
    assert "FPR equals FRR and FNR equals FAR" in definitions["positive_class"]


def test_the_report_records_the_multiple_comparison_policy(report) -> None:
    policy = report["multiple_comparison_policy"]
    assert policy["policy"] == "SINGLE_PRIMARY_WITH_DIAGNOSTICS"
    assert policy["primary_test"]
    assert policy["diagnostic_metrics"]
    assert policy["primary_test"] not in policy["diagnostic_metrics"]


    assert policy["family_wise_alpha"] is None
    assert policy["correction"] is None


def test_every_reference_curve_is_present_and_rests_on_measured_trials(report) -> None:
    assert set(report["curves"]) == REFERENCE_CURVE_KEYS
    for name, curve in report["curves"].items():
        assert curve["points"], name
        assert curve["total_trials"] >= 1, name
        for point in curve["points"]:
            assert point["trials"] >= 1, (name, point)


def test_the_attack_evaluation_covers_every_declared_attack(report) -> None:
    attack = report["attack_evaluation"]
    assert set(attack["by_attack_type"]) == set(SMOKE_PROFILE.attack_types)
    for bundle in attack["by_attack_type"].values():
        assert "not a cryptographic forgery probability" in bundle["far_scope"]
    assert "Honest trials are never malicious" in attack["what_counts_as_malicious"]


def test_the_robustness_section_covers_every_declared_level(report) -> None:
    robustness = report["robustness"]
    labels = [label for label, _ in SMOKE_PROFILE.robustness_levels]
    assert set(robustness["honest_frr_by_noise"]) == set(labels)
    assert set(robustness["detection_by_noise_and_attack"]) == set(labels)


    assert set(robustness["matrices"]) == {f"honest:{label}" for label in labels} | {
        f"{label}:{attack}" for label in labels for attack in REFERENCE_ROBUSTNESS_ATTACKS
    }


def test_the_discrimination_section_has_one_entry_per_attack_type(report) -> None:
    entries = report["discrimination"]
    assert len(entries) == 2
    for entry in entries:
        assert entry["verdict"]
        assert entry["matched"] in (True, False)
        assert entry["criterion"]
        assert entry["honest_label"] and entry["malicious_label"]


def test_the_sample_size_section_declares_the_design_and_what_was_simulated(report) -> None:
    sample_size = report["sample_size"]
    assert sample_size["declared_design"] == list(SMOKE_PROFILE.sample_size_design)
    assert sample_size["simulated_design"] == list(SMOKE_PROFILE.sample_size_simulated)
    assert sample_size["unsimulated_design"] == []
    assert sample_size["rows"]
    assert "not comparable across rows" in sample_size["note"]


def test_each_sample_size_row_carries_its_own_threshold(report) -> None:
    for row in report["sample_size"]["rows"]:
        assert row["threshold_rate"] == pytest.approx(
            row["critical_count"] / row["state_count"]
        )
        assert 0.0 <= row["p_upper"] <= 1.0


def test_the_exact_threshold_table_covers_every_declared_design_size(report) -> None:
    table = report["sample_size"]["exact_threshold_table"]
    assert [row["state_count"] for row in table] == list(SMOKE_PROFILE.sample_size_design)
    for row in table:
        assert row["simulated"] is True
        assert 0 <= row["expected_frr"] <= 1.0
        assert 0.0 <= row["threshold_rate"] <= 1.0
    assert "not valid at N=10,000" in report["sample_size"]["exact_threshold_table_note"]


def test_the_markdown_summary_states_the_definitions_and_the_caveats(markdown) -> None:
    assert markdown
    assert "Milestone 5 report" in markdown


    assert "specified" in markdown and "not optimised" in markdown

    assert "The four quantities that must not be conflated" in markdown
    for name in (
        "confidence_interval",
        "classification_threshold",
        "empirical_attack_acceptance_rate",
        "formal_cryptographic_security_bound",
    ):
        assert name in markdown, name
    assert "NOT produced by this milestone" in markdown

    assert "## Limitations" in markdown
    assert "reference prototype" in markdown
    assert "## Provenance" in markdown

    assert "not a cryptographic forgery probability" in markdown

    assert "none is interpolated or synthetic" in markdown







def test_the_benchmark_can_be_run_with_the_transpile_cache_disabled(
    tiny_benchmark_profile,
) -> None:
    result = run_benchmark(tiny_benchmark_profile, use_transpile_cache=False)
    report = result["report"]


    assert "transpile_cache" not in report["provenance"]
    assert report["milestone"] == "M5"
    assert report["curves"]
