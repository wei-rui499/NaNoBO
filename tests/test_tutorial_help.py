import importlib.util
from pathlib import Path
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import typing_extensions  # Same initialization order as the bundled Qt runtime.
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from chembo import __version__
from chembo.app import QDesktopServices, Window


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    window = Window()
    yield window
    window.dirty = False
    window.close()


def test_help_opens_bundled_offline_languages(window, tmp_path, monkeypatch):
    import chembo.app as module
    guide = tmp_path / "docs/html"
    guide.mkdir(parents=True)
    for name in ("TUTORIAL.zh-CN.html", "TUTORIAL.en.html"):
        (guide / name).write_text("<html>guide</html>")
    monkeypatch.setattr(module, "resources", lambda: tmp_path)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    window.open_tutorial("zh-CN")
    window.open_tutorial("en")
    assert [Path(p).name for p in opened] == ["TUTORIAL.zh-CN.html", "TUTORIAL.en.html"]
    assert all(Path(p).is_file() for p in opened)


def test_export_tutorial_preserves_existing_user_copy(window, tmp_path, monkeypatch):
    import chembo.app as module
    resources = tmp_path / "bundle"
    source = resources / "examples/tutorial/01_quickstart"
    source.mkdir(parents=True)
    (source / "project.chembo.json").write_text('{"synthetic":true}')
    destination = tmp_path / "user"
    destination.mkdir()
    original = destination / f"NaNoBO-tutorial-{__version__}"
    original.mkdir()
    (original / "my-results.csv").write_text("precious measured results")
    monkeypatch.setattr(module, "resources", lambda: resources)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(destination))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda *args: True)
    window.export_tutorial_data()
    assert (original / "my-results.csv").read_text() == "precious measured results"
    assert (destination / f"NaNoBO-tutorial-{__version__} (2)/01_quickstart/project.chembo.json").read_text() == '{"synthetic":true}'


def test_render_guides_keeps_offline_links_tables_and_code(tmp_path):
    spec = importlib.util.spec_from_file_location("render_guides", Path(__file__).resolve().parents[1] / "scripts/render_guides.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "TUTORIAL.zh-CN.md").write_text("# 中文教程\n\n## 导入数据\n\n[English](TUTORIAL.en.md)\n\n| a | b |\n|---|---|\n|1|2|\n\n```\nx < 2\n```\n")
    (docs / "TUTORIAL.en.md").write_text("# English\n\n[中文](TUTORIAL.zh-CN.md)\n")
    output = module.render_guides(tmp_path)
    text = (output / "TUTORIAL.zh-CN.html").read_text()
    assert 'href="TUTORIAL.en.html"' in text
    assert '<table>' in text and 'x &lt; 2' in text
    assert 'href="#导入数据"' in text
    assert (output / "index.html").is_file()
