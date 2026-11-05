"""Schemas for scenario simulation.

Observable output and evaluation output are separate on purpose
----------------------------------------------------------------
A scenario run produces two things: what a verifier could actually observe, and
the ground truth the simulator used to build it. Only the first is ever returned
by default.

Ground truth carries the hidden attack label. Handing it back on an ordinary
simulation response would turn the API into a shortcut around the detector: a
caller could read ``attack_type`` from the response instead of detecting
anything. So ``include_ground_truth`` defaults to ``False``, the field is
``None`` unless the caller asked for it explicitly, and the payload it carries
labels itself as evaluation material.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from backend.api.config import ABSOLUTE_MAX_MESSAGE_CHARS, ABSOLUTE_MAX_SHOT_COUNT
from backend.api.schemas.common import (
    ApiModel,
    Identifier,
    ProtocolVersion,
    configured_limit,
)
from backend.api.schemas.verification import VerificationResultView
from backend.attacks import VALID_ATTACK_TYPES
from backend.noise import VALID_NOISE_TYPES
from backend.protocol import DEFAULT_STATE_COUNT, MAX_STATE_COUNT, PROTOCOL_VERSION
from backend.simulation import MAX_SEED, MEASUREMENT_MODES



GROUND_TRUTH_LABEL = "evaluation ground truth; not observable operational output"


class NoiseSpec(ApiModel):
    """Honest channel configuration."""

    noise_type: str = Field(default="depolarizing", description="One of the modelled channels.")
    noise_strength: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("noise_type")
    @classmethod
    def _known_channel(cls, value: str) -> str:
        if value not in VALID_NOISE_TYPES:
            raise ValueError(
                f"unknown noise_type {value!r}; known: {list(VALID_NOISE_TYPES)}"
            )
        return value


class AttackSpec(ApiModel):
    """Modelled attack configuration."""

    attack_type: str = Field(default="none", description="One of the modelled attacks.")
    fraction: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Share of states the attack targets. Must be 0 for a non-fractional attack.",
    )
    seed: int = Field(default=0, ge=0, le=MAX_SEED)
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Attack-specific parameters, validated by the M3 attack module.",
    )

    @field_validator("attack_type")
    @classmethod
    def _known_attack(cls, value: str) -> str:
        if value not in VALID_ATTACK_TYPES:
            raise ValueError(
                f"unknown attack_type {value!r}; known: {list(VALID_ATTACK_TYPES)}"
            )
        return value


class SimulationRequest(ApiModel):
    """Request body for ``POST /simulations``."""

    scenario_id: str = Field(default="api-scenario", min_length=1, max_length=128)
    message: str = Field(
        default="reference message",
        min_length=1,
        max_length=ABSOLUTE_MAX_MESSAGE_CHARS,
        description=(
            "Message the run signs. The accepted length follows the application's "
            "configured message bound."
        ),
    )
    signer_id: Identifier = Field(default="alice")
    verifier_id: Identifier = Field(default="bob")
    protocol_version: ProtocolVersion = Field(default=PROTOCOL_VERSION)
    state_count: int = Field(default=DEFAULT_STATE_COUNT, ge=1, le=MAX_STATE_COUNT)
    shot_count: int = Field(
        default=1,
        ge=1,
        le=ABSOLUTE_MAX_SHOT_COUNT,
        description=(
            "Shots per state. The largest accepted value follows the application's "
            "configured shot bound."
        ),
    )
    random_seed: int = Field(
        default=0, ge=0, le=MAX_SEED, description="Master seed; makes the run reproducible."
    )
    measurement_mode: str = Field(default="sampled")
    noise: NoiseSpec = Field(default_factory=NoiseSpec)
    attack: AttackSpec = Field(default_factory=AttackSpec)
    extra_authorized_verifiers: List[Identifier] = Field(
        default_factory=list, max_length=16
    )

    @field_validator("message")
    @classmethod
    def _configured_message_bound(cls, value: str, info) -> str:
        return configured_limit(value, info, "max_message_chars")

    @field_validator("shot_count")
    @classmethod
    def _configured_shot_bound(cls, value: int, info) -> int:
        return configured_limit(value, info, "max_shot_count")

    @field_validator("measurement_mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in MEASUREMENT_MODES:
            raise ValueError(
                f"unknown measurement_mode {value!r}; known: {list(MEASUREMENT_MODES)}"
            )
        return value


class StateObservationOut(ApiModel):
    """One observed verification state."""

    index: int
    basis: str
    expected_bit: int
    probability_expected: float
    matched: bool


class AuthorizationObservationsOut(ApiModel):
    """Authorization evidence gathered during the run."""

    presented_signer: str
    presented_verifier: str
    authorized_signers: List[str]
    authorized_verifiers: List[str]
    signer_authorized: bool
    verifier_authorized: bool


class GroundTruthOut(ApiModel):
    """Simulator ground truth. Evaluation material only.

    Carries the hidden attack label, which is exactly why it is returned only
    when the caller asks for it explicitly.
    """

    label: str = Field(default=GROUND_TRUTH_LABEL)
    scenario_id: str
    is_malicious: bool
    noise: Dict[str, Any]
    attack: Dict[str, Any]
    notes: List[str]


class SimulationResponse(ApiModel):
    """Observable simulation output.

    This model has **no ground-truth field at all**. That is stronger than
    carrying one set to null: an operational response cannot expose an attack
    label, not even an absent one, because the shape it is serialised from has
    nowhere to put it.
    """

    scenario_id: str
    protocol_version: str
    state_count: int
    measurement_mode: str
    simulator_seed: int
    mismatch_count: int
    mismatch_proportion: float
    mean_channel_disturbance: float
    basis_counts: Dict[str, int]
    states: List[StateObservationOut]
    verification: VerificationResultView
    authorization: AuthorizationObservationsOut
    runtime_seconds: Optional[float] = None
    observable_only: bool = Field(
        default=True,
        description="Always true here: this response carries no ground truth.",
    )
    note: str = Field(
        default=(
            "Observable output is what a verifier could see. It is produced in "
            "simulation and is not a measurement of any physical device. Ground "
            "truth is not available on this endpoint; use the evaluation "
            "simulation endpoint to obtain it deliberately."
        )
    )


class SimulationEvaluationResponse(SimulationResponse):
    """Observable output **plus** ground truth, for evaluation use.

    A separate schema and a separate route, because the hidden attack label must
    not be reachable from the operational path. The label is present here by
    design, and labels itself as evaluation material.
    """

    ground_truth: GroundTruthOut = Field(
        description="Simulator ground truth, including the hidden attack label."
    )
    observable_only: bool = Field(
        default=False, description="False: this response does include ground truth."
    )
