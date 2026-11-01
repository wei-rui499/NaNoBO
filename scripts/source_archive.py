"""Small reviewable source bundle, excluding environments, data and binaries."""
from pathlib import Path
import zipfile
import os
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/chembo/__init__.py").read_text()).group(1)


def main():
    target = ROOT / "release" / f"NaNoBO-{VERSION}-source.zip"
    target.parent.mkdir(exist_ok=True)
    prefixes = ("src", "tests", "scripts", "docs", "research", "assets", "licenses", ".github", "examples")
    excluded = {".git", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        def files():
            for folder, directories, names in os.walk(ROOT):
                parts = Path(folder).relative_to(ROOT).parts
                if not parts:
                    directories[:] = [name for name in directories if name in prefixes or name == "upstream"]
                else:
                    directories[:] = [name for name in directories if name not in excluded and not name.endswith(".egg-info")]
                for name in names:
                    yield Path(folder) / name
        for path in files():
            relative = path.relative_to(ROOT)
            parts = relative.parts
            if not path.is_file() or path.is_symlink() or path.name == ".DS_Store" or path.name.startswith("._") or "project-inventory" in parts or any(p in excluded or p.endswith(".egg-info") for p in parts):
                continue
            include = parts[0] in prefixes or len(parts) == 1 and (path.suffix in (".md", ".txt", ".toml", ".in") or path.name in ("LICENSE", ".gitignore", ".gitattributes", "CITATION.cff", "REFERENCES.bib"))
            if parts[0] == "upstream" and len(parts) >= 3:
                package, rest = parts[1], "/".join(parts[2:])
                include = package in ("gryffin", "atlas", "olympus-runtime") and (rest.startswith("src/") or "/" not in rest)
                include |= package == "bo-mcp" and (rest.startswith("packages/bo-engine/") or rest in ("LICENSE", "README.md", "UPSTREAM_REVISION"))
            if include and path.suffix not in (".pyc", ".pyxbldc", ".so", ".pyd", ".dylib") and path.stat().st_size < 5000000:
                archive.write(path, "NaNoBO/" + str(relative))
    print(target)
    return target


if __name__ == "__main__":
    main()
