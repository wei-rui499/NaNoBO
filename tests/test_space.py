"""Executable domains stay in original units and exclude completed/reserved work."""
import copy

import pytest

from chembo.engine import validate_project
from chembo.space import candidate_pool, feasible, on_step, pool_metadata


def project(parameters=None):
    return {"name": "recipe", "engine": "bo-mcp", "seed": 9,
            "parameters": parameters or [{"name": "A", "type": "continuous", "low": 0, "high": 1, "step": 0.3}],
            "objectives": [{"name": "yield", "goal": "max"}], "observations": [], "pending": []}


def test_step_grid_uses_low_anchor_never_rounds_to_illegal_upper_bound():
    p = project([{"name": "A", "type": "continuous", "low": 0.1, "high": 1, "step": 0.3}])
    assert candidate_pool(p) == [{"A": 0.1}, {"A": 0.4}, {"A": 0.7}, {"A": 1.0}]
    p["parameters"][0]["high"] = 0.99
    assert candidate_pool(p) == [{"A": 0.1}, {"A": 0.4}, {"A": 0.7}]
    p["observations"] = [{"A": 0.5, "yield": 1}]
    with pytest.raises(ValueError, match="档位"):
        validate_project(p)
    assert not on_step(199999.001, {"low": 0, "step": 1})


@pytest.mark.parametrize("step", [0, -1, True, "NaN", 1e-10])
def test_invalid_steps(step):
    p = project()
    p["parameters"][0]["step"] = step
    with pytest.raises(ValueError):
        validate_project(p)


def test_integer_step_and_finite_constraint_filter_with_blocking():
    p = project([{"name": "A", "type": "discrete", "low": 1, "high": 5, "step": 2},
                 {"name": "B", "type": "continuous", "low": 0, "high": 6, "step": 1}])
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1, "B": 1}, "relation": "eq", "rhs": 6}]
    assert candidate_pool(p) == [{"A": 1, "B": 5.0}, {"A": 3, "B": 3.0}, {"A": 5, "B": 1.0}]
    p["observations"] = [{"A": 1, "B": 5, "yield": 0.2}]
    p["pending"] = [{"A": 3, "B": 3}]
    assert candidate_pool(p) == [{"A": 5, "B": 1.0}]
    p["observations"].append({"A": 5, "B": 1, "yield": 0.3})
    assert candidate_pool(p) == []
    p["observations"][0]["B"] = 4
    with pytest.raises(ValueError, match="约束"):
        validate_project(p)


def test_coupled_equalities_solve_continuous_pivots_with_stepped_variable():
    p = project([{"name": "A", "type": "continuous", "low": 0, "high": 10},
                 {"name": "B", "type": "continuous", "low": 0, "high": 10},
                 {"name": "C", "type": "discrete", "low": 0, "high": 4, "step": 2}])
    p["constraints"] = [
        {"kind": "linear", "coefficients": {"A": 1, "B": 1, "C": 1}, "relation": "eq", "rhs": 10},
        {"kind": "linear", "coefficients": {"A": 1, "B": -1}, "relation": "eq", "rhs": 2}]
    assert candidate_pool(p) == [{"A": 6, "B": 4, "C": 0}, {"A": 5, "B": 3, "C": 2}, {"A": 4, "B": 2, "C": 4}]
    p["observations"] = [{**row, "yield": 1} for row in candidate_pool(p)]
    assert candidate_pool(p) == []


def test_continuous_total_preserves_free_axis_and_is_reproducible():
    p = project([{"name": name, "type": "continuous", "low": 0, "high": 1} for name in ("A", "B", "C")])
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1, "B": 1, "C": 1}, "relation": "eq", "rhs": 1}]
    rows = candidate_pool(p, 24)
    assert len(rows) == 24
    assert rows == candidate_pool(p, 24)
    assert all(feasible(row, validate_project(p)) and sum(row.values()) == pytest.approx(1) for row in rows)


def test_impossible_equalities_and_finite_grid_report_error():
    p = project()
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1}, "relation": "eq", "rhs": 2}]
    with pytest.raises(ValueError, match="冲突"):
        validate_project(p)
    p["constraints"][0]["rhs"] = 0.5
    with pytest.raises(ValueError, match="没有"):
        candidate_pool(p)
    p = project([{"name": name, "type": "continuous", "low": 0, "high": 1} for name in ("A", "B")])
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1, "B": 1}, "relation": "eq", "rhs": rhs} for rhs in (0.5, 1)]
    with pytest.raises(ValueError, match="没有"):
        candidate_pool(p, 4)


