"""Publisher file checks only; these tests do not execute a Windows program."""
import importlib.util
from pathlib import Path
import zipfile

import pytest


@pytest.fixture
def packager(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("nanobo_windows_packager", scripts / "package_windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portable_keeps_runtime_and_tutorial_paths(packager, tmp_path):
    folder = tmp_path / "NaNoBO"
    expected = {"NaNoBO.exe": b"MZ fixture", "_internal/docs/html/TUTORIAL.en.html": b"Offline tutorial", "_internal/examples/tutorial/01.chembo.json": b'{"synthetic":true}'}
    for name, data in expected.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    target = tmp_path / "portable.zip"
    packager.zip_tree(folder, target, "NaNoBO")
    with zipfile.ZipFile(target) as archive:
        assert {name: archive.read("NaNoBO/" + name) for name in expected} == expected
        assert archive.testzip() is None


def test_incomplete_bundle_cannot_be_packaged(packager, tmp_path):
    (tmp_path / "NaNoBO.exe").write_bytes(b"MZ fixture")
    with pytest.raises(RuntimeError, match="python310.dll"):
        packager.bundle_inventory(tmp_path)


def test_unexpected_link_is_not_silently_published(packager, tmp_path):
    folder = tmp_path / "NaNoBO"
    folder.mkdir()
    (tmp_path / "outside.txt").write_text("outside the application")
    try:
        (folder / "outside.txt").symlink_to(tmp_path / "outside.txt")
    except OSError:
        pytest.skip("This test host cannot create symlinks")
    with pytest.raises(RuntimeError, match="symbolic link"):
        packager.zip_tree(folder, tmp_path / "portable.zip", "NaNoBO")
