"""The FastAPI application factory.

``create_app`` builds a fully wired application. It takes its settings and its
store as arguments rather than reading module-level globals, so a test can build
an isolated application with its own configuration and its own in-memory state.

What this layer is
------------------
An application boundary. Routes translate HTTP into typed calls on the service
layer; services translate those into calls on the M1-M6 packages. No quantum
circuit, noise equation, attack model, detection rule, threshold or security
statement is implemented here.
"""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.config import ApiSettings
from backend.api.errors import register_error_handlers
from backend.api.middleware import RequestContextMiddleware, configure_logging
from backend.api.routes import ROOT_ROUTERS, VERSIONED_ROUTERS
from backend.api.store import ApiStore
from backend.api.version import API_PREFIX, API_VERSION

APP_TITLE = "SIH26141 Backend API"

APP_DESCRIPTION = """
Backend API for the SIH26141 reference quantum-digital-signature prototype.

This layer **orchestrates** the validated engines. It reimplements none of them:
quantum mathematics, protocol logic, attack behaviour, noise equations, detection
logic, calibration statistics and security interpretation all live in their own
packages and are called through the service layer.

### Versioning

The API version and the reference protocol version are independent. This
application serves API `v1`; the protocol it exposes is versioned separately and
reported by `/version`.

### Where the operational endpoints live

`/health`, `/ready` and `/version` are mounted at the root, unversioned: an
orchestrator should not need to know the API version to ask whether the process is
alive. Every business endpoint is under `/api/v1`.

### What this API does not claim

* No endpoint answers "is this secure". Detection produces **evidence**, and the
  security endpoints return **assumption-conditioned** statements.
* There is no formal composition theorem, no forgery bound and no universal
  detection guarantee, and no response invents one.
* Ground truth is returned only by the evaluation endpoints (which need it to
  compute rates) and by the simulation endpoint when explicitly requested.

### Storage

Sessions, calibrations and evaluations are held in memory and are **lost on
restart**. There is no database. The replay ledger is likewise in-memory and
single-process.
"""

OPENAPI_TAGS = [
    {
        "name": "operations",
        "description": "Liveness, readiness and version. Cheap, deterministic, no simulation.",
    },
    {"name": "sessions", "description": "Create, sign and expire reference signing sessions."},
    {"name": "verification", "description": "Verify a transcript with the M2 verifier."},
    {"name": "simulation", "description": "Run an M3 scenario. Observable output by default."},
    {"name": "detection", "description": "Run the M4 detector over observable input only."},
    {"name": "calibration", "description": "Derive a threshold, or read the reference operating point."},
    {"name": "evaluation", "description": "Run the M5 benchmark. Consumes ground truth explicitly."},
    {"name": "security", "description": "M6 assumptions, observability, composition and interpretation."},
]


def create_app(
    *,
    settings: Optional[ApiSettings] = None,
    store: Optional[ApiStore] = None,
) -> FastAPI:
    """Build and return the application."""
    resolved_settings = settings if settings is not None else ApiSettings.from_environment()
    resolved_store = store if store is not None else ApiStore()

    configure_logging()

    app = FastAPI(
        title=APP_TITLE,
        version=API_VERSION,
        description=APP_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "SIH26141"},
        license_info={"name": "See LICENSE"},
    )
    app.state.settings = resolved_settings
    app.state.store = resolved_store



    app.add_middleware(RequestContextMiddleware, settings=resolved_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)

    for router in ROOT_ROUTERS:
        app.include_router(router)
    for router in VERSIONED_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)

    return app
