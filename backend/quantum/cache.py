"""Explicit, opt-in memoisation of circuit transpilation.

Why this module exists
----------------------
Signing one signature state costs one three-qubit teleportation circuit, and the
dominant cost of executing it is **transpilation against the Aer target**, not
the simulation itself. Measured on the reference machine, ``transpile(circuit,
AerSimulator())`` takes roughly 85 ms, while the one-shot simulation that
follows takes well under a millisecond.

The reference protocol has exactly six signature states, so a session of ``N``
states constructs the *same six circuits* ``N / 6`` times over. Transpiling
them again each time is pure waste: transpilation is a deterministic pure
function of ``(circuit, backend configuration, seed_transpiler)``.

What this module guarantees
---------------------------
1. **Off by default.** Importing this module changes nothing. ``run_counts``
   behaves exactly as it did in Milestone 1 unless a caller explicitly enables
   the cache, so every Milestone 1-4 test and every recorded result is
   bit-for-bit unaffected by the existence of this module.
2. **Result-preserving.** A cache hit returns the object that the uncached call
   would have returned, for the same key. The key covers the circuit (via a
   canonical ``qpy`` serialisation), the transpiler seed, and the backend
   configuration, so two different inputs cannot collide.
3. **Explicit and inspectable.** Enabling, disabling, clearing and reading
   statistics are separate, named operations; :func:`cache_stats` reports hits,
   misses, entries and evictions so a caller can prove the cache was used and
   measure what it saved.
4. **Bounded.** The store is a fixed-capacity FIFO map, so a long-running
   process cannot grow without limit.

What this module is not
-----------------------
It is **not** a result cache. Nothing derived from a simulation outcome is
stored here -- only the compiled form of a circuit. Two runs that differ only in
their seeds therefore share a transpiled circuit but produce their own,
independent simulation results.

The cache is also not a correctness mechanism. Every number this project
reports is reproducible with the cache disabled; the cache only removes
repeated work.
"""

from __future__ import annotations

import hashlib
import io
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Tuple

from qiskit import QuantumCircuit, qpy

__all__ = [
    "DEFAULT_MAX_ENTRIES",
    "CacheStats",
    "CacheError",
    "circuit_digest",
    "backend_key",
    "transpiled",
    "enable",
    "disable",
    "clear",
    "is_enabled",
    "cache_stats",
    "enabled",
]





DEFAULT_MAX_ENTRIES = 64


class CacheError(RuntimeError):
    """Raised for a programming error in cache use."""


