"""Publisher helper: reproduce exact LGPL library source attachments, hash checked."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def source_records(root=ROOT):
    manifest = root / "docs" / "manifests" / "library-sources.json"
    records = json.loads(manifest.read_text(encoding="utf-8"))
    alternatives = json.loads((root / "docs/manifests/library-source-alternatives.json").read_text(encoding="utf-8"))["items"]
    for index, item in enumerate(records["items"]):
        if item["component"] != "moocore":
            continue
        try:
            installed = metadata.version("moocore")
        except metadata.PackageNotFoundError:
            raise RuntimeError("Install the publisher dependencies before selecting corresponding sources")
        if installed != item["version"]:
            exact = next((a for a in alternatives if a["component"] == "moocore" and a["version"] == installed), None)
            if exact is None:
                raise RuntimeError(f"No verified corresponding source is recorded for installed moocore {installed}")
            records["items"][index] = exact
    return records


def main():
    records = source_records()
    folder = ROOT / "release" / "library-sources"
    folder.mkdir(parents=True, exist_ok=True)
    checksums = []
    for item in records["items"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid archive path")
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            print("Downloading", item["component"], item["version"], flush=True)
            request = urllib.request.Request(item["url"], headers={"User-Agent": "NaNoBO-build/0.1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"Archive checksum mismatch: {relative}")
            target.write_bytes(data)
        checksums.append(item["sha256"] + "  " + str(relative).replace("\\", "/"))
    (folder / "SOURCE-ARCHIVES.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(folder)


if __name__ == "__main__":
    main()
