"""Collect exact installed dependency license files and inventory for each build."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    environment = sys.argv[1] if len(sys.argv) > 1 else "classic"
    destination = ROOT / "licenses" / environment
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    records = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata.get("Name", "").lower()):
        name, version = dist.metadata["Name"], dist.version
        record = {"name": name, "version": version, "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"), "classifiers": [c for c in dist.metadata.get_all("Classifier", []) if c.startswith("License")], "homepage": dist.metadata.get("Home-page"), "files": []}
        for file in dist.files or []:
            relative = Path(str(file))
            if any(part == ".." for part in relative.parts):
                continue
            lower = relative.name.lower()
            if lower.startswith(("license", "licence", "copying", "notice", "copyright")) and not lower.endswith((".py", ".pyc")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = destination / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    record["files"].append(str(target.relative_to(destination)))
        records.append(record)
    (destination / "dependency-inventory.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    # Python's own license is not necessarily represented by a wheel distribution.
    import sysconfig
    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    for candidate in (python_license, Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
        if candidate.is_file():
            shutil.copy2(candidate, destination / "PYTHON-LICENSE.txt")
            break
    print(f"{environment}: {len(records)} distributions, {sum(len(r['files']) for r in records)} license/notice files")


if __name__ == "__main__":
    main()
