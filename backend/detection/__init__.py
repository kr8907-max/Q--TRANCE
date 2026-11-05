"""Observable threat detection engine (Milestone 4).

This package converts observable experiment and protocol evidence into
normalized security measurements, threat-specific evidence, explainable findings
and one structured decision result.

The isolation rule
------------------
``backend.detection`` must never import :mod:`backend.attacks`, must never read
``GroundTruthMetadata``, and must never look at an attack label. It may consume
only observable measurement data, transcript/session information a legitimate
verifier can see, verifier results, authorization context, channel/measurement
observations and its own configured parameters.

The detector asks *"what evidence is observable?"*, never *"what attack was
injected?"*.

Module map
----------
``models``       the observable input contract and shared models
``statistics``   exact binomial intervals for sampled rates
``mismatch``     D_m = N_mismatch / N_valid
``disturbance``  D_v = N_disturbed / N_verification_states
``fidelity``     F = <psi|rho|psi>, and its redundancy with p_match
``consistency``  transcript and session integrity, recomputed
``authorization``signer and verifier authorization, kept separate
``replay``       the session/nonce/transcript reuse ledger
``features``     the documented observable feature set
``evidence``     the structured ThreatEvidence model
``decision``     the structured DetectionResult model
``engine``       the pipeline that wires them together

What this milestone deliberately does not do
--------------------------------------------
No threshold calibration, no ROC/PR analysis, no FAR/FRR evaluation, no
hypothesis tests, no multiple-comparison handling, no machine learning and no
security score. Those belong to Milestone 5, and
:meth:`~backend.detection.decision.DetectionResult.diagnostic_statistics` is the
interface prepared for them.

Dependency direction
--------------------
::

    quantum -> protocol -> noise / attacks -> observable experiment data
                                                    |
                                                    v
                                               detection
                                                    |
                                                    v
                                    future calibration / security analysis

Detection sits *below* calibration and *beside* nothing: it must not depend on
attacks in either direction.
"""

from backend.detection.authorization import (
    AuthorizationCheck,
    AuthorizationReport,
    analyse_authorization,
)
from backend.detection.consistency import ConsistencyReport, analyse_consistency
from backend.detection.decision import DetectionResult, decide
from backend.detection.disturbance import (
    DisturbanceAnalysis,
    analyse_disturbance,
    is_disturbed,
)
from backend.detection.engine import ThreatDetectionEngine, detect
from backend.detection.evidence import (
    BLOCKING_CATEGORIES,
    DETERMINISTIC_SEVERITY,
    EvidenceItem,
    ThreatEvidence,
    assign_finding_ids,
    statistical_severity,
)
from backend.detection.features import (
    FEATURE_CATALOG,
    BasisStatistics,
    DetectionFeatures,
    FeatureDescriptor,
    analyse_basis_statistics,
    extract_features,
)
from backend.detection.fidelity import FidelityAnalysis, analyse_fidelity
from backend.detection.mismatch import MismatchAnalysis, analyse_mismatch
from backend.detection.models import (
    DEFAULT_MEASUREMENT_TOLERANCE,
    DEFAULT_PROTOCOL_VERSIONS,
    CalibrationState,
    DetectionError,
    DetectionInputError,
    DetectorParameters,
    EvidenceCategory,
    ObservableDetectionInput,
    OverallStatus,
    Severity,
    StateEvidence,
    VerificationEvidence,
)
from backend.detection.replay import ReplayEvidence, ReplayRegistry
from backend.detection.statistics import (
    DEFAULT_CONFIDENCE,
    RateEstimate,
    estimate_rate,
    exact_binomial_interval,
)

__all__ = [

    "DEFAULT_MEASUREMENT_TOLERANCE",
    "DEFAULT_PROTOCOL_VERSIONS",
    "CalibrationState",
    "DetectionError",
    "DetectionInputError",
    "DetectorParameters",
    "EvidenceCategory",
    "ObservableDetectionInput",
    "OverallStatus",
    "Severity",
    "StateEvidence",
    "VerificationEvidence",

    "DEFAULT_CONFIDENCE",
    "RateEstimate",
    "estimate_rate",
    "exact_binomial_interval",

    "MismatchAnalysis",
    "analyse_mismatch",
    "DisturbanceAnalysis",
    "analyse_disturbance",
    "is_disturbed",
    "FidelityAnalysis",
    "analyse_fidelity",
    "ConsistencyReport",
    "analyse_consistency",
    "AuthorizationCheck",
    "AuthorizationReport",
    "analyse_authorization",
    "ReplayEvidence",
    "ReplayRegistry",
    "BasisStatistics",
    "analyse_basis_statistics",
    "DetectionFeatures",
    "FeatureDescriptor",
    "FEATURE_CATALOG",
    "extract_features",

    "EvidenceItem",
    "ThreatEvidence",
    "assign_finding_ids",
    "statistical_severity",
    "DETERMINISTIC_SEVERITY",
    "BLOCKING_CATEGORIES",
    "DetectionResult",
    "decide",

    "ThreatDetectionEngine",
    "detect",
]
