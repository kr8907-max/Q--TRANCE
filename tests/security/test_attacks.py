"""Tests for the attack layer.

Milestone 3 -- adversarial channel and protocol attack scenarios.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.attacks import (
    AttackConfig,
    AttackContext,
    AttackScenario,
    AttackValidationError,
    AuthorizationContext,
    VALID_ATTACK_TYPES,
    build_attack_scenario,
    select_targets,
)
from backend.protocol import create_session, sign_session, VerifierContext
from backend.protocol.models import Transcript
from backend.quantum.density import projector
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import uncorrected_branch_states


def _fixture_transcript(message: str = "transfer 100 units to account 7", state_count: int = 8):
    """Build a signed session and its ideal received states as density matrices."""
    sess = create_session(
        message,
        signer_id="alice",
        verifier_id="bob",
        state_count=state_count,
        session_id_factory=lambda: "a" * 32,
        nonce_factory=lambda: "b" * 64,
        clock=lambda: "2026-09-13T10:00:00+00:00",
    )
    signed = sign_session(sess)
    t = signed.transcript
    states = tuple(
        projector(
            uncorrected_branch_states(get_eigenstate(st.label).vector)[(br.m0, br.m1)]
        )
        for st, br in zip(t.states, t.teleportation_branches)
    )
    auth = AuthorizationContext.from_session(sess)
    vctx = VerifierContext(verifier_id="bob")
    return message, sess, t, states, auth, vctx







class TestAttackConfig:
    def test_valid_configs_accepted(self) -> None:
        for atype in VALID_ATTACK_TYPES:
            frac = 0.0 if atype in ("none", "forgery", "impersonation", "unauthorized_verification", "replay") else 0.5
            cfg = AttackConfig(attack_type=atype, fraction=frac, seed=1, parameters={})
            cfg.validate()

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig(attack_type="unknown").validate()

    def test_negative_fraction_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig(attack_type="channel_tampering", fraction=-0.1).validate()

    def test_fraction_above_one_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig(attack_type="channel_tampering", fraction=1.1).validate()

    def test_none_fraction_must_be_zero(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig(attack_type="none", fraction=0.5).validate()

    def test_none_parameters_must_be_empty(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig(attack_type="none", parameters={"x": 1}).validate()







class TestSelectTargets:
    def test_fraction_zero_selects_none(self) -> None:
        rng = np.random.default_rng(7)
        assert select_targets(10, 0.0, rng) == ()

    def test_fraction_one_selects_all(self) -> None:
        rng = np.random.default_rng(7)
        assert select_targets(10, 1.0, rng) == tuple(range(10))

    def test_fraction_half_selects_half(self) -> None:
        rng = np.random.default_rng(7)
        targets = select_targets(10, 0.5, rng)
        assert len(targets) == 5
        assert all(0 <= i < 10 for i in targets)
        assert targets == tuple(sorted(targets))

    def test_reproducible_with_same_seed(self) -> None:
        a = select_targets(20, 0.3, np.random.default_rng(99))
        b = select_targets(20, 0.3, np.random.default_rng(99))
        assert a == b







class TestHonestBaseline:
    def test_none_attack_returns_none(self) -> None:
        assert build_attack_scenario(AttackConfig("none", 0.0, seed=1)) is None







class TestChannelTampering:
    def test_x_flip_changes_some_states(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        changed = sum(
            1 for a, b in zip(states, out.received_states) if not np.allclose(a, b)
        )
        assert 1 <= changed <= len(states) - 1
        assert out.ground_truth["attack_type"] == "channel_tampering"

    def test_full_fraction_changes_at_least_one(self) -> None:
        """X does not disturb its own eigenstates, so not every state need change."""
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("channel_tampering", 1.0, seed=3, parameters={"pauli": "Z"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        changed = sum(
            1 for a, b in zip(states, out.received_states) if not np.allclose(a, b)
        )
        assert changed >= 1

    def test_random_pauli_is_valid(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "random"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert "applied_paulis" in out.ground_truth

    def test_invalid_pauli_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            build_attack_scenario(AttackConfig("channel_tampering", 0.5, parameters={"pauli": "W"}))







class TestInterceptResend:
    def test_changes_some_states(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        changed = sum(
            1 for a, b in zip(states, out.received_states) if not np.allclose(a, b)
        )
        assert 1 <= changed <= len(states) - 1
        assert out.ground_truth["attack_type"] == "intercept_resend"

    def test_reproducible_with_same_seed(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("intercept_resend", 0.5, seed=99, parameters={"eve_basis": "Z"})
        sc = build_attack_scenario(cfg)

        def run():
            ctx = AttackContext(
                message=msg, session=sess, transcript=t, received_states=states,
                verifier_context=vctx, authorization=auth, rng=np.random.default_rng(1234),
            )
            return sc.apply(ctx)

        a = run()
        b = run()
        assert all(
            np.allclose(x, y) for x, y in zip(a.received_states, b.received_states)
        )
        assert a.ground_truth == b.ground_truth

    def test_invalid_basis_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            build_attack_scenario(AttackConfig("intercept_resend", 0.5, parameters={"eve_basis": "Q"}))







class TestForgery:
    def test_rebind_only_changes_transcript_hash(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("forgery", 0.0, seed=1, parameters={"mode": "rebind_only"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.transcript.transcript_hash != t.transcript_hash

        assert all(
            np.allclose(a, b) for a, b in zip(states, out.received_states)
        )

    def test_full_forge_changes_message_binding(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig(
            "forgery", 0.0, seed=1,
            parameters={"mode": "full_forge", "forged_message": "unauthorised transfer"},
        )
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.transcript.transcript_hash != t.transcript_hash
        assert out.ground_truth["forged_message"] == "unauthorised transfer"

    def test_full_forge_uses_default_message(self) -> None:
        sc = build_attack_scenario(AttackConfig("forgery", 0.0, parameters={"mode": "full_forge"}))
        assert sc.forged_message == "forged transfer authorisation"







class TestImpersonation:
    def test_changes_signer_identity(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("impersonation", 0.0, seed=1, parameters={"presented_signer": "eve"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.transcript.signer_id == "eve"
        assert out.ground_truth["presented_signer"] == "eve"
        assert out.ground_truth["original_signer"] == "alice"







class TestUnauthorizedVerification:
    def test_changes_verifier_identity(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig(
            "unauthorized_verification", 0.0, seed=1,
            parameters={"presented_verifier": "mallory"},
        )
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.transcript.verifier_id == "mallory"
        assert out.ground_truth["presented_verifier"] == "mallory"







class TestReplay:
    def test_reuses_prior_transcript(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("replay", 0.0, seed=1)
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.transcript.session_id == t.session_id
        assert out.transcript.transcript_hash == t.transcript_hash
        assert out.ground_truth["attack_type"] == "replay"
        assert out.ground_truth["replayed_transcript_hash"] == t.transcript_hash

    def test_replay_fraction_rejected(self) -> None:
        with pytest.raises(AttackValidationError):
            AttackConfig("replay", 0.1).validate()







class TestSeparation:
    def test_ground_truth_includes_attack_params(self) -> None:
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)
        assert out.ground_truth is not None
        assert out.ground_truth["attack_type"] == "channel_tampering"

    def test_observable_does_not_require_ground_truth(self) -> None:
        """A downstream detector can operate on received_states + transcript alone."""
        msg, sess, t, states, auth, vctx = _fixture_transcript()
        cfg = AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})
        sc = build_attack_scenario(cfg)
        ctx = AttackContext(
            message=msg, session=sess, transcript=t, received_states=states,
            verifier_context=vctx, authorization=auth, rng=np.random.default_rng(7),
        )
        out = sc.apply(ctx)

        assert isinstance(out.received_states, tuple)
        assert isinstance(out.transcript, Transcript)

        assert out.ground_truth is not None







class TestNoDetectionImports:
    def test_attack_modules_do_not_import_detection(self) -> None:
        import backend.attacks.channel_tampering as ct
        import backend.attacks.forgery as fg
        import backend.attacks.impersonation as im
        import backend.attacks.intercept_resend as ir
        import backend.attacks.replay as rp
        import backend.attacks.unauthorized_verification as uv



        forbidden_patterns = (
            "from backend.detection",
            "import backend.detection",
            "from .detection",
            "import .detection",
        )
        for mod in (ct, fg, im, ir, rp, uv):
            src = mod.__file__
            with open(src, encoding="utf-8") as f:
                text = f.read()
            for pat in forbidden_patterns:
                assert pat not in text, f"{mod.__name__} imports detection: {pat!r}"
