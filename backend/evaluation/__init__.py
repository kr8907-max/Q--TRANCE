"""Evaluation: what the calibrated rule actually does, on labelled data.

Where this package sits
-----------------------
::

    backend.simulation (observable half)  ->  backend.detection
                                                     |
                                                     v
                                            backend.calibration   (honest only)
                                                     |
                                                     v
                                            backend.evaluation    (ground truth)

The calibration package may not import :mod:`backend.simulation` or
:mod:`backend.attacks`; the evaluation package may, because evaluating a
detector against known attacks is the entire point of the layer. The boundary is
enforced structurally and checked by the test suite.

The two-layer decision
----------------------
**Layer A -- verification decision.** The single calibrated test on ``D_m``,
produced by :meth:`~backend.calibration.models.OperatingPoint.decide` from
observable statistics alone. It never sees a label.

**Layer B -- security evaluation.** This package. It compares Layer A's answers
against ground truth and reports FAR, FRR and the rest. Ground truth appears
here and nowhere upstream.

The central experiment
----------------------
:mod:`backend.evaluation.discrimination` compares honest noise with a malicious
channel attack **at comparable marginal mismatch rates** and reports honestly
whether the observable evidence can tell them apart. When it cannot, the verdict
is the literal string ``"Not distinguishable under the current observable
model."`` -- a real result, not a failure to be hidden.

Module map
----------
``models``          the typed records, and the confusion-matrix convention
``harness``         runs scenarios and applies the operating point
``datasets``        calibration/validation/evaluation dataset construction
``confusion``       counts of TP/TN/FP/FN
``metrics``         FAR, FRR, detection rate and the descriptive extras
``curves``          curve construction from measured points
``sweeps``          noise and attack sweeps, and the curve builders over them
``robustness``      the honest-noise and noise-plus-attack grid
``discrimination``  the central experiment
``reports``         JSON and Markdown report assembly
``benchmark``       the reference benchmark driver

No machine learning is used anywhere in this package, and no threshold is
learned: the only decision rule in the project is the calibrated one in
:mod:`backend.calibration`.
"""

from backend.evaluation.benchmark import (
    REFERENCE_PROFILE,
    SMOKE_PROFILE,
    BenchmarkProfile,
    SeedAllocator,
    benchmark_base_scenario,
    benchmark_report,
    run_benchmark,
)
from backend.evaluation.confusion import (
    HONEST_ATTACK_TYPE,
    confusion_by,
    confusion_by_attack_type,
    confusion_by_noise,
    confusion_matrix,
    outcome_counts,
    partition_by_attack_type,
    partition_by_noise,
    partition_honest_malicious,
)
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
from backend.evaluation.datasets import (
    DEFAULT_CALIBRATION_CONFIDENCE,
    SEED_BLOCK_SIZE,
    assert_disjoint_seeds,
    build_calibration_dataset,
    honest_observation,
)
from backend.evaluation.discrimination import (
    DEFAULT_DESCRIPTOR,
    DESCRIPTORS,
    NOT_DISTINGUISHABLE_VERDICT,
    MatchPair,
    compare_populations,
    descriptor_values,
    discrimination_experiment,
    match_marginals,
)
from backend.evaluation.harness import (
    build_trial_record,
    decide_observable,
    deterministic_session_identifiers,
    observable_statistics,
    run_trial,
    run_trials,
    scenario_for_trial,
    state_evidence,
)
from backend.evaluation.metrics import (
    DESCRIPTIVE_METRICS,
    FAR_DEFINITION,
    FRR_DEFINITION,
    describe_metrics,
    detection_rate,
    false_acceptance_rate,
    false_rejection_rate,
    metrics,
    metrics_by_attack_type,
    metrics_by_noise,
    metrics_from_matrix,
    summarise_population,
)
from backend.evaluation.models import (
    ConfusionMatrix,
    CurvePoint,
    CurveResult,
    DiscriminationResult,
    EvaluationConfig,
    EvaluationMetrics,
    ObservableStatistics,
    PopulationSummary,
    RobustnessResult,
    TrialOutcome,
    TrialRecord,
)
from backend.evaluation.reports import (
    LIMITATIONS,
    QUANTITY_DISTINCTIONS,
    attack_report,
    build_report,
    curve_report,
    discrimination_report,
    render_markdown,
    robustness_report,
    write_json,
    write_markdown,
)
from backend.evaluation.robustness import (
    REFERENCE_ROBUSTNESS_ATTACKS,
    ROBUSTNESS_NOISE_LEVELS,
    build_robustness_result,
    evaluate_robustness,
    honest_robustness_populations,
    noise_attack_populations,
)
from backend.evaluation.sweeps import (
    attack_config,
    detection_vs_attack_curve,
    fidelity_vs_attack_curve,
    frr_vs_noise_curve,
    mismatch_vs_noise_curve,
    noise_config,
    population_curve,
    population_mean,
    reference_attack_fraction_sweep,
    reference_noise_sweep,
    run_attack_population,
    run_honest_population,
    run_population,
    threshold_tradeoff_curves,
    with_attack,
    with_noise,
)

