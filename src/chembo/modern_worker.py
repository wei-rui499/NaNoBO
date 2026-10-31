"""Native Python 3.13 process for the pinned BO-MCP/BoTorch engine."""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import sys
import traceback
from importlib.metadata import version
from pathlib import Path

UPSTREAM_COMMIT = "56d590b91ac120d0f22a3e41e770843d271808cd"


def _uses_modeling_v2(project):
    operation = project.get("_operation", "recommend")
    if operation not in ("recommend", "analyze"):
        raise ValueError("未知计算操作。")
    return (project.get("_modeling_v2") or operation == "analyze"
            or project.get("task") == "classification" or project.get("objective_mode") == "pareto"
            or project.get("constraints") or project.get("candidates")
            or any("step" in parameter for parameter in project.get("parameters", [])))


def recommend_modern(project: dict) -> dict:
    from chembo.engine import _finite_size, _integer, _row, _same, validate_project
    from bo_engine.botorch_backend import BoTorchBackend
    from bo_engine.types import ObjectiveSpec, ObservationData, OptimizationSpec, ParameterSpec, ParameterType
    import torch

    project = validate_project(project)
    if project["engine"] != "bo-mcp":
        raise ValueError("现代 worker 只执行 BO-MCP 项目。")
    if _uses_modeling_v2(project):
        from chembo.modeling import plan
        return plan(project)
    torch.set_num_threads(1)
    torch.manual_seed(project["seed"])
    params = project["parameters"]
    blocked = project["observations"] + project["pending"]
    size = _finite_size(params)
    if size is not None:
        remaining = size - len({tuple(row[p["name"]] for p in params) for row in blocked})
        if remaining < project["batch_size"]:
            raise ValueError(f"离散搜索空间只剩 {remaining} 个未做且未排队的条件，少于请求批量。")
    parameters = []
    for p in params:
        if p["type"] == "continuous":
            parameter = ParameterSpec(name=p["name"], type=ParameterType.CONTINUOUS,
                                      bounds=(p["low"], p["high"]))
        elif p["type"] == "discrete":
            parameter = ParameterSpec(name=p["name"], type=ParameterType.DISCRETE,
                                      values=list(range(p["low"], p["high"] + 1)))
        else:
            parameter = ParameterSpec(name=p["name"], type=ParameterType.CATEGORICAL,
                                      categories=p["options"])
        parameters.append(parameter)
    spec = OptimizationSpec(
        parameters=parameters,
        objectives=[ObjectiveSpec(name=o["name"], minimize=o["goal"] == "min") for o in project["objectives"]],
        batch_size=project["batch_size"],
        random_seed=project["seed"],
    )
    backend = BoTorchBackend()
    capabilities = backend.validate_capabilities(spec)
    if not capabilities.is_compatible:
        raise ValueError(f"BO-MCP 不支持此问题配置：{capabilities}")
    observations = [ObservationData(
        parameter_values={p["name"]: row[p["name"]] for p in params},
        objective_values={o["name"]: row[o["name"]] for o in project["objectives"]},
    ) for row in project["observations"]]

    signature = hashlib.sha256(json.dumps(
        {k: project[k] for k in ("parameters", "objectives", "seed")},
        sort_keys=True, ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()
    state = project.get("backend_state") or {}
    if state and (not isinstance(state, dict) or state.get("engine") != "bo-mcp" or state.get("state_version") != 1):
        raise ValueError("BO-MCP 状态格式不匹配；请清空该项目的引擎状态后重新生成。")
    if state and state.get("spec_signature") != signature:
        raise ValueError("参数、目标或种子与 BO-MCP 历史状态不匹配，请清空引擎状态后重新生成。")
    iteration = _integer(state.get("iteration", 0), "BO-MCP 迭代编号", 0, 2**31 - 2) + 1
    initial_history = state.get("initial_history", [])
    if not isinstance(initial_history, list):
        raise ValueError("BO-MCP 初始设计历史必须是列表。")
    initial_history = [_row(row, params, [], "BO-MCP 初始设计历史") for row in initial_history]
    batch = backend.generate_suggestions(
        spec=spec,
        observations=observations,
        batch_size=project["batch_size"],
        iteration=iteration,
        backend_state=state.get("engine_state"),
        pending_points=project["pending"],
        initial_design_history=initial_history,
    )
    selected = []
    per_point = []
    for suggestion in batch.suggestions:
        candidate = _row(suggestion["parameter_values"], params, [], "BO-MCP 推荐")
        if any(_same(candidate, row, params) for row in blocked + selected):
            raise RuntimeError("BO-MCP 返回已测、待做或批内重复的条件；本批次没有保存。")
        selected.append(candidate)
        provenance = suggestion["provenance"]
        per_point.append(provenance)
        if provenance.get("generation_method") == "initial_design":
            initial_history.append(candidate)
    if len(selected) != project["batch_size"]:
        raise RuntimeError(f"BO-MCP 只返回 {len(selected)} 个条件，少于请求批量；本批次没有保存。")
    payload = {
        "ok": True,
        "recommendations": selected,
        "provenance": {
            "engine": "bo-mcp", "upstream_commit": UPSTREAM_COMMIT,
            "package_version": version("bo-engine"),
            "method_info": batch.method_info, "suggestions": per_point,
        },
        "backend_state": {
            "engine": "bo-mcp", "state_version": 1, "spec_signature": signature,
            "engine_state": batch.backend_state, "initial_history": initial_history,
            "iteration": iteration,
        },
        "warnings": batch.warnings,
    }
    # Reject accidental NaN or backend tensor leakage before writing a success result.
    json.dumps(payload, allow_nan=False)
    return payload


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if len(args) != 2:
        print("Usage: chembo-modern-worker request.json result.json", file=sys.stderr)
        return 2
    request, result = [Path(arg).resolve() for arg in args]
    try:
        project = json.loads(request.read_text(encoding="utf-8"))
        if _uses_modeling_v2(project):
            from chembo.modeling import plan
            payload = plan(project)
        else:
            payload = recommend_modern(project)
    except Exception as exc:
        traceback.print_exc()
        payload = {"ok": False, "error": str(exc) or type(exc).__name__}
    result.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
