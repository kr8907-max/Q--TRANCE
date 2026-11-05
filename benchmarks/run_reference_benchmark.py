"""Run the Milestone 5 benchmark and write its artifacts.

Usage
-----
From the repository root, with the project virtual environment::

    PYTHONPATH=. .venv/Scripts/python.exe benchmarks/run_reference_benchmark.py

    # a fast profile, for checking the pipeline still runs end to end
    PYTHONPATH=. .venv/Scripts/python.exe benchmarks/run_reference_benchmark.py --profile smoke

Output
------
``benchmarks/<profile-name>.json`` and ``benchmarks/<profile-name>.md`` -- for
the reference profile, ``benchmarks/m5-reference.json`` and
``benchmarks/m5-reference.md``.

What this script is for
-----------------------
Every number in the recorded benchmark comes from a run performed by this
script. Nothing is read from a stored result and nothing is extrapolated, so
re-running it is the only way to check the reported numbers, and it is meant to
be re-run. The JSON payload carries the profile, the protocol version, the
Python and platform versions, the seed blocks, the number of scenarios run and
the measured runtime, so a reader can tell what produced the numbers.

Cost
----
The reference profile simulates roughly 3.8e5 states and takes on the order of
tens of minutes. It is dominated by circuit transpilation, so it runs with the
explicit transpile cache enabled; that cache stores compiled circuits and never
outcomes, and ``tests/quantum/test_cache.py`` proves it does not change a
result. The uncached path is available with ``--no-cache`` if a reader wants to
confirm that for themselves.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.evaluation.benchmark import (  # noqa: E402
    REFERENCE_PROFILE,
    SMOKE_PROFILE,
    BenchmarkProfile,
    run_benchmark,
)
from backend.evaluation.reports import (  # noqa: E402
    render_markdown,
    write_json,
    write_markdown,
)

PROFILES: dict[str, BenchmarkProfile] = {
    "reference": REFERENCE_PROFILE,
    "smoke": SMOKE_PROFILE,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 5 benchmark and write its artifacts.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="reference",
        help="which declared profile to run (default: reference)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "benchmarks"),
        help="where to write the artifacts (default: <repo>/benchmarks)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="disable the transpile cache; much slower, and used only to confirm "
        "that the cache does not change a result",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-step progress",
    )
    args = parser.parse_args(argv)

    profile = PROFILES[args.profile]
    output_dir = Path(args.output_dir)

    if not args.quiet:
        print(
            f"running profile {profile.name!r}: "
            f"{profile.total_planned_states} states planned, "
            f"cache {'off' if args.no_cache else 'on'}",
            flush=True,
        )

    started = time.perf_counter()
    progress = None if args.quiet else (lambda message: print(f"  {message}", flush=True))
    result = run_benchmark(
        profile, progress=progress, use_transpile_cache=not args.no_cache
    )
    elapsed = time.perf_counter() - started

    payload = result["report"]
    markdown = result["markdown"]

    if args.no_cache:




        payload["provenance"]["transpile_cache"] = {
            "enabled_during_run": False,
            "note": (
                "this run was made with --no-cache, so the transpile cache was "
                "not used at any point; the cache stores compiled circuits and "
                "never outcomes, and it is off by default everywhere else in the "
                "project"
            ),
        }
        markdown = render_markdown(payload)

    json_path = output_dir / f"{profile.name}.json"
    markdown_path = output_dir / f"{profile.name}.md"
    write_json(payload, str(json_path))
    write_markdown(markdown, str(markdown_path))

    if not args.quiet:
        print(
            f"wrote {json_path.relative_to(REPO_ROOT)} and "
            f"{markdown_path.relative_to(REPO_ROOT)} in {elapsed:.1f}s",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
