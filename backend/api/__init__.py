"""Milestone 7: the backend API.

An application boundary over the M1-M6 engines, not a second implementation of
them. Every route translates HTTP into a typed call on the service layer, and
every service calls an existing package:

============================  ==========================================
:mod:`backend.protocol`       session creation, signing, verification
:mod:`backend.simulation`     scenario execution
:mod:`backend.detection`      observable detection
:mod:`backend.calibration`    baseline estimation and threshold derivation
:mod:`backend.evaluation`     benchmark runs and metrics
:mod:`backend.security`       assumptions, observability, composition
============================  ==========================================

The dependency direction is one-way: ``backend.api`` imports those packages and
none of them imports ``backend.api``.

Storage is in memory and is lost on restart. The API has no authentication and
says so; it is a prototype boundary for the frontend, not a deployed service.
"""

from backend.api.app import create_app
from backend.api.config import ApiSettings
from backend.api.store import ApiStore

__all__ = ["create_app", "ApiSettings", "ApiStore"]
