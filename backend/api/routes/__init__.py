"""Route modules, grouped by concern.

``ROOT_ROUTERS`` are operational endpoints mounted at the root: an orchestrator
should not have to know the API version to ask whether the process is alive.
``VERSIONED_ROUTERS`` are the business endpoints, all mounted under ``/api/v1``.
"""

from __future__ import annotations

from backend.api.routes import (
    calibration,
    detection,
    evaluation,
    health,
    security,
    sessions,
    simulations,
    verification,
)


ROOT_ROUTERS = (health.router,)


VERSIONED_ROUTERS = (
    sessions.router,
    verification.router,
    simulations.router,
    detection.router,
    calibration.router,
    evaluation.router,
    security.router,
)

ALL_ROUTERS = ROOT_ROUTERS + VERSIONED_ROUTERS

__all__ = ["ROOT_ROUTERS", "VERSIONED_ROUTERS", "ALL_ROUTERS"]
