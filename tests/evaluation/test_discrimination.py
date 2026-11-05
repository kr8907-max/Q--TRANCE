"""The central discrimination experiment.

The question this experiment exists to answer is the interesting one: when an
honest channel and a malicious channel produce *the same marginal mismatch rate*,
does the observable evidence tell them apart at all?

The answer is allowed to be no, and the module is built so that "no" is a
reportable outcome rather than a failure. These tests pin the descriptor
selectors, the marginal-matching rule (including the vacuous-pair skip), and the
two possible verdicts -- a separation on the structural descriptor, and the
explicit ``Not distinguishable under the current observable model.``
"""

from __future__ import annotations

import pytest

from backend.evaluation.discrimination import (
    DEFAULT_DESCRIPTOR,
    DESCRIPTORS,
    NOT_DISTINGUISHABLE_VERDICT,
    compare_populations,
    descriptor_values,
    discrimination_experiment,
    match_marginals,
)







def test_the_descriptors_are_a_fixed_non_learned_set() -> None:


    assert set(DESCRIPTORS) == {
        "basis_mismatch_dispersion",
        "mean_fidelity",
        "minimum_fidelity",
        "disturbance_rate",
    }
    assert DEFAULT_DESCRIPTOR == "basis_mismatch_dispersion"


def test_the_not_distinguishable_verdict_is_the_exact_required_sentence() -> None:
    assert NOT_DISTINGUISHABLE_VERDICT == (
        "Not distinguishable under the current observable model."
    )


def test_descriptor_values_selects_the_requested_descriptor(make_record) -> None:
    records = [
        make_record(
            malicious=True,
            rejected=True,
            per_basis={"Z": 0.0, "X": 0.5, "Y": 0.0},
            n_mismatch=4,
        ),
        make_record(
            malicious=True,
            rejected=True,
            per_basis={"Z": 0.1, "X": 0.3, "Y": 0.1},
            n_mismatch=40,
        ),
    ]


    assert descriptor_values(records, "basis_mismatch_dispersion") == (
        pytest.approx(0.5),
        pytest.approx(0.2),
    )



    assert descriptor_values(records, "disturbance_rate") == (
        pytest.approx(0.02),
        pytest.approx(0.20),
    )
    assert descriptor_values(records, "mean_fidelity") == (
        pytest.approx(0.99),
        pytest.approx(0.99),
    )


def test_descriptor_values_returns_an_empty_tuple_for_an_empty_population() -> None:
    assert descriptor_values([], "basis_mismatch_dispersion") == ()


def test_an_unknown_descriptor_is_refused(make_record) -> None:
    with pytest.raises(ValueError):
        descriptor_values([make_record(malicious=False, rejected=False)], "not_a_descriptor")







def _population(make_record, *, rate: int, malicious: bool, count: int = 2):
    return tuple(
        make_record(
            malicious=malicious,
            rejected=malicious,
            n_mismatch=rate,
            seed=1000 * rate + index,
        )
        for index in range(count)
    )


def test_matching_selects_the_closest_marginal_pair(make_record) -> None:
    honest = [(0.0, _population(make_record, rate=0, malicious=False)),
              (0.02, _population(make_record, rate=4, malicious=False))]
    malicious = [(0.05, _population(make_record, rate=5, malicious=True)),
                 (0.50, _population(make_record, rate=50, malicious=True))]
    pair = match_marginals(honest, malicious, tolerance=0.01)
    assert pair.honest_x == pytest.approx(0.02)
    assert pair.malicious_x == pytest.approx(0.05)
    assert pair.gap == pytest.approx(1 / 200)
    assert pair.matched is True


def test_matching_skips_the_vacuous_both_zero_pair(make_record) -> None:


    honest = [(0.0, _population(make_record, rate=0, malicious=False)),
              (0.02, _population(make_record, rate=4, malicious=False))]
    malicious = [(0.0, _population(make_record, rate=0, malicious=True)),
                 (0.03, _population(make_record, rate=6, malicious=True))]
    pair = match_marginals(honest, malicious, tolerance=0.01)
    assert not (pair.honest_marginal == 0.0 and pair.malicious_marginal == 0.0)
    assert pair.honest_x == pytest.approx(0.02)


def test_a_gap_larger_than_the_tolerance_is_not_matched(make_record) -> None:
    honest = [(0.0, _population(make_record, rate=0, malicious=False))]
    malicious = [(0.5, _population(make_record, rate=50, malicious=True))]
    pair = match_marginals(honest, malicious, tolerance=0.001)
    assert pair.matched is False
    assert pair.gap == pytest.approx(0.25)
    assert pair.tolerance == pytest.approx(0.001)


