"""Mismatch analysis: the empirical rate of disagreeing verification outcomes.

Definition
----------
Given ``N_valid`` usable per-state observations and ``N_mismatch`` of them whose
observed outcome disagreed with the expected eigenvalue::

    D_m = N_mismatch / N_valid

``N_valid`` counts only records that are actually usable (see
:attr:`~backend.detection.models.StateEvidence.usable`). Records that are
missing or malformed are counted separately and excluded from the denominator,
because silently folding them in as "matches" would understate the rate and
folding them in as "mismatches" would overstate it. Neither is honest.

Failure behaviour (documented, and tested)
------------------------------------------
============================  ============================================
condition                     behaviour
============================  ============================================
``N_valid == 0``              ``mismatch_rate`` is ``None``, ``defined`` is
                              ``False``; no division is attempted
missing observations          counted in ``n_missing``, excluded from the
                              denominator, reported in ``notes``
malformed observations        counted in ``n_malformed``, excluded, reported
``N_valid > 0``               exact point estimate plus an exact
                              Clopper-Pearson interval
============================  ============================================

What this module does not do
----------------------------
It does not compare ``D_m`` against any threshold, and it does not decide
attack/no-attack. It produces a measurement. A reference expectation may be
supplied by the caller (see
:class:`~backend.detection.models.DetectorParameters`), in which case the
*engine* -- not this module -- labels the strength of the deviation.

``D_m`` versus ``D_v``
----------------------
In the deterministic ``"projective-analytic"`` measurement mode, "the outcome
disagreed" and "the received state is not the expected eigenstate" are the same
event, so ``D_m`` and the verification-state disturbance rate ``D_v`` coincide
exactly. In ``"sampled"`` mode they differ: ``D_m`` is a finite-shot outcome
frequency while ``D_v`` is computed from the analytic projective probability.
See :mod:`backend.detection.disturbance`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from backend.detection.models import StateEvidence
from backend.detection.statistics import DEFAULT_CONFIDENCE, RateEstimate, estimate_rate

__all__ = ["MismatchAnalysis", "analyse_mismatch"]


@dataclass(frozen=True)
class MismatchAnalysis:
    """The mismatch statistic for one session's observations."""

    n_total: int
    n_valid: int
    n_mismatch: int
    n_missing: int
    n_malformed: int
    mismatch_rate: float | None
    rate_estimate: RateEstimate | None
    defined: bool
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_total": self.n_total,
            "n_valid": self.n_valid,
            "n_mismatch": self.n_mismatch,
            "n_missing": self.n_missing,
            "n_malformed": self.n_malformed,
            "mismatch_rate": self.mismatch_rate,
            "rate_estimate": (
                None if self.rate_estimate is None else self.rate_estimate.to_dict()
            ),
            "defined": self.defined,
            "notes": list(self.notes),
        }


def analyse_mismatch(
    states: Sequence[StateEvidence],
    *,
    declared_state_count: int | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
) -> MismatchAnalysis:
    """Return the mismatch analysis for ``states``.

    ``declared_state_count`` is the count the transcript claims. When it exceeds
    the number of supplied records the difference is reported as missing
    observations; it is never invented as a match or a mismatch.
    """
    records = tuple(states)
    notes: list[str] = []

    n_valid = sum(1 for record in records if record.usable)
    n_malformed = len(records) - n_valid
    n_mismatch = sum(
        1 for record in records if record.usable and record.matched is False
    )

    n_missing = 0
    if declared_state_count is not None and declared_state_count > len(records):
        n_missing = declared_state_count - len(records)

    if n_malformed:
        notes.append(
            f"{n_malformed} observation(s) were malformed or incomplete and were "
            f"excluded from the denominator"
        )
    if n_missing:
        notes.append(
            f"{n_missing} declared state(s) had no observation at all and were "
            f"excluded from the denominator"
        )

    if n_valid == 0:
        notes.append(
            "no usable observations: the mismatch rate is undefined rather than "
            "zero"
        )
        return MismatchAnalysis(
            n_total=len(records),
            n_valid=0,
            n_mismatch=0,
            n_missing=n_missing,
            n_malformed=n_malformed,
            mismatch_rate=None,
            rate_estimate=None,
            defined=False,
            notes=tuple(notes),
        )

    estimate = estimate_rate(n_mismatch, n_valid, confidence=confidence)
    return MismatchAnalysis(
        n_total=len(records),
        n_valid=n_valid,
        n_mismatch=n_mismatch,
        n_missing=n_missing,
        n_malformed=n_malformed,
        mismatch_rate=estimate.rate,
        rate_estimate=estimate,
        defined=True,
        notes=tuple(notes),
    )
