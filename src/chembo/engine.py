"""Validated ask/tell adapters for the real upstream Gryffin and Atlas planners.

Pending experiments only restrict the search space. They never become measurements.
All public results contain JSON-compatible Python values; backends import lazily.
"""
from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path
from typing import Any

_NEAR_FRACTION = 1e-6


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{label} 必须是有限数字。")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label} 必须是有限数字。") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} 不允许 NaN 或 Infinity。")
    return result


def _integer(value: Any, label: str, low: int, high: int) -> int:
    number = _number(value, label)
    if not number.is_integer() or not low <= number <= high:
        raise ValueError(f"{label} 必须是 {low}–{high} 之间的整数。")
    return int(number)


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} 必须是非空文字，且不能包含换行等控制字符。")
    return value.strip()


def _fields(value: Any, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须是对象。")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} 包含未知字段：{', '.join(sorted(map(str, unknown)))}。")
    return value


def _row(row: Any, parameters: list[dict], objectives: list[dict], label: str, classification_labels: list[str] | None = None) -> dict:
    names = [p["name"] for p in parameters] + [o["name"] for o in objectives]
    _fields(row, set(names), label)
    missing = set(names) - set(row)
    if missing:
        raise ValueError(f"{label} 缺少字段：{', '.join(sorted(missing))}。")
    result = {}
    for p in parameters:
        key = p["name"]
        if p["type"] == "categorical":
            value = _name(row[key], f"{label} / {key}")
            if value not in p["options"] and value.startswith("'") and value[1:] in p["options"]:
                value = value[1:]  # Undo this app's spreadsheet formula escaping only when unambiguous.
            if value not in p["options"]:
                raise ValueError(f"{label} / {key} 不在允许的类别中。")
        else:
            value = _number(row[key], f"{label} / {key}")
            if not p["low"] <= value <= p["high"]:
                raise ValueError(f"{label} / {key} 超出范围 [{p['low']}, {p['high']}]。")
            if p["type"] == "discrete":
                if not value.is_integer():
                    raise ValueError(f"{label} / {key} 必须是整数。")
                value = int(value)
            if "step" in p:
                from .space import on_step
                if not on_step(value, p):
                    raise ValueError(f"{label} / {key} 不在以 {p['low']} 为起点、步长 {p['step']} 的允许档位上。")
        result[key] = value
    for o in objectives:
        if classification_labels is None:
            result[o["name"]] = _number(row[o["name"]], f"{label} / {o['name']}")
        else:
            value = row[o["name"]]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric = _number(value, f"{label} / {o['name']}")
                value = str(int(numeric)) if numeric.is_integer() else str(numeric)
            value = _name(value, f"{label} / {o['name']}")
            if value not in classification_labels and value.startswith("'") and value[1:] in classification_labels:
                value = value[1:]
            if value not in classification_labels:
                raise ValueError(f"{label} / {o['name']} 不在已定义的分类标签中。")
            result[o["name"]] = value
    return result


def _same(a: dict, b: dict, parameters: list[dict]) -> bool:
    for p in parameters:
        key = p["name"]
        if p["type"] == "continuous":
            if abs(float(a[key]) - float(b[key])) > (p["high"] - p["low"]) * _NEAR_FRACTION:
                return False
        elif p["type"] == "discrete":
            if float(a[key]) != float(b[key]):
                return False
        elif a[key] != b[key]:
            return False
    return True


