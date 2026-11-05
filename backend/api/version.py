"""Version metadata for the API boundary.

Two versions are deliberately separate concepts and must not be conflated:

* the **API version** (``v1``) versions the HTTP contract;
* the **reference protocol version** (``RQDS-TP-1.0``) versions the QDS
  construction that the API exposes.

They move independently. A protocol change does not renumber the API, and an
additive API change does not touch the protocol.

Nothing here is fabricated. A version is reported only when it can actually be
read from project metadata or from an installed distribution; when it cannot be
read the field is omitted rather than guessed.
"""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path
from typing import Dict, Optional


API_VERSION = "v1"


API_PREFIX = f"/api/{API_VERSION}"


PROJECT_DISTRIBUTION = "sih26141"


REPORTED_PACKAGES = (
    "qiskit",
    "qiskit-aer",
    "numpy",
    "scipy",
    "fastapi",
    "starlette",
    "pydantic",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _distribution_version(name: str) -> Optional[str]:
    """Return the installed version of ``name``, or ``None`` if not installed."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _pyproject_version() -> Optional[str]:
    """Return ``[project].version`` from ``pyproject.toml``, or ``None``.

    The fallback matters because the project is not necessarily installed as a
    distribution: running straight from a checkout is the normal case here.
    """
    path = _REPO_ROOT / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = data.get("project", {}).get("version")
    return str(value) if value else None


def application_version() -> Optional[str]:
    """Return the application version, or ``None`` when it cannot be read."""
    return _distribution_version(PROJECT_DISTRIBUTION) or _pyproject_version()


def protocol_version() -> str:
    """Return the reference protocol version, read from the protocol package."""
    from backend.protocol import PROTOCOL_VERSION

    return str(PROTOCOL_VERSION)


def package_versions() -> Dict[str, str]:
    """Return ``{package: version}`` for every reported package that is installed."""
    found: Dict[str, str] = {}
    for name in REPORTED_PACKAGES:
        version = _distribution_version(name)
        if version is not None:
            found[name] = version
    return found
