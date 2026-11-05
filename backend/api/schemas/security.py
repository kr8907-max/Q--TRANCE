"""Schemas for the security-analysis endpoints.

The M6 boundaries are preserved, not summarised away
----------------------------------------------------
There is deliberately no ``secure: true`` anywhere in this module. A security
analysis result is a set of assumption-conditioned statements, and the response
shapes carry the boundary explicitly:

* every response embeds a :class:`SecurityAssessment` with
  ``formal_proof_present: false`` and the specific things that are **not**
  established;
* the observability response keeps the per-threat breakdown rather than
  collapsing it into "covered";
* the composition response keeps ``formal_composition_theorem_present: false``.

A consumer that wants a boolean has to invent one, and that is the point.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.config import ABSOLUTE_MAX_STATEMENTS_PER_REQUEST
from backend.api.schemas.common import ApiModel, configured_limit
from backend.noise import VALID_NOISE_TYPES
from backend.simulation import MEASUREMENT_MODES


COMMON_LIMITATIONS: tuple = (
    "results are conditional on the assumption register; if an assumption is "
    "violated the argument does not apply",
    "no formal composition theorem is present",
    "no formal QDS forgery bound was derived",
    "no universal attack detection is claimed; six attack families were modelled",
    "all results are from simulation; no hardware validation was performed",
)


class SecurityAssessment(ApiModel):
    """The boundary attached to every security-analysis response."""

    status: str = Field(
        default="assumption_conditioned",
        description="Never 'secure'. The analysis is conditional by construction.",
    )
    formal_proof_present: bool = False
    composable_security_established: bool = False
    universal_detection_guarantee: bool = False
    forgery_bound_derived: bool = False
    limitations: List[str] = Field(default_factory=list)


class AssumptionsQuery(BaseModel):
    """Query parameters for ``GET /security/assumptions``.

    Both values select *which* register is resolved, so both are constrained to
    the domains the simulation and security layers actually define. The accepted
    sets come from the domain constants the simulation and calibration request
    schemas already validate against, so there is one source of truth for each
    rather than a second copy in the API layer.

    A plain :class:`BaseModel` rather than an :class:`ApiModel`: the
    ``extra="forbid"`` rule governs a request body the caller composes, whereas an
    unknown *query* parameter is ignored today and this change does not alter
    that. Only these two parameters are validated.
    """

    model_config = ConfigDict(extra="ignore")

    noise_type: str = Field(
        default="depolarizing",
        description=(
            "Channel the register resolves for. One of: "
            + ", ".join(VALID_NOISE_TYPES)
            + "."
        ),
    )
    measurement_mode: str = Field(
        default="sampled",
        description=(
            "Measurement mode the register resolves for. One of: "
            + ", ".join(MEASUREMENT_MODES)
            + "."
        ),
    )

    @field_validator("noise_type")
    @classmethod
    def _known_channel(cls, value: str) -> str:
        if value not in VALID_NOISE_TYPES:
            raise ValueError(
                f"unknown noise_type {value!r}; known: {list(VALID_NOISE_TYPES)}"
            )
        return value

    @field_validator("measurement_mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in MEASUREMENT_MODES:
            raise ValueError(
                f"unknown measurement_mode {value!r}; known: {list(MEASUREMENT_MODES)}"
            )
        return value


class AssumptionOut(ApiModel):
    """One assumption, with its status and its consequence if violated."""

    key: str
    statement: str
    status: str
    evidence: str
    consequence_if_violated: str
    citation: Optional[str] = None


class AssumptionsResponse(ApiModel):
    """The assumption register for a configuration."""

    noise_type: str
    measurement_mode: str
    assumptions: List[AssumptionOut]
    summary: Dict[str, int]
    weaker_than_exact: List[str]
    by_status: Dict[str, List[str]]
    note: str
    security_assessment: SecurityAssessment


class ObservabilityRowOut(ApiModel):
    """One row of the threat-observability matrix."""

    threat: str
    quantum_disturbance: bool
    protocol_anomaly: bool
    authentication_evidence: bool
    replay_evidence: bool
    detector_visible_quantum: bool
    requires_classical_control: bool
    empirically_evaluated: bool
    covered_by_prototype: bool
    m5_detection_rate: Optional[float] = None
    m5_far: Optional[float] = None
    notes: List[str] = Field(default_factory=list)


class ObservabilityResponse(ApiModel):
    """What each modelled threat looks like to each layer."""

    rows: List[ObservabilityRowOut]
    quantum_visible: List[str] = Field(
        description="Threats the quantum mismatch-rate detector can see."
    )
    classical_only: List[str] = Field(
        description=(
            "Threats the quantum detector cannot see. They are a threat to the "
            "protocol layer, not undetectable by the system as a whole."
        )
    )
    empirically_evaluated_count: int
    covered_count: int
    source: str
    security_assessment: SecurityAssessment


class CompositionRowOut(ApiModel):
    """One component's place in the security argument."""

    component: str
    property_evaluated: str
    evidence_source: str
    assumption_boundary: str
    composition_dependency: str
    unresolved_dependency: str
    security_conclusion: str


class CompositionResponse(ApiModel):
    """The composition assessment."""

    components: List[CompositionRowOut]
    component_count: int
    unresolved_count: int
    formal_composition_theorem_present: bool
    note: str
    security_assessment: SecurityAssessment


class AnalyzeRequest(ApiModel):
    """Request body for ``POST /security/analyze``.

    The caller supplies sentences; the API returns what the interpretation layer
    says about them. This is the machine-checkable half of the security argument:
    a report can prove it stayed inside the boundary.
    """

    statements: List[str] = Field(
        default_factory=list,
        max_length=ABSOLUTE_MAX_STATEMENTS_PER_REQUEST,
        description=(
            "Sentences to check against the forbidden-claim register. The largest "
            "accepted list follows the application's configured statement bound."
        ),
    )
    context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("statements")
    @classmethod
    def _configured_statement_bound(cls, value: List[str], info) -> List[str]:
        return configured_limit(value, info, "max_statements_per_request")


class StatementCheckOut(ApiModel):
    """The verdict for one statement."""

    statement: str
    verdict: str = Field(description="ALLOWED or FORBIDDEN.")
    violations: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class AnalyzeResponse(ApiModel):
    """Interpretation of the supplied statements."""

    checks: List[StatementCheckOut]
    forbidden_claims: List[Dict[str, str]] = Field(
        description="The claims the project must not make, each with its reason."
    )
    banned_terminology: List[Dict[str, str]] = Field(
        description="Terminology this project does not use, each with its reason."
    )
    allowed_statement_example: Optional[str] = Field(
        default=None,
        description=(
            "The shape an allowed measurement statement takes, rendered from the "
            "committed benchmark so the numbers in it are measured numbers. Null "
            "when the artifact is absent: the example is omitted rather than "
            "invented."
        ),
    )
    notes: List[str] = Field(default_factory=list)
    security_assessment: SecurityAssessment
