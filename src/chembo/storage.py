"""Portable project files and CSV without executable project content."""
import csv
import io
import json
import os
import tempfile
from pathlib import Path


def atomic_write(path, text):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".chembo-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_project(path, project):
    atomic_write(path, json.dumps(project, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        # Spreadsheet formula injection: exported categorical labels stay text.
        writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v) for k, v in row.items()})
    atomic_write(path, "\ufeff" + stream.getvalue())
