"""Executable recipe domains: steps, explicit candidates and safe linear/ratio constraints.

This module never evaluates user expressions. A candidate is constructed in the
legal domain before scoring, rather than rounding or normalizing a recommendation.
"""
from __future__ import annotations

import itertools
import math
import random
from decimal import Decimal

MAX_FINITE_SIZE = 200000


def on_step(value, parameter):
    if "step" not in parameter:
        return True
    index = (float(value) - parameter["low"]) / parameter["step"]
    # Tolerance covers only binary representation of an intended grid value.
    return abs(index - round(index)) <= 1e-7


def normalize_constraints(raw_constraints, parameters):
    from .engine import _fields, _number
    if not isinstance(raw_constraints, list):
        raise ValueError("配方约束必须是列表。")
    numeric = {p["name"]: p for p in parameters if p["type"] != "categorical"}
    result = []
    for index, raw in enumerate(raw_constraints, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"约束 {index} 必须是对象。")
        kind = raw.get("kind")
        if kind == "linear":
            _fields(raw, {"kind", "coefficients", "relation", "rhs", "tolerance"}, f"约束 {index}")
            coefficients = raw.get("coefficients")
            if not isinstance(coefficients, dict) or not coefficients:
                raise ValueError("线性约束至少需要一个数值变量的系数。")
            if set(coefficients) - set(numeric):
                raise ValueError("线性约束只能使用已定义的数值变量。")
            terms = {name: _number(value, f"{name} 系数") for name, value in coefficients.items()}
            terms = {name: value for name, value in terms.items() if value != 0}
            if not terms:
                raise ValueError("线性约束系数不能全为零。")
            relation = raw.get("relation")
            if relation not in ("eq", "le", "ge"):
                raise ValueError("线性约束关系必须是 eq、le 或 ge。")
            tolerance = _number(raw.get("tolerance", 1e-8), "约束容差")
            if tolerance <= 0:
                raise ValueError("约束容差必须为正数。")
            item = {"kind": kind, "coefficients": terms, "relation": relation,
                    "rhs": _number(raw.get("rhs"), "约束右侧值"), "tolerance": tolerance}
            # Detect impossible single constraints before sampling any domain.
            lower = sum(coef * numeric[name]["low" if coef >= 0 else "high"] for name, coef in terms.items())
            upper = sum(coef * numeric[name]["high" if coef >= 0 else "low"] for name, coef in terms.items())
            if ((relation == "eq" and not lower - tolerance <= item["rhs"] <= upper + tolerance)
                    or (relation == "le" and lower > item["rhs"] + tolerance)
                    or (relation == "ge" and upper < item["rhs"] - tolerance)):
                raise ValueError("配方约束与参数边界冲突，没有可行条件。")
        elif kind == "ratio":
            _fields(raw, {"kind", "numerator", "denominator", "low", "high"}, f"约束 {index}")
            numerator, denominator = raw.get("numerator"), raw.get("denominator")
            if numerator not in numeric or denominator not in numeric or numerator == denominator:
                raise ValueError("配比约束需要两个不同的数值变量。")
            if numeric[denominator]["high"] <= 0:
                raise ValueError("配比约束的分母必须有大于零的允许值。")
            item = {"kind": kind, "numerator": numerator, "denominator": denominator}
            for bound in ("low", "high"):
                if bound in raw and raw[bound] is not None:
                    item[bound] = _number(raw[bound], f"配比{bound}")
            if "low" not in item and "high" not in item:
                raise ValueError("配比约束至少设置一个上下限。")
            if "low" in item and "high" in item and item["low"] > item["high"]:
                raise ValueError("配比上限不能小于下限。")
        else:
            raise ValueError("约束类型必须是 linear 或 ratio。")
        result.append(item)
    return result


