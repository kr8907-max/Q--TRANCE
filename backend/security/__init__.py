"""Finite-sample bounds, assumptions, interpretation and security analysis
(Milestones 5 and 6).

What this package is for
------------------------
Three jobs, all about keeping a number honest:

**Finite-sample statements.** :mod:`backend.security.finite_size` produces a
Clopper-Pearson exact binomial interval and a Hoeffding concentration bound, each
with its verified primary citation and its assumptions. Neither is a
cryptographic security parameter, and the record type makes that structurally
impossible to claim: constructing a
:class:`~backend.security.models.FiniteSizeBound` with
``is_cryptographic_security_bound=True`` raises.

**Interpretation.** :mod:`backend.security.assumptions` records what each result
depends on, with a status that distinguishes *exact* from *approximate* from
*not verified*. :mod:`backend.security.interpretation` records what may not be
said, and can check a sentence against that list.

**Security analysis (M6).** :mod:`backend.security.threat_bounds` computes the
conservative gap between an observed statistic and the calibrated honest model.
:mod:`backend.security.observability` records which threats are visible to which
layer, derived from structural code evidence and the committed M5 benchmark.
:mod:`backend.security.composition` assesses whether the components compose into
a secure system, and explicitly identifies where a formal composition theorem is
absent.

The four quantities that must not be conflated
----------------------------------------------
======================================  ==========================================
confidence interval                     a statement about an unknown parameter
classification threshold                a decision rule derived from calibration
empirical attack acceptance rate        a measurement made on a dataset
formal cryptographic security bound     **not produced by this milestone**
======================================  ==========================================

Dependency direction::

    backend.calibration  ->  backend.security   (bounds reuse the exact interval)
    backend.evaluation   ->  backend.security   (reports quote the caveats)

:mod:`backend.security` depends on neither, and imports no experiment code.
"""

from backend.security.assumptions import (
    EXACT_STATUSES,
    REFERENCE_ASSUMPTIONS,
    WEAK_STATUSES,
    assumption_dict,
    reference_assumptions,
    summarise_assumptions,
)
from backend.security.composition import (
    REFERENCE_COMPOSITION_ASSESSMENT,
    composition_summary,
    render_composition_table,
    unresolved_dependencies,
)
from backend.security.finite_size import (
    CLOPPER_PEARSON_ASSUMPTIONS,
    CLOPPER_PEARSON_CITATION,
    HOEFFDING_ASSUMPTIONS,
    HOEFFDING_CITATION,
    clopper_pearson_bound,
    compare_bounds,
    hoeffding_bound,
    hoeffding_radius,
    observed_vs_bound_margin,
    prediction_interval,
    required_sample_size,
)
from backend.security.observability import (
    REFERENCE_OBSERVABILITY_MATRIX,
    matrix_summary,
    render_matrix_table,
    threat_observability,
)
from backend.security.threat_bounds import (
    HonestPrediction,
    StatisticalSeparation,
    ThresholdExceedance,
    exceedance_probability,
    honest_prediction,
    statistical_separation,
    threshold_exceedance,
)
from backend.security.interpretation import (
    ALLOWED_QUALIFIERS,
    BANNED_TERMINOLOGY,
    FORBIDDEN_CLAIMS,
    FORBIDDEN_PATTERNS,
    build_interpretation_result,
    check_statement,
    check_statements,
    render_forbidden_examples,
    render_measurement_statement,
)
from backend.security.models import (
    QUANTITY_KINDS,
    Assumption,
    AssumptionRegister,
    AssumptionStatus,
    BoundKind,
    BoundSidedness,
    FiniteSizeBound,
    InterpretationResult,
    StatementCheck,
    StatementVerdict,
)

__all__ = [

    "BoundKind",
    "BoundSidedness",
    "FiniteSizeBound",
    "AssumptionStatus",
    "Assumption",
    "AssumptionRegister",
    "StatementVerdict",
    "StatementCheck",
    "InterpretationResult",
    "QUANTITY_KINDS",

    "CLOPPER_PEARSON_CITATION",
    "HOEFFDING_CITATION",
    "CLOPPER_PEARSON_ASSUMPTIONS",
    "HOEFFDING_ASSUMPTIONS",
    "clopper_pearson_bound",
    "hoeffding_radius",
    "hoeffding_bound",
    "required_sample_size",
    "compare_bounds",
    "observed_vs_bound_margin",
    "prediction_interval",

    "REFERENCE_ASSUMPTIONS",
    "EXACT_STATUSES",
    "WEAK_STATUSES",
    "reference_assumptions",
    "summarise_assumptions",
    "assumption_dict",

    "FORBIDDEN_CLAIMS",
    "FORBIDDEN_PATTERNS",
    "BANNED_TERMINOLOGY",
    "ALLOWED_QUALIFIERS",
    "check_statement",
    "check_statements",
    "render_measurement_statement",
    "render_forbidden_examples",
    "build_interpretation_result",

    "ThresholdExceedance",
    "StatisticalSeparation",
    "HonestPrediction",
    "threshold_exceedance",
    "statistical_separation",
    "honest_prediction",
    "exceedance_probability",

    "REFERENCE_OBSERVABILITY_MATRIX",
    "threat_observability",
    "render_matrix_table",
    "matrix_summary",

    "REFERENCE_COMPOSITION_ASSESSMENT",
    "composition_summary",
    "unresolved_dependencies",
    "render_composition_table",
]
