"""Regression checks for the GUI's data handoff and safe portable files."""
import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import typing_extensions  # Match the frozen app's runtime initialization before Qt.
from PySide6.QtWidgets import QApplication
import pytest

from chembo.app import Window, example_project
from chembo.engine import read_observations
from chembo.storage import save_project, write_csv


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    result = Window()
    yield result
    result.dirty = False
    result.close()


def test_manual_pending_measurement_is_reconciled(window):
    project = example_project()
    project["pending"] = [{"x": 0.55, "category": "B"}, {"x": 0.77, "category": "A"}]
    window.set_project(project)
    window.put_row(window.observed, [0.55, "B", 0.88])
    collected = window.collect()
    assert len(collected["observations"]) == 6
    assert collected["pending"] == [{"x": 0.77, "category": "A"}]
    assert project["pending"] == [{"x": 0.55, "category": "B"}, {"x": 0.77, "category": "A"}]


def test_model_state_invalidated_by_engine_or_seed_change(window):
    project = example_project()
    project["backend_state"] = {"engine": "bo-mcp", "iteration": 2}
    window.set_project(project)
    assert "backend_state" in window.collect()
    window.seed.setValue(17)
    assert "backend_state" not in window.collect()


def test_renaming_parameter_cannot_relabel_old_measurements(window):
    window.params.item(0, 0).setText("new_x")
    with pytest.raises(ValueError):
        window.collect()


def test_incomplete_result_is_not_silently_dropped(window):
    window.put_row(window.observed, [0.55, "B", ""])
    with pytest.raises(ValueError):
        window.collect()


def test_withdraw_uses_values_when_measurement_changes_pending_indices(window):
    project = example_project()
    first, second, third = [{"x": x, "category": "B"} for x in (0.51, 0.52, 0.53)]
    project["pending"] = [first, second, third]
    window.set_project(project)
    window.put_row(window.observed, [first["x"], "B", 0.88])
    window.pending.selectRow(1)
    window.withdraw_pending()
    assert window.project["pending"] == [third]


def test_csv_categorical_formula_escape_round_trip(tmp_path):
    project = example_project()
    project["parameters"][1]["options"] = ["=untrusted()", "B"]
    project["observations"] = []
    row = {"x": 0.2, "category": "=untrusted()", "response": -0.2}
    path = tmp_path / "results.csv"
    write_csv(path, ["x", "category", "response"], [row])
    assert "'=untrusted()" in path.read_text(encoding="utf-8-sig")
    assert read_observations(project, path) == [row]


def test_atomic_project_round_trip(tmp_path):
    import json
    project = example_project()
    path = tmp_path / "project.json"
    save_project(path, project)
    assert json.loads(path.read_text()) == project
    assert list(tmp_path.iterdir()) == [path]


def test_save_as_preserves_original_project(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    import json
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    window.path = str(first)
    assert window.save()
    original = first.read_text()
    window.name.setText("第二个项目")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(second), ""))
    assert window.save(as_new=True)
    assert first.read_text() == original
    assert json.loads(second.read_text())["name"] == "第二个项目"
    assert window.path == str(second)


@pytest.mark.skipif(os.environ.get("CHEMBO_INTEGRATION") != "1", reason="Requires real scientific backends")
@pytest.mark.parametrize("engine", ["gryffin", "atlas", "bo-mcp"])
def test_gui_real_worker_handoff(window, app, monkeypatch, engine):
    from PySide6.QtCore import QEventLoop, QTimer
    project = example_project()
    project["engine"] = engine
    window.set_project(project)
    errors = []
    monkeypatch.setattr(window, "error", lambda exc: errors.append(str(exc)))
    loop = QEventLoop()
    poll, deadline = QTimer(), QTimer()
    poll.setInterval(25)
    poll.timeout.connect(lambda: loop.quit() if window.process is None else None)
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    window.run()
    poll.start()
    deadline.start(120000)
    loop.exec()
    poll.stop()
    deadline.stop()
    if window.process is not None:
        window.cancel_run()
        pytest.fail("GUI worker timed out")
    assert not errors, (errors, window.logs.toPlainText())
    assert len(window.project["pending"]) == 2
    assert len(window.project["history"][-1]["recommendations"]) == 2
