"""Attack-scenario abstraction and the observable / ground-truth split.

The rule this module exists to enforce
--------------------------------------
An attack must produce a **causal effect** on the simulated protocol, channel,
state or transcript. It must never be a boolean that makes the runner announce
"attack detected". The runner therefore has no branch anywhere that reads an
attack label and changes its behaviour: it applies an attack to real material
and then runs the ordinary M2 verification path on the result.

The second rule, equally important
----------------------------------
:class:`AttackOutcome` returns *both* the modified material **and** the attack's
internal ground truth, as two clearly separate things:

* ``received_states``, ``transcript``, ``verifier_context`` and
  ``authorization`` are **observable** -- they are what a verifier can actually
  see, and they are the only attack outputs that reach
  ``ObservableExperimentData``.
* ``ground_truth`` is a plain description of what the attacker did. It is
  recorded for benchmarking and is stored in
  ``GroundTruthMetadata``. Nothing in the observable path reads it.

A future detection engine may consume ``ObservableExperimentData`` and must
never need ``GroundTruthMetadata``.

What an attacker may know
-------------------------
:class:`AttackContext` deliberately does **not** carry the verifier's expected
state sequence. An attacker on a quantum channel does not hold the receiver's
expectations, and giving them to the attack layer would make every attack
trivially "successful" and the whole simulation meaningless. Each attack module
documents precisely what its attacker knows and does not know.

Dependency direction
--------------------
``backend.attacks`` imports ``backend.quantum``, ``backend.protocol`` and
``backend.noise``. It imports **nothing** from a detection layer, because no
detection layer exists and none may be added in this milestone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Mapping, Tuple

import numpy as np

from backend.protocol.models import Session, Transcript, VerifierContext

__all__ = [
    "VALID_ATTACK_TYPES",
    "FRACTIONAL_ATTACK_TYPES",
    "AttackValidationError",
    "AttackConfig",
    "AuthorizationContext",
    "AttackContext",
    "AttackOutcome",
    "AttackScenario",
    "require_fraction",
    "validate_seed",
    "select_targets",
    "reseal_transcript",
    "as_state_matrices",
]


VALID_ATTACK_TYPES: Tuple[str, ...] = (
    "none",
    "forgery",
    "impersonation",
    "unauthorized_verification",
    "replay",
    "intercept_resend",
    "channel_tampering",
)





FRACTIONAL_ATTACK_TYPES: Tuple[str, ...] = (
    "intercept_resend",
    "channel_tampering",
)


class AttackValidationError(ValueError):
    """Raised when an attack parameter is invalid or unsupported."""


def require_fraction(value: Any, label: str = "fraction") -> float:
    """Return ``value`` as a float in ``[0, 1]``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AttackValidationError(
            f"{label} must be a real number in [0, 1], got {type(value).__name__}"
        )
    number = float(value)
    if not np.isfinite(number):
        raise AttackValidationError(f"{label} must be finite, got {value!r}")
    if not 0.0 <= number <= 1.0:
        raise AttackValidationError(f"{label} must lie in [0, 1], got {number!r}")
    return number


