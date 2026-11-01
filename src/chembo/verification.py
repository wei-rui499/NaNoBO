"""Publisher-only frozen GUI/worker integration check; only simulated data."""
import json
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from chembo.app import Window, example_project
from chembo.examples import workflow_example


XLS_FIXTURE = 'eJztWEFIFFEY/t64u+4uus7aKmggi5CZeYkuXXRSSE+J1aGIoFZ3EHFZY+myXbJsj4HgqegieOlieamkgroFBUYdgiDYrWOnoKCD7vj//8zQagbOQS143/C+98///n/ev/P+9/a9ebeaLC8st1ewBf2oQ9WJIVKjU1Ri/o0JanccFv06SsXR+K8Qi9JARsJ41vi2nseQx7sCA49Cr4iBL1Qu4SpGpvN2eg8xKDFkFMfQR6xwnzQJtElUzcLjwgeEH4rlc+GTorkj3Ee2ZXURq9ZIzwkviy8YndKWAD/3ifh8Es0xtOA1Z/GNOeXahjFQmMzk/s2GjlADFkHjNmzn7UImV0aKBnARP5008MOfqS/TWr+3egXS/9qsr99GP2+EgBk4VyTBS5SQK3XcEkHOnsiMF9fIj9OSC438QBgoTtq5bJzu3Ylrbpq4jZLQDcRZNImcFF+Tlua1B9/fnx4btS6LZkYWa3dJP8RRwMFN9iDnhLRIIGLbI3xU+JY89aDI7cIpSkaqu0ZbPGFoVmxuS2sX9XNc8ME6XCN3k1z6duZpR+mrdYTkpeHK9dTSR2sBnfQXkyV/vmbRq3rVvbuMFcuvlTf9Pwu3/bEURA3Ti91xX7RqwjriIiaF3Tt+O8qzV1vsX1AfSuzPCbsjwJbGNpaG2LwRjohlv9GMx6ymxeg34tDQ0NDQ0NDQ0NDYV7gbX3e7z8cAOmLIFpbPFPxdZ51Kdb8/UmjsGs5imq5rdDA9hTzVBRQD5U8rwsp/ltqhj/+9kHGeei9gCmMSx1Sgvhl0+FK1v2fHjmbgrv6GwP1Xg8S5y/1vAOtjwJ8='


def verify_files_and_exports(window):
    """Exercise frozen Excel readers and every plot exporter, not dev packages."""
    import tempfile
    import base64
    import zlib
    from openpyxl import Workbook
    from chembo.engine import read_observations
    from chembo.storage import write_csv
    project = {"name": "SYNTHETIC reader check", "engine": "bo-mcp", "parameters": [{"name": "A", "type": "continuous", "low": 0, "high": 1, "step": .1}], "objectives": [{"name": "yield", "goal": "max"}], "observations": [], "pending": []}
    checks = []
    from chembo.app import resources
    asset_root = resources()
    for language in ("zh-CN", "en"):
        if not (asset_root / "docs/html" / f"TUTORIAL.{language}.html").is_file():
            raise RuntimeError("Missing offline tutorial: " + language)
    for exercise in ("01_quickstart", "02_recipe", "03_pareto", "04_classification"):
        if not (asset_root / "examples/tutorial" / exercise / "project.chembo.json").is_file():
            raise RuntimeError("Missing tutorial exercise: " + exercise)
    checks.append({"case": "frozen-tutorial-resources", "languages": ["zh-CN", "en"], "exercise_folders": 4})
    with tempfile.TemporaryDirectory(prefix="nanobo-frozen-export-") as directory:
        folder = Path(directory)
        expected = [{"A": .2, "yield": 0.0}, {"A": .5, "yield": 1.0}]
        csv_path = folder / "measured.csv"
        write_csv(csv_path, ["A", "yield"], expected)
        book = Workbook()
        book.active.title = "measured"
        book.active.append(["A", "yield"])
        for row in expected:
            book.active.append([row["A"], row["yield"]])
        book.create_sheet("notes").append(["SYNTHETIC"])
        book.save(folder / "measured.xlsx")
        (folder / "measured.xls").write_bytes(zlib.decompress(base64.b64decode(XLS_FIXTURE)))
        for suffix in ("csv", "xls", "xlsx"):
            rows = read_observations(project, folder / ("measured." + suffix), "measured" if suffix == "xlsx" else None)
            if rows != expected:
                raise RuntimeError("Frozen " + suffix + " reader produced unexpected values")
            checks.append({"case": "frozen-import-" + suffix, "rows": len(rows)})
        view = window.analysis_view
        for page_name in ("prediction", "validation", "distribution", "multi", "classification"):
            view.tabs.setCurrentWidget(getattr(view, page_name))
            for suffix in ("png", "pdf", "svg"):
                path = folder / (page_name + "." + suffix)
                view.export_figure(path)
                if path.stat().st_size < 200:
                    raise RuntimeError("Frozen figure export is empty: " + str(path))
        view.export_predictions(folder / "predictions.csv")
        if (folder / "predictions.csv").stat().st_size < 200:
            raise RuntimeError("Frozen predictions export is empty")
        checks.append({"case": "frozen-plot-and-table-exports", "figure_files": 15, "prediction_csv": True})
    return checks


