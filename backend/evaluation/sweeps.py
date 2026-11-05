"""Experiment sweeps and the curves built from them.

This module is where Milestone 5 finally *runs* things: honest populations over a
noise sweep, malicious populations over an attack-intensity sweep, and the curve
builders that turn those populations into measured points.

Ground truth is read here
-------------------------
The attack sweeps need an attack configuration, which lives in
:mod:`backend.attacks`, and they read ``is_malicious`` and ``attack_type`` from
the finished records. That is legitimate: this is the evaluation layer, and the
brief permits ground truth in evaluation and nowhere else. The decision itself
was still made by :func:`~backend.evaluation.harness.decide_observable`, which
never saw a label.

No point on any curve is interpolated, smoothed or invented. Every
:class:`~backend.evaluation.models.CurvePoint` comes from trials that were run.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Sequence, Tuple

from backend.attacks import AttackConfig
from backend.calibration.models import DatasetRole, OperatingPoint
from backend.noise.base import NoiseConfig
from backend.simulation import ScenarioConfig
from backend.simulation.scenario import REFERENCE_ATTACK_FRACTION_SWEEP, REFERENCE_NOISE_SWEEP

from backend.evaluation.confusion import confusion_matrix
from backend.evaluation.curves import build_curve
from backend.evaluation.harness import run_trial
from backend.evaluation.metrics import metrics, summarise_population
from backend.evaluation.models import CurvePoint, CurveResult, TrialRecord

__all__ = [
    "HONEST_ATTACK_TYPE",
    "attack_config",
    "noise_config",
    "with_noise",
    "with_attack",
    "run_population",
    "run_honest_population",
    "run_attack_population",
    "population_curve",
    "detection_vs_attack_curve",
    "frr_vs_noise_curve",
    "mismatch_vs_noise_curve",
    "fidelity_vs_attack_curve",
    "population_mean",
]


HONEST_ATTACK_TYPE = "none"







def attack_config(
    attack_type: str,
    *,
    fraction: float = 0.0,
    parameters: Mapping[str, Any] | None = None,
    seed: int = 0,
) -> AttackConfig:
    """Return a validated attack configuration.

    ``"none"`` is accepted and yields the honest baseline, because the milestone
    treats "honest noise + malicious disturbance" as a first-class experiment and
    the honest arm must be expressible in the same vocabulary.
    """
    if attack_type == HONEST_ATTACK_TYPE:
        return AttackConfig()
    return AttackConfig(
        attack_type=attack_type,
        fraction=float(fraction),
        seed=int(seed),
        parameters=dict(parameters or {}),
    ).validate()


def noise_config(noise_type: str, noise_strength: float) -> NoiseConfig:
    """Return a validated noise configuration."""
    return NoiseConfig(
        noise_type=noise_type, noise_strength=float(noise_strength)
    ).validate()


def with_noise(base: ScenarioConfig, noise_type: str, noise_strength: float) -> ScenarioConfig:
    """Return ``base`` with the honest channel replaced."""
    return base.with_changes(
        noise=noise_config(noise_type, noise_strength),
        scenario_id=f"{base.scenario_id}-n{noise_strength:g}",
    )


def with_attack(
    base: ScenarioConfig,
    attack_type: str,
    *,
    fraction: float = 0.0,
    parameters: Mapping[str, Any] | None = None,
) -> ScenarioConfig:
    """Return ``base`` with the attack replaced."""
    return base.with_changes(
        attack=attack_config(attack_type, fraction=fraction, parameters=parameters),
        scenario_id=f"{base.scenario_id}-a{attack_type}-f{fraction:g}",
    )







def run_population(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> Tuple[TrialRecord, ...]:
    """Run ``trial_count`` trials of ``base`` over consecutive seeds."""
    if trial_count < 1:
        raise ValueError(f"trial_count must be at least 1, got {trial_count}")
    return tuple(
        run_trial(
            base,
            point,
            seed=seed_start + offset,
            experiment_id=evaluation_id,
            dataset_role=dataset_role,
        )
        for offset in range(trial_count)
    )


def run_honest_population(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    noise_type: str = "depolarizing",
    noise_strength: float = 0.0,
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> Tuple[TrialRecord, ...]:
    """Run an honest population under one channel configuration."""
    return run_population(
        with_noise(base, noise_type, noise_strength),
        point,
        evaluation_id=evaluation_id,
        seed_start=seed_start,
        trial_count=trial_count,
        dataset_role=dataset_role,
    )


def run_attack_population(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    attack_type: str,
    fraction: float = 0.0,
    parameters: Mapping[str, Any] | None = None,
    noise_type: str = "depolarizing",
    noise_strength: float = 0.0,
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> Tuple[TrialRecord, ...]:
    """Run a malicious population under one attack and one channel."""
    scenario = with_noise(base, noise_type, noise_strength)
    scenario = with_attack(
        scenario, attack_type, fraction=fraction, parameters=parameters
    )
    return run_population(
        scenario,
        point,
        evaluation_id=evaluation_id,
        seed_start=seed_start,
        trial_count=trial_count,
        dataset_role=dataset_role,
    )







def population_mean(
    records: Iterable[TrialRecord],
    selector: Callable[[TrialRecord], float | None],
) -> float | None:
    """Return the mean of ``selector`` over the records, or ``None``."""
    values = [
        value for value in (selector(record) for record in records) if value is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def population_curve(
    name: str,
    x_label: str,
    y_label: str,
    samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    value_fn: Callable[[Sequence[TrialRecord]], float | None],
    *,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Return a curve over measured populations.

    A population whose ``value_fn`` is undefined (``None``) contributes no point
    and is named in the curve's notes, so an undefined measurement is visible in
    the output rather than silently dropped.
    """
    points = []
    undefined: list[str] = []
    for x, population in samples:
        population = tuple(population)
        value = value_fn(population)
        if value is None:
            undefined.append(f"{x:g} ({len(population)} trials)")
            continue
        matrix = confusion_matrix(population)
        points.append(
            CurvePoint(
                x=float(x),
                y=float(value),
                trials=len(population),
                x_label=x_label,
                metadata={
                    "rejected": matrix.tp + matrix.fp,
                    "accepted": matrix.tn + matrix.fn,
                },
            )
        )

    composed = list(notes)
    if undefined:
        composed.append(
            "no point was plotted for these x values because the measurement was "
            f"undefined on that population: {', '.join(undefined)}"
        )
    return build_curve(
        name, x_label, y_label, points, conditions=conditions, notes=composed
    )


