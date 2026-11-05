"""Report assembly.

This module does not run anything. It turns finished, typed results into two
artifacts a reviewer can actually read:

* a JSON payload, which is the machine-checkable record; and
* a Markdown summary, which states the numbers next to the definitions and the
  caveats so that a number cannot be quoted without its meaning.

The four quantities that must never be conflated are restated in every report:

======================================  ==========================================
confidence interval                     a statement about an unknown parameter
classification threshold                a decision rule derived from calibration
empirical attack acceptance rate        a measurement made on a dataset
formal cryptographic security bound     **not produced by this milestone**
======================================  ==========================================

The report also carries a fixed ``limitations`` list. It is not generated from
the results, because limitations do not stop applying when a result looks good.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Mapping, Sequence

from backend.calibration.models import OperatingPoint
from backend.calibration.multiple_testing import describe_diagnostics, reference_policy
from backend.calibration.operating_points import describe_operating_point

from backend.evaluation.metrics import (
    DESCRIPTIVE_METRICS,
    FAR_DEFINITION,
    FRR_DEFINITION,
    describe_metrics,
)
from backend.evaluation.models import (
    CurveResult,
    DiscriminationResult,
    EvaluationMetrics,
    RobustnessResult,
)

__all__ = [
    "LIMITATIONS",
    "QUANTITY_DISTINCTIONS",
    "build_report",
    "discrimination_report",
    "robustness_report",
    "attack_report",
    "curve_report",
    "render_markdown",
    "write_json",
    "write_markdown",
]


LIMITATIONS: Sequence[str] = (
    "The construction is a reference prototype. The organiser requirement "
    "specifies primitives and goals, not a complete formal QDS protocol, and "
    "nothing here should be read as a specification of one.",
    "Replay and identity checks are classical protocol controls. They are "
    "authorization bookkeeping, not quantum evidence, and they are reported "
    "separately for that reason.",
    "Quantum measurement does not prove identity. A verified session is "
    "consistent with a calibrated honest model; it is not a proof of who sent it.",
    "The simulator does not establish a new information-theoretic security "
    "proof, and no formal forgery bound is derived at this milestone. Deriving "
    "one is Milestone 6 work, and only if it is justified there.",
    "Acceptance in the sampled measurement mode is a finite-shot outcome, not a "
    "deterministic property. The mode travels with every observation so the two "
    "are never conflated.",
    "The statistical test is a consistency test against a calibrated honest "
    "model. A rejection is evidence of inconsistency with that model, not "
    "attribution of a cause.",
    "FAR and FRR are empirical rates measured on the reported dataset. They "
    "depend on the modelled attacks, the modelled channel, the sample size and "
    "the error budget, and they do not transfer to other conditions.",
    "The threshold is defined for one sample size. Applying it at another sample "
    "size is a category error, and the code raises rather than allowing it.",
    "The multiple-comparison policy is one primary test with the remaining "
    "statistics reported as diagnostics. No joint acceptance region was derived, "
    "so no combined family-wise claim is made.",
    "No machine learning is used anywhere. There is no learned threshold, no "
    "trained classifier and no anomaly model, so no result depends on a fitted "
    "model that could not be inspected.",
)


QUANTITY_DISTINCTIONS: Mapping[str, str] = {
    "confidence_interval": (
        "a statement about an unknown parameter, e.g. a Clopper-Pearson interval "
        "for the honest mismatch probability"
    ),
    "classification_threshold": (
        "a decision rule derived from that interval and the sample size, e.g. "
        "reject when the mismatch count exceeds a critical count"
    ),
    "empirical_attack_acceptance_rate": (
        "a measurement: the share of malicious trials the rule accepted, on a "
        "specific dataset under a specific modelled attack"
    ),
    "formal_cryptographic_security_bound": (
        "a proof-level bound on an adversary's advantage; NOT produced by this "
        "milestone and never to be read into the numbers above"
    ),
}


def curve_report(curves: Mapping[str, CurveResult]) -> Dict[str, Any]:
    """Return the serialised curves, with a per-curve evidence summary."""
    return {
        name: {
            **curve.to_dict(),
            "total_trials": sum(point.trials for point in curve.points),
        }
        for name, curve in curves.items()
    }


def attack_report(
    per_attack: Mapping[str, EvaluationMetrics],
    *,
    attack_fraction: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    """Return the per-attack evaluation payload."""
    fractions = dict(attack_fraction or {})
    return {
        "by_attack_type": {
            attack_type: {
                **describe_metrics(bundle),
                "attack_fraction": fractions.get(attack_type),
                "far_scope": (
                    "this FAR is the empirical acceptance rate for the modelled "
                    f"{attack_type} experiment and is not a cryptographic forgery "
                    "probability"
                ),
            }
            for attack_type, bundle in per_attack.items()
        },
        "what_counts_as_malicious": (
            "every trial the experiment injected an attack into: forgery, "
            "impersonation, unauthorized verification, replay, intercept-resend "
            "and channel tampering. Honest trials are never malicious."
        ),
    }


def robustness_report(result: RobustnessResult) -> Dict[str, Any]:
    """Return the robustness payload."""
    return {
        **result.to_dict(),
        "reading": (
            "honest_frr_by_noise is the honest false-rejection rate per noise "
            "level; detection_by_noise_and_attack is the share of malicious "
            "trials rejected at each noise level for each attack"
        ),
    }


def discrimination_report(
    results: Iterable[DiscriminationResult],
) -> Sequence[Dict[str, Any]]:
    """Return the discrimination-experiment payload."""
    return tuple(
        {
            **result.to_dict(),
            "reading": (
                "matched=true means the two populations have comparable marginal "
                "mismatch rates, so any separation on the descriptor is "
                "separation the marginal rate does not provide"
            ),
        }
        for result in results
    )


def build_report(
    *,
    operating_point: OperatingPoint,
    calibration: Mapping[str, Any],
    curves: Mapping[str, CurveResult],
    attack_metrics: Mapping[str, EvaluationMetrics],
    robustness: RobustnessResult | None = None,
    discrimination: Sequence[DiscriminationResult] = (),
    sample_size: Mapping[str, Any] | None = None,
    attack_fractions: Mapping[str, float] | None = None,
    provenance: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Assemble the full report payload from finished results."""
    policy = reference_policy()
    payload: Dict[str, Any] = {
        "milestone": "M5",
        "title": "Statistical calibration, finite-sample analysis and security evaluation",
        "operating_point": {
            **describe_operating_point(operating_point),
            "protocol_version": operating_point.protocol_version,
            "notes": list(operating_point.notes),
        },
        "calibration": dict(calibration),
        "definitions": {
            "far": FAR_DEFINITION,
            "frr": FRR_DEFINITION,
            "descriptive_metrics": list(DESCRIPTIVE_METRICS),
            "quantity_distinctions": dict(QUANTITY_DISTINCTIONS),
            "positive_class": (
                "the positive class is 'the verification decision rejected the "
                "session', so FPR equals FRR and FNR equals FAR"
            ),
        },
        "multiple_comparison_policy": {
            "primary_test": policy.primary_test,
            "policy": policy.policy.value,
            "diagnostic_metrics": list(policy.diagnostic_metrics),
            "family_wise_alpha": policy.family_wise_alpha,
            "correction": policy.correction,
            "policy_notes": list(policy.notes),
            "diagnostics": describe_diagnostics(
                {name: "reported, not adjudicated" for name in policy.diagnostic_metrics},
                policy,
            ),
        },
        "curves": curve_report(curves),
        "attack_evaluation": attack_report(
            attack_metrics, attack_fraction=attack_fractions
        ),
        "limitations": list(LIMITATIONS),
    }
    if robustness is not None:
        payload["robustness"] = robustness_report(robustness)
    if discrimination:
        payload["discrimination"] = list(discrimination_report(discrimination))
    if sample_size is not None:
        payload["sample_size"] = dict(sample_size)
    payload["provenance"] = dict(provenance or {})
    if extra:
        payload.update(dict(extra))
    return payload







