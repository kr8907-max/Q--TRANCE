"""Schemas for evaluation.

Evaluation is explicitly different from detection
-------------------------------------------------
An evaluation run *is allowed* to use ground truth: that is what makes FAR and
FRR computable at all. The separation the project maintains is between this
endpoint and the detection endpoint:

* ``POST /detect`` accepts observable input only and never sees a label;
* ``POST /evaluation/run`` consumes labels deliberately, and says so.

Every evaluation response therefore carries ``ground_truth_used: true`` and an
explicit assessment block, so a consumer cannot mistake a benchmark metric for an
operational detection result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from backend.api.schemas.calibration import RecordedOperatingPointOut
from backend.api.schemas.common import ApiModel



ALLOWED_PROFILES = ("smoke", "reference")


class EvaluationRunRequest(ApiModel):
    """Request body for ``POST /evaluation/run``."""

    profile: str = Field(
        default="smoke",
        description=(
            "'smoke' is the small, fast profile used by the test suite. "
            "'reference' is the full recorded benchmark and takes minutes."
        ),
    )

    @field_validator("profile")
    @classmethod
    def _known_profile(cls, value: str) -> str:
        if value not in ALLOWED_PROFILES:
            raise ValueError(
                f"unknown profile {value!r}; known: {list(ALLOWED_PROFILES)}"
            )
        return value


class ConfusionMatrixOut(ApiModel):
    """Counts behind every rate in this response."""

    tp: int
    tn: int
    fp: int
    fn: int
    total: Optional[int] = None
    honest: Optional[int] = None
    malicious: Optional[int] = None


class MetricsOut(ApiModel):
    """One operating point's measured rates.

    The names are the project's own. They are empirical rates measured on a
    dataset, not probabilities about an adversary.
    """

    confusion: ConfusionMatrixOut
    detection_rate: Optional[float] = None
    far: Optional[float] = Field(default=None, description="Empirical false acceptance rate.")
    frr: Optional[float] = Field(default=None, description="Empirical false rejection rate.")
    tpr: Optional[float] = None
    tnr: Optional[float] = None
    specificity: Optional[float] = None
    fnr: Optional[float] = None
    fpr: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    accuracy: Optional[float] = None
    far_definition: Optional[str] = None
    frr_definition: Optional[str] = None
    note: Optional[str] = None


class EvaluationConfigurationOut(ApiModel):
    """The configuration the evaluation ran under."""

    profile: str
    description: str
    state_count: int
    calibration_sessions: int
    evaluation_trials: int
    measurement_mode: str
    shot_count: int
    noise_type: str
    reference_noise_strength: float
    attack_types: List[str]
    attack_fraction: float
    seed_base: int


class EvaluationAssessment(ApiModel):
    """The boundary of an evaluation result, stated explicitly."""

    status: str = Field(default="empirical_measurement")
    ground_truth_used: bool = True
    formal_proof_present: bool = False
    limitations: List[str] = Field(default_factory=list)


class EvaluationSummary(ApiModel):
    """Compact evaluation result. Returned by run and by retrieval.

    There is deliberately no single "overall" confusion matrix. The M5 benchmark
    scores honest and malicious populations separately, and the per-attack rows
    contain no honest trials at all, so a pooled matrix would mix two different
    populations and report an FRR computed from zero honest sessions.
    """

    evaluation_id: str
    profile: str
    dataset_role: str
    seed_base: int
    configuration: EvaluationConfigurationOut
    operating_point: Optional[RecordedOperatingPointOut] = None
    by_attack_type: Dict[str, MetricsOut] = Field(
        default_factory=dict,
        description="One entry per modelled attack, each with its own confusion matrix.",
    )
    honest_frr_by_noise: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Honest false-rejection rate per noise level. This is the FRR side.",
    )
    detection_by_noise_and_attack: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Share of malicious trials rejected, per noise level and attack.",
    )
    curve_names: List[str] = Field(default_factory=list)
    sample_size_rows: int = 0
    runtime_seconds: Optional[float] = None
    ground_truth_used: bool = True
    security_assessment: EvaluationAssessment
    note: str = Field(
        default=(
            "These are empirical rates measured on modelled attacks at one "
            "configuration. They are not cryptographic bounds and they do not "
            "transfer to other conditions."
        )
    )


class EvaluationArtifactResponse(ApiModel):
    """The full benchmark report. Large; request it deliberately."""

    evaluation_id: str
    profile: str
    artifact: Dict[str, Any] = Field(
        description="The complete benchmark payload as produced by the M5 benchmark runner."
    )
    markdown: Optional[str] = Field(
        default=None,
        description="The same run rendered as a human-readable Markdown report.",
    )
    size_warning: str = Field(
        default=(
            "the reference artifact is on the order of megabytes; prefer the "
            "summary endpoint unless the full report is genuinely needed"
        )
    )
