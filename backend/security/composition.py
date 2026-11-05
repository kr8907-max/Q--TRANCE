"""Conservative composition assessment.

This module records what is known about each component, what property was
actually evaluated, and what remains unresolved. It does **not** claim that
independently validated components automatically compose into a secure QDS
system. Where a formal composition theorem is absent, the conclusion says so
explicitly.

The assessment is read-only: it is a register of facts, not an optimisation or
a proof generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

__all__ = [
    "ComponentAssessment",
    "REFERENCE_COMPOSITION_ASSESSMENT",
    "composition_summary",
    "unresolved_dependencies",
    "render_composition_table",
]


@dataclass(frozen=True)
class ComponentAssessment:
    """One component's place in the security argument.

    Every field is a string rather than a typed model because the assessment is
    interpretive: it records what was shown, not a machine-checkable property.
    The purpose is to make the boundary explicit, not to compute over it.
    """

    component: str
    property_evaluated: str
    evidence_source: str
    assumption_boundary: str
    composition_dependency: str
    unresolved_dependency: str
    security_conclusion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "property_evaluated": self.property_evaluated,
            "evidence_source": self.evidence_source,
            "assumption_boundary": self.assumption_boundary,
            "composition_dependency": self.composition_dependency,
            "unresolved_dependency": self.unresolved_dependency,
            "security_conclusion": self.security_conclusion,
        }




REFERENCE_COMPOSITION_ASSESSMENT: Tuple[ComponentAssessment, ...] = (
    ComponentAssessment(
        component="M1 — Quantum teleportation core",
        property_evaluated=(
            "the teleportation circuit produces the correct Bell state, applies "
            "Pauli corrections, and measures in the expected basis"
        ),
        evidence_source=(
            "unit tests against exact analytic amplitudes; statevector and "
            "density-matrix equality checks"
        ),
        assumption_boundary=(
            "the qiskit-aer simulator correctly implements the quantum circuit; "
            "the Pauli correction table matches the standard teleportation protocol"
        ),
        composition_dependency=(
            "M2 uses M1's states and measurements as primitives"
        ),
        unresolved_dependency=(
            "no proof that the simulator's finite-precision arithmetic preserves "
            "the exact amplitudes for all input sizes; no hardware validation"
        ),
        security_conclusion=(
            "M1 establishes that the primitive works in simulation. It does not "
            "establish any security property, and no security claim is transferred "
            "from it."
        ),
    ),
    ComponentAssessment(
        component="M2 — Reference QDS protocol",
        property_evaluated=(
            "the protocol produces a consistent transcript, binds the message to "
            "the state sequence, and verifies the structure"
        ),
        evidence_source=(
            "protocol acceptance tests: transcript hash, binding derivation, "
            "signature verification, structural consistency"
        ),
        assumption_boundary=(
            "the canonicalisation and hash function are public and deterministic; "
            "there is no secret key, so unforgeability is not claimed"
        ),
        composition_dependency=(
            "M3 simulates attacks on M2 transcripts; M4 analyses M2 verification "
            "outcomes; M5 calibrates on M2 honest sessions"
        ),
        unresolved_dependency=(
            "no formal proof that the protocol satisfies a complete QDS security "
            "definition (unforgeability, non-repudiation, transferability); no "
            "secret key means no unforgeability is even attempted"
        ),
        security_conclusion=(
            "M2 is a reference protocol with binding and integrity, not a "
            "cryptographically secure QDS scheme. Its security properties are "
            "structural, not cryptographic."
        ),
    ),
    ComponentAssessment(
        component="M3 — Channel noise and attack simulation",
        property_evaluated=(
            "six attack families produce distinguishable observable effects on "
            "the simulated channel; honest noise produces a calibrated mismatch "
            "distribution"
        ),
        evidence_source=(
            "attack acceptance tests; M5 benchmark records per-attack decision "
            "outcomes and per-noise robustness grid"
        ),
        assumption_boundary=(
            "attacks are non-adaptive and do not learn the verifier's expected "
            "state sequence; the channel is a product channel; noise is stationary "
            "within a population"
        ),
        composition_dependency=(
            "M4 and M5 consume M3's observable outcomes; M6 interprets M3's "
            "attack behaviour"
        ),
        unresolved_dependency=(
            "adaptive attacks are not modelled; the attacker does not control the "
            "channel outside the simulated fraction; no real quantum hardware is "
            "involved"
        ),
        security_conclusion=(
            "M3 shows that modelled attacks produce observable effects in "
            "simulation. It does not show that real attacks on real hardware would "
            "produce the same effects, and it does not bound an adversary's "
            "advantage."
        ),
    ),
    ComponentAssessment(
        component="M4 — Observable detection engine",
        property_evaluated=(
            "the detector produces structured, non-attributing evidence from "
            "observable inputs, without reading attack labels or ground truth"
        ),
        evidence_source=(
            "detection acceptance tests; architecture tests that ground-truth "
            "identifiers do not reach the detector"
        ),
        assumption_boundary=(
            "the detector sees only ObservableExperimentData and "
            "ObservableDetectionInput; it has no access to GroundTruthMetadata"
        ),
        composition_dependency=(
            "M5 calibrates a threshold on the detector's mismatch output; M6 "
            "interprets the detector's evidence categories"
        ),
        unresolved_dependency=(
            "the detector does not calibrate its own thresholds; it reports "
            "evidence but does not decide whether the evidence is sufficient"
        ),
        security_conclusion=(
            "M4 is an evidence producer, not a decision mechanism. Its outputs "
            "are statistics and findings, not a verdict about security."
        ),
    ),
    ComponentAssessment(
        component="M5 — Statistical calibration and threshold derivation",
        property_evaluated=(
            "a threshold derived from honest-only calibration rejects modelled "
            "channel attacks at a measured rate while keeping honest false "
            "rejections low"
        ),
        evidence_source=(
            "calibration tests; benchmark acceptance tests; reference benchmark "
            "run with fixed seeds and recorded parameters"
        ),
        assumption_boundary=(
            "honest data is independent and identically distributed (exact for "
            "depolarizing, approximate for flip channels); the calibration and "
            "evaluation datasets are disjoint; the attack is non-adaptive"
        ),
        composition_dependency=(
            "M6 uses M5's threshold and measured rates to assess threat "
            "coverage"
        ),
        unresolved_dependency=(
            "the threshold is fitted to the calibration sample, so its nominal "
            "level is not an independent estimate; no proof that the threshold "
            "generalises to channels, sample sizes or attacks outside the "
            "reference configuration"
        ),
        security_conclusion=(
            "M5 provides a calibrated decision rule with measured empirical "
            "rates on modelled attacks. It does not provide a formal security "
            "proof, a forgery bound, or a guarantee of generalisation."
        ),
    ),
    ComponentAssessment(
        component="M6 — Security analysis and interpretation",
        property_evaluated=(
            "explicit assumptions, threat-specific observability, conservative "
            "composition assessment, and forbidden-claim checking"
        ),
        evidence_source=(
            "assumption register tests; observability matrix tests; composition "
            "tests; interpretation-layer tests"
        ),
        assumption_boundary=(
            "the analysis is conditional on all earlier milestones' assumptions; "
            "it does not add new physical or cryptographic assumptions"
        ),
        composition_dependency=(
            "none: M6 is the top-level interpretation layer"
        ),
        unresolved_dependency=(
            "no formal composition theorem links the components; no proof that "
            "the whole system satisfies a QDS security definition; no hardware "
            "or side-channel analysis"
        ),
        security_conclusion=(
            "M6 documents what is known, what is assumed, and what is not "
            "proven. It does not convert empirical measurements into security "
            "guarantees, and it does not claim that the components compose into "
            "a secure system without a formal composition theorem."
        ),
    ),
)


def composition_summary() -> Mapping[str, Any]:
    """Return a JSON-ready summary of the composition assessment."""
    return {
        "components": [item.to_dict() for item in REFERENCE_COMPOSITION_ASSESSMENT],
        "component_count": len(REFERENCE_COMPOSITION_ASSESSMENT),
        "unresolved_count": sum(
            1 for item in REFERENCE_COMPOSITION_ASSESSMENT if item.unresolved_dependency
        ),
        "formal_composition_theorem_present": False,
        "note": (
            "no formal composition theorem is claimed; each component's "
            "security conclusion identifies the gap rather than papering over it"
        ),
    }


def unresolved_dependencies() -> Tuple[str, ...]:
    """Return the unresolved dependencies of all components."""
    return tuple(
        f"{item.component}: {item.unresolved_dependency}"
        for item in REFERENCE_COMPOSITION_ASSESSMENT
        if item.unresolved_dependency
    )


def render_composition_table() -> str:
    """Return a Markdown table of the composition assessment."""
    lines = [
        "| Component | Property evaluated | Security conclusion |",
        "| --- | --- | --- |",
    ]
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        comp = item.component.replace("|", "\\|")
        prop = item.property_evaluated.replace("|", "\\|")
        conc = item.security_conclusion.replace("|", "\\|")
        lines.append(f"| {comp} | {prop} | {conc} |")
    return "\n".join(lines)
