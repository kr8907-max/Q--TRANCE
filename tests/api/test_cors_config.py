"""CORS configuration: the wildcard opt-in is a parse-time validation.

``ApiSettings`` used to carry a second, write-only boolean recording whether a
wildcard origin had been asked for. Nothing read it: the CORS middleware is built
from ``cors_origins`` alone (``backend/api/app.py``), wildcard detection is
already ``ApiSettings.cors_is_wildcard``, and the "``*`` must be asked for"
policy is enforced where the environment is parsed.

These tests pin that design. The redundant field is gone, and the real HTTP CORS
behaviour -- including the deliberate wildcard opt-in -- is unchanged.
"""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

from backend.api import ApiSettings
from backend.api.config import ENV_ALLOW_WILDCARD_CORS, ENV_CORS_ORIGINS

from .conftest import configured_client, repository_text_files



REMOVED_FIELD = "allow_wildcard" + "_cors"


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

ALLOWED_ORIGIN = "http://localhost:5173"
UNKNOWN_ORIGIN = "http://evil.example"







def test_the_settings_declare_no_wildcard_permission_field() -> None:
    assert REMOVED_FIELD not in {f.name for f in dataclasses.fields(ApiSettings)}
    assert not hasattr(ApiSettings(), REMOVED_FIELD)


def test_the_removed_field_cannot_be_passed_to_the_settings() -> None:
    """Construction refuses it, so it cannot be re-declared by accident."""
    with pytest.raises(TypeError):
        ApiSettings(**{REMOVED_FIELD: True})


def test_the_repository_scan_reads_the_files_it_is_meant_to_check() -> None:
    """Guard the guard: a scan that read nothing would pass vacuously."""
    relative = {path.relative_to(REPO_ROOT).as_posix() for path in repository_text_files()}
    assert "backend/api/config.py" in relative
    assert "backend/api/app.py" in relative
    assert "docs/api/integration.md" in relative
    assert len(relative) > 100, f"only {len(relative)} files scanned"


def test_no_source_test_or_document_names_the_removed_field() -> None:
    offenders = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in repository_text_files()
        if REMOVED_FIELD in path.read_text(encoding="utf-8", errors="ignore")
    )
    assert offenders == [], f"stale references to the removed field: {offenders}"







def test_the_environment_opt_in_still_gates_a_wildcard_origin() -> None:
    """The opt-in is enforced where the environment is parsed, and still works."""
    with pytest.raises(ValueError, match="wildcard"):
        ApiSettings.from_environment({ENV_CORS_ORIGINS: "*"})

    opted_in = ApiSettings.from_environment(
        {ENV_CORS_ORIGINS: "*", ENV_ALLOW_WILDCARD_CORS: "1"}
    )
    assert opted_in.cors_origins == ("*",)
    assert opted_in.cors_is_wildcard is True


def test_the_documented_environment_variables_match_the_code() -> None:
    """The documented configuration must be the configuration the code reads."""
    doc = (REPO_ROOT / "docs/api/integration.md").read_text(encoding="utf-8")
    assert ENV_CORS_ORIGINS in doc
    assert ENV_ALLOW_WILDCARD_CORS in doc
    assert ENV_ALLOW_WILDCARD_CORS == "SIH26141_API_ALLOW_WILDCARD_CORS"


def test_the_default_origins_are_the_documented_development_ports() -> None:
    settings = ApiSettings()
    assert settings.cors_origins == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    assert settings.cors_is_wildcard is False







def test_an_allowed_origin_receives_cors_headers(client) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_an_unknown_origin_receives_no_cors_headers(client) -> None:
    response = client.get("/health", headers={"Origin": UNKNOWN_ORIGIN})
    assert response.headers.get("access-control-allow-origin") is None


def test_a_preflight_from_an_allowed_origin_is_answered(client) -> None:
    response = client.options(
        "/api/v1/sessions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_a_preflight_from_an_unknown_origin_is_not_authorised(client) -> None:
    response = client.options(
        "/api/v1/sessions",
        headers={
            "Origin": UNKNOWN_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_credentials_are_never_allowed(client) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.headers.get("access-control-allow-credentials") is None


def test_a_custom_origin_list_is_enforced_over_http() -> None:
    custom = configured_client(cors_origins=("https://a.example",))
    allowed = custom.get("/health", headers={"Origin": "https://a.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://a.example"
    other = custom.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert other.headers.get("access-control-allow-origin") is None


def test_a_deliberate_wildcard_echoes_any_origin_over_http() -> None:
    wildcard = configured_client(cors_origins=("*",))
    response = wildcard.get("/health", headers={"Origin": UNKNOWN_ORIGIN})
    assert response.headers["access-control-allow-origin"] == "*"


def test_two_applications_keep_their_own_origins() -> None:
    """No global state: one application's origins never reach another's."""
    first = configured_client(cors_origins=("https://a.example",))
    second = configured_client(cors_origins=("https://b.example",))

    assert (
        first.get("/health", headers={"Origin": "https://a.example"}).headers[
            "access-control-allow-origin"
        ]
        == "https://a.example"
    )
    assert (
        first.get("/health", headers={"Origin": "https://b.example"}).headers.get(
            "access-control-allow-origin"
        )
        is None
    )
    assert (
        second.get("/health", headers={"Origin": "https://b.example"}).headers[
            "access-control-allow-origin"
        ]
        == "https://b.example"
    )
    assert (
        second.get("/health", headers={"Origin": "https://a.example"}).headers.get(
            "access-control-allow-origin"
        )
        is None
    )
