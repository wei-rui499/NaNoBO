"""Structured recipe constraint editor; never evaluates user expressions."""
import copy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from chembo.engine import read_candidates, validate_project
from chembo.table_io import sheet_names


def choose_sheet(parent, path):
    names = sheet_names(path)
    if len(names) <= 1:
        return names[0] if names else None
    name, accepted = QInputDialog.getItem(parent, "选择工作表", "读取工作表", names, 0, False)
    return name if accepted else False


def number(value=0):
    widget = QDoubleSpinBox()
    widget.setDecimals(8)
    widget.setRange(-1e12, 1e12)
    widget.setValue(value)
    return widget


class RecipeDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = copy.deepcopy(project)
        self.project['engine'] = 'bo-mcp'
        self.setWindowTitle("可执行配方空间")
        self.resize(760, 570)
        layout = QVBoxLayout(self)
        intro = QLabel("步长在变量表中设置。这里设置总量／线性约束、配比和合法候选配方。\n应用后使用 BoTorch；生成条件必须同时满足全部规则。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.table = QTableWidget(0, 1)
        self.table.setHorizontalHeaderLabels(["已启用的联合约束"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        for title, callback in [("＋ 总量／线性", self.add_linear), ("＋ 配比", self.add_ratio), ("删除选中规则", self.remove)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.candidate_label = QLabel()
        self.candidate_label.setWordWrap(True)
        layout.addWidget(self.candidate_label)
        self.preview = QTableWidget()
        self.preview.setMaximumHeight(170)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.preview)
        row = QHBoxLayout()
        for title, callback in [("导入合法候选表（Excel / CSV）", self.import_candidates), ("清除候选表", self.clear_candidates)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        note = QLabel("候选表只含变量列，表头与变量名一致；历史实验可来自表外，下一批仅从候选表选择。配比的分母为 0 时不合法。")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("应用（使用 BoTorch）")
        buttons.accepted.connect(self.accept_checked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self):
        constraints = self.project.get('constraints', [])
        self.table.setRowCount(len(constraints))
        for i, rule in enumerate(constraints):
            if rule['kind'] == 'linear':
                expression = ' + '.join(f"{v:g} × {k}" for k, v in rule['coefficients'].items())
                text = f"{expression}  {dict(eq='=', le='≤', ge='≥')[rule['relation']]}  {rule['rhs']:g}"
            else:
                text = f"{rule['numerator']} / {rule['denominator']}：{rule.get('low', '不限')} ～ {rule.get('high', '不限')}"
            self.table.setItem(i, 0, QTableWidgetItem(text))
        rows = self.project.get('candidates', [])
        names = [p['name'] for p in self.project['parameters']]
        self.candidate_label.setText(f"合法候选表：{len(rows)} 个配方（下方预览前 30 行）" if rows else "未设置候选表：从变量范围／步长和约束构建候选。")
        self.preview.setColumnCount(len(names))
        self.preview.setHorizontalHeaderLabels(names)
        self.preview.setRowCount(min(30, len(rows)))
        for i, values in enumerate(rows[:30]):
            for j, name in enumerate(names):
                self.preview.setItem(i, j, QTableWidgetItem(str(values[name])))
        self.preview.resizeColumnsToContents()

    def numeric_names(self):
        return [p['name'] for p in self.project['parameters'] if p['type'] != 'categorical']

    def add_linear(self):
        names = self.numeric_names()
        if not names:
            QMessageBox.warning(self, "需要数值变量", "总量／线性约束需要至少一个数值变量。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("总量／线性约束")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("填写各变量的系数；总量约束将参与求和的变量设为 1，其余设为 0。"))
        form = QFormLayout()
        coefficients = {name: number(1) for name in names}
        for name, widget in coefficients.items():
            form.addRow(name, widget)
        relation = QComboBox()
        relation.addItems(["=", "≤", "≥"])
        rhs = number(1)
        form.addRow("关系", relation)
        form.addRow("右侧数值（原始单位）", rhs)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            rule = dict(kind='linear', coefficients={key: widget.value() for key, widget in coefficients.items() if widget.value()}, relation=['eq','le','ge'][relation.currentIndex()], rhs=rhs.value())
            if not rule['coefficients']:
                QMessageBox.warning(self, "系数不能为空", "至少一个变量的系数需要非零。")
                return
            self.project.setdefault('constraints', []).append(rule)
            self.refresh()

    def add_ratio(self):
        names = self.numeric_names()
        if len(names) < 2:
            QMessageBox.warning(self, "需要两个数值变量", "配比约束需要两个不同的数值变量。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("配比范围")
        form = QFormLayout(dialog)
        numerator, denominator = QComboBox(), QComboBox()
        numerator.addItems(names)
        denominator.addItems(names)
        denominator.setCurrentIndex(1)
        low, high = number(0), number(1)
        form.addRow("分子", numerator)
        form.addRow("分母", denominator)
        form.addRow("最小配比", low)
        form.addRow("最大配比", high)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec():
            self.project.setdefault('constraints', []).append(dict(kind='ratio', numerator=numerator.currentText(), denominator=denominator.currentText(), low=low.value(), high=high.value()))
            self.refresh()

    def remove(self):
        for index in sorted({x.row() for x in self.table.selectedIndexes()}, reverse=True):
            del self.project['constraints'][index]
        self.refresh()

    def import_candidates(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入合法候选表", "", "实验数据 (*.xlsx *.xls *.csv)")
        if path:
            try:
                sheet = choose_sheet(self, path)
                if sheet is False:
                    return
                # Existing pending are checked when the whole dialog is applied.
                rows = read_candidates(self.project, path, sheet)
                self.project['candidates'] = rows
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "候选表未导入", str(exc))

    def clear_candidates(self):
        self.project.pop('candidates', None)
        self.refresh()

    def accept_checked(self):
        try:
            self.project = validate_project(self.project)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "请检查规则", str(exc))
