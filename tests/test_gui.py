import io
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_grader.cli import cli
from ai_grader.gui import browser_url, create_app
from ai_grader.launcher import main as launcher_main
from ai_grader.submission_loader import Submission


def test_index_renders_default_configuration() -> None:
    app = create_app(default_questions=["Q1", "Q2"], default_dpi=180)
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "AI Grader Studio" in page
    assert "Q1,Q2" in page
    assert "180" in page


def test_api_models_returns_sorted_model_names() -> None:
    app = create_app()

    class FakeClient:
        def __init__(self, host: str) -> None:
            self.host = host

        def list(self) -> dict:
            return {"models": [{"model": "zeta"}, {"model": "alpha"}]}

    app.config["OLLAMA_CLIENT_FACTORY"] = FakeClient
    client = app.test_client()

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "models": ["alpha", "zeta"],
        "message": "",
    }


def test_job_stream_and_download_work_with_fake_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(default_questions=["Q1"])

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args

        def start(self) -> None:
            self.target(*self.args)

    class NoopTimer:
        def __init__(self, interval, function, args=()):
            self.function = function
            self.args = args
            self.daemon = False

        def start(self) -> None:
            return None

        def cancel(self) -> None:
            return None

    class FakeClient:
        def __init__(self, host: str) -> None:
            self.host = host

        def list(self) -> dict:
            return {"models": [{"model": "fake-model"}]}

    def fake_load_scheme(path: str) -> str:
        return "scheme"

    def fake_discover(folder: str) -> list[Submission]:
        return [Submission(student_id="D240051A", name="Alice", path=str(tmp_path / "alice.md"))]

    def fake_load(submission: Submission, dpi: int = 150) -> Submission:
        submission.mode = "text"
        submission.text = "Q1: APPLE"
        return submission

    def fake_grade(*args, **kwargs) -> dict:
        return {"Q1": 1, "reasoning": {"Q1": "ok"}}

    def fake_write_results(results, output_dir, questions, formats) -> list[str]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        csv_path = output / "marks.csv"
        xlsx_path = output / "marks.xlsx"
        csv_path.write_text("student_id,name,Q1,total\nD240051A,Alice,1,1\n", encoding="utf-8")
        xlsx_path.write_text("placeholder", encoding="utf-8")
        return [str(xlsx_path), str(csv_path)]

    app.config.update(
        OLLAMA_CLIENT_FACTORY=FakeClient,
        LOAD_SCHEME=fake_load_scheme,
        DISCOVER=fake_discover,
        LOAD_SUBMISSION=fake_load,
        GRADE=fake_grade,
        WRITE_RESULTS=fake_write_results,
        THREAD_FACTORY=ImmediateThread,
        TIMER_FACTORY=NoopTimer,
    )

    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    client = app.test_client()
    client.get("/")

    response = client.post(
        "/api/jobs",
        data={
            "scheme": (io.BytesIO(b"# Scheme"), "scheme.md"),
            "submissions_path": str(submissions_dir),
            "model": "fake-model",
            "questions": "Q1",
            "dpi": "150",
        },
        headers={"X-CSRF-Token": _csrf_token(client)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True

    stream = client.get(f"/api/jobs/{payload['job_id']}/stream")
    stream_text = stream.get_data(as_text=True)
    assert '"type": "progress"' in stream_text
    assert '"type": "done"' in stream_text

    download = client.get(f"/download/{payload['job_id']}/marks.csv")
    assert download.status_code == 200
    assert "D240051A" in download.get_data(as_text=True)


def test_launcher_main_calls_run(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run": False}

    def fake_run() -> None:
        called["run"] = True

    monkeypatch.setattr("ai_grader.gui.run", fake_run)

    launcher_main()

    assert called["run"] is True


def test_gui_command_invokes_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_run(**kwargs) -> None:
        called.update(kwargs)

    monkeypatch.setattr("ai_grader.gui.run", fake_run)

    result = CliRunner().invoke(
        cli,
        ["gui", "--no-browser", "--questions", "Q1,Q2", "--dpi", "180"],
    )

    assert result.exit_code == 0
    assert called["open_browser"] is False
    assert called["default_questions"] == ["Q1", "Q2"]
    assert called["default_dpi"] == 180


def test_gui_command_refuses_non_local_host_without_flag() -> None:
    result = CliRunner().invoke(cli, ["gui", "--host", "0.0.0.0", "--no-browser"])

    assert result.exit_code != 0
    assert "--unsafe-expose" in result.output


def test_browser_url_formats_bind_addresses() -> None:
    assert browser_url("127.0.0.1", 5000) == "http://127.0.0.1:5000"
    assert browser_url("0.0.0.0", 5000) == "http://127.0.0.1:5000"
    assert browser_url("::1", 5000) == "http://[::1]:5000"


def test_api_jobs_rejects_missing_csrf_token(tmp_path: Path) -> None:
    app = create_app(default_questions=["Q1"])
    client = app.test_client()
    client.get("/")

    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()

    response = client.post(
        "/api/jobs",
        data={
            "scheme": (io.BytesIO(b"# Scheme"), "scheme.md"),
            "submissions_path": str(submissions_dir),
            "model": "fake-model",
            "questions": "Q1",
            "dpi": "150",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 403


def test_stream_resumes_from_last_event_id_query() -> None:
    app = create_app()
    app.extensions["jobs"]["job-1"] = _completed_job()
    client = app.test_client()

    response = client.get("/api/jobs/job-1/stream?last_event_id=1")
    body = response.get_data(as_text=True)

    assert "id: 2" in body
    assert '"type": "done"' in body
    assert '"type": "progress"' not in body


def test_stream_resumes_from_last_event_id_header() -> None:
    app = create_app()
    app.extensions["jobs"]["job-1"] = _completed_job()
    client = app.test_client()

    response = client.get("/api/jobs/job-1/stream", headers={"Last-Event-ID": "1"})
    body = response.get_data(as_text=True)

    assert "id: 2" in body
    assert '"type": "done"' in body
    assert '"type": "progress"' not in body


def _completed_job():
    from ai_grader.gui import JobState, _emit

    job = JobState()
    _emit(job, {"type": "init", "total_submissions": 1, "questions": ["Q1"], "model": "fake-model"})
    _emit(
        job,
        {
            "type": "progress",
            "current": 1,
            "total_submissions": 1,
            "student_id": "D240051A",
            "name": "Alice",
            "marks": {"Q1": 1},
            "total": 1,
            "mode": "text",
            "flagged": False,
        },
    )
    _emit(job, {"type": "done", "graded": 1, "failed": 0, "files": []})
    return job


def _csrf_token(client) -> str:
    with client.session_transaction() as session:
        return session["csrf_token"]
