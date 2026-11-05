"""The structured evidence model.

:class:`ThreatEvidence` is what the engine emits. It is designed so a reader can
answer, without re-running anything:

* **what** was observed (``observed_values``, ``evidence_items``),
* **against what** it was compared (``comparison_values``), when a comparison
  was available at all,
* **how strong** the evidence is (``strength``, ``severity``,
  ``calibration``),
* **whether it blocks** (``blocking``),
* **where it came from** (``source_metrics``, ``session_reference``,
  ``timestamp``),
* **what it means**, in one sentence (``explanation``).

Two rules the model enforces
----------------------------
**No precise attack attribution.** A finding never says "intercept-resend
detected" or "forgery detected". It says what deviated and by how much. The
simulator knows the truth; the detector does not, and the wording must not
pretend otherwise.

**No invented severity.** A finding that rests on a statistic whose decision
rule has not been calibrated is emitted with ``severity = UNCALIBRATED`` and
``calibration = UNCALIBRATED``. That is a real value, not a failure to compute
one: it states precisely that the evidence is reported and not yet adjudicated.

Severity taxonomy
-----------------
Deterministic categories -- the invariant either held or it did not -- carry a
fixed, documented severity:

==============================  ================  ==============================
category                        severity          why
==============================  ================  ==============================
TRANSCRIPT_INTEGRITY            HIGH              the artifact cannot be trusted
CONSISTENCY_ANOMALY             MODERATE          a protocol invariant failed
SIGNATURE_VERIFICATION_ANOMALY  HIGH              the declared signature does not
                                                  match independent derivation
REPLAY                          HIGH              a consumed identity was reused
SIGNER_AUTHORIZATION            CRITICAL          an unauthorised identity acted
                                                  as signer
VERIFIER_AUTHORIZATION          CRITICAL          an unauthorised identity acted
                                                  as verifier
==============================  ================  ==============================

Statistical categories carry ``UNCALIBRATED`` unless the caller supplied a
reference expectation, in which case the severity is derived from the exact
binomial interval -- a documented, sample-aware rule, never an absolute
threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Tuple

from backend.detection.models import (
    CalibrationState,
    EvidenceCategory,
    Severity,
)

__all__ = [
    "EvidenceItem",
    "ThreatEvidence",
    "DETERMINISTIC_SEVERITY",
    "BLOCKING_CATEGORIES",
    "INTEGRITY_CATEGORIES",
    "AUTHORIZATION_CATEGORIES",
    "QUANTUM_CATEGORIES",
    "EvidenceGroup",
    "category_group",
    "assign_finding_ids",
    "statistical_severity",
]


DETERMINISTIC_SEVERITY: Mapping[EvidenceCategory, Severity] = {
    EvidenceCategory.TRANSCRIPT_INTEGRITY: Severity.HIGH,
    EvidenceCategory.CONSISTENCY_ANOMALY: Severity.MODERATE,
    EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY: Severity.HIGH,
    EvidenceCategory.REPLAY: Severity.HIGH,
    EvidenceCategory.SIGNER_AUTHORIZATION: Severity.CRITICAL,
    EvidenceCategory.VERIFIER_AUTHORIZATION: Severity.CRITICAL,
}




BLOCKING_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.TRANSCRIPT_INTEGRITY,
    EvidenceCategory.CONSISTENCY_ANOMALY,
    EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
    EvidenceCategory.REPLAY,
    EvidenceCategory.SIGNER_AUTHORIZATION,
    EvidenceCategory.VERIFIER_AUTHORIZATION,
)


INTEGRITY_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.TRANSCRIPT_INTEGRITY,
    EvidenceCategory.CONSISTENCY_ANOMALY,
    EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
    EvidenceCategory.REPLAY,
)
AUTHORIZATION_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.SIGNER_AUTHORIZATION,
    EvidenceCategory.VERIFIER_AUTHORIZATION,
)
QUANTUM_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY,
    EvidenceCategory.CHANNEL_ANOMALY,
)


class EvidenceGroup(str, Enum):
    """The three families of findings, used to pick the overall status."""

    INTEGRITY = "INTEGRITY"
    AUTHORIZATION = "AUTHORIZATION"
    QUANTUM = "QUANTUM"


def category_group(category: EvidenceCategory) -> EvidenceGroup:
    """Return the family ``category`` belongs to."""
    if category in INTEGRITY_CATEGORIES:
        return EvidenceGroup.INTEGRITY
    if category in AUTHORIZATION_CATEGORIES:
        return EvidenceGroup.AUTHORIZATION
    return EvidenceGroup.QUANTUM


def statistical_severity(
    rate: float | None,
    lower: float | None,
    reference: float | None,
) -> Tuple[Severity, CalibrationState]:
    """Return the severity and calibration state for a sampled rate.

    With no reference the evidence is ``UNCALIBRATED`` -- the honest default.

    With a reference the rule is stated explicitly and is sample-aware:

    * the observed rate does not exceed the reference -> ``LOW`` (no anomaly
      finding is emitted for it in the first place);
    * the reference lies strictly below the interval's lower bound -> ``HIGH``:
      the sample is inconsistent with the reference at the stated confidence;
    * otherwise -> ``MODERATE``: the point estimate exceeds the reference but the
      sample does not exclude it.

    The rule uses the interval the engine already reports, so it adds no new
    constant and no absolute threshold.
    """
    if reference is None or rate is None:
        return Severity.UNCALIBRATED, CalibrationState.UNCALIBRATED
    if rate <= reference:
        return Severity.LOW, CalibrationState.CALIBRATED
    if lower is not None and lower > reference:
        return Severity.HIGH, CalibrationState.CALIBRATED
    return Severity.MODERATE, CalibrationState.CALIBRATED


@dataclass(frozen=True)
class EvidenceItem:
    """One observed fact inside a finding."""

    name: str
    observed: Any
    expected: Any | None = None
    source: str = ""
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "observed": self.observed,
            "expected": self.expected,
            "source": self.source,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class ThreatEvidence:
    """One structured finding.

    ``finding_id`` is assigned deterministically from the category and the
    position within that category, so identical observable input produces
    identical findings down to their identifiers.
    """

    category: EvidenceCategory
    severity: Severity
    calibration: CalibrationState
    blocking: bool
    explanation: str
    finding_id: str = ""
    strength: float | None = None
    evidence_items: Tuple[EvidenceItem, ...] = ()
    observed_values: Mapping[str, Any] = field(default_factory=dict)
    comparison_values: Mapping[str, Any] = field(default_factory=dict)
    source_metrics: Tuple[str, ...] = ()
    session_reference: str | None = None
    timestamp: str | None = None
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "calibration": self.calibration.value,
            "blocking": self.blocking,
            "strength": self.strength,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
            "observed_values": dict(self.observed_values),
            "comparison_values": dict(self.comparison_values),
            "explanation": self.explanation,
            "source_metrics": list(self.source_metrics),
            "session_reference": self.session_reference,
            "timestamp": self.timestamp,
            "notes": list(self.notes),
        }


def assign_finding_ids(findings: Iterable[ThreatEvidence]) -> Tuple[ThreatEvidence, ...]:
    """Return ``findings`` with deterministic per-category identifiers."""
    counters: Dict[str, int] = {}
    assigned = []
    for finding in findings:
        key = finding.category.value
        counters[key] = counters.get(key, 0) + 1
        assigned.append(
            replace(finding, finding_id=f"{key}-{counters[key]:02d}")
        )
    return tuple(assigned)
