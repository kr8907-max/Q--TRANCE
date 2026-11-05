"""Orchestration for calibration.

Two operations:

* :func:`run_calibration` builds an honest-only calibration dataset with the M5
  dataset builder, estimates the baseline with the M5 estimator and derives the
  operating point with the M5 threshold derivation. The API performs no
  statistics of its own.
* :func:`reference_description` reports the reference methodology, and reads the
  operating point recorded in the committed benchmark artifact when that artifact
  is present.

Calibration is never implicit. A verification or detection request cannot trigger
one, because a threshold derived on demand would not be the calibrated object the
reports describe.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from backend.api.errors import ApiError, ErrorCode
from backend.api.schemas.calibration import CalibrationRunRequest
from backend.api.store import ApiStore
from backend.attacks import AttackValidationError
from backend.calibration import (
    REFERENCE_ALPHA,
    REFERENCE_OPERATING_POINT_NAME,
    REFERENCE_THRESHOLD_METHOD,
    DatasetRole,
    build_operating_point,
    estimate_baseline,
)
from backend.evaluation import SMOKE_PROFILE, benchmark_base_scenario, build_calibration_dataset
from backend.noise import NoiseValidationError
from backend.protocol import ProtocolError

_REPO_ROOT = Path(__file__).resolve().parents[3]



REFERENCE_ARTIFACT = _REPO_ROOT / "benchmarks" / "m5-reference.json"

CALIBRATION_LIMITATIONS = (
    "a confidence interval is a statement about an unknown parameter, not a "
    "cryptographic security parameter",
    "the threshold is fitted to the calibration sample, so its nominal level is "
    "not an independent estimate",
    "the threshold is valid only at the sample size, measurement mode, shot count "
    "and channel it was derived for",
    "the empirical false-rejection rate is a measurement on honest material, not "
    "a guarantee",
)

_CONFIGURATION_ERRORS = (
    NoiseValidationError,
    AttackValidationError,
    ProtocolError,
    ValueError,
)


def run_calibration(
    store: ApiStore, request: CalibrationRunRequest
) -> Dict[str, Any]:
    """Derive a threshold from an honest-only calibration dataset."""
    try:
        base = benchmark_base_scenario(SMOKE_PROFILE)
        config, observations = build_calibration_dataset(
            base,
            config_id=request.config_id,
            seed_start=request.seed_start,
            session_count=request.session_count,
            noise_type=request.noise_type,
            noise_strength=request.noise_strength,
            state_count=request.state_count,
            measurement_mode=request.measurement_mode,
            shot_count=request.shot_count,
            confidence=request.confidence,
            dataset_role=DatasetRole.CALIBRATION,
        )
        calibration = estimate_baseline(config, observations)
        operating_point = build_operating_point(
            calibration, name=f"api-{request.config_id}"
        )
    except _CONFIGURATION_ERRORS as exc:
        raise ApiError(
            ErrorCode.BAD_REQUEST,
            f"the calibration configuration was refused: {exc}",
            details={"reason": str(exc), "error_type": type(exc).__name__},
        ) from exc

    calibration_id = f"cal-{uuid4().hex[:12]}"
    payload: Dict[str, Any] = {
        "calibration_id": calibration_id,
        "config": _config_view(calibration.config),
        "total_valid": int(calibration.total_valid),
        "total_mismatch": int(calibration.total_mismatch),
        "pooled_rate": calibration.pooled_rate,
        "interval": _interval_view(calibration.interval),
        "upper_bound": _interval_view(calibration.upper_bound),
        "homogeneity": _homogeneity_view(calibration.homogeneity),
        "threshold": _threshold_view(operating_point),
        "operating_point": _operating_point_view(operating_point),
        "notes": list(calibration.notes),
        "security_assessment": _assessment(),
    }
    store.put_calibration(calibration_id, payload)
    return payload


def reference_description() -> Dict[str, Any]:
    """Describe the reference methodology and its recorded operating point."""
    recorded, provenance = _recorded_operating_point()
    return {
        "methodology": REFERENCE_THRESHOLD_METHOD,
        "statistic": "mismatch_rate",
        "operating_point_name": REFERENCE_OPERATING_POINT_NAME,
        "alpha": float(REFERENCE_ALPHA),
        "calibration_alpha": float(REFERENCE_ALPHA) * 0.5,
        "evaluation_alpha": float(REFERENCE_ALPHA) * 0.5,
        "recorded_operating_point": recorded,
        "provenance": provenance,
        "limitations": list(CALIBRATION_LIMITATIONS),
        "security_assessment": _assessment(),
    }


def _assessment() -> Dict[str, Any]:
    return {
        "status": "assumption_conditioned",
        "formal_proof_present": False,
        "limitations": list(CALIBRATION_LIMITATIONS),
    }


@lru_cache(maxsize=1)
def load_reference_artifact() -> Optional[Dict[str, Any]]:
    """Load and cache the committed reference benchmark, if it is present."""
    try:
        return json.loads(REFERENCE_ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _recorded_operating_point() -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    artifact = load_reference_artifact()
    if not artifact:
        return None, {
            "artifact": str(REFERENCE_ARTIFACT.name),
            "available": False,
            "note": "the committed benchmark artifact is not present in this checkout",
        }

    point = artifact.get("operating_point", {})
    noise = point.get("honest_channel", {})
    recorded = {
        "name": point.get("name", REFERENCE_OPERATING_POINT_NAME),
        "protocol_version": point.get("protocol_version", ""),
        "statistic": point.get("statistic", "mismatch_rate"),
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
    provenance = {
        "artifact": str(REFERENCE_ARTIFACT.name),
        "available": True,
        "milestone": artifact.get("milestone"),
        "reference_operating_point_name": artifact.get("reference_operating_point_name"),
        "note": (
            "read from the committed benchmark artifact; the API does not "
            "recompute the reference operating point"
        ),
    }
    return recorded, provenance


def _config_view(config: Any) -> Dict[str, Any]:
    return {
        "config_id": config.config_id,
        "protocol_version": config.protocol_version,
        "noise_type": config.noise_type,
        "noise_strength": float(config.noise_strength),
        "state_count": int(config.state_count),
        "measurement_mode": config.measurement_mode,
        "shot_count": int(config.shot_count),
        "statistic": config.statistic,
        "confidence": float(config.confidence),
        "seed_start": int(config.seed_start),
        "session_count": int(config.session_count),
        "dataset_role": config.dataset_role.value,
    }


def _interval_view(interval: Any) -> Optional[Dict[str, Any]]:
    if interval is None:
        return None
    return {
        "lower": float(interval.lower),
        "upper": float(interval.upper),
        "confidence": float(interval.confidence),
        "method": interval.method,
        "one_sided": bool(interval.one_sided),
        "successes": int(interval.successes),
        "trials": int(interval.trials),
        "width": float(interval.width),
    }


def _homogeneity_view(homogeneity: Any) -> Dict[str, Any]:
    return {
        "homogeneous": bool(homogeneity.homogeneous),
        "spread": float(homogeneity.spread),
        "tolerance": float(homogeneity.tolerance),
        "minimum": float(homogeneity.minimum),
        "maximum": float(homogeneity.maximum),
        "mean": float(homogeneity.mean),
        "state_count": int(homogeneity.state_count),
        "notes": list(homogeneity.notes),
    }


def _threshold_view(operating_point: Any) -> Dict[str, Any]:
    threshold = operating_point.threshold
    config = threshold.config
    return {
        "state_count": int(threshold.state_count),
        "p_upper": float(threshold.p_upper),
        "critical_count": int(threshold.critical_count),
        "threshold_rate": float(threshold.threshold_rate),
        "method": config.method,
        "alpha": float(config.alpha),
        "calibration_alpha": float(config.calibration_alpha),
        "evaluation_alpha": float(config.evaluation_alpha),
        "calibration_fingerprint": threshold.calibration_fingerprint,
        "calibration_session_count": int(threshold.calibration_session_count),
        "calibration_total_valid": int(threshold.calibration_total_valid),
        "calibration_total_mismatch": int(threshold.calibration_total_mismatch),
        "calibration_pooled_rate": threshold.calibration_pooled_rate,
        "calibration_role": threshold.calibration_role.value,
    }


def _operating_point_view(operating_point: Any) -> Dict[str, Any]:
    return {
        "name": operating_point.name,
        "protocol_version": operating_point.protocol_version,
        "noise_type": operating_point.noise_type,
        "noise_strength": float(operating_point.noise_strength),
        "state_count": int(operating_point.state_count),
        "measurement_mode": operating_point.measurement_mode,
        "shot_count": int(operating_point.shot_count),
        "calibration_seed_start": int(operating_point.calibration_seed_start),
        "calibration_seed_end": int(operating_point.calibration_seed_end),
        "observed_calibration_frr": operating_point.observed_calibration_frr,
        "threshold": _threshold_view(operating_point),
        "notes": list(operating_point.notes),
    }
