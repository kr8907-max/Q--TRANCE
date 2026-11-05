"""The interpretation layer: what may and may not be said.

The milestone forbids three specific overclaims and bans the "decoy-state"
terminology outright. A guard that never fires proves nothing, so these tests do
three things: they check the forbidden claims *are* caught, they check that
honest disclosure of the same limitations is *not* caught, and they pin the
shape of an allowed statement so a report has a form to imitate.
"""

from __future__ import annotations

import pytest

from backend.security.interpretation import (
    ALLOWED_QUALIFIERS,
    BANNED_TERMINOLOGY,
    FORBIDDEN_CLAIMS,
    FORBIDDEN_PATTERNS,
    build_interpretation_result,
    check_statement,
    check_statements,
    render_forbidden_examples,
    render_measurement_statement,
)
from backend.security.models import StatementVerdict







def test_the_three_claims_the_brief_names_are_listed() -> None:
    claims = [claim for claim, _ in FORBIDDEN_CLAIMS]
    assert "This proves the protocol is information-theoretically secure." in claims
    assert "This is a formal forgery bound." in claims
    assert "The framework detects all quantum attacks." in claims


def test_every_forbidden_claim_carries_its_reason() -> None:
    for claim, reason in FORBIDDEN_CLAIMS:
        assert claim.endswith(".")
        assert len(reason) > 40, claim


def test_every_forbidden_claim_is_actually_detectable() -> None:



    undetected = [
        claim
        for claim in render_forbidden_examples()
        if check_statement(claim).verdict is not StatementVerdict.FORBIDDEN
    ]
    assert not undetected, undetected


def test_every_forbidden_pattern_has_a_reason() -> None:
    for pattern, reason in FORBIDDEN_PATTERNS:
        assert pattern == pattern.lower(), pattern
        assert reason







@pytest.mark.parametrize(
    "statement",
    [
        "This proves the protocol is information-theoretically secure.",
        "This is a formal forgery bound.",
        "The framework detects all quantum attacks.",
        "The threshold is optimal.",
        "The detector is secure.",
        "The simulator establishes security.",
        "FAR is the forgery probability.",
        "The results generalise to other conditions.",
    ],
)
def test_a_canonical_forbidden_claim_is_rejected(statement: str) -> None:
    result = check_statement(statement)
    assert result.verdict is StatementVerdict.FORBIDDEN
    assert result.violations
    assert len(result.reasons) == len(result.violations)


def test_a_plausible_paraphrase_is_still_rejected() -> None:


    for statement in (
        "the measured FAR is a formal forgery bound for the protocol",
        "the protocol is provably secure against intercept-resend",
        "our detector detects every attack we tried",
        "the threshold is optimal for this channel",
        "the sample size is a security parameter",
        "this is unconditionally secure",
    ):
        assert check_statement(statement).verdict is StatementVerdict.FORBIDDEN, statement







@pytest.mark.parametrize(
    "statement",
    [
        "no formal forgery bound is derived at this milestone",
        "these are empirical rates and they are not a formal forgery bound",
        "they do not establish security",
        "None of these is a cryptographic security parameter, and none of them "
        "is a forgery probability",
        "It is not a cryptographic forgery probability and it is never reported as one",
        "quoting a confidence interval as a forgery probability would overstate "
        "what was actually shown",
    ],
)
def test_disclosing_a_limitation_is_allowed(statement: str) -> None:


    assert check_statement(statement).verdict is StatementVerdict.ALLOWED, statement


def test_a_negation_after_the_phrase_does_not_excuse_it() -> None:


    result = check_statement("This is a formal forgery bound, not a measurement.")
    assert result.verdict is StatementVerdict.FORBIDDEN


def test_a_negation_in_an_earlier_sentence_does_not_excuse_it() -> None:
    result = check_statement(
        "No forgery bound was derived earlier. This is a formal forgery bound."
    )
    assert result.verdict is StatementVerdict.FORBIDDEN







