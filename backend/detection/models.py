"""The observable detection input contract and the detector's shared models.

Milestone 4 -- observable threat detection engine.

The isolation rule
------------------
This package must never import :mod:`backend.attacks`, never read
``GroundTruthMetadata``, and never look at an attack label. The detector may
consume **only** what a legitimate verifier can observe. That is enforced three
ways:

1. structurally, by :class:`ObservableDetectionInput` having no field that could
   carry an attack type, an attack fraction, a noise strength or an oracle
   label;
2. by a static import check over ``backend/detection`` in the test suite;
3. by a subprocess check that ``import backend.detection`` does not put
   ``backend.attacks`` into ``sys.modules``.

The detector asks "what evidence is observable?", never "what attack was
injected?".

Why the adapter is duck-typed
-----------------------------
:meth:`ObservableDetectionInput.from_observable` reads attributes off whatever
observable evidence object it is handed. It deliberately does **not** import
:mod:`backend.simulation`, because importing that package runs its
``__init__``, which imports the experiment runner, which imports
:mod:`backend.attacks`. A detector that imported the simulator would therefore
transitively depend on the attack layer even though it named none of it. The
detector depends on the *shape* of observable evidence, not on the package that
happens to produce it.

What is deliberately absent, and why
------------------------------------
``ObservableExperimentData`` carries three fields the detector must ignore even
though they sit in the observable half:

``scenario_id``
    Milestone 3 scenario identifiers encode experiment parameters (for example
    ``"base-attack-0.5"``). Reading one would be a label leak in disguise.
``simulator_seed``
    Not observable to a real verifier; it exists so a simulation can be
    replayed.
``mean_channel_disturbance``
    A trace distance between the *ideal* received state and the actual one. A
    real verifier does not hold the ideal received state -- reconstructing it
    requires the signer's private knowledge of the channel -- so this number is
    a simulation artefact, not an observation. The engine instead derives
    disturbance from ``probability_expected``, the projective match probability
    the verifier itself computes, which *is* observable.

``runtime_seconds`` is likewise ignored: it is a property of the machine, not
of the protocol.

Protocol identity fields (session, nonce, binding, transcript hash) come from
the transcript the verifier received, which is by definition observable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Tuple

from backend.protocol.models import PROTOCOL_VERSION
from backend.protocol.verifier import MEASUREMENT_TOLERANCE

from backend.detection.statistics import DEFAULT_CONFIDENCE

__all__ = [
    "DEFAULT_MEASUREMENT_TOLERANCE",
    "DEFAULT_PROTOCOL_VERSIONS",
    "EvidenceCategory",
    "Severity",
    "CalibrationState",
    "OverallStatus",
    "DetectionError",
    "DetectionInputError",
    "DetectorParameters",
    "StateEvidence",
    "VerificationEvidence",
    "ObservableDetectionInput",
]





DEFAULT_MEASUREMENT_TOLERANCE = MEASUREMENT_TOLERANCE


DEFAULT_PROTOCOL_VERSIONS: Tuple[str, ...] = (PROTOCOL_VERSION,)


class DetectionError(Exception):
    """Base class for detection-engine failures."""


class DetectionInputError(DetectionError, ValueError):
    """Raised for a *programming* error in constructing detection input.

    Never raised for untrusted or malformed protocol data: malformed evidence is
    a finding, not an exception. See the module docstring of
    :mod:`backend.detection.consistency`.
    """


class EvidenceCategory(str, Enum):
    """The kinds of finding the engine can emit.

    The categories are deliberately orthogonal. In particular a measurement
    mismatch is *not* reported as forgery: forgery evidence comes from
    verification inconsistency, and measurement deviation is reported under the
    quantum/channel categories.
    """

    TRANSCRIPT_INTEGRITY = "TRANSCRIPT_INTEGRITY"
    REPLAY = "REPLAY"
    SIGNER_AUTHORIZATION = "SIGNER_AUTHORIZATION"
    VERIFIER_AUTHORIZATION = "VERIFIER_AUTHORIZATION"
    QUANTUM_MEASUREMENT_ANOMALY = "QUANTUM_MEASUREMENT_ANOMALY"
    CHANNEL_ANOMALY = "CHANNEL_ANOMALY"
    SIGNATURE_VERIFICATION_ANOMALY = "SIGNATURE_VERIFICATION_ANOMALY"
    CONSISTENCY_ANOMALY = "CONSISTENCY_ANOMALY"





DETERMINISTIC_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.TRANSCRIPT_INTEGRITY,
    EvidenceCategory.REPLAY,
    EvidenceCategory.SIGNER_AUTHORIZATION,
    EvidenceCategory.VERIFIER_AUTHORIZATION,
    EvidenceCategory.SIGNATURE_VERIFICATION_ANOMALY,
    EvidenceCategory.CONSISTENCY_ANOMALY,
)



STATISTICAL_CATEGORIES: Tuple[EvidenceCategory, ...] = (
    EvidenceCategory.QUANTUM_MEASUREMENT_ANOMALY,
    EvidenceCategory.CHANNEL_ANOMALY,
)


class Severity(str, Enum):
    """How strongly the evidence bears on the session.

    ``UNCALIBRATED`` is a first-class value, not a placeholder. It means "the
    evidence is real and reported, but no calibrated rule maps it to a severity
    yet". Every statistical finding defaults to it.
    """

    UNCALIBRATED = "UNCALIBRATED"
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CalibrationState(str, Enum):
    """Whether a finding's strength rests on a calibrated reference."""


    UNCALIBRATED = "UNCALIBRATED"

    CALIBRATED = "CALIBRATED"


