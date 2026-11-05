"""Strongly typed models for Milestone 5 evaluation.

The naming problem this module solves
-------------------------------------
Two conventions for "false positive" are in common use and they disagree, so a
document that does not fix one is ambiguous. This module fixes it once, in code:

**The positive class is "the verification decision rejected the session"**, i.e.
"the session was found inconsistent with the calibrated honest model".

With that convention:

===========================  ==========================================
``tp``                       malicious trial, rejected
``fn``                       malicious trial, accepted
``fp``                       honest trial, rejected
``tn``                       honest trial, accepted
===========================  ==========================================

and therefore

===========================  ==========================================
detection rate / ``tpr``     ``tp / (tp + fn)`` = 1 - FAR
specificity / ``tnr``        ``tn / (tn + fp)`` = 1 - FRR
``fpr``                      ``fp / (fp + tn)`` = **FRR**
``fnr``                      ``fn / (fn + tp)`` = **FAR**
===========================  ==========================================

The identity ``FPR = FRR`` is a consequence of this convention, not an error,
and it is stated here because it is the single most common source of confusion
in detection reporting. ``FAR`` and ``FPR`` are *not* the same quantity: FAR is
the malicious acceptance rate, FPR is the honest rejection rate.

``precision``, ``recall`` and ``F1`` are computed because the brief asks for
them, and they are labelled **descriptive only**. F1 in particular is a
descriptive summary of a particular operating point; it is not a security
metric, and no claim about the protocol is derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Tuple

from backend.calibration.models import DatasetRole, VerificationDecision

__all__ = [
    "TrialOutcome",
    "ObservableStatistics",
    "TrialRecord",
    "EvaluationConfig",
    "ConfusionMatrix",
    "EvaluationMetrics",
    "CurvePoint",
    "CurveResult",
    "RobustnessResult",
    "PopulationSummary",
    "DiscriminationResult",
]


class TrialOutcome(str, Enum):
    """The decision a trial received, in the confusion-matrix convention."""

    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


@dataclass(frozen=True)
class ObservableStatistics:
    """The observable statistical summary of one trial.

    Every field is computed from evidence a legitimate verifier holds. There is
    no attack label, no attack fraction, no noise label and no ground-truth flag
    here, so a record of this type can be handed to the decision layer without
    any risk of label leakage.
    """

    n_valid: int
    n_mismatch: int
    mismatch_rate: float | None
    disturbance_rate: float | None
    mean_fidelity: float | None
    minimum_fidelity: float | None
    measurement_mode: str
    basis_counts: Mapping[str, int] = field(default_factory=dict)
    per_basis_mismatch_rates: Mapping[str, float] = field(default_factory=dict)
    per_basis_disturbance_rates: Mapping[str, float] = field(default_factory=dict)

    @property
    def basis_mismatch_dispersion(self) -> float | None:
        """Return ``max_basis_rate - min_basis_rate``, or ``None``.

        A fixed, non-learned structural descriptor: an attack that touches only
        some measurement bases produces a large dispersion, one that disturbs
        all bases alike produces a small one. It is a diagnostic and never part
        of the verification decision.
        """
        rates = [rate for rate in self.per_basis_mismatch_rates.values()]
        if not rates:
            return None
        return max(rates) - min(rates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_valid": int(self.n_valid),
            "n_mismatch": int(self.n_mismatch),
            "mismatch_rate": self.mismatch_rate,
            "disturbance_rate": self.disturbance_rate,
            "mean_fidelity": self.mean_fidelity,
            "minimum_fidelity": self.minimum_fidelity,
            "measurement_mode": self.measurement_mode,
            "basis_counts": dict(self.basis_counts),
            "per_basis_mismatch_rates": dict(self.per_basis_mismatch_rates),
            "per_basis_disturbance_rates": dict(self.per_basis_disturbance_rates),
            "basis_mismatch_dispersion": self.basis_mismatch_dispersion,
        }


@dataclass(frozen=True)
class TrialRecord:
    """One evaluation trial: observable statistics, decision, and ground truth.

    Ground truth is carried here because this type belongs to the evaluation
    layer, which is the only layer permitted to read it. The decision field was
    produced by a function that was handed the observable half alone, so the
    presence of a label on the record cannot have influenced it.
    """

    experiment_id: str
    random_seed: int
    scenario_fingerprint: str
    dataset_role: DatasetRole
    is_malicious: bool
    attack_type: str
    attack_fraction: float
    noise_type: str
    noise_strength: float
    state_count: int
    statistics: ObservableStatistics
    decision: VerificationDecision

    @property
    def outcome(self) -> TrialOutcome:
        """Return the decision as a confusion-matrix outcome."""
        return (
            TrialOutcome.REJECTED if self.decision.rejected else TrialOutcome.ACCEPTED
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "random_seed": int(self.random_seed),
            "scenario_fingerprint": self.scenario_fingerprint,
            "dataset_role": self.dataset_role.value,
            "is_malicious": self.is_malicious,
            "attack_type": self.attack_type,
            "attack_fraction": float(self.attack_fraction),
            "noise_type": self.noise_type,
            "noise_strength": float(self.noise_strength),
            "state_count": int(self.state_count),
            "outcome": self.outcome.value,
            "statistics": self.statistics.to_dict(),
            "decision": self.decision.to_dict(),
        }


@dataclass(frozen=True)
class EvaluationConfig:
    """What an evaluation run is measuring, and on which data.

    ``dataset_role`` is required to be a role other than ``CALIBRATION``:
    :meth:`validate` refuses to build an evaluation configuration that would
    score a threshold on the data it was fitted to.
    """

    evaluation_id: str
    dataset_role: DatasetRole
    state_count: int
    measurement_mode: str
    shot_count: int
    seed_start: int
    trial_count: int
    notes: Tuple[str, ...] = ()

    def validate(self) -> "EvaluationConfig":
        if self.dataset_role is DatasetRole.CALIBRATION:
            raise ValueError(
                "an evaluation configuration must not use the calibration role: "
                "scoring a threshold on the data it was fitted to is exactly the "
                "leakage the calibration/evaluation split exists to prevent"
            )
        if self.trial_count < 1:
            raise ValueError(f"trial_count must be at least 1, got {self.trial_count}")
        if self.state_count < 1:
            raise ValueError(f"state_count must be at least 1, got {self.state_count}")
        if self.seed_start < 0:
            raise ValueError(f"seed_start must be non-negative, got {self.seed_start}")
        return self

    def seed_range(self) -> Tuple[int, int]:
        """Return the inclusive ``(first, last)`` seed of the dataset."""
        return self.seed_start, self.seed_start + self.trial_count - 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "dataset_role": self.dataset_role.value,
            "state_count": int(self.state_count),
            "measurement_mode": self.measurement_mode,
            "shot_count": int(self.shot_count),
            "seed_start": int(self.seed_start),
            "trial_count": int(self.trial_count),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ConfusionMatrix:
    """Counts of the four trial outcomes, in the convention this module fixes.

    ``positive`` means "the verification decision rejected the session".
    """

    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        """Return the number of trials."""
        return self.tp + self.tn + self.fp + self.fn

    @property
    def malicious(self) -> int:
        """Return the number of malicious trials."""
        return self.tp + self.fn

    @property
    def honest(self) -> int:
        """Return the number of honest trials."""
        return self.tn + self.fp

    def __add__(self, other: "ConfusionMatrix") -> "ConfusionMatrix":
        if not isinstance(other, ConfusionMatrix):
            return NotImplemented
        return ConfusionMatrix(
            tp=self.tp + other.tp,
            tn=self.tn + other.tn,
            fp=self.fp + other.fp,
            fn=self.fn + other.fn,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tp": self.tp,
            "tn": self.tn,
            "fp": self.fp,
            "fn": self.fn,
            "total": self.total,
            "malicious": self.malicious,
            "honest": self.honest,
        }


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return ``numerator / denominator``, or ``None`` for an empty denominator.

    ``None`` rather than ``0.0``: "no honest trials were run" and "no honest
    trial was rejected" are different statements, and a rate that hides the
    difference is a rate that misleads.
    """
    if denominator == 0:
        return None
    return numerator / denominator


