"""Publisher build setup, using native Python 3.10 on Windows/macOS (never WSL).

End users install the compiled application; they do not run this script.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "gryffin": ("the-matter-lab/gryffin", "fb149d18f9c81b96179cc682c46e05db60bc7229"),
    "atlas": ("the-matter-lab/atlas", "ebb1f4f728107f759c48289c2faecfa3af19254f"),
    "olympus-runtime": ("the-matter-lab/olympus", "def3dda70c981c667aed40a3e8a7d8143b284887"),
    "bo-mcp": ("AccelerationConsortium/bo-mcp", "56d590b91ac120d0f22a3e41e770843d271808cd"),
}


def retrieve(url):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NaNoBO-build/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def selected(package, path, size):
    if path.startswith(".") or "/." in path:
        return False
    if package == "bo-mcp":
        return path in ("LICENSE", "README.md") or path.startswith("packages/bo-engine/") and size < 300000
    root_files = {"setup.py", "setup.cfg", "pyproject.toml", "versioneer.py", "MANIFEST.in", "LICENSE", "LICENSE.md", "NOTICE", "NOTICE.md", "README.md", "requirements.txt", "extra_requirements.txt"}
    if "/" not in path:
        return path in root_files
    module = "olympus" if package == "olympus-runtime" else package
    if not path.startswith(f"src/{module}/"):
        return False
    # No 1+ GB benchmark dataset, trained emulator weights, or research notebooks.
    return path.endswith((".py", ".pyx", ".c", ".h", ".json", ".txt", ".yaml")) and size < 4000000


def fetch(package):
    repository, commit = PINS[package]
    target = ROOT / "upstream" / package
    marker = target / "UPSTREAM_REVISION"
    if marker.exists() and commit in marker.read_text(encoding="utf-8").splitlines():
        return target
    tree = json.loads(retrieve(f"https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1"))
    if tree.get("truncated"):
        raise RuntimeError(f"Truncated GitHub tree for {package}")
    entries = [item for item in tree["tree"] if item["type"] == "blob" and selected(package, item["path"], item.get("size", 0))]
    print(f"Fetching {package}: {len(entries)} verified source files", flush=True)
    def download(item):
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Invalid upstream path")
        destination = target / relative
        data = retrieve(f"https://raw.githubusercontent.com/{repository}/{commit}/{item['path']}")
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if digest != item["sha"]:
            raise RuntimeError(f"Source checksum mismatch: {package}/{relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(download, entries))
    marker.write_text(commit + "\n", encoding="utf-8")
    return target


def run(*args):
    subprocess.run([str(x) for x in args], check=True, cwd=ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--only", choices=list(PINS))
    args = parser.parse_args()
    packages = [args.only] if args.only else list(PINS)
    for package in packages:
        fetch(package)
    if args.fetch_only:
        return
    if sys.version_info[:2] != (3, 10):
        raise SystemExit("Classic publishers must use native Python 3.10.")
    run(sys.executable, "-m", "pip", "install", "-r", "requirements-classic.txt")
    gryffin = ROOT / "upstream" / "gryffin"
    for stem in ("kernel_evaluations", "kernel_prob_reshaping"):
        source = gryffin / "src" / "gryffin" / "bayesian_network" / (stem + ".pyx")
        run(sys.executable, "-m", "cython", "-3", source)
        generated = source.with_suffix(".c")
        content = generated.read_text(encoding="utf-8")
        generated.write_text("/* NaNoBO modification: regenerated from unchanged upstream .pyx with Cython 3.3.0 for native Python 3.10 compatibility. */\n" + content, encoding="utf-8")
    for package in ("gryffin", "olympus-runtime", "atlas"):
        if package == "olympus-runtime":
            for module in ("noises", "models", "planners", "surfaces", "scalarizers"):
                source = ROOT / "upstream" / package / "src" / "olympus" / module / "__init__.py"
                text = source.read_text(encoding="utf-8")
                original = "    def __getattr__(self, attr):\n"
                replacement = original + "        # NaNoBO fix: missing Python metadata is not an optimizer/plugin name.\n        if attr.startswith('__'):\n            raise AttributeError(attr)\n"
                if "# NaNoBO fix:" not in text:
                    source.write_text(text.replace(original, replacement), encoding="utf-8")
        if package == "atlas":
            source = ROOT / "upstream" / package / "src" / "atlas" / "acquisition_optimizers" / "pymoo_optimizer.py"
            text = source.read_text(encoding="utf-8")
            old = "            X_arr = list(X_.values())"
            new = "            # NaNoBO fix: evaluate constraints in original parameter units, not Pymoo indices.\n            X_arr = list(self._pymoo_to_olympus([X_])[0].values())"
            if old not in text and new not in text:
                raise RuntimeError("Unexpected Atlas constraint wrapper source")
            source.write_text(text.replace(old, new), encoding="utf-8")
        setup = ROOT / "upstream" / package / "setup.py"
        text = setup.read_text(encoding="utf-8")
        snapshot = "0+chembo." + PINS[package][1][:7]
        text = text.replace("version=versioneer.get_version()", f"version='{snapshot}'")
        if not text.startswith("# ChemBO"):
            text = "# NaNoBO modification: fixed source-snapshot version; no VCS metadata is bundled.\n" + text
        setup.write_text(text, encoding="utf-8")
        run(sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", ROOT / "upstream" / package)
    run(sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "-e", ROOT)


if __name__ == "__main__":
    main()
