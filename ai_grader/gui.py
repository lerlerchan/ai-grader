"""
gui.py — Local Flask web app for non-technical teachers.
"""

from __future__ import annotations

import atexit
import ipaddress
import json
import os
import secrets
import shutil
import tempfile
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import ollama
from flask import Flask, Response, abort, jsonify, render_template, request, send_file, session, stream_with_context
from werkzeug.utils import secure_filename

from .exporter import write_results
from .grader import grade
from .scheme_parser import load_scheme
from .submission_loader import Submission, discover, load

_DEFAULT_QUESTIONS = ["Q1", "Q2", "Q3", "Q4"]
_DEFAULT_FORMATS = ["excel", "csv"]
_JOB_RETENTION_SECONDS = 3600
_POST_DOWNLOAD_RETENTION_SECONDS = 300
_APP_TEMP_DIR_NAME = "ai-grader"


@dataclass
class JobState:
    history: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    job_root: str = ""
    cleanup_timer: threading.Timer | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    condition: threading.Condition = field(default_factory=threading.Condition)
    active_downloads: int = 0
    cleanup_requested: bool = False
    next_event_id: int = 0
    latest_event_type: str = "pending"


def create_app(
    *,
    ollama_host: str = "http://localhost:11434",
    default_questions: list[str] | None = None,
    default_dpi: int = 150,
) -> Flask:
    _purge_stale_job_dirs()
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("AI_GRADER_SECRET_KEY", secrets.token_hex(32))
    app.config.update(
        DEFAULT_OLLAMA_HOST=ollama_host,
        DEFAULT_QUESTIONS=default_questions or list(_DEFAULT_QUESTIONS),
        DEFAULT_DPI=default_dpi,
        OUTPUT_FORMATS=list(_DEFAULT_FORMATS),
        THREAD_FACTORY=threading.Thread,
        TIMER_FACTORY=threading.Timer,
        OLLAMA_CLIENT_FACTORY=ollama.Client,
        LOAD_SCHEME=load_scheme,
        DISCOVER=discover,
        LOAD_SUBMISSION=load,
        GRADE=grade,
        WRITE_RESULTS=write_results,
    )
    app.extensions["jobs"] = {}
    app.extensions["jobs_lock"] = threading.Lock()

    @app.before_request
    def protect_post_routes() -> None:
        if request.method != "POST":
            return
        _verify_same_origin_request()
        if request.headers.get("X-CSRF-Token") != session.get("csrf_token"):
            abort(403)

    @app.get("/")
    def index() -> str:
        session["csrf_token"] = session.get("csrf_token") or secrets.token_urlsafe(32)
        return render_template(
            "index.html",
            default_questions=",".join(app.config["DEFAULT_QUESTIONS"]),
            default_dpi=app.config["DEFAULT_DPI"],
            default_ollama_host=app.config["DEFAULT_OLLAMA_HOST"],
            csrf_token=session["csrf_token"],
        )

    @app.get("/api/browse-folder")
    def api_browse_folder() -> Response:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", True)
            path = filedialog.askdirectory(parent=root, title="Select submissions folder")
            root.destroy()
            if path:
                return jsonify({"ok": True, "path": path})
            return jsonify({"ok": False, "path": ""})
        except Exception as exc:
            return jsonify({"ok": False, "path": "", "message": str(exc)})

    @app.get("/api/models")
    def api_models() -> Response:
        try:
            names = _list_model_names(app)
        except Exception as exc:
            return jsonify(
                {
                    "ok": False,
                    "models": [],
                    "message": (
                        f"Cannot reach Ollama at {app.config['DEFAULT_OLLAMA_HOST']}. "
                        "Start Ollama and pull a model before grading."
                    ),
                    "details": str(exc),
                }
            )

        return jsonify({"ok": True, "models": names, "message": ""})

    @app.post("/api/jobs")
    def create_job() -> Response:
        scheme_file = request.files.get("scheme")
        submissions_path = (request.form.get("submissions_path") or "").strip()
        model = (request.form.get("model") or "").strip()
        questions = _normalize_questions(
            request.form.get("questions") or ",".join(app.config["DEFAULT_QUESTIONS"])
        )
        dpi_value = request.form.get("dpi") or str(app.config["DEFAULT_DPI"])

        if not scheme_file or not scheme_file.filename:
            return jsonify({"ok": False, "message": "Please choose a marking scheme file."}), 400
        if not submissions_path:
            return jsonify({"ok": False, "message": "Please enter the submissions folder path."}), 400
        if not os.path.isdir(submissions_path):
            return jsonify(
                {
                    "ok": False,
                    "message": f"Submissions folder not found: {submissions_path}",
                }
            ), 400
        if not model:
            return jsonify({"ok": False, "message": "Please choose an Ollama model."}), 400
        if not questions:
            return jsonify({"ok": False, "message": "Please provide at least one question label."}), 400

        try:
            dpi = int(dpi_value)
        except ValueError:
            return jsonify({"ok": False, "message": "DPI must be a whole number."}), 400
        if not 72 <= dpi <= 300:
            return jsonify({"ok": False, "message": "DPI must be between 72 and 300."}), 400

        job_id = uuid.uuid4().hex
        job_root = Path(tempfile.mkdtemp(prefix=f"job-{job_id}-", dir=_app_temp_root()))
        job = JobState(job_root=str(job_root))
        with app.extensions["jobs_lock"]:
            app.extensions["jobs"][job_id] = job
        uploads_dir = job_root / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        output_dir = job_root / "output"

        filename = secure_filename(scheme_file.filename) or "scheme.txt"
        scheme_path = uploads_dir / filename
        scheme_file.save(scheme_path)

        thread = app.config["THREAD_FACTORY"](
            target=_run_job,
            args=(app, job_id, str(scheme_path), submissions_path, model, questions, dpi, str(output_dir)),
            daemon=True,
        )
        thread.start()

        return jsonify({"ok": True, "job_id": job_id})

    @app.get("/api/jobs/<job_id>/stream")
    def stream_job(job_id: str) -> Response:
        with app.extensions["jobs_lock"]:
            job = app.extensions["jobs"].get(job_id)
        if job is None:
            return Response(
                _format_sse({"type": "error", "message": "Unknown grading job."}),
                mimetype="text/event-stream",
            )

        raw_last_event_id = (
            request.headers.get("Last-Event-ID")
            or request.args.get("last_event_id")
            or "-1"
        )
        try:
            last_event_id = int(raw_last_event_id)
        except ValueError:
            last_event_id = -1

        def generate() -> Any:
            cursor = last_event_id + 1
            while True:
                with job.condition:
                    while cursor >= len(job.history):
                        if job.latest_event_type in {"done", "error"}:
                            return
                        job.condition.wait(timeout=30)
                        if cursor >= len(job.history) and job.latest_event_type in {"done", "error"}:
                            return

                    event = job.history[cursor]

                yield _format_sse(event)
                cursor += 1
                if event["type"] in {"done", "error"}:
                    return

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.get("/download/<job_id>/<name>")
    def download(job_id: str, name: str) -> Response:
        with app.extensions["jobs_lock"]:
            job = app.extensions["jobs"].get(job_id)
        if job is None:
            return jsonify({"ok": False, "message": "File not found."}), 404

        with job.lock:
            path = job.files.get(name)
            if path is None:
                return jsonify({"ok": False, "message": "File not found."}), 404
            handle = open(path, "rb")
            job.active_downloads += 1

        response = send_file(handle, as_attachment=True, download_name=name)
        response.call_on_close(lambda: _finish_download(app, job_id, handle))
        _schedule_cleanup(app, job_id, _POST_DOWNLOAD_RETENTION_SECONDS)
        return response

    return app


