"""Typed models for the finite-sample and interpretation layer.

Three record types, each answering a question the milestone brief insists on:

:class:`FiniteSizeBound`
    "what can be said about an unknown rate from a finite sample?" It carries its
    method, its citation and its assumptions, and it carries an explicit field
    recording that it is **not** a cryptographic security parameter. Setting that
    field to ``True`` raises, so the category error is impossible rather than
    merely discouraged.

:class:`Assumption`
    "what had to be true for that bound to mean anything?" Each assumption has a
    status -- exact, approximate, satisfied, not verified or violated -- an
    evidence string and a consequence if it fails. An assumption that is only
    approximate is recorded as approximate; there is no field for "probably fine".

:class:`InterpretationResult`
    "what may and may not be said about these numbers?" It carries the allowed
    statements, the forbidden claims with their reasons, and the results of
    checking specific sentences.

The terminology this module enforces
------------------------------------
======================================  ==========================================
confidence interval                     a statement about an unknown parameter
classification threshold                a decision rule derived from calibration
empirical attack acceptance rate        a measurement made on a dataset
formal cryptographic security bound     **not produced by this milestone**
======================================  ==========================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Tuple

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
]


QUANTITY_KINDS: Mapping[str, str] = {
    "confidence_interval": (
        "a statement about an unknown parameter, derived from a finite sample"
    ),
    "classification_threshold": (
        "a decision rule derived from a confidence bound and a sample size"
    ),
    "empirical_attack_acceptance_rate": (
        "a measurement of how often a decision rule accepted a modelled attack"
    ),
    "formal_cryptographic_security_bound": (
        "a proof-level bound on an adversary's advantage; not produced by this "
        "milestone"
    ),
}


class BoundKind(str, Enum):
    """Which finite-sample method produced a bound."""

    EXACT_CLOPPER_PEARSON = "exact-clopper-pearson-binomial-interval"
    HOEFFDING = "hoeffding-concentration-bound"


class BoundSidedness(str, Enum):
    """Which side of the parameter a bound constrains."""

    TWO_SIDED = "two-sided"
    UPPER = "upper"
    LOWER = "lower"


@dataclass(frozen=True)
class FiniteSizeBound:
    """One finite-sample statement about an unknown rate.

    ``is_cryptographic_security_bound`` exists so that the answer to "is this a
    security parameter?" is a field rather than an opinion. It is ``False`` for
    every bound this project produces, and constructing one with ``True`` raises.
    """

    kind: BoundKind
    sidedness: BoundSidedness
    statistic: str
    sample_size: int
    successes: int
    confidence: float
    lower: float | None
    upper: float | None
    point_estimate: float | None
    method: str
    citation: str
    assumptions: Tuple[str, ...]
    notes: Tuple[str, ...] = ()
    is_cryptographic_security_bound: bool = False

    def __post_init__(self) -> None:
        if self.is_cryptographic_security_bound:
            raise ValueError(
                "no finite-sample bound produced by this project is a "
                "cryptographic security bound. A binomial confidence interval or "
                "a Hoeffding bound describes the precision of an estimator of a "
                "rate; it says nothing about an adversary's advantage, and "
                "labelling it a security parameter is a category error."
            )
        if self.sample_size < 0:
            raise ValueError(
                f"sample_size must be non-negative, got {self.sample_size}"
            )
        if not 0.0 < float(self.confidence) < 1.0:
            raise ValueError(
                f"confidence must lie in (0, 1), got {self.confidence!r}"
            )

    @property
    def width(self) -> float | None:
        """Return ``upper - lower`` when both sides are defined."""
        if self.lower is None or self.upper is None:
            return None
        return self.upper - self.lower

    @property
    def quantity_kind(self) -> str:
        """Return the kind of quantity this record describes."""
        return "confidence_interval"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "sidedness": self.sidedness.value,
            "statistic": self.statistic,
            "sample_size": int(self.sample_size),
            "successes": int(self.successes),
            "confidence": float(self.confidence),
            "lower": self.lower,
            "upper": self.upper,
            "point_estimate": self.point_estimate,
            "width": self.width,
            "method": self.method,
            "citation": self.citation,
            "assumptions": list(self.assumptions),
            "notes": list(self.notes),
            "quantity_kind": self.quantity_kind,
            "is_cryptographic_security_bound": False,
        }


class AssumptionStatus(str, Enum):
    """How well an assumption holds for the reference configuration."""

    EXACT = "exact"
    SATISFIED = "satisfied"
    APPROXIMATE = "approximate"
    NOT_VERIFIED = "not-verified"
    VIOLATED = "violated"


@dataclass(frozen=True)
class Assumption:
    """One assumption, with its status and the consequence of its failure."""

    key: str
    statement: str
    status: AssumptionStatus
    evidence: str
    consequence_if_violated: str
    citation: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "statement": self.statement,
            "status": self.status.value,
            "evidence": self.evidence,
            "consequence_if_violated": self.consequence_if_violated,
            "citation": self.citation,
        }


@dataclass(frozen=True)
class AssumptionRegister:
    """The set of assumptions a finite-sample result depends on."""

    assumptions: Tuple[Assumption, ...]

    @property
    def by_status(self) -> Mapping[str, Tuple[str, ...]]:
        """Return assumption keys grouped by status, in a fixed status order."""
        grouped: Dict[str, list[str]] = {
            status.value: [] for status in AssumptionStatus
        }
        for assumption in self.assumptions:
            grouped[assumption.status.value].append(assumption.key)
        return {key: tuple(value) for key, value in grouped.items()}

    @property
    def weaker_than_exact(self) -> Tuple[str, ...]:
        """Return the keys of assumptions that are not exact."""
        return tuple(
            assumption.key
            for assumption in self.assumptions
            if assumption.status is not AssumptionStatus.EXACT
        )

    def summary(self) -> Dict[str, int]:
        """Return a count per status."""
        counts = {status.value: 0 for status in AssumptionStatus}
        for assumption in self.assumptions:
            counts[assumption.status.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assumptions": [item.to_dict() for item in self.assumptions],
            "summary": self.summary(),
            "weaker_than_exact": list(self.weaker_than_exact),
        }


class StatementVerdict(str, Enum):
    """Whether a sentence may be said about this project's results."""

    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class StatementCheck:
    """The result of checking one sentence against the forbidden claims."""

    statement: str
    verdict: StatementVerdict
    violations: Tuple[str, ...] = ()
    reasons: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement": self.statement,
            "verdict": self.verdict.value,
            "violations": list(self.violations),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class InterpretationResult:
    """What may and may not be said about a set of measured results."""

    allowed_statements: Tuple[str, ...]
    forbidden_claims: Tuple[Tuple[str, str], ...]
    checks: Tuple[StatementCheck, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_statements": list(self.allowed_statements),
            "forbidden_claims": [
                {"claim": claim, "why": why} for claim, why in self.forbidden_claims
            ],
            "checks": [check.to_dict() for check in self.checks],
            "context": dict(self.context),
            "notes": list(self.notes),
        }
