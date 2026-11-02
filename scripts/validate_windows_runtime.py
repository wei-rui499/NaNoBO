"""Independent acceptance against the unmodified, installed Windows executables.

The Python running this file only writes synthetic fixtures and checks JSON.
It never imports or supplies model dependencies to the application.
"""
import argparse
import copy
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "validation" / "windows-runtime"
sys.path.insert(0, str(ROOT / "src"))
from chembo.engine import validate_project, _same
from chembo.space import feasible

for stream in (sys.stdout, sys.stderr):
    if callable(getattr(stream, "reconfigure", None)):
        stream.reconfigure(encoding="utf-8", errors="replace")

parser = argparse.ArgumentParser()
parser.add_argument("--bundle", type=Path, required=True)
parser.add_argument("--output", type=Path, default=HERE)
parser.add_argument("--fail-fast", action="store_true")
parser.add_argument("--engine-first", choices=["gryffin", "atlas", "bo-mcp"], default="gryffin")
args = parser.parse_args()
HERE = args.output.resolve()
HERE.mkdir(parents=True, exist_ok=True)
bundle = args.bundle.resolve()
exe = bundle / "NaNoBO.exe"
modern = bundle / "_internal/engines/modern/chembo-modern-worker.exe"
environment = os.environ.copy()
for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING", "VIRTUAL_ENV", "CONDA_PREFIX"):
    environment.pop(key, None)
# Remove installed development interpreters/tools from PATH for every calculation.
environment["PATH"] = os.pathsep.join([str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]])
environment["QT_QPA_PLATFORM"] = "offscreen"
checks = []

