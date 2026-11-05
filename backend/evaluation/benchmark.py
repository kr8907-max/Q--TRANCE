"""The reference benchmark.

One entry point that runs the whole Milestone 5 measurement programme and
returns a report payload. Everything it produces comes from runs performed here;
nothing is read from a stored result file and nothing is extrapolated.

What it runs, in order
----------------------
1. **calibration** -- honest sessions at the reference sample size, honest only;
2. **operating point** -- the single reference point derived from that dataset;
3. **sample-size study** -- a fresh calibration and a fresh evaluation per sample
   size, so each size gets its own threshold rather than borrowing one;
4. **attack evaluation** -- one malicious population per attack type at the
   reference intensity;
5. **curves** -- the eight reference curves, from measured points;
6. **robustness** -- the noise grid, honest and noise-plus-attack;
7. **discrimination** -- the central experiment;
8. **report** -- assembled, with definitions and limitations attached.

Seed allocation
---------------
:class:`SeedAllocator` hands out disjoint blocks and
:func:`~backend.evaluation.datasets.assert_disjoint_seeds` verifies the result,
so calibration data and evaluation data cannot silently share a run.

Cost
----
Signing dominates the runtime, so the profile states the sample sizes and trial
counts explicitly and the benchmark reports how many scenarios it actually ran.
Two profiles are provided: :data:`REFERENCE_PROFILE` for the recorded benchmark
and :data:`SMOKE_PROFILE` for the test suite.
"""

from __future__ import annotations

import platform
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from backend.calibration.baseline import estimate_baseline
from backend.calibration.operating_points import (
    REFERENCE_OPERATING_POINT_NAME,
    build_reference_operating_point,
)
from backend.calibration.models import DatasetRole
from backend.calibration.thresholds import (
    derive_threshold_table,
    expected_false_rejection_rate,
)
from backend.attacks.base import FRACTIONAL_ATTACK_TYPES
from backend.protocol.models import MAX_STATE_COUNT, PROTOCOL_VERSION
from backend.simulation import ScenarioConfig

from backend.evaluation.curves import (
    CURVE_CALIBRATION_DISTRIBUTION,
    CURVE_DETECTION_VS_ATTACK,
    CURVE_DETECTION_VS_SAMPLE_SIZE,
    CURVE_FIDELITY_VS_ATTACK,
    CURVE_FRR_VS_NOISE,
    CURVE_MISMATCH_VS_NOISE,
    build_curve,
    empirical_cdf,
)
from backend.evaluation.datasets import (
    assert_disjoint_seeds,
    build_calibration_dataset,
)
from backend.evaluation.discrimination import discrimination_experiment
from backend.evaluation.metrics import metrics
from backend.evaluation.models import CurvePoint
from backend.evaluation.reports import build_report, render_markdown
from backend.evaluation.robustness import evaluate_robustness
from backend.evaluation.sweeps import (
    detection_vs_attack_curve,
    fidelity_vs_attack_curve,
    frr_vs_noise_curve,
    mismatch_vs_noise_curve,
    run_attack_population,
    run_honest_population,
    threshold_tradeoff_curves,
)

__all__ = [
    "BenchmarkProfile",
    "REFERENCE_PROFILE",
    "REFERENCE_SAMPLE_SIZE_DESIGN",
    "SMOKE_PROFILE",
    "SeedAllocator",
    "attack_fraction_for",
    "benchmark_base_scenario",
    "partition_sample_sizes",
    "run_benchmark",
    "benchmark_report",
]


BENCHMARK_MESSAGE = "transfer 100 units to account 7"












REFERENCE_SAMPLE_SIZE_DESIGN: Tuple[int, ...] = (100, 250, 500, 1000, 2500, 5000, 10000)


@dataclass(frozen=True)
class SampleSizePlan:
    """How many sessions and trials to run at one sample size.

    Derived from a *state budget* rather than hand-picked, so the reason the
    trial count falls as ``N`` rises is visible in the code and in the report:
    the quantity that costs time is the number of simulated states, which is
    ``trials x state_count``, and holding it roughly constant keeps the whole
    study inside a declared cost while still covering every design sample size.
    """

    state_count: int
    trials: int
    calibration_sessions: int

    @property
    def evaluation_states(self) -> int:
        """Return ``trials x state_count`` per arm."""
        return self.trials * self.state_count

    @property
    def calibration_states(self) -> int:
        """Return ``calibration_sessions x state_count``."""
        return self.calibration_sessions * self.state_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_count": int(self.state_count),
            "trials": int(self.trials),
            "calibration_sessions": int(self.calibration_sessions),
            "evaluation_states_per_arm": self.evaluation_states,
            "calibration_states": self.calibration_states,
        }


