import csv
from pathlib import Path

import openpyxl

from ai_grader.exporter import write_results


def test_write_results_creates_csv_and_excel_outputs(tmp_path: Path) -> None:
    results = [
        {
            "student_id": "D240051A",
            "name": "Alice",
            "Q1": 1,
            "Q2": 1,
            "reasoning": {"Q1": "correct", "Q2": "correct"},
        },
        {
            "student_id": "D240052A",
            "name": "Bob",
            "Q1": -1,
            "Q2": 1,
            "reasoning": {"Q1": "parse failed", "Q2": ""},
        },
    ]

    written = write_results(results, str(tmp_path), ["Q1", "Q2"], ["csv", "excel"])

    assert sorted(Path(path).name for path in written) == ["marks.csv", "marks.xlsx"]

    with (tmp_path / "marks.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {
            "student_id": "D240051A",
            "name": "Alice",
            "Q1": "1",
            "Q2": "1",
            "total": "2",
        },
        {
            "student_id": "D240052A",
            "name": "Bob",
            "Q1": "-1",
            "Q2": "1",
            "total": "-1",
        },
    ]

    workbook = openpyxl.load_workbook(tmp_path / "marks.xlsx")
    marks_sheet = workbook["Marks"]
    reasoning_sheet = workbook["Reasoning"]

    assert marks_sheet.max_row == 3
    assert marks_sheet["E2"].value == 2
    assert marks_sheet["E3"].value == -1
    assert reasoning_sheet["C2"].value == "correct"
    assert reasoning_sheet["C3"].value == "parse failed"
