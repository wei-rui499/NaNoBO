"""Publisher build setup, using native Python 3.10 on Windows/macOS (never WSL).

End users install the compiled application; they do not run this script.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
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


def regenerate_extension(source):
    # Existing distributed C files carry our modification notice before Cython's
    # header. Cython refuses to overwrite that header, so generate a new file.
    with tempfile.TemporaryDirectory(prefix=".nanobo-cython-", dir=source.parent) as folder:
        generated = Path(folder) / source.with_suffix(".c").name
        run(sys.executable, "-m", "cython", "-3", "--output-file", generated, source)
        notice = b"/* NaNoBO modification: regenerated from unchanged upstream .pyx with Cython 3.3.0 for native Python 3.10 compatibility. */\n"
        generated.write_bytes(notice + generated.read_bytes())
        generated.replace(source.with_suffix(".c"))


def patch_atlas_constraints(text):
    old = "            X_arr = list(X_.values())"
    fixed = "            X_arr = list(self._pymoo_to_olympus([X_])[0].values())"
    if fixed in text:
        return text  # Older distributed snapshots use the ChemBO Studio notice.
    if old not in text:
        raise RuntimeError("Unexpected Atlas constraint wrapper source")
    notice = "            # NaNoBO fix: evaluate constraints in original parameter units, not Pymoo indices.\n"
    return text.replace(old, notice + fixed)


def patch_gryffin_memory_info(text):
    if "# NaNoBO modification: resource is Unix-only; memory reporting is optional." in text:
        return text
    replacements = {
        "import resource\n": "# NaNoBO modification: resource is Unix-only; memory reporting is optional.\ntry:\n    import resource\nexcept ImportError:\n    resource = None\n",
        "def memory_usage():\n": "def memory_usage():\n    if resource is None:\n        return None, None, None\n",
        "    GB, MB, kB = memory_usage()\n": "    GB, MB, kB = memory_usage()\n    if GB is None:\n        print('==> MEMORY USAGE: unavailable on this platform')\n        return\n",
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError("Unexpected Gryffin memory utility source")
        text = text.replace(old, new)
    return text


def patch_olympus_metadata(text):
    original = "    def __getattr__(self, attr):\n"
    fixed = "        if attr.startswith('__'):\n            raise AttributeError(attr)\n"
    if fixed in text:
        return text
    if original not in text:
        raise RuntimeError("Unexpected Olympus metadata loader source")
    notice = "        # NaNoBO fix: missing Python metadata is not an optimizer/plugin name.\n"
    return text.replace(original, original + notice + fixed)


def patch_gryffin_memory_logging(text):
    marker = "# NaNoBO fix: Windows has no Unix resource statistics; logging must not fail a calculation."
    if marker in text:
        if text.count(marker) != 2:
            raise RuntimeError("Incomplete Gryffin memory logging patch")
        return text
    original = "        self.log(f'Memory usage: {GB:.0f} GB, {MB:.0f} MB, {kB:.0f} kB', 'STATS')"
    if text.count(original) != 2:
        raise RuntimeError("Unexpected Gryffin memory logging source")
    fixed = ("        " + marker + "\n"
             "        if GB is None:\n"
             "            self.log('Memory usage: unavailable on this platform', 'STATS')\n"
             "        else:\n    " + original)
    return text.replace(original, fixed)


def patch_gryffin_discrete_perturbation(text):
    marker = "# NaNoBO fix: discrete samples are zero-based option indices, not user values."
    if marker in text:
        return text
    replacements = {
        "        if param_type in ['continuous', 'discrete']:\n": (
            "        if param_type in ['continuous', 'discrete']:\n"
            "            " + marker + "\n"
            "            low = 0 if param_type == 'discrete' else specs['low']\n"
            "            high = specs['high'] - specs['low'] if param_type == 'discrete' else specs['high']\n"),
        "            sampled_values *= specs['high'] - specs['low']": "            sampled_values *= high - low",
        "            perturbed_sample = np.where(perturbed_sample < specs['low'], specs['low'], perturbed_sample)": "            perturbed_sample = np.where(perturbed_sample < low, low, perturbed_sample)",
        "            perturbed_sample = np.where(perturbed_sample > specs['high'], specs['high'], perturbed_sample)": "            perturbed_sample = np.where(perturbed_sample > high, high, perturbed_sample)",
    }
    for original, fixed in replacements.items():
        if text.count(original) != 1:
            raise RuntimeError("Unexpected Gryffin discrete perturbation source")
        text = text.replace(original, fixed)
    return text


def patch_olympus_campaign_package(text):
    marker = "# NaNoBO fix: importing ParameterSpace for Dataset must not eagerly import Campaign and re-enter Dataset."
    if marker in text:
        return text
    original = "from olympus.campaigns.campaign import Campaign\n"
    if text.count(original) != 1:
        raise RuntimeError("Unexpected Olympus campaign package source")
    return text.replace(original, "") + (
        "\n" + marker + "\n"
        '__all__ = ["Campaign", "Observations", "ParameterSpace"]\n\n\n'
        "def __getattr__(name):\n"
        '    if name == "Campaign":\n'
        "        from olympus.campaigns.campaign import Campaign\n"
        "        globals()[name] = Campaign\n"
        "        return Campaign\n"
        '    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")\n')


def patch_snapshot_version(text, package):
    snapshot = "0+chembo." + PINS[package][1][:7]
    text = text.replace("version=versioneer.get_version()", f"version='{snapshot}'")
    if not re.search(r"\bversion\s*=\s*['\"]" + re.escape(snapshot) + r"['\"]", text):
        raise RuntimeError(f"Unexpected {package} snapshot version source")
    if not text.startswith(("# ChemBO", "# NaNoBO")):
        text = "# NaNoBO modification: fixed source-snapshot version; no VCS metadata is bundled.\n" + text
    return text


def patch_olympus_optional_plotter(text):
    marker = "# NaNoBO fix: the desktop uses its own plots; an unused optional Plotter must not request seaborn during model startup."
    if marker in text:
        return text
    original = "from .plotter import Plotter\n"
    benchmark = "from .olympus import Olympus\n"
    if text.count(original) != 1 or text.count(benchmark) != 1:
        raise RuntimeError("Unexpected Olympus optional plotter source")
    return text.replace(original, "").replace(benchmark, "") + (
        "\n" + marker + "\n"
        "def __getattr__(name):\n"
        '    if name == "Olympus":\n'
        "        from .olympus import Olympus\n"
        "        globals()[name] = Olympus\n"
        "        return Olympus\n"
        '    if name == "Plotter":\n'
        "        from .plotter import Plotter\n"
        "        globals()[name] = Plotter\n"
        "        return Plotter\n"
        '    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")\n\n\n'
        '__all__ = [name for name in globals() if not name.startswith("_")] + ["Olympus", "Plotter"]\n')


def prepare_classic_sources():
    """Prepare the complete pinned source snapshot without installing packages."""
    gryffin = ROOT / "upstream" / "gryffin"
    memory_info = gryffin / "src/gryffin/utilities/infos.py"
    memory_info.write_text(patch_gryffin_memory_info(memory_info.read_text(encoding="utf-8")), encoding="utf-8")
    planner_source = gryffin / "src/gryffin/gryffin.py"
    planner_source.write_text(patch_gryffin_memory_logging(planner_source.read_text(encoding="utf-8")), encoding="utf-8")
    sampler_source = gryffin / "src/gryffin/random_sampler/random_sampler.py"
    sampler_source.write_text(patch_gryffin_discrete_perturbation(sampler_source.read_text(encoding="utf-8")), encoding="utf-8")
    for stem in ("kernel_evaluations", "kernel_prob_reshaping"):
        source = gryffin / "src" / "gryffin" / "bayesian_network" / (stem + ".pyx")
        regenerate_extension(source)
    for package in ("gryffin", "olympus-runtime", "atlas"):
        if package == "olympus-runtime":
            initializer = ROOT / "upstream" / package / "src/olympus/__init__.py"
            initializer.write_text(patch_olympus_optional_plotter(initializer.read_text(encoding="utf-8")), encoding="utf-8")
            campaign = ROOT / "upstream" / package / "src/olympus/campaigns/__init__.py"
            campaign.write_text(patch_olympus_campaign_package(campaign.read_text(encoding="utf-8")), encoding="utf-8")
            for module in ("noises", "models", "planners", "surfaces", "scalarizers"):
                source = ROOT / "upstream" / package / "src" / "olympus" / module / "__init__.py"
                text = source.read_text(encoding="utf-8")
                source.write_text(patch_olympus_metadata(text), encoding="utf-8")
        if package == "atlas":
            source = ROOT / "upstream" / package / "src" / "atlas" / "acquisition_optimizers" / "pymoo_optimizer.py"
            text = source.read_text(encoding="utf-8")
            source.write_text(patch_atlas_constraints(text), encoding="utf-8")
        setup = ROOT / "upstream" / package / "setup.py"
        text = setup.read_text(encoding="utf-8")
        setup.write_text(patch_snapshot_version(text, package), encoding="utf-8")
    return ("gryffin", "olympus-runtime", "atlas")


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
    for package in prepare_classic_sources():
        run(sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", ROOT / "upstream" / package)
    run(sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "-e", ROOT)


if __name__ == "__main__":
    main()