def test_matching_records_the_intensities_it_chose(make_record) -> None:


    honest = [(0.01, _population(make_record, rate=2, malicious=False))]
    malicious = [(0.20, _population(make_record, rate=4, malicious=True))]
    pair = match_marginals(honest, malicious)
    assert pair.honest_x == pytest.approx(0.01)
    assert pair.malicious_x == pytest.approx(0.20)


def test_matching_refuses_a_sweep_with_no_defined_marginal(make_record) -> None:
    honest = [(0.0, _population(make_record, rate=0, malicious=False))]
    malicious = [(0.0, _population(make_record, rate=0, malicious=True))]
    with pytest.raises(ValueError, match="cannot match marginals"):
        match_marginals(honest, malicious)







def _descriptor_population(make_record, *, dispersion: float, malicious: bool):
    """Return a population whose per-basis dispersion is roughly ``dispersion``."""
    return tuple(
        make_record(
            malicious=malicious,
            rejected=malicious,
            per_basis={"Z": 0.0, "X": dispersion, "Y": 0.0},
            seed=int(dispersion * 10_000) + index,
        )
        for index in range(3)
    )


def test_separated_descriptor_ranges_are_distinguishable(
    make_record, small_operating_point
) -> None:
    honest = _descriptor_population(make_record, dispersion=0.02, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.30, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="channel_tampering",
    )
    assert result.distinguishable is True
    assert "distinguishable" in result.verdict
    assert NOT_DISTINGUISHABLE_VERDICT not in result.verdict
    assert result.descriptor == DEFAULT_DESCRIPTOR


def test_overlapping_descriptor_ranges_are_not_distinguishable(
    make_record, small_operating_point
) -> None:



    honest = _descriptor_population(make_record, dispersion=0.05, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.05, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="intercept_resend",
    )
    assert result.distinguishable is False
    assert result.verdict == NOT_DISTINGUISHABLE_VERDICT


def test_the_result_reports_both_rejection_rates_rather_than_a_boolean(
    make_record, small_operating_point
) -> None:



    honest = _descriptor_population(make_record, dispersion=0.02, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.30, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="channel_tampering",
    )
    assert result.honest_rejection_rate is not None
    assert result.malicious_rejection_rate is not None
    assert result.descriptor_separation_rate is not None
    assert 0.0 <= result.descriptor_separation_rate <= 1.0


def test_a_separation_rate_of_one_means_every_malicious_trial_exceeds_the_honest_maximum(
    make_record, small_operating_point
) -> None:
    honest = _descriptor_population(make_record, dispersion=0.01, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.40, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="channel_tampering",
    )
    assert result.descriptor_separation_rate == pytest.approx(1.0)


def test_the_criterion_is_declared_on_the_result(make_record, small_operating_point) -> None:
    honest = _descriptor_population(make_record, dispersion=0.02, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.30, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="channel_tampering",
    )
    assert result.criterion
    assert "range" in result.criterion.lower()


def test_the_result_serialises(make_record, small_operating_point) -> None:
    import json

    honest = _descriptor_population(make_record, dispersion=0.02, malicious=False)
    malicious = _descriptor_population(make_record, dispersion=0.30, malicious=True)
    result = compare_populations(
        honest,
        malicious,
        point=small_operating_point,
        honest_label="honest",
        malicious_label="channel_tampering",
    )
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["descriptor"] == DEFAULT_DESCRIPTOR
    assert "honest_descriptor" in payload







def test_the_experiment_returns_one_result_per_cell(
    small_scenario, small_operating_point
) -> None:
    results = discrimination_experiment(
        small_scenario,
        small_operating_point,
        evaluation_id="disc-test",
        seed_start=0,
        trial_count=1,
        noise_strengths=(0.02,),
        attack_types=("channel_tampering", "intercept_resend"),
        attack_fractions=(0.2,),
    )

    assert len(results) == 2



    labels = {result.malicious_label for result in results}
    assert labels == {
        "channel_tampering at fraction 0.2",
        "intercept_resend at fraction 0.2",
    }
    for result in results:
        assert result.honest_label.startswith("honest noise depolarizing eta=")


def test_the_experiment_reports_a_verdict_for_every_cell(
    small_scenario, small_operating_point
) -> None:
    results = discrimination_experiment(
        small_scenario,
        small_operating_point,
        evaluation_id="disc-test",
        seed_start=0,
        trial_count=1,
        noise_strengths=(0.02,),
        attack_types=("channel_tampering",),
        attack_fractions=(0.2,),
    )
    for result in results:
        assert result.verdict
        assert result.distinguishable in (True, False)
        assert result.honest_marginal is not None
        assert result.malicious_marginal is not None


def test_the_experiment_excludes_the_zero_intensity_arm_by_default() -> None:


    import inspect

    signature = inspect.signature(discrimination_experiment)
    default = signature.parameters["attack_fractions"].default
    assert 0.0 not in default
    assert default == (0.05, 0.10, 0.20, 0.50)
