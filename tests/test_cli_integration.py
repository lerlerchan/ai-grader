import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

import ai_grader.cli as cli_module
from ai_grader.cli import cli


def test_mark_command_writes_expected_csv_with_stubbed_grade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scheme_path = tmp_path / "scheme.md"
    scheme_path.write_text(
        "\n".join(
            [
                "# Simple Marking Scheme",
                "",
                "## Q1. Exact answer (1 mark)",
                "",
                "- Award 1 mark only if the answer is exactly APPLE.",
                "- Award 0 marks otherwise.",
            ]
        ),
        encoding="utf-8",
    )

    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    submission_path = submissions_dir / "Alice_Smith_MATH101_2026A_quiz_D240051A.md"
    submission_path.write_text("Q1: APPLE\n", encoding="utf-8")

    output_dir = tmp_path / "output"
    runner = CliRunner()

    class FakeClient:
        def __init__(self, host: str) -> None:
            self.host = host

        def list(self) -> dict:
            return {"models": [{"model": "fake-model"}]}

    def fake_grade(*args, **kwargs) -> dict:
        return {"Q1": 1, "reasoning": {"Q1": "exact match"}}

    monkeypatch.setattr(cli_module.ollama, "Client", FakeClient)
    monkeypatch.setattr(cli_module, "grade", fake_grade)

    result = runner.invoke(
        cli,
        [
            "mark",
            "--scheme",
            str(scheme_path),
            "--submissions",
            str(submissions_dir),
            "--model",
            "fake-model",
            "--output",
            str(output_dir),
            "--format",
            "csv",
            "--questions",
            "Q1",
            "--ollama-host",
            "http://fake-ollama",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Found 1 submission(s)." in result.output

    with (output_dir / "marks.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {
            "student_id": "D240051A",
            "name": "Alice Smith",
            "Q1": "1",
            "total": "1",
        }
    ]


@pytest.mark.integration
def test_mark_command_live_ollama_smoke_writes_non_error_csv(
    tmp_path: Path,
    live_ollama_client,
    ollama_host: str,
    ollama_model: str,
) -> None:
    scheme_path = tmp_path / "scheme.md"
    scheme_path.write_text(
        "\n".join(
            [
                "# Simple Marking Scheme",
                "",
                "## Q1. Exact answer (1 mark)",
                "",
                "- Award 1 mark only if the answer is exactly APPLE.",
                "- Award 0 marks otherwise.",
            ]
        ),
        encoding="utf-8",
    )

    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    submission_path = submissions_dir / "Alice_Smith_MATH101_2026A_quiz_D240051A.md"
    submission_path.write_text("Q1: APPLE\n", encoding="utf-8")

    output_dir = tmp_path / "output"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "mark",
            "--scheme",
            str(scheme_path),
            "--submissions",
            str(submissions_dir),
            "--model",
            ollama_model,
            "--output",
            str(output_dir),
            "--format",
            "csv",
            "--questions",
            "Q1",
            "--ollama-host",
            ollama_host,
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Found 1 submission(s)." in result.output

    with (output_dir / "marks.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {
            "student_id": "D240051A",
            "name": "Alice Smith",
            "Q1": rows[0]["Q1"],
            "total": rows[0]["total"],
        }
    ]
    score = int(rows[0]["Q1"])
    total = int(rows[0]["total"])

    assert -1 <= score <= 1
    assert total == score
