"""The Milestone 2 acceptance contract, as executable tests.

Each test maps to a numbered acceptance criterion in the milestone brief
(section 28). Criteria whose behaviour is already covered by a dedicated test
module are deliberately *not* duplicated here; this module covers the
cross-cutting criteria that nothing else checks:

* **#21 documentation matches implementation** -- nothing else asserts that
  ``docs/protocol/reference-qds.md`` still agrees with the code.
* **#22 no unsupported security claims** -- the disclaimer must survive edits.
* **#6 verifier reconstruction** -- checked structurally (AST), so a future
  shortcut that assigns the signer's states into the verifier cannot slip in
  behind an equivalent-looking behavioural test.
* **#16/#17/#18 no attack engine, no threshold detector, no machine learning**
  -- checked by module presence and by AST import analysis rather than by
  grepping text, because text greps match docstrings and guard lists.

Where a criterion is covered elsewhere, the docstring says where.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pytest

from backend.protocol import (
    ALPHABET_SIZE,
    BINDING_DOMAIN,
    CANONICAL_HASH_ALGORITHM,
    DEFAULT_STATE_COUNT,
    PROTOCOL_VERSION,
    STATE_ALPHABET,
    STREAM_DOMAIN,
    TRANSCRIPT_VERSION,
    VERIFICATION_POLICY_METADATA,
    VerifierContext,
    compute_transcript_hash,
    describe_protocol,
    transcript_from_json,
    transcript_to_dict,
    transcript_to_json,
    verify,
)
from backend.protocol.encoding import NIBBLE_ACCEPT_LIMIT
from backend.quantum.states import EIGENSTATE_LABELS, PAULI_MATRICES, get_eigenstate

from tests.protocol.conftest import MESSAGE, VERIFIER_ID

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "protocol" / "reference-qds.md"
PROTOCOL_DIR = REPO_ROOT / "backend" / "protocol"

VERIFY_CONTEXT = VerifierContext(verifier_id=VERIFIER_ID)


def markdown_text() -> str:
    """Return the protocol document as normalised prose.

    Emphasis markers are removed -- ``**``, ``*``, backticks and leading ``>``
    or ``#`` -- and runs of whitespace are collapsed to single spaces, so a
    phrase that wraps across two source lines is still found as one string.
    Underscores are preserved because identifiers such as
    ``DEFAULT_STATE_COUNT`` contain them.
    """
    raw = DOC_PATH.read_text(encoding="utf-8")
    stripped = re.sub(r"\*\*|\*|`|^>+ *|^#+ *", "", raw, flags=re.M)
    return re.sub(r"\s+", " ", stripped)


def documented_hash_algorithm() -> str:
    """Return the hash algorithm the document names, in code form.

    The document writes ``SHA-256``; the code constant is ``sha256``. They are
    the same algorithm, so the comparison normalises case and separator.
    """
    return "SHA-256"


def imported_roots(path: Path) -> set[str]:
    """Return the top-level module names imported by a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return {module.split(".")[0] for module in modules}


def all_python_files() -> list[Path]:
    return sorted(REPO_ROOT.glob("backend/**/*.py")) + sorted(
        REPO_ROOT.glob("tests/**/*.py")
    )







def test_criterion_21_documentation_exists_and_is_substantial() -> None:
    assert DOC_PATH.is_file()
    text = markdown_text()
    for section in (
        "Scope",
        "reference prototype",
        "Session model",
        "Message binding",
        "State alphabet",
        "State-sequence derivation",
        "Signer workflow",
        "Transcript",
        "Verifier workflow",
        "Verification result",
        "Canonical serialization",
        "Protocol version",
        "Assumptions",
        "Security boundaries",
        "does NOT prove",
        "Known limitations",
        "Future replacement points",
    ):
        assert section.lower() in text.lower(), section


def test_criterion_21_documented_constants_match_the_code() -> None:
    """Every constant the document quotes must equal the implemented value."""
    text = markdown_text()
    assert PROTOCOL_VERSION in text
    assert f"DEFAULT_STATE_COUNT = {DEFAULT_STATE_COUNT}" in text
    assert STREAM_DOMAIN in text
    assert BINDING_DOMAIN in text
    assert documented_hash_algorithm() in text
    assert CANONICAL_HASH_ALGORITHM == documented_hash_algorithm().lower().replace(
        "-", ""
    )


    assert NIBBLE_ACCEPT_LIMIT == 2 * ALPHABET_SIZE == 12
    assert f"{NIBBLE_ACCEPT_LIMIT} = 2 × {ALPHABET_SIZE}" in text
    assert str(TRANSCRIPT_VERSION) in text


