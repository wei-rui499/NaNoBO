"""Generate the explicitly synthetic, finite teaching exercises.

Run with the classic environment (openpyxl). To regenerate the legacy XLS
fixtures, also install xlwt==1.3.0 in a development-only environment and pass
--xls. No XLS writer is required by the distributed desktop application.
"""
from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "examples" / "tutorial"
NOTICE = (
    "SYNTHETIC / 模拟教学数据：由明确的数学规则生成，不来自真实化学实验，"
    "不是可执行的化学合成建议，也不能作为优化算法优越性的证据。"
)


def project(name, parameters, objectives, candidates, observations):
    return {
        "name": name + " · SYNTHETIC",
        "engine": "bo-mcp",
        "task": "optimization",
        "objective_mode": "hierarchical",
        "seed": 42,
        "batch_size": 2,
        "parameters": parameters,
        "objectives": objectives,
        "constraints": [],
        "candidates": candidates,
        "observations": observations,
        "pending": [],
        "notes": NOTICE,
        "teaching": {"data_status": "SYNTHETIC", "purpose": "software learning only"},
    }


def objective(name, goal="max"):
    return {"name": name, "goal": goal, "tolerance": 0.2}


def cases():
    parameters = [
        dict(name="temperature_C", type="continuous", low=20, high=60, step=10, unit="°C"),
        dict(name="cycles", type="discrete", low=1, high=2, unit="count"),
        dict(name="additive", type="categorical", options=["A", "B"], unit=""),
    ]
    rows = [dict(temperature_C=t, cycles=n, additive=a,
                 yield_pct=round(70 - .025 * (t - 50) ** 2 + 6 * (a == "B") - 3 * (n - 2) ** 2, 4))
            for t, n, a in itertools.product(range(20, 61, 10), [1, 2], ["A", "B"])]
    yield "01_quickstart", "练习 1 · 认识完整实验循环", parameters, [objective("yield_pct")], rows, [0, 4, 7, 10, 13, 19], [3, 12], {}

    parameters = [
        dict(name="A_mL", type="continuous", low=.1, high=.9, step=.1, unit="mL"),
        dict(name="B_mL", type="continuous", low=.1, high=.9, step=.1, unit="mL"),
        dict(name="aging_min", type="discrete", low=10, high=30, step=10, unit="min"),
    ]
    rows = [dict(A_mL=a / 10, B_mL=round(1 - a / 10, 1), aging_min=t,
                 yield_pct=round(91 - 120 * (a / 10 - .55) ** 2 - .018 * (t - 20) ** 2, 4))
            for a, t in itertools.product(range(2, 9), [10, 20, 30])]
    rules = [dict(kind="linear", coefficients={"A_mL": 1, "B_mL": 1}, relation="eq", rhs=1),
             dict(kind="ratio", numerator="A_mL", denominator="B_mL", low=.25, high=4)]
    yield "02_recipe", "练习 2 · 固定总量的配方", parameters, [objective("yield_pct")], rows, [0, 4, 7, 10, 15, 20], [2, 16], {"constraints": rules}

    parameters = [
        dict(name="temperature_C", type="continuous", low=20, high=80, step=10, unit="°C"),
        dict(name="ligand_mM", type="continuous", low=.5, high=2, step=.5, unit="mM"),
    ]
    rows = [dict(temperature_C=t, ligand_mM=l,
                 yield_pct=round(35 + .65 * (t - 20) + 4 * l - .003 * (t - 65) ** 2, 4),
                 cost_index=round(1 + .045 * (t - 20) + .9 * l + .08 * (t >= 60), 4))
            for t, l in itertools.product(range(20, 81, 10), [.5, 1, 1.5, 2])]
    yield "03_pareto", "练习 3 · 性能与成本折衷", parameters, [objective("yield_pct"), objective("cost_index", "min")], rows, [0, 5, 10, 17, 22, 27], [3, 24], {"objective_mode": "pareto", "reference_point": {"yield_pct": 0, "cost_index": 10}}

    def morphology(t, l):
        score = (t - 20) / 10 + 2 * (l - .5) / .5
        return "团聚" if score <= 3 else "球形" if score <= 7 else "棒状"

    rows = [dict(temperature_C=t, ligand_mM=l, morphology=morphology(t, l))
            for t, l in itertools.product(range(20, 81, 10), [.5, 1, 1.5, 2])]
    yield "04_classification", "练习 4 · 探索形貌类别", parameters, [objective("morphology")], rows, [0, 4, 6, 13, 15, 27], [10, 22], {"task": "classification", "classification": {"labels": ["团聚", "球形", "棒状"]}}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_excel(path, columns, rows):
    from openpyxl import Workbook
    book = Workbook()
    book.properties.creator = "NaNoBO tutorial generator"
    book.properties.created = book.properties.modified = datetime(2026, 11, 1)
    sheet = book.active
    sheet.title = "Results"
    sheet.append(columns)
    for row in rows:
        sheet.append([row[col] for col in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for col in sheet.columns:
        sheet.column_dimensions[col[0].column_letter].width = max(16, len(str(col[0].value)) + 3)
    readme = book.create_sheet("ReadMe")
    readme.append(["SYNTHETIC tutorial data / 模拟教学数据"])
    readme.append([NOTICE])
    readme.append(["Import the Results sheet only. / 导入时只选择 Results 工作表。"])
    book.save(path)


def write_xls(path, columns, rows):
    import xlwt
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Results")
    for col, value in enumerate(columns):
        sheet.write(0, col, value)
    for index, row in enumerate(rows, 1):
        for col, key in enumerate(columns):
            sheet.write(index, col, row[key])
    readme = book.add_sheet("ReadMe")
    readme.write(0, 0, "SYNTHETIC tutorial data / 模拟教学数据")
    readme.write(1, 0, NOTICE)
    readme.write(2, 0, "Import Results only / 只导入 Results")
    book.save(str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xls", action="store_true", help="also generate BIFF8 XLS using development-only xlwt")
    args = parser.parse_args(argv)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {"data_status": "SYNTHETIC", "notice": NOTICE, "seed": 42, "batch_size": 2, "exercises": []}
    for folder, title, parameters, objectives, all_rows, seed_indices, follow_indices, extra in cases():
        destination = DESTINATION / folder
        destination.mkdir(exist_ok=True)
        variable_names = [p["name"] for p in parameters]
        columns = variable_names + [o["name"] for o in objectives]
        candidate_rows = [{key: row[key] for key in variable_names} for row in all_rows]
        seed_rows = [all_rows[i] for i in seed_indices]
        follow_rows = [all_rows[i] for i in follow_indices]
        p = project(title, parameters, objectives, candidate_rows, seed_rows)
        p.update(extra)
        write_json(destination / "project.chembo.json", p)
        empty = copy.deepcopy(p)
        empty["observations"] = []
        write_json(destination / "empty-project.chembo.json", empty)
        pending = copy.deepcopy(p)
        pending["pending"] = [{key: row[key] for key in variable_names} for row in follow_rows]
        write_json(destination / "pending-practice.chembo.json", pending)
        write_csv(destination / "seed-observations.csv", columns, seed_rows)
        write_excel(destination / "seed-observations.xlsx", columns, seed_rows)
        if args.xls:
            write_xls(destination / "seed-observations.xls", columns, seed_rows)
        write_csv(destination / "followup-results.csv", columns, follow_rows)
        write_csv(destination / "all-simulated-results.csv", columns, all_rows)
        write_csv(destination / "candidates.csv", variable_names, candidate_rows)
        entry = {"folder": folder, "title": title, "columns": columns, "candidate_rows": len(all_rows),
                 "seed_rows": len(seed_rows), "followup_rows": len(follow_rows),
                 "predictions_before_recommend": len(all_rows) - len(seed_rows),
                 "predictions_after_two_pending": len(all_rows) - len(seed_rows) - 2,
                 "pending_practice_before": {"completed": 6, "pending": 2},
                 "pending_practice_after_followup": {"completed": 8, "pending": 0}}
        if folder == "01_quickstart":
            for engine in ("gryffin", "atlas"):
                classic = copy.deepcopy(p)
                classic.update(engine=engine, candidates=[])
                for parameter in classic["parameters"]:
                    parameter.pop("step", None)
                write_json(destination / (engine + "-project.chembo.json"), classic)
            entry["best_seed_yield_pct"] = max(row["yield_pct"] for row in seed_rows)
        if folder == "03_pareto":
            three = copy.deepcopy(p)
            three["objectives"].append(objective("waste_index", "min"))
            three["reference_point"]["waste_index"] = 20
            rows3 = [dict(row, waste_index=round(6 + .05 * (row["temperature_C"] - 20) + .5 * row["ligand_mM"] ** 2, 4)) for row in all_rows]
            three["observations"] = [rows3[i] for i in seed_indices]
            write_json(destination / "three-objective-project.chembo.json", three)
            write_csv(destination / "three-objective-seed.csv", columns + ["waste_index"], three["observations"])
            write_csv(destination / "three-objective-all-simulated-results.csv", columns + ["waste_index"], rows3)
        if folder == "04_classification":
            binary = copy.deepcopy(p)
            binary["classification"] = {"labels": ["成功", "失败"]}
            binary["objectives"] = [objective("outcome")]
            binary_rows = [{key: row[key] for key in variable_names} | {"outcome": "失败" if row["morphology"] == "团聚" else "成功"} for row in all_rows]
            binary["observations"] = [binary_rows[i] for i in seed_indices]
            write_json(destination / "binary-project.chembo.json", binary)
            write_csv(destination / "binary-all-simulated-results.csv", variable_names + ["outcome"], binary_rows)
            entry["seed_class_counts"] = {label: sum(row["morphology"] == label for row in seed_rows) for label in p["classification"]["labels"]}
        manifest["exercises"].append(entry)
        (destination / "README.txt").write_text(
            NOTICE + "\n\n" + title + "\n"
            "Open project.chembo.json: 6 completed rows, 0 pending.\n"
            "Open empty-project.chembo.json to practise importing exactly ONE seed-observations file.\n"
            "Open pending-practice.chembo.json, then import followup-results.csv: 6 completed / 2 pending -> 8 completed / 0 pending.\n"
            "For newly recommended rows, look up the EXACT variable combination in all-simulated-results.csv. Do not import the entire answer table.\n"
            "Excel: choose Results; ReadMe is documentation, not an experiment table.\n"
            "See docs/TUTORIAL.zh-CN.md or docs/TUTORIAL.en.md.\n",
            encoding="utf-8")
    write_json(DESTINATION / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
