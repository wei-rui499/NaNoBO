"""Optional publisher check: run the synthetic tutorial through the actual models.

Run with the modern Python environment and PYTHONPATH=src. This is a macOS/source
check; Windows runtime validation is intentionally left to the user for 0.2.3.
"""
import copy
import json
from pathlib import Path

from chembo import __version__
from chembo.engine import read_observations, validate_project
from chembo.modeling import plan
from chembo.space import feasible

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "validation" / f"tutorial-{__version__}"
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "examples/tutorial/manifest.json").read_text(encoding="utf-8"))
    checks = []
    for exercise in manifest["exercises"]:
        folder = ROOT / "examples/tutorial" / exercise["folder"]
        original = validate_project(json.loads((folder / "project.chembo.json").read_text(encoding="utf-8")))
        parameters = original["parameters"]
        key = lambda row: tuple(row[p["name"]] for p in parameters)
        oracle = {key(row): row for row in read_observations(original, folder / "all-simulated-results.csv")}
        first = plan(original)
        assert first["ok"] and len(first["recommendations"]) == 2
        assert len(first["analysis"]["predictions"]) == exercise["predictions_before_recommend"]
        assert all(feasible(row, original) and row in original["candidates"] and key(row) not in {key(r) for r in original["observations"]} for row in first["recommendations"])
        queued = copy.deepcopy(original)
        queued["pending"] = first["recommendations"]
        queued["_operation"] = "analyze"
        after_queue = plan(queued)
        assert not after_queue["recommendations"]
        assert len(after_queue["analysis"]["predictions"]) == exercise["predictions_after_two_pending"]
        completed = copy.deepcopy(original)
        completed["observations"] += [oracle[key(row)] for row in first["recommendations"]]
        completed["_operation"] = "analyze"
        analyzed = plan(completed)
        diagnostics = analyzed["analysis"]["diagnostics"]
        assert len(completed["observations"]) == 8 and not completed["pending"]
        assert diagnostics["status"] == "computed" and diagnostics["evaluated"] == 8
        payload = {"project": completed, "analysis": analyzed["analysis"]}
        (output / (exercise["folder"] + ".json")).write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
        checks.append({"exercise": exercise["folder"], "model": analyzed["analysis"]["model"], "recommended": 2, "completed_after_simulated_refill": 8, "loo_evaluated": 8, "candidate_rows_before_recommendation": len(first["analysis"]["predictions"]), "candidate_rows_after_queue": len(after_queue["analysis"]["predictions"]), "passed": True})
        print(exercise["folder"] + ": actual model, pending exclusion and 8-row LOO passed", flush=True)
    report = {"version": __version__, "data_status": "SYNTHETIC", "scope": "macOS source model checks; not Windows runtime or wet-lab validation", "exercises": checks}
    (output / "SUMMARY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
