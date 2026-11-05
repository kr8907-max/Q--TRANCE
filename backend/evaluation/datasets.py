"""Dataset construction for calibration, validation and final evaluation.

Three datasets, three roles, no overlap
---------------------------------------
``CALIBRATION``
    honest runs only. Feeds the baseline estimate, the interval and the
    threshold. No attack is configured, so no attack label can exist in the
    dataset -- not because a filter removes it, but because it was never there.

``VALIDATION``
    an independent honest set plus controlled development attacks. Used while
    building and checking the evaluation, never to fit the threshold.

``FINAL_EVALUATION``
    fresh, independently seeded runs. This is the set whose numbers are
    reported.

Seed blocks are disjoint by construction and :func:`assert_disjoint_seeds`
checks it, so "independent" is a property of the code rather than a claim in a
comment.

Where the isolation rule bites
------------------------------
This module lives in the evaluation layer precisely because it has to run
scenarios. :mod:`backend.calibration` may not import :mod:`backend.simulation`,
so the bridge belongs here, on the far side of the boundary. What crosses the
boundary is a
:class:`~backend.calibration.models.CalibrationObservation`, which has no field
that could carry an attack type, an attack fraction, a noise label or a
ground-truth flag.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence, Tuple

from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    CalibrationConfig,
    CalibrationObservation,
    DatasetRole,
)
from backend.protocol.models import PROTOCOL_VERSION
from backend.simulation import ScenarioConfig

from backend.evaluation.harness import observable_statistics, scenario_for_trial

__all__ = [
    "DEFAULT_CALIBRATION_CONFIDENCE",
    "honest_observation",
    "build_calibration_dataset",
    "assert_disjoint_seeds",
    "SEED_BLOCK_SIZE",
]





DEFAULT_CALIBRATION_CONFIDENCE = 0.95


SEED_BLOCK_SIZE = 1_000_000


def _timestamp() -> str:
    """Return the current UTC time, second resolution."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def honest_observation(
    base: ScenarioConfig,
    *,
    seed: int,
    experiment_id: str,
    dataset_role: DatasetRole,
    noise_type: str,
    noise_strength: float,
    timestamp: str | None = None,
) -> CalibrationObservation:
    """Run one honest scenario and return its calibration observation.

    The observation is built from the observable half alone. ``is_malicious``,
    ``attack_type`` and the noise label are *inputs* to the experiment
    configuration and are recorded in the configuration, never read back from a
    result.
    """
    scenario = scenario_for_trial(
        base.with_changes(
            noise=base.noise.__class__(
                noise_type=noise_type, noise_strength=float(noise_strength)
            ),
            attack=base.attack.__class__(),
            scenario_id=f"{experiment_id}-s{int(seed)}",
        ),
        seed,
    )
    from backend.simulation import run_scenario

    result = run_scenario(scenario)
    statistics = observable_statistics(result.observable)





    match_probabilities = tuple(
        float(item.probability_expected)
        for item in (getattr(result.observable, "states", ()) or ())
        if getattr(item, "probability_expected", None) is not None
    )

    return CalibrationObservation(
        experiment_id=f"{experiment_id}-s{int(seed)}",
        random_seed=int(seed),
        state_count=int(scenario.state_count),
        n_valid=int(statistics.n_valid),
        n_mismatch=int(statistics.n_mismatch),
        mismatch_rate=statistics.mismatch_rate,
        dataset_role=dataset_role,
        timestamp=timestamp or _timestamp(),
        analytic_match_probabilities=match_probabilities,
        mean_fidelity=statistics.mean_fidelity,
        per_basis_mismatch_rates=dict(statistics.per_basis_mismatch_rates),
    )


def build_calibration_dataset(
    base: ScenarioConfig,
    *,
    config_id: str,
    seed_start: int,
    session_count: int,
    noise_type: str = "depolarizing",
    noise_strength: float = 0.0,
    state_count: int | None = None,
    measurement_mode: str | None = None,
    shot_count: int | None = None,
    confidence: float = DEFAULT_CALIBRATION_CONFIDENCE,
    dataset_role: DatasetRole = DatasetRole.CALIBRATION,
    timestamp: str | None = None,
) -> Tuple[CalibrationConfig, Tuple[CalibrationObservation, ...]]:
    """Return an honest calibration configuration and its observations.

    The returned configuration is a :class:`CalibrationConfig`, which requires
    the calibration role when it is validated. Passing another role here is
    therefore refused by the configuration itself, not by this function.
    """
    size = int(state_count if state_count is not None else base.state_count)
    mode = str(measurement_mode if measurement_mode is not None else base.measurement_mode)
    shots = int(shot_count if shot_count is not None else base.shot_count)

    scenario_base = base.with_changes(
        state_count=size, measurement_mode=mode, shot_count=shots
    )

    observations = tuple(
        honest_observation(
            scenario_base,
            seed=seed_start + offset,
            experiment_id=config_id,
            dataset_role=dataset_role,
            noise_type=noise_type,
            noise_strength=noise_strength,
            timestamp=timestamp,
        )
        for offset in range(session_count)
    )

    config = CalibrationConfig(
        config_id=config_id,
        protocol_version=PROTOCOL_VERSION,
        noise_type=noise_type,
        noise_strength=float(noise_strength),
        state_count=size,
        measurement_mode=mode,
        shot_count=shots,
        statistic=STATISTIC_MISMATCH_RATE,
        confidence=float(confidence),
        seed_start=int(seed_start),
        session_count=int(session_count),
        dataset_role=dataset_role,
    ).validate()

    return config, observations


def assert_disjoint_seeds(
    datasets: Iterable[Tuple[str, Sequence[int]]],
) -> None:
    """Raise ``ValueError`` if any two datasets share a seed.

    Called by the benchmark before it runs, so a leakage accident fails loudly
    instead of producing a flattering number.
    """
    seen: dict[int, str] = {}
    for label, seeds in datasets:
        for seed in seeds:
            previous = seen.get(int(seed))
            if previous is not None and previous != label:
                raise ValueError(
                    f"seed {seed} appears in both {previous!r} and {label!r}: the "
                    "datasets are not independent"
                )
            seen[int(seed)] = label
