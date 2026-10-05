"""Read-only MCP tools backed by the same synthetic evidence functions."""
from datetime import datetime
from mcp.server import MCPServer

from app.data import get_scenario, scenarios
from app.investigation import deployment_findings, log_findings, metric_findings

mcp = MCPServer("incident-response-copilot")


@mcp.tool()
def list_incidents() -> list[dict]:
    """List available synthetic incident scenarios and their services."""
    return [{"id": s["id"], "title": s["title"], "service": s["service"],
             "start_time": s["start_time"]} for s in scenarios()]


@mcp.tool()
def search_logs(scenario_id: str, level: str = "", query: str = "",
                service: str = "", start_time: str = "", end_time: str = "") -> dict:
    """Search fixture logs by time range, service, level, or message text.

    Timestamps must be ISO-8601 strings. Empty filters are ignored. Evidence includes stable
    source IDs and timestamps so findings can be checked against the synthetic fixture.
    """
    scenario = get_scenario(scenario_id)
    start = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else None
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else None
    rows = []
    for row in scenario["logs"]:
        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        if level and row["level"].lower() != level.lower():
            continue
        if service and row["service"].lower() != service.lower():
            continue
        if query and query.lower() not in row["message"].lower():
            continue
        if start and timestamp < start:
            continue
        if end and timestamp > end:
            continue
        rows.append({"id": row["id"], "timestamp": row["timestamp"], "source": "logs",
                     "excerpt": row["message"], "service": row["service"], "level": row["level"]})
    return {"scenario_id": scenario_id, "evidence": rows}


@mcp.tool()
def summarize_error_signatures(scenario_id: str) -> dict:
    """Group repeated ERROR messages and return their counts with source evidence."""
    result = log_findings(get_scenario(scenario_id))
    return {"scenario_id": scenario_id, "error_groups": result["error_groups"],
            "evidence": [row for row in result["evidence"]
                         if any(group["signature"] == row["excerpt"]
                                for group in result["error_groups"])]}


@mcp.tool()
def inspect_metrics(scenario_id: str) -> dict:
    """Compare fixture latency, error rate, and traffic before/after incident start."""
    return metric_findings(get_scenario(scenario_id))


@mcp.tool()
def recent_deployments(scenario_id: str) -> dict:
    """List fixture deployments around the incident start time."""
    return deployment_findings(get_scenario(scenario_id))


@mcp.tool()
def get_incident(scenario_id: str) -> dict:
    """Get a scenario's metadata and timeline start; excludes the hidden expected cause."""
    scenario = get_scenario(scenario_id)
    return {k: v for k, v in scenario.items() if k != "expected_cause"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
