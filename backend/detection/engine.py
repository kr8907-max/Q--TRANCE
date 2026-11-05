"""The detection engine: observable evidence in, explainable result out.

Pipeline
--------
::

    ObservableDetectionInput
        |
        v
    1. consistency      protocol/session integrity, recomputed from the artifact
    2. authorization    signer and verifier membership tests, kept separate
    3. replay           session/nonce/transcript reuse against a registry
    4. features         the documented observable feature set
        |
        v
    5. findings         ThreatEvidence, one per established deviation
    6. decision         DetectionResult
        |
        v
    DetectionResult

Each stage is a separate module, and the engine performs each computation
exactly once, so no two components can disagree about the same number.

What the engine is not allowed to know
--------------------------------------
There is no branch anywhere in this package that reads an attack type, an attack
fraction, a noise strength or a ground-truth flag. The engine is handed
observable evidence and asked one question: *what evidence is observable?*

Consequences that the code makes explicit rather than implicit:

* the same observable data produces the same result whatever caused it --
  honest noise, an intercept-resend attack, tampering or an unexplained
  disturbance are indistinguishable at this layer, and the engine does not try
  to tell them apart;
* no finding names an attack. A finding says what deviated and by how much;
* importing this package does not import :mod:`backend.attacks`.

Finding construction order
--------------------------
Findings are emitted in a fixed order -- transcript integrity, consistency,
signature verification, verifier disagreement, replay, signer authorization,
verifier authorization, channel anomaly, quantum measurement anomaly -- and
identifiers are assigned deterministically from the category and the position
within it. Two runs over the same input therefore produce identical results,
which is what the attack-label independence test asserts.

Why the two anomaly findings do not double-count
------------------------------------------------
In the deterministic ``"projective-analytic"`` measurement mode, "the
verification outcome disagreed" and "the received state is not the expected
state" are the same event. Reporting both would present one signal as two, which
the milestone brief forbids. The engine therefore emits

* :attr:`~backend.detection.models.EvidenceCategory.CHANNEL_ANOMALY` whenever the
  *state-level* evidence deviates (disturbance, fidelity, affected bases);
* :attr:`~backend.detection.models.EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY`
  only when the *outcome-level* evidence deviates **and** is not already fully
  described by the state-level evidence -- which happens in the ``"sampled"``
  measurement mode, where the finite-shot outcome frequency is a genuinely
  different statistic.

The redundancy, when it applies, is recorded in ``features.redundancies`` rather
than silently dropped.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.detection.authorization import AuthorizationReport, analyse_authorization
from backend.detection.consistency import ConsistencyReport, analyse_consistency
from backend.detection.decision import DetectionResult, decide
from backend.detection.evidence import (
    BLOCKING_CATEGORIES,
    DETERMINISTIC_SEVERITY,
    EvidenceItem,
    ThreatEvidence,
    assign_finding_ids,
    statistical_severity,
)
from backend.detection.features import DetectionFeatures, extract_features
from backend.detection.models import (
    CalibrationState,
    DetectorParameters,
    EvidenceCategory,
    ObservableDetectionInput,
    VerificationEvidence,
)
from backend.detection.replay import ReplayEvidence, ReplayRegistry

__all__ = ["ThreatDetectionEngine", "detect"]


class ThreatDetectionEngine:
    """The observable threat detection engine.

    ``parameters`` configures the detector. ``replay_registry`` is the optional
    session ledger; without one, replay evidence is reported as unavailable
    rather than assumed absent.
    """

    def __init__(
        self,
        parameters: DetectorParameters | None = None,
        *,
        replay_registry: ReplayRegistry | None = None,
    ) -> None:
        self._parameters = (parameters or DetectorParameters()).validate()
        self._registry = replay_registry

    @property
    def parameters(self) -> DetectorParameters:
        return self._parameters

    @property
    def replay_registry(self) -> ReplayRegistry | None:
        return self._registry

    def detect(
        self,
        detection_input: ObservableDetectionInput,
        *,
        consume: bool = False,
    ) -> DetectionResult:
        """Analyse one session and return an explainable result.

        ``consume`` controls whether the replay ledger is updated. The default
        is ``False`` so a detection pass is **side-effect free**: the same input
        always yields the same result, and a caller that wants to record the
        event asks for it explicitly.
        """
        if detection_input is None:
            raise ValueError("detection input must not be None")

        consistency = analyse_consistency(
            detection_input,
            expected_protocol_versions=self._parameters.expected_protocol_versions,
        )
        authorization = analyse_authorization(detection_input)
        replay = self._replay_evidence(detection_input, consume=consume)

        features = extract_features(
            detection_input,
            consistency=consistency,
            authorization=authorization,
            replay=replay,
            parameters=self._parameters,
        )

        findings = _build_findings(
            detection_input=detection_input,
            consistency=consistency,
            authorization=authorization,
            replay=replay,
            features=features,
            parameters=self._parameters,
        )

        return decide(
            assign_finding_ids(findings),
            features=features,
            session_reference=detection_input.session_id,
            notes=(
                "detector consumed observable evidence only: no attack type, "
                "attack fraction, noise strength or ground-truth label was read",
                "no security score is produced and no threshold is calibrated",
            ),
        )



    def _replay_evidence(
        self,
        detection_input: ObservableDetectionInput,
        *,
        consume: bool,
    ) -> ReplayEvidence:
        if self._registry is None:
            return ReplayEvidence(
                available=False,
                nonce_reused=False,
                session_reused=False,
                transcript_reused=False,
                first_observation=None,
                observed_session_id=detection_input.session_id,
                observed_nonce=detection_input.nonce,
                observed_transcript_hash=detection_input.declared_transcript_hash,
                reason="no replay registry was supplied, so no history was available",
            )
        if consume:
            return self._registry.observe(
                session_id=detection_input.session_id,
                nonce=detection_input.nonce,
                transcript_hash=detection_input.declared_transcript_hash,
            )
        return self._registry.check(
            session_id=detection_input.session_id,
            nonce=detection_input.nonce,
            transcript_hash=detection_input.declared_transcript_hash,
        )


def detect(
    detection_input: ObservableDetectionInput,
    *,
    parameters: DetectorParameters | None = None,
    replay_registry: ReplayRegistry | None = None,
    consume: bool = False,
) -> DetectionResult:
    """Convenience wrapper around :meth:`ThreatDetectionEngine.detect`."""
    return ThreatDetectionEngine(
        parameters, replay_registry=replay_registry
    ).detect(detection_input, consume=consume)







def _build_findings(
    *,
    detection_input: ObservableDetectionInput,
    consistency: ConsistencyReport,
    authorization: AuthorizationReport,
    replay: ReplayEvidence,
    features: DetectionFeatures,
    parameters: DetectorParameters,
) -> Tuple[ThreatEvidence, ...]:
    """Return every established finding, in a fixed order.

    The verifier-disagreement check runs last because it needs to know which
    deviations were *already* established: it exists to surface a rejection the
    detector cannot explain, not to restate one it can.
    """
    integrity = list(_transcript_integrity_findings(detection_input, consistency))
    consistency_findings = list(_consistency_findings(detection_input, consistency))
    signature = list(_signature_verification_findings(detection_input, consistency))
    replay_findings = list(_replay_findings(detection_input, replay))
    authorization_findings = list(
        _authorization_findings(detection_input, authorization)
    )
    channel = list(_channel_anomaly_findings(detection_input, features, parameters))
    quantum = list(_quantum_anomaly_findings(detection_input, features, parameters))

    disagreement = list(
        _verification_disagreement_findings(
            detection_input,
            integrity
            + consistency_findings
            + signature
            + replay_findings
            + authorization_findings
            + channel
            + quantum,
        )
    )

    return tuple(
        integrity
        + consistency_findings
        + disagreement
        + signature
        + replay_findings
        + authorization_findings
        + channel
        + quantum
    )


def _deterministic(
    *,
    category: EvidenceCategory,
    explanation: str,
    evidence_items: Tuple[EvidenceItem, ...],
    observed_values: Dict[str, Any],
    source_metrics: Tuple[str, ...],
    session_reference: str | None,
    timestamp: str | None = None,
    comparison_values: Dict[str, Any] | None = None,
    strength: float | None = None,
    notes: Tuple[str, ...] = (),
) -> ThreatEvidence:
    """Build a finding for a deterministic category."""
    return ThreatEvidence(
        category=category,
        severity=DETERMINISTIC_SEVERITY[category],
        calibration=CalibrationState.CALIBRATED,
        blocking=category in BLOCKING_CATEGORIES,
        explanation=explanation,
        strength=strength,
        evidence_items=evidence_items,
        observed_values=observed_values,
        comparison_values=dict(comparison_values or {}),
        source_metrics=source_metrics,
        session_reference=session_reference,
        timestamp=timestamp,
        notes=notes,
    )


def _reference(detection_input: ObservableDetectionInput) -> Tuple[str | None, str | None]:
    """Return ``(session_reference, timestamp)`` for a finding."""
    return detection_input.session_id, detection_input.created_at


def _transcript_integrity_findings(
    detection_input: ObservableDetectionInput,
    consistency: ConsistencyReport,
) -> Tuple[ThreatEvidence, ...]:
    session, timestamp = _reference(detection_input)
    findings: List[ThreatEvidence] = []

    if consistency.transcript_supplied and not consistency.transcript_parse_ok:
        findings.append(
            _deterministic(
                category=EvidenceCategory.TRANSCRIPT_INTEGRITY,
                explanation=(
                    "The transcript could not be parsed, so no protocol-integrity "
                    "property of the artifact can be established."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="parse_error",
                        observed=consistency.parse_error,
                        source="the declared transcript payload",
                        explanation="the parser's own description of the failure",
                    ),
                ),
                observed_values={"parse_error": consistency.parse_error},
                source_metrics=("transcript_validity",),
                session_reference=session,
                timestamp=timestamp,
            )
        )
        return tuple(findings)

    if consistency.transcript_hash_valid is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.TRANSCRIPT_INTEGRITY,
                explanation=(
                    "The declared transcript_hash does not match the canonical "
                    "digest recomputed from the transcript content: the artifact is "
                    "not internally consistent."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="declared_transcript_hash",
                        observed=consistency.declared_transcript_hash,
                        source="the transcript",
                    ),
                    EvidenceItem(
                        name="recomputed_transcript_hash",
                        observed=consistency.recomputed_transcript_hash,
                        expected=consistency.declared_transcript_hash,
                        source="canonical digest recomputed by the detector",
                    ),
                ),
                observed_values={
                    "declared_transcript_hash": consistency.declared_transcript_hash,
                    "recomputed_transcript_hash": (
                        consistency.recomputed_transcript_hash
                    ),
                },
                comparison_values={
                    "declared_transcript_hash": consistency.declared_transcript_hash
                },
                source_metrics=("transcript_hash_validity",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.transcript_hash_valid is None and consistency.transcript_parse_ok:
        findings.append(
            _deterministic(
                category=EvidenceCategory.TRANSCRIPT_INTEGRITY,
                explanation=(
                    "The transcript content is not canonically encodable, so its "
                    "integrity cannot be established at all."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="canonical_encoding",
                        observed="failed",
                        expected="canonical",
                        source="canonical digest recomputation",
                    ),
                ),
                observed_values={"canonically_encodable": False},
                source_metrics=("transcript_hash_validity",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.message_binding_valid is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.TRANSCRIPT_INTEGRITY,
                explanation=(
                    "The declared message_binding does not match the binding "
                    "recomputed from protocol_version, session_id, nonce and the "
                    "supplied message: the artifact is not bound to this message."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="declared_message_binding",
                        observed=consistency.declared_message_binding,
                        source="the transcript",
                    ),
                    EvidenceItem(
                        name="recomputed_message_binding",
                        observed=consistency.recomputed_message_binding,
                        expected=consistency.declared_message_binding,
                        source="binding recomputed by the detector",
                    ),
                ),
                observed_values={
                    "declared_message_binding": consistency.declared_message_binding,
                    "recomputed_message_binding": (
                        consistency.recomputed_message_binding
                    ),
                },
                comparison_values={
                    "declared_message_binding": consistency.declared_message_binding
                },
                source_metrics=("transcript_validity",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    return tuple(findings)


def _consistency_findings(
    detection_input: ObservableDetectionInput,
    consistency: ConsistencyReport,
) -> Tuple[ThreatEvidence, ...]:
    session, timestamp = _reference(detection_input)
    findings: List[ThreatEvidence] = []

    if consistency.protocol_version_valid is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.CONSISTENCY_ANOMALY,
                explanation=(
                    "The transcript declares a protocol version this detector does "
                    "not speak."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="protocol_version",
                        observed=consistency.observed_protocol_version,
                        expected=list(consistency.expected_protocol_versions),
                        source="the transcript and the detector configuration",
                    ),
                ),
                observed_values={
                    "protocol_version": consistency.observed_protocol_version
                },
                comparison_values={
                    "expected_protocol_versions": list(
                        consistency.expected_protocol_versions
                    )
                },
                source_metrics=("session_consistency",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.session_addressing_valid is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.CONSISTENCY_ANOMALY,
                explanation=(
                    "The transcript is addressed to a different verifier identity "
                    "than the one performing this verification."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="transcript_verifier_id",
                        observed=consistency.transcript_verifier_id,
                        source="the transcript",
                    ),
                    EvidenceItem(
                        name="verifier_context_id",
                        observed=consistency.verifier_context_id,
                        expected=consistency.transcript_verifier_id,
                        source="the verifier's own identity",
                    ),
                ),
                observed_values={
                    "transcript_verifier_id": consistency.transcript_verifier_id,
                    "verifier_context_id": consistency.verifier_context_id,
                },
                source_metrics=("session_consistency",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.state_count_declared_matches_list is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.CONSISTENCY_ANOMALY,
                explanation=(
                    "The declared state_count does not match the number of states "
                    "the transcript actually declares."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="declared_state_count",
                        observed=consistency.state_count_declared,
                        source="the transcript",
                    ),
                ),
                observed_values={
                    "declared_state_count": consistency.state_count_declared,
                    "declared_state_count_matches_list": False,
                },
                source_metrics=("state_count_consistency",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.state_count_declared_matches_observed is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.CONSISTENCY_ANOMALY,
                explanation=(
                    "The declared state_count does not match the number of "
                    "measurement observations supplied for this session."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="declared_state_count",
                        observed=consistency.state_count_declared,
                        expected=detection_input.observed_state_count,
                        source="the transcript",
                    ),
                    EvidenceItem(
                        name="observed_state_count",
                        observed=detection_input.observed_state_count,
                        source="the observation list",
                    ),
                ),
                observed_values={
                    "declared_state_count": consistency.state_count_declared,
                    "observed_state_count": detection_input.observed_state_count,
                },
                comparison_values={
                    "declared_state_count": consistency.state_count_declared
                },
                source_metrics=("state_count_consistency",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    if consistency.state_sequence_metadata_consistent is False:
        findings.append(
            _deterministic(
                category=EvidenceCategory.CONSISTENCY_ANOMALY,
                explanation=(
                    "The declared state_sequence_metadata does not match the "
                    "metadata the detector derived from the binding it recomputed."
                ),
                evidence_items=(
                    EvidenceItem(
                        name="state_sequence_metadata",
                        observed="differs from the derived metadata",
                        source="the transcript and the detector's own derivation",
                    ),
                ),
                observed_values={"state_sequence_metadata_consistent": False},
                source_metrics=("state_count_consistency",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    return tuple(findings)


def _signature_verification_findings(
    detection_input: ObservableDetectionInput,
    consistency: ConsistencyReport,
) -> Tuple[ThreatEvidence, ...]:
    if consistency.declared_state_sequence_matches_derivation is not False:
        return ()
    session, timestamp = _reference(detection_input)
    return (
        _deterministic(
            category=EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
            explanation=(
                "The states the transcript declares do not match the state sequence "
                "the detector derived independently from the message binding: the "
                "declared signature does not correspond to this message."
            ),
            evidence_items=(
                EvidenceItem(
                    name="declared_state_sequence",
                    observed="differs from the derived sequence",
                    source="the transcript",
                ),
                EvidenceItem(
                    name="derived_state_sequence",
                    observed="derived from the recomputed message binding",
                    source="the detector's independent derivation",
                ),
            ),
            observed_values={"declared_state_sequence_matches_derivation": False},
            comparison_values={"derived_from": "recomputed message binding"},
            source_metrics=("transcript_validity", "state_count_consistency"),
            session_reference=session,
            timestamp=timestamp,
            notes=(
                "this is verification inconsistency, not a quantum measurement "
                "result, and it does not by itself identify who produced the "
                "artifact",
            ),
        ),
    )




_FLAG_EXPLAINED_BY: Dict[str, Tuple[EvidenceCategory, ...]] = {
    "transcript_valid": (EvidenceCategory.TRANSCRIPT_INTEGRITY,),
    "message_valid": (
        EvidenceCategory.TRANSCRIPT_INTEGRITY,
        EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
    ),
    "session_valid": (EvidenceCategory.CONSISTENCY_ANOMALY,),
    "state_sequence_valid": (
        EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
        EvidenceCategory.CONSISTENCY_ANOMALY,
    ),
    "measurement_valid": (
        EvidenceCategory.CHANNEL_ANOMALY,
        EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY,
    ),
}


def _verification_disagreement_findings(
    detection_input: ObservableDetectionInput,
    established: List[ThreatEvidence],
) -> Tuple[ThreatEvidence, ...]:
    """Report when the verifier rejected a session the detector cannot explain.

    This is not a claim about an attacker, and it is not a restatement of a
    deviation the detector already established. It fires only when the verifier
    recorded a rejection and at least one failed verification flag has **no**
    corresponding finding -- i.e. two independent recomputations of the same
    protocol invariants disagreed about a fact neither of them explained.

    A rejection whose only failed flag is ``measurement_valid`` is *explained* by
    a channel or measurement anomaly, so no disagreement is reported. That keeps
    honest noise from being dressed up as a protocol problem.
    """
    verification: VerificationEvidence = detection_input.verification
    if not verification.available or verification.accepted is not False:
        return ()

    present = {finding.category for finding in established}
    failed = [
        flag for flag in _FLAG_EXPLAINED_BY if getattr(verification, flag, None) is False
    ]
    unexplained = [
        flag
        for flag in failed
        if not (present & set(_FLAG_EXPLAINED_BY[flag]))
    ]
    if failed and not unexplained:
        return ()

    session, timestamp = _reference(detection_input)
    return (
        _deterministic(
            category=EvidenceCategory.CONSISTENCY_ANOMALY,
            explanation=(
                "The verifier recorded a rejection that the detector's own "
                "recomputation does not account for. The two disagree about this "
                "session."
            ),
            evidence_items=(
                EvidenceItem(
                    name="verification_accepted",
                    observed=verification.accepted,
                    expected=True,
                    source="the verifier's structured result",
                ),
                EvidenceItem(
                    name="unexplained_failed_flags",
                    observed=unexplained,
                    expected=[],
                    source="the verifier's structured result",
                ),
                EvidenceItem(
                    name="verification_errors",
                    observed=list(verification.errors),
                    source="the verifier's structured result",
                ),
            ),
            observed_values={
                "verification_accepted": verification.accepted,
                "failed_verification_flags": failed,
                "unexplained_failed_flags": unexplained,
                "verification_errors": list(verification.errors),
                "detector_finding_categories": sorted(
                    category.value for category in present
                ),
            },
            source_metrics=("transcript_validity", "session_consistency"),
            session_reference=session,
            timestamp=timestamp,
        ),
    )


def _replay_findings(
    detection_input: ObservableDetectionInput,
    replay: ReplayEvidence,
) -> Tuple[ThreatEvidence, ...]:
    if not replay.available or not replay.any_reuse:
        return ()
    session, timestamp = _reference(detection_input)

    reused = [
        name
        for name, flag in (
            ("session_id", replay.session_reused),
            ("nonce", replay.nonce_reused),
            ("transcript_hash", replay.transcript_reused),
        )
        if flag
    ]
    return (
        _deterministic(
            category=EvidenceCategory.REPLAY,
            explanation=(
                "A session identity that had already been consumed was presented "
                "again. Replay is a protocol/session property: the re-presented "
                "material may itself be entirely valid, which is why the evidence "
                "comes from the identity history and not from any measurement."
            ),
            evidence_items=(
                EvidenceItem(
                    name="reused_identifiers",
                    observed=reused,
                    source="the replay registry and the declared transcript identity",
                ),
                EvidenceItem(
                    name="session_id",
                    observed=replay.observed_session_id,
                    source="the transcript",
                ),
                EvidenceItem(
                    name="nonce",
                    observed=replay.observed_nonce,
                    source="the transcript",
                ),
                EvidenceItem(
                    name="transcript_hash",
                    observed=replay.observed_transcript_hash,
                    source="the transcript",
                ),
            ),
            observed_values={
                "session_reused": replay.session_reused,
                "nonce_reused": replay.nonce_reused,
                "transcript_reused": replay.transcript_reused,
                "reused_identifiers": reused,
            },
            comparison_values={"first_observation": replay.first_observation},
            source_metrics=("nonce_freshness_state",),
            session_reference=session,
            timestamp=timestamp,
            notes=(
                "no quantum disturbance is used to support this finding: a replay "
                "can be perfectly undisturbed",
            ),
        ),
    )


def _authorization_findings(
    detection_input: ObservableDetectionInput,
    authorization: AuthorizationReport,
) -> Tuple[ThreatEvidence, ...]:
    session, timestamp = _reference(detection_input)
    findings: List[ThreatEvidence] = []

    for check, category, role in (
        (authorization.signer, EvidenceCategory.SIGNER_AUTHORIZATION, "signer"),
        (
            authorization.verifier,
            EvidenceCategory.VERIFIER_AUTHORIZATION,
            "verifier",
        ),
    ):
        if not check.violated:
            continue
        findings.append(
            _deterministic(
                category=category,
                explanation=(
                    f"An unauthorized {role} identity was presented: "
                    f"{check.reason}. This is a membership test on declared "
                    f"identities and is not proof of identity."
                ),
                evidence_items=(
                    EvidenceItem(
                        name=f"presented_{role}",
                        observed=check.presented_identity,
                        source="the transcript",
                    ),
                    EvidenceItem(
                        name=f"authorized_{role}s",
                        observed=list(check.authorized_identities),
                        expected=check.presented_identity,
                        source="the authorization context",
                    ),
                    EvidenceItem(
                        name="reason",
                        observed=check.reason,
                        source="the detector's membership test",
                    ),
                ),
                observed_values={
                    f"presented_{role}": check.presented_identity,
                    f"authorized_{role}s": list(check.authorized_identities),
                    "authorized": check.authorized,
                },
                comparison_values={
                    f"authorized_{role}s": list(check.authorized_identities)
                },
                source_metrics=(f"{role}_authorization_validity",),
                session_reference=session,
                timestamp=timestamp,
            )
        )

    return tuple(findings)


def _channel_anomaly_findings(
    detection_input: ObservableDetectionInput,
    features: DetectionFeatures,
    parameters: DetectorParameters,
) -> Tuple[ThreatEvidence, ...]:
    """State-level deviation: the received states are not the expected states."""
    disturbance = features.disturbance
    if not disturbance.defined or disturbance.n_disturbed == 0:
        return ()

    reference = parameters.reference_disturbance_rate
    if (
        reference is not None
        and disturbance.disturbance_rate is not None
        and disturbance.disturbance_rate <= reference
    ):
        return ()

    estimate = disturbance.rate_estimate
    severity, calibration = statistical_severity(
        disturbance.disturbance_rate,
        None if estimate is None else estimate.lower,
        reference,
    )
    session, timestamp = _reference(detection_input)

    affected = features.basis.disturbed_bases
    explanation = (
        "The states arriving at the verifier deviate from the reference "
        "expectations supplied for them. The evidence is consistent with a "
        "channel that changed the qubits, with honest noise, or with tampering; "
        "this detector does not distinguish those causes."
    )
    if affected:
        explanation += f" Affected measurement bases: {', '.join(affected)}."

    return (
        ThreatEvidence(
            category=EvidenceCategory.CHANNEL_ANOMALY,
            severity=severity,
            calibration=calibration,
            blocking=False,
            explanation=explanation,
            strength=disturbance.disturbance_rate,
            evidence_items=(
                EvidenceItem(
                    name="verification_state_disturbance_rate",
                    observed=disturbance.disturbance_rate,
                    expected=0.0,
                    source="per-state analytic projective match probability",
                    explanation=(
                        "fraction of verification states whose projective match "
                        "probability fell below 1 - tolerance"
                    ),
                ),
                EvidenceItem(
                    name="disturbed_state_count",
                    observed=disturbance.n_disturbed,
                    expected=0,
                    source="per-state analytic projective match probability",
                ),
                EvidenceItem(
                    name="verification_state_count",
                    observed=disturbance.n_verification_states,
                    source="usable observations",
                ),
                EvidenceItem(
                    name="mean_fidelity",
                    observed=features.fidelity.analytic_mean_fidelity,
                    expected=1.0,
                    source="mean analytic fidelity",
                ),
                EvidenceItem(
                    name="affected_bases",
                    observed=list(affected),
                    expected=[],
                    source="per-basis disturbance statistics",
                ),
                EvidenceItem(
                    name="per_basis_disturbance_rates",
                    observed=dict(features.basis.disturbance_rates),
                    source="per-basis disturbance statistics",
                ),
            ),
            observed_values={
                "verification_state_disturbance_rate": disturbance.disturbance_rate,
                "disturbed_state_count": disturbance.n_disturbed,
                "verification_state_count": disturbance.n_verification_states,
                "mean_fidelity": features.fidelity.analytic_mean_fidelity,
                "minimum_fidelity": features.fidelity.analytic_min_fidelity,
                "affected_bases": list(affected),
                "per_basis_disturbance_rates": dict(
                    features.basis.disturbance_rates
                ),
            },
            comparison_values=(
                {} if reference is None else {"reference_disturbance_rate": reference}
            ),
            source_metrics=(
                "verification_state_disturbance_rate",
                "reconstruction_fidelity",
            ),
            session_reference=session,
            timestamp=timestamp,
            notes=(
                "the disturbance rate is computed from the verifier's own analytic "
                "projective probability; it does not require the ideal channel "
                "output and is therefore genuinely observable",
                "severity is UNCALIBRATED until a reference expectation is supplied",
            ),
        ),
    )


def _quantum_anomaly_findings(
    detection_input: ObservableDetectionInput,
    features: DetectionFeatures,
    parameters: DetectorParameters,
) -> Tuple[ThreatEvidence, ...]:
    """Outcome-level deviation, reported only when it adds information.

    In deterministic measurement mode this is the same event as the channel
    anomaly, so it is not emitted separately. In sampled mode it is a distinct
    statistic and is reported.
    """
    mismatch = features.mismatch
    if not mismatch.defined or mismatch.n_mismatch == 0:
        return ()
    if features.disturbance.identical_to_mismatch:
        return ()

    reference = parameters.reference_mismatch_rate
    if (
        reference is not None
        and mismatch.mismatch_rate is not None
        and mismatch.mismatch_rate <= reference
    ):
        return ()

    estimate = mismatch.rate_estimate
    severity, calibration = statistical_severity(
        mismatch.mismatch_rate,
        None if estimate is None else estimate.lower,
        reference,
    )
    session, timestamp = _reference(detection_input)

    return (
        ThreatEvidence(
            category=EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY,
            severity=severity,
            calibration=calibration,
            blocking=False,
            explanation=(
                "Observed verification outcomes disagree with the expected "
                "eigenvalues more often than the reference expectation accounts "
                "for. The evidence is a measurement statistic; no cause is "
                "attributed."
            ),
            strength=mismatch.mismatch_rate,
            evidence_items=(
                EvidenceItem(
                    name="mismatch_rate",
                    observed=mismatch.mismatch_rate,
                    expected=0.0,
                    source="per-state `matched` flags",
                ),
                EvidenceItem(
                    name="mismatch_count",
                    observed=mismatch.n_mismatch,
                    expected=0,
                    source="per-state `matched` flags",
                ),
                EvidenceItem(
                    name="valid_observations",
                    observed=mismatch.n_valid,
                    source="usable observations",
                ),
                EvidenceItem(
                    name="mismatch_interval",
                    observed=(
                        None if estimate is None else [estimate.lower, estimate.upper]
                    ),
                    source="exact Clopper-Pearson interval",
                ),
                EvidenceItem(
                    name="declared_verifier_mismatch_count",
                    observed=detection_input.verification.declared_mismatch_count,
                    expected=mismatch.n_mismatch,
                    source="the verifier's structured result",
                    explanation=(
                        "cross-check between the verifier's own count and the "
                        "detector's recomputation"
                    ),
                ),
                EvidenceItem(
                    name="per_basis_mismatch_rates",
                    observed=dict(features.basis.mismatch_rates),
                    source="per-basis mismatch statistics",
                ),
            ),
            observed_values={
                "mismatch_rate": mismatch.mismatch_rate,
                "mismatch_count": mismatch.n_mismatch,
                "valid_observations": mismatch.n_valid,
                "measurement_mode": features.fidelity.measurement_mode,
                "per_basis_mismatch_rates": dict(features.basis.mismatch_rates),
            },
            comparison_values=(
                {} if reference is None else {"reference_mismatch_rate": reference}
            ),
            source_metrics=("mismatch_rate",),
            session_reference=session,
            timestamp=timestamp,
            notes=(
                "reported separately from the channel anomaly only because the "
                "measurement mode makes them distinct statistics",
                "severity is UNCALIBRATED until a reference expectation is supplied",
            ),
        ),
    )