__all__ = [

    "TrialOutcome",
    "ObservableStatistics",
    "TrialRecord",
    "EvaluationConfig",
    "ConfusionMatrix",
    "EvaluationMetrics",
    "CurvePoint",
    "CurveResult",
    "RobustnessResult",
    "PopulationSummary",
    "DiscriminationResult",

    "state_evidence",
    "observable_statistics",
    "decide_observable",
    "deterministic_session_identifiers",
    "scenario_for_trial",
    "run_trial",
    "run_trials",
    "build_trial_record",

    "DEFAULT_CALIBRATION_CONFIDENCE",
    "SEED_BLOCK_SIZE",
    "honest_observation",
    "build_calibration_dataset",
    "assert_disjoint_seeds",

    "HONEST_ATTACK_TYPE",
    "confusion_matrix",
    "confusion_by",
    "confusion_by_attack_type",
    "confusion_by_noise",
    "partition_by_attack_type",
    "partition_by_noise",
    "partition_honest_malicious",
    "outcome_counts",

    "FAR_DEFINITION",
    "FRR_DEFINITION",
    "DESCRIPTIVE_METRICS",
    "metrics_from_matrix",
    "metrics",
    "detection_rate",
    "false_acceptance_rate",
    "false_rejection_rate",
    "metrics_by_attack_type",
    "metrics_by_noise",
    "summarise_population",
    "describe_metrics",

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

    "attack_config",
    "noise_config",
    "with_noise",
    "with_attack",
    "run_population",
    "run_honest_population",
    "run_attack_population",
    "population_curve",
    "population_mean",
    "detection_vs_attack_curve",
    "frr_vs_noise_curve",
    "mismatch_vs_noise_curve",
    "fidelity_vs_attack_curve",
    "threshold_tradeoff_curves",
    "reference_noise_sweep",
    "reference_attack_fraction_sweep",

    "ROBUSTNESS_NOISE_LEVELS",
    "REFERENCE_ROBUSTNESS_ATTACKS",
    "honest_robustness_populations",
    "noise_attack_populations",
    "build_robustness_result",
    "evaluate_robustness",

    "DEFAULT_DESCRIPTOR",
    "NOT_DISTINGUISHABLE_VERDICT",
    "DESCRIPTORS",
    "descriptor_values",
    "MatchPair",
    "match_marginals",
    "compare_populations",
    "discrimination_experiment",

    "LIMITATIONS",
    "QUANTITY_DISTINCTIONS",
    "build_report",
    "curve_report",
    "attack_report",
    "robustness_report",
    "discrimination_report",
    "render_markdown",
    "write_json",
    "write_markdown",

    "BenchmarkProfile",
    "REFERENCE_PROFILE",
    "SMOKE_PROFILE",
    "SeedAllocator",
    "benchmark_base_scenario",
    "run_benchmark",
    "benchmark_report",
]
