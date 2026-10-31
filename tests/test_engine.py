"""Fast input-contract tests plus opt-in real backend fits.

Run CHEMBO_INTEGRATION=1 python -m pytest tests/test_engine.py for real model QA.
"""
import copy
import os

import pytest

from chembo.engine import read_observations, reconcile_project, recommend, validate_project


def project(engine="gryffin"):
    return {"name": "合成", "engine": engine, "seed": 17, "batch_size": 2,
            "parameters": [{"name": "temperature", "type": "continuous", "low": 20, "high": 80}],
            "objectives": [{"name": "yield", "goal": "max", "tolerance": 0.2}],
            "observations": [], "pending": []}


def test_normalize_without_mutation():
    p = project()
    before = copy.deepcopy(p)
    normalized = validate_project(p)
    normalized["parameters"][0]["low"] = 0
    assert p == before


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), "NaN", True, None])
def test_reject_nonfinite_parameters(bad):
    p = project()
    p["parameters"][0]["low"] = bad
    with pytest.raises(ValueError):
        validate_project(p)


@pytest.mark.parametrize("field,value", [("seed", -1), ("seed", 2**31), ("batch_size", 0), ("batch_size", 25), ("batch_size", 1.5)])
def test_integer_limits(field, value):
    p = project()
    p[field] = value
    with pytest.raises(ValueError):
        validate_project(p)


@pytest.mark.parametrize("row", [{"temperature": 50}, {"temperature": 50, "yield": ""},
                                  {"temperature": 50, "yield": "NaN"}, {"temperature": 90, "yield": 1},
                                  {"temperature": 50, "yield": 1, "surprise": 3}])
def test_reject_invalid_observation(row):
    p = project()
    p["observations"] = [row]
    with pytest.raises(ValueError):
        validate_project(p)


def test_replicates_allowed_but_pending_duplicate_rejected():
    p = project()
    p["observations"] = [{"temperature": 30, "yield": 0.2}, {"temperature": 30, "yield": 0.3}]
    assert len(validate_project(p)["observations"]) == 2
    p["pending"] = [{"temperature": 30.00001}]
    with pytest.raises(ValueError, match="重复"):
        validate_project(p)


def test_duplicate_names_and_categories():
    p = project()
    p["objectives"][0]["name"] = "temperature"
    with pytest.raises(ValueError):
        validate_project(p)
    p = project()
    p["parameters"] = [{"name": "solvent", "type": "categorical", "options": ["water", " water "]}]
    with pytest.raises(ValueError):
        validate_project(p)


def test_atlas_multiobjective_not_silently_scalarized():
    p = project("atlas")
    p["objectives"].append({"name": "cost", "goal": "min"})
    with pytest.raises(ValueError, match="单目标"):
        validate_project(p)


def test_csv_strict_and_bom(tmp_path):
    path = tmp_path / "observed.csv"
    path.write_text("\ufefftemperature,yield\n30,0.5\n", encoding="utf-8")
    assert read_observations(project(), path) == [{"temperature": 30.0, "yield": 0.5}]
    for content in ["temperature,yield\n30,\n", "temperature,temperature\n30,40\n",
                    "temperature,yield,extra\n30,0.5,x\n", "temperature,yield\n30,0.5,extra\n"]:
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            read_observations(project(), path)


def test_finite_space_exhaustion_before_backend_import():
    p = project()
    p["parameters"] = [{"name": "n", "type": "discrete", "low": 1, "high": 2}]
    p["observations"] = [{"n": 1, "yield": 1}]
    p["pending"] = [{"n": 2}]
    with pytest.raises(ValueError, match="只剩 0"):
        recommend(p)


def test_no_fake_measurements_or_random_recovery(monkeypatch):
    import chembo.engine as engine
    p = project()
    p["observations"] = [{"temperature": 30, "yield": 0.4}]
    before = copy.deepcopy(p)
    def backend(passed, blocked, count, seed):
        assert passed["observations"] == before["observations"]
        return [{"temperature": 30}] * count
    monkeypatch.setattr(engine, "_gryffin", backend)
    with pytest.raises(RuntimeError, match="不重复"):
        recommend(p)
    assert p == before


real = pytest.mark.skipif(os.environ.get("CHEMBO_INTEGRATION") != "1", reason="opt-in real scientific models")


