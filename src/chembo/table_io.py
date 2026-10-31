"""Strict, read-only tabular input for CSV and legacy/modern Excel workbooks."""
from __future__ import annotations

import csv
import math
from pathlib import Path


def sheet_names(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return []
    if path.suffix.lower() not in (".xls", ".xlsx"):
        raise ValueError("只支持 CSV、XLS 或 XLSX 文件。")
    import pandas as pd
    try:
        with pd.ExcelFile(path, engine="xlrd" if path.suffix.lower() == ".xls" else "openpyxl") as workbook:
            return list(workbook.sheet_names)
    except ImportError as exc:
        raise ValueError("当前安装包缺少 Excel 读取组件，请使用完整版或先另存为 CSV。") from exc
    except Exception as exc:
        raise ValueError(f"不能读取 Excel 工作簿：{exc}") from exc


def _missing(value):
    return value is None or isinstance(value, str) and not value.strip() or isinstance(value, float) and math.isnan(value)


def _normalize(raw_rows, source):
    if not raw_rows:
        raise ValueError(f"{source} 不能为空。")
    header = raw_rows[0]
    # Excel readers can retain formatting-only trailing cells. Remove a column
    # only if every row, including its header, is blank in that column.
    width = max(len(row) for row in raw_rows)
    while width and all(len(row) < width or _missing(row[width - 1]) for row in raw_rows):
        width -= 1
    header = list(header[:width])
    if len(header) < width:
        header.extend([None] * (width - len(header)))
    if not width or any(not isinstance(value, str) or not value.strip() for value in header):
        raise ValueError(f"{source} 必须有非空文字列名。")
    columns = [value.strip() for value in header]
    if len(set(columns)) != len(columns):
        raise ValueError(f"{source} 列名不能重复。")
    records = []
    for number, values in enumerate(raw_rows[1:], 2):
        values = list(values)
        if all(_missing(value) for value in values):
            continue
        if len(values) > width and any(not _missing(value) for value in values[width:]):
            raise ValueError(f"{source} 第 {number} 行列数过多。")
        if len(values) < width:
            values.extend([None] * (width - len(values)))
        values = [None if _missing(value) else value for value in values[:width]]
        if any(value is None for value in values):
            raise ValueError(f"{source} 第 {number} 行有缺失单元格，请补齐后导入。")
        records.append(dict(zip(columns, values)))
    return columns, records


def read_table(path, sheet_name=None):
    """Return ordered column names and complete row dictionaries.

    Formula cells in XLSX use cached values from the spreadsheet application.
    Missing formula caches are rejected rather than evaluated or imputed.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                return _normalize(list(csv.reader(stream)), "CSV")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV 请保存为 UTF-8 编码，或直接导入 Excel 工作簿。") from exc
    if suffix not in (".xls", ".xlsx"):
        raise ValueError("只支持 CSV、XLS 或 XLSX 文件。")
    names = sheet_names(path)
    if not names:
        raise ValueError("Excel 工作簿没有工作表。")
    if sheet_name is None:
        if len(names) > 1:
            raise ValueError("工作簿包含多个工作表，请先选择需要导入的工作表。")
        sheet_name = names[0]
    if sheet_name not in names:
        raise ValueError("选定的工作表不存在。")
    import pandas as pd
    try:
        # header=None avoids pandas silently renaming duplicate Excel headers.
        frame = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object,
                              keep_default_na=False,
                              engine="xlrd" if suffix == ".xls" else "openpyxl")
        return _normalize(frame.values.tolist(), f"工作表 {sheet_name}")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"不能读取工作表 {sheet_name}：{exc}") from exc
