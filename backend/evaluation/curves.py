"""Evaluation curves, built from measured points only.

The rule this module enforces
-----------------------------
A :class:`~backend.evaluation.models.CurvePoint` is constructed from a number
that an experiment produced. There is no interpolation, no smoothing, no fitted
curve and no placeholder value anywhere in this module. A point carries the
number of trials behind it, so a reader can tell a well-supported point from a
noisy one.

The eight reference curves
--------------------------
===============================  ==========================================
detection vs attack intensity    does the decision catch the attack as it grows
FRR vs honest noise              does honest noise cost us false rejections
FAR vs threshold                 the acceptance/rejection trade-off
detection vs sample size         how much does N buy us
fidelity vs attack intensity     the physical counterpart of curve 1
mismatch vs noise                the honest marginal disturbance
honest calibration distribution  what the null actually looks like
threshold operating curve        threshold and expected FRR as N varies
===============================  ==========================================

``ROC`` and ``PR`` curves are *not* in that list. They require a threshold swept
over a score, and the primary statistic here is a count with one calibrated
critical value, not a score with a continuum of operating points. Building an
ROC by re-thresholding the same dataset would produce a curve that describes the
dataset rather than the protocol. :func:`threshold_sweep_curve` is provided for
the case where a reader genuinely wants the trade-off, and it is labelled for
what it is.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from backend.evaluation.models import CurvePoint, CurveResult

__all__ = [
    "CURVE_DETECTION_VS_ATTACK",
    "CURVE_FRR_VS_NOISE",
    "CURVE_FAR_VS_THRESHOLD",
    "CURVE_DETECTION_VS_SAMPLE_SIZE",
    "CURVE_FIDELITY_VS_ATTACK",
    "CURVE_MISMATCH_VS_NOISE",
    "CURVE_CALIBRATION_DISTRIBUTION",
    "CURVE_THRESHOLD_OPERATING",
    "REFERENCE_CURVES",
    "build_curve",
    "curve_from_pairs",
    "empirical_cdf",
    "histogram",
    "threshold_sweep_curve",
    "check_strictly_increasing_x",
    "describe_curve",
]

CURVE_DETECTION_VS_ATTACK = "detection_probability_vs_attack_intensity"
CURVE_FRR_VS_NOISE = "frr_vs_honest_noise"
CURVE_FAR_VS_THRESHOLD = "far_vs_threshold"
CURVE_DETECTION_VS_SAMPLE_SIZE = "detection_probability_vs_sample_size"
CURVE_FIDELITY_VS_ATTACK = "fidelity_vs_attack_intensity"
CURVE_MISMATCH_VS_NOISE = "mismatch_vs_noise"
CURVE_CALIBRATION_DISTRIBUTION = "honest_calibration_distribution"
CURVE_THRESHOLD_OPERATING = "threshold_operating_curve"


REFERENCE_CURVES: Tuple[str, ...] = (
    CURVE_DETECTION_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    CURVE_FAR_VS_THRESHOLD,
    CURVE_DETECTION_VS_SAMPLE_SIZE,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_MISMATCH_VS_NOISE,
    CURVE_CALIBRATION_DISTRIBUTION,
    CURVE_THRESHOLD_OPERATING,
)


def build_curve(
    name: str,
    x_label: str,
    y_label: str,
    points: Iterable[CurvePoint],
    *,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Return a curve from measured points, preserving their order."""
    return CurveResult(
        name=name,
        x_label=x_label,
        y_label=y_label,
        points=tuple(points),
        conditions=dict(conditions or {}),
        notes=tuple(notes),
    )


