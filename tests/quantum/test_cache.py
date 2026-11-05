"""The opt-in transpile cache.

The cache exists for one reason: the reference benchmark would otherwise take
hours, and a benchmark nobody re-runs is a benchmark nobody should trust. It is
therefore allowed only if it is provably result-preserving.

These tests are that proof. They do not check that the cache *returns something
plausible*; they run the same seeded scenarios with the cache off and on and
compare the observable evidence field by field, including the per-state
probabilities. They also pin the property that makes the cache safe to have in
the codebase at all: **it is off unless a caller explicitly turns it on.**

The cache stores compiled circuits, never outcomes. That distinction is what
makes it safe: a compiled circuit is a function of the circuit and the backend,
whereas an outcome depends on the seed, so caching outcomes would silently
change results.
"""

from __future__ import annotations

import pytest

from backend.quantum.cache import (
    DEFAULT_MAX_ENTRIES,
    cache_stats,
    circuit_digest,
    clear,
    disable,
    enable,
    enabled,
    is_enabled,
    transpiled,
)
from backend.simulation import ScenarioConfig, run_scenario







def _scenario(**overrides) -> ScenarioConfig:
    base = dict(
        scenario_id="cache-test",
        message="transfer 100 units to account 7",
        signer_id="alice",
        verifier_id="bob",
        state_count=12,
        shot_count=1,
        random_seed=4242,
        measurement_mode="sampled",
        session_id="0" * 32,
        nonce="1" * 64,
        created_at="2026-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return ScenarioConfig(**base).validate()


@pytest.fixture(autouse=True)
def _cache_disabled_after_each_test():
    """Leave the cache off, whatever a test did to it."""
    disable()
    clear()
    yield
    disable()
    clear()


def _observable_signature(observable) -> dict:
    """Return every observable field that must not depend on the cache.

    ``runtime_seconds`` is excluded on purpose: it is a wall-clock measurement,
    so it is *expected* to differ between two runs. Everything else -- including
    each state's analytic probability -- must be byte-identical.
    """
    return {
        "scenario_id": observable.scenario_id,
        "protocol_version": observable.protocol_version,
        "state_count": observable.state_count,
        "measurement_mode": observable.measurement_mode,
        "simulator_seed": observable.simulator_seed,
        "basis_counts": dict(observable.basis_counts),
        "mismatch_count": observable.mismatch_count,
        "mismatch_proportion": observable.mismatch_proportion,
        "mean_channel_disturbance": observable.mean_channel_disturbance,
        "states": [
            {
                "index": state.index,
                "basis": state.basis,
                "expected_bit": state.expected_bit,
                "probability_expected": state.probability_expected,
                "matched": state.matched,
            }
            for state in observable.states
        ],
    }







def test_the_cache_is_off_by_default() -> None:
    assert is_enabled() is False
    stats = cache_stats()
    assert stats.enabled is False
    assert stats.entries == 0
    assert stats.hits == 0
    assert stats.misses == 0


def test_a_disabled_cache_is_a_plain_pass_through() -> None:


    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    backend = AerSimulator()

    first = transpiled(circuit, backend)
    second = transpiled(circuit, backend)
    assert first is not second or first == second
    assert cache_stats().entries == 0
    assert cache_stats().hits == 0


def test_disabling_clears_the_hit_and_miss_counters() -> None:
    enable()
    assert is_enabled() is True
    disable()
    stats = cache_stats()
    assert stats.enabled is False
    assert stats.hits == 0
    assert stats.misses == 0







def test_enable_takes_its_capacity_by_keyword() -> None:
    enable(max_entries=8)
    assert cache_stats().max_entries == 8
    assert is_enabled() is True


def test_the_default_capacity_is_declared() -> None:
    enable()
    assert cache_stats().max_entries == DEFAULT_MAX_ENTRIES


def test_the_context_manager_restores_the_previous_state() -> None:
    assert is_enabled() is False
    with enabled(max_entries=4):
        assert is_enabled() is True
        assert cache_stats().max_entries == 4
    assert is_enabled() is False


def test_the_context_manager_restores_an_already_enabled_cache() -> None:
    enable(max_entries=16)
    with enabled(max_entries=2):
        assert cache_stats().max_entries == 2
    assert is_enabled() is True
    assert cache_stats().max_entries == 16


def test_the_context_manager_restores_state_after_an_exception() -> None:
    with pytest.raises(RuntimeError):
        with enabled(max_entries=4):
            raise RuntimeError("boom")
    assert is_enabled() is False







def test_the_circuit_digest_is_stable() -> None:
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    assert circuit_digest(circuit) == circuit_digest(circuit)
    assert len(circuit_digest(circuit)) == 64


def test_the_circuit_digest_distinguishes_different_circuits() -> None:
    from qiskit import QuantumCircuit

    first = QuantumCircuit(1, 1)
    first.h(0)
    second = QuantumCircuit(1, 1)
    second.x(0)
    assert circuit_digest(first) != circuit_digest(second)


def test_the_circuit_digest_distinguishes_parameter_values() -> None:
    from qiskit import QuantumCircuit
    from qiskit.circuit import Parameter

    parameter = Parameter("theta")
    first = QuantumCircuit(1, 1)
    first.rx(parameter, 0)
    first.assign_parameters({parameter: 0.1}, inplace=True)
    second = QuantumCircuit(1, 1)
    second.rx(parameter, 0)
    second.assign_parameters({parameter: 0.9}, inplace=True)
    assert circuit_digest(first) != circuit_digest(second)







def test_a_repeated_transpile_hits_the_cache() -> None:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    backend = AerSimulator()

    with enabled():
        transpiled(circuit, backend)
        stats_after_first = cache_stats()
        transpiled(circuit, backend)
        stats_after_second = cache_stats()

    assert stats_after_first.misses == 1
    assert stats_after_first.hits == 0
    assert stats_after_second.misses == 1
    assert stats_after_second.hits == 1
    assert stats_after_second.hit_rate == pytest.approx(0.5)


def test_a_different_circuit_is_a_miss() -> None:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    backend = AerSimulator()
    first = QuantumCircuit(1, 1)
    first.h(0)
    second = QuantumCircuit(1, 1)
    second.x(0)

    with enabled():
        transpiled(first, backend)
        transpiled(second, backend)
        stats = cache_stats()

    assert stats.misses == 2
    assert stats.hits == 0
    assert stats.entries == 2


def test_a_different_seed_transpiler_is_a_miss() -> None:

    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    circuit = QuantumCircuit(3, 3)
    circuit.h(range(3))
    circuit.cx(0, 1)
    backend = AerSimulator()

    with enabled():
        transpiled(circuit, backend, seed_transpiler=0)
        transpiled(circuit, backend, seed_transpiler=1)
        stats = cache_stats()

    assert stats.misses == 2
    assert stats.entries == 2


def test_the_store_is_evicted_at_capacity() -> None:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    backend = AerSimulator()
    with enabled(max_entries=2):
        for index in range(4):
            circuit = QuantumCircuit(1, 1)
            if index % 2:
                circuit.x(0)
            circuit.ry(0.1 * index, 0)
            transpiled(circuit, backend)
        stats = cache_stats()

    assert stats.max_entries == 2
    assert stats.entries <= 2
    assert stats.evictions >= 1


def test_clear_empties_the_store_but_leaves_it_enabled() -> None:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    backend = AerSimulator()

    with enabled():
        transpiled(circuit, backend)
        assert cache_stats().entries == 1
        clear()
        stats = cache_stats()
        assert stats.entries == 0
        assert stats.enabled is True







def test_cached_and_uncached_runs_produce_identical_observable_evidence() -> None:




    scenario = _scenario()

    disable()
    clear()
    uncached = run_scenario(scenario).detector_view()

    clear()
    with enabled():
        cached = run_scenario(scenario).detector_view()
        stats = cache_stats()
        assert stats.enabled is True

    assert stats.misses > 0, "the cached run must actually have transpiled something"
    assert _observable_signature(cached) == _observable_signature(uncached)


def test_a_warm_cache_still_produces_identical_evidence() -> None:



    scenario = _scenario()

    clear()
    with enabled():
        first = run_scenario(scenario).detector_view()
        hits_before = cache_stats().hits
        second = run_scenario(scenario).detector_view()
        hits_after = cache_stats().hits

    assert hits_after > hits_before, "the second run should have hit the cache"
    assert _observable_signature(second) == _observable_signature(first)


def test_the_cache_does_not_change_the_seed_derivation() -> None:



    scenario = _scenario(random_seed=7)

    disable()
    clear()
    uncached = run_scenario(scenario).detector_view()

    clear()
    with enabled():
        cached = run_scenario(scenario).detector_view()

    assert cached.simulator_seed == uncached.simulator_seed
    assert cached.simulator_seed == 7


def test_the_cache_preserves_results_across_several_scenarios() -> None:


    from backend.noise.base import NoiseConfig

    cases = [
        _scenario(random_seed=1),
        _scenario(random_seed=2, measurement_mode="projective-analytic"),
        _scenario(
            random_seed=3,
            noise=NoiseConfig(noise_type="depolarizing", noise_strength=0.05),
        ),
        _scenario(random_seed=4, state_count=20),
    ]

    disable()
    clear()
    uncached = [_observable_signature(run_scenario(case).detector_view()) for case in cases]

    clear()
    with enabled():
        cached = [_observable_signature(run_scenario(case).detector_view()) for case in cases]

    assert cached == uncached


def test_the_cache_is_still_off_after_a_benchmark_style_run() -> None:


    clear()
    with enabled():
        run_scenario(_scenario())
    assert is_enabled() is False
    assert cache_stats().enabled is False