def partition_sample_sizes(
    design: Sequence[int],
    *,
    maximum: int = MAX_STATE_COUNT,
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """Split a design range into ``(simulatable, declared-but-unsimulatable)``.

    The reference protocol bounds a signature at ``maximum`` states, so an
    *evaluation* cannot be run at a larger sample size. A *threshold* still can
    be derived at any size, because it is a binomial quantile of the calibrated
    null rather than a simulated quantity. Separating the two keeps the declared
    design range intact while refusing to pretend a run happened.
    """
    reachable = tuple(int(size) for size in design if 1 <= int(size) <= maximum)
    unreachable = tuple(int(size) for size in design if int(size) > maximum)
    return reachable, unreachable


def sample_size_plan(
    state_counts: Sequence[int],
    *,
    calibration_budget: int,
    fixed_trials: int,
    min_calibration_sessions: int,
    max_calibration_sessions: int,
) -> Tuple[SampleSizePlan, ...]:
    """Derive a :class:`SampleSizePlan` for each sample size.

    ``fixed_trials`` is deliberately the *same* at every sample size. Varying it
    would confound the two things the study is trying to separate: a detection
    rate measured on 6 trials at ``N=100`` and on 4 trials at ``N=10000`` differs
    for two reasons at once, and no reader could tell which was responsible.

    Calibration sessions are derived from a budget instead, because the interval
    depends on the total number of observations rather than on the number of
    sessions, so a large ``N`` needs fewer sessions for the same precision.

    Raises
    ------
    ValueError
        If a sample size is outside the reference protocol's supported range.
        The error names the bound and points at :func:`partition_sample_sizes`,
        because the fix is to separate the design range from the simulatable
        range rather than to raise a protocol constant.
    """
    sizes = tuple(int(state_count) for state_count in state_counts)
    for state_count in sizes:
        if not 1 <= state_count <= MAX_STATE_COUNT:
            raise ValueError(
                f"sample size {state_count} is outside the reference protocol's "
                f"supported range [1, {MAX_STATE_COUNT}]. Use "
                f"partition_sample_sizes() to split the declared design range "
                f"into the sizes that can be simulated and the sizes that can "
                f"only have their threshold derived."
            )

    def _sessions(budget: int, low: int, high: int, state_count: int) -> int:
        return max(low, min(high, budget // state_count))

    return tuple(
        SampleSizePlan(
            state_count=state_count,
            trials=int(fixed_trials),
            calibration_sessions=_sessions(
                calibration_budget,
                min_calibration_sessions,
                max_calibration_sessions,
                state_count,
            ),
        )
        for state_count in sizes
    )


@dataclass(frozen=True)
class BenchmarkProfile:
    """The declared scale of a benchmark run.

    Every field is a design value. None of them is a threshold, and none of them
    is read by the detector: they say how much to measure, not what to conclude.

    ``measurement_mode`` and ``shot_count`` are here because they decide whether
    the honest null is *graded* or *degenerate*, which the benchmark must state
    rather than leave implicit:

    * ``"projective-analytic"`` is a deterministic exactness test. ``matched``
      means the received qubit *is* the expected eigenstate, so any nonzero
      channel disturbance makes every state mismatch and the mismatch rate jumps
      from 0 to 1. There is no interior for a finite-sample null to describe.
    * ``"sampled"`` with ``shot_count`` large is the opposite failure: the
      majority vote over many shots of a single qubit swamps small disturbance,
      so the mismatch rate sits at 0.
    * ``"sampled"`` with ``shot_count=1`` is one measurement per state, which is
      also what a verifier physically performs on one qubit. The mismatch
      probability is then ``1 - p_match``, giving a genuine interior null.

    The reference profile therefore uses the last of these, and the reason is
    recorded in the report.
    """

    name: str
    description: str
    state_count: int
    calibration_sessions: int
    evaluation_trials: int
    measurement_mode: str
    shot_count: int
    reference_noise_strength: float
    attack_types: Tuple[str, ...]
    attack_fraction: float
    attack_fractions: Tuple[float, ...]
    noise_type: str
    noise_strengths: Tuple[float, ...]
    sample_size_design: Tuple[int, ...]
    sample_size_plan: Tuple[SampleSizePlan, ...]
    sample_size_calibration_sessions: int
    robustness_levels: Tuple[Tuple[str, float], ...]
    robustness_trials: int
    robustness_attack_fraction: float
    discrimination_trials: int
    discrimination_noise_strengths: Tuple[float, ...]
    discrimination_attack_fractions: Tuple[float, ...]
    seed_base: int = 0
    notes: Tuple[str, ...] = ()

    @property
    def sample_size_simulated(self) -> Tuple[int, ...]:
        """Return the sample sizes the study will actually run."""
        return tuple(plan.state_count for plan in self.sample_size_plan)

    @property
    def sample_size_unreachable(self) -> Tuple[int, ...]:
        """Return declared design sizes the reference protocol cannot simulate."""
        return partition_sample_sizes(self.sample_size_design)[1]

    @property
    def total_planned_states(self) -> int:
        """Return a lower bound on the states the run will simulate."""
        fixed = self.calibration_sessions * self.state_count
        fixed += self.evaluation_trials * self.state_count * (
            len(self.attack_types) + len(self.attack_fractions) + len(self.noise_strengths) + 2
        )
        fixed += self.robustness_trials * self.state_count * (
            len(self.robustness_levels) * 3
        )
        fixed += self.discrimination_trials * self.state_count * (
            len(self.discrimination_noise_strengths)
            + 2 * len(self.discrimination_attack_fractions)
        )
        study = sum(
            plan.calibration_states + 2 * plan.evaluation_states
            for plan in self.sample_size_plan
        )
        return fixed + study

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "state_count": int(self.state_count),
            "calibration_sessions": int(self.calibration_sessions),
            "evaluation_trials": int(self.evaluation_trials),
            "measurement_mode": self.measurement_mode,
            "shot_count": int(self.shot_count),
            "reference_noise_strength": float(self.reference_noise_strength),
            "attack_types": list(self.attack_types),
            "attack_fraction": float(self.attack_fraction),
            "attack_fractions": list(self.attack_fractions),
            "noise_type": self.noise_type,
            "noise_strengths": list(self.noise_strengths),
            "sample_size_design": list(self.sample_size_design),
            "sample_size_simulated": list(self.sample_size_simulated),
            "sample_size_unreachable": list(self.sample_size_unreachable),
            "sample_size_plan": [plan.to_dict() for plan in self.sample_size_plan],
            "robustness_levels": [list(item) for item in self.robustness_levels],
            "robustness_trials": int(self.robustness_trials),
            "robustness_attack_fraction": float(self.robustness_attack_fraction),
            "discrimination_trials": int(self.discrimination_trials),
            "discrimination_noise_strengths": list(self.discrimination_noise_strengths),
            "discrimination_attack_fractions": list(self.discrimination_attack_fractions),
            "seed_base": int(self.seed_base),
            "notes": list(self.notes),
            "total_planned_states_lower_bound": self.total_planned_states,
        }



REFERENCE_PROFILE = BenchmarkProfile(
    name="m5-reference",
    description=(
        "the recorded reference benchmark: one reference operating point, the "
        "eight reference curves, the attack evaluation, the noise grid and the "
        "discrimination experiment"
    ),
    state_count=500,
    calibration_sessions=120,
    evaluation_trials=12,
    measurement_mode="sampled",
    shot_count=1,
    reference_noise_strength=0.02,
    attack_types=(
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
        "intercept_resend",
        "channel_tampering",
    ),
    attack_fraction=0.20,
    attack_fractions=(0.0, 0.05, 0.10, 0.20, 0.50),
    noise_type="depolarizing",
    noise_strengths=(0.0, 0.005, 0.01, 0.02, 0.05, 0.10),






    sample_size_design=REFERENCE_SAMPLE_SIZE_DESIGN,
    sample_size_plan=sample_size_plan(
        partition_sample_sizes(REFERENCE_SAMPLE_SIZE_DESIGN)[0],
        calibration_budget=6000,
        fixed_trials=6,
        min_calibration_sessions=3,
        max_calibration_sessions=24,
    ),
    sample_size_calibration_sessions=0,
    robustness_levels=(
        ("none", 0.0),
        ("low", 0.005),
        ("medium", 0.02),
        ("high", 0.10),
    ),
    robustness_trials=8,
    robustness_attack_fraction=0.20,
    discrimination_trials=12,
    discrimination_noise_strengths=(0.0, 0.005, 0.01, 0.02, 0.05),
    discrimination_attack_fractions=(0.05, 0.10, 0.20, 0.50),
    notes=(
        "trial counts are derived from a declared state budget rather than "
        "hand-picked; the quantity that costs time is trials x state_count, and "
        "holding it bounded keeps the study affordable while covering every "
        "simulatable design sample size",
        "the reference channel is depolarizing at eta=0.02 with one measurement "
        "shot per state, which is the configuration in which the honest mismatch "
        "probability has a genuine interior value",
        "the two largest design sample sizes (5000 and 10000) are above the "
        "reference protocol's maximum signature length of 4096 states, so they "
        "are declared as design values and have their thresholds derived exactly "
        "from the calibrated null, but they are not simulated: the protocol "
        "bound is not widened to make a benchmark reachable",
    ),
)



SMOKE_PROFILE = BenchmarkProfile(
    name="m5-smoke",
    description="a fast profile used by the test suite; results are not reported",
    state_count=20,
    calibration_sessions=12,
    evaluation_trials=6,
    measurement_mode="sampled",
    shot_count=1,
    reference_noise_strength=0.02,
    attack_types=("channel_tampering", "intercept_resend"),
    attack_fraction=0.20,
    attack_fractions=(0.0, 0.20, 0.50),
    noise_type="depolarizing",
    noise_strengths=(0.0, 0.02, 0.10),
    sample_size_design=(20, 40),
    sample_size_plan=sample_size_plan(
        (20, 40),
        calibration_budget=160,
        fixed_trials=4,
        min_calibration_sessions=8,
        max_calibration_sessions=8,
    ),
    sample_size_calibration_sessions=0,
    robustness_levels=(("none", 0.0), ("medium", 0.02), ("high", 0.10)),
    robustness_trials=4,
    robustness_attack_fraction=0.20,
    discrimination_trials=8,
    discrimination_noise_strengths=(0.0, 0.02, 0.05),
    discrimination_attack_fractions=(0.05, 0.20, 0.50),
    notes=("smoke scale only: every number is too small to interpret",),
)


class SeedAllocator:
    """Hands out disjoint seed blocks and records what it gave to whom."""

    def __init__(self, start: int = 0, block: int = 100_000) -> None:
        self._next = int(start)
        self._block = int(block)
        self._allocated: List[Tuple[str, Tuple[int, ...]]] = []

    def take(self, label: str, count: int) -> int:
        """Reserve ``count`` consecutive seeds and return the first one."""
        if count < 1:
            raise ValueError(f"a seed block must hold at least one seed, got {count}")
        start = self._next
        size = max(int(count), self._block)
        self._next = start + size + 1
        self._allocated.append((label, tuple(range(start, start + count))))
        return start

    @property
    def allocations(self) -> Tuple[Tuple[str, Tuple[int, ...]], ...]:
        """Return everything allocated so far."""
        return tuple(self._allocated)

    def verify_disjoint(self) -> None:
        """Raise if any two allocations overlap."""
        assert_disjoint_seeds(self._allocated)


def benchmark_base_scenario(profile: BenchmarkProfile) -> ScenarioConfig:
    """Return the base scenario the benchmark varies."""
    return ScenarioConfig(
        scenario_id=f"{profile.name}-base",
        message=BENCHMARK_MESSAGE,
        signer_id="alice",
        verifier_id="bob",
        state_count=profile.state_count,
        shot_count=profile.shot_count,
        random_seed=0,
        measurement_mode=profile.measurement_mode,
    ).validate()


def _sample_size_study(
    profile: BenchmarkProfile,
    base: ScenarioConfig,
    allocator: SeedAllocator,
    *,
    progress: Any = None,
) -> Tuple[Dict[str, Any], Any]:
    """Calibrate and evaluate at every sample size, and return the rows.

    Each size gets its own calibration dataset and its own threshold, because a
    threshold derived at one sample size is not defined at another.
    """
    rows: List[Dict[str, Any]] = []
    detection_samples: List[Tuple[float, Sequence[Any]]] = []

    for plan in profile.sample_size_plan:
        state_count = plan.state_count
        trials = plan.trials
        config, observations = build_calibration_dataset(
            base,
            config_id=f"{profile.name}-ss{state_count}",
            seed_start=allocator.take(
                f"sample-size-calibration-{state_count}", plan.calibration_sessions
            ),
            session_count=plan.calibration_sessions,
            noise_type=profile.noise_type,
            noise_strength=profile.reference_noise_strength,
            state_count=state_count,
        )
        calibration = estimate_baseline(config, observations)
        point = build_reference_operating_point(calibration)

        honest = run_honest_population(
            base.with_changes(state_count=state_count),
            point,
            evaluation_id=f"{profile.name}-ss{state_count}-honest",
            seed_start=allocator.take(f"sample-size-honest-{state_count}", trials),
            trial_count=trials,
            noise_type=profile.noise_type,
            noise_strength=profile.reference_noise_strength,
            dataset_role=DatasetRole.FINAL_EVALUATION,
        )
        malicious = run_attack_population(
            base.with_changes(state_count=state_count),
            point,
            evaluation_id=f"{profile.name}-ss{state_count}-attack",
            seed_start=allocator.take(f"sample-size-attack-{state_count}", trials),
            trial_count=trials,
            attack_type="channel_tampering",
            fraction=profile.attack_fraction,
            noise_type=profile.noise_type,
            noise_strength=profile.reference_noise_strength,
            dataset_role=DatasetRole.FINAL_EVALUATION,
        )

        honest_metrics = metrics(honest)
        attack_metrics = metrics(malicious)
        rows.append(
            {
                "state_count": int(state_count),
                "trials": int(trials),
                "critical_count": int(point.threshold.critical_count),
                "threshold_rate": point.threshold.threshold_rate,
                "p_upper": point.threshold.p_upper,
                "honest_frr": honest_metrics.frr,
                "detection_rate": attack_metrics.detection_rate,
                "far": attack_metrics.far,
                "calibration_sessions": plan.calibration_sessions,
                "calibration_states": plan.calibration_states,
                "evaluation_states_per_arm": plan.evaluation_states,
            }
        )
        detection_samples.append((float(state_count), malicious))
        if progress is not None:
            progress(f"sample-size N={state_count} done")

    curve = build_curve(
        CURVE_DETECTION_VS_SAMPLE_SIZE,
        "sample size (usable observations)",
        "detection probability",
        tuple(
            CurvePoint(
                x=x,
                y=float(metrics(population).detection_rate or 0.0),
                trials=len(population),
                x_label="sample size",
            )
            for x, population in detection_samples
        ),
        conditions={"attack_type": "channel_tampering", "noise_strength": profile.reference_noise_strength},
        notes=(
            "each sample size has its own threshold, derived from its own "
            "calibration dataset; no threshold is reused across sizes",
            "trial counts differ between sizes, so a point at a large N rests on "
            "fewer trials than a point at a small N",
        ),
    )
    payload = {
        "rows": rows,
        "note": (
            "each row's threshold is derived for that row's sample size only; "
            "the critical count is not comparable across rows as a rate without "
            "dividing by N"
        ),
        "plan": [plan.to_dict() for plan in profile.sample_size_plan],
        "declared_design": [int(size) for size in profile.sample_size_design],
        "simulated_design": [int(size) for size in profile.sample_size_simulated],
        "unsimulated_design": [int(size) for size in profile.sample_size_unreachable],
        "unsimulated_reason": (
            "these design sizes exceed the reference protocol's maximum "
            f"signature length of {MAX_STATE_COUNT} states, so an evaluation "
            "cannot be run at them. Their thresholds are derived exactly in "
            "'exact_threshold_table' below, because a threshold is a binomial "
            "quantile of the calibrated null and needs no simulation; the "
            "protocol bound is deliberately not widened to make a run reachable"
        ),
        "budget_note": (
            "trials and calibration sessions are derived from a declared state "
            "budget, so the trial count falls as the sample size rises; the "
            "simulated sample sizes are the simulatable subset of the declared "
            "design range"
        ),
    }
    return payload, curve


def attack_fraction_for(attack_type: str, fraction: float) -> float:
    """Return the intensity to pass to ``attack_type``.

    Only some attacks act on a subset of the signature states; the rest are
    whole-session attacks for which a fraction means nothing. The attack layer
    *rejects* a non-zero fraction on those rather than silently ignoring it, so
    that an operator cannot believe they configured something that is not
    implemented. The benchmark therefore has to pass ``0.0`` to them instead of
    a single global intensity that only makes sense for the fractional ones.
    """
    return float(fraction) if attack_type in FRACTIONAL_ATTACK_TYPES else 0.0


def _run_benchmark_impl(
    profile: BenchmarkProfile,
    *,
    base: ScenarioConfig | None = None,
    progress: Any = None,
) -> Mapping[str, Any]:
    """Run the benchmark and return ``(report, markdown)``-ready results.

    The return value is a mapping with ``report`` (the JSON-ready payload) and
    ``markdown`` (the rendered summary).
    """
    started = time.perf_counter()
    scenario = base if base is not None else benchmark_base_scenario(profile)
    allocator = SeedAllocator(start=profile.seed_base)

    def say(message: str) -> None:
        if progress is not None:
            progress(message)


    say("calibration")
    config, observations = build_calibration_dataset(
        scenario,
        config_id=f"{profile.name}-calibration",
        seed_start=allocator.take("calibration", profile.calibration_sessions),
        session_count=profile.calibration_sessions,
        noise_type=profile.noise_type,
        noise_strength=profile.reference_noise_strength,
    )
    calibration = estimate_baseline(config, observations)


    point = build_reference_operating_point(calibration)
    say(f"operating point: critical count {point.threshold.critical_count}")


    say("sample-size study")
    sample_size_payload, sample_size_curve = _sample_size_study(
        profile, scenario, allocator, progress=progress
    )






    exact_table = [
        {
            "state_count": threshold.state_count,
            "critical_count": threshold.critical_count,
            "threshold_rate": threshold.threshold_rate,
            "p_upper": threshold.p_upper,
            "expected_frr": expected_false_rejection_rate(
                threshold.p_upper, threshold.state_count, threshold.critical_count
            ),
            "simulated": threshold.state_count in set(profile.sample_size_simulated),
        }
        for threshold in derive_threshold_table(
            calibration, profile.sample_size_design
        )
    ]
    sample_size_payload["exact_threshold_table"] = exact_table
    sample_size_payload["exact_threshold_table_note"] = (
        "every row is derived exactly from the single reference calibration by "
        "the reference threshold method; 'simulated' says whether an evaluation "
        "was also run at that size. This is the answer to 'a threshold at N=100 "
        "is not valid at N=10,000': each row is that size's own threshold, and "
        "none of them is reused at another size"
    )


    say("attack evaluation")
    attack_metrics: Dict[str, Any] = {}
    attack_fractions: Dict[str, float] = {}
    for attack_type in profile.attack_types:
        intensity = attack_fraction_for(attack_type, profile.attack_fraction)
        records = run_attack_population(
            scenario,
            point,
            evaluation_id=f"{profile.name}-attack-{attack_type}",
            seed_start=allocator.take(f"attack-{attack_type}", profile.evaluation_trials),
            trial_count=profile.evaluation_trials,
            attack_type=attack_type,
            fraction=intensity,
            noise_type=profile.noise_type,
            noise_strength=profile.reference_noise_strength,
            dataset_role=DatasetRole.FINAL_EVALUATION,
        )
        attack_metrics[attack_type] = metrics(records)
        attack_fractions[attack_type] = intensity
        say(f"attack {attack_type} done")


    say("curves")
    primary_attack = "channel_tampering"

    attack_intensity_samples = []
    fidelity_samples = []
    for fraction in profile.attack_fractions:
        records = run_attack_population(
            scenario,
            point,
            evaluation_id=f"{profile.name}-intensity-{fraction:g}",
            seed_start=allocator.take(f"intensity-{fraction:g}", profile.evaluation_trials),
            trial_count=profile.evaluation_trials,
            attack_type=primary_attack,
            fraction=fraction,
            noise_type=profile.noise_type,
            noise_strength=profile.reference_noise_strength,
            dataset_role=DatasetRole.FINAL_EVALUATION,
        )
        attack_intensity_samples.append((fraction, records))
        fidelity_samples.append((fraction, records))
        say(f"intensity {fraction:g} done")

    honest_noise_samples = []
    mismatch_noise_samples = []
    for strength in profile.noise_strengths:
        records = run_honest_population(
            scenario,
            point,
            evaluation_id=f"{profile.name}-noise-{strength:g}",
            seed_start=allocator.take(f"noise-{strength:g}", profile.evaluation_trials),
            trial_count=profile.evaluation_trials,
            noise_type=profile.noise_type,
            noise_strength=strength,
            dataset_role=DatasetRole.FINAL_EVALUATION,
        )
        honest_noise_samples.append((strength, records))
        mismatch_noise_samples.append((strength, records))
        say(f"noise {strength:g} done")



    honest_reference = run_honest_population(
        scenario,
        point,
        evaluation_id=f"{profile.name}-reference-honest",
        seed_start=allocator.take("reference-honest", profile.evaluation_trials),
        trial_count=profile.evaluation_trials,
        noise_type=profile.noise_type,
        noise_strength=profile.reference_noise_strength,
        dataset_role=DatasetRole.FINAL_EVALUATION,
    )
    malicious_reference = run_attack_population(
        scenario,
        point,
        evaluation_id=f"{profile.name}-reference-attack",
        seed_start=allocator.take("reference-attack", profile.evaluation_trials),
        trial_count=profile.evaluation_trials,
        attack_type=primary_attack,
        fraction=attack_fraction_for(primary_attack, profile.attack_fraction),
        noise_type=profile.noise_type,
        noise_strength=profile.reference_noise_strength,
        dataset_role=DatasetRole.FINAL_EVALUATION,
    )
    far_curve, frr_operating_curve = threshold_tradeoff_curves(
        honest_reference,
        malicious_reference,
        state_count=point.threshold.state_count,
        critical_counts=range(0, point.threshold.critical_count + 4),
        conditions={
            "attack_type": primary_attack,
            "attack_fraction": attack_fraction_for(primary_attack, profile.attack_fraction),
            "reference_critical_count": point.threshold.critical_count,
        },
        notes=(
            "the reference operating point sits at "
            f"critical count {point.threshold.critical_count}",
        ),
    )

    calibration_curve = build_curve(
        CURVE_CALIBRATION_DISTRIBUTION,
        "per-session mismatch rate",
        "empirical cumulative probability",
        empirical_cdf(
            [
                record.mismatch_rate
                for record in calibration.observations
                if record.mismatch_rate is not None
            ],
            label="per-session mismatch rate",
        ),
        conditions={
            "sessions": calibration.session_count,
            "state_count": config.state_count,
            "pooled_rate": calibration.pooled_rate,
            "p_upper": calibration.upper_bound.upper if calibration.upper_bound else None,
        },
        notes=(
            "this is the honest null as measured, not as assumed; it is an ECDF "
            "rather than a histogram so that no bin width is chosen after seeing "
            "the data",
        ),
    )

    curves = {
        CURVE_DETECTION_VS_ATTACK: detection_vs_attack_curve(
            attack_intensity_samples, attack_type=primary_attack
        ),
        CURVE_FRR_VS_NOISE: frr_vs_noise_curve(
            honest_noise_samples, noise_type=profile.noise_type
        ),
        "far_vs_threshold": far_curve,
        CURVE_DETECTION_VS_SAMPLE_SIZE: sample_size_curve,
        CURVE_FIDELITY_VS_ATTACK: fidelity_vs_attack_curve(
            fidelity_samples, attack_type=primary_attack
        ),
        CURVE_MISMATCH_VS_NOISE: mismatch_vs_noise_curve(
            mismatch_noise_samples, noise_type=profile.noise_type
        ),
        CURVE_CALIBRATION_DISTRIBUTION: calibration_curve,
        "threshold_operating_curve": frr_operating_curve,
    }


    say("robustness")
    robustness = evaluate_robustness(
        scenario,
        point,
        evaluation_id=profile.name,
        seed_start=allocator.take("robustness", 1),
        trial_count=profile.robustness_trials,
        levels=profile.robustness_levels,
        attack_fraction=profile.robustness_attack_fraction,
        noise_type=profile.noise_type,
        dataset_role=DatasetRole.FINAL_EVALUATION,
    )


    say("discrimination experiment")
    discrimination = discrimination_experiment(
        scenario,
        point,
        evaluation_id=profile.name,
        seed_start=allocator.take("discrimination", 1),
        trial_count=profile.discrimination_trials,
        noise_type=profile.noise_type,
        noise_strengths=profile.discrimination_noise_strengths,
        attack_types=(primary_attack, "intercept_resend"),
        attack_fractions=profile.discrimination_attack_fractions,
    )

    allocator.verify_disjoint()


    elapsed = time.perf_counter() - started
    provenance = {
        "profile": profile.name,
        "profile_description": profile.description,
        "profile_notes": list(profile.notes),
        "profile_parameters": profile.to_dict(),
        "protocol_version": PROTOCOL_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "scenario_count": sum(len(seeds) for _, seeds in allocator.allocations),
        "seed_blocks": [
            {"label": label, "first_seed": seeds[0], "count": len(seeds)}
            for label, seeds in allocator.allocations
        ],
        "runtime_seconds": elapsed,
        "runtime_note": (
            "measured with time.perf_counter around the whole run; no runtime "
            "figure in this project is estimated"
        ),
    }

    payload = build_report(
        operating_point=point,
        calibration={
            "config": config.to_dict(),
            "pooled_rate": calibration.pooled_rate,
            "interval": calibration.interval.to_dict() if calibration.interval else None,
            "upper_bound": (
                calibration.upper_bound.to_dict() if calibration.upper_bound else None
            ),
            "homogeneity": calibration.homogeneity.to_dict(),
            "session_count": calibration.session_count,
            "total_valid": calibration.total_valid,
            "total_mismatch": calibration.total_mismatch,
            "notes": list(calibration.notes),
        },
        curves=curves,
        attack_metrics=attack_metrics,
        robustness=robustness,
        discrimination=discrimination,
        sample_size=sample_size_payload,
        attack_fractions=attack_fractions,
        provenance=provenance,
        extra={
            "reference_operating_point_name": REFERENCE_OPERATING_POINT_NAME,
            "profiles_available": ["m5-reference", "m5-smoke"],
            "measurement_configuration": {
                "measurement_mode": profile.measurement_mode,
                "shot_count": int(profile.shot_count),
                "reference_noise": {
                    "noise_type": profile.noise_type,
                    "noise_strength": float(profile.reference_noise_strength),
                },
                "why": (
                    "the measurement mode decides whether the honest null is "
                    "graded or degenerate, and the choice is therefore stated "
                    "rather than left implicit. In 'projective-analytic' mode "
                    "'matched' means the received qubit is exactly the expected "
                    "eigenstate, so any nonzero channel disturbance makes every "
                    "state mismatch and the honest mismatch rate jumps from 0 to "
                    "1 with no interior for a finite-sample null. In 'sampled' "
                    "mode with a large shot count the majority vote over many "
                    "shots of a single qubit swamps small disturbance and the "
                    "rate sits at 0 instead. 'sampled' mode with one shot per "
                    "state is one measurement per qubit, which is what a "
                    "verifier physically performs, and it gives a mismatch "
                    "probability of 1 - p_match: a genuine interior null. This "
                    "was established by measurement, not assumption; the three "
                    "configurations were run over a noise sweep and their "
                    "mismatch rates compared."
                ),
            },
        },
    )
    return {"report": payload, "markdown": render_markdown(payload)}


def run_benchmark(
    profile: BenchmarkProfile = REFERENCE_PROFILE,
    *,
    base: ScenarioConfig | None = None,
    progress: Any = None,
    use_transpile_cache: bool = True,
) -> Mapping[str, Any]:
    """Run the benchmark, optionally with the explicit transpile cache enabled.

    The transpile cache is off by default everywhere else in the project. The
    benchmark enables it for its own duration because a benchmark that would take
    hours is a benchmark nobody re-runs, and re-running it is the only thing that
    makes its numbers trustworthy.

    The cache stores compiled circuits, never outcomes, and it is proven
    result-preserving by ``tests/quantum/test_cache.py``, which runs the same
    scenarios with the cache off and on and compares the observable evidence
    field by field. Whether it was used is recorded in the report's provenance,
    so a reader is never left to assume.
    """
    from backend.quantum.cache import DEFAULT_MAX_ENTRIES, cache_stats, clear, enabled

    if not use_transpile_cache:
        return _run_benchmark_impl(profile, base=base, progress=progress)

    clear()
    with enabled(max_entries=DEFAULT_MAX_ENTRIES):
        result = _run_benchmark_impl(profile, base=base, progress=progress)
        stats = cache_stats().to_dict()

    provenance = result["report"].get("provenance", {})
    provenance["transpile_cache"] = {
        "enabled_during_run": True,
        "max_entries": DEFAULT_MAX_ENTRIES,
        "stats": stats,
        "note": (
            "the cache stores compiled circuits keyed by a canonical circuit "
            "digest; it never stores outcomes. It is off by default and is "
            "proven result-preserving by tests/quantum/test_cache.py. The cache "
            "is disabled again once the run finishes, so enabled=False here "
            "would be wrong to read as 'the cache was not used'."
        ),
    }
    result["report"]["provenance"] = provenance
    result["markdown"] = render_markdown(result["report"])
    return result


def benchmark_report(
    profile: BenchmarkProfile = REFERENCE_PROFILE,
    *,
    base: ScenarioConfig | None = None,
    progress: Any = None,
) -> Tuple[Mapping[str, Any], str]:
    """Run the benchmark and return ``(payload, markdown)``."""
    result = run_benchmark(profile, base=base, progress=progress)
    return result["report"], result["markdown"]
