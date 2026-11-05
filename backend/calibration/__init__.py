"""Statistical calibration (Milestone 5).

This package turns Milestone 4's observable statistics into a **decision rule**
with a stated error budget: it estimates what an honest session looks like,
derives a threshold from that estimate, and records everything needed to
reproduce the threshold.

The isolation rule
------------------
``backend.calibration`` must never import :mod:`backend.attacks` or
:mod:`backend.simulation`, and must never read a ground-truth object. It
consumes :class:`~backend.calibration.models.CalibrationObservation` records,
which have no field that could carry an attack type, an attack fraction, a
noise label or a ground-truth flag. The test suite enforces this structurally
rather than by convention.

Module map
----------
``models``            the typed records, and the terminology they fix
``confidence``        exact binomial intervals and one-sided bounds
``baseline``          the honest null model and baseline estimation
``thresholds``        the one reference threshold methodology
``operating_points``  the single reference operating point
``multiple_testing``  the multiple-comparison policy

The four quantities that must not be confused
---------------------------------------------
============================  ==========================================
confidence interval           a statement about a parameter
classification threshold      a decision rule
empirical acceptance rate     a measurement, made by the evaluation layer
cryptographic security bound  a formal bound; **not produced here**
============================  ==========================================

Dependency direction::

    backend.quantum -> backend.protocol -> backend.noise -> backend.attacks
                                                                  |
                                                                  v
                                            backend.simulation (observable half)
                                                                  |
                                                                  v
                                                          backend.detection
                                                                  |
                                                                  v
                                                        backend.calibration
                                                                  |
                                                                  v
                                                        backend.evaluation
"""

from backend.calibration.baseline import (
    DEFAULT_PROJECTIVE_TOLERANCE,
    HOMOGENEITY_TOLERANCE,
    build_homogeneity_diagnostic,
    estimate_baseline,
    implied_mismatch_probability,
)
from backend.calibration.confidence import (
    CLOPPER_PEARSON_ONE_SIDED,
    CLOPPER_PEARSON_TWO_SIDED,
    lower_bound,
    two_sided_interval,
    upper_bound,
)
from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    SUPPORTED_STATISTICS,
    CalibrationConfig,
    CalibrationObservation,
    CalibrationResult,
    ConfidenceInterval,
    DatasetRole,
    HomogeneityDiagnostic,
    OperatingPoint,
    ThresholdConfig,
    ThresholdResult,
    VerificationDecision,
)
from backend.calibration.multiple_testing import (
    DIAGNOSTIC_METRICS,
    REFERENCE_PRIMARY_TEST,
    MultipleComparisonPolicy,
    MultipleTestingPolicy,
    bonferroni_alpha,
    describe_diagnostics,
    family_wise_error_rate,
    holm_bonferroni,
    reference_policy,
    reject_multiple_primary_tests,
)
from backend.calibration.operating_points import (
    REFERENCE_ALPHA,
    REFERENCE_OPERATING_POINT_NAME,
    REFERENCE_THRESHOLD_CONFIG,
    build_operating_point,
    build_reference_operating_point,
    describe_operating_point,
    evaluate_operating_point,
    observed_rejection_rate,
)
from backend.calibration.thresholds import (
    REFERENCE_THRESHOLD_METHOD,
    critical_count,
    derive_threshold,
    derive_threshold_table,
    expected_false_rejection_rate,
    rejection_probability,
)

__all__ = [

    "STATISTIC_MISMATCH_RATE",
    "SUPPORTED_STATISTICS",
    "DatasetRole",
    "ConfidenceInterval",
    "HomogeneityDiagnostic",
    "CalibrationConfig",
    "CalibrationObservation",
    "CalibrationResult",
    "ThresholdConfig",
    "ThresholdResult",
    "VerificationDecision",
    "OperatingPoint",

    "CLOPPER_PEARSON_ONE_SIDED",
    "CLOPPER_PEARSON_TWO_SIDED",
    "two_sided_interval",
    "upper_bound",
    "lower_bound",

    "DEFAULT_PROJECTIVE_TOLERANCE",
    "HOMOGENEITY_TOLERANCE",
    "implied_mismatch_probability",
    "build_homogeneity_diagnostic",
    "estimate_baseline",

    "REFERENCE_THRESHOLD_METHOD",
    "critical_count",
    "derive_threshold",
    "derive_threshold_table",
    "rejection_probability",
    "expected_false_rejection_rate",

    "REFERENCE_ALPHA",
    "REFERENCE_OPERATING_POINT_NAME",
    "REFERENCE_THRESHOLD_CONFIG",
    "build_operating_point",
    "build_reference_operating_point",
    "describe_operating_point",
    "evaluate_operating_point",
    "observed_rejection_rate",

    "MultipleTestingPolicy",
    "MultipleComparisonPolicy",
    "DIAGNOSTIC_METRICS",
    "REFERENCE_PRIMARY_TEST",
    "reference_policy",
    "family_wise_error_rate",
    "bonferroni_alpha",
    "holm_bonferroni",
    "reject_multiple_primary_tests",
    "describe_diagnostics",
]
