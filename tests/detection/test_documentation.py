"""Documentation matches implementation (Milestone 4 acceptance criterion 22).

The milestone brief requires ``docs/security/detection-engine.md`` to carry a
fixed statement and a fixed set of sections, and requires the written
documentation to describe the features the code actually implements. Rather than
promise that, this module makes it executable:

* the required statement is asserted verbatim;
* the document must contain exactly 16 numbered top-level sections, numbered
  1..16 with no gaps;
* every name in :data:`~backend.detection.features.FEATURE_CATALOG` must appear;
* every :class:`~backend.detection.models.EvidenceCategory` value must appear;
* every :class:`~backend.detection.models.OverallStatus` value must appear;
* every detection module must be named;
* no forbidden overclaim may appear.

The negative checker is itself self-tested, so it cannot pass vacuously -- the
standing lesson from Milestones 2 and 3 is that a text-based check which is never
shown to fire is not a check.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable, Set

from backend.detection.evidence import (
    AUTHORIZATION_CATEGORIES,
    INTEGRITY_CATEGORIES,
    QUANTUM_CATEGORIES,
)
from backend.detection.features import FEATURE_CATALOG
from backend.detection.models import EvidenceCategory, OverallStatus

__all__ = ["assert_documentation_matches"]

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCUMENTATION = REPO_ROOT / "docs" / "security" / "detection-engine.md"


REQUIRED_STATEMENT = (
    "The M4 detector does not use attack ground truth and does not learn from "
    "attack labels."
)


REQUIRED_SECTION_COUNT = 16


REQUIRED_MODULES = (
    "models",
    "statistics",
    "mismatch",
    "disturbance",
    "fidelity",
    "consistency",
    "authorization",
    "replay",
    "features",
    "evidence",
    "decision",
    "engine",
)



FORBIDDEN_PHRASES = (
    "unconditional security",
    "always detected",
    "all attacks are covered",
    "formal cryptographic proof",
    "guarantees detection",
    "detects all attacks",
    "proves the identity",
)


SECTION_PATTERN = re.compile(r"^##\s+(\d+)\.\s+\S", re.MULTILINE)


def normalise(text: str) -> str:
    """Return ``text`` with markdown emphasis and backticks removed.

    Underscores are deliberately **preserved**: feature names are snake_case, and
    stripping underscores (as an earlier milestone's helper did) would mangle
    exactly the identifiers this check exists to verify.
    """
    text = text.replace("**", "").replace("`", "").replace("*", "")
    text = re.sub(r"^[#>\s]+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text)


def read_documentation() -> str:
    """Return the raw documentation text, asserting that it exists."""
    assert DOCUMENTATION.is_file(), f"missing documentation: {DOCUMENTATION}"
    return DOCUMENTATION.read_text(encoding="utf-8")


def missing(text: str, needles: Iterable[str]) -> Set[str]:
    """Return the subset of ``needles`` that does not occur in ``text``."""
    return {needle for needle in needles if needle not in text}


def section_numbers(raw: str) -> list[str]:
    """Return the numbers of the numbered top-level sections, in order."""
    return SECTION_PATTERN.findall(raw)


def assert_documentation_matches() -> None:
    """Assert that the documentation still describes the implementation."""
    raw = read_documentation()
    text = normalise(raw)


    assert REQUIRED_STATEMENT in text, (
        "the required statement is missing from the documentation"
    )


    numbers = section_numbers(raw)
    assert len(numbers) == REQUIRED_SECTION_COUNT, (
        f"expected {REQUIRED_SECTION_COUNT} numbered sections, found "
        f"{len(numbers)}: {numbers}"
    )
    assert numbers == [str(index) for index in range(1, REQUIRED_SECTION_COUNT + 1)], (
        f"section numbers must run 1..{REQUIRED_SECTION_COUNT} in order, got "
        f"{numbers}"
    )


    absent_features = missing(text, FEATURE_CATALOG)
    assert not absent_features, f"undocumented features: {sorted(absent_features)}"


    categories = tuple(category.value for category in EvidenceCategory)
    absent_categories = missing(text, categories)
    assert not absent_categories, (
        f"undocumented evidence categories: {sorted(absent_categories)}"
    )


    statuses = tuple(status.value for status in OverallStatus)
    absent_statuses = missing(text, statuses)
    assert not absent_statuses, (
        f"undocumented overall statuses: {sorted(absent_statuses)}"
    )


    absent_modules = missing(text, REQUIRED_MODULES)
    assert not absent_modules, f"undocumented modules: {sorted(absent_modules)}"


    assert INTEGRITY_CATEGORIES and AUTHORIZATION_CATEGORIES and QUANTUM_CATEGORIES
    for family, label in (
        (INTEGRITY_CATEGORIES, "integrity"),
        (AUTHORIZATION_CATEGORIES, "authorization"),
        (QUANTUM_CATEGORIES, "quantum"),
    ):
        for category in family:
            assert category.value in text, f"{label} category {category.value}"


    found = {phrase for phrase in FORBIDDEN_PHRASES if phrase in text.lower()}
    assert not found, f"forbidden phrasing in documentation: {sorted(found)}"







def test_documentation_matches_implementation() -> None:
    assert_documentation_matches()


def test_required_statement_is_present_verbatim() -> None:
    text = normalise(read_documentation())
    assert REQUIRED_STATEMENT in text


def test_documentation_has_exactly_sixteen_numbered_sections() -> None:
    numbers = section_numbers(read_documentation())
    assert numbers == [str(index) for index in range(1, 17)]


def test_documentation_checker_actually_fires() -> None:
    """A negative checker must be shown to be non-vacuous.

    Without this, a checker whose pattern never matched would report success on
    any input at all.
    """

    assert missing("no features here", ["mismatch_rate"]) == {"mismatch_rate"}
    assert missing("mismatch_rate", ["mismatch_rate"]) == set()


    synthetic = "## 1. First\n### 1.1 Not top level\n## 2. Second\n"
    assert section_numbers(synthetic) == ["1", "2"]


    assert "detects all attacks" in "This tool detects all attacks.".lower()


    assert "detects all attacks" not in normalise(read_documentation()).lower()


def test_normalise_preserves_underscores() -> None:
    """Emphasis stripping must never mangle snake_case identifiers."""
    assert normalise("**mismatch_rate**") == "mismatch_rate"
    assert normalise("`verification_state_disturbance_rate`") == (
        "verification_state_disturbance_rate"
    )
