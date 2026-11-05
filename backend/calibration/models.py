"""Strongly typed models for Milestone 5 calibration.

Everything the calibration layer passes around is an explicit frozen dataclass
or a string-valued enum. Dictionaries appear only at the serialization boundary,
where an explicit ``to_dict`` produces them.

Terminology, fixed once here
----------------------------
The milestone brief requires four quantities that are routinely confused to be
kept apart. They are four different types in this module, not four numbers in a
dictionary:

``ConfidenceInterval``
    A statement about a **parameter** given a sample. It says where the true
    per-state mismatch probability plausibly lies. It is *not* a decision rule.

``ThresholdResult``
    A **decision rule**: a critical count of mismatches for a session of a
    stated size, derived from a confidence bound and a stated error budget.

``CalibrationResult``
    The **honest-only** evidence a threshold was derived from: counts, a pooled
    rate, an interval, and the conditions they were measured under.

``OperatingPoint``
    The single, named, reproducible bundle of the above that the evaluation
    layer uses.

None of these is a cryptographic security parameter, and none of them is a
forgery probability. Those are different objects in a different layer, and
:mod:`backend.security.interpretation` is where the distinction is enforced.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Tuple

__all__ = [
    "STATISTIC_MISMATCH_RATE",
    "SUPPORTED_STATISTICS",
    "DatasetRole",
    "ConfidenceInterval",
    "HomogeneityDiagnostic",
    "CalibrationConfig",
    "CalibrationObservation",
    "CalibrationResult",
    "ThresholdConfig",
    "ThresholdResult",
    "VerificationDecision",
    "OperatingPoint",
]








STATISTIC_MISMATCH_RATE = "mismatch_rate"



SUPPORTED_STATISTICS: Tuple[str, ...] = (STATISTIC_MISMATCH_RATE,)


class DatasetRole(str, Enum):
    """Which part of the calibration/evaluation split a record belongs to.

    The role travels with every observation so that "did a threshold ever see
    the data it is scored on?" is answerable by inspection rather than by trust.
    """


    CALIBRATION = "CALIBRATION"

    VALIDATION = "VALIDATION"

    FINAL_EVALUATION = "FINAL_EVALUATION"


@dataclass(frozen=True)
class ConfidenceInterval:
    """An interval estimate for a binomial probability.

    ``method`` names the construction, so a reader can look up its assumptions
    instead of guessing. The reference construction is Clopper-Pearson, which is
    *exact* in the sense that its coverage is at least ``confidence`` for every
    true probability -- it never understates the uncertainty.
    """

    successes: int
    trials: int
    lower: float
    upper: float
    confidence: float
    method: str
    one_sided: bool

    @property
    def width(self) -> float:
        """Return ``upper - lower``."""
        return self.upper - self.lower

    def to_dict(self) -> Dict[str, Any]:
        return {
            "successes": self.successes,
            "trials": self.trials,
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
            "method": self.method,
            "one_sided": self.one_sided,
            "width": self.width,
        }


@dataclass(frozen=True)
class HomogeneityDiagnostic:
    """How far the honest null is from a single-parameter Bernoulli model.

    The binomial model behind a Clopper-Pearson interval assumes one probability
    shared by every trial. Under an honest channel that is true when the channel
    acts identically on every reference state (the depolarizing channel does:
    every state's projective match probability is ``1 - p/2``) and false when it
    does not (a bit-flip channel leaves ``|+>`` untouched but flips ``|0>``).

    The diagnostic is computed from the verifier's own analytic
    ``probability_expected`` values, which are observable, so it needs no ground
    truth. It reports the spread of the implied per-state mismatch
    probabilities and states plainly whether the binomial assumption is exact
    for the measured configuration or only an approximation.
    """

    state_count: int
    predicted_probabilities: Tuple[float, ...]
    minimum: float | None
    maximum: float | None
    mean: float | None
    spread: float | None
    homogeneous: bool | None
    tolerance: float
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_count": self.state_count,
            "predicted_probabilities": list(self.predicted_probabilities),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "spread": self.spread,
            "homogeneous": self.homogeneous,
            "tolerance": self.tolerance,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class CalibrationConfig:
    """The conditions a calibration dataset was collected under.

    Every field is an input. Nothing derived -- no rate, no threshold -- is
    stored here, so the configuration can be hashed, diffed and replayed.
    """

    config_id: str
    protocol_version: str
    noise_type: str
    noise_strength: float
    state_count: int
    measurement_mode: str
    shot_count: int
    statistic: str
    confidence: float
    seed_start: int
    session_count: int
    dataset_role: DatasetRole

    def validate(self) -> "CalibrationConfig":
        if self.statistic not in SUPPORTED_STATISTICS:
            raise ValueError(
                f"statistic must be one of {list(SUPPORTED_STATISTICS)}, "
                f"got {self.statistic!r}"
            )
        if not 0.0 < float(self.confidence) < 1.0:
            raise ValueError(
                f"confidence must lie in (0, 1), got {self.confidence!r}"
            )
        if self.session_count < 1:
            raise ValueError(
                f"session_count must be at least 1, got {self.session_count}"
            )
        if self.state_count < 1:
            raise ValueError(f"state_count must be at least 1, got {self.state_count}")
        if self.seed_start < 0:
            raise ValueError(f"seed_start must be non-negative, got {self.seed_start}")
        if self.dataset_role is not DatasetRole.CALIBRATION:
            raise ValueError(
                "a calibration configuration must carry DatasetRole.CALIBRATION; "
                f"got {self.dataset_role.value!r}. Fitting a threshold on any other "
                "role would break the calibration/evaluation split."
            )
        return self

    def seed_range(self) -> Tuple[int, int]:
        """Return the inclusive ``(first, last)`` seed of the dataset."""
        return self.seed_start, self.seed_start + self.session_count - 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "protocol_version": self.protocol_version,
            "noise_type": self.noise_type,
            "noise_strength": float(self.noise_strength),
            "state_count": int(self.state_count),
            "measurement_mode": self.measurement_mode,
            "shot_count": int(self.shot_count),
            "statistic": self.statistic,
            "confidence": float(self.confidence),
            "seed_start": int(self.seed_start),
            "session_count": int(self.session_count),
            "dataset_role": self.dataset_role.value,
        }

    def fingerprint(self) -> str:
        """Return a stable SHA-256 fingerprint of the configuration."""
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class CalibrationObservation:
    """One honest session's contribution to a calibration dataset.

    This is the *only* shape the calibration layer accepts as input, and it has
    no field for an attack type, an attack fraction, a noise label or a
    ground-truth flag. A calibration dataset therefore cannot carry a label even
    if a caller wanted it to.

    ``analytic_match_probabilities`` are the verifier's own per-state projective
    match probabilities ``q_i`` (``probability_expected``). They are observable
    -- the verifier computes them -- and they are what lets the calibration layer
    check whether the binomial assumption is exact for the configuration rather
    than assuming it.
    """

    experiment_id: str
    random_seed: int
    state_count: int
    n_valid: int
    n_mismatch: int
    mismatch_rate: float | None
    dataset_role: DatasetRole
    timestamp: str | None = None
    analytic_match_probabilities: Tuple[float, ...] = ()
    mean_fidelity: float | None = None
    per_basis_mismatch_rates: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> "CalibrationObservation":
        if self.dataset_role is not DatasetRole.CALIBRATION:
            raise ValueError(
                "a calibration observation must carry DatasetRole.CALIBRATION; "
                f"got {self.dataset_role.value!r}"
            )
        if self.n_valid < 0:
            raise ValueError(f"n_valid must be non-negative, got {self.n_valid}")
        if not 0 <= self.n_mismatch <= self.n_valid:
            raise ValueError(
                f"n_mismatch must lie in [0, {self.n_valid}], got {self.n_mismatch}"
            )
        if self.n_valid > 0:
            expected = self.n_mismatch / self.n_valid
            if self.mismatch_rate is None or abs(self.mismatch_rate - expected) > 1e-12:
                raise ValueError(
                    f"mismatch_rate must equal n_mismatch / n_valid = {expected!r}, "
                    f"got {self.mismatch_rate!r}"
                )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "random_seed": int(self.random_seed),
            "state_count": int(self.state_count),
            "n_valid": int(self.n_valid),
            "n_mismatch": int(self.n_mismatch),
            "mismatch_rate": self.mismatch_rate,
            "dataset_role": self.dataset_role.value,
            "timestamp": self.timestamp,
            "analytic_match_probabilities": list(self.analytic_match_probabilities),
            "mean_fidelity": self.mean_fidelity,
            "per_basis_mismatch_rates": dict(self.per_basis_mismatch_rates),
        }


@dataclass(frozen=True)
class CalibrationResult:
    """The honest baseline a threshold is derived from.

    ``pooled_rate`` treats every usable verification state as one Bernoulli
    observation, which is what the null model asserts. ``per_session_rates``
    keeps the session-level view, because a calibration dataset whose sessions
    disagree far more than the binomial model predicts is evidence that the
    independence assumption is strained, and that should be visible rather than
    averaged away.
    """

    config: CalibrationConfig
    observations: Tuple[CalibrationObservation, ...]
    total_valid: int
    total_mismatch: int
    pooled_rate: float | None
    interval: ConfidenceInterval | None
    upper_bound: ConfidenceInterval | None
    per_session_rates: Tuple[float, ...]
    homogeneity: HomogeneityDiagnostic
    notes: Tuple[str, ...] = ()

    @property
    def session_count(self) -> int:
        """Return the number of honest sessions in the dataset."""
        return len(self.observations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "config_fingerprint": self.config.fingerprint(),
            "session_count": self.session_count,
            "total_valid": self.total_valid,
            "total_mismatch": self.total_mismatch,
            "pooled_rate": self.pooled_rate,
            "interval": None if self.interval is None else self.interval.to_dict(),
            "upper_bound": (
                None if self.upper_bound is None else self.upper_bound.to_dict()
            ),
            "per_session_rates": list(self.per_session_rates),
            "homogeneity": self.homogeneity.to_dict(),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ThresholdConfig:
    """How a threshold is derived, and with what error budget.

    ``alpha`` is the **total** per-session false-rejection budget. It is split
    across the two places randomness enters the construction:

    * ``alpha * calibration_alpha_fraction`` is spent on the one-sided upper
      confidence bound for the honest mismatch probability (the calibration
      sample is finite, so the bound itself can be wrong);
    * the remainder is spent on the quantile of the honest null distribution
      (the session being tested is itself a finite sample).

    Splitting the budget is what makes the *total* false-rejection probability
    bounded by ``alpha`` rather than by roughly twice it. The split is a
    parameter, not a hidden constant, and the resulting empirical rate is
    measured rather than assumed.
    """

    alpha: float = 0.05
    calibration_alpha_fraction: float = 0.5
    method: str = "honest-null-quantile-with-upper-confidence-bound"

    @property
    def calibration_alpha(self) -> float:
        """Return the share of ``alpha`` spent on the confidence bound."""
        return self.alpha * self.calibration_alpha_fraction

    @property
    def evaluation_alpha(self) -> float:
        """Return the share of ``alpha`` spent on the null-distribution quantile."""
        return self.alpha * (1.0 - self.calibration_alpha_fraction)

    def validate(self) -> "ThresholdConfig":
        if not 0.0 < float(self.alpha) < 1.0:
            raise ValueError(f"alpha must lie in (0, 1), got {self.alpha!r}")
        if not 0.0 < float(self.calibration_alpha_fraction) < 1.0:
            raise ValueError(
                "calibration_alpha_fraction must lie in (0, 1), got "
                f"{self.calibration_alpha_fraction!r}"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha": float(self.alpha),
            "calibration_alpha_fraction": float(self.calibration_alpha_fraction),
            "calibration_alpha": self.calibration_alpha,
            "evaluation_alpha": self.evaluation_alpha,
            "method": self.method,
        }


@dataclass(frozen=True)
class ThresholdResult:
    """A decision rule, fully traceable to how it was derived.

    Every field a reader needs in order to reproduce the number is present:
    which calibration dataset, which method, which error budget, which sample
    size, and the resulting critical count. There is no default threshold
    anywhere in this project, and this record is what makes that checkable.
    """

    state_count: int
    p_upper: float
    critical_count: int
    threshold_rate: float
    config: ThresholdConfig
    calibration_fingerprint: str
    calibration_session_count: int
    calibration_total_valid: int
    calibration_total_mismatch: int
    calibration_pooled_rate: float | None
    calibration_role: DatasetRole

    def rejects(self, n_mismatch: int, n_valid: int) -> bool:
        """Return whether a session is inconsistent with the honest model.

        A session with fewer usable observations than the threshold was derived
        for is **not** silently accepted: the rule is defined only for its own
        sample size, and using it at another size would be exactly the mistake
        the milestone brief warns about. Such a session raises.
        """
        if n_valid != self.state_count:
            raise ValueError(
                f"this threshold was derived for {self.state_count} usable "
                f"observations and is not defined for {n_valid}; derive a "
                f"threshold for the sample size you are testing"
            )
        return n_mismatch > self.critical_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_count": int(self.state_count),
            "p_upper": self.p_upper,
            "critical_count": int(self.critical_count),
            "threshold_rate": self.threshold_rate,
            "config": self.config.to_dict(),
            "calibration_fingerprint": self.calibration_fingerprint,
            "calibration_session_count": int(self.calibration_session_count),
            "calibration_total_valid": int(self.calibration_total_valid),
            "calibration_total_mismatch": int(self.calibration_total_mismatch),
            "calibration_pooled_rate": self.calibration_pooled_rate,
            "calibration_role": self.calibration_role.value,
        }


@dataclass(frozen=True)
class VerificationDecision:
    """Layer A of the dual-layer decision: the statistical verification result.

    ``diagnostics`` carries the other Milestone 4 statistics. They are reported
    and are explicitly **not** part of the decision -- see
    :mod:`backend.calibration.multiple_testing` for why, and
    :attr:`decision_basis` for the machine-readable statement of what the
    decision was actually made from.
    """

    rejected: bool
    statistic: str
    observed_rate: float | None
    observed_count: int
    sample_size: int
    threshold_rate: float
    critical_count: int
    operating_point: str
    explanation: str
    decision_basis: Tuple[str, ...]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rejected": self.rejected,
            "statistic": self.statistic,
            "observed_rate": self.observed_rate,
            "observed_count": int(self.observed_count),
            "sample_size": int(self.sample_size),
            "threshold_rate": self.threshold_rate,
            "critical_count": int(self.critical_count),
            "operating_point": self.operating_point,
            "explanation": self.explanation,
            "decision_basis": list(self.decision_basis),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class OperatingPoint:
    """The one reference operating point of the project.

    It bundles a :class:`ThresholdResult` with the conditions it belongs to and
    the honest false-rejection rate observed on the calibration data itself.

    The word "optimal" is deliberately absent. No optimisation was performed
    against an explicit objective, so no claim of optimality is made. The point
    is *specified*: one method, one error budget, one sample size, one honest
    channel configuration.
    """

    name: str
    threshold: ThresholdResult
    protocol_version: str
    noise_type: str
    noise_strength: float
    state_count: int
    measurement_mode: str
    shot_count: int
    calibration_seed_start: int
    calibration_seed_end: int
    observed_calibration_frr: float | None
    notes: Tuple[str, ...] = ()

    @property
    def statistic(self) -> str:
        """Return the single primary statistic this point tests."""
        return STATISTIC_MISMATCH_RATE

    def decide(
        self,
        *,
        n_mismatch: int,
        n_valid: int,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> VerificationDecision:
        """Apply the operating point to one session's observable statistics."""
        rejected = self.threshold.rejects(n_mismatch, n_valid)
        rate = (n_mismatch / n_valid) if n_valid > 0 else None
        if rejected:
            explanation = (
                f"the empirical verification mismatch rate {rate!r} exceeds the "
                f"calibrated threshold {self.threshold.threshold_rate!r} for "
                f"{self.threshold.state_count} observations at alpha="
                f"{self.threshold.config.alpha!r}: the session is not consistent "
                f"with the calibrated honest model"
            )
        else:
            explanation = (
                f"the empirical verification mismatch rate {rate!r} is within the "
                f"calibrated threshold {self.threshold.threshold_rate!r} for "
                f"{self.threshold.state_count} observations at alpha="
                f"{self.threshold.config.alpha!r}: the session is consistent with "
                f"the calibrated honest model"
            )
        return VerificationDecision(
            rejected=rejected,
            statistic=STATISTIC_MISMATCH_RATE,
            observed_rate=rate,
            observed_count=int(n_mismatch),
            sample_size=int(n_valid),
            threshold_rate=self.threshold.threshold_rate,
            critical_count=self.threshold.critical_count,
            operating_point=self.name,
            explanation=explanation,
            decision_basis=(
                f"{STATISTIC_MISMATCH_RATE} > {self.threshold.critical_count} "
                f"(critical count for n={self.threshold.state_count})",
                "one primary statistical test; no other statistic enters the "
                "decision",
                "the test is a statistical consistency test against a calibrated "
                "honest model, not a proof of security",
            ),
            diagnostics=dict(diagnostics or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "statistic": STATISTIC_MISMATCH_RATE,
            "protocol_version": self.protocol_version,
            "noise_type": self.noise_type,
            "noise_strength": float(self.noise_strength),
            "state_count": int(self.state_count),
            "measurement_mode": self.measurement_mode,
            "shot_count": int(self.shot_count),
            "calibration_seed_start": int(self.calibration_seed_start),
            "calibration_seed_end": int(self.calibration_seed_end),
            "observed_calibration_frr": self.observed_calibration_frr,
            "threshold": self.threshold.to_dict(),
            "notes": list(self.notes),
        }
