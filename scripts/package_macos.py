"""Package an already tested native .app with source and library source archives."""
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import json
from datetime import datetime, timezone
from build_support import app_version

ROOT = Path(__file__).resolve().parents[1]
VERSION = app_version(ROOT)


def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)


def main():
    if sys.platform != "darwin":
        raise SystemExit("This installer is built on macOS only.")
    app = ROOT / "dist" / "NaNoBO.app"
    if not app.is_dir():
        raise SystemExit("Build the app first.")
    run(sys.executable, ROOT / "scripts" / "source_archive.py")
    # A clean temporary filesystem avoids Finder metadata being added while signing.
    temporary = tempfile.TemporaryDirectory(prefix="nanobo-dmg-")
    staging = Path(temporary.name)
    (staging / "Applications").symlink_to("/Applications")
    packaged_app = staging / app.name
    run("ditto", "--noextattr", "--norsrc", app, packaged_app)
    plist_path = packaged_app / "Contents" / "Info.plist"
    with plist_path.open("rb") as stream:
        info = plistlib.load(stream)
    info.update(CFBundleName="NaNoBO", CFBundleDisplayName="NaNoBO", CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION, LSMinimumSystemVersion="14.0", NSHighResolutionCapable=True)
    with plist_path.open("wb") as stream:
        plistlib.dump(info, stream)
    license_destination = packaged_app / "Contents" / "Resources" / "licenses"
    if license_destination.exists():
        shutil.rmtree(license_destination)
    shutil.copytree(ROOT / "licenses", license_destination)
    run("chflags", "-R", "nohidden", packaged_app)
    run("codesign", "--force", "--deep", "--sign", "-", packaged_app)
    run("codesign", "--verify", "--deep", "--strict", packaged_app)
    # A cached PYZ can otherwise survive an incremental source edit.
    source_checks = {}
    for python, executable, modules in [
        (sys.executable, packaged_app / "Contents/MacOS/NaNoBO", ["app", "engine", "space", "table_io", "recipe_dialog", "analysis_view", "verification", "examples"]),
        (ROOT / ".venv-modern/bin/python", packaged_app / "Contents/Resources/engines/modern/chembo-modern-worker", ["engine", "space", "modeling"]),
    ]:
        checked = subprocess.check_output([str(python), str(ROOT / "scripts/verify_frozen_sources.py"), str(executable), *modules], cwd=ROOT, text=True)
        source_checks.update(json.loads(checked))
    run(sys.executable, ROOT / "scripts" / "smoke_frozen.py", "--bundle", packaged_app)
    import os
    result = staging / "gui-verification.json"
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        environment.pop(key, None)
    subprocess.run([str(packaged_app / "Contents" / "MacOS" / "NaNoBO"), "--verify-ui", str(result)], check=True, env=environment, timeout=420)
    ui_report = json.loads(result.read_text(encoding="utf-8"))
    if not ui_report["ok"]:
        raise RuntimeError("Frozen GUI verification failed")
    result.unlink()
    source = staging / "Source-and-Licenses"
    source.mkdir()
    import xml.etree.ElementTree as ET
    regression_file = ROOT / "validation" / f"regression-{VERSION}.xml"
    suite = ET.parse(regression_file).getroot().find("testsuite")
    regression_report = {key: int(suite.attrib.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")}
    if regression_report["failures"] or regression_report["errors"]:
        raise RuntimeError("Current regression report contains failures")
    report = {"product": "NaNoBO", "version": VERSION, "time_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "architecture": platform.machine(), "signature": "ad-hoc verified, not Developer ID notarized", "frozen_model_cases_passed": 6, "gui_checks": ui_report["checks"], "frozen_code_matches_source": source_checks, "classic_tests": regression_report, "current_release_validation": json.loads((ROOT / "docs" / f"VALIDATION_V{VERSION}.json").read_text(encoding="utf-8"))}
    (source / "MAC_VALIDATION.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "release" / f"MAC_VALIDATION-{VERSION}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "release" / f"NaNoBO-{VERSION}-source.zip", source)
    shutil.copytree(ROOT / "licenses", source / "licenses")
    for name in ("ACKNOWLEDGMENTS.md", "THIRD_PARTY_NOTICES.md", "CITATION.cff", "REFERENCES.bib"):
        shutil.copy2(ROOT / name, source)
    tutorial = ROOT / "release" / f"NaNoBO-{VERSION}-tutorial-examples.zip"
    if tutorial.is_file():
        shutil.copy2(tutorial, source)
    library_sources = ROOT / "release" / "library-sources"
    if library_sources.is_dir():
        shutil.copytree(library_sources, source / "library-sources")
    shutil.copy2(ROOT / "docs" / "THIRD_PARTY.md", source)
    (staging / "安装说明-ReadMe.txt").write_text("将 NaNoBO.app 拖入 Applications。\n打开后点击“使用教程”，或从“帮助”选择 English tutorial。\n从“帮助 → 导出教程练习数据…”复制配套项目、CSV 和 Excel 到自己的文件夹。\n本地预览版采用 ad-hoc 签名，尚未经过 Apple Developer ID 公证。\n首次引擎冷启动可能需要约一分钟；无需安装 Python 或 WSL。\nSource-and-Licenses 包含应用源码、科研引用、第三方许可证和对应库源。\n\nDrag NaNoBO.app into Applications. Open Help → English tutorial.\nUse 帮助 → 导出教程练习数据… to copy the synthetic practice files to a writable folder.\nNo Python or WSL is needed. This preview has an ad-hoc signature and is not Apple-notarized.\n", encoding="utf-8")
    dmg = ROOT / "release" / f"NaNoBO-{VERSION}-macOS-{platform.machine()}.dmg"
    run("hdiutil", "create", "-volname", "NaNoBO", "-srcfolder", staging, "-ov", "-format", "UDZO", dmg)
    print(dmg)
    temporary.cleanup()


if __name__ == "__main__":
    main()