def validate_project(project: dict) -> dict:
    """Return a detached normalized project, or raise an actionable ValueError.

    Replicate measured experiments are allowed. Pending points must be distinct
    from each other and from measured points (continuous tolerance: 1e-6 range).
    Objective order is the Chimera priority order; tolerance is relative [0, 1].
    """
    if not isinstance(project, dict):
        raise ValueError("项目必须是对象。")
    try:
        json.dumps(project, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("项目必须是有效的 JSON 数据，且不能包含 NaN/Infinity。") from exc
    if "notes" in project and not isinstance(project["notes"], str):
        raise ValueError("项目备注必须是文字。")
    if "history" in project and not isinstance(project["history"], list):
        raise ValueError("项目历史必须是列表。")
    engine = project.get("engine", "gryffin")
    if engine not in ("gryffin", "atlas", "bo-mcp"):
        raise ValueError("算法必须是 gryffin、atlas 或 bo-mcp。")
    task = project.get("task", "optimization")
    mode = project.get("objective_mode", "hierarchical")
    if task not in ("optimization", "classification"):
        raise ValueError("任务必须是 optimization 或 classification。")
    if mode not in ("hierarchical", "pareto"):
        raise ValueError("多目标模式必须是 hierarchical 或 pareto。")
    classification = None
    if task == "classification":
        raw_classification = project.get("classification", {})
        _fields(raw_classification, {"labels"}, "分类设置")
        labels = raw_classification.get("labels")
        if not isinstance(labels, list) or len(labels) < 2:
            raise ValueError("分类任务至少需要两个预定义标签。")
        labels = [_name(label, "分类标签") for label in labels]
        if len(set(labels)) != len(labels):
            raise ValueError("分类标签不能重复。")
        classification = {"labels": labels}
        if mode == "pareto":
            raise ValueError("分类任务不能使用 Pareto 多目标模式。")
    parameters, objectives = [], []
    raw_parameters = project.get("parameters")
    raw_objectives = project.get("objectives")
    if not isinstance(raw_parameters, list) or not raw_parameters:
        raise ValueError("至少设置一个实验参数。")
    if not isinstance(raw_objectives, list) or not raw_objectives:
        raise ValueError("至少设置一个优化目标。")
    used_names = set()
    for i, raw in enumerate(raw_parameters, 1):
        _fields(raw, {"name", "type", "low", "high", "options", "unit", "step"}, f"参数 {i}")
        p = {"name": _name(raw.get("name"), f"参数 {i} 名称"), "type": raw.get("type")}
        if p["name"] in used_names:
            raise ValueError("参数和目标名称必须各不相同。")
        used_names.add(p["name"])
        if p["type"] == "categorical":
            options = raw.get("options")
            if not isinstance(options, list) or len(options) < 2:
                raise ValueError(f"{p['name']} 至少需要两个类别。")
            p["options"] = [_name(v, f"{p['name']} 类别") for v in options]
            if len(set(p["options"])) != len(options):
                raise ValueError(f"{p['name']} 的类别不能重复。")
        elif p["type"] in ("continuous", "discrete"):
            p["low"] = _number(raw.get("low"), f"{p['name']} 下限")
            p["high"] = _number(raw.get("high"), f"{p['name']} 上限")
            if p["low"] >= p["high"] or not math.isfinite(p["high"] - p["low"]):
                raise ValueError(f"{p['name']} 上限必须大于下限，且跨度必须有限。")
            if p["type"] == "discrete":
                # Gryffin stores discrete options as signed int32 values.
                p["low"] = _integer(p["low"], f"{p['name']} 下限", -(2**31), 2**31 - 1)
                p["high"] = _integer(p["high"], f"{p['name']} 上限", -(2**31), 2**31 - 1)
                if p["high"] - p["low"] > 10000:
                    raise ValueError(f"{p['name']} 整数范围超过 10001 个候选值，请缩小范围。")
        else:
            raise ValueError(f"{p['name']} 的类型必须是 continuous、discrete 或 categorical。")
        if "step" in raw:
            if p["type"] == "categorical":
                raise ValueError(f"{p['name']} 类别变量不能设置数值步长。")
            step = _number(raw["step"], f"{p['name']} 步长")
            if step <= 0 or not math.isfinite((p["high"] - p["low"]) / step):
                raise ValueError(f"{p['name']} 步长必须为正数，且档位数必须有限。")
            if p["type"] == "discrete" and not step.is_integer():
                raise ValueError(f"{p['name']} 整数变量的步长必须是整数。")
            if step < max(math.ulp(p["low"]), math.ulp(p["high"])):
                raise ValueError(f"{p['name']} 的步长小于当前数值范围的浮点精度，请调整单位或增大步长。")
            if (p["high"] - p["low"]) / step > 200000:
                raise ValueError(f"{p['name']} 的步长生成超过 200001 个档位，请增大步长。")
            p["step"] = int(step) if p["type"] == "discrete" else step
        if "unit" in raw:
            if not isinstance(raw["unit"], str):
                raise ValueError(f"{p['name']} 单位必须是文字。")
            p["unit"] = raw["unit"]
        parameters.append(p)
    for i, raw in enumerate(raw_objectives, 1):
        _fields(raw, {"name", "goal", "tolerance"}, f"目标 {i}")
        name = _name(raw.get("name"), f"目标 {i} 名称")
        if name in used_names:
            raise ValueError("参数和目标名称必须各不相同。")
        used_names.add(name)
        goal = raw.get("goal")
        if goal not in ("min", "max"):
            raise ValueError(f"{name} 的方向必须是 min 或 max。")
        tolerance = _number(raw.get("tolerance", 0.2), f"{name} 容差")
        if not 0 <= tolerance <= 1:
            raise ValueError(f"{name} 的相对容差必须在 0–1 之间。")
        objectives.append({"name": name, "goal": goal, "tolerance": tolerance})
    if task == "classification" and len(objectives) != 1:
        raise ValueError("分类任务必须且只能设置一个标签列。")
    if mode == "pareto" and len(objectives) < 2:
        raise ValueError("Pareto 优化至少需要两个数值目标。")
    if mode == "hierarchical" and engine in ("atlas", "bo-mcp") and len(objectives) != 1:
        raise ValueError("Atlas / BO-MCP 层级接口支持单目标；多目标请选择 Pareto + BO-MCP 或 Gryffin + Chimera。")
    from .space import normalize_constraints, feasible
    constraints = normalize_constraints(project.get("constraints", []), parameters)
    enhanced = task == "classification" or mode == "pareto" or constraints or project.get("candidates") or any("step" in p for p in parameters)
    if enhanced and engine != "bo-mcp":
        raise ValueError("步长、候选表、配方约束、Pareto 和分类任务请明确选择 BO-MCP / BoTorch 引擎执行。")
    rows = {}
    for key in ("observations", "pending"):
        raw_rows = project.get(key, [])
        if not isinstance(raw_rows, list):
            raise ValueError(f"{key} 必须是记录列表。")
        rows[key] = [_row(row, parameters, objectives if key == "observations" else [], f"{key} 第 {i} 行", classification["labels"] if classification and key == "observations" else None) for i, row in enumerate(raw_rows, 1)]
    raw_candidates = project.get("candidates", [])
    if not isinstance(raw_candidates, list):
        raise ValueError("候选表必须是参数记录列表。")
    if len(raw_candidates) > 200000:
        raise ValueError("候选表超过 200000 行，请缩小候选范围。")
    candidates = [_row(row, parameters, [], f"候选表第 {i} 行") for i, row in enumerate(raw_candidates, 1)]
    seen = set()
    for row in candidates:
        fingerprint = tuple(row[p["name"]] for p in parameters)
        if fingerprint in seen:
            raise ValueError("候选表包含重复条件，请先去除重复记录。")
        seen.add(fingerprint)
    continuous = [p for p in parameters if p["type"] == "continuous"]
    if continuous and len(candidates) > 1:
        groups = {}
        exact_parameters = [p for p in parameters if p["type"] != "continuous"]
        for row in candidates:
            groups.setdefault(tuple(row[p["name"]] for p in exact_parameters), []).append(row)
        for group in groups.values():
            if len(group) < 2:
                continue
            axis = max(continuous, key=lambda p: (max(row[p["name"]] for row in group) - min(row[p["name"]] for row in group)) / (p["high"] - p["low"]))
            ordered = sorted(group, key=lambda row: row[axis["name"]])
            tolerance = (axis["high"] - axis["low"]) * _NEAR_FRACTION
            start = 0
            for index, row in enumerate(ordered):
                while row[axis["name"]] - ordered[start][axis["name"]] > tolerance:
                    start += 1
                if any(_same(row, ordered[other], parameters) for other in range(start, index)):
                    raise ValueError("候选表包含重复或过于接近的条件（连续变量阈值为范围的 1e-6），请合并后导入。")
    context = {"parameters": parameters, "constraints": constraints}
    for key, records in [*rows.items(), ("candidates", candidates)]:
        for i, row in enumerate(records, 1):
            if not feasible(row, context):
                raise ValueError(f"{key} 第 {i} 行不满足配方约束。")
    if candidates:
        candidate_keys = {tuple(row[p["name"]] for p in parameters) for row in candidates}
        for row in rows["pending"]:
            if tuple(row[p["name"]] for p in parameters) not in candidate_keys:
                raise ValueError("待实验条件不在当前允许的候选表中。")
    blocked = list(rows["observations"])
    for i, pending in enumerate(rows["pending"], 1):
        if any(_same(pending, other, parameters) for other in blocked):
            raise ValueError(f"待做实验第 {i} 行与已测或其他待做实验重复/过于接近，请移除重复记录。")
        blocked.append(pending)
    return {
        **copy.deepcopy(project),
        "name": _name(project.get("name", "未命名实验"), "项目名称"),
        "engine": engine,
        "task": task,
        "objective_mode": mode,
        "constraints": constraints,
        "candidates": candidates,
        **({"classification": classification} if classification else {}),
        "seed": _integer(project.get("seed", 42), "随机种子", 0, 2**31 - 1),
        "batch_size": _integer(project.get("batch_size", 1), "批量大小", 1, 24),
        "parameters": parameters,
        "objectives": objectives,
        **rows,
    }



def reconcile_project(project: dict) -> dict:
    """Normalize a measurement update, removing only completed pending points.

    Invalid/partial rows still fail. Unmatched pending points remain queued, and
    duplicate pending points which have not been measured still fail validation.
    """
    if not isinstance(project, dict):
        raise ValueError("项目必须是对象。")
    pending = project.get("pending", [])
    if not isinstance(pending, list):
        raise ValueError("pending 必须是记录列表。")
    normalized = validate_project({**project, "pending": []})
    queued = [_row(row, normalized["parameters"], [], f"pending 第 {i} 行") for i, row in enumerate(pending, 1)]
    normalized["pending"] = [row for row in queued if not any(_same(row, measured, normalized["parameters"]) for measured in normalized["observations"])]
    return validate_project(normalized)


def read_observations(project: dict, csv_path: str | Path, sheet_name: str | None = None) -> list[dict]:
    """Read complete measured rows from UTF-8 CSV, XLS or XLSX without imputation."""
    from .table_io import read_table
    project = validate_project(project)
    columns, records = read_table(csv_path, sheet_name=sheet_name)
    expected = {p["name"] for p in project["parameters"]} | {o["name"] for o in project["objectives"]}
    if set(columns) != expected:
        raise ValueError(f"结果表列名必须恰好是：{', '.join(sorted(expected))}。")
    labels = project.get("classification", {}).get("labels") if project["task"] == "classification" else None
    result = [_row(row, project["parameters"], project["objectives"], f"结果表第 {i} 行", labels) for i, row in enumerate(records, 2)]
    # Validate each imported measurement's domain without changing its order or pending.
    validate_project({**project, "observations": result, "pending": []})
    return result


def read_candidates(project: dict, path: str | Path, sheet_name: str | None = None) -> list[dict]:
    """Read an explicit allowed candidate domain; measurements are a separate table."""
    from .table_io import read_table
    project = validate_project(project)
    columns, records = read_table(path, sheet_name=sheet_name)
    expected = {p["name"] for p in project["parameters"]}
    if set(columns) != expected:
        raise ValueError(f"候选表只包含参数列：{', '.join(sorted(expected))}。")
    result = [_row(row, project["parameters"], [], f"候选表第 {i} 行") for i, row in enumerate(records, 2)]
    if not result:
        raise ValueError("候选表没有数据行。")
    return validate_project({**project, "candidates": result, "pending": []})["candidates"]


def _finite_size(parameters: list[dict]) -> int | None:
    if any(p["type"] == "continuous" for p in parameters):
        return None
    return math.prod(len(p["options"]) if p["type"] == "categorical" else p["high"] - p["low"] + 1 for p in parameters)


def _gryffin(project: dict, blocked: list[dict], count: int, seed: int) -> list[dict]:
    from gryffin import Gryffin
    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    parameters = []
    for p in project["parameters"]:
        if p["type"] == "categorical":
            parameters.append({"name": p["name"], "type": p["type"], "category_details": dict.fromkeys(p["options"])})
        else:
            parameters.append({key: value for key, value in p.items() if key != "unit"})
    excluded = list(blocked)
    available = lambda candidate: not any(_same(candidate, row, project["parameters"]) for row in excluded)
    config = {
        "general": {"num_cpus": 1, "random_seed": seed, "verbosity": 1, "auto_desc_gen": False,
                    "save_database": False, "batches": count, "sampling_strategies": 1},
        "parameters": parameters,
        "objectives": [{**o, "absolute": False} for o in project["objectives"]],
    }
    size = _finite_size(project["parameters"])
    unique_blocked = {tuple(row[p["name"]] for p in project["parameters"]) for row in blocked}
    fraction = 1.0 if size is None else max(1 / size, (size - len(unique_blocked)) / size)
    if size is not None:
        config["general"]["reject_tol"] = max(1000, size * 10)
    planner = Gryffin(config_dict=config, known_constraints=available, frac_feas=fraction)
    # Gryffin's own initial design is random when there are no observations.
    # This is native behavior, never a substitute for a failing trained model.
    if not project["observations"]:
        result = []
        for _ in range(count):
            sample = planner.recommend([], sampling_strategies=[0.0], num_batches=1)[0]
            result.append(sample)
            excluded.append(sample)
        return result
    return planner.recommend(project["observations"], sampling_strategies=[0.0], num_batches=count)


def _atlas(project: dict, blocked: list[dict], count: int, seed: int) -> list[dict]:
    from atlas.planners.gp.planner import GPPlanner
    from olympus import Campaign, ParameterContinuous, ParameterDiscrete, ParameterCategorical, ParameterVector
    from olympus.campaigns import ParameterSpace
    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    space = ParameterSpace()
    for p in project["parameters"]:
        if p["type"] == "continuous":
            parameter = ParameterContinuous(name=p["name"], low=p["low"], high=p["high"])
        elif p["type"] == "discrete":
            parameter = ParameterDiscrete(name=p["name"], options=list(range(p["low"], p["high"] + 1)))
        else:
            parameter = ParameterCategorical(name=p["name"], options=p["options"])
        space.add(parameter)
    campaign = Campaign()
    campaign.set_param_space(space)
    for row in project["observations"]:
        vector = ParameterVector().from_dict({p["name"]: row[p["name"]] for p in project["parameters"]}, param_space=space)
        campaign.add_observation(vector, [row[project["objectives"][0]["name"]]])
    names = [p["name"] for p in project["parameters"]]
    excluded = list(blocked)
    def available(values):
        candidate = dict(zip(names, values))
        return not any(_same(candidate, row, project["parameters"]) for row in excluded)
    # The upstream gradient path drops the KnownConstraints container during
    # continuous optimization and may return an already measured boundary point.
    # Use Atlas's native Pymoo optimizer for every space so ask/tell exclusions
    # apply to single requests as well as mixed variables and batches.
    planner = GPPlanner(goal={"min": "minimize", "max": "maximize"}[project["objectives"][0]["goal"]],
                        batch_size=count, random_seed=seed, num_init_design=5,
                        init_design_strategy="random", acquisition_optimizer_kind="pymoo", known_constraints=[available])
    planner.set_param_space(space)
    result = []
    for _ in range(count):
        planner.batch_size = count - len(result)
        if len(project["observations"]) < 5:
            # Upstream initial_design otherwise emits all remaining design points
            # when the remaining design size is not divisible by batch_size.
            planner.batch_size = min(planner.batch_size, 5 - len(project["observations"]))
            planner.num_init_design = len(project["observations"]) + planner.batch_size
        samples = [sample.to_dict() for sample in planner.recommend(campaign.observations)]
        fresh = [sample for sample in samples if not any(_same(sample, row, project["parameters"]) for row in excluded)]
        if not fresh:
            break
        for sample in fresh:
            if not any(_same(sample, row, project["parameters"]) for row in excluded):
                result.append(sample)
                excluded.append(sample)
                if len(result) == count:
                    return result
    return result


def recommend(project: dict) -> list[dict]:
    """Ask the selected real planner; raise on failure, exhausted space or repeats.

    Returns exactly batch_size fresh parameter-only rows. No random recovery,
    imputed objectives or measured/pending mutation is performed by this API.
    """
    project = validate_project(project)
    if project["engine"] == "bo-mcp":
        raise RuntimeError("BO-MCP 必须由独立的 Python 3.13 现代 worker 执行；不能在此经典优化器环境中运行。")
    blocked = project["observations"] + project["pending"]
    size = _finite_size(project["parameters"])
    if size is not None:
        unique = {tuple(row[p["name"]] for p in project["parameters"]) for row in blocked}
        remaining = size - len(unique)
        if remaining < project["batch_size"]:
            raise ValueError(f"离散搜索空间只剩 {remaining} 个未做且未排队的条件，少于请求的 {project['batch_size']} 个；请缩小批量或扩展范围。")
        # Both selected upstream interfaces materialize finite Cartesian grids.
        if size > 200000:
            raise ValueError("离散组合超过 200000 个，当前桌面接口暂不展开此规模；请缩小搜索范围。")
    if project["engine"] == "atlas":
        discrete_choices = math.prod(len(p["options"]) if p["type"] == "categorical" else p["high"] - p["low"] + 1 for p in project["parameters"] if p["type"] != "continuous")
        if discrete_choices > 200000:
            raise ValueError("Atlas 混合域的离散组合超过 200000 个，请缩小搜索范围。")
    backend = _gryffin if project["engine"] == "gryffin" else _atlas
    selected = []
    for attempt in range(4):
        seed = (project["seed"] + attempt) % (2**31)
        raw = backend(project, blocked + selected, project["batch_size"] - len(selected), seed)
        for candidate in raw:
            # Convert backend scalar types before applying the same input contract.
            candidate = {p["name"]: str(candidate[p["name"]]) if p["type"] == "categorical" else float(candidate[p["name"]]) for p in project["parameters"]}
            candidate = _row(candidate, project["parameters"], [], "算法推荐")
            if not any(_same(candidate, row, project["parameters"]) for row in blocked + selected):
                selected.append(candidate)
            if len(selected) == project["batch_size"]:
                return selected
    raise RuntimeError(f"{project['engine']} 未能给出足够的不重复条件。尚未保存部分批次；请调整批量大小、种子或搜索范围。")