def run(
    *,
    host: str = "127.0.0.1",
    port: int = 5000,
    open_browser: bool = True,
    ollama_host: str = "http://localhost:11434",
    default_questions: list[str] | None = None,
    default_dpi: int = 150,
) -> None:
    app = create_app(
        ollama_host=ollama_host,
        default_questions=default_questions,
        default_dpi=default_dpi,
    )
    atexit.register(_cleanup_all_jobs, app)
    url = browser_url(host, port)
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, use_reloader=False)


def _run_job(
    app: Flask,
    job_id: str,
    scheme_path: str,
    submissions_path: str,
    model: str,
    questions: list[str],
    dpi: int,
    output_dir: str,
) -> None:
    with app.extensions["jobs_lock"]:
        job = app.extensions["jobs"][job_id]

    try:
        available_models = _list_model_names(app)
        if model not in available_models:
            _emit(job, {"type": "pulling", "message": f"Model '{model}' not found locally. Downloading from Ollama — this may take a few minutes…"})
            try:
                client_factory = app.config["OLLAMA_CLIENT_FACTORY"]
                client = client_factory(host=app.config["DEFAULT_OLLAMA_HOST"])
                client.pull(model)
            except Exception as pull_exc:
                _emit(job, {"type": "error", "message": f"Could not download '{model}': {pull_exc}"})
                return
            _emit(job, {"type": "pull_done", "message": f"'{model}' downloaded. Starting grading…"})

        scheme_text = app.config["LOAD_SCHEME"](scheme_path)
        submissions = app.config["DISCOVER"](submissions_path)
        if not submissions:
            _emit(
                job,
                {
                    "type": "error",
                    "message": f"No supported submissions found in: {submissions_path}",
                },
            )
            return

        _emit(
            job,
            {
                "type": "init",
                "total_submissions": len(submissions),
                "questions": questions,
                "model": model,
            },
        )

        results = []
        for index, submission in enumerate(submissions, start=1):
            try:
                app.config["LOAD_SUBMISSION"](submission, dpi=dpi)
                marks = app.config["GRADE"](
                    submission,
                    scheme_text,
                    model,
                    app.config["DEFAULT_OLLAMA_HOST"],
                    questions,
                )
                result = {
                    "student_id": submission.student_id,
                    "name": submission.name,
                    "reasoning": marks.get("reasoning", {}),
                }
                for question in questions:
                    result[question] = marks.get(question, -1)
            except Exception as exc:
                result = _error_result(submission, questions, str(exc))

            results.append(result)
            q_vals = [result.get(question, -1) for question in questions]
            total = sum(q_vals) if all(value >= 0 for value in q_vals) else -1
            _emit(
                job,
                {
                    "type": "progress",
                    "current": index,
                    "total_submissions": len(submissions),
                    "student_id": result["student_id"],
                    "name": result["name"],
                    "marks": {question: result.get(question, -1) for question in questions},
                    "total": total,
                    "mode": submission.mode,
                    "flagged": total < 0,
                },
            )

        written = app.config["WRITE_RESULTS"](
            results,
            output_dir,
            questions,
            app.config["OUTPUT_FORMATS"],
        )
        job.files = {Path(path).name: path for path in written}
        _emit(
            job,
            {
                "type": "done",
                "graded": len(results),
                "failed": sum(
                    1 for result in results if any(result.get(question, -1) < 0 for question in questions)
                ),
                "files": [
                    {
                        "name": name,
                        "url": f"/download/{job_id}/{name}",
                    }
                    for name in job.files
                ],
            },
        )
    except Exception as exc:
        _emit(job, {"type": "error", "message": str(exc)})
    finally:
        _schedule_cleanup(app, job_id, _JOB_RETENTION_SECONDS)


