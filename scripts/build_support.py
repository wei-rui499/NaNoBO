"""Small shared helpers for publisher scripts; no application imports."""
import ast
from pathlib import Path


def app_version(root):
    source = Path(root) / "src" / "chembo" / "__init__.py"
    for item in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in item.targets):
            value = ast.literal_eval(item.value)
            if isinstance(value, str) and value:
                return value
    raise RuntimeError("NaNoBO __version__ is missing")
