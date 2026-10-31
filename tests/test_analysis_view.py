"""Synthetic results exercise chart truthfulness, inspection and portable exports."""
import csv
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import typing_extensions  # Match the Python 3.10 frozen runtime before Qt imports.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import numpy as np
import pytest

from chembo.analysis_view import AnalysisView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    result = AnalysisView()
    result.resize(1120, 790)
    yield result
    # Flush matplotlib's queued draw before Qt deletes each test widget.
    app.processEvents()
    result.close()
    app.processEvents()


def synthetic_optimization():
    """Deliberately synthetic, including a pending row with extreme fake values."""
    project = {
        "name": "Synthetic display verification", "task": "optimization",
        "parameters": [{"name": "dose", "type": "continuous", "low": 0, "high": 10}],
        "objectives": [{"name": "yield", "goal": "max"}, {"name": "cost", "goal": "min"},
                       {"name": "selectivity", "goal": "max"}],
        "observations": [
            {"dose": 1, "yield": 2, "cost": 6, "selectivity": .4},
            {"dose": 2, "yield": 4, "cost": 4, "selectivity": .6},
            {"dose": 3, "yield": 5, "cost": 3, "selectivity": .5},
            {"dose": 4, "yield": 3, "cost": 5, "selectivity": .3}],
        "pending": [{"dose": 5, "yield": 999, "cost": 999, "selectivity": 999}],
    }
    analysis = {
        "task": "optimization", "engine": "bo-mcp", "model": "Synthetic display fixture GP",
        "status": "trained", "warnings": [], "score_label": "logNEHVI",
        "score_rule": "Synthetic acquisition scores are first-step values.",
        "predictions": [
            {"parameters": {"dose": 5}, "mean": {"yield": 10, "cost": 2, "selectivity": .6},
             "std": {"yield": 1, "cost": .4, "selectivity": .1}, "score": .1, "selected": False},
            {"parameters": {"dose": 6}, "mean": {"yield": 2, "cost": 3, "selectivity": .8},
             "std": {"yield": .2, "cost": .3, "selectivity": .1}, "score": .9, "selected": True},
            {"parameters": {"dose": 7}, "mean": {"yield": 100, "cost": 4, "selectivity": .9},
             "std": {"yield": 2, "cost": .5, "selectivity": .05}, "score": .2, "selected": False}],
        "diagnostics": {"method": "LOOCV", "status": "computed", "evaluated": 4, "total": 4,
            "rows": [{"index": i, "actual": {k: row[k] for k in ("yield", "cost", "selectivity")},
                      "predicted": {k: row[k] + .1 for k in ("yield", "cost", "selectivity")},
                      "std": {"yield": .2, "cost": .3, "selectivity": .05}}
                     for i, row in enumerate(project["observations"])],
            "metrics": {k: {"rmse": .1, "mae": .1, "r2": .98, "n": 4}
                        for k in ("yield", "cost", "selectivity")}},
        "pareto": {"indices": [1, 2], "rows": project["observations"][1:3],
            "reference_point": {"yield": 1, "cost": 7, "selectivity": .2},
            "reference_rule": "Synthetic fixed reference for display tests.",
            "hypervolume_history": [{"index": 1, "value": .1}, {"index": 2, "value": .3},
                                    {"index": 3, "value": .6}, {"index": 4, "value": .6}]},
    }
    return project, analysis


def synthetic_classification():
    labels = ["成功且得到目标形貌的样品", "失败且未得到目标形貌的样品", "需要进一步确认的中间样品"]
    project = {"name": "Synthetic classifier display fixture", "task": "classification",
               "parameters": [{"name": "dose"}], "objectives": [{"name": "outcome"}],
               "classification": {"labels": labels},
               "observations": [{"dose": i, "outcome": label} for i, label in enumerate(labels)],
               "pending": []}
    analysis = {"task": "classification", "status": "trained", "model": "Synthetic classifier",
                "score_label": "entropy", "predictions": [
                    {"parameters": {"dose": 4}, "probabilities": dict(zip(labels, [.6, .3, .1])),
                     "entropy": .89, "score": .89, "selected": True},
                    {"parameters": {"dose": 5}, "probabilities": dict(zip(labels, [.2, .3, .5])),
                     "entropy": 1.03, "score": 1.03, "selected": False}],
                "diagnostics": {"method": "LOOCV", "status": "computed",
                    "rows": [{"index": i, "actual": {"outcome": actual}, "predicted": {"outcome": predicted}}
                             for i, (actual, predicted) in enumerate(zip(labels, [labels[0], labels[1], labels[0]]))],
                    "metrics": {"outcome": {"accuracy": 2/3, "n": 3}},
                    "confusion": {"labels": labels, "matrix": [[1, 0, 0], [0, 1, 0], [1, 0, 0]]}}}
    return project, analysis


def test_empty_and_initial_design_do_not_invent_predictions(view):
    assert view.table.rowCount() == 0
    with pytest.raises(ValueError, match="没有可导出"):
        view.export_predictions("unused.csv")
    project, _ = synthetic_optimization()
    view.set_analysis({"task": "optimization", "status": "initial_design", "predictions": []}, project)
    assert view.table.rowCount() == 0
    assert len(view.prediction.figure.axes[0].collections) == 0
    assert "没有已拟合" in view.prediction.note.text()
    assert len(view.validation.figure.axes[0].collections) == 0
    view.clear()
    assert view.objective.count() == 0


