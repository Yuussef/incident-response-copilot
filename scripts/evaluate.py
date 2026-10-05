"""Run the deterministic evaluation set and print auditable metrics."""
import json
from pathlib import Path

from app.data import get_scenario
from app.investigation import investigate

eval_path = Path(__file__).resolve().parents[1] / "data" / "evaluations" / "cases.json"
cases = json.loads(eval_path.read_text(encoding="utf-8"))
correct = required_evidence = grounded = chronologies = 0
for case in cases:
    report = investigate(case["scenario_id"])
    source_ids = {row["id"] for row in (get_scenario(case["scenario_id"])["logs"]
        + get_scenario(case["scenario_id"])["metrics"]
        + get_scenario(case["scenario_id"])["deployments"])}
    report_ids = {row["id"] for row in report["evidence"]}
    correct += report["root_cause"] == case["expected_cause"]
    required_evidence += set(case["required_evidence_ids"]) <= report_ids
    grounded += report_ids <= source_ids
    chronologies += report["timeline"] == sorted(report["timeline"], key=lambda x: x["timestamp"])
    print(f"{case['scenario_id']}: expected={case['expected_cause']} predicted={report['root_cause']} "
          f"confidence={report['confidence']:.0%} cited={len(report_ids)} "
          f"required evidence covered={set(case['required_evidence_ids']) <= report_ids}")
print(f"\nCause accuracy: {correct}/{len(cases)} ({correct / len(cases):.0%})")
print(f"Required evidence coverage: {required_evidence}/{len(cases)} "
      f"({required_evidence / len(cases):.0%})")
print(f"Evidence provenance valid: {grounded}/{len(cases)} ({grounded / len(cases):.0%})")
print(f"Chronology valid: {chronologies}/{len(cases)} ({chronologies / len(cases):.0%})")
