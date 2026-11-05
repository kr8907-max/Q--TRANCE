"""Curves, and the rule that every point is a measured point.

There is no interpolation, no smoothing and no fitted curve in this layer. These
tests pin that a point carries the trial count behind it, that the eight
reference curves are exactly the eight the brief names, and that ROC/PR are
deliberately absent rather than accidentally missing.
"""

from __future__ import annotations

import pytest

from backend.evaluation.curves import (
    CURVE_CALIBRATION_DISTRIBUTION,
    CURVE_DETECTION_VS_ATTACK,
    CURVE_DETECTION_VS_SAMPLE_SIZE,
    CURVE_FAR_VS_THRESHOLD,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    CURVE_MISMATCH_VS_NOISE,
    CURVE_THRESHOLD_OPERATING,
    REFERENCE_CURVES,
    build_curve,
    check_strictly_increasing_x,
    curve_from_pairs,
    describe_curve,
    empirical_cdf,
    histogram,
    threshold_sweep_curve,
)
from backend.evaluation.models import CurvePoint







def test_the_eight_reference_curves_are_the_ones_the_brief_names() -> None:
    assert len(REFERENCE_CURVES) == 8
    assert set(REFERENCE_CURVES) == {
        CURVE_DETECTION_VS_ATTACK,
        CURVE_FRR_VS_NOISE,
        CURVE_FAR_VS_THRESHOLD,
        CURVE_DETECTION_VS_SAMPLE_SIZE,
        CURVE_FIDELITY_VS_ATTACK,
        CURVE_MISMATCH_VS_NOISE,
        CURVE_CALIBRATION_DISTRIBUTION,
        CURVE_THRESHOLD_OPERATING,
    }
    assert len(set(REFERENCE_CURVES)) == 8


def test_roc_and_pr_are_not_reference_curves() -> None:


    joined = " ".join(REFERENCE_CURVES).lower()
    assert "roc" not in joined
    assert "precision_recall" not in joined
    assert "pr_curve" not in joined







def test_build_curve_preserves_point_order() -> None:
    points = [
        CurvePoint(x=0.0, y=0.1, trials=5),
        CurvePoint(x=0.5, y=0.6, trials=5),
        CurvePoint(x=1.0, y=0.9, trials=5),
    ]
    curve = build_curve("demo", "x", "y", points)
    assert [point.x for point in curve.points] == [0.0, 0.5, 1.0]
    assert curve.name == "demo"


def test_curve_from_pairs_stamps_a_common_trial_count() -> None:
    curve = curve_from_pairs("demo", "x", "y", [(0.1, 0.2), (0.3, 0.4)], trials=12)
    assert [point.trials for point in curve.points] == [12, 12]
    assert curve.points[0].y == pytest.approx(0.2)
    assert curve.points[0].x_label == "x"


def test_a_curve_with_no_points_is_allowed_but_empty() -> None:


    curve = build_curve("empty", "x", "y", [])
    assert curve.points == ()
    assert describe_curve(curve)["point_count"] == 0
    assert describe_curve(curve)["total_trials"] == 0


def test_curve_conditions_and_notes_are_carried() -> None:
    curve = build_curve(
        "demo",
        "x",
        "y",
        [CurvePoint(x=0.0, y=0.0, trials=1)],
        conditions={"state_count": 500},
        notes=("measured, not interpolated",),
    )
    assert curve.conditions == {"state_count": 500}
    assert curve.notes == ("measured, not interpolated",)







def test_the_ecdf_is_monotone_and_ends_at_one() -> None:
    points = empirical_cdf([0.3, 0.1, 0.2, 0.1])
    assert [point.x for point in points] == [0.1, 0.1, 0.2, 0.3]
    ys = [point.y for point in points]
    assert ys == sorted(ys)
    assert ys[-1] == pytest.approx(1.0)
    assert all(point.trials == 4 for point in points)


def test_the_ecdf_records_the_rank_of_each_point() -> None:
    points = empirical_cdf([5.0, 1.0])
    assert [point.metadata["rank"] for point in points] == [1, 2]


