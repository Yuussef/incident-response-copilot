from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents import build_a2a_routes
from app.data import get_scenario, scenarios
from app.orchestrator import run_coordinated_investigation

app = FastAPI(title="Incident Response Copilot", version="0.1.0",
              description="Synthetic, evidence-grounded incident investigations. Read-only demo.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.router.routes.extend(build_a2a_routes())


class InvestigationRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    use_llm: bool = False


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "incident-response-copilot", "mode": "synthetic-read-only"}


@app.get("/api/scenarios")
def list_scenarios():
    return [{k: s[k] for k in ("id", "title", "description", "service", "start_time")}
            for s in scenarios()]


@app.get("/api/scenarios/{scenario_id}")
def scenario_detail(scenario_id: str):
    try:
        return {k: v for k, v in get_scenario(scenario_id).items() if k != "expected_cause"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown scenario") from exc


@app.post("/api/investigations")
async def start_investigation(request: InvestigationRequest):
    try:
        get_scenario(request.scenario_id)
        report = await run_coordinated_investigation(request.scenario_id)
        if request.use_llm:
            report["llm_explanation"] = await optional_explanation(report)
        return report
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown scenario") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent investigation failed: {exc}") from exc


async def optional_explanation(report: dict) -> dict:
    """Optional paraphrase only. It never changes the deterministic findings."""
    import os
    if not os.getenv("OPENAI_API_KEY"):
        return {"available": False, "text": "No OPENAI_API_KEY configured; deterministic report shown."}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        response = await client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=[{"role":"system","content":"Explain the supplied incident report for an on-call engineer. "
                    "Use only the report facts and cited evidence. Clearly label the root cause as a hypothesis. "
                    "Do not invent evidence or recommend executing changes."},
                   {"role":"user","content":str({"summary":report["summary"],
                    "hypotheses":report["hypotheses"],"evidence":report["evidence"]})}])
        return {"available": True, "text": response.output_text}
    except Exception:
        return {"available": False, "text": "LLM unavailable; deterministic report shown."}


# In production, serve the Vite build from the same origin as the API. During
# local development Vite runs separately, so this mount is omitted when absent.
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
