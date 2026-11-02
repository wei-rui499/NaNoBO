"""Rebuild targeted Python compatibility fixes over the verified 0.2.3 Windows runtime.

Run with native CPython 3.10 and PyInstaller installed. The base ZIP is verified
against the published digest. Native libraries and the modern worker are retained
byte for byte; the six affected Python modules are compiled from this checkout.
The normal bootstrap/build workflow also includes the same source corrections.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import marshal
from pathlib import Path
import struct
import sys
import zipfile
import zlib
from datetime import datetime, timezone

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "461cf348b3dc49da82646a59df90045cd464913c2cfea24883204a9364fc6825"
PATCHES = {
    "gryffin.gryffin": ROOT / "upstream/gryffin/src/gryffin/gryffin.py",
    "gryffin.random_sampler.random_sampler": ROOT / "upstream/gryffin/src/gryffin/random_sampler/random_sampler.py",
    "olympus": ROOT / "upstream/olympus-runtime/src/olympus/__init__.py",
    "olympus.campaigns": ROOT / "upstream/olympus-runtime/src/olympus/campaigns/__init__.py",
    "chembo.worker": ROOT / "src/chembo/worker.py",
    "chembo.engine": ROOT / "src/chembo/engine.py",
}
COOKIE = struct.Struct("!8sIIII64s")
ENTRY = struct.Struct("!IIIIBc")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rebuild_pyz(reader):
    with open(reader._filename, "rb") as stream:
        stream.seek(reader._start_offset)
        header = stream.read(17)
        if header[:4] != b"PYZ\0" or header[4:8] != importlib.util.MAGIC_NUMBER:
            raise RuntimeError("The builder must match the bundle's CPython bytecode version")
        output = io.BytesIO()
        output.write(header)
        toc = []
        for name, (kind, offset, length) in reader.toc.items():
            stream.seek(reader._start_offset + offset)
            compressed = stream.read(length)
            if name in PATCHES:
                old_code = marshal.loads(zlib.decompress(compressed))
                code = compile(PATCHES[name].read_text(encoding="utf-8"), old_code.co_filename, "exec", dont_inherit=True)
                compressed = zlib.compress(marshal.dumps(code), 6)
            toc.append((name, (kind, output.tell(), len(compressed))))
            output.write(compressed)
        toc_offset = output.tell()
        output.write(marshal.dumps(toc))
        output.seek(8)
        output.write(struct.pack("!i", toc_offset))
        return output.getvalue()


def rebuild_executable(path):
    original = CArchiveReader(str(path))
    pyz = original.open_embedded_archive("PYZ.pyz")
    if not set(PATCHES) <= set(pyz.toc):
        raise RuntimeError("Expected modules are missing from the original bundle")
    replacement = rebuild_pyz(pyz)
    data = path.read_bytes()
    cookie_offset = data.rfind(b"MEI\014\013\012\013\016")
    if cookie_offset + COOKIE.size != len(data):
        raise RuntimeError("Only the published unsigned executable layout is supported")
    magic, old_length, toc_offset, toc_length, pyvers, library = COOKIE.unpack_from(data, cookie_offset)
    start = cookie_offset + COOKIE.size - old_length
    if start != original._start_offset or pyvers != 310:
        raise RuntimeError("Unexpected classic runtime layout")
    old_toc = data[start + toc_offset:start + toc_offset + toc_length]
    payload = io.BytesIO()
    new_toc = []
    cursor = 0
    while cursor < len(old_toc):
        size, offset, length, raw_length, compressed, kind = ENTRY.unpack_from(old_toc, cursor)
        name_bytes = old_toc[cursor + ENTRY.size:cursor + size]
        name = name_bytes.rstrip(b"\0").decode("utf-8")
        blob = data[start + offset:start + offset + length]
        if name == "PYZ.pyz":
            raw_length = len(replacement)
            blob = zlib.compress(replacement, 9) if compressed else replacement
        new_toc.append(ENTRY.pack(size, payload.tell(), len(blob), raw_length, compressed, kind) + name_bytes)
        payload.write(blob)
        cursor += size
    new_toc_offset = payload.tell()
    serialized_toc = b"".join(new_toc)
    payload.write(serialized_toc)
    payload.write(COOKIE.pack(magic, payload.tell() + COOKIE.size, new_toc_offset, len(serialized_toc), pyvers, library))
    # A separate output file avoids modifying any source executable in place.
    temporary = path.with_suffix(".hotfix.tmp")
    temporary.write_bytes(data[:start] + payload.getvalue())
    rebuilt = CArchiveReader(str(temporary))
    rebuilt_pyz = rebuilt.open_embedded_archive("PYZ.pyz")
    rebuilt_data = temporary.read_bytes()
    if set(rebuilt_pyz.toc) != set(pyz.toc):
        raise RuntimeError("Rebuilt module inventory changed")
    for name in pyz.toc:
        if name in PATCHES:
            code = rebuilt_pyz.extract(name)
            expected = compile(PATCHES[name].read_text(encoding="utf-8"), code.co_filename, "exec", dont_inherit=True)
            if code != expected:
                raise RuntimeError("Rebuilt source verification failed: " + name)
        else:
            kind, offset, length = pyz.toc[name]
            new_kind, new_offset, new_length = rebuilt_pyz.toc[name]
            old_blob = data[pyz._start_offset + offset:pyz._start_offset + offset + length]
            new_blob = rebuilt_data[rebuilt_pyz._start_offset + new_offset:rebuilt_pyz._start_offset + new_offset + new_length]
            if kind != new_kind or old_blob != new_blob:
                raise RuntimeError("Unrelated module changed: " + name)
    for name in original.toc:
        if name != "PYZ.pyz" and rebuilt.extract(name) != original.extract(name):
            raise RuntimeError("Unrelated executable entry changed: " + name)
    temporary.replace(path)
    return len(pyz.toc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted extraction only after verifying every base file")
    parser.add_argument("--update-existing", action="store_true", help="Update a verified hotfix after checking its unchanged runtime against the base")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:2] != (3, 10):
        raise SystemExit("Run this builder with native Windows CPython 3.10")
    if sha256(args.base) != BASE_SHA256:
        raise SystemExit("The base ZIP does not match the verified official 0.2.3 Windows distribution")
    destination = args.output.resolve()
    occupied = destination.exists() and any(destination.iterdir())
    if occupied and not (args.resume or args.update_existing):
        raise SystemExit("Use an empty output directory")
    if args.update_existing:
        previous = destination / "NaNoBO/WINDOWS_HOTFIX.json"
        if not previous.is_file():
            raise SystemExit("The output is not a previously verified hotfix")
        record = json.loads(previous.read_text(encoding="utf-8"))
        if record.get("base_zip_sha256") != BASE_SHA256 or record.get("executable_sha256") != sha256(destination / "NaNoBO/NaNoBO.exe"):
            raise SystemExit("The previous hotfix executable does not match its recorded digest")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.base) as archive:
        for name in archive.namelist():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise SystemExit("Unsafe base archive member")
        if occupied:
            allowed = {"NaNoBO/NaNoBO.exe"} if args.update_existing else set()
            if args.update_existing:
                for name, source in PATCHES.items():
                    relative = Path(*name.split("."))
                    mirror = relative / "__init__.py" if source.name == "__init__.py" else relative.with_suffix(".py")
                    allowed.add((Path("NaNoBO/_internal") / mirror).as_posix())
            for item in archive.infolist():
                if item.is_dir():
                    continue
                if item.filename in allowed:
                    continue
                if args.update_existing and item.filename.startswith("NaNoBO/_internal/docs/html/"):
                    rendered = ROOT / item.filename.removeprefix("NaNoBO/_internal/")
                    path = destination / item.filename
                    if rendered.is_file() and path.is_file() and sha256(path) == sha256(rendered):
                        continue
                path = destination / item.filename
                if not path.is_file() or sha256(path) != hashlib.sha256(archive.read(item)).hexdigest():
                    raise SystemExit("Interrupted output no longer matches the base: " + item.filename)
        else:
            archive.extractall(destination)
    bundle = destination / "NaNoBO"
    checked = rebuild_executable(bundle / "NaNoBO.exe")
    for name, source in PATCHES.items():
        relative = Path(*name.split("."))
        mirror = bundle / "_internal" / (relative / "__init__.py" if source.name == "__init__.py" else relative.with_suffix(".py"))
        if mirror.exists():
            mirror.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    report = {
        "product": "NaNoBO", "version": "0.2.3", "windows_hotfix": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(), "base_zip_sha256": BASE_SHA256,
        "python": sys.version, "verified_frozen_modules": checked,
        "patches": {name: {"source": source.relative_to(ROOT).as_posix(), "sha256": sha256(source)} for name, source in PATCHES.items()},
        "executable_sha256": sha256(bundle / "NaNoBO.exe"),
        "unchanged_runtime": "Every other frozen module, native dependency and the complete modern worker is retained from the verified base.",
        "runtime_validation": "See the accompanying WINDOWS_ACCEPTANCE report; compilation alone is not runtime acceptance.",
    }
    (bundle / "WINDOWS_HOTFIX.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
