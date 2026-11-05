"""The decision model: findings in, one explainable result out.

What the result is
------------------
:class:`DetectionResult` answers three questions and refuses to answer a fourth:

1. *Is the protocol/session structure valid?* -- :attr:`protocol_valid`.
2. *What was observed?* -- :attr:`findings` and :attr:`features`.
3. *Which family of problems, if any, applies?* -- :attr:`overall_status`.
4. *(refused) How dangerous is this, on a scale?* -- there is no security score.

Why the overall status is categorical
-------------------------------------
The status names which *family* of findings fired -- integrity, authorization or
quantum -- and never how close a number came to a limit. The milestone brief is
explicit that the overall result must not depend on arbitrary percentages, and a
categorical rule is the only way to satisfy that before calibration exists.

=============================  ==============================================
findings present               overall status
=============================  ==============================================
none                           ``CLEAR``
exactly one family             that family's status
two or more families           ``MULTIPLE_FINDINGS``
=============================  ==============================================

The family mapping is fixed and lives in :mod:`backend.detection.evidence`.

``protocol_valid`` and authorization
------------------------------------
``protocol_valid`` covers the protocol/session integrity axis: transcript
integrity, consistency, signature-verification and replay. Authorization is a
**policy** axis, not a protocol-structure property -- a session can be
structurally perfect and still be attempted by an unauthorised party -- so an
authorization finding is reported through the findings and the overall status
but does not make ``protocol_valid`` false. The distinction is stated here
because it is exactly the kind of thing that gets blurred later.

The multiple-testing limitation
-------------------------------
Milestone 4 runs **no hypothesis tests**. It reports diagnostic statistics and
the mathematical relationships between them. It deliberately does not implement
"five independent tests at alpha = 0.05", which the architecture review
identified as a defect. Selecting the primary verification statistic, choosing
joint/multiple-comparison handling, calibrating thresholds and evaluating
FAR/FRR all belong to Milestone 5.

:meth:`DetectionResult.diagnostic_statistics` is the interface for that work: it
exposes the statistics and their exact intervals, with no decision attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

from backend.detection.evidence import (
    EvidenceGroup,
    ThreatEvidence,
    category_group,
)
from backend.detection.features import DetectionFeatures
from backend.detection.models import (
    EvidenceCategory,
    OverallStatus,
)

__all__ = ["DetectionResult", "decide"]


_STATUS_BY_GROUP: Mapping[EvidenceGroup, OverallStatus] = {
    EvidenceGroup.INTEGRITY: OverallStatus.INTEGRITY_VIOLATION,
    EvidenceGroup.AUTHORIZATION: OverallStatus.AUTHORIZATION_VIOLATION,
    EvidenceGroup.QUANTUM: OverallStatus.QUANTUM_ANOMALY,
}


_PROTOCOL_INTEGRITY_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.TRANSCRIPT_INTEGRITY,
    EvidenceCategory.CONSISTENCY_ANOMALY,
    EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
    EvidenceCategory.REPLAY,
)


@dataclass(frozen=True)
class DetectionResult:
    """The engine's explainable output for one session."""

    protocol_valid: bool
    findings: Tuple[ThreatEvidence, ...]
    overall_status: OverallStatus
    explanation: str
    features: DetectionFeatures
    session_reference: str | None = None
    notes: Tuple[str, ...] = ()



    def findings_for(
        self, category: EvidenceCategory
    ) -> Tuple[ThreatEvidence, ...]:
        """Return the findings in ``category``."""
        return tuple(item for item in self.findings if item.category is category)

    def blocking_findings(self) -> Tuple[ThreatEvidence, ...]:
        """Return the findings that block acceptance."""
        return tuple(item for item in self.findings if item.blocking)

    def categories(self) -> Tuple[EvidenceCategory, ...]:
        """Return the distinct categories present, in first-seen order."""
        seen: list[EvidenceCategory] = []
        for item in self.findings:
            if item.category not in seen:
                seen.append(item.category)
        return tuple(seen)

    def diagnostic_statistics(self) -> Dict[str, Any]:
        """Return the statistics Milestone 5 will calibrate.

        Deliberately carries **no decision**: only the measured values and their
        exact intervals, so the calibration milestone can select a primary
        statistic and handle multiplicity without inheriting a choice from here.
        """
        mismatch = self.features.mismatch
        disturbance = self.features.disturbance
        return {
            "mismatch_rate": mismatch.mismatch_rate,
            "mismatch_interval": (
                None if mismatch.rate_estimate is None else mismatch.rate_estimate.to_dict()
            ),
            "disturbance_rate": disturbance.disturbance_rate,
            "disturbance_interval": (
                None
                if disturbance.rate_estimate is None
                else disturbance.rate_estimate.to_dict()
            ),
            "mean_fidelity": self.features.reconstruction_fidelity,
            "minimum_fidelity": self.features.fidelity.analytic_min_fidelity,
            "sample_size": mismatch.n_valid,
            "disturbance_sample_size": disturbance.n_verification_states,
            "measurement_mode": self.features.fidelity.measurement_mode,
            "redundancies": dict(self.features.redundancies),
            "multiple_testing_handling": "not implemented at Milestone 4",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_valid": self.protocol_valid,
            "overall_status": self.overall_status.value,
            "explanation": self.explanation,
            "session_reference": self.session_reference,
            "finding_count": len(self.findings),
            "findings": [item.to_dict() for item in self.findings],
            "features": self.features.to_dict(),
            "diagnostic_statistics": self.diagnostic_statistics(),
            "notes": list(self.notes),
        }


def decide(
    findings: Iterable[ThreatEvidence],
    *,
    features: DetectionFeatures,
    session_reference: str | None = None,
    notes: Tuple[str, ...] = (),
) -> DetectionResult:
    """Turn findings into a :class:`DetectionResult`."""
    ordered = tuple(findings)

    groups: list[EvidenceGroup] = []
    for item in ordered:
        group = category_group(item.category)
        if group not in groups:
            groups.append(group)

    if not groups:
        overall = OverallStatus.CLEAR
    elif len(groups) > 1:
        overall = OverallStatus.MULTIPLE_FINDINGS
    else:
        overall = _STATUS_BY_GROUP[groups[0]]

    protocol_valid = not any(
        item.blocking and item.category in _PROTOCOL_INTEGRITY_CATEGORIES
        for item in ordered
    )

    return DetectionResult(
        protocol_valid=protocol_valid,
        findings=ordered,
        overall_status=overall,
        explanation=_explain(overall, ordered, features),
        features=features,
        session_reference=session_reference,
        notes=tuple(notes),
    )


def _explain(
    overall: OverallStatus,
    findings: Tuple[ThreatEvidence, ...],
    features: DetectionFeatures,
) -> str:
    """Return a one-paragraph, non-attributing explanation."""
    if overall is OverallStatus.CLEAR:
        return (
            "No protocol, authorization or measurement evidence deviated from the "
            "supplied reference expectations. This states what was observed; it "
            "does not assert that the session was free of any cause, because "
            "noise and undetectable manipulation produce identical observations."
        )

    lines = [
        f"{overall.value}: {len(findings)} finding(s) across "
        f"{len({category_group(item.category) for item in findings})} family(ies)."
    ]
    for item in findings:
        lines.append(f"[{item.finding_id}] {item.explanation}")

    if any(
        item.category
        in (
            EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY,
            EvidenceCategory.CHANNEL_ANOMALY,
        )
        for item in findings
    ):
        lines.append(
            "Observed verification measurements deviate from the currently "
            "supplied reference expectations; no cause is attributed."
        )
    return " ".join(lines)
