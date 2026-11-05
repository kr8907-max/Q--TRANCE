"""Reproducibility: the same declaration must produce the same numbers.

Two distinct claims are pinned here.

**Determinism.** A trial is a pure function of its seed and its scenario, so
re-running the same seed must reproduce the same observable evidence *and* the
same decision. If it did not, no number in the report would mean anything.

**Cache neutrality.** The benchmark enables the transpile cache for its own
duration. That is only acceptable if the cache cannot change a result, so the
whole benchmark pipeline is run with the cache on and with it off and the two
reports are compared field by field, with only the measured runtime excluded.
This is the benchmark-level counterpart of the per-scenario comparison in
``tests/quantum/test_cache.py``.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from backend.calibration.models import DatasetRole
from backend.quantum.cache import is_enabled

from backend.evaluation.benchmark import run_benchmark
from backend.evaluation.sweeps import run_honest_population




_VOLATILE_PROVENANCE_KEYS = ("runtime_seconds",)



_CACHE_KEYS = ("transpile_cache",)



_RUNTIME_LINE = re.compile(r'"runtime_seconds":\s*[-+0-9.eE]+')


def _strip_runtime(text: str) -> str:
    """Return ``text`` with the measured runtime masked out."""
    return _RUNTIME_LINE.sub('"runtime_seconds": <measured>', text)


def _stable(payload: Any) -> Any:
    """Return ``payload`` with measured quantities removed, recursively."""
    if isinstance(payload, dict):
        return {
            key: _stable(value)
            for key, value in payload.items()
            if key not in _VOLATILE_PROVENANCE_KEYS and key not in _CACHE_KEYS
        }
    if isinstance(payload, list):
        return [_stable(item) for item in payload]
    return payload







def test_the_same_seed_block_reproduces_the_same_records(
    small_scenario, small_operating_point
) -> None:
    kwargs = dict(
        evaluation_id="repro-honest",
        seed_start=4242,
        trial_count=2,
        noise_type="depolarizing",
        noise_strength=0.02,
        dataset_role=DatasetRole.VALIDATION,
    )
    first = run_honest_population(small_scenario, small_operating_point, **kwargs)
    second = run_honest_population(small_scenario, small_operating_point, **kwargs)
    assert len(first) == len(second) == 2
    for left, right in zip(first, second):



        assert left.statistics.to_dict() == right.statistics.to_dict()
        assert left.decision.to_dict() == right.decision.to_dict()
        assert left.random_seed == right.random_seed
        assert left.scenario_fingerprint == right.scenario_fingerprint


def test_a_different_seed_block_produces_a_different_scenario(
    small_scenario, small_operating_point
) -> None:
    first = run_honest_population(
        small_scenario,
        small_operating_point,
        evaluation_id="repro-honest",
        seed_start=0,
        trial_count=1,
        noise_strength=0.02,
    )
    second = run_honest_population(
        small_scenario,
        small_operating_point,
        evaluation_id="repro-honest",
        seed_start=1,
        trial_count=1,
        noise_strength=0.02,
    )


    assert first[0].scenario_fingerprint != second[0].scenario_fingerprint
    assert first[0].random_seed != second[0].random_seed







@pytest.fixture(scope="module")
def repeated_runs(tiny_benchmark_profile):
    """Return ``(cached_a, uncached, cached_b)`` for the tiny profile.

    The tiny profile is used because the whole pipeline is run three times. It
    measures every section at a scale that finishes quickly, and none of its
    numbers is reported.
    """
    first = run_benchmark(tiny_benchmark_profile, use_transpile_cache=True)
    uncached = run_benchmark(tiny_benchmark_profile, use_transpile_cache=False)
    second = run_benchmark(tiny_benchmark_profile, use_transpile_cache=True)
    return first, uncached, second


def test_two_identical_benchmark_runs_produce_the_same_report(repeated_runs) -> None:
    first, _, second = repeated_runs
    assert _stable(first["report"]) == _stable(second["report"])


def test_two_identical_benchmark_runs_produce_the_same_markdown(repeated_runs) -> None:
    first, _, second = repeated_runs




    assert first["markdown"] != second["markdown"]
    assert _strip_runtime(first["markdown"]) == _strip_runtime(second["markdown"])


def test_the_transpile_cache_does_not_change_any_result(repeated_runs) -> None:
    first, uncached, _ = repeated_runs
    assert _stable(first["report"]) == _stable(uncached["report"])


def test_the_transpile_cache_is_reported_when_used_and_absent_when_not(
    repeated_runs,
) -> None:
    first, uncached, _ = repeated_runs
    assert first["report"]["provenance"]["transpile_cache"]["enabled_during_run"] is True
    assert "transpile_cache" not in uncached["report"]["provenance"]


def test_the_uncached_run_records_the_same_seed_allocation(repeated_runs) -> None:


    first, uncached, _ = repeated_runs
    assert (
        first["report"]["provenance"]["seed_blocks"]
        == uncached["report"]["provenance"]["seed_blocks"]
    )


def test_the_cache_is_left_disabled_after_a_benchmark_run(repeated_runs) -> None:


    assert is_enabled() is False


def test_only_the_runtime_and_the_cache_statistics_differ_between_cached_runs(
    repeated_runs,
) -> None:
    first, _, second = repeated_runs
    left = first["report"]["provenance"]
    right = second["report"]["provenance"]
    differing = sorted(
        key for key in set(left) | set(right) if left.get(key) != right.get(key)
    )
    assert differing == ["runtime_seconds"], differing
