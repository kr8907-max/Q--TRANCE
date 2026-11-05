"""Operational endpoints: liveness, readiness and version.

These are mounted at the root rather than under ``/api/v1``. An orchestrator or
load balancer should not have to know the API version to ask whether the process
is alive, and a version bump should not move the liveness probe.

None of them runs a simulation. ``/ready`` imports the component packages and
checks the store; it does not execute a scenario, calibrate anything or read the
benchmark artifact.
"""

from __future__ import annotations

import importlib
import platform

from fastapi import APIRouter, status

from backend.api.dependencies import SettingsDep, StoreDep
from backend.api.schemas.common import (
    HealthResponse,
    ReadyCheck,
    ReadyResponse,
    ServiceStatus,
    VersionResponse,
)
from backend.api.version import (
    API_VERSION,
    application_version,
    package_versions,
    protocol_version,
)

router = APIRouter(tags=["operations"])


REQUIRED_COMPONENTS = (
    ("protocol", "backend.protocol"),
    ("simulation", "backend.simulation"),
    ("detection", "backend.detection"),
    ("calibration", "backend.calibration"),
    ("evaluation", "backend.evaluation"),
    ("security", "backend.security"),
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness",
    description=(
        "Cheap and deterministic. Reports the API version, the reference protocol "
        "version and the counts of in-memory orchestration objects. Performs no "
        "simulation and exposes no secret."
    ),
)
def health(settings: SettingsDep, store: StoreDep) -> HealthResponse:
    return HealthResponse(
        status=ServiceStatus.OK,
        api_version=API_VERSION,
        protocol_version=protocol_version(),
        application_version=application_version(),
        environment=settings.environment,
        state=store.counts(),
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Version inventory",
    description=(
        "Reports the application version, the API version and the reference "
        "protocol version. The first two are independent of the third. Versions "
        "are read from project metadata and installed distributions; a version "
        "that cannot be read is omitted rather than invented."
    ),
)
def version() -> VersionResponse:
    return VersionResponse(
        application_version=application_version(),
        api_version=API_VERSION,
        protocol_version=protocol_version(),
        python_version=platform.python_version(),
        packages=package_versions(),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness",
    description=(
        "Verifies that the required component packages are importable and that "
        "the orchestration store responds. Deliberately does not run a quantum "
        "simulation, so it stays cheap enough to poll."
    ),
)
def ready(store: StoreDep) -> ReadyResponse:
    checks = [_component_check(name, module) for name, module in REQUIRED_COMPONENTS]
    checks.append(_store_check(store))
    return ReadyResponse(
        ready=all(check.ok for check in checks),
        checks=checks,
    )


def _component_check(name: str, module: str) -> ReadyCheck:
    try:
        importlib.import_module(module)
    except Exception as exc:  # pragma: no cover - only on a broken install
        return ReadyCheck(name=name, ok=False, detail=f"{module} failed to import: {exc}")
    return ReadyCheck(name=name, ok=True, detail=f"{module} importable")


def _store_check(store: StoreDep) -> ReadyCheck:
    try:
        counts = store.counts()
    except Exception as exc:  # pragma: no cover - only on a broken store
        return ReadyCheck(name="store", ok=False, detail=f"store unavailable: {exc}")
    return ReadyCheck(
        name="store",
        ok=True,
        detail=(
            f"in-memory store available; sessions={counts['sessions']} "
            f"calibrations={counts['calibrations']} evaluations={counts['evaluations']}"
        ),
    )
