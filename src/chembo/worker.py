"""One isolated calculation; stdout is diagnostic, result is structured JSON."""
import json
import os
import sys
import traceback
from pathlib import Path


def prepare_streams():
    """Qt pipes use UTF-8 logs, including on Windows systems with a GBK locale."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
        elif callable(getattr(stream, "reconfigure", None)):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(args):
    if len(args) != 2:
        return 2
    # Windowed EXEs can have no console or a GBK-encoded QProcess pipe.
    # Atlas logs Unicode characters before fitting; neither case may fail a model.
    prepare_streams()
    request, result = [Path(value).resolve() for value in args]
    try:
        # All engine scratch files belong to this calculation, including in a frozen app.
        os.chdir(request.parent)
        os.environ["ATLAS_SCRATCH"] = str(request.parent / "atlas-scratch")
        os.environ["OLYMPUS_SCRATCH"] = str(request.parent / "olympus-scratch")
        os.environ["MPLCONFIGDIR"] = str(request.parent / "matplotlib-cache")
        for name in ("atlas-scratch", "olympus-scratch"):
            (request.parent / name).mkdir(exist_ok=True)
        from chembo.engine import recommend
        project = json.loads(request.read_text(encoding="utf-8"))
        rows = recommend(project)
        payload = {"ok": True, "recommendations": rows}
    except BaseException as exc:
        traceback.print_exc()
        import typing
        import typing_extensions
        payload = {"ok": False, "error": str(exc) or type(exc).__name__, "diagnostic": traceback.format_exc(),
                   "runtime": {"python": sys.version, "typing": typing.__file__, "typing_extensions": typing_extensions.__file__, "Self": repr(typing_extensions.Self), "special_form": str(type(typing_extensions.Self))}}
    result.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0 if payload["ok"] else 1
