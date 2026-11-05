"""Tests for the simulation layer (scenario, runner, results, seed).

Milestone 3 -- reproducible experiment framework.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.attacks import AttackConfig
from backend.noise import NoiseConfig
from backend.protocol.models import ProtocolValidationError
from backend.simulation import (
    ScenarioConfig,
    ScenarioValidationError,
    run_scenario,
    run_sweep,
    sweep_attack_fraction,
    sweep_noise,
)
from backend.simulation.results import ExperimentResult, ObservableExperimentData
from backend.simulation.scenario import REFERENCE_NOISE_SWEEP

BASE = dict(
    scenario_id="test",
    message="transfer 100 units to account 7",
    signer_id="alice",
    verifier_id="bob",
    state_count=8,
    random_seed=42,
    session_id="a" * 32,
    nonce="b" * 64,
    created_at="2026-09-13T10:00:00+00:00",
)







class TestScenarioConfigValidation:
    def test_minimal_valid_config(self) -> None:
        cfg = ScenarioConfig(**BASE)
        cfg.validate()
        assert cfg.fingerprint() != ""

    def test_missing_message_rejected(self) -> None:
        with pytest.raises((ScenarioValidationError, ProtocolValidationError)):
            ScenarioConfig(**{**BASE, "message": ""}).validate()

    def test_invalid_protocol_version_rejected(self) -> None:
        with pytest.raises((ScenarioValidationError, ProtocolValidationError)):
            ScenarioConfig(**{**BASE, "protocol_version": "99.99"}).validate()

    def test_invalid_measurement_mode_rejected(self) -> None:
        with pytest.raises(ScenarioValidationError):
            ScenarioConfig(**{**BASE, "measurement_mode": "magic"}).validate()

    def test_with_changes_creates_new_instance(self) -> None:
        cfg = ScenarioConfig(**BASE)
        cfg2 = cfg.with_changes(state_count=16)
        assert cfg2.state_count == 16
        assert cfg.state_count == 8







class TestSweeps:
    def test_sweep_noise_produces_correct_values(self) -> None:
        cfg = ScenarioConfig(**{**BASE, "noise": NoiseConfig("bit_flip", 0.0)})
        values = (0.0, 0.1, 0.25)
        swept = list(sweep_noise(cfg, values))
        assert len(swept) == len(values)
        for s, expected in zip(swept, values):
            assert s.noise.noise_strength == expected

    def test_sweep_attack_fraction_produces_correct_values(self) -> None:
        cfg = ScenarioConfig(**{**BASE, "attack": AttackConfig("channel_tampering", 0.0, seed=1, parameters={"pauli": "X"})})
        values = (0.0, 0.25, 0.5)
        swept = list(sweep_attack_fraction(cfg, values))
        assert len(swept) == len(values)
        for s, expected in zip(swept, values):
            assert s.attack.fraction == expected

    def test_run_sweep_executes_all(self) -> None:
        cfg = ScenarioConfig(**{**BASE, "noise": NoiseConfig("bit_flip", 0.0)})
        swept = list(sweep_noise(cfg, (0.0, 0.1)))
        results = list(run_sweep(swept))
        assert len(results) == 2
        for r in results:
            assert isinstance(r, ExperimentResult)







class TestRunnerHonest:
    def test_ideal_channel_accepted(self) -> None:
        cfg = ScenarioConfig(**BASE)
        res = run_scenario(cfg)
        assert res.observable.verification.accepted is True
        assert res.observable.mismatch_count == 0
        assert res.observable.mean_channel_disturbance == 0.0
        assert res.ground_truth.is_malicious is False

    def test_ideal_reproducible(self) -> None:
        cfg = ScenarioConfig(**BASE)
        a = run_scenario(cfg)
        b = run_scenario(cfg)
        assert a.observable.to_dict() == b.observable.to_dict()

    def test_different_seed_different_observable(self) -> None:
        cfg = ScenarioConfig(**BASE)
        a = run_scenario(cfg)
        b = run_scenario(cfg.with_changes(random_seed=999))

        assert a.observable.to_dict() != b.observable.to_dict()

    def test_runtime_measured_when_requested(self) -> None:
        cfg = ScenarioConfig(**BASE)
        res = run_scenario(cfg, measure_runtime=True)
        assert res.observable.runtime_seconds > 0.0

    def test_baseline_has_all_observable_fields(self) -> None:
        cfg = ScenarioConfig(**BASE)
        res = run_scenario(cfg)
        o = res.observable
        assert o.scenario_id == "test"
        assert o.protocol_version == "RQDS-TP-1.0"
        assert o.state_count == 8
        assert o.measurement_mode in ("projective-analytic", "sampled")
        assert set(o.basis_counts) <= {"X", "Y", "Z"}
        assert 0 <= o.mismatch_count <= o.state_count
        assert 0.0 <= o.mean_channel_disturbance <= 1.0
        assert o.verification is not None







class TestRunnerNoise:
    def test_depolarizing_increases_mismatch(self) -> None:
        cfg = ScenarioConfig(**{**BASE, "noise": NoiseConfig("depolarizing", 0.1)})
        res = run_scenario(cfg)

        assert res.observable.mean_channel_disturbance > 0.0

    def test_zero_noise_same_as_ideal(self) -> None:
        cfg = ScenarioConfig(**{**BASE, "noise": NoiseConfig("depolarizing", 0.0)})
        res = run_scenario(cfg)
        assert res.observable.verification.accepted is True
        assert res.observable.mismatch_count == 0







class TestRunnerAttack:
    def test_channel_tampering_creates_mismatch(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})}
        )
        res = run_scenario(cfg)
        assert res.ground_truth.is_malicious is True
        assert res.observable.mean_channel_disturbance > 0.0

    def test_forgery_rejected(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("forgery", 0.0, seed=1, parameters={"mode": "rebind_only"})}
        )
        res = run_scenario(cfg)
        assert res.observable.verification.accepted is False
        assert res.ground_truth.is_malicious is True

    def test_impersonation_recorded_in_ground_truth(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("impersonation", 0.0, seed=1, parameters={"presented_signer": "eve"})}
        )
        res = run_scenario(cfg)



        assert res.ground_truth.is_malicious is True
        assert res.ground_truth.attack["presented_signer"] == "eve"
        assert res.ground_truth.attack["signer_was_authorized"] is False

    def test_unauthorized_verification_recorded_in_ground_truth(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("unauthorized_verification", 0.0, seed=1, parameters={"presented_verifier": "mallory"})}
        )
        res = run_scenario(cfg)
        assert res.ground_truth.is_malicious is True
        assert res.ground_truth.attack["presented_verifier"] == "mallory"
        assert res.ground_truth.attack["verifier_was_authorized"] is False

    def test_replay_accepted_because_hash_valid(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("replay", 0.0, seed=1)}
        )
        res = run_scenario(cfg)

        assert res.observable.verification.accepted is True
        assert res.ground_truth.is_malicious is True

    def test_intercept_resend_creates_mismatch(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"})}
        )
        res = run_scenario(cfg)
        assert res.ground_truth.is_malicious is True
        assert res.observable.mean_channel_disturbance > 0.0







class TestRunnerComposition:
    def test_noise_plus_attack(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE,
               "noise": NoiseConfig("depolarizing", 0.05),
               "attack": AttackConfig("intercept_resend", 0.3, seed=5, parameters={"eve_basis": "random"})}
        )
        res = run_scenario(cfg)
        assert res.observable.mean_channel_disturbance > 0.0
        assert res.ground_truth.is_malicious is True
        assert res.ground_truth.noise is not None

    def test_attack_fraction_sweep(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("channel_tampering", 0.0, seed=3, parameters={"pauli": "Z"})}
        )
        disturbances = []
        for s in sweep_attack_fraction(cfg, (0.0, 0.25, 0.5, 1.0)):
            res = run_scenario(s)
            disturbances.append(res.observable.mean_channel_disturbance)

        assert disturbances[0] <= disturbances[1] <= disturbances[2] <= disturbances[3]







class TestReproducibility:
    def test_same_seed_same_result(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE,
               "noise": NoiseConfig("bit_flip", 0.1),
               "attack": AttackConfig("intercept_resend", 0.3, seed=7, parameters={"eve_basis": "random"})}
        )
        a = run_scenario(cfg)
        b = run_scenario(cfg)
        assert a.observable.to_dict() == b.observable.to_dict()
        assert a.ground_truth.to_dict() == b.ground_truth.to_dict()

    def test_different_seed_different_attack_targets(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("intercept_resend", 0.5, seed=5, parameters={"eve_basis": "random"})}
        )
        a = run_scenario(cfg)
        b = run_scenario(cfg.with_changes(random_seed=999))


        assert a.observable.to_dict() != b.observable.to_dict()







class TestSeparation:
    def test_observable_has_no_ground_truth(self) -> None:
        cfg = ScenarioConfig(**BASE)
        res = run_scenario(cfg)
        d = res.observable.to_dict()
        assert "ground_truth" not in d
        assert "is_malicious" not in d

    def test_ground_truth_has_attack_info(self) -> None:
        cfg = ScenarioConfig(
            **{**BASE, "attack": AttackConfig("channel_tampering", 0.5, seed=3, parameters={"pauli": "X"})}
        )
        res = run_scenario(cfg)
        assert res.ground_truth.is_malicious is True
        assert res.ground_truth.attack["attack_type"] == "channel_tampering"







class TestNegative:
    def test_invalid_noise_strength(self) -> None:


        from backend.noise import build_noise_channel
        with pytest.raises(ValueError):
            build_noise_channel(NoiseConfig("depolarizing", 1.5))

    def test_invalid_attack_fraction(self) -> None:
        with pytest.raises(ValueError):
            ScenarioConfig(
                **{**BASE, "attack": AttackConfig("channel_tampering", 1.5, seed=1, parameters={})}
            ).validate()

    def test_malformed_scenario_id(self) -> None:
        with pytest.raises((ScenarioValidationError, ProtocolValidationError)):
            ScenarioConfig(**{**BASE, "scenario_id": ""}).validate()