def test_ratio_positive_denominator_and_exact_ratio_plane():
    p = project([{"name": name, "type": "continuous", "low": 0, "high": 2} for name in ("A", "B")])
    p["constraints"] = [{"kind": "ratio", "numerator": "A", "denominator": "B", "low": 2, "high": 2}]
    rows = candidate_pool(p, 16)
    assert len(rows) == 16
    assert all(row["B"] > 0 and row["A"] / row["B"] == pytest.approx(2) for row in rows)
    normalized = validate_project(p)
    assert not feasible({"A": 0, "B": 0}, normalized)
    p["pending"] = [{"A": 0, "B": 0}]
    with pytest.raises(ValueError, match="约束"):
        validate_project(p)


def test_explicit_candidates_allow_historic_observations_outside_table():
    p = project()
    p["candidates"] = [{"A": 0.6}, {"A": 0.9}]
    p["observations"] = [{"A": 0, "yield": 1}]
    p["pending"] = [{"A": 0.6}]
    assert candidate_pool(p) == [{"A": 0.9}]
    p["pending"] = [{"A": 0.3}]
    with pytest.raises(ValueError, match="候选表"):
        validate_project(p)
    p["pending"] = []
    p["candidates"].append({"A": 0.9})
    with pytest.raises(ValueError, match="重复"):
        validate_project(p)


def test_finite_domain_limit_and_subsample_explained():
    p = project([{"name": "A", "type": "continuous", "low": 0, "high": 100, "step": 1}])
    first = candidate_pool(p, 5)
    assert len(first) == 5 and first == candidate_pool(p, 5)
    assert pool_metadata(validate_project(p), 5)["strategy"] == "finite-grid-subsample"
    p["parameters"] *= 0
    p["parameters"] = [{"name": name, "type": "discrete", "low": 0, "high": 500} for name in ("A", "B")]
    with pytest.raises(ValueError, match="200000"):
        candidate_pool(p)


@pytest.mark.parametrize("engine", ["gryffin", "atlas"])
def test_classic_backends_refuse_enhanced_domain(engine):
    p = project()
    p["engine"] = engine
    with pytest.raises(ValueError, match="BoTorch"):
        validate_project(p)


def test_pareto_and_classification_contract_and_metadata():
    p = project()
    p.update(task="classification", classification={"labels": ["0", "1"]}, notes="memo", history=[{"ok": True}], extra={"preserve": True})
    p["parameters"][0]["unit"] = "mL"
    p["observations"] = [{"A": 0, "yield": 1}]
    before = copy.deepcopy(p)
    normalized = validate_project(p)
    assert normalized["observations"][0]["yield"] == "1"
    assert normalized["extra"] == before["extra"] and normalized["parameters"][0]["unit"] == "mL"
    assert p == before
    p["observations"][0]["yield"] = "other"
    with pytest.raises(ValueError, match="标签"):
        validate_project(p)
    p = project()
    p["objective_mode"] = "pareto"
    with pytest.raises(ValueError, match="至少"):
        validate_project(p)
    p["objectives"].append({"name": "cost", "goal": "min"})
    assert validate_project(p)["objective_mode"] == "pareto"


def test_explicit_candidates_refuse_near_duplicates_consistently_with_pending():
    p = project([{ "name": "A", "type": "continuous", "low": 0, "high": 1}])
    p["candidates"] = [{"A": 0.2}, {"A": 0.2000001}]
    with pytest.raises(ValueError, match="过于接近"):
        validate_project(p)


def test_step_smaller_than_machine_precision_is_rejected():
    p = project([{ "name": "A", "type": "continuous", "low": 1e20, "high": 1e20 + 1e6, "step": 1000}])
    with pytest.raises(ValueError, match="浮点精度"):
        validate_project(p)


def test_equalities_keep_declared_tolerance_and_coefficient_units():
    p = project([{ "name": "A", "type": "continuous", "low": 0, "high": 1}])
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1}, "relation": "eq", "rhs": rhs, "tolerance": 1e-6} for rhs in (0.5, 0.5000001)]
    assert candidate_pool(p) == [{"A": 0.5}]
    p["constraints"] = [{"kind": "linear", "coefficients": {"A": 1e-16}, "relation": "eq", "rhs": 5e-17, "tolerance": 1e-25}]
    assert candidate_pool(p) == [{"A": 0.5}]
