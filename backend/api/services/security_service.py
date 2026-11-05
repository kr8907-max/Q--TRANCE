"""Orchestration for the security-analysis endpoints.

Everything here reads from :mod:`backend.security` and returns it. The service
does not summarise a security statement into something simpler, and in
particular it never produces a boolean verdict: the M6 boundaries travel with
every response.

The allowed-statement example is rendered from the committed benchmark artifact
rather than written by hand, so the numbers in it are measured numbers and not
decorative ones. When the artifact is absent the field is ``None``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.api.schemas.security import AnalyzeRequest, COMMON_LIMITATIONS
from backend.api.services.calibration_service import load_reference_artifact
from backend.security import (
    BANNED_TERMINOLOGY,
    FORBIDDEN_CLAIMS,
    check_statement,
    composition_summary,
    matrix_summary,
    reference_assumptions,
    render_measurement_statement,
    summarise_assumptions,
)


def _assessment(extra: Optional[List[str]] = None) -> Dict[str, Any]:
    limitations = list(COMMON_LIMITATIONS)
    if extra:
        limitations.extend(extra)
    return {
        "status": "assumption_conditioned",
        "formal_proof_present": False,
        "composable_security_established": False,
        "universal_detection_guarantee": False,
        "forgery_bound_derived": False,
        "limitations": limitations,
    }


def assumptions_view(
    *, noise_type: str, measurement_mode: str
) -> Dict[str, Any]:
    """Return the assumption register for a configuration."""
    register = reference_assumptions(
        noise_type=noise_type, measurement_mode=measurement_mode
    )
    summary = summarise_assumptions(register)
    return {
        "noise_type": noise_type,
        "measurement_mode": measurement_mode,
        "assumptions": [item.to_dict() for item in register.assumptions],
        "summary": dict(summary["summary"]),
        "weaker_than_exact": list(summary["weaker_than_exact"]),
        "by_status": {key: list(value) for key, value in summary["by_status"].items()},
        "note": summary["note"],
        "security_assessment": _assessment(
            [
                f"the register is resolved for noise_type={noise_type!r} and "
                f"measurement_mode={measurement_mode!r}; another configuration "
                "yields a different register",
            ]
        ),
    }


def observability_view() -> Dict[str, Any]:
    """Return the threat-observability matrix."""
    summary = matrix_summary()
    return {
        "rows": list(summary["rows"]),
        "quantum_visible": list(summary["quantum_visible"]),
        "classical_only": list(summary["classical_only"]),
        "empirically_evaluated_count": int(summary["empirically_evaluated_count"]),
        "covered_count": int(summary["covered_count"]),
        "source": summary["source"],
        "security_assessment": _assessment(
            [
                "'classical_only' means the quantum mismatch-rate detector cannot "
                "see the threat; it does not mean the threat is undetectable by "
                "the system as a whole",
                "the measured rates come from the committed M5 benchmark and are "
                "empirical detection rates, not forgery probabilities",
            ]
        ),
    }


def composition_view() -> Dict[str, Any]:
    """Return the composition assessment."""
    summary = composition_summary()
    return {
        "components": list(summary["components"]),
        "component_count": int(summary["component_count"]),
        "unresolved_count": int(summary["unresolved_count"]),
        "formal_composition_theorem_present": bool(
            summary["formal_composition_theorem_present"]
        ),
        "note": summary["note"],
        "security_assessment": _assessment(),
    }


def analyze_view(request: AnalyzeRequest) -> Dict[str, Any]:
    """Check caller-supplied statements against the forbidden-claim register."""
    checks = []
    for statement in request.statements:
        result = check_statement(statement)
        checks.append(
            {
                "statement": result.statement,
                "verdict": result.verdict.value,
                "violations": list(result.violations),
                "reasons": list(result.reasons),
            }
        )

    return {
        "checks": checks,
        "forbidden_claims": [
            {"claim": claim, "reason": reason} for claim, reason in FORBIDDEN_CLAIMS
        ],
        "banned_terminology": [
            {"term": term, "reason": reason} for term, reason in BANNED_TERMINOLOGY
        ],
        "allowed_statement_example": _allowed_example(),
        "notes": [
            "the checker is a blunt substring guard-rail with clause-level "
            "negation handling, not a completeness guarantee",
            "the forbidden claims are listed so the boundary is visible; they are "
            "not a description of anything this project measured",
        ],
        "security_assessment": _assessment(),
    }


def _allowed_example() -> Optional[str]:
    """Render the allowed statement shape from the committed benchmark.

    Returns ``None`` rather than inventing numbers when the artifact is absent.
    """
    artifact = load_reference_artifact()
    if not artifact:
        return None
    point = artifact.get("operating_point", {}) or {}
    noise = point.get("honest_channel", {}) or {}
    attack = (
        (artifact.get("attack_evaluation", {}) or {}).get("by_attack_type", {}) or {}
    ).get("intercept_resend")
    if not point or not attack:
        return None

    return render_measurement_statement(
        state_count=int(point.get("state_count", 0)),
        measurement_mode=str(point.get("measurement_mode", "")),
        shot_count=int(point.get("shot_count", 0)),
        noise_type=str(noise.get("noise_type", "")),
        noise_strength=float(noise.get("noise_strength", 0.0)),
        honest_trials=int(point.get("calibration_sessions", 0)),
        frr=point.get("observed_calibration_frr"),
        attack_type="intercept_resend",
        attack_fraction=float(attack.get("attack_fraction", 0.0)),
        detection_rate=attack.get("detection_rate"),
        far=attack.get("far"),
    )
