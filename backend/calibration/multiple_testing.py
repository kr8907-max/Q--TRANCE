"""The multiple-comparison policy.

The defect this module exists to prevent
----------------------------------------
Milestone 4 exposes several statistics. Testing each of them at ``alpha = 0.05``
and then reporting "the combined false-positive rate is 5%" is invalid: with
``k`` independent tests at level ``alpha``, the family-wise error rate is
``1 - (1 - alpha)**k``, which reaches 40% at ``k = 10`` and 92% at ``k = 50``.
The milestone brief records this as a design defect found by the earlier
architecture audit, and this module is the machine-checkable answer to it.

The reference policy
--------------------
**One primary statistical verification test, plus diagnostic evidence that is
reported and never adjudicated.**

* Exactly one statistic is tested: the empirical verification mismatch rate
  ``D_m``, against the calibrated threshold. Its level is ``alpha``.
* Every other Milestone 4 quantity -- the verification-state disturbance rate,
  the projective match probability, the reconstruction fidelity, the per-basis
  mismatch and disturbance rates, the protocol consistency, authorization and
  replay findings -- is **diagnostic**. It is reported, it is not compared
  against a calibrated limit, and it does not move the decision.
* There is no family-wise correction in the reference policy, because with one
  test there is no family to correct for. The correction machinery is
  implemented so that a future design that *does* add tests cannot do so
  silently, and it is explicitly marked as unused here.

What is and is not part of the formal decision
----------------------------------------------
:func:`MultipleComparisonPolicy.is_part_of_decision` answers this in code, and
:meth:`~backend.calibration.models.VerificationDecision.decision_basis` records
it on every decision, so a reader never has to infer it from prose.

A joint acceptance region over several statistics could be mathematically
justified -- for example by deriving the null distribution of a combined
statistic under the honest model. It is **not** justified here, because no such
derivation has been done, and claiming one without it would be exactly the
overclaiming the brief forbids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Sequence, Tuple

__all__ = [
    "MultipleTestingPolicy",
    "DIAGNOSTIC_METRICS",
    "REFERENCE_PRIMARY_TEST",
    "MultipleComparisonPolicy",
    "family_wise_error_rate",
    "bonferroni_alpha",
    "holm_bonferroni",
    "reference_policy",
    "reject_multiple_primary_tests",
]


REFERENCE_PRIMARY_TEST = "mismatch_rate_against_calibrated_threshold"




DIAGNOSTIC_METRICS: Tuple[str, ...] = (
    "verification_state_disturbance_rate",
    "projective_match_probability",
    "reconstruction_fidelity",
    "minimum_fidelity",
    "measurement_counts_by_basis",
    "basis_distribution",
    "per_basis_mismatch_rates",
    "per_basis_disturbance_rates",
    "state_count_consistency",
    "transcript_validity",
    "transcript_hash_validity",
    "session_consistency",
    "nonce_freshness_state",
    "signer_authorization_validity",
    "verifier_authorization_validity",
    "cross_verifier_disagreement",
)


class MultipleTestingPolicy(str, Enum):
    """The multiple-comparison policies this project recognises."""


    SINGLE_PRIMARY_WITH_DIAGNOSTICS = "SINGLE_PRIMARY_WITH_DIAGNOSTICS"




    CORRECTED_FAMILY = "CORRECTED_FAMILY"


@dataclass(frozen=True)
class MultipleComparisonPolicy:
    """A declared policy for how many statistical tests are performed.

    A policy with more than one primary test must name a family-wise correction
    and a family-wise budget; :meth:`validate` enforces that, so an
    uncorrected multi-test design cannot be constructed at all.
    """

    policy: MultipleTestingPolicy
    primary_test: str
    diagnostic_metrics: Tuple[str, ...] = DIAGNOSTIC_METRICS
    family_wise_alpha: float | None = None
    correction: str | None = None
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:




        self.validate()

    def validate(self) -> "MultipleComparisonPolicy":
        if self.policy is MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS:
            if self.family_wise_alpha is not None:
                raise ValueError(
                    "a single-test policy has no family to correct for, so "
                    "family_wise_alpha must be None"
                )
            if self.correction is not None:
                raise ValueError(
                    "a single-test policy performs no correction, so correction "
                    "must be None"
                )
        elif self.policy is MultipleTestingPolicy.CORRECTED_FAMILY:
            if not self.correction:
                raise ValueError(
                    "a corrected family policy must name its correction"
                )
            if self.family_wise_alpha is None:
                raise ValueError(
                    "a corrected family policy must state a family-wise budget"
                )
            if not 0.0 < float(self.family_wise_alpha) < 1.0:
                raise ValueError(
                    f"family_wise_alpha must lie in (0, 1), got "
                    f"{self.family_wise_alpha!r}"
                )
        if self.primary_test in self.diagnostic_metrics:
            raise ValueError(
                f"{self.primary_test!r} is listed both as the primary test and as "
                f"a diagnostic metric"
            )
        if not self.primary_test:
            raise ValueError("primary_test must be named")
        return self

    def is_part_of_decision(self, metric: str) -> bool:
        """Return whether ``metric`` may influence the verification decision."""
        return metric == self.primary_test

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.value,
            "primary_test": self.primary_test,
            "diagnostic_metrics": list(self.diagnostic_metrics),
            "family_wise_alpha": self.family_wise_alpha,
            "correction": self.correction,
            "notes": list(self.notes),
        }


def reference_policy() -> MultipleComparisonPolicy:
    """Return the reference policy: one primary test, everything else diagnostic."""
    return MultipleComparisonPolicy(
        policy=MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS,
        primary_test=REFERENCE_PRIMARY_TEST,
        notes=(
            "exactly one statistic is tested; its level is the operating point's "
            "alpha, with no family to correct for",
            "every other Milestone 4 quantity is diagnostic evidence: reported, "
            "never adjudicated",
            "a joint acceptance region over several statistics is not "
            "implemented, because no honest-model derivation of one has been done",
        ),
    ).validate()


def family_wise_error_rate(alpha: float, tests: int) -> float:
    """Return ``1 - (1 - alpha) ** tests`` for independent tests.

    This is the number that makes the naive design indefensible: ten tests at
    5% give a 40% chance of at least one false rejection if ``H0`` holds.
    """
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")
    if isinstance(tests, bool) or not isinstance(tests, int) or tests < 1:
        raise ValueError(f"tests must be a positive int, got {tests!r}")
    return float(1.0 - (1.0 - float(alpha)) ** tests)


def bonferroni_alpha(alpha: float, tests: int) -> float:
    """Return the per-test level that keeps the family-wise rate at ``alpha``."""
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")
    if isinstance(tests, bool) or not isinstance(tests, int) or tests < 1:
        raise ValueError(f"tests must be a positive int, got {tests!r}")
    return float(alpha) / tests


def holm_bonferroni(
    p_values: Sequence[float],
    alpha: float,
) -> Tuple[bool, ...]:
    """Return Holm-Bonferroni rejection decisions for ``p_values``.

    Implemented so the corrected-family policy is real rather than described,
    and **not used** by the reference operating point: the reference performs a
    single test, so there is nothing to correct. It is exercised by the test
    suite to pin its behaviour, which is the point of having it at all.
    """
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")
    values = tuple(float(value) for value in p_values)
    for value in values:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"p-values must lie in [0, 1], got {value!r}")
    if not values:
        return ()

    order = sorted(range(len(values)), key=lambda index: values[index])
    decisions = [False] * len(values)
    total = len(values)
    for rank, index in enumerate(order):
        threshold = float(alpha) / (total - rank)
        if values[index] <= threshold:
            decisions[index] = True
        else:
            break
    return tuple(decisions)


def reject_multiple_primary_tests(primary_tests: Sequence[str]) -> None:
    """Raise unless exactly one primary test is declared.

    The reference design has one primary test. A caller that tries to register
    two is stopped here rather than allowed to produce a decision whose level is
    unknown.
    """
    declared = tuple(primary_tests)
    if len(declared) != 1:
        raise ValueError(
            f"the reference design performs exactly one primary statistical test; "
            f"got {len(declared)}: {list(declared)!r}. If several tests are "
            f"genuinely required, declare a CORRECTED_FAMILY policy with a "
            f"family-wise budget instead of adding uncorrected tests."
        )


def describe_diagnostics(
    diagnostics: Mapping[str, Any],
    policy: MultipleComparisonPolicy | None = None,
) -> Dict[str, Any]:
    """Return ``diagnostics`` annotated with their decision status.

    Every diagnostic is labelled with whether it is part of the decision. The
    answer is always "no" under the reference policy, and it is attached to the
    values themselves so a consumer cannot lose the distinction.
    """
    active = (policy or reference_policy()).validate()
    return {
        name: {
            "value": value,
            "part_of_decision": active.is_part_of_decision(name),
        }
        for name, value in diagnostics.items()
    }