def feasible(row, project):
    """Check a parameter-only row in original units, including step and constraints."""
    try:
        for parameter in project["parameters"]:
            value = row[parameter["name"]]
            if parameter["type"] == "categorical":
                if value not in parameter["options"]:
                    return False
            else:
                if isinstance(value, bool) or not math.isfinite(float(value)):
                    return False
                if not parameter["low"] <= value <= parameter["high"]:
                    return False
                if parameter["type"] == "discrete" and not float(value).is_integer():
                    return False
                if not on_step(value, parameter):
                    return False
        for constraint in project.get("constraints", []):
            if constraint["kind"] == "linear":
                residual = sum(coef * row[name] for name, coef in constraint["coefficients"].items()) - constraint["rhs"]
                tolerance = constraint.get("tolerance", 1e-8)
                if not math.isfinite(residual):
                    return False
                if constraint["relation"] == "eq" and abs(residual) > tolerance:
                    return False
                if constraint["relation"] == "le" and residual > tolerance:
                    return False
                if constraint["relation"] == "ge" and residual < -tolerance:
                    return False
            else:
                denominator = row[constraint["denominator"]]
                if denominator <= 0:
                    return False
                ratio = row[constraint["numerator"]] / denominator
                if not math.isfinite(ratio):
                    return False
                if "low" in constraint and ratio < constraint["low"] - 1e-10:
                    return False
                if "high" in constraint and ratio > constraint["high"] + 1e-10:
                    return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False