def test_numeric_table_sorting_and_unrounded_csv(view, tmp_path):
    project, analysis = synthetic_optimization()
    view.set_analysis(analysis, project)
    column = view._columns.index("yield · 预测")
    view.table.sortItems(column, Qt.AscendingOrder)
    assert [float(view.table.item(i, column).text()) for i in range(3)] == [2, 10, 100]
    path = tmp_path / "predictions.csv"
    view.export_predictions(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert rows[0]["yield · 预测"] == "10"
    assert rows[1]["本批推荐"] == "是"
    assert "采集分值 · logNEHVI" in rows[0]
    analysis["predictions"][0]["mean"]["yield"] = -999
    assert view.analysis["predictions"][0]["mean"]["yield"] == 10


def test_validation_uncertainty_and_objective_switch(view):
    project, analysis = synthetic_optimization()
    # Partial standard deviations should retain the available uncertainty bar.
    del analysis["diagnostics"]["rows"][0]["std"]["yield"]
    analysis["diagnostics"]["note"] = "Synthetic partial validation: 4 of 40 observations."
    view.set_analysis(analysis, project)
    axis = view.validation.figure.axes[0]
    assert len(axis.containers) == 1
    assert "RMSE=0.1" in view.validation.note.text()
    assert "4 of 40" in view.validation.note.text()
    view.objective.setCurrentText("cost")
    assert "cost" in view.validation.figure.axes[0].get_title()
    view.validation.kind.setCurrentIndex(1)
    assert view.validation.figure.axes[0].get_ylabel() == "预测 − 实测"
    view.prediction.kind.setCurrentIndex(1)
    assert view.prediction.figure.axes[0].get_ylabel() == "模型标准差"


def test_pareto_uses_observed_only_and_history_indices_are_not_shifted(view):
    project, analysis = synthetic_optimization()
    view.set_analysis(analysis, project)
    axis = view.multi.figure.axes[0]
    assert sum(len(collection.get_offsets()) for collection in axis.collections) == 4
    assert max(float(x) for collection in axis.collections for x, y in collection.get_offsets()) < 999
    view.multi.kind.setCurrentIndex(1)
    assert view.multi.figure.axes[0].name == "3d"
    view.multi.kind.setCurrentIndex(2)
    assert list(view.multi.figure.axes[0].lines[0].get_xdata()) == [1, 2, 3, 4]
    assert "yield=1" in view.multi.note.text()
    assert "Synthetic fixed reference" in view.multi.note.text()
    view.multi.kind.setCurrentIndex(0)
    view.axes[1].setCurrentIndex(0)
    assert "请选择 2" in view.multi.note.text()


def test_observed_history_and_missing_distribution_values(view):
    project, analysis = synthetic_optimization()
    project["observations"].append({"dose": 8, "cost": 8, "selectivity": .1})
    view.set_analysis(analysis, project)
    view.variable.setCurrentText("yield")
    view.distribution.kind.setCurrentIndex(1)
    axis = view.distribution.figure.axes[0]
    assert list(axis.lines[0].get_ydata()) == [2, 4, 5, 5]
    assert "4 条完整" in view.distribution.note.text()


def test_classification_probabilities_and_genuine_holdout_confusion(view):
    project, analysis = synthetic_classification()
    view.set_analysis(analysis, project)
    assert len(view.classification.figure.axes[0].patches) == 6
    assert all(abs(sum(p["probabilities"].values()) - 1) < 1e-10 for p in analysis["predictions"])
    view.classification.kind.setCurrentIndex(1)
    assert len(view.classification.figure.axes[0].collections[0].get_offsets()) == 2
    view.classification.kind.setCurrentIndex(2)
    assert [patch.get_height() for patch in view.classification.figure.axes[0].patches] == [1, 1, 1]
    view.classification.kind.setCurrentIndex(3)
    assert np.array_equal(view.classification.figure.axes[0].images[0].get_array(), [[1, 0, 0], [0, 1, 0], [1, 0, 0]])
    assert "0.667" in view.classification.note.text()
    # A class absent from the fitted model remains missing, rather than a manufactured zero.
    for prediction in analysis["predictions"]:
        del prediction["probabilities"][project["classification"]["labels"][2]]
    view.classification.kind.setCurrentIndex(0)
    view.set_analysis(analysis, project)
    assert len(view.classification.figure.axes[0].patches) == 4
    assert view._rows[0][f"P({project['classification']['labels'][2]})"] is None


def test_export_each_portable_chart_format_with_long_chinese_caption(view, app, tmp_path):
    project, analysis = synthetic_classification()
    analysis["warnings"] = ["合成数据仅用于界面测试：" + "这是一个很长的中文分类标签与模型状态说明。" * 5]
    view.set_analysis(analysis, project)
    view.tabs.setCurrentWidget(view.classification)
    view.show()
    app.processEvents()
    original_size = view.classification.figure.get_size_inches().copy()
    for suffix in ("png", "pdf", "svg"):
        path = tmp_path / f"long-caption.{suffix}"
        view.export_figure(path)
        assert path.stat().st_size > 1000
        assert np.allclose(view.classification.figure.get_size_inches(), original_size)
        assert len(view.classification.figure.texts) == 0
    svg = (tmp_path / "long-caption.svg").read_text()
    assert "Synthetic classifier" in svg
    assert "合成数据仅用于界面测试" in svg
    with pytest.raises(ValueError, match="PNG"):
        view.export_figure(tmp_path / "bad.jpg")
