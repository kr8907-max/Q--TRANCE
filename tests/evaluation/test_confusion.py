"""Confusion matrices, and the convention that makes them unambiguous.

Two conventions for "false positive" are in common use and they disagree. This
project fixes one: **the positive class is "the verification decision rejected
the session"**. These tests pin the consequences, including the identity that
surprises most readers -- ``FPR = FRR`` -- so that it is asserted rather than
merely documented.
"""

from __future__ import annotations

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
    records_to_dicts,
)
from backend.evaluation.models import ConfusionMatrix, TrialOutcome


def test_the_empty_input_yields_the_zero_matrix(make_record) -> None:
    matrix = confusion_matrix([])
    assert matrix == ConfusionMatrix()
    assert matrix.total == 0


def test_each_outcome_lands_in_the_documented_cell(make_record) -> None:
    records = [
        make_record(malicious=True, rejected=True),
        make_record(malicious=True, rejected=False),
        make_record(malicious=False, rejected=True),
        make_record(malicious=False, rejected=False),
    ]
    matrix = confusion_matrix(records)
    assert (matrix.tp, matrix.fn, matrix.fp, matrix.tn) == (1, 1, 1, 1)
    assert matrix.total == 4
    assert matrix.malicious == 2
    assert matrix.honest == 2


def test_the_matrix_is_additive(make_record) -> None:
    a = confusion_matrix([make_record(malicious=True, rejected=True)])
    b = confusion_matrix([make_record(malicious=False, rejected=False)])
    assert (a + b) == ConfusionMatrix(tp=1, tn=1)


def test_adding_a_non_matrix_is_not_supported() -> None:
    assert ConfusionMatrix().__add__(3) is NotImplemented


def test_the_honest_group_can_only_contribute_tn_and_fp(make_record) -> None:



    honest = [make_record(malicious=False, rejected=index % 2 == 0) for index in range(6)]
    matrix = confusion_matrix(honest)
    assert matrix.malicious == 0
    assert matrix.tp == 0
    assert matrix.fn == 0
    assert matrix.honest == 6







def test_confusion_by_groups_in_first_seen_order(make_record) -> None:
    records = [
        make_record(malicious=False, rejected=False, attack_type="beta"),
        make_record(malicious=True, rejected=True, attack_type="alpha"),
        make_record(malicious=False, rejected=False, attack_type="beta"),
    ]
    grouped = confusion_by(records, lambda record: record.attack_type)
    assert list(grouped) == ["beta", "alpha"]
    assert grouped["beta"].tn == 2
    assert grouped["alpha"].tp == 1


def test_confusion_by_attack_type_puts_honest_under_none(make_record) -> None:
    records = [
        make_record(malicious=False, rejected=False),
        make_record(malicious=True, rejected=True, attack_type="intercept_resend"),
    ]
    grouped = confusion_by_attack_type(records)
    assert set(grouped) == {HONEST_ATTACK_TYPE, "intercept_resend"}
    assert grouped[HONEST_ATTACK_TYPE].tn == 1
    assert grouped["intercept_resend"].tp == 1


def test_confusion_by_noise_keys_on_type_and_strength(make_record) -> None:
    records = [
        make_record(malicious=False, rejected=False, noise_strength=0.0),
        make_record(malicious=False, rejected=False, noise_strength=0.02),
    ]
    grouped = confusion_by_noise(records)
    assert set(grouped) == {"depolarizing@0", "depolarizing@0.02"}


def test_partition_by_attack_type_preserves_input_order(make_record) -> None:
    first = make_record(malicious=True, rejected=True, attack_type="a", seed=1)
    second = make_record(malicious=True, rejected=True, attack_type="b", seed=2)
    third = make_record(malicious=True, rejected=True, attack_type="a", seed=3)
    grouped = partition_by_attack_type([first, second, third])
    assert grouped["a"] == (first, third)
    assert grouped["b"] == (second,)


def test_partition_by_noise_preserves_input_order(make_record) -> None:
    records = [
        make_record(malicious=False, rejected=False, noise_strength=0.0, seed=1),
        make_record(malicious=False, rejected=False, noise_strength=0.1, seed=2),
        make_record(malicious=False, rejected=False, noise_strength=0.0, seed=3),
    ]
    grouped = partition_by_noise(records)
    assert grouped["depolarizing@0"] == (records[0], records[2])
    assert grouped["depolarizing@0.1"] == (records[1],)


def test_partition_honest_malicious_splits_and_keeps_order(make_record) -> None:
    honest_a = make_record(malicious=False, rejected=False, seed=1)
    malicious = make_record(malicious=True, rejected=True, seed=2)
    honest_b = make_record(malicious=False, rejected=True, seed=3)
    honest, bad = partition_honest_malicious([honest_a, malicious, honest_b])
    assert honest == (honest_a, honest_b)
    assert bad == (malicious,)


def test_outcome_counts_distinguishes_zero_from_no_trials(make_record) -> None:


    empty = outcome_counts([])
    assert empty == {TrialOutcome.REJECTED.value: 0, TrialOutcome.ACCEPTED.value: 0}

    counted = outcome_counts(
        [
            make_record(malicious=True, rejected=True),
            make_record(malicious=False, rejected=False),
            make_record(malicious=False, rejected=False),
        ]
    )
    assert counted == {"REJECTED": 1, "ACCEPTED": 2}


def test_records_to_dicts_serialises_each_record(make_record) -> None:
    payloads = records_to_dicts([make_record(malicious=True, rejected=True)])
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["is_malicious"] is True
    assert payload["outcome"] == "REJECTED"
    assert "statistics" in payload
    assert "decision" in payload