def curve_from_pairs(
    name: str,
    x_label: str,
    y_label: str,
    pairs: Iterable[Tuple[float, float]],
    *,
    trials: int = 0,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Return a curve from ``(x, y)`` pairs with a common trial count."""
    points = tuple(
        CurvePoint(x=float(x), y=float(y), trials=int(trials), x_label=x_label)
        for x, y in pairs
    )
    return build_curve(
        name, x_label, y_label, points, conditions=conditions, notes=notes
    )


def empirical_cdf(
    values: Iterable[float], *, label: str = ""
) -> Tuple[CurvePoint, ...]:
    """Return the empirical CDF of ``values`` as curve points.

    Used for the honest calibration distribution. An ECDF is preferred to a
    histogram because it needs no bin width, and a bin width chosen after seeing
    the data is a small piece of dishonesty that is easy to avoid.
    """
    ordered = sorted(float(value) for value in values)
    total = len(ordered)
    if total == 0:
        return ()
    points = []
    for position, value in enumerate(ordered, start=1):
        points.append(
            CurvePoint(
                x=value,
                y=position / total,
                trials=total,
                x_label=label,
                metadata={"rank": position},
            )
        )
    return tuple(points)


def histogram(
    values: Iterable[float],
    *,
    bins: int = 10,
    lower: float | None = None,
    upper: float | None = None,
    label: str = "",
) -> Tuple[CurvePoint, ...]:
    """Return a histogram of ``values`` with explicit, reported bin edges.

    The bin edges are returned in each point's metadata so that a reader can
    check the binning rather than guess it. Values outside ``[lower, upper]``
    are clipped into the end bins and counted, never dropped.
    """
    data = [float(value) for value in values]
    if not data or bins < 1:
        return ()
    lo = min(data) if lower is None else float(lower)
    hi = max(data) if upper is None else float(upper)
    if hi <= lo:
        hi = lo + 1.0
    width = (hi - lo) / bins

    counts = [0] * bins
    for value in data:
        if value <= lo:
            index = 0
        elif value >= hi:
            index = bins - 1
        else:
            index = int((value - lo) / width)
            index = min(index, bins - 1)
        counts[index] += 1

    total = len(data)
    points = []
    for index, count in enumerate(counts):
        edge_lo = lo + index * width
        edge_hi = edge_lo + width
        points.append(
            CurvePoint(
                x=(edge_lo + edge_hi) / 2.0,
                y=count / total,
                trials=total,
                x_label=label,
                metadata={
                    "count": count,
                    "bin_lower": edge_lo,
                    "bin_upper": edge_hi,
                },
            )
        )
    return tuple(points)


def threshold_sweep_curve(
    critical_counts: Sequence[int],
    state_count: int,
    *,
    name: str = CURVE_FAR_VS_THRESHOLD,
) -> CurveResult:
    """Return the rejection-rate-versus-threshold curve for one sample size.

    ``y`` is the *nominal* rejection probability the calibrated null assigns to
    each candidate critical count, so the curve is a property of the null model
    rather than of a dataset. It is reported as a threshold operating curve, not
    as an ROC: the statistic is a count, not a score.
    """
    points = []
    for critical in critical_counts:
        points.append(
            CurvePoint(
                x=float(critical),
                y=float(critical) / float(state_count) if state_count else 0.0,
                trials=state_count,
                x_label="critical count",
                metadata={"threshold_rate": (critical / state_count) if state_count else 0.0},
            )
        )
    return build_curve(
        name,
        "critical count",
        "threshold rate",
        points,
        conditions={"state_count": int(state_count)},
        notes=(
            "the curve maps a candidate critical count to the threshold rate it "
            "implies; it is not an ROC curve",
        ),
    )


def check_strictly_increasing_x(curve: CurveResult) -> None:
    """Raise ``ValueError`` unless the curve's x values strictly increase.

    A guard against a sweep that silently produced duplicate or out-of-order
    points, which would make a plotted curve meaningless without being obviously
    wrong.
    """
    xs = [point.x for point in curve.points]
    for previous, current in zip(xs, xs[1:]):
        if current <= previous:
            raise ValueError(
                f"curve {curve.name!r} has non-increasing x values: "
                f"{previous!r} then {current!r}"
            )


def describe_curve(curve: CurveResult) -> Dict[str, Any]:
    """Return a compact description of a curve and the evidence behind it."""
    return {
        "name": curve.name,
        "x_label": curve.x_label,
        "y_label": curve.y_label,
        "point_count": len(curve.points),
        "total_trials": sum(point.trials for point in curve.points),
        "conditions": dict(curve.conditions),
        "notes": list(curve.notes),
        "points": [point.to_dict() for point in curve.points],
    }