def _emit(job: JobState, payload: dict[str, Any]) -> None:
    with job.condition:
        event = {"id": job.next_event_id, **payload}
        job.next_event_id += 1
        job.latest_event_type = payload["type"]
        job.history.append(event)
        job.condition.notify_all()


def _format_sse(payload: dict[str, Any]) -> str:
    prefix = f"id: {payload['id']}\n" if "id" in payload else ""
    return f"{prefix}data: {json.dumps(payload)}\n\n"


def _normalize_questions(raw: str) -> list[str]:
    return [question.strip().upper() for question in raw.split(",") if question.strip()]


def _list_model_names(app: Flask) -> list[str]:
    client_factory: Callable[..., Any] = app.config["OLLAMA_CLIENT_FACTORY"]
    client = client_factory(host=app.config["DEFAULT_OLLAMA_HOST"])
    response = client.list()

    if isinstance(response, dict):
        models = response.get("models", [])
    else:
        models = getattr(response, "models", [])

    names = []
    for model in models:
        if isinstance(model, dict):
            name = model.get("model") or model.get("name")
        else:
            name = getattr(model, "model", None) or getattr(model, "name", None)
        if name:
            names.append(name)
    return sorted(names)


def _error_result(submission: Submission, questions: list[str], error_message: str) -> dict[str, Any]:
    result = {"student_id": submission.student_id, "name": submission.name, "reasoning": {}}
    for question in questions:
        result[question] = -1
        result["reasoning"][question] = error_message if question == questions[0] else ""
    return result


