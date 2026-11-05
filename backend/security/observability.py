"""Threat-observability matrix: what each attack looks like to the verifier.

The matrix is derived from **two sources**:

1. **Structural code evidence.** Each attack module documents what it modifies.
   The four protocol-layer attacks (forgery, impersonation, unauthorized
   verification, replay) do not modify ``received_states``, so they produce no
   quantum-channel disturbance. This is a structural property of the code, not
   an assumption.

2. **Measured M5 benchmark evidence.** The reference benchmark
   ``benchmarks/m5-reference.json`` records the decision outcome for each
   attack under the calibrated mismatch-rate test at N=500, depolarizing
   eta=0.02, sampled mode, one shot per state.

Both sources agree: the mismatch-rate detector sees the two channel attacks
(intercept_resend, channel_tampering) and sees nothing of the four protocol
attacks. The protocol-layer attacks are protected by classical controls
(binding, authorization, replay bookkeeping), not by the quantum statistic.

Do not read this matrix as "attacks with False in every quantum column are not
a threat". They are a threat to the *protocol layer*, and their protection
requires classical controls that are outside the scope of the quantum
measurement. The matrix exists precisely to prevent that conflation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

__all__ = [
    "ThreatObservability",
    "REFERENCE_OBSERVABILITY_MATRIX",
    "threat_observability",
    "render_matrix_table",
    "matrix_summary",
]


@dataclass(frozen=True)
class ThreatObservability:
    """One row of the threat-observability matrix.

    Every field is a factual statement about what the current prototype
    observes, measures, or controls for this threat. ``None`` means the
    information is not available or not applicable.
    """

    threat: str

    quantum_disturbance: bool

    protocol_anomaly: bool

    authentication_evidence: bool

    replay_evidence: bool

    detector_visible_quantum: bool

    requires_classical_control: bool

    empirically_evaluated: bool

    covered_by_prototype: bool

    m5_detection_rate: float | None

    m5_far: float | None

    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threat": self.threat,
            "quantum_disturbance": self.quantum_disturbance,
            "protocol_anomaly": self.protocol_anomaly,
            "authentication_evidence": self.authentication_evidence,
            "replay_evidence": self.replay_evidence,
            "detector_visible_quantum": self.detector_visible_quantum,
            "requires_classical_control": self.requires_classical_control,
            "empirically_evaluated": self.empirically_evaluated,
            "covered_by_prototype": self.covered_by_prototype,
            "m5_detection_rate": self.m5_detection_rate,
            "m5_far": self.m5_far,
            "notes": list(self.notes),
        }






REFERENCE_OBSERVABILITY_MATRIX: Tuple[ThreatObservability, ...] = (
    ThreatObservability(
        threat="forgery",
        quantum_disturbance=False,
        protocol_anomaly=True,
        authentication_evidence=False,
        replay_evidence=False,
        detector_visible_quantum=False,
        requires_classical_control=True,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=0.0,
        m5_far=1.0,
        notes=(
            "structural: the forgery module modifies the transcript binding, "
            "not the quantum states; the received_states are passed through "
            "unchanged",
            "measured: 0/12 trials rejected by the mismatch-rate detector; "
            "all 12 accepted (FAR=1.0)",
            "protection is protocol-level: the verifier re-derives the expected "
            "state sequence from the binding it computes and compares it to "
            "the declared sequence",
        ),
    ),
    ThreatObservability(
        threat="impersonation",
        quantum_disturbance=False,
        protocol_anomaly=False,
        authentication_evidence=True,
        replay_evidence=False,
        detector_visible_quantum=False,
        requires_classical_control=True,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=0.0,
        m5_far=1.0,
        notes=(
            "structural: the impersonation module replaces the signer_id in the "
            "transcript and recomputes the hash; received_states are passed "
            "through unchanged",
            "measured: 0/12 trials rejected; all 12 accepted (FAR=1.0)",
            "protection is authorization bookkeeping: the declared signer must "
            "be in the authorized_signers set",
        ),
    ),
    ThreatObservability(
        threat="unauthorized_verification",
        quantum_disturbance=False,
        protocol_anomaly=False,
        authentication_evidence=True,
        replay_evidence=False,
        detector_visible_quantum=False,
        requires_classical_control=True,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=0.0,
        m5_far=1.0,
        notes=(
            "structural: the unauthorized_verification module replaces the "
            "verifier_id in the transcript and verifier_context; received_states "
            "are passed through unchanged",
            "measured: 0/12 trials rejected; all 12 accepted (FAR=1.0)",
            "protection is authorization bookkeeping: the declared verifier must "
            "be in the authorized_verifiers set",
        ),
    ),
    ThreatObservability(
        threat="replay",
        quantum_disturbance=False,
        protocol_anomaly=False,
        authentication_evidence=False,
        replay_evidence=True,
        detector_visible_quantum=False,
        requires_classical_control=True,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=0.0,
        m5_far=1.0,
        notes=(
            "structural: the replay module presents the same transcript again "
            "without modification; received_states are passed through unchanged",
            "measured: 0/12 trials rejected; all 12 accepted (FAR=1.0)",
            "protection is temporal bookkeeping: the same nonce in two events "
            "is a replay indicator. The prototype implements an in-memory "
            "consumed-identity ledger, backend.detection.replay.ReplayRegistry, "
            "which records the session identifier, the nonce and the transcript "
            "identity it has already seen and reports reuse as replay evidence; "
            "the detection engine accepts one as an optional component",
            "that ledger is a prototype session-state mechanism: it is in-memory, "
            "single-process and not persisted, so it is not a persistent or "
            "distributed replay-prevention system",
        ),
    ),
    ThreatObservability(
        threat="intercept_resend",
        quantum_disturbance=True,
        protocol_anomaly=False,
        authentication_evidence=False,
        replay_evidence=False,
        detector_visible_quantum=True,
        requires_classical_control=False,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=1.0,
        m5_far=0.0,
        notes=(
            "structural: the intercept_resend module measures a subset of states "
            "and forwards a replacement state; this disturbs the quantum channel",
            "measured: 12/12 trials rejected by the mismatch-rate detector "
            "(detection_rate=1.0, FAR=0.0)",
            "the disturbance is partial: Eve guesses the basis correctly one third "
            "of the time and forwards the correct state, so the observable "
            "disturbance depends on the basis distribution",
        ),
    ),
    ThreatObservability(
        threat="channel_tampering",
        quantum_disturbance=True,
        protocol_anomaly=False,
        authentication_evidence=False,
        replay_evidence=False,
        detector_visible_quantum=True,
        requires_classical_control=False,
        empirically_evaluated=True,
        covered_by_prototype=True,
        m5_detection_rate=1.0,
        m5_far=0.0,
        notes=(
            "structural: the channel_tampering module applies a Pauli operator to "
            "a subset of states; this disturbs the quantum channel",
            "measured: 12/12 trials rejected by the mismatch-rate detector "
            "(detection_rate=1.0, FAR=0.0)",
            "the disturbance is basis-dependent: a Pauli that anti-commutes with "
            "the measurement basis produces maximal mismatch, one that commutes "
            "produces none",
        ),
    ),
)


def threat_observability(threat: str) -> ThreatObservability:
    """Return the observability row for ``threat``, or raise."""
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        if row.threat == threat:
            return row
    raise KeyError(
        f"no observability row for {threat!r}; known threats: "
        f"{[r.threat for r in REFERENCE_OBSERVABILITY_MATRIX]}"
    )


def render_matrix_table() -> str:
    """Return a Markdown table of the matrix."""
    header = (
        "| Threat | Quantum disturbance | Protocol anomaly | Auth evidence | "
        "Replay evidence | Detector-visible | Classical control | Evaluated | "
        "Covered |"
    )
    sep = "|" + "|".join([" --- " for _ in range(9)]) + "|"
    lines = [header, sep]
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        qd = "yes" if row.quantum_disturbance else "no"
        pa = "yes" if row.protocol_anomaly else "no"
        ae = "yes" if row.authentication_evidence else "no"
        re = "yes" if row.replay_evidence else "no"
        dv = "yes" if row.detector_visible_quantum else "no"
        cc = "yes" if row.requires_classical_control else "no"
        ev = "yes" if row.empirically_evaluated else "no"
        cv = "yes" if row.covered_by_prototype else "no"
        lines.append(
            f"| {row.threat} | {qd} | {pa} | {ae} | {re} | {dv} | {cc} | {ev} | {cv} |"
        )
    return "\n".join(lines)


def matrix_summary() -> Mapping[str, Any]:
    """Return a JSON-ready summary of the matrix."""
    rows = [row.to_dict() for row in REFERENCE_OBSERVABILITY_MATRIX]
    quantum_visible = [r.threat for r in REFERENCE_OBSERVABILITY_MATRIX if r.detector_visible_quantum]
    classical_only = [r.threat for r in REFERENCE_OBSERVABILITY_MATRIX if not r.detector_visible_quantum]
    return {
        "rows": rows,
        "quantum_visible": quantum_visible,
        "classical_only": classical_only,
        "empirically_evaluated_count": sum(1 for r in REFERENCE_OBSERVABILITY_MATRIX if r.empirically_evaluated),
        "covered_count": sum(1 for r in REFERENCE_OBSERVABILITY_MATRIX if r.covered_by_prototype),
        "source": "derived from structural code evidence and the committed M5 benchmark "
        "benchmarks/m5-reference.json",
    }
