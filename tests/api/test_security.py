"""Security-analysis endpoints, and the boundaries they must preserve."""

from __future__ import annotations

import json


def test_assumptions_returns_the_register(client) -> None:
    response = client.get("/api/v1/security/assumptions")
    assert response.status_code == 200
    body = response.json()
    assert body["assumptions"]
    for assumption in body["assumptions"]:
        assert assumption["key"]
        assert assumption["statement"]
        assert assumption["status"]
        assert assumption["consequence_if_violated"]
    assert body["summary"]
    assert body["by_status"]


def test_the_api_reports_domain_statuses_verbatim(client) -> None:

    statuses = {item["status"] for item in client.get("/api/v1/security/assumptions").json()["assumptions"]}
    assert statuses <= {"exact", "satisfied", "approximate", "not_verified", "violated"}


def test_assumptions_marks_the_weak_one(client) -> None:
    body = client.get("/api/v1/security/assumptions").json()


    assert "attacks_are_non_adaptive" in body["weaker_than_exact"]


def test_assumptions_depend_on_the_channel(client) -> None:
    depolarizing = client.get(
        "/api/v1/security/assumptions", params={"noise_type": "depolarizing"}
    ).json()
    bit_flip = client.get(
        "/api/v1/security/assumptions", params={"noise_type": "bit_flip"}
    ).json()
    status = {
        item["key"]: item["status"]
        for item in depolarizing["assumptions"]
        if item["key"] == "homogeneous_mismatch_probability"
    }
    other = {
        item["key"]: item["status"]
        for item in bit_flip["assumptions"]
        if item["key"] == "homogeneous_mismatch_probability"
    }


    assert status["homogeneous_mismatch_probability"] == "exact"
    assert other["homogeneous_mismatch_probability"] == "approximate"


def test_observability_keeps_the_per_threat_breakdown(client) -> None:
    body = client.get("/api/v1/security/observability").json()
    threats = {row["threat"] for row in body["rows"]}
    assert threats == {
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
        "intercept_resend",
        "channel_tampering",
    }
    assert len(body["quantum_visible"]) == 2
    assert len(body["classical_only"]) == 4
    assert set(body["quantum_visible"]) | set(body["classical_only"]) == threats


def test_observability_does_not_conflate_the_two_kinds_of_invisible(client) -> None:
    body = client.get("/api/v1/security/observability").json()
    by_threat = {row["threat"]: row for row in body["rows"]}
    for threat in body["classical_only"]:
        row = by_threat[threat]


        assert row["detector_visible_quantum"] is False
        assert row["requires_classical_control"] is True
    for threat in body["quantum_visible"]:
        assert by_threat[threat]["detector_visible_quantum"] is True
        assert by_threat[threat]["requires_classical_control"] is False
    assert any("does not mean the threat is undetectable" in item for item in body["security_assessment"]["limitations"])


def test_composition_denies_a_formal_theorem(client) -> None:
    body = client.get("/api/v1/security/composition").json()
    assert body["formal_composition_theorem_present"] is False
    assert body["component_count"] == 6
    assert body["unresolved_count"] == 6
    for component in body["components"]:
        assert component["unresolved_dependency"], component["component"]
        assert component["security_conclusion"]


def test_analyze_flags_a_forbidden_claim(client) -> None:
    body = client.post(
        "/api/v1/security/analyze",
        json={"statements": ["This proves the protocol is information-theoretically secure."]},
    ).json()
    assert body["checks"][0]["verdict"] == "forbidden"
    assert body["checks"][0]["violations"]
    assert body["checks"][0]["reasons"]


def test_analyze_allows_an_honest_disclosure(client) -> None:
    body = client.post(
        "/api/v1/security/analyze",
        json={"statements": ["no formal forgery bound is derived at this milestone"]},
    ).json()
    assert body["checks"][0]["verdict"] == "allowed"


def test_analyze_lists_the_boundary(client) -> None:
    body = client.post("/api/v1/security/analyze", json={"statements": []}).json()
    assert len(body["forbidden_claims"]) >= 3
    assert {item["term"] for item in body["banned_terminology"]} == {"decoy", "decoy-state"}
    assert body["allowed_statement_example"]
    assert "empirical" in body["allowed_statement_example"]


def test_analyze_refuses_too_many_statements(client) -> None:

    response = client.post(
        "/api/v1/security/analyze", json={"statements": ["x"] * 51}
    )
    assert response.status_code == 422






SECURITY_PATHS = (
    "/api/v1/security/assumptions",
    "/api/v1/security/observability",
    "/api/v1/security/composition",
)


def test_every_security_response_carries_an_assessment(client) -> None:
    for path in SECURITY_PATHS:
        assessment = client.get(path).json()["security_assessment"]
        assert assessment["status"] == "assumption_conditioned", path
        assert assessment["formal_proof_present"] is False, path
        assert assessment["composable_security_established"] is False, path
        assert assessment["universal_detection_guarantee"] is False, path
        assert assessment["limitations"], path


def test_no_security_response_offers_a_boolean_verdict(client) -> None:
    payloads = [client.get(path).json() for path in SECURITY_PATHS]
    payloads.append(client.post("/api/v1/security/analyze", json={"statements": []}).json())
    for body in payloads:
        rendered = json.dumps(body)
        assert '"secure": true' not in rendered
        assert '"is_secure"' not in rendered
        assert '"information_theoretically_secure"' not in rendered
        assert '"unforgeable"' not in rendered