class OverallStatus(str, Enum):
    """The engine's top-level explanation of a session.

    The status is a *category* statement, never a percentage: it says which
    family of findings fired, not how close a number came to a limit.
    """

    CLEAR = "CLEAR"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"
    AUTHORIZATION_VIOLATION = "AUTHORIZATION_VIOLATION"
    QUANTUM_ANOMALY = "QUANTUM_ANOMALY"
    MULTIPLE_FINDINGS = "MULTIPLE_FINDINGS"


@dataclass(frozen=True)
class DetectorParameters:
    """Configured detector parameters.

    Everything here is either a *definition* (what counts as "exactly the
    expected state", which protocol versions are spoken) or an **optional
    caller-supplied reference expectation**.

    There are no absolute thresholds. When a reference is absent the
    corresponding evidence is emitted with :attr:`Severity.UNCALIBRATED`,
    because inventing a decision rule is exactly what the milestone brief
    forbids. Milestone 5 supplies calibrated references.
    """



    match_tolerance: float = DEFAULT_MEASUREMENT_TOLERANCE


    expected_protocol_versions: Tuple[str, ...] = DEFAULT_PROTOCOL_VERSIONS


    reference_mismatch_rate: float | None = None
    reference_disturbance_rate: float | None = None
    reference_fidelity: float | None = None



    confidence: float = DEFAULT_CONFIDENCE

    def validate(self) -> "DetectorParameters":
        if isinstance(self.match_tolerance, bool) or not isinstance(
            self.match_tolerance, (int, float)
        ):
            raise DetectionInputError(
                f"match_tolerance must be a real number, got "
                f"{type(self.match_tolerance).__name__}"
            )
        if not 0.0 <= float(self.match_tolerance) <= 1.0:
            raise DetectionInputError(
                f"match_tolerance must lie in [0, 1], got {self.match_tolerance!r}"
            )
        if not self.expected_protocol_versions:
            raise DetectionInputError("expected_protocol_versions must not be empty")
        for version in self.expected_protocol_versions:
            if not isinstance(version, str) or not version:
                raise DetectionInputError(
                    f"expected protocol versions must be non-empty strings, got "
                    f"{version!r}"
                )
        for name, value in (
            ("reference_mismatch_rate", self.reference_mismatch_rate),
            ("reference_disturbance_rate", self.reference_disturbance_rate),
            ("reference_fidelity", self.reference_fidelity),
        ):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DetectionInputError(
                    f"{name} must be a real number or None, got "
                    f"{type(value).__name__}"
                )
            if not 0.0 <= float(value) <= 1.0:
                raise DetectionInputError(
                    f"{name} must lie in [0, 1], got {value!r}"
                )
        if not 0.0 < float(self.confidence) < 1.0:
            raise DetectionInputError(
                f"confidence must lie in (0, 1), got {self.confidence!r}"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_tolerance": float(self.match_tolerance),
            "expected_protocol_versions": list(self.expected_protocol_versions),
            "reference_mismatch_rate": self.reference_mismatch_rate,
            "reference_disturbance_rate": self.reference_disturbance_rate,
            "reference_fidelity": self.reference_fidelity,
            "confidence": float(self.confidence),
        }


