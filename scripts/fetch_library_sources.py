"""Publisher helper: reproduce exact LGPL library source attachments, hash checked."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = ROOT / "docs" / "manifests" / "library-sources.json"
    records = json.loads(manifest.read_text(encoding="utf-8"))
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
    shutil.copy2(manifest, folder / "SOURCE-ARCHIVES.json")
    (folder / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(folder)


if __name__ == "__main__":
    main()
