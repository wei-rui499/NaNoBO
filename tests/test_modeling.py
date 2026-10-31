"""The installed native BoTorch/GPC models, not stand-in model tests."""
import copy
import json
import math
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from chembo.modeling import _acquisition, _fit_gp, _pareto, _scores, plan
from chembo.modern_worker import main, recommend_modern
from chembo.space import feasible


def project():
    return {
        "name": "NaNoBO native models", "engine": "bo-mcp", "seed": 42, "batch_size": 2,
        "parameters": [{"name": "x", "type": "continuous", "low": 0, "high": 1, "step": 0.05}],
        "objectives": [{"name": "loss", "goal": "min", "tolerance": 0.2}],
        "observations": [], "pending": [], "_modeling_v2": True,
    }


class ModelingTests(unittest.TestCase):
    def assert_json(self, payload):
        json.dumps(payload, ensure_ascii=False, allow_nan=False)

    def test_initial_design_resume_and_no_fake_predictions(self):
        p = project()
        original = copy.deepcopy(p)
        first = plan(p)
        self.assertEqual(p, original)
        self.assertEqual("initial_design", first["analysis"]["status"])
        self.assertEqual([], first["analysis"]["predictions"])
        p["pending"] = first["recommendations"]
        second = plan(p)
        self.assertTrue(all(row not in p["pending"] for row in second["recommendations"]))
        self.assertEqual(2, len(second["recommendations"]))
        self.assert_json(second)

    def test_mixed_recipe_native_model_and_candidate_constraint_ranking(self):
        p = project()
        p["parameters"] = [
            {"name": "x", "type": "continuous", "low": 0, "high": 1, "step": 0.1},
            {"name": "y", "type": "continuous", "low": 0, "high": 1, "step": 0.1},
            {"name": "solvent", "type": "categorical", "options": ["water", "ethanol"]},
        ]
        p["constraints"] = [{"kind": "linear", "coefficients": {"x": 1, "y": 1}, "relation": "eq", "rhs": 1},
                            {"kind": "ratio", "numerator": "x", "denominator": "y", "high": 4}]
        p["observations"] = [{"x": x, "y": round(1-x, 1), "solvent": solvent,
                              "loss": 20 + (x-0.3)**2 + (solvent == "water")}
                             for x, solvent in [(0.2, "water"), (0.4, "ethanol"), (0.6, "water"), (0.8, "ethanol")]]
        p["pending"] = [{"x": 0.5, "y": 0.5, "solvent": "ethanol"}]
        p["candidates"] = [{"x": i/10, "y": (10-i)/10, "solvent": solvent}
                           for i in range(9) for solvent in ("water", "ethanol")]
        result = plan(p)
        a = result["analysis"]
        self.assertEqual("trained", a["status"])
        self.assertIn("SingleTaskGP", a["model"])
        self.assertEqual("logEI", a["score_label"])
        self.assertEqual(2, len(result["recommendations"]))
        self.assertTrue(all(feasible(row, p) and row in p["candidates"] and row not in p["pending"]
                            for row in result["recommendations"]))
        self.assertEqual(2, sum(row["selected"] for row in a["predictions"]))
        self.assertTrue(all(row["mean"]["loss"] > 0 and row["std"]["loss"] >= 0 for row in a["predictions"]))
        self.assertEqual(sorted((row["score"] for row in a["predictions"]), reverse=True),
                         [row["score"] for row in a["predictions"]])
        self.assert_json(result)

    def test_native_pending_changes_acquisition_without_changing_posterior(self):
        import torch
        torch.set_num_threads(1)
        p = project()
        x = np.array([[0], [.2], [.4], [.6], [.8], [1.]])
        y = -(x-.35)**2
        model = _fit_gp(x, y, 42)
        candidates = np.array([[.1], [.3], [.5], [.7], [.9]])
        without = _scores(_acquisition(model, p, x, y, np.empty((0, 1)), 42), candidates)
        with_pending = _scores(_acquisition(model, p, x, y, np.array([[.3]]), 42), candidates)
        self.assertFalse(np.allclose(without, with_pending))
        self.assertTrue(np.isfinite(with_pending).all())

    def test_analysis_loo_same_gp_raw_units_and_no_mutation(self):
        p = project()
        p.update(_operation="analyze", observations=[{"x": x, "loss": 10 + (x-.35)**2}
                                                    for x in (0, .25, .5, .75, 1)])
        original = copy.deepcopy(p)
        result = plan(p)
        self.assertEqual(p, original)
        self.assertEqual([], result["recommendations"])
        d = result["analysis"]["diagnostics"]
        self.assertEqual(("LOOCV", "computed", 5, 5), (d["method"], d["status"], d["evaluated"], d["total"]))
        delta = np.array([row["actual"]["loss"]-row["predicted"]["loss"] for row in d["rows"]])
        self.assertAlmostEqual(float(np.sqrt((delta**2).mean())), d["metrics"]["loss"]["rmse"])
        self.assertTrue(all(row["predicted"]["loss"] > 0 for row in d["rows"]))
        self.assert_json(result)

    def test_observed_pareto_mixed_directions_and_fixed_hypervolume(self):
        p = project()
        p["objectives"] = [{"name": "cost", "goal": "min"}, {"name": "yield", "goal": "max"}]
        p["reference_point"] = {"cost": 5, "yield": 0}
        p["observations"] = [{"x": 0, "cost": 3, "yield": 3}, {"x": .5, "cost": 2, "yield": 2},
                             {"x": 1, "cost": 4, "yield": 1}]
        p["objective_mode"] = "pareto"
        pareto = _pareto(p, np.array([[-3, 3], [-2, 2], [-4, 1]]))
        self.assertEqual([0, 1], pareto["indices"])
        self.assertEqual([6, 8, 8], [row["value"] for row in pareto["hypervolume_history"]])
        self.assertEqual(p["reference_point"], pareto["reference_point"])
        result = plan(p)
        self.assertEqual("logNEHVI", result["analysis"]["score_label"])
        self.assertEqual(2, len(result["recommendations"]))
        self.assertEqual([0, 1], result["analysis"]["pareto"]["indices"])
        self.assert_json(result)

    def test_classification_multiclass_entropy_actual_loo_confusion(self):
        p = project()
        p.update(task="classification", classification={"labels": ["bad", "middle", "good", "unseen"]},
                 objectives=[{"name": "label", "goal": "max"}], _operation="analyze")
        p["observations"] = [{"x": x, "label": label} for x, label in
                             [(0, "bad"), (.2, "bad"), (.4, "middle"), (.6, "middle"), (.8, "good"), (1, "good")]]
        result = plan(p)
        a = result["analysis"]
        self.assertEqual("trained", a["status"])
        self.assertEqual("entropy", a["score_label"])
        self.assertTrue(any("unseen" in warning for warning in a["warnings"]))
        for row in a["predictions"]:
            self.assertEqual({"bad", "middle", "good"}, set(row["probabilities"]))
            self.assertAlmostEqual(1, sum(row["probabilities"].values()))
            self.assertTrue(0 <= row["entropy"] <= math.log(3) + 1e-12)
        d = a["diagnostics"]
        self.assertEqual(6, d["evaluated"])
        self.assertEqual(6, sum(map(sum, d["confusion"]["matrix"])))
        self.assertTrue(0 <= d["metrics"]["label"]["accuracy"] <= 1)
        self.assert_json(result)

    def test_one_class_is_initial_design_without_probabilities(self):
        p = project()
        p.update(task="classification", classification={"labels": ["bad", "good"]},
                 objectives=[{"name": "label", "goal": "max"}], _diagnostics=True)
        p["observations"] = [{"x": x, "label": "bad"} for x in (0, .5, 1)]
        result = plan(p)
        self.assertEqual("initial_design", result["analysis"]["status"])
        self.assertEqual([], result["analysis"]["predictions"])
        self.assertEqual(0, result["analysis"]["diagnostics"]["evaluated"])
        self.assertEqual(2, len(result["recommendations"]))
        self.assert_json(result)

    def test_exhausted_domain_can_analyze_and_model_failure_never_falls_back(self):
        p = project()
        p["parameters"][0]["step"] = 1
        p.update(_operation="analyze", observations=[{"x": 0, "loss": 1}, {"x": 1, "loss": 0}])
        result = plan(p)
        self.assertEqual([], result["recommendations"])
        self.assertEqual([], result["analysis"]["predictions"])
        p["parameters"][0]["step"] = .25
        with patch("chembo.modeling._fit_gp", side_effect=RuntimeError("training failed")):
            with self.assertRaisesRegex(RuntimeError, "training failed"):
                plan(p)

    def test_cli_analysis_dispatch_ignores_legacy_state(self):
        p = project()
        p.update(_operation="analyze", backend_state={"engine": "bo-mcp", "state_version": 1, "spec_signature": "old"})
        with tempfile.TemporaryDirectory() as folder:
            request, result = Path(folder)/"request.json", Path(folder)/"result.json"
            request.write_text(json.dumps(p), encoding="utf-8")
            self.assertEqual(0, main([str(request), str(result)]))
            payload = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual([], payload["recommendations"])
        self.assertEqual("nanobo-botorch-v2", payload["provenance"]["engine"])

    def test_public_api_enhanced_domain_never_uses_legacy_model(self):
        p = project()
        p.pop("_modeling_v2")
        result = recommend_modern(p)
        self.assertEqual("nanobo-botorch-v2", result["provenance"]["engine"])
        self.assertTrue(all(abs(row["x"]/.05-round(row["x"]/.05)) < 1e-8 for row in result["recommendations"]))

    @unittest.skipUnless(os.environ.get("CHEMBO_MODERN_WORKER"), "Set CHEMBO_MODERN_WORKER to test the native binary")
    def test_frozen_modern_models_without_python_on_path(self):
        worker = str(Path(os.environ["CHEMBO_MODERN_WORKER"]).resolve())
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        env["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32") if os.name == "nt" else "/usr/bin:/bin"
        regression = project()
        regression["observations"] = [{"x": x, "loss": (x-.35)**2} for x in (0, .25, .5, .75, 1)]
        pareto = copy.deepcopy(regression)
        pareto.update(objective_mode="pareto", _operation="analyze")
        pareto["objectives"].append({"name": "yield", "goal": "max"})
        for row in pareto["observations"]:
            row["yield"] = row["x"]
        classification = project()
        classification.update(task="classification", classification={"labels": ["bad", "good"]},
                              objectives=[{"name": "label", "goal": "max"}], _operation="analyze")
        classification["observations"] = [{"x": x, "label": "good" if x >= .5 else "bad"}
                                          for x in (0, .2, .4, .6, .8, 1)]
        with tempfile.TemporaryDirectory() as folder:
            request, result = Path(folder)/"request.json", Path(folder)/"result.json"
            for p, expected in [(regression, "logEI"), (pareto, "logNEHVI"), (classification, "entropy")]:
                with self.subTest(model=expected):
                    request.write_text(json.dumps(p), encoding="utf-8")
                    result.unlink(missing_ok=True)
                    started = time.monotonic()
                    done = subprocess.run([worker, str(request), str(result)], env=env,
                                          capture_output=True, text=True, timeout=180)
                    print(f"frozen {expected}: {time.monotonic()-started:.2f}s", flush=True)
                    self.assertTrue(result.exists(), done.stderr[-5000:])
                    payload = json.loads(result.read_text(encoding="utf-8"))
                    self.assertEqual(0, done.returncode, payload)
                    self.assertEqual(expected, payload["analysis"]["score_label"])
                    self.assertTrue(payload["analysis"]["predictions"])
                    if p.get("_operation") == "analyze":
                        self.assertEqual([], payload["recommendations"])
                        self.assertEqual("computed", payload["analysis"]["diagnostics"]["status"])


if __name__ == "__main__":
    unittest.main()
