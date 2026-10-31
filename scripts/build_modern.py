"""Run with the native Python 3.13 modern environment on macOS or Windows.

    .venv-modern/bin/python scripts/build_modern.py               # macOS
    .venv-modern\\Scripts\\python.exe scripts\\build_modern.py    # Windows

PyInstaller builds for the current operating system and architecture; no WSL.
The complete dist-modern/chembo-modern-worker directory belongs in the app;
keep its _internal directory next to the executable.
"""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if sys.version_info < (3, 13):
    raise SystemExit("BO-MCP worker requires native Python 3.13 or later.")
environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(root / "build-modern" / "cache"))
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
    "--name", "chembo-modern-worker", "--paths", str(root / "src"),
    "--collect-all", "bo_engine", "--copy-metadata", "bo-engine",
    "--collect-submodules", "botorch", "--collect-submodules", "gpytorch",
    "--collect-submodules", "scipy._external",
    "--collect-submodules", "sklearn.externals.array_api_compat",
    "--distpath", str(root / "dist-modern"),
    "--workpath", str(root / "build-modern"),
    "--specpath", str(root / "build-modern"),
    str(root / "src" / "chembo" / "modern_worker.py"),
], cwd=root, env=environment, check=True)