def main(args):
    if len(args) != 1:
        return 2
    output = Path(args[0]).resolve()
    app = QApplication(sys.argv[:1])
    window = Window()
    errors, checks = [], []
    window.error = lambda error: errors.append(str(error))
    cases = []
    for engine in ('gryffin', 'atlas', 'bo-mcp'):
        project = example_project()
        project['engine'] = engine
        cases.append((engine, project, 'recommend'))
    for mode in ('recipe', 'pareto', 'classification'):
        cases.append((mode, workflow_example(mode), 'recommend'))
    for mode in ('pareto', 'classification'):
        project = workflow_example(mode)
        project['pending'] = [{'x':.6,'category':'A'}]
        cases.append((mode+'-validation', project, 'analyze'))
    cases = iter(cases)
    active = None
    exit_code = 1

    def finish(ok, error=None):
        nonlocal exit_code
        timer.stop()
        if window.process is not None:
            window.cancel_run()
        output.write_text(json.dumps({'ok':ok,'checks':checks,'error':error}, ensure_ascii=False, indent=2), encoding='utf-8')
        window.dirty = False
        exit_code = 0 if ok else 1
        app.quit()

    def tick():
        nonlocal active
        if window.process is not None:
            return
        if errors:
            finish(False, {'messages':errors,'log':window.logs.toPlainText()})
            return
        if active is not None:
            name, original, operation = active
            expected = len(original.get('pending', [])) + (2 if operation=='recommend' else 0)
            if len(window.project['pending']) != expected or window.pending.rowCount() != expected:
                finish(False, f'{name}: worker results did not reach pending table correctly')
                return
            analysis = window.project.get('analysis', {})
            if original['engine']=='bo-mcp' and not analysis.get('predictions'):
                finish(False, f'{name}: missing actual candidate model predictions')
                return
            if operation=='analyze' and not analysis.get('diagnostics',{}).get('rows'):
                finish(False, f'{name}: missing genuine cross-validation rows')
                return
            checks.append({'case':name,'operation':operation,'pending_rows':expected,'prediction_rows':len(analysis.get('predictions',[])), 'validation_rows':len(analysis.get('diagnostics',{}).get('rows',[]))})
        active = next(cases, None)
        if active is None:
            try:
                checks.extend(verify_files_and_exports(window))
            except Exception as exc:
                finish(False, str(exc))
                return
            finish(True)
            return
        _, project, operation = active
        window.set_project(project)
        window.run(operation=operation)

    timer = QTimer()
    timer.setInterval(30)
    timer.timeout.connect(tick)
    QTimer.singleShot(360000, lambda: finish(False, 'GUI verification timed out'))
    window.show()
    timer.start()
    app.exec()
    return exit_code
