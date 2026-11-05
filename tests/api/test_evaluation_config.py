"""Evaluation is bounded by the profile allow-list, not by a settings cap.

``ApiSettings`` used to declare a bound on the number of evaluation trials that
no code path ever read. Evaluation is bounded instead by the benchmark profile a
caller selects: ``smoke`` and ``reference`` are the only accepted profiles, and
the trial count is a property of the profile itself, so there is no
client-supplied evaluation count for a setting to cap.

A bound that appears to limit work but is never consulted is worse than no bound:
an operator could tighten it, restart, and observe no change. These tests pin its
removal so that reintroducing a dead bound fails here.
"""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

from backend.api import ApiSettings
from backend.api.schemas.evaluation import ALLOWED_PROFILES, EvaluationRunRequest
from backend.evaluation import SMOKE_PROFILE

from .conftest import repository_text_files



REMOVED_SETTING = "max_evaluation" + "_trials"


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]







def test_the_settings_declare_no_evaluation_trial_bound() -> None:
    assert REMOVED_SETTING not in {f.name for f in dataclasses.fields(ApiSettings)}
    assert not hasattr(ApiSettings(), REMOVED_SETTING)


def test_the_removed_setting_cannot_be_passed_to_the_settings() -> None:
    """Construction refuses it, so it cannot be re-declared by accident."""
    with pytest.raises(TypeError):
        ApiSettings(**{REMOVED_SETTING: 1})


def test_the_repository_scan_reads_the_files_it_is_meant_to_check() -> None:
    """Guard the guard: a scan that read nothing would pass vacuously."""
    relative = {
        path.relative_to(REPO_ROOT).as_posix() for path in repository_text_files()
    }
    assert "backend/api/config.py" in relative
    assert "backend/api/schemas/evaluation.py" in relative
    assert "tests/api/test_evaluation_config.py" in relative
    assert len(relative) > 100, f"only {len(relative)} files scanned"


def test_no_source_test_or_document_names_the_removed_setting() -> None:
    offenders = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in repository_text_files()
        if REMOVED_SETTING in path.read_text(encoding="utf-8", errors="ignore")
    )
    assert offenders == [], f"stale references to the removed setting: {offenders}"







def test_the_request_offers_no_trial_count_for_a_setting_to_cap() -> None:
    """The only evaluation input is an allow-listed profile name."""
    assert set(EvaluationRunRequest.model_fields) == {"profile"}
    assert ALLOWED_PROFILES == ("smoke", "reference")


def test_evaluation_trials_are_a_property_of_the_selected_profile(
    evaluation_run,
) -> None:
    """The reported trial count comes from the profile, not from a setting.

    This is also the default-behaviour check: an application built with no
    explicit settings still runs the smoke profile and reports the profile's own
    trial count.
    """
    configuration = evaluation_run["configuration"]
    assert configuration["profile"] == SMOKE_PROFILE.name
    assert configuration["evaluation_trials"] == SMOKE_PROFILE.evaluation_trials


def test_a_request_cannot_smuggle_the_removed_bound_back_in(client) -> None:
    """An unknown field is refused, so the bound cannot return through a body."""
    response = client.post(
        "/api/v1/evaluation/run",
        json={"profile": "smoke", REMOVED_SETTING: 1},
    )
    assert response.status_code == 422
