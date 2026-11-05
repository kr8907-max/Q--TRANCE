"""Feature extraction: the explicit, documented observable feature set.

Every feature the engine uses is declared once, here, with:

definition
    what the number is
source
    which observable field it is computed from
meaning
    what it is mathematically
range
    its units and admissible values
failure behaviour
    what happens when the source data is missing or malformed

The catalog is data, not prose: :data:`FEATURE_CATALOG` is the single source of
truth, the test suite checks that every catalogued feature exists on
:class:`DetectionFeatures`, and the documentation test checks that the written
documentation still names the same features. That keeps "documentation matches
implementation" an executable property rather than a promise.

No composite scores
-------------------
There is no ``security_score``, no weighted sum and no single "threat number".
The milestone brief forbids them, and for good reason: a weighted sum would hide
exactly the structure the evidence is supposed to expose. Each feature stands on
its own, and where two features are mathematically the same signal the
redundancy is *stated* (see :attr:`DetectionFeatures.redundancies`).

Cross-verifier disagreement
---------------------------
The milestone brief lists it as a possible feature. The Milestone 2 and 3 data
model records exactly one verifier identity per session, so no cross-verifier
comparison is possible. Rather than invent a value, the feature is reported as
unavailable with the reason attached. When the data model grows a second
verifier view, this is the single place to fill in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from backend.detection.consistency import ConsistencyReport
from backend.detection.disturbance import DisturbanceAnalysis, analyse_disturbance
from backend.detection.fidelity import FidelityAnalysis, analyse_fidelity
from backend.detection.mismatch import MismatchAnalysis, analyse_mismatch
from backend.detection.models import (
    DEFAULT_MEASUREMENT_TOLERANCE,
    DetectorParameters,
    ObservableDetectionInput,
    StateEvidence,
)
from backend.detection.replay import ReplayEvidence
from backend.detection.authorization import AuthorizationReport

__all__ = [
    "FeatureDescriptor",
    "FEATURE_CATALOG",
    "BasisStatistics",
    "DetectionFeatures",
    "analyse_basis_statistics",
    "extract_features",
]


@dataclass(frozen=True)
class FeatureDescriptor:
    """The declared definition of one observable feature."""

    name: str
    definition: str
    source: str
    meaning: str
    range: str
    failure_behaviour: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "definition": self.definition,
            "source": self.source,
            "meaning": self.meaning,
            "range": self.range,
            "failure_behaviour": self.failure_behaviour,
        }




FEATURE_CATALOG: Mapping[str, FeatureDescriptor] = {
    "mismatch_rate": FeatureDescriptor(
        name="mismatch_rate",
        definition="D_m = N_mismatch / N_valid",
        source="per-state `matched` flags",
        meaning=(
            "empirical proportion of usable verification outcomes that disagreed "
            "with the expected eigenvalue"
        ),
        range="[0, 1], or undefined when N_valid = 0",
        failure_behaviour=(
            "undefined (None) when there are no usable observations; malformed "
            "records are counted separately and excluded from the denominator"
        ),
    ),
    "measurement_counts_by_basis": FeatureDescriptor(
        name="measurement_counts_by_basis",
        definition="count of usable observations per measurement basis",
        source="per-state `basis` field",
        meaning="the verifier's measurement-basis histogram for this session",
        range="non-negative integers summing to N_valid",
        failure_behaviour=(
            "records without a usable basis are excluded and reported as malformed"
        ),
    ),
    "basis_distribution": FeatureDescriptor(
        name="basis_distribution",
        definition="counts per basis divided by N_valid",
        source="measurement_counts_by_basis",
        meaning="empirical measurement-basis distribution",
        range="each entry in [0, 1]; entries sum to 1 when defined",
        failure_behaviour="empty mapping when N_valid = 0",
    ),
    "verification_state_disturbance_rate": FeatureDescriptor(
        name="verification_state_disturbance_rate",
        definition="D_v = N_disturbed / N_verification_states",
        source="per-state `probability_expected`",
        meaning=(
            "proportion of verification states whose analytic projective match "
            "probability fell below 1 - tolerance, i.e. the received qubit was "
            "not the expected eigenstate"
        ),
        range="[0, 1], or undefined when N_verification_states = 0",
        failure_behaviour=(
            "undefined (None) when no usable verification state exists; not "
            "called 'decoy disturbance' because no decoy protocol is implemented"
        ),
    ),
    "projective_match_probability": FeatureDescriptor(
        name="projective_match_probability",
        definition="mean_i probability_expected_i",
        source="per-state `probability_expected`",
        meaning=(
            "mean analytic probability that the received qubit yields the expected "
            "eigenvalue"
        ),
        range="[0, 1], or undefined when no usable observation exists",
        failure_behaviour="undefined (None) with no usable observations",
    ),
    "reconstruction_fidelity": FeatureDescriptor(
        name="reconstruction_fidelity",
        definition="mean_i <psi_i|rho_i|psi_i>",
        source="per-state `probability_expected`",
        meaning=(
            "analytic fidelity of the received state against the expected pure "
            "state; identical to the projective match probability for a pure "
            "expected state"
        ),
        range="[0, 1], or undefined when no usable observation exists",
        failure_behaviour=(
            "undefined (None) with no usable observations; mathematically "
            "redundant with projective_match_probability and declared as such"
        ),
    ),
    "state_count_consistency": FeatureDescriptor(
        name="state_count_consistency",
        definition="declared state_count equals the number of observed states",
        source="transcript `state_count` and the observation list",
        meaning="a protocol-structure invariant, not a statistic",
        range="True, False, or None when the declared count is unavailable",
        failure_behaviour="None when the declared count could not be read",
    ),
    "transcript_validity": FeatureDescriptor(
        name="transcript_validity",
        definition="the transcript parsed and satisfied every integrity check",
        source="the declared transcript payload",
        meaning="protocol-integrity property of the received artifact",
        range="True, False, or None when no transcript was supplied",
        failure_behaviour="None with no transcript; False when parsing failed",
    ),
    "transcript_hash_validity": FeatureDescriptor(
        name="transcript_hash_validity",
        definition="declared transcript_hash equals the recomputed canonical digest",
        source="the declared transcript payload",
        meaning="content integrity of the transcript artifact",
        range="True, False, or None when the digest could not be recomputed",
        failure_behaviour="None when the payload is not canonically encodable",
    ),
    "session_consistency": FeatureDescriptor(
        name="session_consistency",
        definition="protocol version is spoken and the transcript is addressed here",
        source="declared protocol_version and verifier_id, plus the verifier context",
        meaning="protocol/session addressing invariant",
        range="True, False, or None when the verifier context was not supplied",
        failure_behaviour="None when the verifier context is unavailable",
    ),
    "nonce_freshness_state": FeatureDescriptor(
        name="nonce_freshness_state",
        definition="whether the observed nonce was seen in an earlier event",
        source="the replay registry and the declared nonce",
        meaning="protocol/session identity reuse, never a quantum property",
        range="True (fresh), False (reused), or None when not observable",
        failure_behaviour="None when no nonce is observable or no registry is given",
    ),
    "signer_authorization_validity": FeatureDescriptor(
        name="signer_authorization_validity",
        definition="presented signer identity is a member of the authorised signers",
        source="declared signer_id and the authorization context",
        meaning="deterministic membership test; not proof of identity",
        range="True, False, or None when the identity or the set is unavailable",
        failure_behaviour="None when either side of the membership test is missing",
    ),
    "verifier_authorization_validity": FeatureDescriptor(
        name="verifier_authorization_validity",
        definition=(
            "presented verifier identity is a member of the authorised verifiers"
        ),
        source="declared verifier_id and the authorization context",
        meaning=(
            "deterministic membership test, kept distinct from signer "
            "authorization"
        ),
        range="True, False, or None when the identity or the set is unavailable",
        failure_behaviour="None when either side of the membership test is missing",
    ),
    "cross_verifier_disagreement": FeatureDescriptor(
        name="cross_verifier_disagreement",
        definition="disagreement between two verifiers' observations of one session",
        source="a second verifier's observations",
        meaning="unavailable in this data model",
        range="always None at Milestone 4",
        failure_behaviour=(
            "reported as unavailable: the M2/M3 data model records exactly one "
            "verifier identity per session, so no comparison exists to make"
        ),
    ),
}


@dataclass(frozen=True)
class BasisStatistics:
    """Per-basis measurement and deviation statistics.

    Reported because a disturbance that is concentrated in one basis is
    structurally different from one spread evenly, and because the milestone's
    explainability requirement asks which bases were affected.
    """

    observed_bases: Tuple[str, ...]
    counts: Mapping[str, int]
    distribution: Mapping[str, float]
    mismatch_counts: Mapping[str, int]
    mismatch_rates: Mapping[str, float | None]
    disturbance_counts: Mapping[str, int]
    disturbance_rates: Mapping[str, float | None]
    disturbed_bases: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observed_bases": list(self.observed_bases),
            "counts": dict(self.counts),
            "distribution": dict(self.distribution),
            "mismatch_counts": dict(self.mismatch_counts),
            "mismatch_rates": dict(self.mismatch_rates),
            "disturbance_counts": dict(self.disturbance_counts),
            "disturbance_rates": dict(self.disturbance_rates),
            "disturbed_bases": list(self.disturbed_bases),
        }


def analyse_basis_statistics(
    states: Sequence[StateEvidence],
    *,
    tolerance: float = DEFAULT_MEASUREMENT_TOLERANCE,
) -> BasisStatistics:
    """Return per-basis counts and deviation statistics."""
    records = tuple(states)
    counts: Dict[str, int] = {}
    mismatch_counts: Dict[str, int] = {}
    disturbance_counts: Dict[str, int] = {}

    for record in records:
        if not record.usable:
            continue
        basis = str(record.basis)
        counts[basis] = counts.get(basis, 0) + 1
        if record.matched is False:
            mismatch_counts[basis] = mismatch_counts.get(basis, 0) + 1
        if float(record.probability_expected) < 1.0 - float(tolerance):
            disturbance_counts[basis] = disturbance_counts.get(basis, 0) + 1

    total = sum(counts.values())
    observed_bases = tuple(sorted(counts))
    distribution = {
        basis: (counts[basis] / total if total else 0.0) for basis in observed_bases
    }
    mismatch_rates = {
        basis: (mismatch_counts.get(basis, 0) / counts[basis]) for basis in observed_bases
    }
    disturbance_rates = {
        basis: (disturbance_counts.get(basis, 0) / counts[basis])
        for basis in observed_bases
    }
    disturbed_bases = tuple(
        basis for basis in observed_bases if disturbance_counts.get(basis, 0) > 0
    )

    return BasisStatistics(
        observed_bases=observed_bases,
        counts=counts,
        distribution=distribution,
        mismatch_counts=mismatch_counts,
        mismatch_rates=mismatch_rates,
        disturbance_counts=disturbance_counts,
        disturbance_rates=disturbance_rates,
        disturbed_bases=disturbed_bases,
    )


@dataclass(frozen=True)
class DetectionFeatures:
    """Every observable feature the engine computes, in one frozen record."""

    mismatch: MismatchAnalysis
    disturbance: DisturbanceAnalysis
    fidelity: FidelityAnalysis
    basis: BasisStatistics

    measurement_counts_by_basis: Mapping[str, int]
    basis_distribution: Mapping[str, float]
    mismatch_rate: float | None
    projective_match_probability: float | None
    reconstruction_fidelity: float | None
    verification_state_disturbance_rate: float | None

    state_count_consistency: bool | None
    transcript_validity: bool | None
    transcript_hash_validity: bool | None
    session_consistency: bool | None
    nonce_freshness_state: bool | None
    signer_authorization_validity: bool | None
    verifier_authorization_validity: bool | None
    cross_verifier_disagreement: None

    redundancies: Mapping[str, str]
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mismatch": self.mismatch.to_dict(),
            "disturbance": self.disturbance.to_dict(),
            "fidelity": self.fidelity.to_dict(),
            "basis": self.basis.to_dict(),
            "measurement_counts_by_basis": dict(self.measurement_counts_by_basis),
            "basis_distribution": dict(self.basis_distribution),
            "mismatch_rate": self.mismatch_rate,
            "projective_match_probability": self.projective_match_probability,
            "reconstruction_fidelity": self.reconstruction_fidelity,
            "verification_state_disturbance_rate": (
                self.verification_state_disturbance_rate
            ),
            "state_count_consistency": self.state_count_consistency,
            "transcript_validity": self.transcript_validity,
            "transcript_hash_validity": self.transcript_hash_validity,
            "session_consistency": self.session_consistency,
            "nonce_freshness_state": self.nonce_freshness_state,
            "signer_authorization_validity": self.signer_authorization_validity,
            "verifier_authorization_validity": self.verifier_authorization_validity,
            "cross_verifier_disagreement": self.cross_verifier_disagreement,
            "redundancies": dict(self.redundancies),
            "notes": list(self.notes),
        }


def extract_features(
    detection_input: ObservableDetectionInput,
    *,
    consistency: ConsistencyReport,
    authorization: AuthorizationReport,
    replay: ReplayEvidence | None = None,
    parameters: DetectorParameters | None = None,
) -> DetectionFeatures:
    """Extract the documented feature set from observable evidence.

    The sub-analyses are passed in rather than recomputed, so the engine
    performs each computation exactly once and no two components can disagree
    about the same number.
    """
    params = (parameters or DetectorParameters()).validate()

    mismatch = analyse_mismatch(
        detection_input.states,
        declared_state_count=detection_input.declared_state_count,
        confidence=params.confidence,
    )
    disturbance = analyse_disturbance(
        detection_input.states,
        mismatch=mismatch,
        declared_state_count=detection_input.declared_state_count,
        tolerance=params.match_tolerance,
        confidence=params.confidence,
    )
    fidelity = analyse_fidelity(
        detection_input.states, measurement_mode=detection_input.measurement_mode
    )
    basis = analyse_basis_statistics(
        detection_input.states, tolerance=params.match_tolerance
    )

    notes: list[str] = []

    state_count_consistency: bool | None
    if detection_input.declared_state_count is None:
        state_count_consistency = None
    else:
        state_count_consistency = (
            detection_input.declared_state_count
            == detection_input.observed_state_count
        )

    transcript_validity: bool | None
    if not detection_input.transcript_supplied:
        transcript_validity = None
    else:
        transcript_validity = consistency.protocol_valid

    session_consistency: bool | None
    if consistency.protocol_version_valid is None:
        session_consistency = None
    elif consistency.session_addressing_valid is None:
        session_consistency = consistency.protocol_version_valid
    else:
        session_consistency = (
            consistency.protocol_version_valid
            and consistency.session_addressing_valid
        )

    if replay is None or not replay.available:
        nonce_freshness_state: bool | None = None
        notes.append(
            "nonce freshness is unavailable: no replay history covered this event"
        )
    else:
        nonce_freshness_state = not replay.nonce_reused

    redundancies: Dict[str, str] = {}
    if disturbance.identical_to_mismatch:
        redundancies["verification_state_disturbance_rate"] = (
            "identical to mismatch_rate for this session: the deterministic "
            "measurement mode makes 'outcome disagreed' and 'state disturbed' the "
            "same event, so they are one signal"
        )
    redundancies["reconstruction_fidelity"] = (
        "identical to projective_match_probability: for a pure expected state the "
        "analytic fidelity equals the projective match probability"
    )
    if detection_input.measurement_mode == "sampled":
        redundancies["sampled_match_frequency"] = (
            "a finite-shot estimator of the same quantity as the analytic mean "
            "fidelity, not an independent measurement"
        )

    notes.append(
        "no composite score is computed: each feature stands alone and no "
        "weighted sum is formed"
    )

    return DetectionFeatures(
        mismatch=mismatch,
        disturbance=disturbance,
        fidelity=fidelity,
        basis=basis,
        measurement_counts_by_basis=dict(basis.counts),
        basis_distribution=dict(basis.distribution),
        mismatch_rate=mismatch.mismatch_rate,
        projective_match_probability=fidelity.analytic_mean_fidelity,
        reconstruction_fidelity=fidelity.analytic_mean_fidelity,
        verification_state_disturbance_rate=disturbance.disturbance_rate,
        state_count_consistency=state_count_consistency,
        transcript_validity=transcript_validity,
        transcript_hash_validity=consistency.transcript_hash_valid,
        session_consistency=session_consistency,
        nonce_freshness_state=nonce_freshness_state,
        signer_authorization_validity=authorization.signer.authorized,
        verifier_authorization_validity=authorization.verifier.authorized,
        cross_verifier_disagreement=None,
        redundancies=redundancies,
        notes=tuple(notes),
    )
