"""A2A coordinator delegates to specialist A2A endpoints over JSON-RPC."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

from app.investigation import investigate


async def _call_agent(client: httpx.AsyncClient, base: str, name: str,
                      scenario_id: str) -> dict[str, Any]:
    request = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage",
        "params": {"message": {"messageId": str(uuid.uuid4()), "role": "ROLE_USER",
            "parts": [{"text": scenario_id}]}}}
    response = await client.post(f"{base}/a2a/{name}", json=request,
                                 headers={"A2A-Version": "1.0"}, timeout=10)
    response.raise_for_status()
    payload = response.json().get("result", {})
    task_or_message = payload.get("task", payload)
    artifacts = task_or_message.get("artifacts", [])
    for artifact in artifacts:
        for part in artifact.get("parts", []):
            text = part.get("text")
            if text:
                return json.loads(text)
    # Protocol implementations may also return a direct message.
    for part in payload.get("parts", []):
        if part.get("text"):
            return json.loads(part["text"])
    raise ValueError(f"A2A agent {name} returned no JSON findings")


async def run_coordinated_investigation(scenario_id: str) -> dict[str, Any]:
    # Call the agents through this container's listener. PUBLIC_BASE_URL is for
    # externally advertised A2A Agent Cards, not internal service-to-self calls.
    port = os.getenv("PORT", "8000")
    base = os.getenv("A2A_INTERNAL_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    async with httpx.AsyncClient() as client:
        results = await __import__("asyncio").gather(*[
            _call_agent(client, base, agent, scenario_id)
            for agent in ("logs", "metrics", "deployments")])
    report = investigate(scenario_id, results)
    report["mode"] = "A2A + deterministic rules"
    return report