@dataclass(frozen=True)
class EvaluationMetrics:
    """Every rate the evaluation layer reports, derived from one confusion matrix.

    ``far`` and ``frr`` are the two the milestone brief defines explicitly:
    ``far`` is the malicious acceptance rate and ``frr`` is the honest rejection
    rate. ``fpr`` equals ``frr`` under the convention this module fixes, and
    ``fnr`` equals ``far``; both identities are computed independently so a test
    can assert them rather than trusting the derivation.
    """

    matrix: ConfusionMatrix

    @property
    def detection_rate(self) -> float | None:
        """Return ``tp / (tp + fn)``: the share of malicious trials rejected."""
        return _ratio(self.matrix.tp, self.matrix.malicious)

    @property
    def tpr(self) -> float | None:
        """Return the true positive rate, identical to the detection rate."""
        return self.detection_rate

    @property
    def specificity(self) -> float | None:
        """Return ``tn / (tn + fp)``: the share of honest trials accepted."""
        return _ratio(self.matrix.tn, self.matrix.honest)

    @property
    def tnr(self) -> float | None:
        """Return the true negative rate, identical to the specificity."""
        return self.specificity

    @property
    def fpr(self) -> float | None:
        """Return ``fp / (fp + tn)``, the honest rejection rate."""
        return _ratio(self.matrix.fp, self.matrix.honest)

    @property
    def fnr(self) -> float | None:
        """Return ``fn / (fn + tp)``, the malicious acceptance rate."""
        return _ratio(self.matrix.fn, self.matrix.malicious)

    @property
    def far(self) -> float | None:
        """Return the false acceptance rate: malicious accepted / malicious."""
        return self.fnr

    @property
    def frr(self) -> float | None:
        """Return the false rejection rate: honest rejected / honest."""
        return self.fpr

    @property
    def precision(self) -> float | None:
        """Return ``tp / (tp + fp)``. Descriptive only."""
        return _ratio(self.matrix.tp, self.matrix.tp + self.matrix.fp)

    @property
    def recall(self) -> float | None:
        """Return ``tp / (tp + fn)``. Descriptive only; equals the detection rate."""
        return self.detection_rate

    @property
    def f1(self) -> float | None:
        """Return the harmonic mean of precision and recall.

        **Descriptive only.** F1 summarises one operating point on one dataset.
        It is not a security metric and no protocol claim is derived from it.
        """
        precision = self.precision
        recall = self.recall
        if precision is None or recall is None or (precision + recall) == 0.0:
            return None
        return 2.0 * precision * recall / (precision + recall)

    @property
    def accuracy(self) -> float | None:
        """Return ``(tp + tn) / total``. Descriptive only."""
        return _ratio(self.matrix.tp + self.matrix.tn, self.matrix.total)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matrix": self.matrix.to_dict(),
            "detection_rate": self.detection_rate,
            "tpr": self.tpr,
            "specificity": self.specificity,
            "tnr": self.tnr,
            "fpr": self.fpr,
            "fnr": self.fnr,
            "far": self.far,
            "frr": self.frr,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "descriptive_only": ["precision", "recall", "f1", "accuracy"],
        }