@real
@pytest.mark.parametrize("engine", ["gryffin", "atlas"])
def test_real_initial_design(engine):
    p = project(engine)
    p["pending"] = [{"temperature": 50}]
    samples = recommend(p)
    assert len(samples) == 2
    assert all(set(s) == {"temperature"} and 20 <= s["temperature"] <= 80 and abs(s["temperature"] - 50) > 60e-6 for s in samples)
    assert abs(samples[0]["temperature"] - samples[1]["temperature"]) > 60e-6


@real
@pytest.mark.parametrize("engine", ["gryffin", "atlas"])
def test_real_trained_model(engine):
    p = project(engine)
    p["batch_size"] = 1
    p["observations"] = [{"temperature": t, "yield": 1 - ((t - 57) / 40)**2} for t in (20, 30, 45, 65, 80)]
    before = copy.deepcopy(p)
    samples = recommend(p)
    assert len(samples) == 1
    assert 20 <= samples[0]["temperature"] <= 80
    assert all(abs(samples[0]["temperature"] - row["temperature"]) > 60e-6 for row in p["observations"])
    assert p == before


@real
def test_real_gryffin_chimera_and_mixed_initial():
    p = project()
    p["parameters"].extend([{"name": "cycles", "type": "discrete", "low": 1, "high": 3},
                            {"name": "solvent", "type": "categorical", "options": ["water", "ethanol"]}])
    p["objectives"].append({"name": "cost", "goal": "min", "tolerance": 0.2})
    samples = recommend(p)
    assert all(s["cycles"] in (1, 2, 3) and s["solvent"] in ("water", "ethanol") for s in samples)
    p["batch_size"] = 1
    p["observations"] = [{"temperature": t, "cycles": c, "solvent": s, "yield": y, "cost": cost} for t, c, s, y, cost in
                         [(20, 1, "water", 0.1, 5), (40, 2, "water", 0.5, 4), (60, 3, "ethanol", 0.8, 8), (80, 1, "ethanol", 0.4, 2)]]
    assert len(recommend(p)) == 1


def test_metadata_and_formula_escaped_category(tmp_path):
    p = project()
    p["notes"] = "chemistry"
    p["history"] = [{"run": 1}]
    p["future_metadata"] = {"anything": "preserved"}
    p["parameters"] = [{"name": "solvent", "type": "categorical", "options": ["=water", "ethanol"], "unit": ""}]
    normalized = validate_project(p)
    assert normalized["future_metadata"] == p["future_metadata"]
    assert normalized["parameters"][0]["unit"] == ""
    path = tmp_path / "observed.csv"
    path.write_text("solvent,yield\n'=water,0.5\n", encoding="utf-8")
    assert read_observations(p, path)[0]["solvent"] == "=water"


def test_modern_engine_requires_separate_worker():
    with pytest.raises(RuntimeError, match="worker"):
        recommend(project("bo-mcp"))


def test_reconcile_removes_only_completed_pending():
    p = project()
    p["observations"] = [{"temperature": 30, "yield": 0.4}]
    p["pending"] = [{"temperature": 30.00001}, {"temperature": 50}]
    before = copy.deepcopy(p)
    result = reconcile_project(p)
    assert result["pending"] == [{"temperature": 50.0}]
    assert result["observations"] == p["observations"]
    assert p == before
    p["pending"].append({"temperature": 50})
    with pytest.raises(ValueError, match="重复"):
        reconcile_project(p)
    p["pending"] = [{"temperature": 30, "yield": 0.4}]
    with pytest.raises(ValueError, match="未知字段"):
        reconcile_project(p)


@real
def test_real_gryffin_initial_finite_batch_without_replacement():
    p = project()
    p["parameters"] = [{"name": "solvent", "type": "categorical", "options": ["a", "b", "c"]}]
    p["pending"] = [{"solvent": "c"}]
    assert {row["solvent"] for row in recommend(p)} == {"a", "b"}


@real
def test_real_atlas_finite_initial_batch_without_replacement():
    p = project("atlas")
    p["parameters"] = [{"name": "solvent", "type": "categorical", "options": ["a", "b", "c"]}]
    p["pending"] = [{"solvent": "c"}]
    assert {row["solvent"] for row in recommend(p)} == {"a", "b"}


