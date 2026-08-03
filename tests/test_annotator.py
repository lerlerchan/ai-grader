from pathlib import Path

import fitz
import pytest

from ai_grader.annotator import annotate


def _make_pdf(path: Path, pages: int = 2) -> None:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    doc.save(str(path))
    doc.close()


def test_annotate_inserts_cover_page_and_badges(tmp_path: Path) -> None:
    source = tmp_path / "student.pdf"
    _make_pdf(source, pages=2)
    output = tmp_path / "annotated" / "student.pdf"

    marks = {
        "Q1": 2,
        "Q2": 1,
        "Q3": 0,
        "reasoning": {"Q1": "correct method", "Q2": "partial credit", "Q3": "blank"},
        "location": {
            "Q1": {"page": 1, "region": "top-left"},
            "Q2": {"page": 3, "region": "top-left"},  # out of range, must be skipped
        },
    }

    annotate(str(source), "Alice Tan", "D240051A", ["Q1", "Q2", "Q3"], marks, str(output))

    assert output.exists()
    doc = fitz.open(str(output))
    assert doc.page_count == 3  # cover page + 2 original pages

    cover_text = doc[0].get_text()
    assert "Alice Tan" in cover_text
    assert "D240051A" in cover_text
    assert "Q1: 2" in cover_text
    assert "Q3: 0" in cover_text
    assert "correct method" in cover_text

    page1_text = doc[1].get_text()
    assert "Q1: 2" in page1_text  # badge drawn on original page 1 (now index 1)
    doc.close()


def test_annotate_skips_all_badges_when_no_valid_locations(tmp_path: Path) -> None:
    source = tmp_path / "student.pdf"
    _make_pdf(source, pages=1)
    output = tmp_path / "student_annotated.pdf"

    marks = {
        "Q1": 1,
        "reasoning": {"Q1": "ok"},
        "location": {},
    }

    annotate(str(source), "Bob Lee", "D240052A", ["Q1"], marks, str(output))

    doc = fitz.open(str(output))
    assert doc.page_count == 2  # cover page + 1 original page, no crash
    assert "Q1: 1" in doc[0].get_text()  # still on cover page
    doc.close()
