"""The assumptions the finite-sample results depend on.

Why this is a register and not a paragraph
------------------------------------------
Every number this milestone reports is conditional. A confidence interval is
conditional on independence; a binomial null is conditional on homogeneity; a
detection rate is conditional on the attack being non-adaptive. If those
conditions are stated in prose in a document, they drift out of step with the
code. Here they are records with a status, so a report can print exactly which
ones hold exactly, which hold approximately, and which are simply not verified.

The statuses are deliberately unforgiving. ``APPROXIMATE`` is not a synonym for
``SATISFIED``: it means the derivation assumed something the configuration does
not provide, and the reported interval is therefore not exactly the interval the
method promises. There is no status meaning "probably fine".

The one that most often gets lost
---------------------------------
``homogeneity``. A single pooled binomial interval treats every usable state as
one draw from a *common* Bernoulli probability. For the depolarizing channel that
is exact, because every state has the same projective match probability
``1 - eta/2``. For the bit-flip, phase-flip and bit-phase-flip channels it is
**not** exact: the mismatch probability depends on the measurement basis, so the
mismatch count is Poisson-binomial rather than binomial, and a pooled binomial
interval is an approximation. The register says so, and
:func:`~backend.calibration.baseline.build_homogeneity_diagnostic` measures it
from the observable data rather than assuming it.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from backend.security.finite_size import (
    CLOPPER_PEARSON_CITATION,
    HOEFFDING_CITATION,
)
from backend.security.models import (
    Assumption,
    AssumptionRegister,
    AssumptionStatus,
)

__all__ = [
    "REFERENCE_ASSUMPTIONS",
    "reference_assumptions",
    "summarise_assumptions",
    "EXACT_STATUSES",
    "WEAK_STATUSES",
]


EXACT_STATUSES: Tuple[AssumptionStatus, ...] = (
    AssumptionStatus.EXACT,
    AssumptionStatus.SATISFIED,
)


WEAK_STATUSES: Tuple[AssumptionStatus, ...] = (
    AssumptionStatus.APPROXIMATE,
    AssumptionStatus.NOT_VERIFIED,
    AssumptionStatus.VIOLATED,
)


def _homogeneity_assumption(noise_type: str) -> Assumption:
    """Return the homogeneity assumption for a channel model."""
    if noise_type == "depolarizing":
        return Assumption(
            key="homogeneous_mismatch_probability",
            statement=(
                "every usable verification state shares one mismatch probability, "
                "so the pooled mismatch count is Binomial(N, p)"
            ),
            status=AssumptionStatus.EXACT,
            evidence=(
                "for the depolarizing channel the received state is "
                "(1-p)rho + p I/2, so the projective match probability is "
                "1 - p/2 for every state regardless of basis; the per-state "
                "probability is therefore constant by algebra, not by assumption"
            ),
            consequence_if_violated=(
                "the pooled binomial interval would be an approximation; the "
                "mismatch count would be Poisson-binomial and the interval could "
                "be too narrow"
            ),
            citation=CLOPPER_PEARSON_CITATION,
        )
    if noise_type == "none":
        return Assumption(
            key="homogeneous_mismatch_probability",
            statement=(
                "every usable verification state shares one mismatch probability"
            ),
            status=AssumptionStatus.EXACT,
            evidence=(
                "with no channel the match probability is 1 for every state, so "
                "the common probability is 1 and the mismatch probability is 0"
            ),
            consequence_if_violated="not applicable: the channel is the identity",
        )
    return Assumption(
        key="homogeneous_mismatch_probability",
        statement=(
            "every usable verification state shares one mismatch probability"
        ),
        status=AssumptionStatus.APPROXIMATE,
        evidence=(
            f"the {noise_type} channel applies a fixed Pauli with a fixed "
            "probability, so the resulting match probability depends on whether "
            "the measurement basis commutes with that Pauli; the mismatch count "
            "is Poisson-binomial, not binomial"
        ),
        consequence_if_violated=(
            "the pooled binomial interval is an approximation for this channel; "
            "the homogeneity diagnostic in the calibration record measures how "
            "far apart the per-state probabilities are, and the calibration notes "
            "say when the approximation is in force"
        ),
        citation=CLOPPER_PEARSON_CITATION,
    )




REFERENCE_ASSUMPTIONS: Tuple[Assumption, ...] = (
    Assumption(
        key="independence_within_session",
        statement=(
            "the mismatch indicators of distinct verification states are "
            "statistically independent"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "each signature state is a separate qubit prepared independently, the "
            "channel is a product channel, the measurements are separate, and the "
            "sampled outcome for state i is drawn from a generator stream derived "
            "from (random_seed, 'measurement', 'state', i), so the draws use "
            "independent streams by construction"
        ),
        consequence_if_violated=(
            "the binomial variance would be wrong and the interval would "
            "understate the uncertainty"
        ),
        citation=CLOPPER_PEARSON_CITATION,
    ),
    _homogeneity_assumption("depolarizing"),
    Assumption(
        key="sessions_are_independent",
        statement="different trials are independent draws, not repeated views",
        status=AssumptionStatus.EXACT,
        evidence=(
            "each trial uses a distinct random seed, and session_id, nonce and "
            "created_at are derived deterministically from that seed; the "
            "benchmark allocates disjoint seed blocks per dataset and "
            "assert_disjoint_seeds raises if two blocks ever collide"
        ),
        consequence_if_violated=(
            "the trials would be correlated and the effective sample size would "
            "be smaller than the nominal one"
        ),
    ),
    Assumption(
        key="calibration_is_honest_only",
        statement="no attack data influences the baseline, the interval or the threshold",
        status=AssumptionStatus.EXACT,
        evidence=(
            "CalibrationObservation has no field that could carry an attack type, "
            "an attack fraction, a noise label or a ground-truth flag; "
            "build_calibration_dataset constructs an honest attack configuration "
            "for every calibration run; and estimate_baseline refuses any "
            "observation whose dataset role is not CALIBRATION"
        ),
        consequence_if_violated=(
            "the threshold would be fitted to the attacks it is meant to detect "
            "and the reported false-rejection rate would be meaningless"
        ),
    ),
    Assumption(
        key="calibration_and_evaluation_are_disjoint",
        statement="the data the threshold is fitted on is not the data it is scored on",
        status=AssumptionStatus.EXACT,
        evidence=(
            "the benchmark draws calibration, validation and final-evaluation "
            "datasets from disjoint seed blocks, and SeedAllocator.verify_disjoint "
            "checks this before any result is reported; "
            "EvaluationConfig.validate refuses the CALIBRATION role outright"
        ),
        consequence_if_violated=(
            "the reported false-rejection rate would be a fitted quantity rather "
            "than an independent estimate"
        ),
    ),
    Assumption(
        key="stationary_channel_within_a_population",
        statement="every trial in a population sees the same channel configuration",
        status=AssumptionStatus.EXACT,
        evidence=(
            "the channel type and strength are fixed in the configuration and only "
            "the seed varies between trials; the configuration is recorded with "
            "each result"
        ),
        consequence_if_violated=(
            "a population would mix conditions and its rate would describe no "
            "single configuration"
        ),
    ),
    Assumption(
        key="born_rule_sampling",
        statement=(
            "a sampled measurement outcome is a draw from the projective "
            "probability, not a deterministic property"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "the runner draws rng.binomial(shot_count, probability) and compares "
            "the majority to the expected bit, so the outcome distribution is the "
            "Born distribution of the received state"
        ),
        consequence_if_violated=(
            "the sampled mismatch rate would not estimate the projective mismatch "
            "probability"
        ),
    ),
    Assumption(
        key="threshold_is_conditional_on_its_conditions",
        statement=(
            "the threshold is valid only at its calibrated sample size, "
            "measurement mode, shot count and channel"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "ThresholdResult.rejects raises when a session's usable-observation "
            "count differs from the size the threshold was derived for, rather "
            "than silently accepting or rejecting it"
        ),
        consequence_if_violated=(
            "using a threshold outside its conditions would be the category error "
            "the milestone brief warns about"
        ),
    ),
    Assumption(
        key="single_primary_statistical_test",
        statement="exactly one statistical test decides, so there is no family to correct",
        status=AssumptionStatus.EXACT,
        evidence=(
            "the reference multiple-comparison policy is "
            "SINGLE_PRIMARY_WITH_DIAGNOSTICS with family_wise_alpha None and "
            "correction None; every other statistic is reported as a diagnostic "
            "and no joint acceptance region is claimed"
        ),
        consequence_if_violated=(
            "testing several statistics each at alpha would inflate the "
            "family-wise error rate above alpha"
        ),
    ),
    Assumption(
        key="attacks_are_non_adaptive",
        statement=(
            "the modelled attack is fixed before the run and does not adapt to the "
            "verifier's measurement outcomes"
        ),
        status=AssumptionStatus.SATISFIED,
        evidence=(
            "every attack in backend.attacks acts on the received states before "
            "verification and takes no input from the verifier's outcomes"
        ),
        consequence_if_violated=(
            "an adaptive adversary could choose its disturbance after seeing which "
            "states were measured in which basis; that is outside the scope of "
            "this milestone and is not covered by any number reported here"
        ),
    ),
    Assumption(
        key="measurement_mode_is_the_operational_definition",
        statement=(
            "'matched' means what the configured measurement mode defines it to "
            "mean, and the statistics are about that definition"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "in 'projective-analytic' mode 'matched' means the received qubit is "
            "the expected eigenstate; in 'sampled' mode it means the finite-shot "
            "majority agreed. The mode travels with every observation and is "
            "recorded in every calibration configuration and every report"
        ),
        consequence_if_violated=(
            "two sessions measured in different modes would not be comparable, "
            "which is why the mode is never inferred and never defaulted silently"
        ),
    ),
    Assumption(
        key="no_label_reaches_the_decision",
        statement="no attack label can influence the verification decision",
        status=AssumptionStatus.EXACT,
        evidence=(
            "the decision function takes only ObservableStatistics, whose fields "
            "are counts and rates; backend.detection may not import "
            "backend.attacks; and backend.calibration may not import "
            "backend.simulation or backend.attacks at all"
        ),
        consequence_if_violated=(
            "the reported detection rate would be circular"
        ),
    ),
    Assumption(
        key="finite_sample_bound_is_not_a_security_parameter",
        statement=(
            "a confidence interval or a concentration bound describes an "
            "estimator, not an adversary's advantage"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "FiniteSizeBound carries is_cryptographic_security_bound=False and "
            "raises if constructed with True, so the category error cannot be "
            "expressed"
        ),
        consequence_if_violated=(
            "quoting a confidence interval as a forgery probability would "
            "overstate what was actually shown"
        ),
        citation=HOEFFDING_CITATION,
    ),
    Assumption(
        key="protocol_binding_is_public_and_deterministic",
        statement=(
            "the message binding, the state-sequence derivation and the "
            "transcript canonicalisation are public and deterministic"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "the protocol's binding derivation is a public function of the "
            "message, the session identifier and the nonce; the state sequence "
            "is derived from the binding by a public algorithm; and the "
            "transcript hash is computed from the canonical payload"
        ),
        consequence_if_violated=(
            "a secret binding or a randomised canonicalisation would change "
            "what the protocol guarantees; the current construction makes no "
            "such guarantee and the assumption documents that"
        ),
    ),
    Assumption(
        key="classical_identity_is_bookkeeping_not_quantum",
        statement=(
            "signer and verifier identity checks are classical protocol "
            "controls, not quantum measurements"
        ),
        status=AssumptionStatus.EXACT,
        evidence=(
            "the authorization context is a deterministic membership test on "
            "declared identities; it involves no quantum state, no threshold "
            "and no statistical inference"
        ),
        consequence_if_violated=(
            "if identity were inferred from quantum measurement, the protocol "
            "would need a quantum authentication mechanism, which this "
            "construction does not provide"
        ),
    ),
)


def reference_assumptions(
    *,
    noise_type: str = "depolarizing",
    measurement_mode: str = "sampled",
) -> AssumptionRegister:
    """Return the assumption register for a configuration.

    The homogeneity assumption is the one that changes with the channel, so it is
    resolved from ``noise_type``. Passing a flip channel yields an
    ``APPROXIMATE`` status rather than a silently identical register.
    """
    assumptions = tuple(
        _homogeneity_assumption(noise_type)
        if item.key == "homogeneous_mismatch_probability"
        else item
        for item in REFERENCE_ASSUMPTIONS
    )
    if measurement_mode not in ("sampled", "projective-analytic"):
        assumptions = assumptions + (
            Assumption(
                key="recognised_measurement_mode",
                statement="the measurement mode is one the project defines",
                status=AssumptionStatus.VIOLATED,
                evidence=f"the configuration names {measurement_mode!r}",
                consequence_if_violated=(
                    "the meaning of 'matched' is undefined for this mode, so no "
                    "statistical statement can be made"
                ),
            ),
        )
    return AssumptionRegister(assumptions=assumptions)


def summarise_assumptions(register: AssumptionRegister) -> Mapping[str, Any]:
    """Return a compact, JSON-ready summary of an assumption register."""
    return {
        "summary": register.summary(),
        "weaker_than_exact": list(register.weaker_than_exact),
        "by_status": {key: list(value) for key, value in register.by_status.items()},
        "note": (
            "'approximate' means the derivation assumed something the "
            "configuration does not provide; it is not a synonym for 'satisfied'"
        ),
    }


def assumption_dict(assumption: Assumption) -> Dict[str, Any]:
    """Return one assumption as a plain mapping."""
    return assumption.to_dict()
