"""A2A agents: specialist agents return structured JSON as text artifacts."""
from __future__ import annotations

import json
import os
from typing import Any

from a2a.helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Part
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

from app.data import get_scenario
from app.investigation import deployment_findings, log_findings, metric_findings

AGENTS: dict[str, tuple[str, str]] = {
    "logs": ("Log Analyst", "Searches synthetic application logs and groups error signatures."),
    "metrics": ("Metrics Analyst", "Compares synthetic service metrics around incident start."),
    "deployments": ("Deployment Analyst", "Checks synthetic deployments near incident start."),
}


class SpecialistExecutor(AgentExecutor):
    def __init__(self, name: str):
        self.name = name

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        text = " ".join(part.text for part in context.message.parts if getattr(part, "text", None))
        try:
            scenario = get_scenario(text.strip())
            result = {"logs": log_findings, "metrics": metric_findings,
                      "deployments": deployment_findings}[self.name](scenario)
            response = json.dumps(result, ensure_ascii=False)
            updater = TaskUpdater(event_queue, task.id, task.context_id)
            await updater.add_artifact(parts=[Part(text=response)], name=f"{self.name}-findings")
            await updater.complete()
        except (KeyError, ValueError) as exc:
            updater = TaskUpdater(event_queue, task.id, task.context_id)
            await updater.failed()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def build_a2a_routes() -> list[Any]:
    public_base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    routes: list[Any] = []
    for key, (name, description) in AGENTS.items():
        path = f"/a2a/{key}"
        card = AgentCard(name=name, description=description,
            supported_interfaces=[AgentInterface(url=f"{public_base}{path}",
                protocol_binding="JSONRPC", protocol_version="1.0")], version="0.1.0",
            capabilities=AgentCapabilities(streaming=False),
            default_input_modes=["text/plain"], default_output_modes=["text/plain"],
            skills=[AgentSkill(id=key, name=name, description=description,
                               tags=["incident-response", key])])
        handler = DefaultRequestHandler(agent_executor=SpecialistExecutor(key),
                                        task_store=InMemoryTaskStore(), agent_card=card)
        routes.extend(create_agent_card_routes(card,
            card_url=f"{path}{AGENT_CARD_WELL_KNOWN_PATH}"))
        routes.extend(create_jsonrpc_routes(handler, rpc_url=path))
    return routes