def run_case(name, project, expected_ok=True, extra=None):
    directory = HERE / "cases" / name
    directory.mkdir(parents=True, exist_ok=True)
    request, result = directory / "request.json", directory / "result.json"
    request.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    command = [str(modern)] if project.get("engine") == "bo-mcp" else [str(exe), "--worker"]
    started = time.monotonic()
    record = {"name": name, "engine": project.get("engine"), "expected_ok": expected_ok}
    payload = None
    try:
        proc = subprocess.run(command + [str(request), str(result)], cwd=directory,
                              env=environment, capture_output=True, timeout=180)
        (directory / "stdout.txt").write_bytes(proc.stdout)
        (directory / "stderr.txt").write_bytes(proc.stderr)
        record["exit_code"] = proc.returncode
        assert result.exists(), "Executable produced no result file"
        payload = json.loads(result.read_text(encoding="utf-8-sig"))
        assert payload.get("ok") is expected_ok, payload.get("error", "Unexpected success")
        if expected_ok:
            assert proc.returncode == 0, proc.returncode
            assert b"ModuleNotFoundError" not in proc.stderr, "Successful model still requests a missing component"
            p = validate_project(project)
            rows = payload["recommendations"]
            expected_count = 0 if p.get("_operation") == "analyze" else p["batch_size"]
            assert len(rows) == expected_count, (len(rows), expected_count)
            blocked = p["observations"] + p["pending"]
            for row in rows:
                assert set(row) == {x["name"] for x in p["parameters"]}
                assert feasible(row, p), row
                assert not any(_same(row, b, p["parameters"]) for b in blocked), row
                if p.get("candidates"):
                    assert row in p["candidates"], row
                blocked.append(row)
            validate_project({**p, "pending": p["pending"] + rows})
            analysis = payload.get("analysis", {})
            for prediction in analysis.get("predictions", []):
                assert not any(_same(prediction["parameters"], b, p["parameters"])
                               for b in p["observations"] + p["pending"])
                for value in prediction.get("std", {}).values():
                    assert math.isfinite(value) and value >= 0
                if prediction.get("probabilities"):
                    probs = prediction["probabilities"]
                    assert set(probs) <= set(p["classification"]["labels"])
                    assert all(0 <= v <= 1 for v in probs.values())
                    assert abs(sum(probs.values()) - 1) < 1e-7
            if extra:
                extra(payload)
            record.update(model=analysis.get("model"), status=analysis.get("status"),
                          recommendations=len(rows), predictions=len(analysis.get("predictions", [])),
                          loo=analysis.get("diagnostics", {}).get("evaluated"),
                          provenance=payload.get("provenance"))
        else:
            assert payload.get("error"), "Missing actionable error"
            record["expected_error"] = payload["error"]
        record["passed"] = True
    except Exception as exc:
        record.update(passed=False, error=str(exc))
    record["seconds"] = round(time.monotonic() - started, 2)
    checks.append(record)
    (HERE / "acceptance-results.json").write_text(json.dumps({"bundle":str(bundle), "checks":checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)
    if args.fail_fast and not record["passed"]:
        raise SystemExit(1)
    return payload if record["passed"] else None

def base(engine="bo-mcp"):
    return dict(name="SYNTHETIC Windows acceptance",engine=engine,seed=42,batch_size=2,
                parameters=[dict(name="x",type="continuous",low=0,high=1)],
                objectives=[dict(name="response",goal="max",tolerance=.2)],
                observations=[dict(x=x,response=1-(x-.63)**2) for x in [0,.15,.35,.75,1]],
                pending=[dict(x=.5)], _modeling_v2=True)

# Every real native engine: trained, cold start, and mixed categorical/integer batch.
for engine in [args.engine_first] + [name for name in ["gryffin", "atlas", "bo-mcp"] if name != args.engine_first]:
    p = base(engine)
    run_case(engine + "-trained-continuous", p)
    p = base(engine); p.update(observations=[], pending=[])
    run_case(engine + "-cold-start", p)
    p = base(engine)
    p["parameters"] += [dict(name="n",type="discrete",low=1,high=4),
                         dict(name="类别",type="categorical",options=["甲","乙","丙"])]
    for i,row in enumerate(p["observations"]): row.update(n=1+i%4,类别=["甲","乙","丙"][i%3])
    p["pending"] = [dict(x=.5,n=2,类别="乙")]
    run_case(engine + "-mixed-chinese-path", p)

# Native boundary paths: single requests, finite pools and maximum batch.
for engine in ["gryffin", "atlas"]:
    p=base(engine);p.update(batch_size=1);p["objectives"][0]["goal"]="min"
    run_case(engine+"-single-continuous-min",p)
    p=base(engine);p.update(batch_size=2,parameters=[dict(name="solvent",type="categorical",options=["甲","乙","丙"])],observations=[],pending=[dict(solvent="丙")])
    run_case(engine+"-finite-cold-exhaust-pool",p)
    p=base(engine);p.update(batch_size=2,parameters=[dict(name="n",type="discrete",low=1,high=8)],observations=[dict(n=n,response=n/8) for n in range(1,6)],pending=[dict(n=8)])
    run_case(engine+"-finite-trained-last-two",p)
    p=base(engine);p.update(batch_size=24,observations=[],pending=[])
    run_case(engine+"-cold-maximum-batch24",p)
p=base("atlas");p.update(batch_size=1,parameters=[dict(name="n",type="discrete",low=1,high=8)],observations=[dict(n=n,response=n/8) for n in range(1,6)],pending=[dict(n=8)])
run_case("atlas-finite-trained-single",p)

# Four released tutorials: recommend -> synthetic measured refill -> genuine LOO.
manifest = json.loads((ROOT / "examples/tutorial/MANIFEST.json").read_text(encoding="utf-8"))
for item in manifest["exercises"]:
    folder = ROOT / "examples/tutorial" / item["folder"]
    p = json.loads((folder / "project.chembo.json").read_text(encoding="utf-8"))
    p.update(_modeling_v2=True)
    first = run_case(item["folder"] + "-recommend", p)
    if first:
        with (folder / "all-simulated-results.csv").open(encoding="utf-8-sig", newline="") as stream:
            all_rows = list(csv.DictReader(stream))
        p["pending"] = first["recommendations"]
        run_case(item["folder"] + "-pending-exclusion", {**p,"_operation":"analyze"})
        for pending in p["pending"]:
            found = next(row for row in all_rows if all(
                row[d["name"]] == str(pending[d["name"]]) if d["type"]=="categorical" else
                abs(float(row[d["name"]])-pending[d["name"]])<1e-7 for d in p["parameters"]))
            p["observations"].append({**pending, **{o["name"]:found[o["name"]] if p.get("task")=="classification" else float(found[o["name"]]) for o in p["objectives"]}})
        p.update(pending=[],_operation="analyze",_diagnostics=True)
        def check_loo(payload):
            assert payload["analysis"]["diagnostics"]["evaluated"] == 8
            assert payload["analysis"]["status"] == "trained"
        run_case(item["folder"] + "-refill-loo", p, extra=check_loo)
        (HERE / (item["folder"] + "-completed.chembo.json")).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")

# Gryffin's supported native prioritized multiobjective workflow.
p=base("gryffin");p["objectives"].append(dict(name="cost",goal="min",tolerance=.2))
for i,row in enumerate(p["observations"]):row["cost"] = i+1
run_case("gryffin-chimera",p)

p=base();p["objectives"][0]["goal"]="min"
run_case("botorch-minimization",p)
p=base();p["parameters"]=[dict(name="A",type="continuous",low=.1,high=.9),dict(name="B",type="continuous",low=.1,high=.9)]
p["constraints"]=[dict(kind="linear",coefficients={"A":1,"B":1},relation="eq",rhs=1),
                   dict(kind="ratio",numerator="A",denominator="B",low=.2,high=3)]
p["observations"]=[dict(A=x,B=1-x,response=1-(x-.6)**2) for x in [.2,.3,.4,.7]];p["pending"]=[]
run_case("continuous-equality-and-ratio",p)
p=base();p["parameters"][0]["step"]=.05;p.update(objective_mode="pareto",pending=[])
p["objectives"] += [dict(name="cost",goal="min"),dict(name="selectivity",goal="max")]
for row in p["observations"]:row.update(cost=1+row["x"],selectivity=2-row["x"]**2)
run_case("pareto-three-objectives",p)
for observed_classes in [1,2]:
    p=base();p["parameters"][0]["step"]=.05;p.update(task="classification",classification={"labels":["失败","成功","其他"]},pending=[])
    for i,row in enumerate(p["observations"]):row["response"]=["失败","成功"][i%observed_classes]
    run_case("classification-"+str(observed_classes)+"-seen-classes",p)

# A small deterministic finite domain checks actual regression response sensitivity.
p=base();p["parameters"][0]["step"] = .05;p["pending"]=[]
a=run_case("fixed-gp-positive",p)
b=run_case("fixed-gp-reproducible",p)
q=copy.deepcopy(p)
for row in q["observations"]:row["response"] *= -1
c=run_case("fixed-gp-changed-measurements",q)
if a and b and c:
    checks.append(dict(name="model-reproducibility-and-data-sensitivity",passed=
        a["recommendations"]==b["recommendations"] and a["analysis"]["predictions"]==b["analysis"]["predictions"]
        and a["analysis"]["predictions"]!=c["analysis"]["predictions"]))

# Native validation must reject unsupported workflows and bad inputs, no fallback.
for name,change in [
    ("invalid-batch",dict(batch_size=25)),
    ("invalid-engine",dict(engine="fake-model")),
    ("duplicate-pending",dict(pending=[dict(x=.15)])),
    ("missing-result",dict(observations=[dict(x=.2)])),
    ("nonfinite-result",dict(observations=[dict(x=.2,response="NaN")])),
    ("exhausted-candidates",dict(candidates=[dict(x=0),dict(x=1)],pending=[])),
    ("atlas-rejects-steps",dict(engine="atlas",parameters=[dict(name="x",type="continuous",low=0,high=1,step=.05)])),
    ("gryffin-rejects-steps",dict(engine="gryffin",parameters=[dict(name="x",type="continuous",low=0,high=1,step=.05)])),
]:
    p=base();p.update(change);run_case(name,p,expected_ok=False)

summary={"bundle":str(bundle),"passed":sum(x["passed"] for x in checks),"total":len(checks),"checks":checks}
(HERE / "acceptance-results.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print("FINAL",summary["passed"],"/",summary["total"],flush=True)
raise SystemExit(0 if summary["passed"] == summary["total"] else 1)