def test_criterion_21_documented_alphabet_matches_the_code() -> None:
    text = markdown_text()
    for identifier in STATE_ALPHABET:
        assert identifier in text, identifier
    assert f"{ALPHABET_SIZE}" in text


def test_criterion_21_documented_correction_convention_matches_the_code() -> None:
    """The document's stated convention must match the recorded policy."""
    assert VERIFICATION_POLICY_METADATA["correction_convention"] == "Z^m0 . X^m1"
    assert "Z^m0 . X^m1" in markdown_text().replace("·", ".")


def test_criterion_21_documented_encoding_rules_match_the_canonical_module() -> None:
    """The serialization rules the document states must be the implemented ones."""
    from backend.protocol.canonical import CanonicalTypeError, canonical_json

    text = markdown_text()
    assert "NFC" in text
    assert "sort_keys=True" in text
    assert "separators" in text
    assert "ensure_ascii=False" in text

    with pytest.raises(CanonicalTypeError):
        canonical_json({"amplitude": 0.70710678})


def test_criterion_21_documented_binding_is_not_concatenation() -> None:
    """The document claims a structured encoding; the code must honour it."""
    text = markdown_text()
    assert "Why not concatenate" in text
    from backend.protocol import compute_message_binding

    left = compute_message_binding(
        protocol_version=PROTOCOL_VERSION, session_id="ab", nonce="cd", message="m"
    )
    right = compute_message_binding(
        protocol_version=PROTOCOL_VERSION, session_id="abc", nonce="d", message="m"
    )
    assert left != right


def test_criterion_21_protocol_description_matches_the_document() -> None:
    description = describe_protocol()
    text = markdown_text()
    assert description["protocol_version"] in text
    assert documented_hash_algorithm() in text
    assert description["hash_algorithm"] == CANONICAL_HASH_ALGORITHM
    assert list(STATE_ALPHABET) == description["state_alphabet"]







def test_criterion_22_disclaimers_are_present_in_the_document() -> None:
    text = markdown_text()
    assert "not formally proven information-theoretically secure" in text
    assert "not the official Egreen Quanta protocol" in text
    assert "not a standardized QDS protocol" in text
    assert "does not prove information-theoretic security" in text


def test_criterion_22_structured_flags_deny_a_security_claim() -> None:
    description = describe_protocol()
    assert description["formal_security_claim"] is False
    assert description["standardized"] is False
    assert description["kind"] == "reference-prototype-construction"


def test_criterion_22_verifier_always_warns(transcript) -> None:
    """Even an accepted result must not read as a security guarantee."""
    result = verify(transcript, MESSAGE, VERIFY_CONTEXT)
    assert result.accepted
    assert result.verification_warnings
    assert "not unforgeability" in " ".join(result.verification_warnings)


OVERCLAIM_PHRASES = (
    "is information-theoretically secure",
    "proves unconditional security",
    "unconditionally secure because",
    "guarantees unforgeability",
    "is provably secure",
)





NEGATIONS = re.compile(r"\b(not|no|never|nothing|none|cannot|without|fails?)\b")


def affirmative_overclaims(text: str) -> list[str]:
    """Return overclaim phrases that appear in a non-negated sentence."""
    offenders = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lowered = sentence.lower()
        if NEGATIONS.search(lowered):
            continue
        for phrase in OVERCLAIM_PHRASES:
            if phrase in lowered:
                offenders.append(f"{phrase!r} in {sentence.strip()[:70]!r}")
    return offenders


def test_criterion_22_document_does_not_claim_teleportation_implies_security() -> None:
    """No affirmative security claim, anywhere in the document.

    The check is sentence-aware: the phrases above legitimately appear inside
    negated disclaimers, so a bare substring search would produce false alarms.
    """
    assert affirmative_overclaims(markdown_text()) == []


