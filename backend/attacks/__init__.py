"""Reference attack scenarios.

These modules model *protocol-level* and *channel-level* attacks on the
reference construction from Milestone 2. They produce the evidence a later
milestone will interpret; they make no security decision themselves.

Two rules hold across the whole package:

1. **No attack is a boolean.** Every scenario acts on real material -- a
   transcript, an identity, a received qubit -- and the runner then executes the
   ordinary verification path on the result. There is no branch anywhere that
   reads an attack label and announces a detection.
2. **Ground truth is separated from observable evidence.** Each scenario returns
   an :class:`~backend.attacks.base.AttackOutcome` whose ``ground_truth`` field
   never reaches :class:`~backend.simulation.results.ObservableExperimentData`.

Dependency direction::

    backend.quantum -> backend.protocol -> backend.noise -> backend.attacks -> backend.simulation

``backend.attacks`` imports nothing from a detection layer, because no detection
layer exists in this milestone and none may be added.
"""

from backend.attacks.base import (
    FRACTIONAL_ATTACK_TYPES,
    VALID_ATTACK_TYPES,
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
    AuthorizationContext,
    reseal_transcript,
    require_fraction,
    select_targets,
    validate_seed,
)
from backend.attacks.channel_tampering import (
    VALID_TAMPER_PAULIS,
    ChannelTamperingAttack,
)
from backend.attacks.forgery import (
    DEFAULT_FORGED_MESSAGE,
    VALID_FORGERY_MODES,
    ForgeryAttack,
)
from backend.attacks.impersonation import (
    DEFAULT_IMPERSONATED_SIGNER,
    ImpersonationAttack,
)
from backend.attacks.intercept_resend import (
    VALID_EVE_BASES,
    InterceptResendAttack,
)
from backend.attacks.replay import VALID_REPLAY_MODES, ReplayAttack
from backend.attacks.unauthorized_verification import (
    DEFAULT_UNAUTHORIZED_VERIFIER,
    UnauthorizedVerificationAttack,
)

__all__ = [
    "VALID_ATTACK_TYPES",
    "FRACTIONAL_ATTACK_TYPES",
    "VALID_TAMPER_PAULIS",
    "VALID_EVE_BASES",
    "VALID_FORGERY_MODES",
    "VALID_REPLAY_MODES",
    "DEFAULT_FORGED_MESSAGE",
    "DEFAULT_IMPERSONATED_SIGNER",
    "DEFAULT_UNAUTHORIZED_VERIFIER",
    "AttackConfig",
    "AttackContext",
    "AttackOutcome",
    "AttackScenario",
    "AttackValidationError",
    "AuthorizationContext",
    "ChannelTamperingAttack",
    "ForgeryAttack",
    "ImpersonationAttack",
    "InterceptResendAttack",
    "ReplayAttack",
    "UnauthorizedVerificationAttack",
    "reseal_transcript",
    "require_fraction",
    "select_targets",
    "validate_seed",
    "build_attack_scenario",
]




_REGISTRY = {
    "forgery": ForgeryAttack,
    "impersonation": ImpersonationAttack,
    "unauthorized_verification": UnauthorizedVerificationAttack,
    "replay": ReplayAttack,
    "intercept_resend": InterceptResendAttack,
    "channel_tampering": ChannelTamperingAttack,
}


def build_attack_scenario(config: AttackConfig) -> AttackScenario | None:
    """Return the scenario described by ``config``, or ``None`` for no attack.

    Raises :class:`~backend.attacks.base.AttackValidationError` for an unknown
    type or an invalid parameter. Nothing is silently coerced, and an unknown
    parameter is rejected rather than ignored.
    """
    config = config.validate()
    if config.attack_type == "none":
        return None
    scenario_class = _REGISTRY.get(config.attack_type)
    if scenario_class is None:



        raise AttackValidationError(
            f"attack_type {config.attack_type!r} has no registered scenario"
        )
    return scenario_class(config)