def test_the_ecdf_of_nothing_is_empty() -> None:
    assert empirical_cdf([]) == ()


def test_the_histogram_counts_every_value_including_the_extremes() -> None:


    points = histogram([0.0, 0.5, 1.0, 5.0], bins=2, lower=0.0, upper=1.0)
    assert sum(point.metadata["count"] for point in points) == 4


def test_the_histogram_reports_its_bin_edges() -> None:
    points = histogram([0.0, 1.0], bins=4)
    for point in points:
        assert point.metadata["bin_upper"] > point.metadata["bin_lower"]
    assert points[0].metadata["bin_lower"] == pytest.approx(0.0)
    assert points[-1].metadata["bin_upper"] == pytest.approx(1.0)


def test_the_histogram_densities_sum_to_one() -> None:
    points = histogram([index / 10 for index in range(10)], bins=5)
    assert sum(point.y for point in points) == pytest.approx(1.0)


def test_a_degenerate_histogram_range_is_widened_rather_than_dividing_by_zero() -> None:
    points = histogram([2.0, 2.0, 2.0], bins=3)
    assert len(points) == 3
    assert sum(point.metadata["count"] for point in points) == 3


def test_an_empty_histogram_is_empty() -> None:
    assert histogram([]) == ()
    assert histogram([1.0], bins=0) == ()







def test_the_threshold_sweep_maps_a_count_to_a_rate() -> None:
    curve = threshold_sweep_curve([0, 5, 10], 200)
    assert curve.name == CURVE_FAR_VS_THRESHOLD
    assert [point.x for point in curve.points] == [0.0, 5.0, 10.0]
    assert [point.y for point in curve.points] == pytest.approx([0.0, 0.025, 0.05])
    assert curve.conditions["state_count"] == 200


def test_the_threshold_sweep_says_it_is_not_an_roc() -> None:
    curve = threshold_sweep_curve([1], 100)
    assert any("not an ROC" in note for note in curve.notes)


def test_the_threshold_sweep_is_defined_without_a_sample_size() -> None:
    curve = threshold_sweep_curve([1, 2], 0)
    assert [point.y for point in curve.points] == [0.0, 0.0]







def test_a_strictly_increasing_curve_passes_the_guard() -> None:
    curve = curve_from_pairs("ok", "x", "y", [(0.0, 1.0), (0.5, 2.0), (1.0, 3.0)])
    check_strictly_increasing_x(curve)


def test_a_duplicate_x_is_refused() -> None:
    curve = curve_from_pairs("dup", "x", "y", [(0.0, 1.0), (0.0, 2.0)])
    with pytest.raises(ValueError, match="non-increasing"):
        check_strictly_increasing_x(curve)


def test_an_out_of_order_x_is_refused() -> None:
    curve = curve_from_pairs("backwards", "x", "y", [(1.0, 1.0), (0.5, 2.0)])
    with pytest.raises(ValueError, match="non-increasing"):
        check_strictly_increasing_x(curve)


def test_a_single_point_curve_passes_the_guard() -> None:
    check_strictly_increasing_x(curve_from_pairs("one", "x", "y", [(0.0, 1.0)]))
    check_strictly_increasing_x(build_curve("none", "x", "y", []))







def test_describe_curve_sums_the_evidence_behind_the_points() -> None:
    curve = build_curve(
        "demo",
        "x",
        "y",
        [
            CurvePoint(x=0.0, y=0.1, trials=10),
            CurvePoint(x=1.0, y=0.2, trials=15),
        ],
        conditions={"noise": "depolarizing"},
    )
    described = describe_curve(curve)
    assert described["point_count"] == 2
    assert described["total_trials"] == 25
    assert described["conditions"] == {"noise": "depolarizing"}
    assert len(described["points"]) == 2


def test_a_curve_point_serialises_its_metadata() -> None:
    point = CurvePoint(x=1.0, y=0.5, trials=3, metadata={"count": 3})
    assert point.to_dict()["metadata"] == {"count": 3}
    assert point.to_dict()["trials"] == 3
