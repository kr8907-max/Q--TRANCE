"""Serializable, validated scenario configuration.

A scenario is a *description of an experiment*, never a result. Nothing derived
-- no transcript, no measurement, no statistic -- is stored here, so a
configuration can be written to disk, hashed, diffed and replayed.

Canonicalization note
---------------------
``ScenarioConfig.fingerprint()`` hashes ``json.dumps(..., sort_keys=True,
separators=(",", ":"))`` of the configuration. This is deliberately **not** the
protocol layer's ``canonical_json``: that encoder rejects ``float`` outright,
because a transcript must never carry amplitudes, whereas a scenario
configuration legitimately carries physical parameters such as a noise
strength. Using one encoder for both would mean either weakening the transcript
guarantee or pretending a probability is a string. The two concerns are kept
separate and each is documented where it lives.

``json`` renders floats via ``repr``, which is the shortest round-tripping
decimal and is platform-independent, so the fingerprint is stable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Sequence, Tuple

from backend.attacks.base import AttackConfig
from backend.noise.base import NoiseConfig
from backend.protocol.models import (
    DEFAULT_STATE_COUNT,
    MAX_STATE_COUNT,
    PROTOCOL_VERSION,
    validate_identifier,
    validate_message,
    validate_protocol_version,
)

__all__ = [
    "MEASUREMENT_MODES",
    "REFERENCE_NOISE_SWEEP",
    "REFERENCE_ATTACK_FRACTION_SWEEP",
    "ScenarioValidationError",
    "ScenarioConfig",
    "sweep_noise",
    "sweep_attack_fraction",
]









MEASUREMENT_MODES: Tuple[str, ...] = ("projective-analytic", "sampled")






REFERENCE_NOISE_SWEEP: Tuple[float, ...] = (0.0, 0.001, 0.005, 0.01, 0.02, 0.05)


REFERENCE_ATTACK_FRACTION_SWEEP: Tuple[float, ...] = (
    0.0,
    0.01,
    0.05,
    0.10,
    0.20,
    0.50,
)


class ScenarioValidationError(ValueError):
    """Raised when a scenario configuration is invalid."""


@dataclass(frozen=True)
class ScenarioConfig:
    """A complete, serializable description of one experiment.

    Fields are inputs only. ``session_id``, ``nonce`` and ``created_at`` are
    optional *pins*: leaving them ``None`` lets the protocol layer draw
    cryptographic identifiers from the OS CSPRNG, which makes the transcript
    irreproducible by design; pinning them makes a run fully reproducible and is
    a simulation convenience.
    """

    scenario_id: str
    message: str
    signer_id: str
    verifier_id: str
    protocol_version: str = PROTOCOL_VERSION
    state_count: int = DEFAULT_STATE_COUNT
    shot_count: int = 1024
    random_seed: int = 0
    measurement_mode: str = "projective-analytic"
    noise: NoiseConfig = field(default_factory=NoiseConfig)
    attack: AttackConfig = field(default_factory=AttackConfig)
    session_id: str | None = None
    nonce: str | None = None
    created_at: str | None = None
    extra_authorized_verifiers: Tuple[str, ...] = ()

    def validate(self) -> "ScenarioConfig":
        validate_identifier(self.scenario_id, "scenario_id")
        validate_message(self.message)
        validate_identifier(self.signer_id, "signer_id")
        validate_identifier(self.verifier_id, "verifier_id")
        validate_protocol_version(self.protocol_version, "protocol_version")

        if isinstance(self.state_count, bool) or not isinstance(self.state_count, int):
            raise ScenarioValidationError(
                f"state_count must be an integer, got {type(self.state_count).__name__}"
            )
        if not 1 <= self.state_count <= MAX_STATE_COUNT:
            raise ScenarioValidationError(
                f"state_count must lie in [1, {MAX_STATE_COUNT}], got {self.state_count}"
            )
        if isinstance(self.shot_count, bool) or not isinstance(self.shot_count, int):
            raise ScenarioValidationError(
                f"shot_count must be an integer, got {type(self.shot_count).__name__}"
            )
        if self.shot_count < 1:
            raise ScenarioValidationError(
                f"shot_count must be positive, got {self.shot_count}"
            )
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise ScenarioValidationError(
                f"random_seed must be an integer, got "
                f"{type(self.random_seed).__name__}"
            )
        if self.random_seed < 0:
            raise ScenarioValidationError(
                f"random_seed must be non-negative, got {self.random_seed}"
            )
        if self.measurement_mode not in MEASUREMENT_MODES:
            raise ScenarioValidationError(
                f"measurement_mode must be one of {list(MEASUREMENT_MODES)}, "
                f"got {self.measurement_mode!r}"
            )

        self.noise.validate()
        self.attack.validate()

        for name, value in (
            ("session_id", self.session_id),
            ("nonce", self.nonce),
            ("created_at", self.created_at),
        ):
            if value is not None and not isinstance(value, str):
                raise ScenarioValidationError(
                    f"{name} must be a string or None, got {type(value).__name__}"
                )
        for verifier in self.extra_authorized_verifiers:
            validate_identifier(verifier, "extra_authorized_verifiers")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "message": self.message,
            "signer_id": self.signer_id,
            "verifier_id": self.verifier_id,
            "protocol_version": self.protocol_version,
            "state_count": int(self.state_count),
            "shot_count": int(self.shot_count),
            "random_seed": int(self.random_seed),
            "measurement_mode": self.measurement_mode,
            "noise": self.noise.to_dict(),
            "attack": self.attack.to_dict(),
            "session_id": self.session_id,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "extra_authorized_verifiers": list(self.extra_authorized_verifiers),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ScenarioConfig":
        if not isinstance(data, dict):
            raise ScenarioValidationError(
                f"scenario must be an object, got {type(data).__name__}"
            )
        known = set(cls.__dataclass_fields__)
        unknown = sorted(set(data) - known)
        if unknown:
            raise ScenarioValidationError(f"scenario has unknown fields {unknown}")
        missing = sorted({"scenario_id", "message", "signer_id", "verifier_id"} - set(data))
        if missing:
            raise ScenarioValidationError(f"scenario is missing fields {missing}")
        config = cls(
            scenario_id=data["scenario_id"],
            message=data["message"],
            signer_id=data["signer_id"],
            verifier_id=data["verifier_id"],
            protocol_version=data.get("protocol_version", PROTOCOL_VERSION),
            state_count=data.get("state_count", DEFAULT_STATE_COUNT),
            shot_count=data.get("shot_count", 1024),
            random_seed=data.get("random_seed", 0),
            measurement_mode=data.get("measurement_mode", "projective-analytic"),
            noise=NoiseConfig.from_dict(data.get("noise", {})),
            attack=AttackConfig.from_dict(data.get("attack", {})),
            session_id=data.get("session_id"),
            nonce=data.get("nonce"),
            created_at=data.get("created_at"),
            extra_authorized_verifiers=tuple(
                data.get("extra_authorized_verifiers", ())
            ),
        )
        return config.validate()

    def fingerprint(self) -> str:
        """Return a stable SHA-256 fingerprint of the configuration."""
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def with_changes(self, **overrides: Any) -> "ScenarioConfig":
        """Return a validated copy with fields replaced."""
        return replace(self, **overrides).validate()


def sweep_noise(
    base: ScenarioConfig,
    strengths: Sequence[float] = REFERENCE_NOISE_SWEEP,
) -> Tuple[ScenarioConfig, ...]:
    """Return one configuration per noise strength.

    Each configuration gets a distinct ``scenario_id`` suffix so results stay
    distinguishable. The sweep values are experiment parameters only.
    """
    configs = []
    for strength in strengths:
        configs.append(
            base.with_changes(
                scenario_id=f"{base.scenario_id}-noise-{strength:g}",
                noise=NoiseConfig(
                    noise_type=base.noise.noise_type, noise_strength=float(strength)
                ),
            )
        )
    return tuple(configs)


def sweep_attack_fraction(
    base: ScenarioConfig,
    fractions: Sequence[float] = REFERENCE_ATTACK_FRACTION_SWEEP,
) -> Tuple[ScenarioConfig, ...]:
    """Return one configuration per attack fraction.

    The fractions are experiment parameters only. In particular, a run at
    ``0.10`` is not an acceptance threshold: nothing in this package compares a
    measurement against it.
    """
    configs = []
    for fraction in fractions:
        configs.append(
            base.with_changes(
                scenario_id=f"{base.scenario_id}-attack-{fraction:g}",
                attack=AttackConfig(
                    attack_type=base.attack.attack_type,
                    fraction=float(fraction),
                    seed=base.attack.seed,
                    parameters=dict(base.attack.parameters),
                ),
            )
        )
    return tuple(configs)
