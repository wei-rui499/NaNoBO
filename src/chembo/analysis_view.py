"""Inspect real model results in Qt; plots never manufacture missing predictions."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import textwrap

import typing_extensions  # Initialize Python 3.10 annotation backports before Qt.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - register the native 3-D projection
import numpy as np

from chembo.storage import write_csv

GREEN, LIGHT, GOLD, GRAY = "#237b63", "#a9cbbb", "#bf8c35", "#74867e"


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _label(value, width=20):
    return "\n".join(textwrap.wrap(str(value), width=width))


def _font():
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in ("PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Arial Unicode MS", "DejaVu Sans"):
        if name in available:
            return name
    return "sans-serif"


class _NumberItem(QTableWidgetItem):
    """Keep numeric sorting numeric, while rendering a compact readable value."""
    def __init__(self, value):
        super().__init__("" if value is None else f"{value:.7g}" if _finite(value) else str(value))
        self.value = value
        self.setToolTip("" if value is None else str(value))

    def __lt__(self, other):
        if isinstance(other, _NumberItem) and _finite(self.value) and _finite(other.value):
            return self.value < other.value
        return self.text() < other.text()


class _Plot(QWidget):
    def __init__(self, parent, choices, draw):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.controls = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(choices)
        self.controls.addWidget(self.kind)
        layout.addLayout(self.controls)
        self.figure = Figure(figsize=(7.2, 4.6), dpi=100, layout="constrained", facecolor="#fcfdfb")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(230)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #61766b; padding: 4px;")
        layout.addWidget(self.note)
        self.kind.currentIndexChanged.connect(draw)
        self.canvas.mpl_connect("pick_event", parent._picked)

    def axis(self, title, projection=None):
        self.figure.clear()
        axis = self.figure.add_subplot(111, projection=projection)
        axis.set_title(title, fontsize=11, pad=12, color="#233d34")
        if projection != "3d":
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(alpha=.16, color=GRAY)
        axis.tick_params(labelsize=9)
        return axis

    def empty(self, title, explanation):
        axis = self.axis(title)
        axis.axis("off")
        axis.text(.5, .5, explanation, ha="center", va="center", wrap=True,
                  transform=axis.transAxes, color=GRAY, fontsize=11)
        self.note.setText(explanation)
        self.canvas.draw_idle()


class AnalysisView(QWidget):
    """A self-contained result view; analysis stays tied to its project snapshot.

    Public API: set_analysis(analysis, project), clear(), export_figure(path),
    export_predictions(path). The currently visible chart is the exported one.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis, self.project, self._columns, self._rows = {}, {}, [], []
        self.loading = False
        self.font_name = _font()
        layout = QVBoxLayout(self)
        self.summary = QLabel("尚未分析；生成建议或运行模型分析后，在这里查看结果。")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("background:#eaf3ee; padding:9px; border-radius:6px;")
        layout.addWidget(self.summary)
        row = QHBoxLayout()
        self.objective = QComboBox()
        self.objective.setAccessibleName("图表目标")
        row.addWidget(QLabel("查看目标"))
        row.addWidget(self.objective, 1)
        export_plot = QPushButton("导出当前图…")
        export_plot.setToolTip("导出当前图表；在预测表页时导出候选预测图。")
        export_data = QPushButton("导出预测表 CSV…")
        export_plot.clicked.connect(self._choose_figure)
        export_data.clicked.connect(self._choose_predictions)
        row.addWidget(export_plot)
        row.addWidget(export_data)
        layout.addLayout(row)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.table, "候选预测表")
        self.prediction = _Plot(self, ["候选预测与区间", "预测均值与不确定性", "采集分值排序"], self.redraw)
        self.validation = _Plot(self, ["预测与实测", "验证误差"], self.redraw)
        self.distribution = _Plot(self, ["观测分布", "实测历史"], self.redraw)
        self.variable = QComboBox()
        self.variable.setAccessibleName("分布变量")
        self.distribution.controls.addWidget(self.variable, 1)
        self.multi = _Plot(self, ["二维 Pareto", "三维 Pareto", "超体积历史"], self.redraw)
        self.axes = []
        for name in ("X", "Y", "Z"):
            box = QComboBox()
            box.setAccessibleName(f"Pareto {name}轴")
            self.multi.controls.addWidget(QLabel(name))
            self.multi.controls.addWidget(box, 1)
            box.currentIndexChanged.connect(self.redraw)
            self.axes.append(box)
        self.classification = _Plot(self, ["候选类别概率", "分类不确定性", "已测类别分布", "混淆矩阵"], self.redraw)
        for page, name in [(self.prediction, "预测与探索"), (self.validation, "模型验证"),
                           (self.distribution, "数据分布"), (self.multi, "Pareto 多目标"),
                           (self.classification, "分类分析")]:
            self.tabs.addTab(page, name)
        self.objective.currentIndexChanged.connect(self.redraw)
        self.variable.currentIndexChanged.connect(self.redraw)
        self.detail = QLabel("点击图中的候选点可查看对应条件；工具栏支持平移、缩放和还原。")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.clear()

    def clear(self):
        self.set_analysis({}, {})

    def set_analysis(self, analysis, project):
        self.loading = True
        self.analysis, self.project = copy.deepcopy(analysis or {}), copy.deepcopy(project or {})
        objectives = [o["name"] for o in self.project.get("objectives", [])]
        self.objective.clear()
        self.objective.addItems(objectives)
        self.variable.clear()
        self.variable.addItems([p["name"] for p in self.project.get("parameters", [])] + objectives)
        for index, box in enumerate(self.axes):
            box.clear()
            box.addItems(objectives)
            box.setCurrentIndex(min(index, max(0, len(objectives)-1)))
        model = self.analysis.get("model") or self.analysis.get("engine") or "尚未拟合模型"
        status = self.analysis.get("status", "尚无分析结果")
        if isinstance(status, dict):
            status = status.get("message", str(status))
        status = {"trained": "已拟合", "initial_design": "初始设计"}.get(status, status)
        warnings = self.analysis.get("warnings") or []
        self.summary.setText(f"{model}  ·  {status}" + ("\n" + "；".join(map(str, warnings)) if warnings else ""))
        self._fill_table()
        self.loading = False
        self.redraw()

    def _predictions(self):
        return self.analysis.get("predictions") or []

    def _fill_table(self):
        parameters = [p["name"] for p in self.project.get("parameters", [])]
        objectives = [o["name"] for o in self.project.get("objectives", [])]
        labels = self.project.get("classification", {}).get("labels", [])
        classification = self.analysis.get("task", self.project.get("task")) == "classification"
        columns = ["候选编号", "本批推荐"] + parameters
        columns += [f"P({label})" for label in labels] + ["熵"] if classification else [s for o in objectives for s in (f"{o} · 预测", f"{o} · 标准差")]
        score_column = "采集分值" + (" · " + self.analysis["score_label"] if self.analysis.get("score_label") else "")
        columns += [score_column]
        self._columns, self._rows = columns, []
        for index, prediction in enumerate(self._predictions(), 1):
            selected = prediction.get("selected")
            row = {"候选编号": index, "本批推荐": "是" if selected is True else "否" if selected is False else "", **prediction.get("parameters", {})}
            if classification:
                row.update({f"P({label})": prediction.get("probabilities", {}).get(label) for label in labels})
                row["熵"] = prediction.get("entropy")
            else:
                for objective in objectives:
                    row[f"{objective} · 预测"] = prediction.get("mean", {}).get(objective)
                    row[f"{objective} · 标准差"] = prediction.get("std", {}).get(objective)
            row[score_column] = prediction.get("score")
            self._rows.append(row)
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            for j, name in enumerate(columns):
                self.table.setItem(i, j, _NumberItem(row.get(name)))
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def _style(self, page):
        for text in page.figure.findobj(match=lambda obj: hasattr(obj, "set_fontfamily")):
            text.set_fontfamily(self.font_name)
        page.figure.set_facecolor("#fcfdfb")
        page.canvas.draw_idle()

    def redraw(self, *args):
        if self.loading:
            return
        self._draw_prediction()
        self._draw_validation()
        self._draw_distribution()
        self._draw_multi()
        self._draw_classification()
        for page in (self.prediction, self.validation, self.distribution, self.multi, self.classification):
            self._style(page)

    def _picked(self, event):
        descriptions = getattr(event.artist, "_nanobo_labels", [])
        if descriptions and len(event.ind):
            index = event.ind[0]
            if index < len(descriptions):
                self.detail.setText(descriptions[index])

    def _draw_prediction(self):
        page, objective = self.prediction, self.objective.currentText()
        if self.analysis.get("task", self.project.get("task")) == "classification":
            page.empty("数值预测", "当前任务为分类；请查看“分类分析”中的类别概率与熵。")
            return
        points = [(i, p) for i, p in enumerate(self._predictions(), 1) if _finite(p.get("mean", {}).get(objective))]
        if not points:
            page.empty("候选预测", "当前没有已拟合模型的候选预测。初始设计阶段尚未训练模型；完成模型分析后显示预测值与区间。")
            return
        indices = np.array([i for i, p in points])
        mean = np.array([p["mean"][objective] for i, p in points])
        std = np.array([p.get("std", {}).get(objective, np.nan) for i, p in points], dtype=float)
        axis = page.axis(_label(objective) + " · 候选模型预测")
        mode = page.kind.currentIndex()
        descriptions = [f"候选 {i}: " + ", ".join(f"{k}={v}" for k, v in p.get("parameters", {}).items()) for i, p in points]
        if mode == 1:
            valid = np.isfinite(std) & (std >= 0)
            if not valid.any():
                page.empty("预测均值与不确定性", "当前引擎没有返回可用的候选模型标准差。")
                return
            artist = axis.scatter(mean[valid], std[valid], c=indices[valid], cmap="YlGn", edgecolors=GREEN, s=38, picker=5)
            artist._nanobo_labels = [v for v, ok in zip(descriptions, valid) if ok]
            axis.set_xlabel("预测均值")
            axis.set_ylabel("模型标准差")
        elif mode == 2:
            valid = [(i, p, d) for (i, p), d in zip(points, descriptions) if _finite(p.get("score"))]
            if not valid:
                page.empty("采集分值", "当前引擎未返回可用的采集分值。")
                return
            valid.sort(key=lambda item: item[1]["score"], reverse=True)
            axis.plot(range(1, len(valid)+1), [p["score"] for i, p, d in valid], color=GREEN, alpha=.5)
            artist = axis.scatter(range(1, len(valid)+1), [p["score"] for i, p, d in valid], s=28, color=GREEN, picker=5)
            artist._nanobo_labels = [d for i, p, d in valid]
            axis.set_xlabel("按采集分值排序的位置")
            axis.set_ylabel(self.analysis.get("score_label", "采集分值") + "（同次分析内比较）")
        else:
            valid = np.isfinite(std) & (std >= 0)
            if valid.any():
                axis.fill_between(indices[valid], mean[valid]-1.96*std[valid], mean[valid]+1.96*std[valid], color=LIGHT, alpha=.4, label="均值 ± 1.96 × 模型标准差")
            artist = axis.scatter(indices, mean, color=GREEN, s=26, picker=5, label="模型均值")
            artist._nanobo_labels = descriptions
            selected = np.array([p.get("selected") is True for i, p in points])
            if selected.any():
                chosen = axis.scatter(indices[selected], mean[selected], color=GOLD, marker="*", s=105, zorder=4, picker=5, label="本批推荐")
                chosen._nanobo_labels = [v for v, ok in zip(descriptions, selected) if ok]
            axis.set_xlabel("候选编号（对应预测表）")
            axis.set_ylabel(_label(objective))
            axis.legend(fontsize=8, loc="best")
        page.note.setText(f"{len(points)} 个未测候选。图中为模型预测，不是实测结果；区间未作额外覆盖率校准，不表示实验误差。采集分值仅供本次分析内比较。" + str(self.analysis.get("score_rule", "")))

    def _draw_validation(self):
        page, objective = self.validation, self.objective.currentText()
        diagnostic = self.analysis.get("diagnostics") or {}
        diagnostic_note = diagnostic.get("note") or diagnostic.get("message") or ""
        rows = diagnostic.get("rows") or []
        if self.analysis.get("task", self.project.get("task")) == "classification":
            page.empty("模型验证", "分类验证请查看“分类分析 → 混淆矩阵”。")
            return
        rows = [r for r in rows if _finite(r.get("actual", {}).get(objective)) and _finite(r.get("predicted", {}).get(objective))]
        if not rows:
            page.empty("模型验证", diagnostic_note or "尚无交叉验证结果。完成模型验证后显示；样本不足或模型尚未拟合时暂不计算。")
            return
        actual = np.array([r["actual"][objective] for r in rows])
        predicted = np.array([r["predicted"][objective] for r in rows])
        axis = page.axis(f"{diagnostic.get('method', '交叉验证')} · {_label(objective)}")
        if page.kind.currentIndex() == 1:
            index = [r.get("index", i)+1 for i, r in enumerate(rows)]
            axis.axhline(0, color=GRAY, linestyle="--", linewidth=1)
            axis.scatter(index, predicted-actual, color=GREEN, s=36)
            axis.set_xlabel("被留出实验的序号")
            axis.set_ylabel("预测 − 实测")
        else:
            valid_std = [r.get("std", {}).get(objective) for r in rows]
            std_indices = [i for i, v in enumerate(valid_std) if _finite(v) and v >= 0]
            low_values = [predicted[i] - 1.96*valid_std[i] for i in std_indices]
            high_values = [predicted[i] + 1.96*valid_std[i] for i in std_indices]
            lo = min([actual.min(), predicted.min()] + low_values)
            hi = max([actual.max(), predicted.max()] + high_values)
            margin = max((hi-lo)*.07, abs(hi)*.03, .01)
            axis.plot([lo-margin, hi+margin], [lo-margin, hi+margin], linestyle="--", color=GRAY, linewidth=1)
            if std_indices:
                axis.errorbar(actual[std_indices], predicted[std_indices], yerr=1.96*np.array([valid_std[i] for i in std_indices]), fmt="none", color=LIGHT, alpha=.7, capsize=2)
            axis.scatter(actual, predicted, s=40, color=GREEN, edgecolor="white")
            axis.set_xlabel("实测值（验证时未参与训练）")
            axis.set_ylabel("留出预测值")
            axis.set_xlim(lo-margin, hi+margin)
            axis.set_ylim(lo-margin, hi+margin)
            axis.set_aspect("equal", adjustable="box")
        metrics = (diagnostic.get("metrics") or {}).get(objective, {})
        items = [f"{'R²' if key == 'r2' else key.upper()}={value:.5g}" for key, value in metrics.items() if key in ("rmse", "mae", "r2") and _finite(value)]
        page.note.setText(f"实际使用模型的 {diagnostic.get('method', '交叉验证')}；验证 {len(rows)} 行。" + "   ".join(items) + ("  " + diagnostic_note if diagnostic_note else ""))

    def _draw_distribution(self):
        page, name = self.distribution, self.variable.currentText()
        observations = self.project.get("observations") or []
        if not observations or not name:
            page.empty("观测数据", "录入已完成实验后显示分布；待实验条件不计入统计。")
            return
        present = [(i, row[name]) for i, row in enumerate(observations, 1) if name in row and row[name] is not None]
        values = [value for i, value in present if not isinstance(value, (int, float)) or _finite(value)]
        if not values:
            page.empty("观测数据", "该变量尚无完整的实测数据。")
            return
        axis = page.axis(_label(name) + " · 已完成实验")
        if all(_finite(value) for value in values):
            if page.kind.currentIndex() == 1:
                indices = [i for i, value in present if _finite(value)]
                axis.scatter(indices, values, color=GREEN, s=30, label="实测")
                objective = next((o for o in self.project.get("objectives", []) if o["name"] == name), None)
                if objective:
                    best = np.maximum.accumulate(values) if objective["goal"] == "max" else np.minimum.accumulate(values)
                    axis.plot(indices, best, color=GOLD, label="历史最佳实测")
                    axis.legend(fontsize=8)
                axis.set_xlabel("实验记录序号")
                axis.set_ylabel(_label(name))
            else:
                axis.hist(values, bins=min(16, max(3, int(math.sqrt(len(values))))), color=GREEN, alpha=.75, edgecolor="white")
                axis.set_xlabel(_label(name))
                axis.set_ylabel("实测记录数")
        else:
            labels = list(dict.fromkeys(str(v) for v in values))
            axis.bar(range(len(labels)), [sum(str(v) == label for v in values) for label in labels], color=GREEN, alpha=.8)
            axis.set_xticks(range(len(labels)), [_label(s, 12) for s in labels], rotation=20, ha="right")
            axis.set_ylabel("实测记录数")
        page.note.setText(f"该变量有 {len(values)} 条完整实测记录，包含重复实验；记录顺序不等于真实时间间隔。")

    def _draw_multi(self):
        page, data = self.multi, self.analysis.get("pareto") or {}
        objectives = self.project.get("objectives") or []
        if len(objectives) < 2 or not data:
            page.empty("Pareto 多目标", "至少两个数值目标，并运行 Pareto 分析后显示；Chimera 优先级优化不等同于 Pareto 搜索。")
            return
        mode = page.kind.currentIndex()
        if mode == 2:
            history = data.get("hypervolume_history") or []
            points = [p for p in history if _finite(p.get("value"))]
            if not points:
                page.empty("超体积历史", "当前没有在共同参考点下计算的超体积记录。")
                return
            axis = page.axis("已测 Pareto 前沿 · 超体积历史")
            axis.plot([p.get("index", i+1) for i, p in enumerate(points)], [p["value"] for p in points], color=GREEN, marker="o", markersize=3)
            axis.set_xlabel("实验记录序号")
            axis.set_ylabel("超体积（共同参考点）")
        else:
            dimensions = 3 if mode == 1 else 2
            selected = [box.currentText() for box in self.axes[:dimensions]]
            if len(set(selected)) != dimensions:
                page.empty("Pareto 目标投影", f"请选择 {dimensions} 个不同目标。")
                return
            observations = self.project.get("observations") or []
            rows = [(i, row) for i, row in enumerate(observations) if all(_finite(row.get(name)) for name in selected)]
            if not rows:
                page.empty("Pareto 前沿", "尚无完整的多目标实测数据。")
                return
            axis = page.axis("已测结果 · " + ("三维 Pareto" if dimensions == 3 else "Pareto 投影"), "3d" if dimensions == 3 else None)
            pareto = set(data.get("indices") or [])
            dominated = [row for i, row in rows if i not in pareto]
            front = [row for i, row in rows if i in pareto]
            for group, color, label, size in [(dominated, GRAY, "其他实测", 28), (front, GREEN, "全目标非支配实测", 58)]:
                if group:
                    axis.scatter(*[[row[name] for row in group] for name in selected], color=color, s=size, label=label, alpha=.85)
            for setter, name in zip([axis.set_xlabel, axis.set_ylabel] + ([axis.set_zlabel] if dimensions == 3 else []), selected):
                goal = next(o.get("goal") for o in objectives if o["name"] == name)
                setter(_label(name) + (" ↑" if goal == "max" else " ↓"), fontsize=9, labelpad=8)
            axis.legend(fontsize=8, loc="best")
        reference = data.get("reference_point") or {}
        page.note.setText("只绘制已测结果，未测预测与 pending 不进入实测 Pareto 前沿。参考点：" + ", ".join(f"{k}={v:.5g}" if _finite(v) else f"{k}={v}" for k, v in reference.items()) + "。" + str(data.get("reference_rule", "")) + " 多于两个目标时，二维投影不保证形成有序曲线。")

    def _draw_classification(self):
        page = self.classification
        if self.analysis.get("task", self.project.get("task")) != "classification":
            page.empty("分类主动学习", "当前任务为数值优化。切换分类任务后显示类别概率、熵和分类验证。")
            return
        labels = self.project.get("classification", {}).get("labels", [])
        objective = (self.project.get("objectives") or [{}])[0].get("name")
        predictions = self._predictions()
        mode = page.kind.currentIndex()
        axis = page.axis(["未测候选 · 类别概率", "未测候选 · 分类熵", "已完成实验 · 类别分布", "留出验证 · 混淆矩阵"][mode])
        if mode == 0:
            predictions = [(i, p) for i, p in enumerate(predictions, 1) if p.get("probabilities")]
            if not predictions:
                page.empty("类别概率", "尚未具备可训练的类别数据。初始探索阶段尚无模型类别概率。")
                return
            # Keep the visible plot readable; the exportable table retains every candidate.
            plotted_labels = [label for label in labels if any(label in p["probabilities"] for i, p in predictions)]
            if not plotted_labels:
                page.empty("类别概率", "模型没有返回所设类别的概率；请查看模型状态与警告。")
                return
            shown = [(i, p) for i, p in predictions if all(_finite(p["probabilities"].get(label)) for label in plotted_labels)][:40]
            if not shown:
                page.empty("类别概率", "模型返回的类别概率不完整，无法绘制堆积概率图。")
                return
            bottom = np.zeros(len(shown))
            colors = ["#237b63", "#b3cfa8", "#bf8c35", "#6c9ec2", "#ae8db5"]
            for index, label in enumerate(plotted_labels):
                values = np.array([p["probabilities"][label] for i, p in shown])
                axis.bar([i for i, p in shown], values, bottom=bottom, label=_label(label, 12), color=colors[index % len(colors)], width=.9)
                bottom += values
            axis.set_ylim(0, 1)
            axis.set_xlabel("候选编号（前 40 个；完整数据见表格）")
            axis.set_ylabel("类别概率")
            axis.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
        elif mode == 1:
            points = [(i, p) for i, p in enumerate(predictions, 1) if _finite(p.get("entropy"))]
            if not points:
                page.empty("分类不确定性", "当前没有已拟合分类器的熵。")
                return
            axis.scatter([i for i, p in points], [p["entropy"] for i, p in points], color=GREEN, s=24)
            axis.set_xlabel("候选编号")
            axis.set_ylabel("预测类别熵（越大越不确定）")
        elif mode == 2:
            values = [str(row.get(objective)) for row in self.project.get("observations", [])]
            axis.bar(range(len(labels)), [values.count(str(label)) for label in labels], color=GREEN)
            axis.set_xticks(range(len(labels)), [_label(label, 12) for label in labels], rotation=20, ha="right")
            axis.set_ylabel("实测记录数")
        else:
            diagnostic = self.analysis.get("diagnostics") or {}
            diagnostic_note = diagnostic.get("note") or diagnostic.get("message") or ""
            rows = diagnostic.get("rows") or []
            pairs = [(str(r.get("actual", {}).get(objective)), str(r.get("predicted", {}).get(objective))) for r in rows]
            pairs = [(a, b) for a, b in pairs if a in labels and b in labels]
            if not pairs:
                page.empty("混淆矩阵", diagnostic_note or "尚无留出分类验证；样本或类别不足时暂不计算准确率。")
                return
            matrix = np.array([[sum(a == x and b == y for a, b in pairs) for y in labels] for x in labels])
            axis.grid(False)
            axis.imshow(matrix, cmap="Greens", vmin=0)
            for i in range(len(labels)):
                for j in range(len(labels)):
                    axis.text(j, i, str(matrix[i, j]), ha="center", va="center", color="white" if matrix[i, j] > matrix.max()/2 else "#233d34")
            axis.set_xticks(range(len(labels)), [_label(label, 12) for label in labels], rotation=20, ha="right")
            axis.set_yticks(range(len(labels)), [_label(label, 12) for label in labels])
            axis.set_xlabel("留出预测类别")
            axis.set_ylabel("实测类别")
        diagnostic = self.analysis.get("diagnostics") or {}
        diagnostic_note = diagnostic.get("note") or diagnostic.get("message") or ""
        metrics = (diagnostic.get("metrics") or {}).get(objective, {})
        accuracy = metrics.get("accuracy")
        page.note.setText("固定分类模型的概率/熵仅用于分类主动学习；它不等于化学性能预测。未返回的类别概率保持缺失，不补零。" + (f" 留出准确率={accuracy:.3f}。" if _finite(accuracy) else "") + (" " + diagnostic_note if diagnostic_note else ""))

    def export_figure(self, path):
        page = self.tabs.currentWidget()
        if not isinstance(page, _Plot):
            page = self.classification if self.analysis.get("task", self.project.get("task")) == "classification" else self.prediction
        path = Path(path)
        if path.suffix.lower() not in (".png", ".pdf", ".svg"):
            raise ValueError("图像格式必须是 PNG、PDF 或 SVG。")
        self._style(page)
        page.canvas.draw()
        # Put the explanation in the exported artifact as well as the Qt label.
        # Reserve space in physical units so long Chinese captions cannot overlap axes.
        figure = page.figure
        original_size = figure.get_size_inches().copy()
        width, height = 8., 5.2
        caption = _label(self.summary.text() + "\n" + page.note.text(), int(width*8))
        footer_height = .2 * (caption.count("\n") + 1) + .18
        engine = figure.get_layout_engine()
        original_rect = engine.get()["rect"] if engine else None
        footer = figure.text(.02, .025, caption, fontsize=8, fontfamily=self.font_name,
                             color="#61766b", ha="left", va="bottom")
        try:
            figure.set_size_inches(width, height + footer_height, forward=False)
            if engine:
                engine.set(rect=(0, footer_height/(height+footer_height), 1, height/(height+footer_height)))
            figure.canvas.draw()
            extra_artists = [footer]
            for axis in figure.axes:
                extra_artists.extend([axis.xaxis.label, axis.yaxis.label])
                if hasattr(axis, "zaxis"):
                    extra_artists.append(axis.zaxis.label)
                if axis.get_legend():
                    extra_artists.append(axis.get_legend())
            figure.savefig(path, dpi=220, bbox_inches="tight", bbox_extra_artists=extra_artists,
                           pad_inches=.22, facecolor=figure.get_facecolor())
        finally:
            footer.remove()
            figure.set_size_inches(*original_size, forward=False)
            if engine:
                engine.set(rect=original_rect)
            page.canvas.draw_idle()

    def export_predictions(self, path):
        if not self._rows:
            raise ValueError("没有可导出的候选预测。")
        write_csv(path, self._columns, self._rows)

    def _choose_figure(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出当前分析图", "NaNoBO-analysis.png", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if path:
            try:
                self.export_figure(path)
            except Exception as exc:
                QMessageBox.warning(self, "导图失败", str(exc))

    def _choose_predictions(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出候选预测表", "NaNoBO-predictions.csv", "CSV (*.csv)")
        if path:
            try:
                self.export_predictions(path)
            except Exception as exc:
                QMessageBox.warning(self, "导出失败", str(exc))
