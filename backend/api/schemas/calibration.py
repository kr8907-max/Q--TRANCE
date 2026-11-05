"""Schemas for calibration.

Two endpoints, deliberately different in cost:

* ``POST /calibration/run`` derives a threshold from an honest-only calibration
  dataset. It is the expensive one and it runs only when asked.
* ``GET /calibration/reference`` describes the reference methodology and, when
  the committed benchmark artifact is present, reports the operating point that
  was recorded for it.

Nothing here recalibrates implicitly. A verification request never triggers a
calibration, because a threshold derived on demand would not be the calibrated
object the report describes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from backend.api.config import (
    ABSOLUTE_MAX_CALIBRATION_SESSIONS,
    ABSOLUTE_MAX_SHOT_COUNT,
)
from backend.api.schemas.common import ApiModel, ProtocolVersion, configured_limit
from backend.protocol import PROTOCOL_VERSION
from backend.simulation import MEASUREMENT_MODES




_HOMOGENEITY_NOTE = (
    "per-state probability vector omitted: it is simulator-internal detail, and "
    "for the reference dataset it is tens of thousands of values"
)


class CalibrationConfigOut(ApiModel):
    """The configuration a calibration ran under."""

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
    dataset_role: str


class ConfidenceIntervalOut(ApiModel):
    """An exact binomial interval, as computed by the calibration layer."""

    lower: float
    upper: float
    confidence: float
    method: str
    one_sided: bool
    successes: int
    trials: int
    width: float


class HomogeneityOut(ApiModel):
    """Summary of the per-state homogeneity diagnostic."""

    homogeneous: bool
    spread: float
    tolerance: float
    minimum: float
    maximum: float
    mean: float
    state_count: int
    notes: List[str] = Field(default_factory=list)
    omitted: str = Field(default=_HOMOGENEITY_NOTE)


class ThresholdOut(ApiModel):
    """The derived decision threshold."""

    state_count: int
    p_upper: float = Field(description="One-sided upper bound on the honest mismatch probability.")
    critical_count: int = Field(description="Reject when the mismatch count exceeds this.")
    threshold_rate: float
    method: str
    alpha: float
    calibration_alpha: float
    evaluation_alpha: float
    calibration_fingerprint: str
    calibration_session_count: int
    calibration_total_valid: int
    calibration_total_mismatch: int
    calibration_pooled_rate: Optional[float] = None
    calibration_role: str


class OperatingPointOut(ApiModel):
    """The calibrated operating point."""

    name: str
    protocol_version: str
    noise_type: str
    noise_strength: float
    state_count: int
    measurement_mode: str
    shot_count: int
    calibration_seed_start: int
    calibration_seed_end: int
    observed_calibration_frr: Optional[float] = Field(
        default=None, description="Honest false-rejection rate observed on the calibration data."
    )
    threshold: ThresholdOut
    notes: List[str] = Field(default_factory=list)


class CalibrationRunRequest(ApiModel):
    """Request body for ``POST /calibration/run``."""

    config_id: str = Field(default="api-calibration", min_length=1, max_length=128)
    protocol_version: ProtocolVersion = Field(default=PROTOCOL_VERSION)
    noise_type: str = Field(default="depolarizing")
    noise_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    state_count: int = Field(default=100, ge=1, le=4096)
    measurement_mode: str = Field(default="sampled")
    shot_count: int = Field(
        default=1,
        ge=1,
        le=ABSOLUTE_MAX_SHOT_COUNT,
        description=(
            "Shots per state. The largest accepted value follows the application's "
            "configured shot bound."
        ),
    )
    confidence: float = Field(default=0.95, gt=0.0, lt=1.0)
    seed_start: int = Field(default=0, ge=0)
    session_count: int = Field(
        default=8,
        ge=1,
        le=ABSOLUTE_MAX_CALIBRATION_SESSIONS,
        description=(
            "Honest calibration sessions. Bounded so one request cannot run an "
            "unbounded study; the largest accepted value follows the application's "
            "configured session bound."
        ),
    )

    @field_validator("measurement_mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in MEASUREMENT_MODES:
            raise ValueError(f"unknown measurement_mode {value!r}; known: {list(MEASUREMENT_MODES)}")
        return value

    @field_validator("shot_count")
    @classmethod
    def _configured_shot_bound(cls, value: int, info) -> int:
        return configured_limit(value, info, "max_shot_count")

    @field_validator("session_count")
    @classmethod
    def _configured_session_bound(cls, value: int, info) -> int:
        return configured_limit(value, info, "max_calibration_sessions")


class CalibrationAssessment(ApiModel):
    """The boundary of a calibration result, stated explicitly."""

    status: str = Field(default="assumption_conditioned")
    formal_proof_present: bool = False
    limitations: List[str] = Field(default_factory=list)


class CalibrationResponse(ApiModel):
    """Result of a calibration run."""

    calibration_id: str
    config: CalibrationConfigOut
    total_valid: int
    total_mismatch: int
    pooled_rate: Optional[float] = None
    interval: Optional[ConfidenceIntervalOut] = None
    upper_bound: Optional[ConfidenceIntervalOut] = None
    homogeneity: HomogeneityOut
    threshold: ThresholdOut
    operating_point: OperatingPointOut
    notes: List[str] = Field(default_factory=list)
    security_assessment: CalibrationAssessment


class RecordedOperatingPointOut(ApiModel):
    """The operating point recorded in the committed benchmark artifact."""

    name: str
    protocol_version: str
    statistic: str
    state_count: int
    measurement_mode: str
    shot_count: int
    p_upper: float
    critical_count: int
    threshold_rate: float
    alpha: float
    noise_type: str
    noise_strength: float
    calibration_sessions: int
    observed_calibration_frr: Optional[float] = None


class ReferenceCalibrationResponse(ApiModel):
    """The reference methodology, plus the recorded operating point when available."""

    methodology: str
    statistic: str
    operating_point_name: str
    alpha: float
    calibration_alpha: float
    evaluation_alpha: float
    recorded_operating_point: Optional[RecordedOperatingPointOut] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    security_assessment: CalibrationAssessment
