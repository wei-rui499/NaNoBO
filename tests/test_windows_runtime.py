"""Regressions for failures reproduced in the released native Windows bundle."""
import ast
from pathlib import Path
import sys
import types
import io

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("method", ["build_surrogate", "recommend"])
@pytest.mark.parametrize("memory", [(None, None, None), (1.0, 2.0, 3.0)])
def test_real_gryffin_summary_does_not_fail_without_unix_memory_statistics(method, memory):
    source = ROOT / "upstream/gryffin/src/gryffin/gryffin.py"
    planner = next(node for node in ast.parse(source.read_text(encoding="utf-8")).body
                   if isinstance(node, ast.ClassDef) and node.name == "Gryffin")
    function = next(node for node in planner.body if isinstance(node, ast.FunctionDef) and node.name == method)
    index = next(i for i, node in enumerate(function.body)
                 if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                 and isinstance(node.value.func, ast.Name) and node.value.func.id == "memory_usage")
    # Execute the actual statistics statements from both calculation paths. The
    # former test of infos.print_memory_usage alone missed these two call sites.
    summary = ast.Module(body=function.body[index:index + 2], type_ignores=[])
    calls = []
    class Logger:
        def log(self, text, level):
            calls.append((text, level))
    exec(compile(summary, str(source), "exec"), {"self": Logger(), "memory_usage": lambda: memory})
    assert len(calls) == 1 and calls[0][1] == "STATS"
    assert ("unavailable" in calls[0][0]) is (memory[0] is None)


def test_native_compatibility_patches_are_idempotent():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from bootstrap import patch_gryffin_memory_logging, patch_gryffin_discrete_perturbation, patch_olympus_campaign_package, patch_olympus_optional_plotter
        for path, patch in [
            ("upstream/gryffin/src/gryffin/gryffin.py", patch_gryffin_memory_logging),
            ("upstream/gryffin/src/gryffin/random_sampler/random_sampler.py", patch_gryffin_discrete_perturbation),
            ("upstream/olympus-runtime/src/olympus/campaigns/__init__.py", patch_olympus_campaign_package),
            ("upstream/olympus-runtime/src/olympus/__init__.py", patch_olympus_optional_plotter),
        ]:
            text = (ROOT / path).read_text(encoding="utf-8")
            assert patch(text) == text
    finally:
        sys.path.pop(0)


@pytest.mark.parametrize("relative,symbol,module", [
    ("campaigns/__init__.py", "Campaign", "olympus.campaigns.campaign"),
    ("__init__.py", "Plotter", "olympus.plotter"),
    ("__init__.py", "Olympus", "olympus.olympus"),
])
def test_optional_exports_are_lazy_and_cached(monkeypatch, relative, symbol, module):
    source = ROOT / "upstream/olympus-runtime/src/olympus" / relative
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.ImportFrom) and node.module in {module, module.rsplit(".", 1)[-1]} for node in tree.body)
    loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "__getattr__")
    package = types.ModuleType("campaign_package_test")
    exec(compile(ast.Module(body=[loader], type_ignores=[]), str(source), "exec"), package.__dict__)
    expected = type(symbol, (), {})
    calls = []
    import builtins
    original_import = builtins.__import__
    def import_campaign(name, *args, **kwargs):
        if name in {module, module.rsplit(".", 1)[-1]}:
            calls.append(name)
            return types.SimpleNamespace(**{symbol: expected})
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", import_campaign)
    assert getattr(package, symbol) is expected and getattr(package, symbol) is expected
    assert len(calls) == 1
    with pytest.raises(AttributeError):
        package.missing_metadata


def test_worker_logging_accepts_unicode_with_gbk_console_streams(monkeypatch):
    import chembo.worker as worker
    output, errors = io.BytesIO(), io.BytesIO()
    fake_sys = types.SimpleNamespace(stdout=io.TextIOWrapper(output, encoding="gbk"),
                                     stderr=io.TextIOWrapper(errors, encoding="gbk"))
    monkeypatch.setattr(worker, "sys", fake_sys)
    worker.prepare_streams()
    text = "Atlas \U0001f495 中文"
    fake_sys.stdout.write(text)
    fake_sys.stderr.write(text)
    fake_sys.stdout.flush()
    fake_sys.stderr.flush()
    assert output.getvalue().decode("utf-8") == text
    assert errors.getvalue().decode("utf-8") == text


@pytest.mark.parametrize("kind,low,high,reference,expected", [
    ("discrete", 5, 7, 1, [1, 2, 0]),
    ("discrete", -5, -3, 1, [1, 2, 0]),
    ("discrete", 0, 2, 1, [1, 2, 0]),
    ("continuous", 5, 7, 6, [6, 7, 5]),
])
def test_gryffin_perturbation_preserves_internal_index_and_continuous_bounds(kind, low, high, reference, expected):
    import numpy as np
    source = ROOT / "upstream/gryffin/src/gryffin/random_sampler/random_sampler.py"
    sampler = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "RandomSampler")
    method = next(n for n in sampler.body if isinstance(n, ast.FunctionDef) and n.name == "_perturb_single_parameter")
    namespace = {"np": np}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    fake = types.SimpleNamespace(_draw_continuous=lambda *args: np.array([[0.], [1.], [-1.]]))
    actual = namespace[method.name](fake, reference, 3, kind, {"low": low, "high": high}, 1)
    assert actual[:, 0].tolist() == expected