@dataclass(frozen=True)
class CacheStats:
    """A snapshot of the transpiled-circuit store."""

    enabled: bool
    entries: int
    max_entries: int
    hits: int
    misses: int
    evictions: int

    @property
    def lookups(self) -> int:
        """Return the number of lookups served."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float | None:
        """Return ``hits / lookups``, or ``None`` before any lookup."""
        if self.lookups == 0:
            return None
        return self.hits / self.lookups

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "entries": self.entries,
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "lookups": self.lookups,
            "hit_rate": self.hit_rate,
        }







_STORE: "Dict[Tuple[str, int, str], QuantumCircuit]" = {}
_ENABLED = False
_MAX_ENTRIES = DEFAULT_MAX_ENTRIES
_HITS = 0
_MISSES = 0
_EVICTIONS = 0


def is_enabled() -> bool:
    """Return whether the transpiled-circuit cache is currently active."""
    return _ENABLED


def enable(*, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
    """Activate the cache with a bounded capacity.

    Enabling does not clear the store: a caller that wants a cold start calls
    :func:`clear` as well. Counters are not reset, so a caller can measure
    across an enable/disable cycle.
    """
    global _ENABLED, _MAX_ENTRIES
    if isinstance(max_entries, bool) or not isinstance(max_entries, int):
        raise CacheError(
            f"max_entries must be an int, got {type(max_entries).__name__}"
        )
    if max_entries < 1:
        raise CacheError(f"max_entries must be at least 1, got {max_entries}")
    _MAX_ENTRIES = max_entries
    _ENABLED = True
    _evict_to_capacity()


def disable() -> None:
    """Deactivate the cache. The store is retained until :func:`clear`."""
    global _ENABLED
    _ENABLED = False


def clear() -> None:
    """Empty the store and reset the counters."""
    global _HITS, _MISSES, _EVICTIONS
    _STORE.clear()
    _HITS = 0
    _MISSES = 0
    _EVICTIONS = 0


def cache_stats() -> CacheStats:
    """Return a snapshot of the store and its counters."""
    return CacheStats(
        enabled=_ENABLED,
        entries=len(_STORE),
        max_entries=_MAX_ENTRIES,
        hits=_HITS,
        misses=_MISSES,
        evictions=_EVICTIONS,
    )


@contextmanager
def enabled(*, max_entries: int = DEFAULT_MAX_ENTRIES) -> Iterator[None]:
    """Enable the cache for the duration of the block, then restore.

    The previous enabled/disabled state is restored on exit, so nesting and
    exception paths cannot leave the cache silently switched on.
    """
    global _MAX_ENTRIES
    was_enabled = _ENABLED
    previous_max = _MAX_ENTRIES
    enable(max_entries=max_entries)
    try:
        yield
    finally:
        _MAX_ENTRIES = previous_max
        if was_enabled:
            enable(max_entries=previous_max)
        else:
            disable()


def _evict_to_capacity() -> None:
    """Drop the oldest entries until the store fits its capacity."""
    global _EVICTIONS
    while len(_STORE) > _MAX_ENTRIES:
        oldest = next(iter(_STORE))
        del _STORE[oldest]
        _EVICTIONS += 1







def circuit_digest(circuit: QuantumCircuit) -> str:
    """Return a canonical SHA-256 digest of ``circuit``.

    The circuit is serialised with Qiskit's own ``qpy`` format, which is the
    SDK's canonical machine-readable circuit encoding. That makes the digest
    depend on the circuit's full content -- gates, parameters, registers,
    ordering -- rather than on object identity or on a ``repr`` that could
    drift between Qiskit versions.
    """
    if not isinstance(circuit, QuantumCircuit):
        raise CacheError(
            f"expected a QuantumCircuit, got {type(circuit).__name__}"
        )
    buffer = io.BytesIO()
    qpy.dump(circuit, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def backend_key(backend: Any) -> str:
    """Return a stable description of the backend a transpile targeted.

    The transpiled circuit depends on the backend's configuration, so the key
    must too. The class name alone is not enough -- two ``AerSimulator``
    instances with different options have different targets -- so the backend's
    options are folded in as well. ``repr`` of an options mapping is stable for
    the SDK's own option containers.
    """
    if backend is None:
        return "no-backend"
    options = getattr(backend, "options", None)
    rendered = repr(dict(options)) if hasattr(options, "items") else repr(options)
    return f"{type(backend).__module__}.{type(backend).__qualname__}|{rendered}"


def transpiled(circuit: QuantumCircuit, backend: Any, *, seed_transpiler: int = 0):
    """Return ``transpile(circuit, backend, seed_transpiler=seed_transpiler)``.

    The call is memoised only while the cache is enabled. With the cache
    disabled -- the default -- this is a plain pass-through to Qiskit's
    transpiler, which is what keeps Milestone 1-4 behaviour unchanged.
    """
    if not _ENABLED:
        from qiskit import transpile

        return transpile(circuit, backend, seed_transpiler=seed_transpiler)

    key = (circuit_digest(circuit), int(seed_transpiler), backend_key(backend))
    global _HITS, _MISSES
    stored = _STORE.get(key)
    if stored is not None:
        _HITS += 1
        return stored

    from qiskit import transpile

    compiled = transpile(circuit, backend, seed_transpiler=seed_transpiler)
    _MISSES += 1
    _STORE[key] = compiled
    _evict_to_capacity()
    return compiled
