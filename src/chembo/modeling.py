"""Fixed modern planners, posterior predictions and honest validation for NaNoBO.

Candidates are feasible original-unit recipes. The model ranks that domain;
recommendations are never rounded or normalized after acquisition optimization.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np


def _encode(rows, parameters):
    """Stable numeric scaling and complete one-hot encoding of declared categories."""
    width = sum(len(p["options"]) if p["type"] == "categorical" else 1 for p in parameters)
    matrix = np.empty((len(rows), width), dtype=float)
    for i, row in enumerate(rows):
        values = []
        for p in parameters:
            if p["type"] == "categorical":
                values.extend(float(row[p["name"]] == option) for option in p["options"])
            else:
                values.append((float(row[p["name"]]) - p["low"]) / (p["high"] - p["low"]))
        matrix[i] = values
    return matrix


def _signs(objectives):
    return np.array([1.0 if o["goal"] == "max" else -1.0 for o in objectives])


def _fit_gp(x, y, seed):
    import torch
    from botorch.fit import fit_gpytorch_mll
    from botorch.models import ModelListGP, SingleTaskGP
    from gpytorch.mlls import ExactMarginalLogLikelihood, SumMarginalLogLikelihood

    torch.manual_seed(seed)
    x = torch.as_tensor(x, dtype=torch.double)
    y = torch.as_tensor(y, dtype=torch.double)
    if y.shape[-1] == 1:
        model = SingleTaskGP(x, y)
        mll = ExactMarginalLogLikelihood(model.likelihood, model)
    else:
        model = ModelListGP(*(SingleTaskGP(x, y[:, i:i + 1]) for i in range(y.shape[-1])))
        mll = SumMarginalLogLikelihood(model.likelihood, model)
    fit_gpytorch_mll(mll, optimizer_kwargs={"options": {"maxiter": 100}})
    model.eval()
    return model


def _posterior(model, x, signs):
    import torch
    if len(x) == 0:
        return np.empty((0, len(signs))), np.empty((0, len(signs)))
    with torch.no_grad():
        posterior = model.posterior(torch.as_tensor(x, dtype=torch.double))
        mean = posterior.mean.detach().cpu().numpy() * signs
        std = posterior.variance.clamp_min(0).sqrt().detach().cpu().numpy()
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise RuntimeError("高斯过程返回非有限预测；未保存本次建议。")
    return mean, std


def _class_model(x, labels, seed):
    from sklearn.gaussian_process import GaussianProcessClassifier
    from sklearn.gaussian_process.kernels import ConstantKernel, RBF
    kernel = ConstantKernel(1.0, (0.01, 100.0)) * RBF(np.ones(x.shape[1]), (0.01, 100.0))
    return GaussianProcessClassifier(kernel=kernel, random_state=seed, max_iter_predict=100).fit(x, labels)


def _initial_indices(x, observed_x, count):
    """Maximin initial design in the supplied feasible candidate pool."""
    if count > len(x):
        raise ValueError(f"合法且未做的候选只剩 {len(x)} 个，少于请求的 {count} 个。")
    selected, anchors = [], np.array(observed_x, dtype=float, copy=True)
    for _ in range(count):
        if len(anchors):
            distance = ((x[:, None, :] - anchors[None, :, :]) ** 2).sum(axis=2).min(axis=1)
        else:
            distance = -((x - 0.5) ** 2).sum(axis=1)
        distance[selected] = -np.inf
        index = int(np.argmax(distance))
        selected.append(index)
        anchors = np.vstack((anchors, x[index]))
    return selected


def _reference(project, signed_y):
    objectives = project["objectives"]
    signs = _signs(objectives)
    provided = project.get("reference_point")
    if provided is not None:
        from chembo.engine import _number
        if not isinstance(provided, dict) or set(provided) != {o["name"] for o in objectives}:
            raise ValueError("Pareto 参考点必须为每个目标提供一个原单位数值。")
        values = np.array([_number(provided[o["name"]], "Pareto 参考点") for o in objectives])
        if not np.isfinite(values).all():
            raise ValueError("Pareto 参考点必须为有限数字。")
        return values * signs, dict(zip([o["name"] for o in objectives], values.tolist())), "用户给定；同一参考点用于整个历史曲线。"
    worst, spread = signed_y.min(axis=0), np.ptp(signed_y, axis=0)
    margin = np.maximum(spread * 0.1, np.maximum(np.abs(worst) * 0.01, 1e-6))
    reference = worst - margin
    return reference, dict(zip([o["name"] for o in objectives], (reference * signs).tolist())), "本次全部已测目标的最差值外加余量；本图历史统一用此点。自动参考点跨分析可能变化，跨轮比较请固定参考点。"


def _pareto(project, signed_y):
    import torch
    from botorch.utils.multi_objective.hypervolume import Hypervolume
    from botorch.utils.multi_objective.pareto import is_non_dominated

    if len(signed_y) == 0:
        return {"indices": [], "rows": [], "reference_point": {}, "reference_rule": "尚无实测结果。", "hypervolume_history": []}
    reference, original_reference, rule = _reference(project, signed_y)
    y = torch.as_tensor(signed_y, dtype=torch.double)
    ref = torch.as_tensor(reference, dtype=torch.double)
    mask = is_non_dominated(y)
    indices = mask.nonzero().flatten().tolist()
    hv = Hypervolume(ref)
    history = [{"index": i, "value": float(hv.compute(y[:i][is_non_dominated(y[:i])]))} for i in range(1, len(y) + 1)]
    return {"indices": indices, "rows": [project["observations"][i] for i in indices],
            "reference_point": original_reference, "reference_rule": rule, "hypervolume_history": history}


def _acquisition(model, project, x_train, signed_y, pending, seed):
    import torch
    from botorch.acquisition.logei import qLogExpectedImprovement
    from botorch.acquisition.multi_objective.logei import qLogNoisyExpectedHypervolumeImprovement
    from botorch.sampling.normal import SobolQMCNormalSampler

    sampler = SobolQMCNormalSampler(torch.Size([64]), seed=seed)
    kw = {"model": model, "sampler": sampler,
          "X_pending": torch.as_tensor(pending, dtype=torch.double) if len(pending) else None}
    if len(project["objectives"]) == 1:
        return qLogExpectedImprovement(best_f=float(signed_y.max()), **kw)
    reference, _, _ = _reference(project, signed_y)
    return qLogNoisyExpectedHypervolumeImprovement(ref_point=reference.tolist(),
                                                  X_baseline=torch.as_tensor(x_train, dtype=torch.double),
                                                  prune_baseline=False, **kw)


def _scores(acquisition, x):
    import torch
    pieces = []
    with torch.no_grad():
        for start in range(0, len(x), 128):
            scores = acquisition(torch.as_tensor(x[start:start + 128], dtype=torch.double).unsqueeze(-2))
            pieces.append(scores.detach().cpu().numpy().reshape(-1))
    result = np.concatenate(pieces) if pieces else np.empty(0)
    if not np.isfinite(result).all():
        raise RuntimeError("采集函数返回非有限分值；请检查数据或搜索空间。")
    return result


def _diagnostics(project, x, signed_y, labels=None):
    """Retrain the actual fixed model on each fold; never substitute a generic GP."""
    observations, objectives = project["observations"], project["objectives"]
    n = len(observations)
    result = {"method": "LOOCV", "status": "not_requested", "evaluated": 0, "total": n, "rows": [], "metrics": {}}
    if not project.get("_diagnostics", project.get("_operation") == "analyze"):
        return result
    if n < 3:
        result.update(status="insufficient_data", note="至少三条实测记录才能进行留一验证。")
        return result
    indices = np.unique(np.linspace(0, n - 1, min(n, 30), dtype=int))
    if n > 30:
        result["note"] = f"为控制计算时间，对 {n} 条记录中均匀选出的 30 条做留一预测；每折训练仍使用其余全部记录。"
    classification = project.get("task") == "classification"
    for index in indices:
        train = np.arange(n) != index
        if classification:
            if len(set(np.asarray(labels)[train])) < 2:
                continue
            model = _class_model(x[train], np.asarray(labels)[train], project["seed"])
            prediction = str(model.predict(x[index:index + 1])[0])
            row = {"index": int(index), "actual": {objectives[0]["name"]: str(labels[index])},
                   "predicted": {objectives[0]["name"]: prediction}}
        else:
            model = _fit_gp(x[train], signed_y[train], project["seed"])
            mean, std = _posterior(model, x[index:index + 1], _signs(objectives))
            row = {"index": int(index), "actual": {o["name"]: observations[index][o["name"]] for o in objectives},
                   "predicted": {o["name"]: float(mean[0, j]) for j, o in enumerate(objectives)},
                   "std": {o["name"]: float(std[0, j]) for j, o in enumerate(objectives)}}
        result["rows"].append(row)
    result["evaluated"] = len(result["rows"])
    result["status"] = "computed" if result["rows"] else "insufficient_data"
    if classification:
        from sklearn.metrics import accuracy_score, confusion_matrix
        name = objectives[0]["name"]
        actual = [row["actual"][name] for row in result["rows"]]
        predicted = [row["predicted"][name] for row in result["rows"]]
        declared = project["classification"]["labels"]
        if actual:
            result["metrics"][name] = {"accuracy": float(accuracy_score(actual, predicted)), "n": len(actual)}
            result["confusion"] = {"labels": declared, "matrix": confusion_matrix(actual, predicted, labels=declared).tolist()}
        if len(result["rows"]) < len(indices):
            result["note"] = (result.get("note", "") + " 部分留一折只剩一个训练类别，已跳过并计入 evaluated/total。").strip()
    else:
        for o in objectives:
            actual = np.array([row["actual"][o["name"]] for row in result["rows"]], dtype=float)
            predicted = np.array([row["predicted"][o["name"]] for row in result["rows"]], dtype=float)
            difference = actual - predicted
            denominator = float(((actual - actual.mean()) ** 2).sum())
            result["metrics"][o["name"]] = {"rmse": float(np.sqrt(np.mean(difference ** 2))),
                                                "mae": float(np.mean(np.abs(difference))),
                                                "r2": 1 - float((difference ** 2).sum()) / denominator if denominator > 0 else None,
                                                "n": len(actual)}
    return result


def plan(project):
    """Modern recommendation or analysis request with fixed, source-identifiable models."""
    import torch
    from chembo.engine import validate_project
    from chembo.space import candidate_pool, pool_metadata

    project = validate_project(project)
    if project["engine"] != "bo-mcp":
        raise ValueError("此分析接口仅用于 BoTorch / 分类任务；经典引擎应走其原生分析接口。")
    operation = project.get("_operation", "recommend")
    if operation not in ("recommend", "analyze"):
        raise ValueError("未知计算操作。")
    if not isinstance(project.get("_diagnostics", False), bool):
        raise ValueError("诊断选项必须为布尔值。")
    torch.set_num_threads(1)
    torch.manual_seed(project["seed"])
    np.random.seed(project["seed"])
    parameters, objectives = project["parameters"], project["objectives"]
    observations = project["observations"]
    classification = project.get("task", "optimization") == "classification"
    pool = candidate_pool(project, limit=4096)
    count = project["batch_size"] if operation == "recommend" else 0
    if count > len(pool):
        raise ValueError(f"合法且未做的候选只剩 {len(pool)} 个，少于请求的 {count} 个。")
    x_train, x_pool = _encode(observations, parameters), _encode(pool, parameters)
    x_pending = _encode(project["pending"], parameters)
    warnings_out = []
    search = pool_metadata(project, limit=4096)
    if "sample" in str(search.get("strategy", "")):
        warnings_out.append("候选排序基于本次确定性生成/抽取的合法候选子集，不代表整个连续域或完整候选表的全局最优。")
    model_name = "GaussianProcessClassifier" if classification else "BoTorch ModelListGP + qLogNEHVI" if len(objectives) > 1 else "BoTorch SingleTaskGP + qLogEI"
    analysis = {"task": "classification" if classification else "optimization", "engine": "bo-mcp", "model": model_name,
                "status": "initial_design", "predictions": [], "warnings": warnings_out, "search_space": search}
    signed_y = None
    if classification:
        labels = [str(row[objectives[0]["name"]]) for row in observations]
        classes = sorted(set(labels))
        trained = len(classes) >= 2
        analysis["label_counts"] = {label: labels.count(label) for label in project["classification"]["labels"]}
        if trained:
            model = _class_model(x_train, labels, project["seed"])
            probabilities = model.predict_proba(x_pool) if len(x_pool) else np.empty((0, len(model.classes_)))
            scores = -(probabilities * np.log(np.clip(probabilities, 1e-15, 1))).sum(axis=1)
            selected = np.argsort(-scores, kind="stable")[:count].tolist()
            for i, (row, proba, score) in enumerate(zip(pool, probabilities, scores)):
                analysis["predictions"].append({"parameters": row, "probabilities": {str(label): float(value) for label, value in zip(model.classes_, proba)},
                                                "predicted_label": str(model.classes_[int(np.argmax(proba))]), "entropy": float(score), "score": float(score), "selected": i in selected})
            missing = [label for label in project["classification"]["labels"] if label not in classes]
            if missing:
                warnings_out.append("尚未观察到类别 " + "、".join(missing) + "；预测概率仅在已观察类别之间归一化，不能解释为未见类别的概率。")
            analysis["status"], analysis["score_label"] = "trained", "entropy"
        else:
            selected = _initial_indices(x_pool, np.vstack((x_train, x_pending)), count)
            analysis["score_label"] = "maximin_initial_design"
            warnings_out.append("尚未观察到两个类别，当前执行合法候选域中的分散初始设计，不提供分类概率。")
        analysis["diagnostics"] = _diagnostics(project, x_train, None, labels)
    else:
        signs = _signs(objectives)
        actual_y = np.array([[row[o["name"]] for o in objectives] for row in observations], dtype=float).reshape(-1, len(objectives))
        signed_y = actual_y * signs
        trained = len(observations) >= 2
        if len(objectives) > 1:
            analysis["pareto"] = _pareto(project, signed_y)
        if trained:
            model = _fit_gp(x_train, signed_y, project["seed"])
            mean, std = _posterior(model, x_pool, signs)
            acquisition = _acquisition(model, project, x_train, signed_y, x_pending, project["seed"])
            scores = _scores(acquisition, x_pool)
            table_scores = scores.copy()
            selected = []
            for _ in range(count):
                choose = scores.copy()
                choose[selected] = -np.inf
                selected.append(int(np.argmax(choose)))
                if len(selected) < count:
                    pending = np.vstack((x_pending, x_pool[selected]))
                    acquisition = _acquisition(model, project, x_train, signed_y, pending, project["seed"])
                    scores = _scores(acquisition, x_pool)
            for i, row in enumerate(pool):
                analysis["predictions"].append({"parameters": row, "mean": {o["name"]: float(mean[i, j]) for j, o in enumerate(objectives)},
                                                "std": {o["name"]: float(std[i, j]) for j, o in enumerate(objectives)},
                                                "score": float(table_scores[i]), "selected": i in selected})
            analysis["status"] = "trained"
            analysis["score_label"] = "logNEHVI" if len(objectives) > 1 else "logEI"
            analysis["score_rule"] = "表中为考虑现有待实验条件的首轮单点采集分值；批内依次将新选择点加入 X_pending 后重新评分，推荐顺序可能不同于首轮排名。"
        else:
            selected = _initial_indices(x_pool, np.vstack((x_train, x_pending)), count)
            analysis["score_label"] = "maximin_initial_design"
            warnings_out.append("少于两条实测结果，当前执行合法候选域中的分散初始设计，不提供后验预测。")
        analysis["diagnostics"] = _diagnostics(project, x_train, signed_y)
    analysis["predictions"].sort(key=lambda row: row["score"], reverse=True)
    recommendations = [pool[i] for i in selected]
    for rank, row in enumerate(analysis["predictions"], 1):
        row["rank"] = rank
    signature = hashlib.sha256(json.dumps({key: project.get(key) for key in
                                           ("task", "objective_mode", "parameters", "objectives", "seed", "constraints", "candidates", "classification")},
                                          ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
    payload = {"ok": True, "recommendations": recommendations, "analysis": analysis, "warnings": warnings_out,
               "provenance": {"engine": "nanobo-botorch-v2", "model": model_name, "candidate_count": len(pool), "operation": operation,
                              "acquisition": analysis["score_label"], "generation_method": "model" if analysis["status"] == "trained" else "initial_design"},
               "backend_state": {"engine": "nanobo-botorch-v2", "state_version": 2, "spec_signature": signature}}
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return payload
