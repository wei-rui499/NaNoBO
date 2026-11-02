"""Install, execute and uninstall a native Windows package using synthetic data.

This is a publisher acceptance tool. Ordinary users only run the installer.
Every calculation uses the installed executables with development environment
variables removed and no Python/compiler locations on their PATH.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

for stream in (sys.stdout, sys.stderr):
    if callable(getattr(stream, "reconfigure", None)):
        stream.reconfigure(encoding="utf-8", errors="replace")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-record", type=Path)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("This acceptance runs only on native Windows")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit("Use an empty output directory; existing project files are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    installed = output / "安装 验收" / "NaNoBO"
    preserved = output / "user-project.chembo.json"
    preserved.write_bytes((ROOT / "examples/tutorial/01_quickstart/project.chembo.json").read_bytes())
    preserved_hash = digest(preserved)
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING", "VIRTUAL_ENV", "CONDA_PREFIX"):
        environment.pop(key, None)
    environment["PATH"] = os.environ["SystemRoot"] + os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")
    environment["QT_QPA_PLATFORM"] = "offscreen"
    report = {"ok": False, "data_status": "SYNTHETIC", "installer_sha256": digest(args.installer),
              "created_utc": datetime.now(timezone.utc).isoformat(), "checks": {}}
    started = time.monotonic()
    try:
        install = subprocess.run([str(args.installer.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/NOICONS",
                                  "/LANG=chinesesimp", "/DIR=" + str(installed), "/LOG=" + str(output / "install.log")],
                                 cwd=output, env=environment, timeout=600)
        report["checks"]["install"] = {"exit_code": install.returncode, "executable_present": (installed / "NaNoBO.exe").is_file()}
        if install.returncode or not (installed / "NaNoBO.exe").is_file():
            raise RuntimeError("The user installer failed")
        report["installed_executable_sha256"] = digest(installed / "NaNoBO.exe")
        print("PASS ordinary-user installation into a Chinese/spaces path", flush=True)
        native = subprocess.run([sys.executable, str(ROOT / "scripts/validate_windows_runtime.py"),
                                 "--bundle", str(installed), "--output", str(output / "runtime"), "--fail-fast"],
                                cwd=ROOT, env=environment, capture_output=True, timeout=1800)
        (output / "runtime-stdout.txt").write_bytes(native.stdout)
        (output / "runtime-stderr.txt").write_bytes(native.stderr)
        runtime_path = output / "runtime/acceptance-results.json"
        if runtime_path.exists():
            report["checks"]["native_models"] = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime = report["checks"].get("native_models", {})
        if native.returncode or not runtime.get("total") or runtime.get("passed") != runtime["total"]:
            raise RuntimeError("Installed native-model acceptance failed; see runtime logs")
        print(f"PASS installed native workflows: {runtime['passed']}/{runtime['total']}", flush=True)
        ui_path = output / "frozen-ui-results.json"
        ui = subprocess.run([str(installed / "NaNoBO.exe"), "--verify-ui", str(ui_path)], cwd=output,
                            env=environment, capture_output=True, timeout=480)
        (output / "gui-stdout.txt").write_bytes(ui.stdout)
        (output / "gui-stderr.txt").write_bytes(ui.stderr)
        if ui_path.exists():
            report["checks"]["frozen_gui"] = json.loads(ui_path.read_text(encoding="utf-8"))
        gui = report["checks"].get("frozen_gui", {})
        if ui.returncode or not gui.get("ok"):
            raise RuntimeError("Installed GUI/worker/file-export acceptance failed")
        cases = {item["case"] for item in gui.get("checks", [])}
        expected = {"gryffin", "atlas", "bo-mcp", "recipe", "pareto", "classification",
                    "pareto-validation", "classification-validation", "frozen-import-csv",
                    "frozen-import-xls", "frozen-import-xlsx", "frozen-plot-and-table-exports"}
        if not expected <= cases:
            raise RuntimeError("Installed GUI acceptance omitted required workflows")
        print("PASS installed Qt handoff, Excel/CSV readers and PNG/PDF/SVG exports", flush=True)
        report["ok"] = True
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        uninstaller = installed / "unins000.exe"
        if uninstaller.exists():
            try:
                removal = subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                                          "/LOG=" + str(output / "uninstall.log")], cwd=output, env=environment, timeout=300)
                report["checks"]["uninstall"] = {
                    "exit_code": removal.returncode,
                    "executable_removed": not (installed / "NaNoBO.exe").exists(),
                    "user_project_preserved": preserved.is_file() and digest(preserved) == preserved_hash,
                }
                if removal.returncode or not all(report["checks"]["uninstall"][name] for name in ("executable_removed", "user_project_preserved")):
                    report["ok"] = False
                    report["uninstall_error"] = "Removal or user-project preservation failed"
            except Exception as exc:
                report["ok"] = False
                report["uninstall_error"] = str(exc)
        else:
            report["ok"] = False
            report["uninstall_error"] = "The installed uninstaller is missing"
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        (output / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["ok"] and args.build_record:
        record_path = args.build_record.resolve()
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record.update(status="WINDOWS_RUNTIME_VALIDATED", application_started=True, models_executed=True,
                      installer_executed=True, runtime_validation="Native installed-model, GUI, file-format and uninstall acceptance passed",
                      windows_acceptance=report)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checksum_path = record_path.parent / ("SHA256SUMS-windows-" + record["version"] + ".txt")
        if checksum_path.exists():
            lines = checksum_path.read_text(encoding="utf-8").splitlines()
            replacement = digest(record_path) + "  " + record_path.name
            lines = [replacement if line.endswith("  " + record_path.name) else line for line in lines]
            checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report": str(output / "REPORT.json"), "error": report.get("error")}, ensure_ascii=False), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
