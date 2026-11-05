"""Composition assessment: no formal composition theorem is claimed.

These tests verify that the composition assessment is conservative, that every
component identifies its unresolved dependency, and that no conclusion fabricates
a formal security proof.
"""

from __future__ import annotations

import pytest

from backend.security.composition import (
    REFERENCE_COMPOSITION_ASSESSMENT,
    composition_summary,
    render_composition_table,
    unresolved_dependencies,
)







def test_all_six_milestones_are_assessed() -> None:
    components = {item.component for item in REFERENCE_COMPOSITION_ASSESSMENT}
    assert len(components) == 6
    assert any("M1" in item.component for item in REFERENCE_COMPOSITION_ASSESSMENT)
    assert any("M6" in item.component for item in REFERENCE_COMPOSITION_ASSESSMENT)


def test_every_component_has_an_unresolved_dependency() -> None:
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        assert item.unresolved_dependency, item.component
        assert len(item.unresolved_dependency) > 10


def test_no_security_conclusion_claims_a_formal_proof() -> None:
    forbidden = (
        "information-theoretically secure",
        "formal forgery bound",
        "unconditional",
        "provably secure",
        "guarantees detection",
        "guarantees security",
    )
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        lowered = item.security_conclusion.lower()
        for phrase in forbidden:
            assert phrase not in lowered, (item.component, phrase)


def test_the_composition_summary_denies_a_formal_theorem() -> None:
    summary = composition_summary()
    assert summary["formal_composition_theorem_present"] is False
    assert "no formal composition theorem" in summary["note"].lower()


def test_unresolved_dependencies_is_non_empty() -> None:
    deps = unresolved_dependencies()
    assert len(deps) == 6
    for dep in deps:
        assert ":" in dep







def test_render_composition_table_is_markdown() -> None:
    table = render_composition_table()
    assert "| Component |" in table
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        assert item.component in table







def test_every_assessment_serialises() -> None:
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        payload = item.to_dict()
        assert payload["component"] == item.component
        assert "property_evaluated" in payload
        assert "security_conclusion" in payload