def _levels(parameter):
    if parameter["type"] == "categorical":
        return list(parameter["options"])
    step = parameter.get("step", 1 if parameter["type"] == "discrete" else None)
    if step is None:
        return None
    low, high, width = map(lambda value: Decimal(str(value)), (parameter["low"], parameter["high"], step))
    count = int((high - low) // width) + 1
    if count > MAX_FINITE_SIZE + 1:
        raise ValueError("单个变量的允许档位超过 200001 个，请增大步长。")
    values = [float(low + i * width) for i in range(count)]
    return [int(value) for value in values] if parameter["type"] == "discrete" else values


def pool_metadata(project, limit=4096):
    explicit = project.get("candidates", [])
    levels = [_levels(p) for p in project["parameters"]]
    full_size = len(explicit) if explicit else math.prod(len(values) for values in levels) if all(values is not None for values in levels) else None
    if explicit:
        strategy = "explicit-subsample" if len(explicit) > limit else "explicit-candidates"
    elif full_size is not None:
        strategy = "finite-grid-subsample" if full_size > limit else "finite-grid"
    else:
        strategy = "feasible-sample"
    return {"strategy": strategy, "search_limit": limit, "full_size": full_size,
            "full_size_definition": "显式候选行数或过滤约束前的全网格组合数；不是合法未做条件数"}


def _equality_system(parameters, constraints):
    """Eliminate continuous pivots once, leaving sampled free/grid variables."""
    adjustable = [p["name"] for p in parameters if p["type"] == "continuous" and "step" not in p]
    fixed = [p["name"] for p in parameters if p["type"] != "categorical" and p["name"] not in adjustable]
    names = adjustable + fixed
    equalities = [c for c in constraints if c["kind"] == "linear" and c["relation"] == "eq"]
    # An exact ratio is a linear equality while its positive-denominator domain
    # is still checked by feasible(). Rejection sampling cannot hit a ratio plane.
    equalities += [{"coefficients": {c["numerator"]: 1, c["denominator"]: -c["low"]}, "rhs": 0}
                   for c in constraints if c["kind"] == "ratio" and "low" in c and c.get("high") == c["low"]]
    matrix = [[float(c["coefficients"].get(name, 0)) for name in names] + [c["rhs"]] for c in equalities]
    tolerances = [c.get("tolerance", 1e-8) for c in equalities]
    # Normalize each equation so coefficients in different physical units do not
    # disappear behind an absolute pivot threshold. Propagate its residual bound.
    for r, values in enumerate(matrix):
        scale = max(abs(value) for value in values[:-1])
        matrix[r] = [value / scale for value in values]
        tolerances[r] /= scale
    pivot_row, pivots = 0, []
    for col in range(len(adjustable)):
        pivot = max(range(pivot_row, len(matrix)), key=lambda r: abs(matrix[r][col]), default=None)
        if pivot is None or abs(matrix[pivot][col]) <= 1e-14:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        tolerances[pivot_row], tolerances[pivot] = tolerances[pivot], tolerances[pivot_row]
        divisor = matrix[pivot_row][col]
        matrix[pivot_row] = [value / divisor for value in matrix[pivot_row]]
        tolerances[pivot_row] /= abs(divisor)
        for r in range(len(matrix)):
            if r != pivot_row:
                coefficient = matrix[r][col]
                matrix[r] = [a - coefficient * b for a, b in zip(matrix[r], matrix[pivot_row])]
                tolerances[r] += abs(coefficient) * tolerances[pivot_row]
        pivots.append((pivot_row, col))
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    if any(all(abs(value) <= 1e-12 for value in values[:-1]) and abs(values[-1]) > tolerances[r] for r, values in enumerate(matrix)):
        raise ValueError("等式约束相互冲突，没有可行候选条件。")
    pivot_columns = {col for _, col in pivots}
    free = [name for j, name in enumerate(adjustable) if j not in pivot_columns]

    def project(row):
        for r in range(pivot_row, len(matrix)):
            values = matrix[r]
            residual = values[-1] - sum(values[j] * row[name] for j, name in enumerate(names) if j >= len(adjustable))
            if abs(residual) > tolerances[r]:
                return None
        result = dict(row)
        for r, col in pivots:
            result[names[col]] = matrix[r][-1] - sum(matrix[r][j] * row[name] for j, name in enumerate(names) if j not in pivot_columns)
        return result

    return project, free


def candidate_pool(project, limit=4096):
    """Return legal, distinct, unmeasured/unreserved candidates, deterministically.

    Explicit/finite domains are fully constraint-filtered up to 200,000 source
    rows; larger finite domains require an explicit candidate file or coarser
    steps. Continuous domains use a bounded reproducible feasible sample, not a
    claim of exhaustive optimization. All-blocked domains return an empty list.
    """
    from .engine import _same, validate_project
    project = validate_project(project)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_FINITE_SIZE:
        raise ValueError("候选池上限必须是 1–200000 的整数。")
    parameters = project["parameters"]
    levels = [_levels(parameter) for parameter in parameters]
    blocked = project["observations"] + project["pending"]
    rng = random.Random(project["seed"])
    explicit = project.get("candidates", [])
    result, had_feasible = [], False

    def add(row, deduplicate=True):
        nonlocal had_feasible
        if not feasible(row, project):
            return
        had_feasible = True
        if any(_same(row, other, parameters) for other in blocked):
            return
        if deduplicate and any(_same(row, other, parameters) for other in result):
            return
        result.append(row)

    if explicit or all(values is not None for values in levels):
        size = len(explicit) if explicit else math.prod(len(values) for values in levels)
        if size > MAX_FINITE_SIZE:
            raise ValueError("有限配方空间超过 200000 组，请增大步长或导入预先筛选的候选表。")
        names = [p["name"] for p in parameters]
        iterable = explicit if explicit else (dict(zip(names, values)) for values in itertools.product(*levels))
        # Exact finite domains are unique by construction; use exact keys to
        # avoid quadratic scans over up to 200k rows. Near-duplicate checks are
        # still applied against measured/pending conditions.
        for row in iterable:
            if not feasible(row, project):
                continue
            had_feasible = True
            if any(_same(row, other, parameters) for other in blocked):
                continue
            result.append(dict(row))
        if len(result) > limit:
            selected = sorted(rng.sample(range(len(result)), limit))
            result = [result[index] for index in selected]
    else:
        project_equalities, free = _equality_system(parameters, project["constraints"])
        finite_axes = [(p["name"], values) for p, values in zip(parameters, levels) if values is not None]
        # Fully determined continuous coordinates leave a finite domain. Enumerate
        # it once so an exhausted equality domain does not repeat 300k samples.
        fixed_size = math.prod(len(values) for _, values in finite_axes)
        if not free and fixed_size <= MAX_FINITE_SIZE:
            names = [name for name, _ in finite_axes]
            for values in itertools.product(*(values for _, values in finite_axes)):
                row = {p["name"]: p.get("low") for p in parameters}
                row.update(zip(names, values))
                row = project_equalities(row)
                if row is not None:
                    add(row, deduplicate=False)
            if len(result) > limit:
                selected = sorted(rng.sample(range(len(result)), limit))
                result = [result[index] for index in selected]
            if not had_feasible:
                raise ValueError("等式约束与档位或边界冲突，没有可行候选条件。")
            return result
        # Include endpoints and the midpoint in addition to seeded random draws.
        # This improves basic boundary coverage while never stepping off-grid.
        max_attempts = min(100000, max(1000, limit * 40))
        for attempt in range(max_attempts):
            row = {}
            for parameter, values in zip(parameters, levels):
                if values is not None:
                    row[parameter["name"]] = rng.choice(values)
                else:
                    fraction = (0.0, 1.0, 0.5)[attempt] if attempt < 3 else rng.random()
                    row[parameter["name"]] = parameter["low"] + fraction * (parameter["high"] - parameter["low"])
            row = project_equalities(row)
            if row is not None:
                add(row)
            if len(result) == limit:
                break
    if not had_feasible:
        raise ValueError("没有找到满足边界、步长和配方约束的候选条件；请检查约束，或导入合法候选表。")
    return result
