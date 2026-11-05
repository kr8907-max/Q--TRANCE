"""Claim language in the API's own documentation and code.

Milestone 6's criterion-23 guard scans ``docs/security`` and three engine
packages. It does not scan ``docs/api`` or ``backend/api``, which Milestone 7
introduced, so the boundary was unguarded in exactly the layer that publishes it.

This test closes that gap. It uses
:func:`backend.security.check_statement` -- the same checker the API exposes --
rather than a second, weaker pattern list, so a claim that the API would refuse
from a caller is also refused from the API's own documentation.

It lives in ``tests/api`` rather than extending criterion 23 on purpose: that
test is rewritten by the Milestone 6 hardening branch, and a second change to the
same lines would conflict.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from backend.security import check_statement

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
API_DOCS = REPO_ROOT / "docs" / "api"


def _clauses(text: str):
    """Yield clause-sized pieces, so a negation stays with what it negates.

    Splitting per line and then per sentence keeps a negation cue in the same
    piece as the claim it excuses. Splitting only on sentence punctuation would
    let a negation in a later sentence excuse an earlier claim.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for piece in re.split(r"(?<=[.!?])\s+", line):
            piece = piece.strip()
            if piece:
                yield piece


def _documentation_paths() -> list:
    return sorted(API_DOCS.rglob("*.md"))


def test_the_api_documentation_exists_to_scan() -> None:
    assert _documentation_paths(), "no API documentation found; the guard would be vacuous"


@pytest.mark.parametrize("path", _documentation_paths(), ids=lambda p: p.name)
def test_the_api_documentation_makes_no_unsupported_claim(path: pathlib.Path) -> None:
    """No clause may assert a claim the project forbids."""
    violations = []
    for clause in _clauses(path.read_text(encoding="utf-8")):
        result = check_statement(clause)
        if result.verdict.value == "forbidden":
            violations.append((clause[:120], list(result.violations)))
    assert not violations, f"{path.name} asserts forbidden claims: {violations}"


def test_the_reference_document_states_the_boundary() -> None:
    """The claim-language section must stay, and must stay negated."""
    text = (API_DOCS / "api-reference.md").read_text(encoding="utf-8")
    assert "## 6. Claim language" in text
    section = text.split("## 6. Claim language", 1)[1].split("## 7.", 1)[0]



    bullets = [line.strip() for line in section.splitlines() if line.strip().startswith("*")]
    assert len(bullets) >= 4
    for bullet in bullets:
        assert " does not " in bullet, bullet


def test_the_api_layer_code_makes_no_unsupported_claim() -> None:
    """The same check over the API's Python, at string-literal granularity.

    Scanning line by line would false-positive on wrapped string literals, where
    a negation sits on the previous physical line. Reading each string literal as
    a unit avoids that.
    """
    import ast

    api_root = REPO_ROOT / "backend" / "api"
    sources = sorted(api_root.rglob("*.py"))

    assert len(sources) >= 30, f"only {len(sources)} API modules found"

    violations = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for clause in _clauses(node.value):
                result = check_statement(clause)
                if result.verdict.value == "forbidden":
                    violations.append(
                        f"{path.name}:{node.lineno} {clause[:90]!r} {list(result.violations)}"
                    )
    assert not violations, f"the API layer asserts forbidden claims: {violations}"
