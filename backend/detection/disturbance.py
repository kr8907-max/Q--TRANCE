"""Verification-state disturbance: how often a received state is not the state
the reference expects.

Terminology
-----------
This statistic is called ``verification_state_disturbance_rate`` and nothing
else. It is **not** called "decoy disturbance", because no decoy-state protocol
is implemented anywhere in this project: there is no decoy intensity, no
signal/decoy ratio and no decoy analysis. Borrowing that vocabulary would
suggest a security argument the reference construction does not make.

Definition
----------
For each usable observation the verifier computes ``probability_expected``: the
analytic projective probability that the received qubit yields the expected
eigenvalue of the expected basis. A verification state is **disturbed** when
that probability is strictly below ``1 - tolerance``::

    N_disturbed = |{ i : probability_expected_i < 1 - tolerance }|
    D_v         = N_disturbed / N_verification_states

``tolerance`` is the floating-point tolerance that defines "the received qubit
*is* the expected eigenstate" -- the same constant the Milestone 2 verifier uses
(:data:`~backend.detection.models.DEFAULT_MEASUREMENT_TOLERANCE`). It is a
numerical definition, not a security threshold: for a noiseless, untampered
channel the projective probability is exactly 1 and ``D_v`` is exactly 0.

Saturation, and what it means
-----------------------------
Because the reference expectation is *exact*, ``D_v`` is a **detection**
indicator, not a magnitude indicator. Any nonzero channel deviation -- a
depolarizing probability of 0.001 just as much as an intercept-resend attack on
every state -- moves every projective probability strictly below 1, so
``D_v = 1`` in all of those cases. That is a true statement about the
mathematics, not a defect: it answers "has the channel changed anything at
all?", and it answers it sharply.

The *magnitude* of the deviation is carried by the fidelity
(:mod:`backend.detection.fidelity`), which varies continuously and is where a
reader should look for "how far from ideal". Reporting both, and saying which
one answers which question, is the point.

Relationship to the mismatch rate
---------------------------------
``D_v`` and ``D_m`` are **not** presented as independent evidence, and the
analysis reports whether they coincide:

``"projective-analytic"`` mode
    The outcome is deterministic, so "the outcome disagreed" is exactly "the
    state is disturbed". ``D_v`` and ``D_m`` are then the *same number computed
    from the same records*, and :attr:`DisturbanceAnalysis.identical_to_mismatch`
    is ``True``. They must never be counted as two signals.
``"sampled"`` mode
    ``D_m`` is a finite-shot outcome frequency, whereas ``D_v`` uses the
    analytic probability. They are genuinely different statistics --
    ``D_m`` is an estimator whose expectation is driven by the same probability
    threshold, but it fluctuates with the shot count. The two are then reported
    separately and the flag is ``False``.

Either way the redundancy is *stated*, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from backend.detection.models import DEFAULT_MEASUREMENT_TOLERANCE, StateEvidence
from backend.detection.mismatch import MismatchAnalysis
from backend.detection.statistics import DEFAULT_CONFIDENCE, RateEstimate, estimate_rate

__all__ = ["DisturbanceAnalysis", "analyse_disturbance"]


@dataclass(frozen=True)
class DisturbanceAnalysis:
    """The verification-state disturbance statistic for one session."""

    n_verification_states: int
    n_disturbed: int
    n_undisturbed: int
    n_missing: int
    n_malformed: int
    disturbance_rate: float | None
    rate_estimate: RateEstimate | None
    tolerance: float
    defined: bool
    identical_to_mismatch: bool
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_verification_states": self.n_verification_states,
            "n_disturbed": self.n_disturbed,
            "n_undisturbed": self.n_undisturbed,
            "n_missing": self.n_missing,
            "n_malformed": self.n_malformed,
            "disturbance_rate": self.disturbance_rate,
            "rate_estimate": (
                None if self.rate_estimate is None else self.rate_estimate.to_dict()
            ),
            "tolerance": self.tolerance,
            "defined": self.defined,
            "identical_to_mismatch": self.identical_to_mismatch,
            "notes": list(self.notes),
        }


def is_disturbed(
    state: StateEvidence, tolerance: float = DEFAULT_MEASUREMENT_TOLERANCE
) -> bool | None:
    """Return whether ``state`` is disturbed, or ``None`` when unusable.

    A state is disturbed when the analytic projective probability of the
    expected eigenvalue is strictly below ``1 - tolerance``.
    """
    if not state.usable:
        return None
    return float(state.probability_expected) < 1.0 - float(tolerance)


def analyse_disturbance(
    states: Sequence[StateEvidence],
    *,
    mismatch: MismatchAnalysis | None = None,
    declared_state_count: int | None = None,
    tolerance: float = DEFAULT_MEASUREMENT_TOLERANCE,
    confidence: float = DEFAULT_CONFIDENCE,
) -> DisturbanceAnalysis:
    """Return the verification-state disturbance analysis for ``states``.

    ``mismatch`` is the matching mismatch analysis, used only to *report*
    whether the two statistics coincide for this session. It never feeds the
    computation.
    """
    records = tuple(states)
    notes: list[str] = []

    verdicts = [is_disturbed(record, tolerance) for record in records]
    n_valid = sum(1 for verdict in verdicts if verdict is not None)
    n_disturbed = sum(1 for verdict in verdicts if verdict is True)
    n_undisturbed = n_valid - n_disturbed
    n_malformed = len(records) - n_valid

    n_missing = 0
    if declared_state_count is not None and declared_state_count > len(records):
        n_missing = declared_state_count - len(records)

    if n_malformed:
        notes.append(
            f"{n_malformed} observation(s) lacked a usable projective probability "
            f"and were excluded from the denominator"
        )
    if n_missing:
        notes.append(
            f"{n_missing} declared verification state(s) had no observation and "
            f"were excluded from the denominator"
        )

    identical = bool(
        mismatch is not None
        and mismatch.defined
        and n_valid == mismatch.n_valid
        and n_disturbed == mismatch.n_mismatch
    )
    if identical:
        notes.append(
            "disturbance and mismatch coincide for this session (deterministic "
            "measurement mode): they are one signal, not two"
        )
    elif mismatch is not None and mismatch.defined:
        notes.append(
            "disturbance and mismatch differ for this session: they are distinct "
            "statistics"
        )

    if n_valid == 0:
        notes.append(
            "no usable verification states: the disturbance rate is undefined "
            "rather than zero"
        )
        return DisturbanceAnalysis(
            n_verification_states=0,
            n_disturbed=0,
            n_undisturbed=0,
            n_missing=n_missing,
            n_malformed=n_malformed,
            disturbance_rate=None,
            rate_estimate=None,
            tolerance=float(tolerance),
            defined=False,
            identical_to_mismatch=False,
            notes=tuple(notes),
        )

    estimate = estimate_rate(n_disturbed, n_valid, confidence=confidence)
    return DisturbanceAnalysis(
        n_verification_states=n_valid,
        n_disturbed=n_disturbed,
        n_undisturbed=n_undisturbed,
        n_missing=n_missing,
        n_malformed=n_malformed,
        disturbance_rate=estimate.rate,
        rate_estimate=estimate,
        tolerance=float(tolerance),
        defined=True,
        identical_to_mismatch=identical,
        notes=tuple(notes),
    )