@real
@pytest.mark.parametrize("batch_size", [1, 2])
def test_real_atlas_mixed_trained_batch(batch_size):
    p = project("atlas")
    p["batch_size"] = batch_size
    p["parameters"].extend([{"name": "cycles", "type": "discrete", "low": 1, "high": 2},
                            {"name": "solvent", "type": "categorical", "options": ["water", "ethanol"]}])
    p["observations"] = [{"temperature": t, "cycles": c, "solvent": s, "yield": y} for t, c, s, y in
                         [(20, 1, "water", 0.1), (40, 2, "water", 0.5), (60, 2, "ethanol", 0.8),
                          (80, 1, "ethanol", 0.4), (50, 1, "water", 0.6)]]
    samples = recommend(p)
    assert len(samples) == batch_size
    assert all(s["cycles"] in (1, 2) and s["solvent"] in ("water", "ethanol") and 20 <= s["temperature"] <= 80 for s in samples)


@real
def test_real_atlas_initial_full_batch():
    p = project("atlas")
    p["batch_size"] = 24
    assert len(recommend(p)) == 24


@real
def test_real_atlas_trained_continuous_batch():
    p = project("atlas")
    p["observations"] = [{"temperature": t, "yield": 1 - ((t - 57) / 40)**2} for t in (20, 30, 45, 65, 80)]
    assert len(recommend(p)) == 2


@real
def test_real_atlas_trained_finite_batch():
    p = project("atlas")
    p["parameters"] = [{"name": "n", "type": "discrete", "low": 1, "high": 8}]
    p["observations"] = [{"n": n, "yield": n / 8} for n in range(1, 6)]
    p["pending"] = [{"n": 8}]
    assert {sample["n"] for sample in recommend(p)} == {6, 7}


@real
def test_real_atlas_trained_finite_single():
    p = project("atlas")
    p["batch_size"] = 1
    p["parameters"] = [{"name": "n", "type": "discrete", "low": 1, "high": 8}]
    p["observations"] = [{"n": n, "yield": n / 8} for n in range(1, 6)]
    p["pending"] = [{"n": 8}]
    assert recommend(p)[0]["n"] in {6, 7}


@real
def test_real_atlas_pymoo_constraints_decode_original_units():
    """Exact regression for upstream Pymoo passing indices to raw constraints."""
    from atlas.acquisition_optimizers.pymoo_optimizer import PymooProblemWrapper
    from olympus import ParameterContinuous, ParameterDiscrete, ParameterCategorical
    from olympus.campaigns import ParameterSpace

    space = ParameterSpace()
    space.add(ParameterContinuous(name="temperature", low=20, high=80))
    space.add(ParameterDiscrete(name="cycles", options=[5, 6, 7]))
    space.add(ParameterCategorical(name="solvent", options=["buffer A", "特殊溶剂"]))
    wrapper = object.__new__(PymooProblemWrapper)
    wrapper.param_space = space
    wrapper.fixed_param_name = "not-a-parameter"
    wrapper.cat_option_maps = {"solvent": {"x0": "buffer A", "x1": "特殊溶剂"}}
    seen = []
    def allowed(raw):
        seen.append(list(raw))
        return raw != [50.0, 7.0, "特殊溶剂"]
    wrapper.known_constraints = [allowed]
    result = wrapper._known_constraints_wrapper([
        {"temperature": 50.0, "cycles": 2, "solvent": "x1"},
        {"temperature": 40.0, "cycles": 0, "solvent": "x0"},
    ])
    assert result.tolist() == [2, -2]
    assert seen == [[50.0, 7.0, "特殊溶剂"], [40.0, 5.0, "buffer A"]]


@real
def test_real_atlas_trained_custom_categories_pending():
    p = project("atlas")
    options = ["water", "buffer A", "乙醇", "DMSO", "MeCN", "特殊溶剂甲", "特殊溶剂乙", "queued solvent"]
    p["parameters"] = [{"name": "solvent", "type": "categorical", "options": options}]
    p["observations"] = [{"solvent": option, "yield": i / 5} for i, option in enumerate(options[:5])]
    p["pending"] = [{"solvent": options[7]}]
    assert {sample["solvent"] for sample in recommend(p)} == {options[5], options[6]}