def _schedule_cleanup(app: Flask, job_id: str, delay_seconds: int) -> None:
    with app.extensions["jobs_lock"]:
        job = app.extensions["jobs"].get(job_id)
    if job is None:
        return

    with job.lock:
        if job.cleanup_timer is not None:
            job.cleanup_timer.cancel()

        timer = app.config["TIMER_FACTORY"](delay_seconds, _cleanup_job, args=(app, job_id))
        timer.daemon = True
        job.cleanup_timer = timer
    timer.start()


def _cleanup_job(app: Flask, job_id: str) -> None:
    with app.extensions["jobs_lock"]:
        job = app.extensions["jobs"].get(job_id)
    if job is None:
        return

    with job.lock:
        if job.active_downloads > 0:
            job.cleanup_requested = True
            return
        if job.cleanup_timer is not None:
            job.cleanup_timer.cancel()
        job.cleanup_timer = None
        job_root = job.job_root

    with app.extensions["jobs_lock"]:
        app.extensions["jobs"].pop(job_id, None)

    if job_root:
        shutil.rmtree(job_root, ignore_errors=True)


def _finish_download(app: Flask, job_id: str, handle: Any) -> None:
    try:
        handle.close()
    finally:
        with app.extensions["jobs_lock"]:
            job = app.extensions["jobs"].get(job_id)
        if job is None:
            return

        should_cleanup = False
        with job.lock:
            job.active_downloads = max(0, job.active_downloads - 1)
            if job.active_downloads == 0 and job.cleanup_requested:
                job.cleanup_requested = False
                should_cleanup = True

        if should_cleanup:
            _cleanup_job(app, job_id)


def browser_url(host: str, port: int) -> str:
    display_host = host
    if host == "0.0.0.0":
        display_host = "127.0.0.1"
    else:
        try:
            address = ipaddress.ip_address(host)
            if address.version == 6:
                display_host = f"[{host}]"
        except ValueError:
            display_host = host

    return f"http://{display_host}:{port}"


def _app_temp_root() -> str:
    root = Path(tempfile.gettempdir()) / _APP_TEMP_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return str(root)


def _purge_stale_job_dirs() -> None:
    root = Path(_app_temp_root())
    cutoff = time.time() - _JOB_RETENTION_SECONDS
    for path in root.glob("job-*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except FileNotFoundError:
            continue


def _cleanup_all_jobs(app: Flask) -> None:
    with app.extensions["jobs_lock"]:
        job_ids = list(app.extensions["jobs"].keys())
    for job_id in job_ids:
        _cleanup_job(app, job_id)


def _verify_same_origin_request() -> None:
    expected_origin = request.host_url.rstrip("/")
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")

    if origin and origin != expected_origin:
        abort(403)
    if referer and not referer.startswith(expected_origin):
        abort(403)
