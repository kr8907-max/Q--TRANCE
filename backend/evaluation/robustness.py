"""Noise robustness: what honest noise costs, and what an attack costs on top.

The grid
--------
Two things are measured, and they are measured rather than assumed:

1. **honest channel, increasing noise** -- how the false-rejection rate moves as
   the honest channel degrades. A detector that only works on a perfect channel
   is not a detector.
2. **noise plus attack** -- whether an attack is still detectable when it sits on
   top of a noisy honest channel. This is the case that matters, because a real
   channel is never noiseless.

The noise levels are named (``none``/``low``/``medium``/``high``) and each name
is bound to an explicit depolarizing strength that is recorded with the result.
No level is chosen after seeing the numbers.

Nothing here assumes that detection degrades gracefully. If it collapses at
``high`` noise, that is what the result says.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from backend.calibration.models import DatasetRole, OperatingPoint
from backend.simulation import ScenarioConfig

from backend.evaluation.confusion import confusion_matrix
from backend.evaluation.metrics import metrics
from backend.evaluation.models import ConfusionMatrix, RobustnessResult, TrialRecord
from backend.evaluation.sweeps import run_attack_population, run_honest_population

__all__ = [
    "ROBUSTNESS_NOISE_LEVELS",
    "REFERENCE_ROBUSTNESS_ATTACKS",
    "honest_robustness_populations",
    "noise_attack_populations",
    "build_robustness_result",
    "evaluate_robustness",
]



ROBUSTNESS_NOISE_LEVELS: Tuple[Tuple[str, float], ...] = (
    ("none", 0.0),
    ("low", 0.005),
    ("medium", 0.02),
    ("high", 0.10),
)


REFERENCE_ROBUSTNESS_ATTACKS: Tuple[str, ...] = (
    "intercept_resend",
    "channel_tampering",
)


def honest_robustness_populations(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    levels: Sequence[Tuple[str, float]] = ROBUSTNESS_NOISE_LEVELS,
    noise_type: str = "depolarizing",
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> Dict[str, Tuple[TrialRecord, ...]]:
    """Return an honest population per named noise level.

    Each level gets its own disjoint seed block so the populations are
    independent draws rather than overlapping windows of one stream.
    """
    populations: Dict[str, Tuple[TrialRecord, ...]] = {}
    for offset, (label, strength) in enumerate(levels):
        populations[label] = run_honest_population(
            base,
            point,
            evaluation_id=f"{evaluation_id}-honest-{label}",
            seed_start=seed_start + offset * trial_count,
            trial_count=trial_count,
            noise_type=noise_type,
            noise_strength=strength,
            dataset_role=dataset_role,
        )
    return populations


def noise_attack_populations(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    attack_types: Sequence[str] = REFERENCE_ROBUSTNESS_ATTACKS,
    attack_fraction: float = 0.20,
    levels: Sequence[Tuple[str, float]] = ROBUSTNESS_NOISE_LEVELS,
    noise_type: str = "depolarizing",
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
) -> Dict[str, Dict[str, Tuple[TrialRecord, ...]]]:
    """Return a malicious population per ``(noise level, attack)`` cell."""
    populations: Dict[str, Dict[str, Tuple[TrialRecord, ...]]] = {}
    block = 0
    for label, strength in levels:
        per_attack: Dict[str, Tuple[TrialRecord, ...]] = {}
        for attack_type in attack_types:
            per_attack[attack_type] = run_attack_population(
                base,
                point,
                evaluation_id=f"{evaluation_id}-{label}-{attack_type}",
                seed_start=seed_start + block * trial_count,
                trial_count=trial_count,
                attack_type=attack_type,
                fraction=attack_fraction,
                noise_type=noise_type,
                noise_strength=strength,
                dataset_role=dataset_role,
            )
            block += 1
        populations[label] = per_attack
    return populations


def build_robustness_result(
    name: str,
    honest: Mapping[str, Sequence[TrialRecord]],
    malicious: Mapping[str, Mapping[str, Sequence[TrialRecord]]],
    *,
    notes: Sequence[str] = (),
) -> RobustnessResult:
    """Assemble a :class:`RobustnessResult` from measured populations."""
    honest_frr: Dict[str, float | None] = {}
    matrices: Dict[str, ConfusionMatrix] = {}

    for label, records in honest.items():
        matrix = confusion_matrix(records)
        matrices[f"honest:{label}"] = matrix
        honest_frr[label] = metrics(records).frr

    detection: Dict[str, Dict[str, float | None]] = {}
    for label, per_attack in malicious.items():
        detection[label] = {}
        for attack_type, records in per_attack.items():
            matrix = confusion_matrix(records)
            matrices[f"{label}:{attack_type}"] = matrix
            detection[label][attack_type] = metrics(records).detection_rate

    return RobustnessResult(
        name=name,
        honest_frr_by_noise=honest_frr,
        detection_by_noise_and_attack=detection,
        matrices=matrices,
        notes=tuple(notes),
    )


def evaluate_robustness(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    levels: Sequence[Tuple[str, float]] = ROBUSTNESS_NOISE_LEVELS,
    attack_types: Sequence[str] = REFERENCE_ROBUSTNESS_ATTACKS,
    attack_fraction: float = 0.20,
    noise_type: str = "depolarizing",
    dataset_role: DatasetRole = DatasetRole.VALIDATION,
    notes: Sequence[str] = (),
) -> RobustnessResult:
    """Run the full robustness grid and return the measured result."""
    honest = honest_robustness_populations(
        base,
        point,
        evaluation_id=evaluation_id,
        seed_start=seed_start,
        trial_count=trial_count,
        levels=levels,
        noise_type=noise_type,
        dataset_role=dataset_role,
    )

    malicious = noise_attack_populations(
        base,
        point,
        evaluation_id=evaluation_id,
        seed_start=seed_start + 10_000,
        trial_count=trial_count,
        attack_types=attack_types,
        attack_fraction=attack_fraction,
        levels=levels,
        noise_type=noise_type,
        dataset_role=dataset_role,
    )
    composed = list(notes)
    composed.append(
        "honest populations and malicious populations use disjoint seed blocks, "
        "so no trial is scored twice"
    )
    composed.append(
        f"the attack fraction is fixed at {attack_fraction:g} across the grid; "
        "the grid varies noise, not intensity"
    )
    return build_robustness_result(
        f"{evaluation_id}-robustness", honest, malicious, notes=composed
    )
