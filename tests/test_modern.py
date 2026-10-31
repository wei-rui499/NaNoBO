"""Real BO-MCP checks, run inside .venv-modern with PYTHONPATH=src."""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from chembo.modern_worker import main, recommend_modern


def project():
    return {
        "name": "BO-MCP contract", "engine": "bo-mcp", "seed": 42, "batch_size": 2,
        "parameters": [{"name": "temperature", "type": "continuous", "low": 0, "high": 1}],
        "objectives": [{"name": "loss", "goal": "min", "tolerance": 0.2}],
        "observations": [], "pending": [],
    }


class ModernTests(unittest.TestCase):
    def test_initial_resume_with_pending(self):
        p = project()
        first = recommend_modern(p)
        p["backend_state"] = first["backend_state"]
        p["pending"] = first["recommendations"]
        second = recommend_modern(p)
        self.assertEqual(2, len(second["recommendations"]))
        self.assertEqual(4, len(second["backend_state"]["initial_history"]))
        self.assertTrue(all(r not in p["pending"] for r in second["recommendations"]))
        json.dumps(second, allow_nan=False)

    def test_real_model_and_pending(self):
        p = project()
        p["batch_size"] = 1
        p["observations"] = [{"temperature": x, "loss": (x - 0.35)**2}
                             for x in [0.0, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0]]
        p["pending"] = [{"temperature": 0.4}]
        result = recommend_modern(p)
        self.assertEqual("bo", result["provenance"]["suggestions"][0]["generation_method"])
        self.assertNotEqual(0.4, result["recommendations"][0]["temperature"])
        self.assertTrue(0 <= result["recommendations"][0]["temperature"] <= 1)
        json.dumps(result, allow_nan=False)

    def test_mixed_domain_initial(self):
        p = project()
        p["parameters"] += [
            {"name": "count", "type": "discrete", "low": 1, "high": 4},
            {"name": "solvent", "type": "categorical", "options": ["water", "ethanol"]},
        ]
        result = recommend_modern(p)
        for row in result["recommendations"]:
            self.assertIn(row["count"], [1, 2, 3, 4])
            self.assertIn(row["solvent"], ["water", "ethanol"])

    def test_mixed_model_and_changed_state(self):
        p = project()
        p["batch_size"] = 1
        p["parameters"] += [
            {"name": "count", "type": "discrete", "low": 1, "high": 2},
            {"name": "solvent", "type": "categorical", "options": ["water", "ethanol"]},
        ]
        p["observations"] = [
            {"temperature": x, "count": n, "solvent": solvent,
             "loss": (x - 0.35)**2 + n*0.05 + (solvent == "water")*0.1}
            for x in [0.1, 0.8] for n in [1, 2] for solvent in ["water", "ethanol"]
        ]
        p["pending"] = [{"temperature": 0.4, "count": 1, "solvent": "ethanol"}]
        result = recommend_modern(p)
        self.assertEqual("bo", result["provenance"]["suggestions"][0]["generation_method"])
        self.assertIn(result["recommendations"][0]["count"], [1, 2])
        p["backend_state"] = result["backend_state"]
        p["seed"] += 1
        with self.assertRaisesRegex(ValueError, "状态不匹配"):
            recommend_modern(p)

    @unittest.skipUnless(os.environ.get("CHEMBO_MODERN_WORKER"), "Set CHEMBO_MODERN_WORKER to test the native binary")
    def test_frozen_worker_without_python_on_path(self):
        worker = str(Path(os.environ["CHEMBO_MODERN_WORKER"]).resolve())
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        env["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32") if os.name == "nt" else "/usr/bin:/bin"
        p = project()
        with tempfile.TemporaryDirectory() as folder:
            request, result = Path(folder)/"request.json", Path(folder)/"result.json"
            for stage in ("initial", "pending", "model"):
                if stage == "pending":
                    p["pending"] = payload["recommendations"]
                    p["backend_state"] = payload["backend_state"]
                elif stage == "model":
                    p["observations"] = [{"temperature": x, "loss": (x - 0.35)**2}
                                         for x in [0.0, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0]]
                    p["batch_size"] = 1
                request.write_text(json.dumps(p))
                result.unlink(missing_ok=True)
                started = time.monotonic()
                done = subprocess.run([worker, str(request), str(result)], env=env,
                                      capture_output=True, text=True, timeout=180)
                print(f"frozen {stage}: {time.monotonic() - started:.2f}s", flush=True)
                self.assertTrue(result.exists(), done.stderr[-5000:])
                payload = json.loads(result.read_text())
                self.assertEqual(0, done.returncode, payload)
                self.assertTrue(payload["ok"], payload)
                self.assertEqual(p["batch_size"], len(payload["recommendations"]))
                self.assertTrue(all(row not in p["pending"] for row in payload["recommendations"]))
                if stage == "model":
                    self.assertEqual("bo", payload["provenance"]["suggestions"][0]["generation_method"])

    def test_invalid_observation_cli_error(self):
        p = project()
        p["observations"] = [{"temperature": 3, "loss": 2}]
        with tempfile.TemporaryDirectory() as folder:
            request, result = Path(folder)/"request.json", Path(folder)/"result.json"
            request.write_text(json.dumps(p))
            self.assertEqual(1, main([str(request), str(result)]))
            self.assertFalse(json.loads(result.read_text())["ok"])


if __name__ == "__main__":
    unittest.main()