def validate_seed(value: Any, label: str = "seed") -> int:
    """Return ``value`` as a non-negative integer seed."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AttackValidationError(
            f"{label} must be an integer, got {type(value).__name__}"
        )
    if value < 0:
        raise AttackValidationError(f"{label} must be non-negative, got {value}")
    return value


@dataclass(frozen=True)
class AttackConfig:
    """Configuration of an attack scenario.

    ``fraction`` is the share of signature states the attack touches. It is an
    **experiment sweep value**, not an acceptance threshold: setting it to 0.10
    does not mean "10% is tolerable", it means "this run tampered with about a
    tenth of the states".

    ``seed`` seeds only the attack's own sampling. It is independent of the
    scenario seed and of the cryptographic session identifiers.
    """

    attack_type: str = "none"
    fraction: float = 0.0
    seed: int = 0
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> "AttackConfig":
        if (
            not isinstance(self.attack_type, str)
            or self.attack_type not in VALID_ATTACK_TYPES
        ):
            raise AttackValidationError(
                f"attack_type must be one of {list(VALID_ATTACK_TYPES)}, "
                f"got {self.attack_type!r}"
            )
        require_fraction(self.fraction)
        validate_seed(self.seed)
        if not isinstance(self.parameters, Mapping):
            raise AttackValidationError(
                f"parameters must be a mapping, got {type(self.parameters).__name__}"
            )
        if self.attack_type not in FRACTIONAL_ATTACK_TYPES and float(self.fraction) != 0.0:
            raise AttackValidationError(
                f"attack_type {self.attack_type!r} does not act on a subset of "
                f"states, so fraction must be 0.0, got {self.fraction!r}"
            )
        if self.attack_type == "none" and self.parameters:
            raise AttackValidationError(
                "attack_type 'none' takes no parameters, got "
                f"{sorted(self.parameters)}"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "fraction": float(self.fraction),
            "seed": int(self.seed),
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AttackConfig":
        if not isinstance(data, dict):
            raise AttackValidationError(
                f"attack config must be an object, got {type(data).__name__}"
            )
        unknown = sorted(
            set(data) - {"attack_type", "fraction", "seed", "parameters"}
        )
        if unknown:
            raise AttackValidationError(f"attack config has unknown fields {unknown}")
        config = cls(
            attack_type=data.get("attack_type", "none"),
            fraction=data.get("fraction", 0.0),
            seed=data.get("seed", 0),
            parameters=dict(data.get("parameters", {})),
        )
        return config.validate()


@dataclass(frozen=True)
class AuthorizationContext:
    """Which identities are authorised for a session.

    This is *protocol authorization semantics*, not threat detection: it is a
    deterministic membership test on the identities a session declares, of the
    same kind as M2's ``verifier_id`` check. There is no threshold and no
    statistic here.

    Modelling it explicitly is what lets impersonation ("someone claims to be
    Alice") be kept distinct from unauthorized verification ("Bob is not
    entitled to check this session"), as the project audit required.
    """

    authorized_signers: FrozenSet[str]
    authorized_verifiers: FrozenSet[str]

    def __post_init__(self) -> None:
        for name, values in (
            ("authorized_signers", self.authorized_signers),
            ("authorized_verifiers", self.authorized_verifiers),
        ):
            if not isinstance(values, frozenset) or not values:
                raise AttackValidationError(
                    f"{name} must be a non-empty frozenset, got {values!r}"
                )

    def signer_authorized(self, signer_id: str) -> bool:
        return signer_id in self.authorized_signers

    def verifier_authorized(self, verifier_id: str) -> bool:
        return verifier_id in self.authorized_verifiers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized_signers": sorted(self.authorized_signers),
            "authorized_verifiers": sorted(self.authorized_verifiers),
        }

    @classmethod
    def from_session(
        cls,
        session: Session,
        *,
        extra_verifiers: Tuple[str, ...] = (),
    ) -> "AuthorizationContext":
        """Return the context in which only the session's own parties are authorised."""
        return cls(
            authorized_signers=frozenset({session.signer_id}),
            authorized_verifiers=frozenset({session.verifier_id, *extra_verifiers}),
        )


@dataclass(frozen=True)
class AttackContext:
    """The material an attack acts on.

    Contract: ``received_states`` are 2x2 density matrices. The experiment
    runner converts the M1 branch decomposition's amplitude vectors once, before
    building the context; attacks that modify states still coerce defensively so
    they cannot be misused.

    Note what is absent: the verifier's expected state sequence. An attacker on
    the channel does not have it. Attacks that need to derive a state sequence
    (forgery) must do so from public protocol data, exactly as a real attacker
    would, and must document that capability.
    """

    message: str
    session: Session
    transcript: Transcript
    received_states: Tuple[np.ndarray, ...]
    verifier_context: VerifierContext
    authorization: AuthorizationContext
    rng: np.random.Generator

    def with_material(
        self,
        *,
        received_states: Tuple[np.ndarray, ...] | None = None,
        transcript: Transcript | None = None,
        verifier_context: VerifierContext | None = None,
        authorization: AuthorizationContext | None = None,
    ) -> "AttackContext":
        """Return a copy with some material replaced, keeping the RNG stream."""
        return AttackContext(
            message=self.message,
            session=self.session,
            transcript=self.transcript if transcript is None else transcript,
            received_states=(
                self.received_states if received_states is None else received_states
            ),
            verifier_context=(
                self.verifier_context if verifier_context is None else verifier_context
            ),
            authorization=(
                self.authorization if authorization is None else authorization
            ),
            rng=self.rng,
        )


@dataclass(frozen=True)
class AttackOutcome:
    """The result of applying an attack: modified material plus ground truth.

    The first four fields are observable. ``ground_truth`` is not, and the
    experiment runner copies it into ``GroundTruthMetadata`` only.
    """

    received_states: Tuple[np.ndarray, ...]
    transcript: Transcript
    verifier_context: VerifierContext
    authorization: AuthorizationContext
    ground_truth: Mapping[str, Any]

    def observable_summary(self) -> Dict[str, Any]:
        """Return a description of the observable material only.

        Used by tests to assert that no ground-truth field can reach the
        observable path.
        """
        return {
            "state_count": len(self.received_states),
            "transcript_hash": self.transcript.transcript_hash,
            "signer_id": self.transcript.signer_id,
            "verifier_id": self.transcript.verifier_id,
            "verifier_context_id": self.verifier_context.verifier_id,
            "authorization": self.authorization.to_dict(),
        }


class AttackScenario(ABC):
    """A reference attack on the simulated protocol.

    Subclasses implement :meth:`apply`; the base class validates the
    configuration and exposes a ground-truth description.
    """


    name: str = "attack"


    uses_fraction: bool = False

    def __init__(self, config: AttackConfig) -> None:
        self._config = config.validate()
        if self._config.attack_type != self.name:
            raise AttackValidationError(
                f"{type(self).__name__} implements {self.name!r} but was "
                f"configured for {self._config.attack_type!r}"
            )
        if self.uses_fraction != (self.name in FRACTIONAL_ATTACK_TYPES):
            raise AttackValidationError(
                f"{type(self).__name__} declares uses_fraction="
                f"{self.uses_fraction}, which disagrees with "
                f"FRACTIONAL_ATTACK_TYPES"
            )

    @property
    def config(self) -> AttackConfig:
        return self._config

    @property
    def fraction(self) -> float:
        return float(self._config.fraction)

    @property
    def parameters(self) -> Mapping[str, Any]:
        return self._config.parameters

    @abstractmethod
    def apply(self, context: AttackContext) -> AttackOutcome:
        """Apply the attack and return modified material plus ground truth."""

    def describe(self) -> Dict[str, Any]:
        """Return the ground-truth description of this scenario."""
        return {
            "attack_type": self.name,
            "fraction": self.fraction,
            "seed": self._config.seed,
            "parameters": dict(self._config.parameters),
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{type(self).__name__}(fraction={self.fraction})"


def select_targets(
    state_count: int,
    fraction: float,
    rng: np.random.Generator,
) -> Tuple[int, ...]:
    """Return the sorted indices an attack with ``fraction`` touches.

    The count is ``round(fraction * state_count)``, capped at ``state_count``,
    and the positions are drawn without replacement from the seeded generator.
    ``fraction = 0`` touches nothing; ``fraction = 1`` touches everything.

    This helper lives in the attack layer because it is part of *attack*
    sampling. It is not a threshold and not a decision rule.
    """
    if state_count < 0:
        raise AttackValidationError(f"state_count must be non-negative, got {state_count}")
    require_fraction(fraction)
    target_count = int(round(fraction * state_count))
    target_count = max(0, min(target_count, state_count))
    if target_count == 0:
        return ()
    chosen = rng.choice(state_count, size=target_count, replace=False)
    return tuple(sorted(int(index) for index in chosen))


def as_state_matrices(states: Tuple[np.ndarray, ...]) -> Tuple[np.ndarray, ...]:
    """Coerce received states to density matrices.

    The M1 teleportation branch decomposition returns normalised amplitude
    *vectors*; a channel, a Pauli operator and a projective measurement all
    want a density *matrix*. The conversion happens once, here, so no attack
    module has to care which representation it was handed.
    """
    from backend.noise.base import as_qubit_density_matrix

    return tuple(as_qubit_density_matrix(state) for state in states)


def reseal_transcript(transcript: Transcript, **overrides: Any) -> Transcript:
    """Return ``transcript`` with fields replaced and the hash recomputed.

    An attacker who knows the public canonicalization can do this, so the
    attack scenarios use it to produce *internally consistent* tampered
    transcripts. That is what makes the negative tests meaningful: the
    transcript hash check cannot catch the tampering, so the protocol's
    binding and consistency checks have to.
    """
    from dataclasses import replace

    from backend.protocol.transcript import compute_transcript_hash

    altered = replace(transcript, **overrides)
    return replace(
        altered,
        transcript_hash=compute_transcript_hash(altered.payload()),
    )
