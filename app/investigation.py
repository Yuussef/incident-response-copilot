"""Deterministic read-only evidence gathering and evidence-grounded diagnosis."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.data import get_scenario


def log_findings(s: dict[str, Any]) -> dict[str, Any]:
    logs = s["logs"]
    groups = Counter(row["message"] for row in logs if row["level"] == "ERROR")
    evidence = [{"id": row["id"], "timestamp": row["timestamp"], "source": "logs",
                 "excerpt": row["message"], "service": row["service"]}
                for row in logs if row["level"] in {"ERROR", "WARN"}]
    return {"agent": "logs", "summary": f"Found {len(evidence)} error/warning log entries; "
            f"{len(groups)} distinct error signatures.", "error_groups": [
                {"signature": msg, "count": count} for msg, count in groups.most_common()],
            "evidence": evidence}


def metric_findings(s: dict[str, Any]) -> dict[str, Any]:
    rows = sorted(s["metrics"], key=lambda r: r["timestamp"])
    before = [r for r in rows if r["timestamp"] < s["start_time"]]
    after = [r for r in rows if r["timestamp"] >= s["start_time"]]
    baseline = before[-1] if before else rows[0]
    peak = max(after or rows, key=lambda r: r["error_rate_pct"])
    volume_peak = max(after or rows, key=lambda r: r["requests_per_minute"])
    anomaly_point = next((row for row in after if
        row["latency_p95_ms"] >= baseline["latency_p95_ms"] * 2
        or row["error_rate_pct"] - baseline["error_rate_pct"] >= 5
        or row["requests_per_minute"] >= baseline["requests_per_minute"] * 2), None)
    latency_ratio = round(peak["latency_p95_ms"] / max(baseline["latency_p95_ms"], 1), 2)
    error_delta = round(peak["error_rate_pct"] - baseline["error_rate_pct"], 2)
    volume_ratio = round(peak["requests_per_minute"] / max(baseline["requests_per_minute"], 1), 2)
    evidence = [{"id": r["id"], "timestamp": r["timestamp"], "source": "metrics",
                 "excerpt": (f"p95 {r['latency_p95_ms']}ms; errors {r['error_rate_pct']}%; "
                             f"requests/min {r['requests_per_minute']}"), "service": r["service"]}
                for r in {row["id"]: row for row in
                          (baseline, peak, volume_peak, anomaly_point) if row is not None}.values()]
    anomalies = []
    if latency_ratio >= 2:
        anomalies.append("p95 latency doubled or more")
    if error_delta >= 5:
        anomalies.append("error rate increased by at least 5 percentage points")
    if volume_ratio >= 2:
        anomalies.append("request volume doubled or more")
    return {"agent": "metrics", "summary": f"Peak p95 is {latency_ratio}x baseline; "
            f"error rate changed by {error_delta} percentage points; request volume is "
            f"{volume_ratio}x baseline.", "baseline": baseline, "peak": peak,
            "latency_ratio": latency_ratio, "error_delta_pct_points": error_delta,
            "request_volume_ratio": volume_ratio, "anomalies": anomalies, "evidence": evidence}


def deployment_findings(s: dict[str, Any]) -> dict[str, Any]:
    start = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
    window_start = start - timedelta(hours=2)
    recent = []
    for row in s["deployments"]:
        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        if window_start <= timestamp <= start + timedelta(minutes=10):
            recent.append(row)
    evidence = [{"id": r["id"], "timestamp": r["timestamp"], "source": "deployments",
                 "excerpt": f"{r['version']}: {r['summary']}", "service": r["service"]}
                for r in (recent or s["deployments"][:1])]
    return {"agent": "deployments", "summary": (f"{len(recent)} deployment(s) in the two-hour "
            "pre-incident window." if recent else "No deployment found in the two-hour "
            "pre-incident window."), "recent_deployments": recent, "evidence": evidence}


def investigate_hypotheses(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Investigator stage: rank causes from evidence without reading expected labels."""
    by_name = {r["agent"]: r for r in results}
    metrics = by_name["metrics"]
    logs = by_name["logs"]
    deploy = by_name["deployments"]
    # Explicit, explainable rules rank candidate causes. The expected label is not read here.
    candidates = {"deployment_regression": 0.1,
                  "external_dependency_degradation": 0.1,
                  "traffic_capacity_saturation": 0.1,
                  "unknown": 0.1}
    recent_deployments = deploy.get("recent_deployments", [])
    messages = " ".join(g["signature"].lower() for g in logs.get("error_groups", []))
    if recent_deployments:
        candidates["deployment_regression"] += 0.5
    if any(term in messages for term in ("provider", "gateway timeout", "circuit breaker")):
        candidates["external_dependency_degradation"] += 0.7
    if metrics.get("request_volume_ratio", 1) >= 2:
        candidates["traffic_capacity_saturation"] += 0.75
    if (metrics.get("error_delta_pct_points", 0) >= 5
            and metrics.get("request_volume_ratio", 1) < 2 and recent_deployments):
        candidates["deployment_regression"] += 0.3
    ordered = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    total = sum(score for _, score in ordered)
    hypotheses = [{"cause": cause, "confidence": round(score / total, 2),
                   "reason": _reason(cause, deploy, metrics, messages)}
                  for cause, score in ordered]
    evidence = [ev for result in results for ev in result.get("evidence", [])]
    evidence = list({ev["id"]: ev for ev in evidence}.values())
    return {"agent": "investigator", "summary": f"Ranked {len(hypotheses)} candidate causes "
            "using explicit evidence rules.", "hypotheses": hypotheses, "evidence": evidence}


def report_incident(s: dict[str, Any], results: list[dict[str, Any]],
                    investigator: dict[str, Any]) -> dict[str, Any]:
    """Reporter stage: turn specialist and investigator output into a cited report."""
    hypotheses = investigator["hypotheses"]
    evidence = investigator["evidence"]
    reporter = {"agent": "reporter", "summary": "Assembled a chronological report, cited "
                "evidence, confidence, and human follow-up checks.", "evidence": evidence}
    primary = hypotheses[0]
    return {"scenario_id": s["id"], "service": s["service"], "incident_start": s["start_time"],
            "status": "completed", "mode": "deterministic", "root_cause": primary["cause"],
            "confidence": primary["confidence"], "summary": f"Most supported hypothesis: "
            f"{primary['cause'].replace('_', ' ')}. {primary['reason']}",
            "hypotheses": hypotheses, "timeline": sorted(evidence, key=lambda ev: ev["timestamp"]),
            "evidence": evidence, "agent_results": [*results, investigator, reporter],
            "recommendations": ["Compare the cited error traces with the affected request path.",
                "Check the owning service dashboard and deployment diff before taking action.",
                "Confirm this hypothesis with an on-call engineer; no remediation was executed."],
            "safety": "Read-only synthetic investigation. No production systems were accessed or changed."}


def investigate(scenario_id: str, agent_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    s = get_scenario(scenario_id)
    results = agent_results or [log_findings(s), metric_findings(s), deployment_findings(s)]
    investigator = investigate_hypotheses(results)
    return report_incident(s, results, investigator)


def _reason(cause: str, deploy: dict[str, Any], metrics: dict[str, Any], messages: str) -> str:
    if cause == "deployment_regression":
        return "A deployment is close to incident start and error metrics rose while request volume stayed similar."
    if cause == "external_dependency_degradation":
        return "Logs contain provider timeout or circuit-breaker evidence."
    if cause == "traffic_capacity_saturation":
        return "Request volume rose sharply alongside latency and errors."
    return "The available synthetic signals do not strongly support another candidate."