def test_decoy_terminology_is_banned_and_never_excused() -> None:
    terms = {term for term, _ in BANNED_TERMINOLOGY}
    assert "decoy" in terms
    assert "decoy-state" in terms


    for statement in (
        "the decoy states are prepared in two intensities",
        "there is no decoy state here",
        "we avoid the term decoy-state",
    ):
        assert check_statement(statement).verdict is StatementVerdict.FORBIDDEN, statement


def test_the_banned_terminology_explains_why() -> None:
    for term, reason in BANNED_TERMINOLOGY:
        assert "QKD" in reason or "not used" in reason, term







def test_an_allowed_statement_carries_every_qualifier() -> None:
    statement = render_measurement_statement(
        state_count=5000,
        measurement_mode="sampled",
        shot_count=1,
        noise_type="depolarizing",
        noise_strength=0.02,
        honest_trials=12,
        frr=0.008,
        attack_type="intercept_resend",
        attack_fraction=0.20,
        detection_rate=0.941,
        far=0.059,
    )
    assert check_statement(statement).verdict is StatementVerdict.ALLOWED
    for qualifier in ALLOWED_QUALIFIERS:
        assert qualifier in statement, qualifier
    assert "N=5000" in statement
    assert "empirical" in statement
    assert "modelled" in statement
    assert "0.80%" in statement
    assert "94.10%" in statement
    assert "5.90%" in statement


def test_the_allowed_statement_does_not_claim_security() -> None:
    statement = render_measurement_statement(
        state_count=500,
        measurement_mode="sampled",
        shot_count=1,
        noise_type="depolarizing",
        noise_strength=0.02,
        honest_trials=8,
        frr=0.0,
        attack_type="forgery",
        attack_fraction=0.2,
        detection_rate=1.0,
    )
    lowered = statement.lower()
    assert "not a formal forgery bound" in lowered
    assert "do not establish security" in lowered


def test_an_undefined_rate_is_rendered_as_undefined_not_as_zero() -> None:
    statement = render_measurement_statement(
        state_count=100,
        measurement_mode="sampled",
        shot_count=1,
        noise_type="depolarizing",
        noise_strength=0.0,
        honest_trials=0,
        frr=None,
        attack_type="replay",
        attack_fraction=0.2,
        detection_rate=None,
    )
    assert "undefined" in statement
    assert "0.00%" not in statement







def test_check_statements_returns_one_check_per_statement() -> None:
    checks = check_statements(
        ["the protocol is provably secure", "the empirical FRR was 0.8%"]
    )
    assert len(checks) == 2
    assert checks[0].verdict is StatementVerdict.FORBIDDEN
    assert checks[1].verdict is StatementVerdict.ALLOWED


def test_check_statement_refuses_a_non_string() -> None:
    with pytest.raises(TypeError):
        check_statement(42)  # type: ignore[arg-type]


def test_check_statement_is_case_insensitive() -> None:
    assert check_statement("THIS IS A FORMAL FORGERY BOUND.").verdict is (
        StatementVerdict.FORBIDDEN
    )







def test_the_interpretation_result_carries_the_boundary_and_the_checks() -> None:
    result = build_interpretation_result(
        allowed_statements=["the empirical FRR was 0.8% at N=5000"],
        context={"operating_point": "m5-reference"},
        extra_statements_to_check=["the empirical FRR was 0.8% at N=5000"],
    )
    assert result.allowed_statements == ("the empirical FRR was 0.8% at N=5000",)
    assert result.forbidden_claims == FORBIDDEN_CLAIMS
    assert len(result.checks) == 1
    assert result.checks[0].verdict is StatementVerdict.ALLOWED
    assert result.context["operating_point"] == "m5-reference"


def test_the_interpretation_result_states_the_four_quantity_distinction() -> None:
    result = build_interpretation_result()
    joined = " ".join(result.notes)
    assert "confidence interval" in joined
    assert "decision rule" in joined
    assert "measurement" in joined
    assert "theorem" in joined
    assert "Only the first three are produced here" in joined


def test_the_interpretation_result_says_the_forbidden_list_is_not_a_description() -> None:
    result = build_interpretation_result()
    assert any("not a description" in note for note in result.notes)
