"""Orchestration for evaluation.

Runs the M5 benchmark and reports its results.

Evaluation is the one place ground truth is legitimately consumed
--------------------------------------------------------------
FAR and FRR cannot be computed without knowing which trials were malicious, so
the benchmark reads labels deliberately. That is why the response carries
``ground_truth_used: true`` and an explicit assessment block, and why the
detection endpoint is a separate thing entirely.

The API adds no statistics. Rates come from
:func:`backend.evaluation.metrics_from_matrix` (or from the benchmark payload,
which already contains them); this module selects and renames fields.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from backend.api.schemas.evaluation import EvaluationRunRequest
from backend.api.store import ApiStore
from backend.evaluation import (
    REFERENCE_PROFILE,
    SMOKE_PROFILE,
    run_benchmark,
)


EVALUATION_LIMITATIONS = (
    "FAR and FRR are empirical rates measured on a specific dataset at one "
    "configuration; they are not cryptographic bounds",
    "the benchmark consumes ground truth deliberately, because rates cannot be "
    "computed without it; this endpoint is not the detection path",
    "results are conditional on the modelled channel, the sample size, the "
    "measurement mode and the modelled attacks",
    "no formal composition theorem and no forgery bound are established here",
)

_PROFILES = {"smoke": SMOKE_PROFILE, "reference": REFERENCE_PROFILE}


def run_evaluation(
    store: ApiStore, request: EvaluationRunRequest
) -> Dict[str, Any]:
    """Run a benchmark profile and store its summary and artifact."""
    profile = _PROFILES[request.profile]



    wrapper = run_benchmark(profile)
    payload = dict(wrapper["report"])

    evaluation_id = f"eval-{uuid4().hex[:12]}"
    summary = summarise(evaluation_id, payload)
    store.put_evaluation(
        evaluation_id,
        {
            "summary": summary,
            "artifact": payload,
            "markdown": wrapper.get("markdown"),
            "profile": profile.name,
        },
    )
    return summary


def summarise(evaluation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the compact summary from a benchmark payload."""
    attack_evaluation = payload.get("attack_evaluation", {}) or {}
    by_attack = attack_evaluation.get("by_attack_type", {}) or {}

    robustness = payload.get("robustness", {}) or {}
    provenance = payload.get("provenance", {}) or {}
    profile_parameters = provenance.get("profile_parameters", {}) or {}

    return {
        "evaluation_id": evaluation_id,
        "profile": provenance.get("profile", "unknown"),
        "dataset_role": "FINAL_EVALUATION",
        "seed_base": int(profile_parameters.get("seed_base", 0)),
        "configuration": _configuration_view(payload, profile_parameters),
        "operating_point": _operating_point_view(payload),
        "by_attack_type": {
            name: _metrics_view(row) for name, row in by_attack.items()
        },
        "honest_frr_by_noise": {
            str(level): value
            for level, value in (robustness.get("honest_frr_by_noise", {}) or {}).items()
        },
        "detection_by_noise_and_attack": {
            str(level): dict(values)
            for level, values in (
                robustness.get("detection_by_noise_and_attack", {}) or {}
            ).items()
        },
        "curve_names": sorted((payload.get("curves", {}) or {}).keys()),
        "sample_size_rows": len(
            ((payload.get("sample_size", {}) or {}).get("rows", []) or [])
        ),
        "runtime_seconds": provenance.get("runtime_seconds"),
        "ground_truth_used": True,
        "security_assessment": {
            "status": "empirical_measurement",
            "ground_truth_used": True,
            "formal_proof_present": False,
            "limitations": list(EVALUATION_LIMITATIONS),
        },
    }


def get_summary(store: ApiStore, evaluation_id: str) -> Dict[str, Any]:
    """Return a stored evaluation summary."""
    return dict(store.get_evaluation(evaluation_id)["summary"])


def get_artifact(store: ApiStore, evaluation_id: str) -> Dict[str, Any]:
    """Return the stored full benchmark artifact."""
    record = store.get_evaluation(evaluation_id)
    return {
        "evaluation_id": evaluation_id,
        "profile": record.get("profile", "unknown"),
        "artifact": record["artifact"],
        "markdown": record.get("markdown"),
    }


def _configuration_view(
    payload: Dict[str, Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    measurement = payload.get("measurement_configuration", {}) or {}
    reference_noise = measurement.get("reference_noise", {}) or {}
    operating_point = payload.get("operating_point", {}) or {}
    return {
        "profile": (payload.get("provenance", {}) or {}).get("profile", "unknown"),
        "description": (payload.get("provenance", {}) or {}).get("profile_description", ""),
        "state_count": int(parameters.get("state_count", operating_point.get("state_count", 0))),
        "calibration_sessions": int(parameters.get("calibration_sessions", 0)),
        "evaluation_trials": int(parameters.get("evaluation_trials", 0)),
        "measurement_mode": str(
            parameters.get("measurement_mode", measurement.get("measurement_mode", ""))
        ),
        "shot_count": int(parameters.get("shot_count", measurement.get("shot_count", 0))),
        "noise_type": str(
            reference_noise.get("noise_type", parameters.get("noise_type", ""))
        ),
        "reference_noise_strength": float(
            reference_noise.get(
                "noise_strength", parameters.get("reference_noise_strength", 0.0)
            )
        ),
        "attack_types": list(parameters.get("attack_types", [])),
        "attack_fraction": float(parameters.get("attack_fraction", 0.0)),
        "seed_base": int(parameters.get("seed_base", 0)),
    }


def _operating_point_view(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    point = payload.get("operating_point")
    if not point:
        return None
    noise = point.get("honest_channel", {}) or {}
    return {
        "name": point.get("name", ""),
        "protocol_version": point.get("protocol_version", ""),
        "statistic": point.get("statistic", ""),
        "state_count": int(point.get("state_count", 0)),
        "measurement_mode": point.get("measurement_mode", ""),
        "shot_count": int(point.get("shot_count", 0)),
        "p_upper": float(point.get("p_upper", 0.0)),
        "critical_count": int(point.get("critical_count", 0)),
        "threshold_rate": float(point.get("threshold_rate", 0.0)),
        "alpha": float(point.get("alpha", 0.0)),
        "noise_type": noise.get("noise_type", ""),
        "noise_strength": float(noise.get("noise_strength", 0.0)),
        "calibration_sessions": int(point.get("calibration_sessions", 0)),
        "observed_calibration_frr": point.get("observed_calibration_frr"),
    }


def _metrics_view(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a benchmark metric row onto the typed response model."""
    matrix = row.get("matrix", {}) or {}
    return {
        "confusion": {
            "tp": int(matrix.get("tp", 0)),
            "tn": int(matrix.get("tn", 0)),
            "fp": int(matrix.get("fp", 0)),
            "fn": int(matrix.get("fn", 0)),
            "total": matrix.get("total"),
            "honest": matrix.get("honest"),
            "malicious": matrix.get("malicious"),
        },
        "detection_rate": row.get("detection_rate"),
        "far": row.get("far"),
        "frr": row.get("frr"),
        "tpr": row.get("tpr"),
        "tnr": row.get("tnr"),
        "specificity": row.get("specificity"),
        "fnr": row.get("fnr"),
        "fpr": row.get("fpr"),
        "precision": row.get("precision"),
        "recall": row.get("recall"),
        "f1": row.get("f1"),
        "accuracy": row.get("accuracy"),
        "far_definition": row.get("far_definition"),
        "frr_definition": row.get("frr_definition"),
        "note": row.get("note"),
    }
