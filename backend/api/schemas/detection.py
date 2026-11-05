"""Schemas for the detection endpoint.

Observable input only
---------------------
The request model mirrors :class:`backend.detection.models.ObservableDetectionInput`
and nothing else. It has no field for ``attack_type``, ``attack_fraction``,
``noise_strength`` or any ground-truth metadata, and ``extra="forbid"`` means a
caller who sends one gets a 422 rather than having it quietly dropped.

That is the whole point: the detector must not be reachable with a shortcut to
the answer. If a request could carry an attack label, a client could learn the
label from the response and mistake it for detection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from backend.api.config import ABSOLUTE_MAX_MESSAGE_CHARS
from backend.api.schemas.common import ApiModel, configured_limit


class StateEvidenceIn(ApiModel):
    """One verification state as the verifier observed it."""

    index: int = Field(ge=0)
    basis: Optional[str] = None
    expected_bit: Optional[int] = None
    probability_expected: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    matched: Optional[bool] = None


class VerificationEvidenceIn(ApiModel):
    """What the verification step reported, as input to detection."""

    available: bool = True
    accepted: Optional[bool] = None
    session_valid: Optional[bool] = None
    message_valid: Optional[bool] = None
    transcript_valid: Optional[bool] = None
    state_sequence_valid: Optional[bool] = None
    measurement_valid: Optional[bool] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    declared_mismatch_count: Optional[int] = Field(default=None, ge=0)
    declared_basis_counts: Dict[str, int] = Field(default_factory=dict)
    measurement_summary: Dict[str, int] = Field(default_factory=dict)


class DetectionRequest(ApiModel):
    """Observable-only detection input.

    There is deliberately no attack, noise or ground-truth field. Adding one
    would make the detector reachable with the answer already in hand.
    """

    session_id: Optional[str] = None
    nonce: Optional[str] = None
    protocol_version: Optional[str] = None
    message_binding: Optional[str] = None
    declared_transcript_hash: Optional[str] = None
    signer_id: Optional[str] = None
    verifier_id: Optional[str] = None
    created_at: Optional[str] = None
    message: Optional[str] = Field(
        default=None,
        max_length=ABSOLUTE_MAX_MESSAGE_CHARS,
        description=(
            "Observed message, when the caller has one. The accepted length follows "
            "the application's configured message bound."
        ),
    )
    verifier_context_id: Optional[str] = None
    expected_protocol_version: Optional[str] = None
    authorized_signers: List[str] = Field(default_factory=list, max_length=64)
    authorized_verifiers: List[str] = Field(default_factory=list, max_length=64)
    reported_signer_authorized: Optional[bool] = None
    reported_verifier_authorized: Optional[bool] = None
    transcript_payload: Optional[Dict[str, Any]] = None
    transcript_parse_error: Optional[str] = None
    states: List[StateEvidenceIn] = Field(default_factory=list)
    declared_state_count: Optional[int] = Field(default=None, ge=0)
    measurement_mode: Optional[str] = None
    basis_counts: Dict[str, int] = Field(default_factory=dict)
    verification: VerificationEvidenceIn = Field(default_factory=VerificationEvidenceIn)
    consume_replay: bool = Field(
        default=False,
        description=(
            "When true, this event is recorded in the shared replay ledger. The "
            "ledger is in-memory and is lost on restart."
        ),
    )

    @field_validator("message")
    @classmethod
    def _configured_message_bound(cls, value: Optional[str], info) -> Optional[str]:
        return configured_limit(value, info, "max_message_chars")





class RateEstimateOut(ApiModel):
    """An estimated rate with its interval."""

    successes: int
    trials: int
    confidence: float
    rate: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    defined: bool


class MismatchAnalysisOut(ApiModel):
    n_total: int
    n_valid: int
    n_mismatch: int
    n_missing: int
    n_malformed: int
    mismatch_rate: Optional[float] = None
    rate_estimate: Optional[RateEstimateOut] = None
    defined: bool
    notes: List[str] = Field(default_factory=list)


class DisturbanceAnalysisOut(ApiModel):
    n_verification_states: int
    n_disturbed: int
    n_undisturbed: int
    n_missing: int
    n_malformed: int
    disturbance_rate: Optional[float] = None
    rate_estimate: Optional[RateEstimateOut] = None
    tolerance: float
    defined: bool
    identical_to_mismatch: bool
    notes: List[str] = Field(default_factory=list)


class FidelityAnalysisOut(ApiModel):
    n_valid: int
    n_malformed: int
    analytic_mean_fidelity: Optional[float] = None
    analytic_min_fidelity: Optional[float] = None
    mean_mismatch_probability: Optional[float] = None
    sampled_match_frequency: Optional[float] = None
    sampled_match_count: Optional[int] = None
    measurement_mode: Optional[str] = None
    defined: bool
    notes: List[str] = Field(default_factory=list)


class BasisStatisticsOut(ApiModel):
    observed_bases: List[str]
    counts: Dict[str, int]
    distribution: Dict[str, float]
    mismatch_counts: Dict[str, int]
    mismatch_rates: Dict[str, Optional[float]]
    disturbance_counts: Dict[str, int]
    disturbance_rates: Dict[str, Optional[float]]
    disturbed_bases: List[str]


class DetectionFeaturesOut(ApiModel):
    """Diagnostic statistics. Reported as evidence, never as a decision."""

    mismatch: MismatchAnalysisOut
    disturbance: DisturbanceAnalysisOut
    fidelity: FidelityAnalysisOut
    basis: BasisStatisticsOut
    measurement_counts_by_basis: Dict[str, int]
    basis_distribution: Dict[str, float]
    mismatch_rate: Optional[float] = None
    projective_match_probability: Optional[float] = None
    reconstruction_fidelity: Optional[float] = None
    verification_state_disturbance_rate: Optional[float] = None
    state_count_consistency: Optional[bool] = None
    transcript_validity: Optional[bool] = None
    transcript_hash_validity: Optional[bool] = None
    session_consistency: Optional[bool] = None
    nonce_freshness_state: Optional[bool] = None
    signer_authorization_validity: Optional[bool] = None
    verifier_authorization_validity: Optional[bool] = None
    cross_verifier_disagreement: Optional[Any] = Field(
        default=None,
        description="Reserved: no cross-verifier comparison is modelled in the reference prototype.",
    )
    redundancies: Dict[str, str] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class EvidenceItemOut(ApiModel):
    name: str
    observed: Any = None
    expected: Any = None
    source: str
    explanation: str


class ThreatEvidenceOut(ApiModel):
    """One finding. Structured evidence, with no attribution of a cause."""

    category: str
    severity: str
    calibration: str
    blocking: bool
    explanation: str
    finding_id: str
    strength: Optional[float] = None
    evidence_items: List[EvidenceItemOut] = Field(default_factory=list)
    observed_values: Dict[str, Any] = Field(default_factory=dict)
    comparison_values: Dict[str, Any] = Field(default_factory=dict)
    source_metrics: List[str] = Field(default_factory=list)
    session_reference: Optional[str] = None
    timestamp: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class DetectionAssessment(ApiModel):
    """The security boundary of a detection result, stated explicitly.

    Deliberately not a boolean. There is no field here that says the session is
    secure, because a detection result cannot establish that.
    """

    status: str = Field(
        default="evidence_only",
        description="Always 'evidence_only': detection produces evidence, not a verdict.",
    )
    formal_proof_present: bool = False
    ground_truth_used: bool = False
    limitations: List[str] = Field(default_factory=list)


class DetectionResponse(ApiModel):
    """The M4 detection result, reported without reinterpretation."""

    protocol_valid: bool
    overall_status: str
    explanation: str
    finding_count: int
    findings: List[ThreatEvidenceOut]
    features: DetectionFeaturesOut
    diagnostic_statistics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic metrics recorded alongside the decision; not read by it.",
    )
    session_reference: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    security_assessment: DetectionAssessment
