"""Interpretation: what may and may not be said about these numbers.

The problem this module solves
------------------------------
A benchmark produces a table of rates. A reader under time pressure quotes one of
them without its conditions, and a sentence like "the framework detects quantum
attacks with 94% accuracy" is born. Nothing in the table is false; the sentence
is. This module makes the gap explicit and machine-checkable.

Three things it provides
------------------------
:data:`FORBIDDEN_CLAIMS`
    The claims this project must not make, each with the reason it is wrong.

:func:`check_statement`
    A check that flags a sentence containing a forbidden claim, so a report can
    be tested rather than trusted.

:func:`render_measurement_statement`
    A statement built from actual measured numbers, carrying the sample size, the
    calibrated channel, the word "empirical", the modelled attack and its
    intensity. This is the shape an allowed claim takes: every qualifier is
    present because removing any of them changes what the number means.

The allowed form, by example
----------------------------
    At N=5000 under the calibrated honest depolarizing channel at eta=0.02 with
    one shot per state, the empirical false-rejection rate was 0.8% over 12
    independent honest trials; under the same configuration the empirical
    acceptance rate for the modelled intercept-resend attack at fraction=0.20
    was 5.9%, i.e. an empirical detection rate of 94.1%.

The forbidden forms, and why
----------------------------
    "This proves the protocol is information-theoretically secure"
        No security proof was constructed. The evidence is a statistical
        consistency test against a calibrated model, and consistency with a model
        is not a proof about an adversary.

    "This is a formal forgery bound"
        No forgery bound was derived. What was measured is the empirical
        acceptance rate of a specific modelled forgery experiment, on a specific
        dataset, at a specific sample size. A formal bound is a theorem; this is
        a measurement.

    "The framework detects all quantum attacks"
        Six attack families were modelled. Nothing was shown about any attack
        that was not modelled, and the discrimination experiment explicitly
        identifies a case that the current observable evidence cannot separate
        from honest noise.

Terminology that is banned
--------------------------
"Decoy" and "decoy-state" are not used anywhere in this project. The
measurement bases are protocol-determined and are not decoys, and borrowing the
term from QKD would imply a security mechanism that this construction does not
have. :func:`check_statement` flags it.

Negation, and why it has to be handled
--------------------------------------
A check that flags the phrase "formal forgery bound" wherever it appears also
flags the sentence "no formal forgery bound is derived", which is the opposite
of the overclaim it is meant to catch. That is not a hypothetical: this module's
own :func:`render_measurement_statement` ends by saying the numbers are *not* a
formal forgery bound, and a blunt substring check rejects it.

So a forbidden phrase is excused when the clause immediately preceding it is
negated. "This is a formal forgery bound" is still flagged, and so is "this is a
formal forgery bound, not a measurement" -- the negation there follows the
phrase and governs a different clause.

This is a guard-rail, not a decision procedure: a determined author can still
phrase an overclaim so that it slips past. It is stated here rather than left
implicit so that no reader mistakes a clean check for a proof of honesty.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence, Tuple

from backend.security.models import (
    InterpretationResult,
    StatementCheck,
    StatementVerdict,
)

__all__ = [
    "FORBIDDEN_CLAIMS",
    "FORBIDDEN_PATTERNS",
    "BANNED_TERMINOLOGY",
    "ALLOWED_QUALIFIERS",
    "check_statement",
    "check_statements",
    "render_measurement_statement",
    "render_forbidden_examples",
    "build_interpretation_result",
]


FORBIDDEN_CLAIMS: Tuple[Tuple[str, str], ...] = (
    (
        "This proves the protocol is information-theoretically secure.",
        "no security proof was constructed. The verification decision is a "
        "statistical consistency test against a calibrated honest model, and "
        "consistency with a model says nothing about an adversary's advantage.",
    ),
    (
        "This is a formal forgery bound.",
        "no forgery bound was derived. What is measured is the empirical "
        "acceptance rate of one modelled forgery experiment on one dataset at one "
        "sample size. A formal bound is a theorem about an adversary; this is a "
        "measurement about an experiment.",
    ),
    (
        "The framework detects all quantum attacks.",
        "six attack families were modelled and measured. Nothing was shown about "
        "any attack outside that set, and the discrimination experiment identifies "
        "a modelled attack whose observable evidence cannot be separated from "
        "honest noise at comparable marginal mismatch rates.",
    ),
    (
        "The threshold is optimal.",
        "no objective function was maximised. The reference operating point is "
        "specified: one method, one error budget, one sample size, one calibrated "
        "channel. Specified is not optimised.",
    ),
    (
        "The detector is secure.",
        "the detector is a statistical consistency test with a measured false "
        "acceptance rate on modelled attacks. It is not a security mechanism and "
        "it has no security claim attached.",
    ),
    (
        "The simulator establishes security.",
        "a simulator reproduces a model. Reproducing a model cannot establish a "
        "property of the world, and the model's own assumptions bound what the "
        "simulation can show.",
    ),
    (
        "FAR is the forgery probability.",
        "FAR is the empirical share of malicious trials the rule accepted on this "
        "dataset. A forgery probability is a property of a protocol against an "
        "adversary, and it is not what was measured.",
    ),
    (
        "The results generalise to other conditions.",
        "every rate is conditional on the calibrated channel, the sample size, "
        "the measurement mode, the shot count and the modelled attacks. The "
        "threshold is not even defined outside its own sample size.",
    ),
)


FORBIDDEN_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (
        "information-theoretically secure",
        "no information-theoretic security proof was constructed at this milestone",
    ),
    (
        "information theoretic security",
        "no information-theoretic security proof was constructed at this milestone",
    ),
    (
        "formal forgery bound",
        "no forgery bound was derived; only an empirical acceptance rate was measured",
    ),
    (
        "is a forgery probability",
        "FAR is an empirical acceptance rate on one dataset, not a forgery probability",
    ),
    (
        "is the forgery probability",
        "FAR is an empirical acceptance rate on one dataset, not a forgery probability",
    ),
    (
        "proves the protocol is secure",
        "a statistical consistency test is not a proof of security",
    ),
    (
        "unconditionally secure",
        "unconditional security requires a proof that was not constructed here",
    ),
    (
        "detects all quantum attacks",
        "only six modelled attack families were measured",
    ),
    (
        "detects every attack",
        "only six modelled attack families were measured",
    ),
    (
        "cannot be fooled",
        "the rule has a measured, non-zero false acceptance rate on modelled attacks",
    ),
    (
        "provably secure",
        "no security proof was constructed",
    ),
    (
        "detector is secure",
        "the detector is a statistical consistency test with no security claim attached",
    ),
    (
        "establishes security",
        "a statistical consistency test establishes no security property",
    ),
    (
        "establish security",
        "a statistical consistency test establishes no security property",
    ),
    (
        "generalise to other conditions",
        "every rate is conditional on the channel, sample size, mode and modelled attacks",
    ),
    (
        "generalize to other conditions",
        "every rate is conditional on the channel, sample size, mode and modelled attacks",
    ),
    (
        "the threshold is optimal",
        "no optimisation was performed against an objective",
    ),
    (
        "optimal threshold",
        "no optimisation was performed against an objective",
    ),
    (
        "guarantees detection",
        "the measured detection rate is below 1 for some attacks and some intensities",
    ),
    (
        "security parameter",
        "the sample size is an experimental design value, not a security parameter",
    ),
    (
        "security level",
        "no security level is established by a statistical consistency test",
    ),
    (
        "unconditional security",
        "unconditional security requires a proof that was not constructed here",
    ),
    (
        "always detected",
        "the measured detection rate is below 1 for some attacks and intensities",
    ),
    (
        "all attacks are covered",
        "only six modelled attack families were measured",
    ),
    (
        "formal cryptographic proof",
        "no formal cryptographic proof was constructed at this milestone",
    ),
    (
        "composable security",
        "no composition theorem was proven, so no composable-security claim holds",
    ),
    (
        "device-independent secure",
        "no device-independent security property was established",
    ),
    (
        "device-independent security",
        "no device-independent security property was established",
    ),
    (
        "deterministic finite-shot acceptance",
        "acceptance in sampled mode is a finite-shot outcome, not a deterministic "
        "property",
    ),
)


BANNED_TERMINOLOGY: Tuple[Tuple[str, str], ...] = (
    (
        "decoy",
        "'decoy' and 'decoy-state' belong to QKD security analysis and imply a "
        "mechanism this construction does not have; the measurement bases here "
        "are protocol-determined and are not decoys",
    ),
    (
        "decoy-state",
        "'decoy-state' belongs to QKD security analysis and is not used in this "
        "project",
    ),
)


ALLOWED_QUALIFIERS: Tuple[str, ...] = (
    "empirical",
    "modelled",
    "at fraction",
    "under the calibrated",
)


_NEGATION_CUES: Tuple[str, ...] = (
    "no",
    "not",
    "never",
    "none",
    "nothing",
    "nobody",
    "cannot",
    "can not",
    "without",
    "neither",
    "nor",
    "isn't",
    "aren't",
    "doesn't",
    "don't",
    "didn't",
    "wasn't",
    "weren't",
)


_NEGATION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(cue) for cue in _NEGATION_CUES) + r")\b"
)




_CLAUSE_BOUNDARY = re.compile(r"[.;:,!?]")


def _clause_start(lowered: str, index: int) -> int:
    """Return the offset where the clause ending at ``index`` begins."""
    start = 0
    for boundary in _CLAUSE_BOUNDARY.finditer(lowered, 0, index):
        start = boundary.end()
    return start


def _is_negated(lowered: str, index: int) -> bool:
    """Return whether the clause immediately before ``index`` is negated.

    Only the current clause counts, so "a formal forgery bound, not a
    measurement" is still flagged: the negation there governs the clause after
    the phrase rather than the one containing it.
    """
    clause = lowered[_clause_start(lowered, index) : index]
    return _NEGATION_PATTERN.search(clause) is not None


def check_statement(statement: str) -> StatementCheck:
    """Return whether ``statement`` contains a forbidden claim or banned term.

    Matching is case-insensitive substring matching, which is deliberately
    blunt: a check that a clever phrasing can slip past is worse than no check,
    because it creates the impression of having been verified.

    A forbidden *phrase* is excused when the clause immediately preceding it is
    negated, so that disclosing a limitation ("no formal forgery bound is
    derived") is not punished as though it were the claim itself. Banned
    *terminology* is not excused: "decoy" is not used here in any construction.
    """
    if not isinstance(statement, str):
        raise TypeError(f"statement must be a string, got {type(statement).__name__}")
    lowered = statement.lower()

    violations: list[str] = []
    reasons: list[str] = []

    for pattern, reason in FORBIDDEN_PATTERNS:
        positions = [match.start() for match in re.finditer(re.escape(pattern), lowered)]
        if positions and any(not _is_negated(lowered, index) for index in positions):
            violations.append(pattern)
            reasons.append(reason)

    for term, reason in BANNED_TERMINOLOGY:
        if term in lowered:
            violations.append(term)
            reasons.append(reason)

    verdict = (
        StatementVerdict.FORBIDDEN if violations else StatementVerdict.ALLOWED
    )
    return StatementCheck(
        statement=statement,
        verdict=verdict,
        violations=tuple(violations),
        reasons=tuple(reasons),
    )


def check_statements(statements: Sequence[str]) -> Tuple[StatementCheck, ...]:
    """Return one check per statement."""
    return tuple(check_statement(statement) for statement in statements)


def render_forbidden_examples() -> Tuple[str, ...]:
    """Return the canonical forbidden claims, for a report's appendix."""
    return tuple(claim for claim, _ in FORBIDDEN_CLAIMS)


def render_measurement_statement(
    *,
    state_count: int,
    measurement_mode: str,
    shot_count: int,
    noise_type: str,
    noise_strength: float,
    honest_trials: int,
    frr: float | None,
    attack_type: str,
    attack_fraction: float,
    detection_rate: float | None,
    far: float | None = None,
) -> str:
    """Render an allowed statement from measured numbers.

    Every qualifier is load-bearing. Removing the sample size, the calibrated
    channel, the word "empirical", or the attack intensity changes what the
    sentence asserts, which is exactly why they are all present.
    """
    frr_text = "undefined" if frr is None else f"{frr * 100:.2f}%"
    detection_text = (
        "undefined" if detection_rate is None else f"{detection_rate * 100:.2f}%"
    )
    acceptance_text = "undefined" if far is None else f"{far * 100:.2f}%"

    return (
        f"At N={int(state_count)} under the calibrated honest {noise_type} channel "
        f"at eta={float(noise_strength):g}, measured in "
        f"{measurement_mode!r} mode with {int(shot_count)} shot(s) per state, the "
        f"empirical false-rejection rate was {frr_text} over {int(honest_trials)} "
        f"independent honest trials. Under the same configuration the empirical "
        f"acceptance rate for the modelled {attack_type} attack at "
        f"fraction={float(attack_fraction):g} was {acceptance_text}, i.e. an "
        f"empirical detection rate of {detection_text}. These are empirical rates "
        f"on this dataset at this sample size and channel; they are not a formal "
        f"forgery bound and they do not establish security."
    )


def build_interpretation_result(
    *,
    allowed_statements: Sequence[str] = (),
    context: Mapping[str, Any] | None = None,
    extra_statements_to_check: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> InterpretationResult:
    """Assemble the interpretation payload for a report.

    The forbidden claims and the banned terminology are included so that a reader
    sees the boundary rather than having to infer it, and the extra statements are
    checked so that a report can prove it stayed inside it.
    """
    composed = list(notes)
    composed.append(
        "the forbidden claims are listed so the boundary is visible; they are not "
        "a description of anything this project measured"
    )
    composed.append(
        "the four quantities that must not be conflated: a confidence interval is "
        "a statement about a parameter, a threshold is a decision rule, an "
        "empirical acceptance rate is a measurement, and a formal cryptographic "
        "security bound is a theorem. Only the first three are produced here."
    )
    return InterpretationResult(
        allowed_statements=tuple(allowed_statements),
        forbidden_claims=FORBIDDEN_CLAIMS,
        checks=check_statements(extra_statements_to_check),
        context=dict(context or {}),
        notes=tuple(composed),
    )