def _is_real_number(value: Any) -> bool:
    """Return ``True`` for an ``int``/``float`` that is not a ``bool`` or NaN."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value == value


def _coerce_int(value: Any) -> int | None:
    """Return ``value`` as an ``int``, or ``None`` when it is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


@dataclass(frozen=True)
class StateEvidence:
    """One observable per-state measurement record.

    Fields mirror what the verifier sees: which state index it checked, which
    basis it measured in, which eigenvalue the reference expects,
    ``probability_expected`` -- the analytic projective probability of that
    eigenvalue, computed by the verifier itself -- and whether the outcome
    agreed.

    Any field may be ``None`` or malformed. That is intentional: the engine must
    be *safe under malformed input*, so unusable records are excluded from
    denominators and counted, rather than raising.
    """

    index: int
    basis: str | None = None
    expected_bit: int | None = None
    probability_expected: float | None = None
    matched: bool | None = None

    @property
    def usable(self) -> bool:
        """Return whether this record can contribute to a statistic.

        A record is usable when every field is present and well formed:
        ``basis`` a string, ``expected_bit`` exactly 0 or 1, ``matched`` a
        ``bool``, and ``probability_expected`` a real number in ``[0, 1]``.
        """
        if not isinstance(self.basis, str) or not self.basis:
            return False
        if self.expected_bit not in (0, 1) or isinstance(self.expected_bit, bool):
            return False
        if not isinstance(self.matched, bool):
            return False
        if not _is_real_number(self.probability_expected):
            return False
        return 0.0 <= float(self.probability_expected) <= 1.0

    @classmethod
    def from_observation(cls, observation: Any) -> "StateEvidence":
        """Build a record from any object exposing the observation fields.

        Duck-typed for the same reason the whole adapter is: see the module
        docstring. Missing attributes become ``None`` and the record is then
        reported as unusable rather than silently treated as a match.
        """
        return cls(
            index=_coerce_int(getattr(observation, "index", None)) or 0,
            basis=getattr(observation, "basis", None),
            expected_bit=getattr(observation, "expected_bit", None),
            probability_expected=getattr(observation, "probability_expected", None),
            matched=getattr(observation, "matched", None),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "basis": self.basis,
            "expected_bit": self.expected_bit,
            "probability_expected": self.probability_expected,
            "matched": self.matched,
        }


