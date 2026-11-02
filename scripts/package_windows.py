"""Compile the Windows installer and portable ZIP without running the application.

This is a publisher command for native Windows. File/ZIP integrity checks do
not claim that the models or graphical application have been tested on Windows.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from build_support import app_version

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_inventory(bundle):
    """Check required distributed files, without importing or executing them."""
    bundle = Path(bundle)
    required = [
        "NaNoBO.exe", "_internal/python310.dll",
        "_internal/engines/modern/chembo-modern-worker.exe",
        "_internal/engines/modern/_internal/python313.dll",
        "_internal/docs/html/index.html",
        "_internal/docs/html/TUTORIAL.zh-CN.html",
        "_internal/docs/html/TUTORIAL.en.html",
        "_internal/licenses/classic/dependency-inventory.json",
        "_internal/licenses/modern/dependency-inventory.json",
        "_internal/LICENSE", "_internal/ACKNOWLEDGMENTS.md",
        "_internal/THIRD_PARTY_NOTICES.md", "_internal/CITATION.cff",
        "_internal/REFERENCES.bib",
    ]
    for name in required:
        path = bundle / name
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"Required packaged file is missing or empty: {name}")
    resources = bundle / "_internal"
    extensions = []
    for pattern in ("kernel_evaluations*.pyd", "kernel_prob_reshaping*.pyd", "qwindows.dll"):
        matches = list(resources.rglob(pattern))
        if not matches:
            raise RuntimeError(f"Required native extension/platform plugin is absent: {pattern}")
        extensions.extend(p.relative_to(bundle).as_posix() for p in matches)
    examples = list((resources / "examples/tutorial").rglob("*.chembo.json"))
    if len(examples) < 4:
        raise RuntimeError("The four tutorial project exercises have not been bundled")
    return {"required_files": required, "native_files": sorted(extensions), "tutorial_projects": len(examples)}


def zip_tree(folder, target, prefix, compression=zipfile.ZIP_DEFLATED):
    folder, target = Path(folder), Path(target)
    with zipfile.ZipFile(target, "w", compression=compression, allowZip64=True) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                if path.is_symlink():
                    raise RuntimeError(f"Unexpected symbolic link in Windows distribution: {path}")
                archive.write(path, (Path(prefix) / path.relative_to(folder)).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"Archive CRC check failed: {target.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 7/ISCC.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "installers")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Windows packages must be compiled on native Windows, without WSL.")
    if not args.compiler.is_file():
        raise SystemExit("Inno Setup 7 compiler is missing; pass --compiler with its ISCC.exe path.")
    version = app_version(ROOT)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle = ROOT / "dist/NaNoBO"
    inventory = bundle_inventory(bundle)
    subprocess.run([
        str(args.compiler), f"/DAppVersion={version}", f"/DDistDir={bundle}",
        f"/O{output}", str(ROOT / "scripts/build_installer.iss"),
    ], check=True, cwd=ROOT)
    installer = output / f"NaNoBO-{version}-windows-x64-setup-unsigned.exe"
    if not installer.is_file() or installer.stat().st_size < 1024 * 1024:
        raise RuntimeError("The native installer was not produced")
    with installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError("The installer does not have a Windows PE header")
    portable = output / f"NaNoBO-{version}-windows-x64-portable-unsigned.zip"
    zip_tree(bundle, portable, "NaNoBO")
    # Attach the exact build input, rather than promising that a Mac archive
    # contains the generated Windows extension source/metadata.
    subprocess.run([sys.executable, str(ROOT / "scripts/source_archive.py")], check=True, cwd=ROOT)
    source = ROOT / "release" / f"NaNoBO-{version}-source.zip"
    if not source.is_file():
        raise RuntimeError(f"Matching source archive is missing: {source.name}")
    windows_source = output / f"NaNoBO-{version}-windows-source.zip"
    shutil.copy2(source, windows_source)
    corresponding = ROOT / "release/library-sources"
    if not (corresponding / "SOURCE-ARCHIVES.json").is_file():
        raise RuntimeError("Fetch exact corresponding library sources before Windows packaging")
    library_source = output / f"NaNoBO-{version}-windows-library-sources.zip"
    zip_tree(corresponding, library_source, "library-sources", zipfile.ZIP_STORED)
    asset_paths = [installer, portable, windows_source, library_source]
    for name in ("LICENSE", "ACKNOWLEDGMENTS.md", "THIRD_PARTY_NOTICES.md", "CITATION.cff", "REFERENCES.bib"):
        shutil.copy2(ROOT / name, output / name)
        asset_paths.append(output / name)
    report = {
        "product": "NaNoBO", "version": version, "platform": "Windows", "architecture": "x64",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": os.environ.get("GITHUB_SHA"),
        "status": "BUILD_ONLY_RUNTIME_UNVERIFIED",
        "application_started": False, "models_executed": False,
        "installer_executed": False,
        "runtime_validation": "Not run, as requested; the user will test the Windows application.",
        "file_presence_checks": inventory,
        "portable_zip_crc": "passed", "installer_pe_header": "passed",
        "code_signature": "unsigned",
        "assets": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in asset_paths},
        "dependencies": {kind: [{"name": item["name"], "version": item["version"]} for item in json.loads((bundle / "_internal/licenses" / kind / "dependency-inventory.json").read_text(encoding="utf-8"))] for kind in ("classic", "modern")},
    }
    evidence = output / f"WINDOWS_BUILD-{version}.json"
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksums = [sha256(p) + "  " + p.name for p in sorted(asset_paths + [evidence])]
    (output / f"SHA256SUMS-windows-{version}.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"Windows build-only artifacts: {output}; application/runtime not tested.")


if __name__ == "__main__":
    main()
