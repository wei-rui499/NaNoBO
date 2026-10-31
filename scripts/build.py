"""Build the current native platform. Requires the separately built modern worker."""
import os
import importlib.util
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    modern_name = "chembo-modern-worker.exe" if sys.platform == "win32" else "chembo-modern-worker"
    modern_folder = ROOT / "dist-modern" / "chembo-modern-worker"
    modern = modern_folder / modern_name
    if not modern.is_file():
        raise SystemExit("Build the Python 3.13 modern worker first: scripts/build_modern.py")
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "cache")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_icon.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_licenses.py"), "classic"], check=True)
    arguments = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--windowed", "--onedir", "--name", "NaNoBO", "--paths", str(ROOT / "src"), "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"), "--specpath", str(ROOT / "build"), "--add-data", f"{ROOT / 'licenses'}{os.pathsep}licenses", "--add-data", f"{modern_folder}{os.pathsep}engines/modern", "--collect-all", "gryffin", "--collect-all", "atlas", "--collect-all", "olympus", "--collect-all", "golem", "--collect-all", "chimera", "--hidden-import", "PySide6.QtSvg", "--hidden-import", "pymoo.algorithms.soo.nonconvex.ga", "--hidden-import", "pymoo.operators.sampling.rnd", "--hidden-import", "pymoo.operators.crossover.sbx", "--hidden-import", "pymoo.operators.mutation.pm", "--hidden-import", "pymoo.termination.default", "--exclude-module", "tkinter", "--exclude-module", "pytest", "--exclude-module", "IPython", "--exclude-module", "jupyterlab", "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets", "--exclude-module", "PySide6.QtWebEngineQuick", "--exclude-module", "tensorflow", "--exclude-module", "tensorflow_probability"]
    if sys.platform == "darwin":
        arguments += ["--osx-bundle-identifier", "org.nanobo.studio", "--icon", str(ROOT / "assets" / "NaNoBO.icns")]
    elif sys.platform == "win32":
        arguments += ["--icon", str(ROOT / "assets" / "NaNoBO.ico")]
    # Olympus has optional legacy planners that intentionally exit on import.
    for index in range(len(arguments) - 2, -1, -1):
        if arguments[index:index + 2] == ["--collect-all", "olympus"]:
            del arguments[index:index + 2]
    arguments += ["--additional-hooks-dir", str(ROOT / "scripts" / "hooks")]
    arguments += ["--runtime-hook", str(ROOT / "scripts" / "runtime_init.py")]
    arguments += ["--copy-metadata", "moocore", "--exclude-module", "Cython"]
    arguments += ["--hidden-import", "matplotlib.backends.backend_qtagg", "--hidden-import", "matplotlib.backends.backend_pdf", "--hidden-import", "matplotlib.backends.backend_svg", "--hidden-import", "mpl_toolkits.mplot3d", "--collect-all", "openpyxl", "--collect-all", "xlrd", "--collect-all", "pymoo", "--collect-all", "autograd"]
    qt_package = Path(importlib.util.find_spec("PySide6").origin).parent
    qt_plugins = qt_package / ("plugins" if sys.platform == "win32" else "Qt/plugins")
    # Explicit file enumeration also sees macOS hidden flags inherited from uv's cache.
    # Qt's plugin discovery can otherwise silently omit every platform plugin.
    qt_destination = "PySide6/plugins" if sys.platform == "win32" else "PySide6/Qt/plugins"
    for kind in ("platforms", "imageformats"):
        for plugin in (qt_plugins / kind).iterdir():
            if plugin.suffix in (".dylib", ".dll", ".so") and "qpdf" not in plugin.stem.lower() and " " not in plugin.stem:
                arguments += ["--add-binary", f"{plugin}{os.pathsep}{qt_destination}/{kind}"]
    # Keep the Python 3.13 runtime out of the Python 3.10 dependency analysis.
    # Otherwise PyInstaller can relink nested extensions against the wrong Python.
    modern_option = f"{modern_folder}{os.pathsep}engines/modern"
    index = arguments.index(modern_option)
    del arguments[index - 1:index + 1]
    if "--incremental" in sys.argv:
        arguments.remove("--clean")
    arguments.append(str(ROOT / "src" / "chembo" / "__main__.py"))
    subprocess.run(arguments, cwd=ROOT, check=True)
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    if sys.platform == "darwin":
        app = ROOT / "dist" / "NaNoBO.app"
        plist_path = app / "Contents" / "Info.plist"
        with plist_path.open("rb") as stream:
            info = plistlib.load(stream)
        info.update(CFBundleName="NaNoBO", CFBundleDisplayName="NaNoBO", CFBundleShortVersionString="0.2.1", CFBundleVersion="0.2.1", LSMinimumSystemVersion="14.0", NSHighResolutionCapable=True)
        with plist_path.open("wb") as stream:
            plistlib.dump(info, stream)
        destination = app / "Contents" / "Resources" / "engines" / "modern"
        shutil.copytree(modern_folder, destination, symlinks=True, dirs_exist_ok=True)
        # uv's macOS cache can mark wheel files hidden; Qt skips hidden platform plugins.
        subprocess.run(["chflags", "-R", "nohidden", str(app)], check=True)
        if "--bundle-only" in sys.argv:
            print(f"Bundle assembled: {app}; final signing is performed by scripts/package_macos.py")
            return
        subprocess.run([sys.executable, str(ROOT / "scripts" / "package_macos.py")], check=True)
    else:
        destination = ROOT / "dist" / "NaNoBO" / "_internal" / "engines" / "modern"
        shutil.copytree(modern_folder, destination, symlinks=True, dirs_exist_ok=True)
        print("Native folder ready: dist/NaNoBO. Build scripts/build_installer.iss with Inno Setup.")


if __name__ == "__main__":
    main()
