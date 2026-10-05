"""Read-only access to bundled synthetic incident fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "scenarios.json"


def scenarios() -> list[dict[str, Any]]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def get_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    raise KeyError(scenario_id)
