"""Native, offline ask/tell workflow. Scientific engines run outside the UI process."""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTemporaryDir, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QInputDialog,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QScrollArea,
)

from chembo import __version__
from chembo.engine import read_candidates, read_observations, reconcile_project, validate_project
from chembo.analysis_view import AnalysisView
from chembo.recipe_dialog import RecipeDialog
from chembo.table_io import sheet_names
from chembo.storage import save_project, write_csv

ENGINE_NAMES = {"Gryffin · 类别与连续变量": "gryffin", "Atlas · 高斯过程": "atlas", "BoTorch · 优化与分类": "bo-mcp"}
TASKS = {"数值优化 / 优先级": ("optimization", "hierarchical"), "Pareto 多目标": ("optimization", "pareto"), "分类主动学习": ("classification", "hierarchical")}
TYPES = {"连续": "continuous", "整数": "discrete", "类别": "categorical"}


def example_project():
    return {
        "name": "教学示例 · 模拟响应", "engine": "gryffin", "seed": 42, "batch_size": 2,
        "parameters": [{"name": "x", "type": "continuous", "low": 0, "high": 1, "unit": ""},
                       {"name": "category", "type": "categorical", "options": ["A", "B", "C"], "unit": ""}],
        "objectives": [{"name": "response", "goal": "max", "tolerance": 0.2}],
        "observations": [{"x": 0.1, "category": "A", "response": 0.2},
                         {"x": 0.4, "category": "B", "response": 0.8},
                         {"x": 0.8, "category": "C", "response": 0.4},
                         {"x": 0.65, "category": "B", "response": 0.95},
                         {"x": 0.3, "category": "A", "response": 0.5}],
        "pending": [], "notes": "仅用于演示软件流程，所有响应数据均为模拟数据。"}


def resources():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        return root.parent / "Resources"
    return root


