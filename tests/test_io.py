"""Read actual workbooks without implicit missing-value filling or header repair."""
import pytest

from chembo.engine import read_candidates, read_observations
from chembo.table_io import read_table, sheet_names


def project():
    return {"engine": "bo-mcp", "parameters": [{"name": "A", "type": "continuous", "low": 0, "high": 1, "step": 0.1}],
            "objectives": [{"name": "yield", "goal": "max"}], "observations": [], "pending": []}


def workbook(path, sheets):
    import openpyxl
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    book.save(path)
    return path


def test_xlsx_actual_numeric_values_and_explicit_sheet_selection(tmp_path):
    path = workbook(tmp_path / "results.xlsx", {"measured": [["A", "yield"], [0.3, 0]], "candidates": [["A"], [0.4], [0.5]]})
    assert sheet_names(path) == ["measured", "candidates"]
    with pytest.raises(ValueError, match="多个"):
        read_table(path)
    assert read_observations(project(), path, "measured") == [{"A": 0.3, "yield": 0.0}]
    assert read_candidates(project(), path, "candidates") == [{"A": 0.4}, {"A": 0.5}]
    with pytest.raises(ValueError, match="不存在"):
        read_table(path, "absent")
    with pytest.raises(ValueError, match="候选表只包含"):
        read_candidates(project(), path, "measured")


@pytest.mark.parametrize("rows,match", [
    ([["A", "A"], [0.3, 1]], "重复"),
    ([["A", None], [0.3, 1]], "列名"),
    ([["A", "yield"], [0.3, None]], "缺失"),
    ([["A", "yield"], [None, 1]], "缺失"),
    ([["A", "yield"], [0.3, "=1+1"]], "缺失"),
])
def test_xlsx_rejects_duplicate_headers_missing_cells_and_uncached_formulas(tmp_path, rows, match):
    path = workbook(tmp_path / "bad.xlsx", {"data": rows})
    with pytest.raises(ValueError, match=match):
        read_table(path)


def test_excel_classification_labels_and_literal_na(tmp_path):
    p = project()
    p.update(task="classification", classification={"labels": ["0", "1", "NA"]})
    path = workbook(tmp_path / "labels.xlsx", {"data": [["A", "yield"], [0.1, 0], [0.2, 1], [0.3, "NA"]]})
    assert [row["yield"] for row in read_observations(p, path)] == ["0", "1", "NA"]


def test_csv_bom_blank_rows_and_literal_na_are_preserved(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("\ufeffA,label\n0,NA\n\n", encoding="utf-8")
    assert sheet_names(path) == []
    assert read_table(path) == (["A", "label"], [{"A": "0", "label": "NA"}])
    for text in ["A,A\n0,1\n", "A,label\n0,\n", "A,label\n,NA\n", "A,label\n0,NA,extra\n"]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            read_table(path)


def test_candidate_table_is_nonempty_distinct_and_domain_checked(tmp_path):
    path = tmp_path / "candidates.csv"
    for text in ["A\n", "A\n0.2\n0.2\n", "A\n0.25\n", "A\n1.1\n"]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            read_candidates(project(), path)
    path.write_text("A\n0.2\n0.4\n", encoding="utf-8")
    assert read_candidates(project(), path) == [{"A": 0.2}, {"A": 0.4}]


def test_unsupported_or_corrupt_input_reports_error(tmp_path):
    path = tmp_path / "bad.xlsx"
    path.write_bytes(b"not an excel workbook")
    with pytest.raises(ValueError, match="不能读取"):
        read_table(path)
    path = tmp_path / "data.txt"
    path.write_text("A,yield\n0.1,1\n")
    with pytest.raises(ValueError, match="CSV"):
        read_table(path)


def test_real_biff8_xls_reader(tmp_path):
    # Compressed BIFF8 fixture generated once with xlwt; no writer dependency ships.
    import base64
    import zlib
    payload = 'eJztWEFIFFEY/t64u+4uus7aKmggi5CZeYkuXXRSSE+J1aGIoFZ3EHFZY+myXbJsj4HgqegieOlieamkgroFBUYdgiDYrWOnoKCD7vj//8zQagbOQS143/C+98///n/ev/P+9/a9ebeaLC8st1ewBf2oQ9WJIVKjU1Ri/o0JanccFv06SsXR+K8Qi9JARsJ41vi2nseQx7sCA49Cr4iBL1Qu4SpGpvN2eg8xKDFkFMfQR6xwnzQJtElUzcLjwgeEH4rlc+GTorkj3Ee2ZXURq9ZIzwkviy8YndKWAD/3ifh8Es0xtOA1Z/GNOeXahjFQmMzk/s2GjlADFkHjNmzn7UImV0aKBnARP5008MOfqS/TWr+3egXS/9qsr99GP2+EgBk4VyTBS5SQK3XcEkHOnsiMF9fIj9OSC438QBgoTtq5bJzu3Ylrbpq4jZLQDcRZNImcFF+Tlua1B9/fnx4btS6LZkYWa3dJP8RRwMFN9iDnhLRIIGLbI3xU+JY89aDI7cIpSkaqu0ZbPGFoVmxuS2sX9XNc8ME6XCN3k1z6duZpR+mrdYTkpeHK9dTSR2sBnfQXkyV/vmbRq3rVvbuMFcuvlTf9Pwu3/bEURA3Ti91xX7RqwjriIiaF3Tt+O8qzV1vsX1AfSuzPCbsjwJbGNpaG2LwRjohlv9GMx6ymxeg34tDQ0NDQ0NDQ0NDYV7gbX3e7z8cAOmLIFpbPFPxdZ51Kdb8/UmjsGs5imq5rdDA9hTzVBRQD5U8rwsp/ltqhj/+9kHGeei9gCmMSx1Sgvhl0+FK1v2fHjmbgrv6GwP1Xg8S5y/1vAOtjwJ8='
    path = tmp_path / "legacy.xls"
    path.write_bytes(zlib.decompress(base64.b64decode(payload)))
    assert sheet_names(path) == ["legacy"]
    assert read_observations(project(), path) == [{"A": 0.2, "yield": 0.0}, {"A": 0.5, "yield": 1.0}]
