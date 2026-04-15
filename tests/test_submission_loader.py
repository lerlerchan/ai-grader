from pathlib import Path

from ai_grader.submission_loader import discover, parse_filename


def test_parse_filename_extracts_student_id_and_normalizes_name() -> None:
    student_id, name = parse_filename("John__Doe_MATH101_2026A_quiz_D240051A.pdf")

    assert student_id == "D240051A"
    assert name == "John Doe"


def test_parse_filename_falls_back_to_stem_for_unmatched_names() -> None:
    student_id, name = parse_filename("freeform_submission.pdf.pdf")

    assert student_id == "freeform_submission"
    assert name == "freeform_submission"


def test_discover_filters_supported_files_and_sorts_by_filename(tmp_path: Path) -> None:
    files = [
        "Zed_MATH101_2026A_quiz_D240053A.md",
        "Amy_MATH101_2026A_quiz_D240051A.pdf.pdf",
        "Ben_MATH101_2026A_quiz_D240052A.txt",
        "ignore.jpg",
    ]
    for filename in files:
        (tmp_path / filename).write_text("sample", encoding="utf-8")

    submissions = discover(str(tmp_path))

    assert [submission.student_id for submission in submissions] == [
        "D240051A",
        "D240052A",
        "D240053A",
    ]
    assert [submission.name for submission in submissions] == ["Amy", "Ben", "Zed"]
