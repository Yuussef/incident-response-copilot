import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.data import scenarios
from app.investigation import deployment_findings, investigate, log_findings, metric_findings
from app.mcp_server import mcp, search_logs, summarize_error_signatures
from app.main import app


def test_deterministic_evaluation_cases_match_expected_causes():
    cases = json.loads((Path(__file__).parents[1] / "data/evaluations/cases.json").read_text())
    for case in cases:
        report = investigate(case["scenario_id"])
        assert report["root_cause"] == case["expected_cause"]
        assert set(case["required_evidence_ids"]) <= {row["id"] for row in report["evidence"]}
        assert report["evidence"]
        assert report["timeline"] == sorted(report["timeline"], key=lambda x: x["timestamp"])
        assert {"logs", "metrics", "deployments", "investigator", "reporter"} <= {
            result["agent"] for result in report["agent_results"]}


def test_specialist_tools_return_provenance():
    scenario = scenarios()[0]
    for result in (log_findings(scenario), metric_findings(scenario), deployment_findings(scenario)):
        assert result["evidence"]
        assert all({"id", "timestamp", "source", "excerpt"} <= set(row)
                   for row in result["evidence"])


def test_api_lists_scenarios_and_rejects_unknown_id():
    client = TestClient(app)
    assert len(client.get("/api/scenarios").json()) == 3
    assert client.post("/api/investigations", json={"scenario_id": "missing"}).status_code == 404


def test_mcp_registers_read_only_tools_and_filters_logs():
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"list_incidents", "get_incident", "search_logs", "summarize_error_signatures",
            "inspect_metrics", "recent_deployments"} <= names
    result = search_logs("deployment-regression", service="checkout-api", level="INFO",
                         start_time="2026-04-10T09:50:00Z", end_time="2026-04-10T10:00:00Z")
    assert [row["id"] for row in result["evidence"]] == ["log-104"]
    summary = summarize_error_signatures("deployment-regression")
    assert summary["error_groups"][0]["count"] == 2
    assert all(row["source"] == "logs" for row in summary["evidence"])
