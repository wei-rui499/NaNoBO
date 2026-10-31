"""Exercise bundled engines without using the developer environment.

Run with any Python after native packaging, or against a silent-installed app:
    python scripts/smoke_frozen.py --bundle "dist/NaNoBO"
    python scripts/smoke_frozen.py --bundle "dist/NaNoBO.app"
"""
import argparse
import json
import os
import math
import subprocess
import sys
import tempfile
from pathlib import Path


def smoke(bundle):
    bundle = bundle.resolve()
    windows = sys.platform == "win32"
    if bundle.suffix == ".app":
        executable = bundle / "Contents" / "MacOS" / "NaNoBO"
    else:
        executable = bundle / ("NaNoBO.exe" if windows else "NaNoBO")
    if not executable.is_file():
        raise RuntimeError(f"Main application is missing: {executable}")
    modern_name = "chembo-modern-worker.exe" if windows else "chembo-modern-worker"
    candidates = sorted(bundle.rglob(modern_name))
    if not candidates:
        raise RuntimeError(f"Modern engine is missing from {bundle}")
    modern = candidates[0]
    environment = os.environ.copy()
    # This check must load the frozen bundle, never the source tree or dev Python.
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX"):
        environment.pop(key, None)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="chembo-smoke-") as directory:
        folder = Path(directory)
        for engine in ("gryffin", "atlas", "bo-mcp"):
            project = {
                "name": "Frozen bundle synthetic smoke test",
                "engine": engine, "seed": 24, "batch_size": 1,
                "parameters": [{"name": "x", "type": "continuous", "low": 0.0, "high": 1.0}],
                "objectives": [{"name": "response", "goal": "max", "tolerance": 0.2}],
                "observations": [{"x": x, "response": 1.0 - (x - 0.6) ** 2} for x in (0.0, 0.15, 0.35, 0.75, 1.0)],
                "pending": [{"x": 0.5}],
            }
            request = folder / f"{engine}-request.json"
            result = folder / f"{engine}-result.json"
            request.write_text(json.dumps(project, allow_nan=False), encoding="utf-8")
            command = ([str(modern)] if engine == "bo-mcp" else [str(executable), "--worker"])
            completed = subprocess.run(
                [*command, str(request), str(result)], cwd=folder, env=environment,
                capture_output=True, text=True, errors="replace", timeout=300,
            )
            if completed.returncode or not result.exists():
                raise RuntimeError(f"{engine} frozen process failed ({completed.returncode})\n{completed.stdout[-6000:]}\n{completed.stderr[-6000:]}")
            payload = json.loads(result.read_text(encoding="utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(f"{engine}: {payload.get('error')}")
            rows = payload["recommendations"]
            if len(rows) != 1 or set(rows[0]) != {"x"}:
                raise RuntimeError(f"{engine} returned an invalid batch: {rows}")
            x = rows[0]["x"]
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not 0 <= x <= 1:
                raise RuntimeError(f"{engine} returned an invalid value: {x!r}")
            if any(abs(x - row["x"]) <= 1e-6 for row in project["observations"] + project["pending"]):
                raise RuntimeError(f"{engine} returned an observed/pending point: {x}")
            print(f"PASS frozen {engine}: x={x:.8g}", flush=True)
        # Exercise the mixed-space modules that the continuous smoke never imports.
        for engine in ("gryffin", "atlas", "bo-mcp"):
            project = {
                "name": "Mixed-space frozen synthetic test", "engine": engine, "seed": 42, "batch_size": 2,
                "parameters": [{"name": "x", "type": "continuous", "low": 0, "high": 1},
                               {"name": "n", "type": "discrete", "low": 1, "high": 4},
                               {"name": "solvent", "type": "categorical", "options": ["类别 A", "类别 B", "类别 C"]}],
                "objectives": [{"name": "response", "goal": "max", "tolerance": 0.2}],
                "observations": [{"x": x, "n": n, "solvent": c, "response": y} for x, n, c, y in
                                 [(0.1, 1, "类别 A", 0.2), (0.4, 2, "类别 B", 0.8), (0.8, 3, "类别 C", 0.4), (0.65, 2, "类别 B", 0.95), (0.3, 4, "类别 A", 0.5)]],
                "pending": [{"x": 0.55, "n": 2, "solvent": "类别 B"}],
            }
            if engine == "gryffin":
                project["objectives"].append({"name": "cost", "goal": "min", "tolerance": 0.2})
                for index, observation in enumerate(project["observations"]):
                    observation["cost"] = float(index + 1)
            request, result = folder / f"{engine}-mixed-request.json", folder / f"{engine}-mixed-result.json"
            request.write_text(json.dumps(project, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            command = [str(modern)] if engine == "bo-mcp" else [str(executable), "--worker"]
            completed = subprocess.run([*command, str(request), str(result)], cwd=folder, env=environment,
                                       capture_output=True, text=True, errors="replace", timeout=300)
            if completed.returncode or not result.exists():
                raise RuntimeError(f"{engine} mixed frozen process failed\n{completed.stdout[-6000:]}\n{completed.stderr[-6000:]}")
            payload = json.loads(result.read_text(encoding="utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(f"{engine} mixed: {payload.get('error')}")
            rows = payload["recommendations"]
            if len(rows) != 2:
                raise RuntimeError(f"{engine} mixed returned the wrong batch size")
            blocked = project["observations"] + project["pending"]
            for row in rows:
                if set(row) != {"x", "n", "solvent"} or not math.isfinite(row["x"]) or not 0 <= row["x"] <= 1 or row["n"] not in (1, 2, 3, 4) or row["solvent"] not in ("类别 A", "类别 B", "类别 C"):
                    raise RuntimeError(f"{engine} mixed returned invalid parameters: {row}")
                if any(abs(row["x"] - other["x"]) <= 1e-6 and row["n"] == other["n"] and row["solvent"] == other["solvent"] for other in blocked):
                    raise RuntimeError(f"{engine} mixed returned a duplicate")
                blocked.append(row)
            print(f"PASS frozen {engine}: mixed parameters, batch 2" + (", Chimera multiobjective" if engine == "gryffin" else ""), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    smoke(parser.parse_args().bundle)