def test_criterion_22_negation_aware_check_actually_detects_a_claim() -> None:
    """Guard against the checker silently passing on everything."""
    assert affirmative_overclaims("This construction is information-theoretically secure.")
    assert affirmative_overclaims(markdown_text()) == []







def test_criterion_06_verifier_derives_expected_states_from_its_own_binding() -> None:
    """No assignment may take the verifier's expectations from the transcript.

    Behaviour is covered by
    ``test_verifier.py::test_verifier_does_not_trust_the_signers_state_sequence``;
    this structural check additionally forbids the shortcut reappearing behind
    a differently shaped behavioural test.
    """
    tree = ast.parse((PROTOCOL_DIR / "verifier.py").read_text(encoding="utf-8"))
    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "expected_states":
                function = getattr(node.value, "func", None)
                first_argument = (
                    getattr(node.value.args[0], "id", None)
                    if getattr(node.value, "args", None)
                    else None
                )
                assignments.append((getattr(function, "id", None), first_argument))

    assert assignments == [("derive_state_sequence", "recomputed_binding")], assignments


def test_criterion_06_verifier_never_reads_the_signer_module() -> None:
    assert "backend.protocol.signer" not in imported_roots(
        PROTOCOL_DIR / "verifier.py"
    )







def test_criterion_16_no_detection_subpackage_exists() -> None:
    """Milestone 2 asserted that no attack, noise, detection, security, API or
    frontend subpackage existed.

    Milestone 3 legitimately introduced ``backend.noise`` and
    ``backend.attacks``; Milestone 4 legitimately introduces
    ``backend.detection``; Milestone 5 legitimately introduces
    ``backend.security``; Milestone 7 legitimately introduces ``backend.api``.
    Those names are therefore no longer forbidden *as packages*. The property
    this criterion protects is unchanged and still binding: the **protocol
    layer** contains no detection engine, no security layer, no API and no
    frontend, and it depends on none of the layers above it. Detection sits above
    the protocol layer, never inside it.

    The dependency half is checked by AST rather than by grepping text, because a
    text grep also matches docstrings and guard lists. M3's, M4's and M5's own
    acceptance tests cover the attack-layer, detection-layer and security-layer
    separation.

    Removing a name from the package list does not weaken the guard: the name is
    moved into the forbidden-import tuple below, so the layer is protected by
    dependency rather than by absence. ``api`` has now made that move; only
    ``frontend`` remains forbidden as a package, because Milestone 8 has not been
    started.
    """
    for name in ("frontend",):
        assert not (REPO_ROOT / "backend" / name).exists(), name





    forbidden = (
        "backend.api",
        "backend.detection",
        "backend.calibration",
        "backend.evaluation",
        "backend.security",
        "backend.attacks",
        "backend.noise",
        "backend.simulation",
    )
    offenders: set[str] = set()
    for path in PROTOCOL_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden):
                        offenders.add(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0 and module.startswith(forbidden):
                    offenders.add(f"{path.name}: from {module}")
    assert not offenders, sorted(offenders)


@pytest.mark.parametrize(
    "forbidden",
    ["sklearn", "tensorflow", "torch", "keras", "xgboost", "lightgbm", "jax"],
)
def test_criterion_18_no_machine_learning_library_is_imported(forbidden: str) -> None:
    """AST-based, so guard lists that merely name these libraries do not match."""
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in all_python_files()
        if forbidden in imported_roots(path)
    ]
    assert offenders == [], offenders


def test_criterion_17_no_threshold_or_rate_statistics_are_reported(transcript) -> None:
    payload = json.dumps(verify(transcript, MESSAGE, VERIFY_CONTEXT).to_dict())
    for forbidden in (
        "threshold",
        "false_positive",
        "false_negative",
        "detection_rate",
        "attack_label",
        "classifier",
    ):
        assert forbidden not in payload, forbidden


def test_criterion_17_verification_result_exposes_only_raw_counts(transcript) -> None:
    result = verify(transcript, MESSAGE, VERIFY_CONTEXT)
    assert set(result.basis_counts) <= {"X", "Y", "Z"}
    assert set(result.measurement_summary) == {"checked", "matched", "mismatched"}
    assert result.mismatch_count == 0


