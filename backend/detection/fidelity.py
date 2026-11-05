"""Fidelity: the analytic overlap between the expected state and what arrived.

Definition
----------
For a pure expected state ``|psi>`` and the received qubit ``rho`` the fidelity
is::

    F = <psi|rho|psi>

The Milestone 1 core proves (``backend/quantum/density.py``) that for a pure
expected state this is *identically* the projective match probability
``p_match = Tr(P_psi rho)``, not merely approximately equal. The verifier
already computes that quantity per state as ``probability_expected``, so this
module does not recompute any quantum state: it aggregates the value the
verifier observed.

    analytic_mean_fidelity = mean_i probability_expected_i

Distinguishing the two fidelities
---------------------------------
The milestone brief asks for a clear separation between

**analytic fidelity from a state representation**
    ``F = <psi|rho|psi>``, an exact number. Reported here as
    :attr:`FidelityAnalysis.analytic_mean_fidelity`, together with the minimum
    over the session.

**empirical sampled verification probability**
    The frequency with which finite-shot measurement outcomes agreed with the
    expectation, i.e. the observed match frequency. Only meaningful in the
    ``"sampled"`` measurement mode; ``None`` otherwise. Reported as
    :attr:`FidelityAnalysis.sampled_match_frequency`.

They are different kinds of quantity -- one exact, one an estimator -- and they
are never averaged together or presented as two independent signals.

Redundancy, stated rather than hidden
-------------------------------------
Per state, ``F_i == p_match_i == probability_expected_i``. Therefore:

* the mean analytic fidelity **is** the mean projective match probability --
  one number, not two;
* ``1 - analytic_mean_fidelity`` is the mean per-state *mismatch probability*,
  which is **not** the mismatch rate ``D_m``: ``D_m`` counts states whose
  fidelity fell below ``1 - tolerance``, whereas ``1 - mean(F)`` averages the
  shortfall. They agree only in the extremes (all states exact, or all states
  fully depolarised), and the difference is reported in
  :attr:`FidelityAnalysis.notes`.

The detector therefore reports fidelity once and points at the redundancy
instead of double-counting it as independent evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from backend.detection.models import StateEvidence

__all__ = ["FidelityAnalysis", "analyse_fidelity"]


SAMPLED_MEASUREMENT_MODE = "sampled"


ANALYTIC_MEASUREMENT_MODE = "projective-analytic"


@dataclass(frozen=True)
class FidelityAnalysis:
    """Fidelity statistics for one session."""

    n_valid: int
    n_malformed: int
    analytic_mean_fidelity: float | None
    analytic_min_fidelity: float | None
    mean_mismatch_probability: float | None
    sampled_match_frequency: float | None
    sampled_match_count: int | None
    measurement_mode: str
    defined: bool
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_valid": self.n_valid,
            "n_malformed": self.n_malformed,
            "analytic_mean_fidelity": self.analytic_mean_fidelity,
            "analytic_min_fidelity": self.analytic_min_fidelity,
            "mean_mismatch_probability": self.mean_mismatch_probability,
            "sampled_match_frequency": self.sampled_match_frequency,
            "sampled_match_count": self.sampled_match_count,
            "measurement_mode": self.measurement_mode,
            "defined": self.defined,
            "notes": list(self.notes),
        }


def analyse_fidelity(
    states: Sequence[StateEvidence],
    *,
    measurement_mode: str = "unknown",
) -> FidelityAnalysis:
    """Return the fidelity analysis for ``states``.

    Aggregates ``probability_expected`` -- which the verifier computed as the
    projective match probability of the received qubit, and which the Milestone
    1 core proves equals ``<psi|rho|psi>`` -- and, in sampled mode, the observed
    match frequency.
    """
    records = tuple(states)
    notes: list[str] = []

    probabilities = [
        float(record.probability_expected) for record in records if record.usable
    ]
    n_valid = len(probabilities)
    n_malformed = len(records) - n_valid

    if n_malformed:
        notes.append(
            f"{n_malformed} observation(s) had no usable projective probability "
            f"and were excluded"
        )

    if n_valid == 0:
        notes.append(
            "no usable observations: fidelity is undefined rather than assumed"
        )
        return FidelityAnalysis(
            n_valid=0,
            n_malformed=n_malformed,
            analytic_mean_fidelity=None,
            analytic_min_fidelity=None,
            mean_mismatch_probability=None,
            sampled_match_frequency=None,
            sampled_match_count=None,
            measurement_mode=measurement_mode,
            defined=False,
            notes=tuple(notes),
        )

    mean_fidelity = sum(probabilities) / n_valid
    min_fidelity = min(probabilities)
    mean_mismatch_probability = 1.0 - mean_fidelity

    notes.append(
        "per state the analytic fidelity equals the projective match probability "
        "the verifier computed; the mean fidelity and the mean projective match "
        "probability are therefore one number, not two"
    )
    notes.append(
        "1 - mean(fidelity) is the mean mismatch probability, which is not the "
        "mismatch rate: the rate counts states below the tolerance, the mean "
        "averages the shortfall"
    )

    sampled_frequency: float | None = None
    sampled_count: int | None = None
    if measurement_mode == SAMPLED_MEASUREMENT_MODE:
        matched = [
            1 for record in records if record.usable and record.matched is True
        ]
        sampled_count = len(matched)
        sampled_frequency = len(matched) / n_valid
        notes.append(
            "the sampled match frequency is a finite-shot estimator of the same "
            "quantity, not an independent measurement"
        )
    else:
        notes.append(
            "no finite-shot match frequency: this session's measurement mode is "
            f"{measurement_mode!r}, whose outcomes are deterministic"
        )

    return FidelityAnalysis(
        n_valid=n_valid,
        n_malformed=n_malformed,
        analytic_mean_fidelity=mean_fidelity,
        analytic_min_fidelity=min_fidelity,
        mean_mismatch_probability=mean_mismatch_probability,
        sampled_match_frequency=sampled_frequency,
        sampled_match_count=sampled_count,
        measurement_mode=measurement_mode,
        defined=True,
        notes=tuple(notes),
    )