def detection_vs_attack_curve(
    samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    *,
    attack_type: str,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Curve 1: detection probability against attack intensity.

    ``y`` is ``tp / (tp + fn)`` on the malicious population at that intensity: the
    share of malicious trials the calibrated rule rejected.
    """
    merged = dict(conditions or {})
    merged["attack_type"] = attack_type
    composed = list(notes)
    composed.append(
        "the x axis is the attack fraction the experiment injected, not a "
        "threshold; the decision rule never sees it"
    )
    return population_curve(
        "detection_probability_vs_attack_intensity",
        "attack intensity (fraction of states)",
        "detection probability",
        samples,
        lambda records: metrics(records).detection_rate,
        conditions=merged,
        notes=composed,
    )


def frr_vs_noise_curve(
    samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    *,
    noise_type: str = "depolarizing",
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Curve 2: false-rejection rate against honest noise strength."""
    merged = dict(conditions or {})
    merged["noise_type"] = noise_type
    return population_curve(
        "frr_vs_honest_noise",
        "honest noise strength",
        "false-rejection rate",
        samples,
        lambda records: metrics(records).frr,
        conditions=merged,
        notes=notes,
    )


def mismatch_vs_noise_curve(
    samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    *,
    noise_type: str = "depolarizing",
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Curve 6: mean honest mismatch rate against noise strength."""
    merged = dict(conditions or {})
    merged["noise_type"] = noise_type
    return population_curve(
        "mismatch_vs_noise",
        "honest noise strength",
        "mean mismatch rate",
        samples,
        lambda records: population_mean(
            records, lambda record: record.statistics.mismatch_rate
        ),
        conditions=merged,
        notes=notes,
    )


def fidelity_vs_attack_curve(
    samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    *,
    attack_type: str,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> CurveResult:
    """Curve 5: mean analytic fidelity against attack intensity."""
    merged = dict(conditions or {})
    merged["attack_type"] = attack_type
    return population_curve(
        "fidelity_vs_attack_intensity",
        "attack intensity (fraction of states)",
        "mean analytic fidelity",
        samples,
        lambda records: population_mean(
            records, lambda record: record.statistics.mean_fidelity
        ),
        conditions=merged,
        notes=notes,
    )


def reference_noise_sweep() -> Tuple[float, ...]:
    """Return the reference honest noise sweep used by the benchmark."""
    return tuple(REFERENCE_NOISE_SWEEP)


def reference_attack_fraction_sweep() -> Tuple[float, ...]:
    """Return the reference attack-intensity sweep used by the benchmark."""
    return tuple(REFERENCE_ATTACK_FRACTION_SWEEP)


def threshold_tradeoff_curves(
    honest: Sequence[TrialRecord],
    malicious: Sequence[TrialRecord],
    *,
    state_count: int,
    critical_counts: Sequence[int] | None = None,
    conditions: Mapping[str, Any] | None = None,
    notes: Sequence[str] = (),
) -> Tuple[CurveResult, CurveResult]:
    """Return ``(far_vs_threshold, threshold_operating_curve)``.

    Both curves are measured, not modelled: for a candidate critical count ``k``,

    * ``FAR(k)`` is the share of **malicious** trials with ``n_mismatch > k``;
    * ``FRR(k)`` is the share of **honest** trials with ``n_mismatch > k``.

    Sweeping ``k`` therefore shows the actual trade-off this dataset exhibits,
    including the lumpiness that a small trial count produces. The reference
    critical count is recorded in the conditions so a reader can see where on the
    curve the project's single operating point sits.
    """
    if critical_counts is None:
        counts = sorted(
            {record.statistics.n_mismatch for record in tuple(honest) + tuple(malicious)}
        )
        counts = counts or [0]
    else:
        counts = sorted(int(count) for count in critical_counts)

    def _rate(records: Sequence[TrialRecord], critical: int) -> float | None:
        population = tuple(records)
        if not population:
            return None
        return (
            sum(1 for record in population if record.statistics.n_mismatch > critical)
            / len(population)
        )

    far_points = []
    frr_points = []
    for critical in counts:
        far = _rate(malicious, critical)
        frr = _rate(honest, critical)
        if far is not None:
            far_points.append(
                CurvePoint(
                    x=float(critical),
                    y=float(far),
                    trials=len(malicious),
                    x_label="critical count",
                    metadata={"threshold_rate": critical / state_count},
                )
            )
        if frr is not None:
            frr_points.append(
                CurvePoint(
                    x=float(critical),
                    y=float(frr),
                    trials=len(honest),
                    x_label="critical count",
                    metadata={"threshold_rate": critical / state_count},
                )
            )

    merged = dict(conditions or {})
    merged["state_count"] = int(state_count)
    composed = list(notes)
    composed.append(
        "the x axis is a candidate critical count applied to measured mismatch "
        "counts; both axes come from the same two populations"
    )

    far_curve = build_curve(
        "far_vs_threshold",
        "critical count",
        "false acceptance rate",
        far_points,
        conditions=merged,
        notes=composed,
    )
    frr_curve = build_curve(
        "threshold_operating_curve",
        "critical count",
        "honest false-rejection rate",
        frr_points,
        conditions=merged,
        notes=composed,
    )
    return far_curve, frr_curve
