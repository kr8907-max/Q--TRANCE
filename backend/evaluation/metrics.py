"""Rates derived from confusion matrices, and population summaries.

Definitions this module fixes, in the milestone's own terms
----------------------------------------------------------
``FAR``
    ``malicious trials accepted / malicious trials``. It is an **empirical
    acceptance rate for a modelled experiment**. It is *not* a cryptographic
    forgery probability and it is never reported as one.

``FRR``
    ``honest trials rejected / honest trials``. It is an empirical rejection
    rate on honest material.

What counts as "malicious" is not decided here. It is whatever the experiment
injected and the simulation layer recorded as ``is_malicious`` -- forgery,
impersonation, unauthorized verification, replay, intercept-resend or channel
tampering. The report names the attack next to the number so that a reader is
never left to guess which population an acceptance rate belongs to.

``precision``, ``recall`` and ``F1`` are computed because the brief lists them.
They are marked descriptive, they are not security metrics, and no claim about
the protocol is derived from them.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from backend.evaluation.confusion import confusion_by_attack_type, confusion_by_noise
from backend.evaluation.models import (
    ConfusionMatrix,
    EvaluationMetrics,
    PopulationSummary,
    TrialRecord,
)

__all__ = [
    "FAR_DEFINITION",
    "FRR_DEFINITION",
    "metrics_from_matrix",
    "metrics",
    "detection_rate",
    "false_acceptance_rate",
    "false_rejection_rate",
    "metrics_by_attack_type",
    "metrics_by_noise",
    "summarise_population",
    "describe_metrics",
    "DESCRIPTIVE_METRICS",
]


FAR_DEFINITION = (
    "FAR = malicious trials accepted / malicious trials: an empirical acceptance "
    "rate for the modelled attack experiment, not a cryptographic forgery "
    "probability"
)


FRR_DEFINITION = (
    "FRR = honest trials rejected / honest trials: an empirical rejection rate "
    "measured on honest material"
)


DESCRIPTIVE_METRICS: Tuple[str, ...] = ("precision", "recall", "f1", "accuracy")


def metrics_from_matrix(matrix: ConfusionMatrix) -> EvaluationMetrics:
    """Return the metric bundle for ``matrix``."""
    return EvaluationMetrics(matrix=matrix)


def metrics(records: Iterable[TrialRecord]) -> EvaluationMetrics:
    """Return the metric bundle for a population of trials."""
    from backend.evaluation.confusion import confusion_matrix

    return EvaluationMetrics(matrix=confusion_matrix(records))


def detection_rate(records: Iterable[TrialRecord]) -> float | None:
    """Return the share of malicious trials the decision rejected."""
    return metrics(records).detection_rate


def false_acceptance_rate(records: Iterable[TrialRecord]) -> float | None:
    """Return ``FAR``: the share of malicious trials the decision accepted."""
    return metrics(records).far


def false_rejection_rate(records: Iterable[TrialRecord]) -> float | None:
    """Return ``FRR``: the share of honest trials the decision rejected."""
    return metrics(records).frr


def metrics_by_attack_type(
    records: Iterable[TrialRecord],
) -> Dict[str, EvaluationMetrics]:
    """Return a metric bundle per attack type.

    An honest group (``"none"``) has no malicious trials, so its ``far``,
    ``detection_rate``, ``precision`` and ``f1`` are ``None`` rather than zero.
    That is deliberate: a detection rate over an empty malicious population is
    undefined, and printing ``0.0`` would read as a failure of the detector.
    """
    return {
        key: metrics_from_matrix(matrix)
        for key, matrix in confusion_by_attack_type(records).items()
    }


def metrics_by_noise(
    records: Iterable[TrialRecord],
) -> Dict[str, EvaluationMetrics]:
    """Return a metric bundle per ``(noise_type, noise_strength)`` cell."""
    return {
        key: metrics_from_matrix(matrix)
        for key, matrix in confusion_by_noise(records).items()
    }


def _describe(values: Sequence[float]) -> Tuple[float | None, float | None, float | None]:
    """Return ``(mean, minimum, maximum)``, or three ``None`` values."""
    if not values:
        return None, None, None
    return sum(values) / len(values), min(values), max(values)


def summarise_population(
    records: Iterable[TrialRecord], label: str
) -> PopulationSummary:
    """Return descriptive statistics for one population of trials.

    Every quantity summarised here is observable, so a summary can be computed
    from records whose labels have been stripped -- which is what makes it
    usable as a *descriptor* in the discrimination experiment rather than as a
    second decision rule.
    """
    population = tuple(records)
    marginals = [
        record.statistics.mismatch_rate
        for record in population
        if record.statistics.mismatch_rate is not None
    ]
    dispersions = [
        record.statistics.basis_mismatch_dispersion
        for record in population
        if record.statistics.basis_mismatch_dispersion is not None
    ]
    fidelities = [
        record.statistics.mean_fidelity
        for record in population
        if record.statistics.mean_fidelity is not None
    ]

    mean_marginal, min_marginal, max_marginal = _describe(marginals)
    mean_dispersion, min_dispersion, max_dispersion = _describe(dispersions)
    mean_fidelity, _, _ = _describe(fidelities)

    return PopulationSummary(
        label=label,
        trials=len(population),
        mean_mismatch_rate=mean_marginal,
        minimum_mismatch_rate=min_marginal,
        maximum_mismatch_rate=max_marginal,
        mean_basis_dispersion=mean_dispersion,
        minimum_basis_dispersion=min_dispersion,
        maximum_basis_dispersion=max_dispersion,
        mean_fidelity=mean_fidelity,
    )


def describe_metrics(bundle: EvaluationMetrics) -> Mapping[str, Any]:
    """Return a metric bundle as a report payload, with definitions attached."""
    payload: Dict[str, Any] = dict(bundle.to_dict())
    payload["far_definition"] = FAR_DEFINITION
    payload["frr_definition"] = FRR_DEFINITION
    payload["descriptive_metrics"] = list(DESCRIPTIVE_METRICS)
    payload["note"] = (
        "FAR and FRR are empirical rates measured on this dataset. Neither is a "
        "cryptographic bound, and F1 and accuracy are descriptive summaries of "
        "one operating point on one dataset."
    )
    return payload