def _format_rate(value: Any) -> str:
    """Return a rate as a percentage string, or ``n/a``."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value * 100:.2f}%"
    return str(value)


def _format_number(value: Any) -> str:
    """Return a number compactly, or ``n/a``."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the report payload as a Markdown summary."""
    lines: list[str] = []
    add = lines.append

    add(f"# Milestone 5 report — {report.get('title', '')}")
    add("")

    point = report.get("operating_point", {})
    add("## Reference operating point")
    add("")
    add("Exactly one operating point is defined. It is *specified*, not optimised:")
    add("no objective was maximised, so no claim of optimality is made.")
    add("")
    add("| field | value |")
    add("| --- | --- |")
    for key in (
        "name",
        "statistic",
        "state_count",
        "measurement_mode",
        "shot_count",
        "threshold_rate",
        "critical_count",
        "p_upper",
        "alpha",
        "calibration_sessions",
        "observed_calibration_frr",
    ):
        value = point.get(key)
        if key in {"threshold_rate", "p_upper", "observed_calibration_frr"}:
            rendered = _format_rate(value)
        else:
            rendered = _format_number(value)
        add(f"| `{key}` | {rendered} |")
    add("")
    add("Honest channel: " + json.dumps(point.get("honest_channel", {}), sort_keys=True))
    add("")
    add("Calibration seed range: " + json.dumps(point.get("calibration_seed_range")))
    add("")

    configuration = report.get("measurement_configuration")
    if configuration:
        add("## Measurement configuration")
        add("")
        add(f"- measurement mode: `{configuration.get('measurement_mode')}`")
        add(f"- shots per state: {configuration.get('shot_count')}")
        add(
            "- reference honest channel: "
            + json.dumps(configuration.get("reference_noise", {}), sort_keys=True)
        )
        add("")
        add(f"> {configuration.get('why', '')}")
        add("")

    add("## Definitions")
    add("")
    definitions = report.get("definitions", {})
    add(f"- FAR — {definitions.get('far', '')}")
    add(f"- FRR — {definitions.get('frr', '')}")
    add(f"- {definitions.get('positive_class', '')}")
    add("")
    add("The four quantities that must not be conflated:")
    add("")
    for name, description in definitions.get("quantity_distinctions", {}).items():
        add(f"- **{name}** — {description}")
    add("")

    add("## Multiple-comparison policy")
    add("")
    policy = report.get("multiple_comparison_policy", {})
    add(f"- primary test: `{policy.get('primary_test', '')}`")
    add(f"- policy: {policy.get('policy', '')}")
    add(f"- family-wise alpha: {policy.get('family_wise_alpha')} "
        f"(correction: {policy.get('correction')})")
    add("- reported as diagnostics only, never adjudicated: "
        + ", ".join(f"`{name}`" for name in policy.get("diagnostic_metrics", [])))
    add("")
    for note in policy.get("policy_notes", []):
        add(f"> {note}")
    add("")

    curves = report.get("curves", {})
    if curves:
        add("## Curves")
        add("")
        add("Every point below comes from runs; none is interpolated or synthetic.")
        add("")
        for name, curve in curves.items():
            add(f"### `{name}`")
            add("")
            add(f"- x: {curve.get('x_label', '')}; y: {curve.get('y_label', '')}")
            add(f"- points: {len(curve.get('points', []))}; "
                f"total trials: {curve.get('total_trials', 0)}")
            add("")
            add("| x | y | trials |")
            add("| --- | --- | --- |")
            for entry in curve.get("points", []):
                add(
                    f"| {_format_number(entry.get('x'))} | "
                    f"{_format_number(entry.get('y'))} | {entry.get('trials')} |"
                )
            add("")
            for note in curve.get("notes", []):
                add(f"> {note}")
            add("")

    attack = report.get("attack_evaluation", {})
    if attack:
        add("## Attack evaluation")
        add("")
        add(f"> {attack.get('what_counts_as_malicious', '')}")
        add("")
        add("| attack | fraction | malicious trials | detection rate | FAR | FRR |")
        add("| --- | --- | --- | --- | --- | --- |")
        for attack_type, bundle in attack.get("by_attack_type", {}).items():
            matrix = bundle.get("matrix", {})
            add(
                f"| `{attack_type}` | {_format_number(bundle.get('attack_fraction'))} | "
                f"{matrix.get('malicious', 0)} | "
                f"{_format_rate(bundle.get('detection_rate'))} | "
                f"{_format_rate(bundle.get('far'))} | "
                f"{_format_rate(bundle.get('frr'))} |"
            )
        add("")

    robustness = report.get("robustness")
    if robustness:
        detection = robustness.get("detection_by_noise_and_attack", {}) or {}
        add("## Noise robustness")
        add("")
        add("| noise level | honest FRR | " + " | ".join(detection) + " |")
        add("| --- | --- | " + " | ".join("---" for _ in detection) + " |")
        for level, frr in robustness.get("honest_frr_by_noise", {}).items():
            cells = [_format_rate(detection[attack].get(level)) for attack in detection]
            add(f"| {level} | {_format_rate(frr)} | " + " | ".join(cells) + " |")
        add("")

    sample_size = report.get("sample_size")
    if sample_size:
        add("## Sample-size study")
        add("")
        add("| N | critical count | threshold rate | honest FRR | detection |")
        add("| --- | --- | --- | --- | --- |")
        for row in sample_size.get("rows", []):
            add(
                f"| {row.get('state_count')} | {row.get('critical_count')} | "
                f"{_format_rate(row.get('threshold_rate'))} | "
                f"{_format_rate(row.get('honest_frr'))} | "
                f"{_format_rate(row.get('detection_rate'))} |"
            )
        add("")

    discrimination = report.get("discrimination")
    if discrimination:
        add("## Discrimination experiment")
        add("")
        add(
            "Comparing honest noise with a malicious channel attack at comparable "
            "marginal mismatch rates."
        )
        add("")
        for entry in discrimination:
            add(f"### {entry.get('malicious_label', '')}")
            add("")
            add(f"- honest marginal mismatch rate: "
                f"{_format_number(entry.get('honest_marginal'))}")
            add(f"- malicious marginal mismatch rate: "
                f"{_format_number(entry.get('malicious_marginal'))}")
            add(f"- marginal gap: {_format_number(entry.get('marginal_gap'))} "
                f"(matched: {entry.get('matched')})")
            add(f"- descriptor: `{entry.get('descriptor')}`")
            add(f"- distinguishable: **{entry.get('distinguishable')}**")
            add(f"- verdict: {entry.get('verdict')}")
            add(f"- honest rejection rate: "
                f"{_format_rate(entry.get('honest_rejection_rate'))}")
            add(f"- malicious rejection rate: "
                f"{_format_rate(entry.get('malicious_rejection_rate'))}")
            add("")

    add("## Limitations")
    add("")
    for limitation in report.get("limitations", []):
        add(f"- {limitation}")
    add("")

    provenance = report.get("provenance")
    if provenance:
        add("## Provenance")
        add("")
        add("```json")
        add(json.dumps(provenance, indent=2, sort_keys=True))
        add("```")
        add("")

    return "\n".join(lines)


def write_json(payload: Mapping[str, Any], path: str) -> str:
    """Write ``payload`` as JSON to ``path``, creating parent directories."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write_markdown(text: str, path: str) -> str:
    """Write ``text`` to ``path``, creating parent directories."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path