@dataclass(frozen=True)
class CurvePoint:
    """One point on an evaluation curve, with the evidence behind it."""

    x: float
    y: float
    trials: int
    x_label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "trials": int(self.trials),
            "x_label": self.x_label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CurveResult:
    """A named curve, its points, and the conditions that produced them.

    Every point comes from a seeded run; the curve carries the seed range and
    the trial count per point so that a reader can reproduce it and a reviewer
    can check that no point is interpolated or synthetic.
    """

    name: str
    x_label: str
    y_label: str
    points: Tuple[CurvePoint, ...]
    conditions: Mapping[str, Any] = field(default_factory=dict)
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "points": [point.to_dict() for point in self.points],
            "conditions": dict(self.conditions),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PopulationSummary:
    """Descriptive statistics for one population of trials.

    ``mean_mismatch_rate`` is the marginal disturbance the population exhibits;
    ``mean_basis_dispersion`` and ``mean_fidelity`` are the structural
    descriptors used by the discrimination experiment. All three are observable
    quantities, so a summary can be computed without ground truth.
    """

    label: str
    trials: int
    mean_mismatch_rate: float | None
    minimum_mismatch_rate: float | None
    maximum_mismatch_rate: float | None
    mean_basis_dispersion: float | None
    minimum_basis_dispersion: float | None
    maximum_basis_dispersion: float | None
    mean_fidelity: float | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "trials": int(self.trials),
            "mean_mismatch_rate": self.mean_mismatch_rate,
            "minimum_mismatch_rate": self.minimum_mismatch_rate,
            "maximum_mismatch_rate": self.maximum_mismatch_rate,
            "mean_basis_dispersion": self.mean_basis_dispersion,
            "minimum_basis_dispersion": self.minimum_basis_dispersion,
            "maximum_basis_dispersion": self.maximum_basis_dispersion,
            "mean_fidelity": self.mean_fidelity,
        }