@dataclass(frozen=True)
class VerificationEvidence:
    """The observable half of a Milestone 2 :class:`VerificationResult`.

    Only the flags, the recorded errors and the raw counts are kept. There is no
    field for "which attack caused this", because the verifier does not know.
    """

    available: bool = False
    accepted: bool | None = None
    session_valid: bool | None = None
    message_valid: bool | None = None
    transcript_valid: bool | None = None
    state_sequence_valid: bool | None = None
    measurement_valid: bool | None = None
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    declared_mismatch_count: int | None = None
    declared_basis_counts: Mapping[str, int] = field(default_factory=dict)
    measurement_summary: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def unavailable(cls) -> "VerificationEvidence":
        """Return the record used when no verification result was supplied."""
        return cls(available=False)

    @classmethod
    def from_result(cls, result: Any) -> "VerificationEvidence":
        """Build a record from a :class:`VerificationResult`-shaped object."""
        if result is None:
            return cls.unavailable()
        return cls(
            available=True,
            accepted=getattr(result, "accepted", None),
            session_valid=getattr(result, "session_valid", None),
            message_valid=getattr(result, "message_valid", None),
            transcript_valid=getattr(result, "transcript_valid", None),
            state_sequence_valid=getattr(result, "state_sequence_valid", None),
            measurement_valid=getattr(result, "measurement_valid", None),
            errors=tuple(getattr(result, "verification_errors", ()) or ()),
            warnings=tuple(getattr(result, "verification_warnings", ()) or ()),
            declared_mismatch_count=getattr(result, "mismatch_count", None),
            declared_basis_counts=dict(getattr(result, "basis_counts", {}) or {}),
            measurement_summary=dict(
                getattr(result, "measurement_summary", {}) or {}
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "accepted": self.accepted,
            "session_valid": self.session_valid,
            "message_valid": self.message_valid,
            "transcript_valid": self.transcript_valid,
            "state_sequence_valid": self.state_sequence_valid,
            "measurement_valid": self.measurement_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "declared_mismatch_count": self.declared_mismatch_count,
            "declared_basis_counts": dict(self.declared_basis_counts),
            "measurement_summary": dict(self.measurement_summary),
        }


@dataclass(frozen=True)
class ObservableDetectionInput:
    """Everything a detector may legitimately observe about one session.

    The contract in one sentence: **if a legitimate verifier cannot see it, it
    is not here.**

    Fields are grouped by where the verifier got them:

    identity
        Read from the transcript the verifier received. ``None`` when the
        transcript was absent or unparseable.
    verifier knowledge
        The message the verifier was asked to check, the identity it believes
        it has, and the protocol version it is willing to speak. These are
        supplied by the caller in Milestone 2 and are never read out of the
        transcript, so a transcript cannot talk the verifier into a different
        protocol.
    authorization
        The authorised identity sets the verification system holds, plus the
        booleans the verifier recorded. The engine recomputes the membership
        tests and reports any disagreement with the recorded flags.
    transcript material
        The declared payload, so the detector can recompute the canonical
        transcript hash itself instead of trusting the stored one, plus the
        parse error when the payload could not be parsed at all.
    measurement
        The per-state observations and the declared state count.
    verification
        The verifier's own structured outcome.

    There is no field for an attack type, an attack fraction, a noise strength,
    a ground-truth flag, or an oracle label, and there never will be one: adding
    one would break the isolation the milestone exists to establish.
    """


    session_id: str | None = None
    nonce: str | None = None
    protocol_version: str | None = None
    message_binding: str | None = None
    declared_transcript_hash: str | None = None
    signer_id: str | None = None
    verifier_id: str | None = None
    created_at: str | None = None


    message: str | None = None
    verifier_context_id: str | None = None
    expected_protocol_version: str | None = None


    authorized_signers: Tuple[str, ...] = ()
    authorized_verifiers: Tuple[str, ...] = ()
    reported_signer_authorized: bool | None = None
    reported_verifier_authorized: bool | None = None


    transcript_payload: Mapping[str, Any] | None = None
    transcript_parse_error: str | None = None


    states: Tuple[StateEvidence, ...] = ()
    declared_state_count: int | None = None
    measurement_mode: str = "unknown"
    basis_counts: Mapping[str, int] = field(default_factory=dict)


    verification: VerificationEvidence = field(default_factory=VerificationEvidence.unavailable)





    @property
    def observed_state_count(self) -> int:
        """Return the number of measurement records supplied."""
        return len(self.states)

    @property
    def transcript_supplied(self) -> bool:
        """Return whether a transcript payload or a parse error was supplied."""
        return self.transcript_payload is not None or self.transcript_parse_error is not None

    @classmethod
    def from_observable(
        cls,
        observable: Any,
        *,
        transcript: Any = None,
        message: str | None = None,
        verifier_context: Any = None,
    ) -> "ObservableDetectionInput":
        """Build the contract from observable experiment evidence.

        ``observable`` is duck-typed (see the module docstring). ``transcript``
        may be a Milestone 2 :class:`Transcript` or already-plain transcript
        data; it is the artifact the verifier received, so it is observable.
        ``verifier_context`` supplies the verifier's independent knowledge.

        Nothing is read from a ground-truth object, and no argument of this
        method accepts one.
        """
        if observable is None:
            raise DetectionInputError("observable evidence must not be None")

        payload, parse_error = _transcript_payload(transcript)

        states = tuple(
            StateEvidence.from_observation(item)
            for item in (getattr(observable, "states", ()) or ())
        )

        return cls(
            session_id=_string_or_none(payload.get("session_id")) if payload else None,
            nonce=_string_or_none(payload.get("nonce")) if payload else None,
            protocol_version=(
                _string_or_none(payload.get("protocol_version"))
                if payload
                else _string_or_none(getattr(observable, "protocol_version", None))
            ),
            message_binding=(
                _string_or_none(payload.get("message_binding")) if payload else None
            ),
            declared_transcript_hash=(
                _string_or_none(payload.get("transcript_hash")) if payload else None
            ),
            signer_id=_string_or_none(payload.get("signer_id")) if payload else None,
            verifier_id=_string_or_none(payload.get("verifier_id")) if payload else None,
            created_at=_string_or_none(payload.get("created_at")) if payload else None,
            message=message,
            verifier_context_id=_string_or_none(
                getattr(verifier_context, "verifier_id", None)
            ),
            expected_protocol_version=_string_or_none(
                getattr(verifier_context, "expected_protocol_version", None)
            ),
            authorized_signers=tuple(
                getattr(
                    getattr(observable, "authorization", None),
                    "authorized_signers",
                    (),
                )
                or ()
            ),
            authorized_verifiers=tuple(
                getattr(
                    getattr(observable, "authorization", None),
                    "authorized_verifiers",
                    (),
                )
                or ()
            ),
            reported_signer_authorized=_bool_or_none(
                getattr(
                    getattr(observable, "authorization", None),
                    "signer_authorized",
                    None,
                )
            ),
            reported_verifier_authorized=_bool_or_none(
                getattr(
                    getattr(observable, "authorization", None),
                    "verifier_authorized",
                    None,
                )
            ),
            transcript_payload=payload,
            transcript_parse_error=parse_error,
            states=states,
            declared_state_count=_coerce_int(
                payload.get("state_count") if payload else None
            )
            or _coerce_int(getattr(observable, "state_count", None)),
            measurement_mode=str(
                getattr(observable, "measurement_mode", "unknown") or "unknown"
            ),
            basis_counts={
                str(key): int(value)
                for key, value in (
                    getattr(observable, "basis_counts", {}) or {}
                ).items()
            },
            verification=VerificationEvidence.from_result(
                getattr(observable, "verification", None)
            ),
        )

    @classmethod
    def with_authorization(
        cls,
        base: "ObservableDetectionInput",
        observations: Any,
    ) -> "ObservableDetectionInput":
        """Return ``base`` with authorization bookkeeping attached.

        Kept separate because :class:`ObservableExperimentData` stores the
        authorization observations in their own object; the engine needs both
        the authorized sets and the reported booleans.
        """
        from dataclasses import replace

        return replace(
            base,
            authorized_signers=tuple(
                getattr(observations, "authorized_signers", ()) or ()
            ),
            authorized_verifiers=tuple(
                getattr(observations, "authorized_verifiers", ()) or ()
            ),
            reported_signer_authorized=_bool_or_none(
                getattr(observations, "signer_authorized", None)
            ),
            reported_verifier_authorized=_bool_or_none(
                getattr(observations, "verifier_authorized", None)
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "nonce": self.nonce,
            "protocol_version": self.protocol_version,
            "message_binding": self.message_binding,
            "declared_transcript_hash": self.declared_transcript_hash,
            "signer_id": self.signer_id,
            "verifier_id": self.verifier_id,
            "created_at": self.created_at,
            "message": self.message,
            "verifier_context_id": self.verifier_context_id,
            "expected_protocol_version": self.expected_protocol_version,
            "authorized_signers": list(self.authorized_signers),
            "authorized_verifiers": list(self.authorized_verifiers),
            "transcript_parse_error": self.transcript_parse_error,
            "transcript_supplied": self.transcript_supplied,
            "states": [state.to_dict() for state in self.states],
            "declared_state_count": self.declared_state_count,
            "observed_state_count": self.observed_state_count,
            "measurement_mode": self.measurement_mode,
            "basis_counts": dict(self.basis_counts),
            "verification": self.verification.to_dict(),
        }


def _string_or_none(value: Any) -> str | None:
    """Return ``value`` if it is a ``str``, else ``None``."""
    return value if isinstance(value, str) else None


def _bool_or_none(value: Any) -> bool | None:
    """Return ``value`` if it is a ``bool``, else ``None``."""
    return value if isinstance(value, bool) else None


def _transcript_payload(transcript: Any) -> tuple[Dict[str, Any] | None, str | None]:
    """Return ``(payload, parse_error)`` for whatever transcript was handed over.

    Accepts ``None``, a Milestone 2 ``Transcript`` (anything with a ``to_dict``
    returning a mapping) or plain data. A malformed payload is *reported*, never
    raised: malformed evidence is a finding.
    """
    if transcript is None:
        return None, None
    if isinstance(transcript, Mapping):
        return dict(transcript), None
    to_dict = getattr(transcript, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"transcript.to_dict() failed: {type(exc).__name__}"
        if isinstance(data, Mapping):
            return dict(data), None
        return None, f"transcript.to_dict() returned {type(data).__name__}"
    return None, f"unsupported transcript type {type(transcript).__name__}"
