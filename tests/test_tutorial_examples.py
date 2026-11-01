"""Check the actual learner files against the same import/domain rules as the app."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chembo.engine import read_candidates, read_observations, reconcile_project, validate_project
from chembo.space import candidate_pool, feasible

ROOT = Path(__file__).resolve().parents[1] / "examples" / "tutorial"
FOLDERS = ["01_quickstart", "02_recipe", "03_pareto", "04_classification"]


def load(folder, name="project.chembo.json"):
    return validate_project(json.loads((ROOT / folder / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("folder,total", list(zip(FOLDERS, [20, 21, 28, 28])))
def test_teaching_files_use_the_app_import_rules_and_complete_oracle(folder, total):
    p = load(folder)
    assert "SYNTHETIC" in p["notes"] and p["teaching"]["data_status"] == "SYNTHETIC"
    assert len(p["observations"]) == 6 and p["pending"] == []
    assert len(candidate_pool(p)) == total - 6
    assert len(read_candidates(p, ROOT / folder / "candidates.csv")) == total
    for suffix in ("csv", "xlsx", "xls"):
        path = ROOT / folder / ("seed-observations." + suffix)
        assert path.is_file(), "Ship real legacy XLS examples too; do not rename an XLSX file."
        assert read_observations(p, path, "Results" if suffix != "csv" else None) == p["observations"]
    all_rows = read_observations(p, ROOT / folder / "all-simulated-results.csv")
    assert len(all_rows) == total
    names = [parameter["name"] for parameter in p["parameters"]]
    assert [{key: row[key] for key in names} for row in all_rows] == p["candidates"]
    assert all(feasible(row, p) for row in all_rows)


@pytest.mark.parametrize("folder", FOLDERS)
def test_fixed_pending_refill_practice_is_six_two_to_eight_zero(folder):
    p = load(folder, "pending-practice.chembo.json")
    assert (len(p["observations"]), len(p["pending"])) == (6, 2)
    p["observations"].extend(read_observations(p, ROOT / folder / "followup-results.csv"))
    updated = reconcile_project(p)
    assert (len(updated["observations"]), len(updated["pending"])) == (8, 0)
    assert p["pending"], "Reconciliation should not mutate the learner's input dictionary."
    empty = load(folder, "empty-project.chembo.json")
    empty["observations"] = read_observations(empty, ROOT / folder / "seed-observations.csv")
    assert empty["observations"] == load(folder)["observations"]


def test_variants_and_guide_counts_match_the_shipped_data():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for record in manifest["exercises"]:
        p = load(record["folder"])
        assert record["seed_rows"] == len(p["observations"])
        assert record["predictions_before_recommend"] == len(candidate_pool(p))
    for engine in ("gryffin", "atlas"):
        p = load("01_quickstart", engine + "-project.chembo.json")
        assert p["engine"] == engine and not p["candidates"]
        assert all("step" not in parameter for parameter in p["parameters"])
    three = load("03_pareto", "three-objective-project.chembo.json")
    assert len(three["objectives"]) == 3 and len(three["observations"]) == 6
    binary = load("04_classification", "binary-project.chembo.json")
    assert {row["outcome"] for row in binary["observations"]} == {"成功", "失败"}
    classes = load("04_classification")
    assert {label: sum(row["morphology"] == label for row in classes["observations"])
            for label in classes["classification"]["labels"]} == {"团聚": 2, "球形": 2, "棒状": 2}
