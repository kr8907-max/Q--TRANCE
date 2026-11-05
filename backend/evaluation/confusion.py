"""Confusion matrices for evaluation trials.

The convention is fixed in :mod:`backend.evaluation.models` and repeated here
because it is the thing a reader will get wrong:

**the positive class is "the verification decision rejected the session".**

Therefore

* ``tp`` -- a malicious trial the decision rejected;
* ``fn`` -- a malicious trial the decision accepted (**a false acceptance**);
* ``fp`` -- an honest trial the decision rejected (**a false rejection**);
* ``tn`` -- an honest trial the decision accepted.

and ``FAR = fn / malicious`` while ``FRR = fp / honest``. ``FPR`` is *not* FAR:
``FPR`` is the honest rejection rate, which under this convention equals ``FRR``.
That identity is asserted in the test suite rather than merely documented.

Nothing in this module runs an experiment or reads a threshold. It counts
outcomes that have already been decided.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence, Tuple

from backend.evaluation.models import ConfusionMatrix, TrialRecord, TrialOutcome

__all__ = [
    "HONEST_ATTACK_TYPE",
    "confusion_matrix",
    "confusion_by",
    "confusion_by_attack_type",
    "confusion_by_noise",
    "partition_by_attack_type",
    "partition_by_noise",
    "partition_honest_malicious",
    "outcome_counts",
]


HONEST_ATTACK_TYPE = "none"


def confusion_matrix(records: Iterable[TrialRecord]) -> ConfusionMatrix:
    """Return the confusion matrix of ``records``.

    Empty input yields the all-zero matrix, which is the honest answer: no
    trials were scored, so no counts exist.
    """
    tp = tn = fp = fn = 0
    for record in records:
        rejected = record.decision.rejected
        if record.is_malicious:
            if rejected:
                tp += 1
            else:
                fn += 1
        else:
            if rejected:
                fp += 1
            else:
                tn += 1
    return ConfusionMatrix(tp=tp, tn=tn, fp=fp, fn=fn)


def confusion_by(
    records: Iterable[TrialRecord],
    key: Callable[[TrialRecord], str],
) -> Dict[str, ConfusionMatrix]:
    """Return one confusion matrix per group, keyed by ``key``.

    Groups appear in first-seen order so a report reads in the order the
    experiments were run rather than in hash order.
    """
    groups: "OrderedDict[str, ConfusionMatrix]" = OrderedDict()
    for record in records:
        group = str(key(record))
        groups[group] = groups.get(group, ConfusionMatrix()) + _single(record)
    return dict(groups)


def _single(record: TrialRecord) -> ConfusionMatrix:
    """Return the one-trial confusion matrix for ``record``."""
    rejected = record.decision.rejected
    if record.is_malicious:
        return ConfusionMatrix(tp=1) if rejected else ConfusionMatrix(fn=1)
    return ConfusionMatrix(fp=1) if rejected else ConfusionMatrix(tn=1)


def confusion_by_attack_type(
    records: Iterable[TrialRecord],
) -> Dict[str, ConfusionMatrix]:
    """Return a confusion matrix per attack type.

    Honest records land under ``"none"``. Because honest trials are never
    malicious, their group can only ever contribute ``tn`` and ``fp``: the
    "detection rate" of the honest group is undefined, which is the correct
    reading and is why the report never prints one.
    """
    return confusion_by(records, lambda record: record.attack_type)


def confusion_by_noise(records: Iterable[TrialRecord]) -> Dict[str, ConfusionMatrix]:
    """Return a confusion matrix per ``(noise_type, noise_strength)`` cell."""
    return confusion_by(
        records, lambda record: f"{record.noise_type}@{record.noise_strength:g}"
    )


def partition_by_attack_type(
    records: Iterable[TrialRecord],
) -> Dict[str, Tuple[TrialRecord, ...]]:
    """Return the records grouped by attack type, in first-seen order."""
    groups: "OrderedDict[str, list[TrialRecord]]" = OrderedDict()
    for record in records:
        groups.setdefault(record.attack_type, []).append(record)
    return {key: tuple(value) for key, value in groups.items()}


def partition_by_noise(
    records: Iterable[TrialRecord],
) -> Dict[str, Tuple[TrialRecord, ...]]:
    """Return the records grouped by ``(noise_type, noise_strength)``."""
    groups: "OrderedDict[str, list[TrialRecord]]" = OrderedDict()
    for record in records:
        key = f"{record.noise_type}@{record.noise_strength:g}"
        groups.setdefault(key, []).append(record)
    return {key: tuple(value) for key, value in groups.items()}


def partition_honest_malicious(
    records: Iterable[TrialRecord],
) -> Tuple[Tuple[TrialRecord, ...], Tuple[TrialRecord, ...]]:
    """Return ``(honest, malicious)`` partitions, each in input order."""
    honest: list[TrialRecord] = []
    malicious: list[TrialRecord] = []
    for record in records:
        (malicious if record.is_malicious else honest).append(record)
    return tuple(honest), tuple(malicious)


def outcome_counts(records: Iterable[TrialRecord]) -> Mapping[str, int]:
    """Return how many trials ended in each outcome.

    Reported alongside the confusion matrix because "0 rejections" and "no
    trials" look identical in a matrix of zeros and do not mean the same thing.
    """
    counts = {TrialOutcome.REJECTED.value: 0, TrialOutcome.ACCEPTED.value: 0}
    for record in records:
        counts[record.outcome.value] += 1
    return counts


def records_to_dicts(records: Sequence[TrialRecord]) -> Tuple[Dict[str, Any], ...]:
    """Return the serialised records, for report payloads."""
    return tuple(record.to_dict() for record in records)
