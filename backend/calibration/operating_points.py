"""The single reference operating point.

Exactly one operating point is defined, and it is *specified* rather than
*optimised*. No objective function was maximised, so no claim of optimality is
made anywhere in this project; the point is reproducible, configurable and
documented, which is what the milestone requires.

What the operating point contains
---------------------------------
* the primary statistic (``D_m``, the empirical verification mismatch rate);
* the threshold, with the calibration dataset it came from, the method, the
  error budget and the sample size it is defined for;
* the honest conditions it belongs to -- protocol version, channel, session
  size, measurement mode, shot count;
* the honest false-rejection rate **actually observed** on the calibration data,
  which is a measurement and not a restatement of ``alpha``.

The observed calibration rate is deliberately reported even though it flatters
the construction. A threshold whose nominal level is 5% and whose measured
rejection rate is 0% on its own calibration sample has not been validated at
5%; it has been *fitted* to that sample. The honest check is the independent
evaluation set, and that is what :mod:`backend.evaluation` produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence, Tuple

from backend.calibration.models import (
    CalibrationResult,
    DatasetRole,
    OperatingPoint,
    ThresholdConfig,
    ThresholdResult,
)
from backend.calibration.thresholds import REFERENCE_THRESHOLD_METHOD, derive_threshold

__all__ = [
    "REFERENCE_OPERATING_POINT_NAME",
    "REFERENCE_ALPHA",
    "REFERENCE_THRESHOLD_CONFIG",
    "observed_rejection_rate",
    "build_operating_point",
    "build_reference_operating_point",
]


REFERENCE_OPERATING_POINT_NAME = "m5-reference"


REFERENCE_ALPHA = 0.05



REFERENCE_THRESHOLD_CONFIG = ThresholdConfig(
    alpha=REFERENCE_ALPHA,
    calibration_alpha_fraction=0.5,
    method=REFERENCE_THRESHOLD_METHOD,
)


def observed_rejection_rate(
    threshold: ThresholdResult,
    mismatch_counts: Iterable[int],
    sample_size: int,
) -> float | None:
    """Return the fraction of sessions the threshold rejects.

    ``None`` when no sessions were supplied: "no sessions" and "no rejections"
    are different statements, and collapsing them would overstate the evidence.
    """
    counts = tuple(int(count) for count in mismatch_counts)
    if not counts:
        return None
    rejected = sum(1 for count in counts if threshold.rejects(count, sample_size))
    return rejected / len(counts)


def build_operating_point(
    calibration: CalibrationResult,
    *,
    name: str = REFERENCE_OPERATING_POINT_NAME,
    threshold_config: ThresholdConfig | None = None,
    state_count: int | None = None,
    notes: Sequence[str] = (),
) -> OperatingPoint:
    """Build an operating point from an honest calibration result.

    Every field of the operating point is read from the calibration record, so
    the point cannot describe conditions other than the ones its threshold was
    actually derived under.

    Raises
    ------
    ValueError
        If the calibration dataset is not a calibration-role dataset, or if a
        threshold cannot be derived from it.
    """
    if calibration.config.dataset_role is not DatasetRole.CALIBRATION:
        raise ValueError(
            "an operating point may be built only from a calibration-role "
            f"dataset; got {calibration.config.dataset_role.value!r}"
        )
    settings = (threshold_config or REFERENCE_THRESHOLD_CONFIG).validate()
    size = calibration.config.state_count if state_count is None else state_count
    threshold = derive_threshold(
        calibration, state_count=size, config=settings
    )

    observed = observed_rejection_rate(
        threshold,
        (record.n_mismatch for record in calibration.observations),
        size,
    )
    seed_start, seed_end = calibration.config.seed_range()

    composed = list(notes)
    composed.append(
        "the observed calibration false-rejection rate is measured on the "
        "calibration data itself and is therefore a fitted quantity, not an "
        "independent estimate of the operating point's false-rejection rate"
    )
    if calibration.homogeneity.homogeneous is False:
        composed.append(
            "the honest null is not homogeneous for this configuration, so the "
            "binomial interval behind the threshold is an approximation"
        )

    return OperatingPoint(
        name=name,
        threshold=threshold,
        protocol_version=calibration.config.protocol_version,
        noise_type=calibration.config.noise_type,
        noise_strength=calibration.config.noise_strength,
        state_count=size,
        measurement_mode=calibration.config.measurement_mode,
        shot_count=calibration.config.shot_count,
        calibration_seed_start=seed_start,
        calibration_seed_end=seed_end,
        observed_calibration_frr=observed,
        notes=tuple(composed),
    )


def build_reference_operating_point(
    calibration: CalibrationResult,
) -> OperatingPoint:
    """Build the reference operating point from a calibration result."""
    return build_operating_point(
        calibration,
        name=REFERENCE_OPERATING_POINT_NAME,
        threshold_config=REFERENCE_THRESHOLD_CONFIG,
        notes=(
            "reference operating point: one primary statistical test at "
            f"alpha={REFERENCE_ALPHA}, derived by {REFERENCE_THRESHOLD_METHOD}",
        ),
    )


def describe_operating_point(point: OperatingPoint) -> Dict[str, Any]:
    """Return a compact, human-readable description of an operating point."""
    return {
        "name": point.name,
        "statistic": point.statistic,
        "state_count": point.state_count,
        "measurement_mode": point.measurement_mode,
        "shot_count": point.shot_count,
        "honest_channel": {
            "noise_type": point.noise_type,
            "noise_strength": point.noise_strength,
        },
        "threshold_rate": point.threshold.threshold_rate,
        "critical_count": point.threshold.critical_count,
        "p_upper": point.threshold.p_upper,
        "alpha": point.threshold.config.alpha,
        "calibration_sessions": point.threshold.calibration_session_count,
        "calibration_seed_range": [
            point.calibration_seed_start,
            point.calibration_seed_end,
        ],
        "observed_calibration_frr": point.observed_calibration_frr,
    }


def evaluate_operating_point(
    point: OperatingPoint,
    sessions: Sequence[Tuple[int, int]],
) -> Dict[str, Any]:
    """Apply an operating point to ``(n_mismatch, n_valid)`` session pairs.

    A convenience for drivers and reports: it returns counts, not a verdict, and
    it never sees a label.
    """
    rejected = 0
    for n_mismatch, n_valid in sessions:
        if point.threshold.rejects(n_mismatch, n_valid):
            rejected += 1
    total = len(sessions)
    return {
        "operating_point": point.name,
        "sessions": total,
        "rejected": rejected,
        "rejection_rate": (rejected / total) if total else None,
    }