def test_criterion_16_protocol_layer_imports_no_future_module() -> None:
    forbidden = {
        "backend.attacks",
        "backend.detection",
        "backend.noise",
        "backend.security",
        "backend.api",
        "backend.frontend",
    }
    offenders = []
    for path in sorted(PROTOCOL_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            for name in names:
                if any(name == item or name.startswith(item + ".") for item in forbidden):
                    offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders







def test_criterion_19_m1_test_suite_is_present() -> None:
    """The authoritative check is the full pytest run, which includes all 213
    M1 tests. This asserts the M1 suite is still part of the project.

    The criterion names the seven M1 test modules rather than asserting a file
    count, so a later milestone adding its own test module to this directory
    (Milestone 5 added ``test_cache.py``) does not read as a regression. Naming
    the files is the stronger check: a count can be satisfied by any seven files,
    whereas this fails if even one M1 module is renamed or removed.
    """
    m1_test_modules = {
        "test_bell.py",
        "test_bit_ordering.py",
        "test_correction.py",
        "test_density.py",
        "test_measurements.py",
        "test_states.py",
        "test_teleport.py",
    }
    present = {
        path.name
        for path in (REPO_ROOT / "tests" / "quantum").glob("test_*.py")
    }
    missing = sorted(m1_test_modules - present)
    assert not missing, f"M1 quantum test modules missing: {missing}"
    assert (REPO_ROOT / "tests" / "quantum" / "statutil.py").is_file()


def test_criterion_19_m1_quantum_api_behaves() -> None:
    """A compact regression guard on the verified core M2 builds on."""
    assert len(EIGENSTATE_LABELS) == 6
    for label in EIGENSTATE_LABELS:
        state = get_eigenstate(label)
        operator = PAULI_MATRICES[state.basis]
        assert np.allclose(
            operator @ state.vector, state.eigenvalue * state.vector, atol=1e-12
        )


def test_criterion_19_m2_does_not_import_into_the_quantum_layer() -> None:
    """AST-based: the quantum core must not import the protocol layer."""
    offenders = []
    for path in sorted((REPO_ROOT / "backend" / "quantum").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("backend.protocol"):
                    offenders.append(f"{path.name}: {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("backend.protocol"):
                        offenders.append(f"{path.name}: {alias.name}")
    assert offenders == [], offenders







@pytest.mark.parametrize(
    "module",
    [
        "test_architecture",
        "test_binding",
        "test_canonical",
        "test_encoding",
        "test_end_to_end",
        "test_negative",
        "test_session",
        "test_signer",
        "test_transcript",
        "test_verifier",
    ],
)
def test_criterion_20_m2_test_module_exists(module: str) -> None:
    assert (REPO_ROOT / "tests" / "protocol" / f"{module}.py").is_file(), module







def test_criteria_01_to_15_contract_holds_for_a_round_tripped_transcript(
    transcript,
) -> None:
    """The milestone's core contract, asserted once against a real transcript.

    Detailed coverage lives in ``test_signer``, ``test_verifier``,
    ``test_transcript`` and ``test_negative``; this is the summary that would
    fail first if the contract as a whole regressed.
    """

    wire = transcript_to_json(transcript)
    restored = transcript_from_json(wire)
    assert transcript_to_json(restored) == wire
    assert verify(restored, MESSAGE, VERIFY_CONTEXT).accepted


    assert restored.transcript_hash == compute_transcript_hash(restored.payload())


    assert restored.message_binding and restored.message_hash


    base = transcript_to_dict(transcript)

    def resealed(**overrides) -> dict:
        payload = {**base, **overrides}
        payload.pop("transcript_hash")
        payload["transcript_hash"] = compute_transcript_hash(payload)
        return payload

    assert not verify({**base, "transcript_hash": "0" * 64}, MESSAGE, VERIFY_CONTEXT).accepted
    assert not verify(base, MESSAGE + "!", VERIFY_CONTEXT).accepted
    assert not verify(resealed(nonce="f" * 64), MESSAGE, VERIFY_CONTEXT).accepted
    assert not verify(resealed(session_id="f" * 32), MESSAGE, VERIFY_CONTEXT).accepted
    assert not verify(
        resealed(protocol_version="RQDS-TP-9.9"), MESSAGE, VERIFY_CONTEXT
    ).accepted