class Trend(QWidget):
    def __init__(self):
        super().__init__()
        self.values, self.goal = [], "max"
        self.setMinimumHeight(130)
        self.setAccessibleName("首个优化目标的历史最佳值")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f5f8f7"))
        painter.setPen(QColor("#63766f"))
        painter.drawText(16, 22, "首个目标 · 历史最佳实测值")
        if not self.values:
            painter.drawText(16, 60, "录入实验结果后显示趋势")
            return
        best, running = [], self.values[0]
        for value in self.values:
            running = min(running, value) if self.goal == "min" else max(running, value)
            best.append(running)
        low, high = min(best), max(best)
        span = high - low or max(abs(high) * 0.1, 1)
        left, top, width, height = 72, 38, max(40, self.width() - 100), max(30, self.height() - 65)
        painter.drawText(12, top + 8, f"{high:.4g}")
        painter.drawText(12, top + height, f"{low:.4g}")
        painter.setPen(QPen(QColor("#d8e1dd"), 1))
        painter.drawLine(left, top + height, left + width, top + height)
        painter.setPen(QPen(QColor("#237b63"), 2.5))
        points = [(left + i * width / max(1, len(best) - 1), top + height * (1 - (value - low) / span)) for i, value in enumerate(best)]
        for i, (x, y) in enumerate(points):
            if i:
                from PySide6.QtCore import QPointF
                painter.drawLine(QPointF(*points[i - 1]), QPointF(x, y))
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project, self.path = {}, None
        self.action_buttons = []
        self.dirty, self.loading, self.process, self.cancelled = False, True, None, False
        self.setMinimumSize(1040, 720)
        self.resize(1360, 860)
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 18)
        heading = QHBoxLayout()
        title = QLabel("NaNoBO")
        title.setObjectName("title")
        subtitle = QLabel("化学实验规划  /  本地计算")
        subtitle.setObjectName("muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        heading.addStretch()
        for label, callback in [("新项目", self.new_project), ("教学示例", self.load_example), ("打开", self.open_project), ("保存", self.save), ("关于 / 许可", self.about)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.action_buttons.append(button)
            heading.addWidget(button)
        outer.addLayout(heading)
        self.message = QLabel("定义变量 → 录入已有结果 → 生成下一批 → 实验后回填")
        self.message.setObjectName("banner")
        self.message.setWordWrap(True)
        outer.addWidget(self.message)
        split = QSplitter()
        outer.addWidget(split, 1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 14, 0)
        form = QFormLayout()
        self.name = QLineEdit()
        self.engine = QComboBox()
        self.engine.addItems(ENGINE_NAMES)
        self.task = QComboBox()
        self.task.addItems(TASKS)
        self.labels = QLineEdit("成功 | 失败")
        self.labels.setToolTip("分类标签用 | 分隔；结果表目标列填写其中一个标签。")
        self.batch = QSpinBox()
        self.batch.setRange(1, 24)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        form.addRow("项目名称", self.name)
        form.addRow("任务类型", self.task)
        form.addRow("推荐引擎", self.engine)
        form.addRow("分类标签", self.labels)
        form.addRow("本批实验数", self.batch)
        form.addRow("随机种子", self.seed)
        left_layout.addLayout(form)
        label = QLabel("1  定义实验空间")
        label.setObjectName("section")
        left_layout.addWidget(label)
        self.params = self.table(["变量名", "类型", "下限", "上限", "类别（| 分隔）", "单位", "步长"])
        for column, width in enumerate((100, 75, 65, 65, 125, 50, 65)):
            self.params.setColumnWidth(column, width)
        left_layout.addWidget(self.params, 3)
        self.button_row(left_layout, [("＋ 变量", self.add_parameter), ("删除选中变量", lambda: self.remove_rows(self.params))])
        self.domain_summary = QLabel()
        self.domain_summary.setWordWrap(True)
        left_layout.addWidget(self.domain_summary)
        self.button_row(left_layout, [("配方约束 / 候选表…", self.edit_recipe), ("清除联合限制", self.clear_recipe)])
        self.objective_tip = QLabel("数值目标可最大化或最小化；分类只保留一个标签列。")
        self.objective_tip.setWordWrap(True)
        left_layout.addWidget(self.objective_tip)
        self.objectives = self.table(["目标名称", "方向", "容忍比例 (0–1)"])
        left_layout.addWidget(self.objectives, 1)
        self.button_row(left_layout, [("＋ 目标", self.add_objective), ("删除选中目标", lambda: self.remove_rows(self.objectives))])
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("项目备注、实验单位、数据来源……")
        self.notes.setMaximumHeight(78)
        left_layout.addWidget(self.notes)
        tip = QLabel("BoTorch 支持步长、合法候选表、总量／配比约束、Pareto、分类与模型验证。步长从下限起算，留空表示连续。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        left_layout.addWidget(tip)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(left)
        split.addWidget(scroll)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 0, 0, 0)
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)
        observed_page = QWidget()
        observed_layout = QVBoxLayout(observed_page)
        observed_layout.addWidget(QLabel("2  已完成实验 · 每行填写全部变量和目标值"))
        self.observed = self.table([])
        observed_layout.addWidget(self.observed, 1)
        self.button_row(observed_layout, [("＋ 录入一行", self.add_observation), ("导入 Excel / CSV", self.import_csv), ("导出结果", self.export_observed), ("删除选中行", lambda: self.remove_rows(self.observed))])
        self.trend = Trend()
        observed_layout.addWidget(self.trend)
        self.tabs.addTab(observed_page, "已完成实验")
        pending_page = QWidget()
        pending_layout = QVBoxLayout(pending_page)
        pending_layout.addWidget(QLabel("3  待实验条件 · 回填结果前保持在此列表，避免重复推荐"))
        self.pending = self.table([])
        self.pending.setEditTriggers(QTableWidget.NoEditTriggers)
        pending_layout.addWidget(self.pending, 1)
        self.button_row(pending_layout, [("导出待回填 CSV", self.export_pending), ("将选中条件转入结果表", self.pending_to_observed), ("撤回选中条件", self.withdraw_pending)])
        pending_layout.addWidget(QLabel("导出 CSV 后填写目标列，再从“已完成实验”导入；匹配的待实验条件会自动移除。"))
        self.tabs.addTab(pending_page, "下一批 / 待实验")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.log_tab = self.tabs.addTab(self.logs, "运行日志")
        self.analysis_view = AnalysisView()
        self.analysis_tab = self.tabs.addTab(self.analysis_view, "模型与可视化")
        controls = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        controls.addWidget(self.progress, 1)
        self.cancel = QPushButton("取消计算")
        self.cancel.clicked.connect(self.cancel_run)
        self.cancel.hide()
        controls.addWidget(self.cancel)
        self.generate = QPushButton("生成下一批实验  →")
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(lambda: self.run())
        self.analyze = QPushButton("分析与交叉验证")
        self.analyze.clicked.connect(lambda: self.run(operation="analyze"))
        controls.addWidget(self.analyze)
        controls.addWidget(self.generate)
        right_layout.addLayout(controls)
        split.addWidget(right)
        split.setSizes([560, 730])
        self.status = QLabel()
        self.status.setObjectName("muted")
        outer.addWidget(self.status)
        self.setCentralWidget(root)
        file_menu = self.menuBar().addMenu("文件")
        for label, shortcut, callback in [("新项目", QKeySequence.New, self.new_project),
                                          ("打开项目…", QKeySequence.Open, self.open_project),
                                          ("保存项目", QKeySequence.Save, self.save),
                                          ("项目另存为…", QKeySequence.SaveAs, lambda: self.save(as_new=True))]:
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)
        help_menu = self.menuBar().addMenu("帮助")
        about_action = QAction("关于 NaNoBO", self)
        about_action.setMenuRole(QAction.AboutRole)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        for table in [self.params, self.objectives, self.observed]:
            table.itemChanged.connect(self.changed)
        self.name.textChanged.connect(self.changed)
        self.notes.textChanged.connect(self.changed)
        self.engine.currentIndexChanged.connect(self.engine_changed)
        self.task.currentIndexChanged.connect(self.task_changed)
        self.labels.textChanged.connect(self.changed)
        self.batch.valueChanged.connect(self.changed)
        self.seed.valueChanged.connect(self.changed)
        project = example_project()
        project["engine"] = "bo-mcp"
        self.set_project(project)

    def table(self, labels):
        table = QTableWidget(0, len(labels))
        table.setHorizontalHeaderLabels(labels)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setMinimumHeight(100)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(32)
        return table

    def button_row(self, layout, actions):
        row = QHBoxLayout()
        for label, callback in actions:
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.action_buttons.append(button)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

    def changed(self, *args):
        if not self.loading:
            self.dirty = True
            if self.analysis_view.project or self.analysis_view.analysis:
                self.analysis_view.clear()
            self.update_title()

    def engine_changed(self, *args):
        self.refresh_task()
        self.changed()

    def task_changed(self, *args):
        if not self.loading and self.task.currentIndex() > 0:
            self.engine.setCurrentText(next(k for k, v in ENGINE_NAMES.items() if v == "bo-mcp"))
        self.refresh_task()
        self.changed()
        if not self.loading:
            self.message.setText("任务已切换。已有数据保留；请检查目标列和分类标签，或载入相应教学示例。")

    def refresh_task(self):
        classification = TASKS[self.task.currentText()][0] == "classification"
        self.labels.setEnabled(classification)
        modern = ENGINE_NAMES[self.engine.currentText()] == "bo-mcp"
        if hasattr(self, "analyze"):
            self.analyze.setEnabled(modern and not self.process)
            self.analyze.setToolTip("使用与推荐相同的 BoTorch / 分类模型重新拟合并进行留一验证。" if modern else "当前引擎保留原生推荐；模型诊断请使用 BoTorch 工作流。")
        if hasattr(self, "objectives"):
            self.objectives.setColumnHidden(2, classification or self.task.currentIndex() == 1 or modern)
            for row in range(self.objectives.rowCount()):
                box = self.objectives.cellWidget(row, 1)
                if box:
                    box.setEnabled(not classification)

    def refresh_domain(self):
        self.domain_summary.setText(f"联合约束 {len(self.project.get('constraints', []))} 条  ·  合法候选表 {len(self.project.get('candidates', []))} 行")

    @staticmethod
    def analysis_signature(project):
        return json.dumps({key: project.get(key) for key in ("engine", "task", "objective_mode", "classification", "parameters", "objectives", "constraints", "candidates", "observations", "pending", "seed", "batch_size", "reference_point")}, sort_keys=True, ensure_ascii=False)

    def edit_recipe(self):
        try:
            project = self.collect()
            dialog = RecipeDialog(project, self)
            if dialog.exec():
                path = self.path
                project = dialog.project
                project.pop("analysis", None)
                project.pop("backend_state", None)
                self.set_project(project, path)
                self.changed()
        except Exception as exc:
            self.error(exc)

    def choose_sheet(self, path):
        from chembo.recipe_dialog import choose_sheet
        return choose_sheet(self, path)

    def clear_recipe(self):
        for key in ("constraints", "candidates", "analysis", "backend_state"):
            self.project.pop(key, None)
        self.refresh_domain()
        self.changed()
        self.message.setText("已清除联合约束和候选表；变量步长仍在变量表中，可单独修改。")

    def update_title(self):
        self.setWindowTitle(f"{'● ' if self.dirty else ''}{self.name.text()} — NaNoBO {__version__}")

    def text(self, table, row, col):
        item = table.item(row, col)
        return item.text().strip() if item else ""

    def put_row(self, table, values):
        row = table.rowCount()
        table.insertRow(row)
        for col, value in enumerate(values):
            table.setItem(row, col, QTableWidgetItem(str(value)))

    def combo(self, table, row, col, values, selected):
        box = QComboBox()
        box.addItems(values)
        box.setCurrentText(selected)
        box.currentIndexChanged.connect(self.changed)
        table.setCellWidget(row, col, box)

    def add_parameter(self):
        self.put_row(self.params, [f"param_{self.params.rowCount() + 1}", "", "0", "1", "", "", ""])
        self.combo(self.params, self.params.rowCount() - 1, 1, TYPES, "连续")
        self.changed()

    def add_objective(self):
        self.put_row(self.objectives, [f"response_{self.objectives.rowCount() + 1}", "", "0.2"])
        self.combo(self.objectives, self.objectives.rowCount() - 1, 1, ["最大化", "最小化"], "最大化")
        self.changed()

    def remove_rows(self, table):
        for row in sorted({index.row() for index in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)
        self.changed()

    def set_project(self, project, path=None):
        project = validate_project(project)
        self.loading = True
        self.project, self.path = copy.deepcopy(project), path
        self.name.setText(project["name"])
        task_pair = (project.get("task", "optimization"), project.get("objective_mode", "hierarchical"))
        self.task.setCurrentText(next(k for k, v in TASKS.items() if v == task_pair))
        self.labels.setText(" | ".join(project.get("classification", {}).get("labels", ["成功", "失败"])))
        self.engine.setCurrentText(next(k for k, v in ENGINE_NAMES.items() if v == project["engine"]))
        self.batch.setValue(project.get("batch_size", 1))
        self.seed.setValue(project.get("seed", 42))
        self.notes.setPlainText(project.get("notes", ""))
        self.params.setRowCount(0)
        for p in project["parameters"]:
            self.put_row(self.params, [p["name"], "", p.get("low", ""), p.get("high", ""), " | ".join(p.get("options", [])), p.get("unit", ""), p.get("step", "")])
            self.combo(self.params, self.params.rowCount() - 1, 1, TYPES, next(k for k, v in TYPES.items() if v == p["type"]))
        self.objectives.setRowCount(0)
        for objective in project["objectives"]:
            self.put_row(self.objectives, [objective["name"], "", objective.get("tolerance", 0.2)])
            self.combo(self.objectives, self.objectives.rowCount() - 1, 1, ["最大化", "最小化"], "最大化" if objective["goal"] == "max" else "最小化")
        self.render_data()
        self.refresh_task()
        self.refresh_domain()
        self.loading, self.dirty = False, False
        self.update_title()

    def columns(self, include_objectives=True):
        return [p["name"] for p in self.project["parameters"]] + ([o["name"] for o in self.project["objectives"]] if include_objectives else [])

    def fill_data(self, table, rows, columns):
        table.setRowCount(0)
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        for row in rows:
            self.put_row(table, [row.get(col, "") for col in columns])
        table.resizeColumnsToContents()

    def render_data(self):
        old_loading, self.loading = self.loading, True
        self.fill_data(self.observed, self.project.get("observations", []), self.columns())
        self.fill_data(self.pending, self.project.get("pending", []), self.columns(False))
        objective = self.project["objectives"][0]
        classification = self.project.get("task") == "classification"
        self.trend.setVisible(not classification)
        self.trend.values = [] if classification else [float(row[objective["name"]]) for row in self.project.get("observations", [])]
        self.trend.goal = objective["goal"]
        self.trend.update()
        self.status.setText(f"已完成 {self.observed.rowCount()} 个实验   ·   待实验 {self.pending.rowCount()} 个   ·   {self.path or '尚未保存项目'}")
        self.analysis_view.set_analysis(self.project.get("analysis", {}), self.project)
        self.loading = old_loading

    def replace_data(self, project):
        if self.analysis_signature(project) != self.analysis_signature(self.project):
            project.pop("analysis", None)
        self.project = project
        self.render_data()

    def collect(self):
        project = copy.deepcopy(self.project)
        project.update(name=self.name.text().strip(), engine=ENGINE_NAMES[self.engine.currentText()], seed=self.seed.value(), batch_size=self.batch.value(), notes=self.notes.toPlainText())
        task, mode = TASKS[self.task.currentText()]
        project.update(task=task, objective_mode=mode)
        if task == "classification":
            project["classification"] = {"labels": [x.strip() for x in self.labels.text().split("|")]}
        else:
            project.pop("classification", None)
        params = []
        for row in range(self.params.rowCount()):
            kind = TYPES[self.params.cellWidget(row, 1).currentText()]
            p = {"name": self.text(self.params, row, 0), "type": kind, "unit": self.text(self.params, row, 5)}
            if kind == "categorical":
                p["options"] = [x.strip() for x in self.text(self.params, row, 4).split("|")]
            else:
                p.update(low=float(self.text(self.params, row, 2)), high=float(self.text(self.params, row, 3)))
                if self.text(self.params, row, 6):
                    p["step"] = float(self.text(self.params, row, 6))
            params.append(p)
        project["parameters"] = params
        project["objectives"] = [{"name": self.text(self.objectives, row, 0), "goal": "max" if self.objectives.cellWidget(row, 1).currentText() == "最大化" else "min", "tolerance": float(self.text(self.objectives, row, 2))} for row in range(self.objectives.rowCount())]
        # Keep existing column names: renaming a variable cannot silently relabel old data.
        headers = [self.observed.horizontalHeaderItem(col).text() for col in range(self.observed.columnCount())]
        project["observations"] = [{key: self.text(self.observed, row, col) for col, key in enumerate(headers)} for row in range(self.observed.rowCount())]
        if any(project.get(key) != self.project.get(key) for key in ("parameters", "objectives", "engine", "seed", "task", "objective_mode", "classification", "constraints", "candidates")):
            project.pop("backend_state", None)
        validated = reconcile_project(project)
        if self.analysis_signature(validated) != self.analysis_signature(self.project):
            validated.pop("analysis", None)
        return validated

    def error(self, exc):
        QMessageBox.warning(self, "请检查输入", str(exc))

    def preserve(self):
        if self.process:
            self.error("请先等待计算完成，或取消计算。")
            return False
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, "保存项目", "当前项目有未保存的修改。", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        return self.save() if answer == QMessageBox.Save else answer == QMessageBox.Discard

    def new_project(self):
        if self.preserve():
            project = example_project()
            project.update(name="我的实验项目", engine="bo-mcp", observations=[], pending=[], notes="")
            self.set_project(project)

    def load_example(self):
        if not self.preserve():
            return
        choices = ["数值优化", "总量与步长", "Pareto 多目标", "分类主动学习"]
        choice, ok = QInputDialog.getItem(self, "教学示例（全部为模拟数据）", "选择工作流", choices, 0, False)
        if ok:
            from chembo.examples import workflow_example
            self.set_project(workflow_example(["optimization", "recipe", "pareto", "classification"][choices.index(choice)]))

    def open_project(self):
        if not self.preserve():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", "ChemBO 项目 (*.json)")
        if path:
            try:
                project = validate_project(json.loads(Path(path).read_text(encoding="utf-8")))
                self.set_project(project, path)
            except Exception as exc:
                self.error(exc)

    def save(self, checked=False, *, as_new=False):
        try:
            project = self.collect()
            path = None if as_new else self.path
            if not path:
                path, _ = QFileDialog.getSaveFileName(self, "保存项目", "experiment.chembo.json", "ChemBO 项目 (*.json)")
            if not path:
                return False
            save_project(path, project)
            self.project, self.path, self.dirty = project, path, False
            self.render_data()
            self.update_title()
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def add_observation(self):
        try:
            self.project = self.collect()
            self.render_data()
            self.put_row(self.observed, [""] * len(self.columns()))
            self.changed()
        except Exception as exc:
            self.error(exc)

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入完成的实验结果", "", "实验数据 (*.xlsx *.xls *.csv)")
        if path:
            try:
                project = self.collect()
                sheet = self.choose_sheet(path)
                if sheet is False:
                    return
                rows = read_observations(project, path, sheet)
                project["observations"].extend(rows)
                # Validate the entire append before mutating UI state.
                project = reconcile_project(project)
                self.replace_data(project)
                self.changed()
            except Exception as exc:
                self.error(exc)

    def export_rows(self, rows, default):
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", default, "CSV (*.csv)")
        if path:
            write_csv(path, self.columns(), rows)
            self.message.setText(f"已导出：{path}")

    def export_observed(self):
        try:
            self.project = self.collect()
            self.export_rows(self.project["observations"], "observations.csv")
        except Exception as exc:
            self.error(exc)

    def export_pending(self):
        try:
            self.project = self.collect()
            self.export_rows(self.project["pending"], "next_experiments.csv")
        except Exception as exc:
            self.error(exc)

    def pending_to_observed(self):
        try:
            selected = [copy.deepcopy(self.project["pending"][row]) for row in sorted({index.row() for index in self.pending.selectedIndexes()})]
            self.project = self.collect()
            self.render_data()
            for row in selected:
                if row in self.project["pending"]:
                    self.put_row(self.observed, [row.get(k, "") for k in self.columns()])
            self.tabs.setCurrentIndex(0)
            self.changed()
        except Exception as exc:
            self.error(exc)

    def withdraw_pending(self):
        try:
            selected = [copy.deepcopy(self.project["pending"][row]) for row in sorted({index.row() for index in self.pending.selectedIndexes()})]
            project = self.collect()
            project["pending"] = [p for p in project.get("pending", []) if p not in selected]
            self.replace_data(project)
            self.changed()
        except Exception as exc:
            self.error(exc)

    def run(self, operation="recommend"):
        try:
            self.project = self.collect()
            self.render_data()
            self.temporary = QTemporaryDir(str(Path(tempfile.gettempdir()) / "nanobo-XXXXXX"))
            if not self.temporary.isValid():
                raise RuntimeError("无法创建计算临时目录。")
            folder = Path(self.temporary.path()).resolve()
            self.result_path = folder / "result.json"
            request_path = folder / "request.json"
            self.operation = operation
            request = copy.deepcopy(self.project)
            request.update(_modeling_v2=True, _operation=operation, _diagnostics=operation == "analyze")
            save_project(request_path, request)
            command, args = self.worker_command(request_path, self.result_path)
            self.logs.clear()
            self.logs.appendPlainText(f"正在运行 {self.project['engine']}；首次启动可能需要较长时间。")
            self.cancelled = False
            self.process = QProcess(self)
            if not getattr(sys, "frozen", False):
                environment = QProcessEnvironment.systemEnvironment()
                environment.insert("PYTHONPATH", str(resources() / "src") + (os.pathsep + environment.value("PYTHONPATH") if environment.contains("PYTHONPATH") else ""))
                self.process.setProcessEnvironment(environment)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_log)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.process_error)
            self.busy(True)
            self.process.start(command, args)
        except Exception as exc:
            self.error(exc)

    def worker_command(self, request_path, result_path):
        if self.project["engine"] == "bo-mcp":
            binary = resources() / "engines" / "modern" / ("chembo-modern-worker.exe" if sys.platform == "win32" else "chembo-modern-worker")
            if binary.exists():
                return str(binary), [str(request_path), str(result_path)]
            python = resources() / ".venv-modern" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            if not python.exists():
                raise RuntimeError("当前安装包未包含 BoTorch 引擎。请安装完整版。")
            return str(python), [str(resources() / "src/chembo/modern_worker.py"), str(request_path), str(result_path)]
        if getattr(sys, "frozen", False):
            return sys.executable, ["--worker", str(request_path), str(result_path)]
        return sys.executable, ["-m", "chembo", "--worker", str(request_path), str(result_path)]

    def busy(self, value):
        for button in self.action_buttons:
            button.setEnabled(not value)
        self.generate.setEnabled(not value)
        self.analyze.setEnabled(not value and ENGINE_NAMES[self.engine.currentText()] == "bo-mcp")
        self.menuBar().setEnabled(not value)
        self.params.setEnabled(not value)
        self.objectives.setEnabled(not value)
        self.observed.setEnabled(not value)
        self.pending.setEnabled(not value)
        for widget in [self.name, self.notes, self.engine, self.seed, self.batch, self.task, self.labels]:
            widget.setEnabled(not value)
        self.progress.setVisible(value)
        self.cancel.setVisible(value)
        self.message.setText("模型计算中；可切换到运行日志查看进度。" if value else "计算结束。项目保存在本机。")
        if not value:
            self.refresh_task()

    def read_log(self):
        if self.process:
            self.logs.appendPlainText(bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace"))

    def process_error(self, error):
        if error == QProcess.FailedToStart:
            self.logs.appendPlainText(self.process.errorString())
            self.finished(-1, QProcess.CrashExit)

    def finished(self, code, status):
        if self.process is None:
            return
        self.read_log()
        self.process = None
        self.busy(False)
        if self.cancelled:
            self.message.setText("已取消计算，实验记录已保留。")
            return
        try:
            if not self.result_path.exists():
                raise RuntimeError("引擎未返回结果。请查看运行日志。")
            payload = json.loads(self.result_path.read_text(encoding="utf-8"))
            if not payload.get("ok"):
                if payload.get("diagnostic"):
                    self.logs.appendPlainText(payload["diagnostic"])
                raise RuntimeError(payload.get("error", "模型计算失败"))
            rows = payload.get("recommendations", [])
            updated = copy.deepcopy(self.project)
            updated.setdefault("pending", []).extend(rows)
            if "backend_state" in payload:
                updated["backend_state"] = payload["backend_state"]
            from datetime import datetime, timezone
            if payload.get("analysis"):
                updated["analysis"] = payload["analysis"]
            updated.setdefault("history", []).append({"operation": getattr(self, "operation", "recommend"), "time_utc": datetime.now(timezone.utc).isoformat(), "engine": updated["engine"], "seed": updated["seed"], "observations": len(updated["observations"]), "recommendations": rows, "provenance": payload.get("provenance"), "warnings": payload.get("warnings", [])})
            self.project = validate_project(updated)
            self.render_data()
            self.changed()
            self.analysis_view.set_analysis(payload.get("analysis", {}), self.project)
            analyzing = getattr(self, "operation", "recommend") == "analyze"
            self.tabs.setCurrentIndex(self.analysis_tab if analyzing else 1)
            self.message.setText("模型分析与验证已完成；结果见“模型与可视化”，请保存项目。" if analyzing else f"已生成 {len(rows)} 个待实验条件。可查看预测与排序、导出配方后回填结果。")
            for warning in payload.get("warnings", []):
                self.logs.appendPlainText(str(warning))
        except Exception as exc:
            self.tabs.setCurrentIndex(self.log_tab)
            self.error(exc)

    def cancel_run(self):
        if self.process:
            self.cancelled = True
            self.process.kill()

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 NaNoBO")
        dialog.resize(640, 440)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(f"NaNoBO {__version__}\n\n独立开发的本地实验规划界面，并非上游团队官方桌面产品。\n\nGryffin — Apache-2.0，Copyright (C) 2020 Harvard University\nAtlas — MIT，Copyright (c) 2022 rileyhickman\nBO-MCP — MIT，Copyright (c) 2026 Willi Gottstein\nChimera / Olympus / Golem — 见随附上游许可证\nQt / PySide6 — LGPLv3，动态链接；可重建、替换相容库。\n\n初始点属于实验设计；有足够实测数据后才由模型指导推荐。\n推荐值不是已验证的实验结果，也不保证最优。\n\n源代码、依赖锁定、重建说明及完整第三方声明随项目提供。\n发表科研结果时请引用实际使用的算法论文。")
        layout.addWidget(text)
        licenses = QPushButton("打开随附许可证文件夹")
        licenses.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resources() / "licenses"))))
        layout.addWidget(licenses)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def closeEvent(self, event):
        if self.preserve():
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NaNoBO")
    app.setOrganizationName("NaNoBO")
    app.setFont(QFont("PingFang SC" if sys.platform == "darwin" else "Segoe UI", 11))
    app.setStyleSheet("""
        QMainWindow, QWidget { background: #fcfdfb; color: #233d34; }
        QLabel#title { font-size: 25px; font-weight: 700; }
        QLabel#muted { color: #6b7c75; font-size: 11px; }
        QLabel#section { font-size: 15px; font-weight: 650; padding-top: 10px; }
        QLabel#banner { background: #eaf3ee; padding: 11px; border-radius: 8px; color: #235b49; }
        QPushButton { border: 1px solid #d3dfd8; border-radius: 6px; padding: 7px 10px; background: #f6f9f6; }
        QPushButton:hover { background: #e9f2ec; }
        QPushButton#primary { color: white; background: #237b63; padding: 12px 20px; font-size: 15px; font-weight: 650; }
        QPushButton:disabled { color: #93a29a; background: #e5ebe7; }
        QLineEdit, QSpinBox, QComboBox, QPlainTextEdit { border: 1px solid #d3dfd8; border-radius: 5px; padding: 5px; background: white; }
        QTableWidget { background: white; alternate-background-color: #f6f9f6; gridline-color: #e5ebe7; border: 1px solid #dce5df; selection-background-color: #d4eadd; selection-color: #173d2e; }
        QHeaderView::section { background: #eef4ef; border: 0; padding: 7px; color: #3f5e50; }
        QTabWidget::pane { border: 1px solid #dce5df; border-radius: 5px; }
        QTabBar::tab { padding: 10px 16px; background: #f0f4f0; }
        QTabBar::tab:selected { background: #e0eee5; color: #176449; }
    """)
    window = Window()
    window.show()
    return app.exec()