@dataclass(frozen=True)
class DiscriminationResult:
    """The outcome of the central discrimination experiment.

    ``distinguishable`` is the honest answer to "can the observable evidence
    tell these two populations apart?" under a fixed, non-learned, conservative
    criterion: the *ranges* of the chosen structural statistic must not overlap
    between the populations. Overlapping ranges mean "not distinguishable under
    the current observable model", which is a real result and is reported as
    such rather than dressed up.

    ``honest_rejection_rate`` and ``malicious_rejection_rate`` are what the
    calibrated marginal rule does to the two matched populations. They are
    reported as numbers and deliberately not reduced to a boolean: the point of
    the experiment is that these two numbers can be close while the structural
    descriptors differ, and a reader should see the closeness rather than be
    told it.

    ``descriptor_separation_rate`` is the share of malicious trials whose
    descriptor exceeds the honest maximum. It is a simple, declared statistic
    used to describe the degree of separation, not a trained classifier and not
    a security metric.
    """

    honest_label: str
    malicious_label: str
    honest_marginal: float | None
    malicious_marginal: float | None
    marginal_gap: float | None
    matched: bool
    descriptor: str
    honest_descriptor: PopulationSummary
    malicious_descriptor: PopulationSummary
    distinguishable: bool | None
    criterion: str
    verdict: str
    honest_rejection_rate: float | None = None
    malicious_rejection_rate: float | None = None
    descriptor_separation_rate: float | None = None
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "honest_label": self.honest_label,
            "malicious_label": self.malicious_label,
            "honest_marginal": self.honest_marginal,
            "malicious_marginal": self.malicious_marginal,
            "marginal_gap": self.marginal_gap,
            "matched": self.matched,
            "descriptor": self.descriptor,
            "honest_descriptor": self.honest_descriptor.to_dict(),
            "malicious_descriptor": self.malicious_descriptor.to_dict(),
            "distinguishable": self.distinguishable,
            "criterion": self.criterion,
            "verdict": self.verdict,
            "honest_rejection_rate": self.honest_rejection_rate,
            "malicious_rejection_rate": self.malicious_rejection_rate,
            "descriptor_separation_rate": self.descriptor_separation_rate,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class RobustnessResult:
    """Detection and false-rejection behaviour across a noise/attack grid."""

    name: str
    honest_frr_by_noise: Mapping[str, float | None]
    detection_by_noise_and_attack: Mapping[str, Mapping[str, float | None]]
    matrices: Mapping[str, ConfusionMatrix]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "honest_frr_by_noise": dict(self.honest_frr_by_noise),
            "detection_by_noise_and_attack": {
                key: dict(value)
                for key, value in self.detection_by_noise_and_attack.items()
            },
            "matrices": {
                key: matrix.to_dict() for key, matrix in self.matrices.items()
            },
            "notes": list(self.notes),
        }
