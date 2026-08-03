# Annotated PDF Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every graded submission gets a marked-up PDF (cover page + on-page badges) written to an `annotated/` folder, and the GUI gains real submission file upload (replacing the broken server-side-only folder path) plus a manual "clear now" cleanup action.

**Architecture:** `grader.py`'s JSON schema gains an optional per-question `location` field (page + coarse region). A new `annotator.py` module uses PyMuPDF to insert a cover page and draw region badges onto a copy of the original submission PDF. `cli.py` and `gui.py` both call `annotate()` once per submission, in addition to the existing `write_results()` call. The GUI's submissions input changes from a server-local folder path to a real multi-file upload (mirroring the existing scheme-file upload), and gets one new endpoint to trigger the *existing* job cleanup immediately instead of waiting for the timer.

**Tech Stack:** PyMuPDF (`fitz`, already a dependency), Flask, vanilla JS (no new frontend deps), pytest.

## Global Constraints

- No pixel-precise bounding boxes — location is `{"page": int, "region": one of 6 named regions}`. Source: spec approval, 2026-08-03.
- Missing/invalid `location` for a question → skip its on-page badge only; cover page still shows the mark. Never abort a submission over annotation.
- Annotated PDFs live in `<output_dir>/annotated/`. Never touch `exporter.py`'s existing `marks.xlsx`/`marks.csv` format.
- "Clear this batch" is always an explicit user action — no new timed/automatic deletion (the GUI already has automatic retention timers; don't change those).
- No new PyPI dependencies — PyMuPDF is already in `pyproject.toml`.

---

### Task 1: Grader — extend schema with per-question `location`

**Files:**
- Modify: `ai_grader/grader.py:14-138`
- Test: `tests/test_grader.py`

**Interfaces:**
- Produces: `grade()`/`_parse_response()` return dict now always includes a `"location"` key: `dict[str, dict[str, int | str]]`, mapping question label → `{"page": int, "region": str}` for *valid* entries only. Missing/invalid ones are simply absent from this dict (not `None`, not present with garbage values). Region is one of: `"top-left"`, `"top-right"`, `"mid-left"`, `"mid-right"`, `"bottom-left"`, `"bottom-right"`.

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/test_grader.py` with:

```python
from ai_grader.grader import _parse_response


def test_parse_response_accepts_valid_json() -> None:
    raw = """
    {
      "questions": {"Q1": 1, "Q2": 0},
      "reasoning": {"Q1": "exact match", "Q2": "missing answer"}
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2"])

    assert parsed == {
        "Q1": 1,
        "Q2": 0,
        "reasoning": {"Q1": "exact match", "Q2": "missing answer"},
        "location": {},
    }


def test_parse_response_extracts_json_wrapped_in_extra_text() -> None:
    raw = 'Here is the result: {"questions": {"Q1": 1}, "reasoning": {"Q1": "ok"}}'

    parsed = _parse_response(raw, ["Q1"])

    assert parsed["Q1"] == 1
    assert parsed["reasoning"]["Q1"] == "ok"
    assert parsed["location"] == {}


def test_parse_response_returns_blank_scores_on_invalid_json() -> None:
    parsed = _parse_response("definitely not json", ["Q1", "Q2"])

    assert parsed == {
        "Q1": -1,
        "Q2": -1,
        "reasoning": {"Q1": "", "Q2": ""},
        "location": {},
    }


def test_parse_response_captures_valid_locations() -> None:
    raw = """
    {
      "questions": {"Q1": 2, "Q2": 1},
      "reasoning": {"Q1": "ok", "Q2": "partial"},
      "location": {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": 2, "region": "bottom-right"}
      }
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2"])

    assert parsed["location"] == {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": 2, "region": "bottom-right"},
    }


def test_parse_response_drops_invalid_locations() -> None:
    raw = """
    {
      "questions": {"Q1": 2, "Q2": 1, "Q3": 0},
      "reasoning": {"Q1": "ok", "Q2": "partial", "Q3": "blank"},
      "location": {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": "not-a-number", "region": "top-left"},
        "Q3": {"page": 1, "region": "center"}
      }
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2", "Q3"])

    assert parsed["location"] == {"Q1": {"page": 1, "region": "top-left"}}
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run pytest tests/test_grader.py -v`
Expected: `test_parse_response_accepts_valid_json`, `_extracts_json_wrapped`, `_returns_blank_scores`, `_captures_valid_locations`, `_drops_invalid_locations` all FAIL (no `location` key produced yet).

- [ ] **Step 3: Implement the schema + parsing change**

In `ai_grader/grader.py`, replace the `_SYSTEM_PROMPT` constant (lines 14-42) with:

```python
_VALID_REGIONS = (
    "top-left", "top-right",
    "mid-left", "mid-right",
    "bottom-left", "bottom-right",
)

_SYSTEM_PROMPT = """\
You are an experienced teacher marking a student quiz.

Below is the official marking scheme:

{scheme}

INSTRUCTIONS:
- Carefully examine the student's work (images or text provided).
- Award marks based on demonstrated understanding. Use partial credit generously \
where the student shows partial knowledge or correct method with minor errors.
- The submission may be handwritten and OCR-extracted; spelling errors, merged \
words, or garbled characters do NOT count against the student — focus on \
mathematical/conceptual correctness and intent.
- All mark values must be non-negative integers within the range shown for each question.
- For each question, also report roughly where the student's answer to that \
question appears: which page number (1-indexed, matching the order pages were \
given to you) and a coarse region on that page, one of: top-left, top-right, \
mid-left, mid-right, bottom-left, bottom-right. This is a rough pointer for a \
teacher to find the answer quickly — it does not need to be pixel-precise. If \
you cannot tell, omit the location for that question rather than guessing.
- Return ONLY a valid JSON object — no explanation outside the JSON.

Required JSON format (use exactly these question keys):
{{
  "questions": {{
{question_format}
  }},
  "reasoning": {{
{reasoning_format}
  }},
  "location": {{
{location_format}
  }}
}}

If a question is genuinely blank (no attempt at all), award 0.
"""
```

Then update `grade()` (lines 55-103) to build the new `location_format` prompt fragment — replace the two `question_format`/`reasoning_format` lines (71-72) with:

```python
    question_format = "\n".join(f'    "{q}": <integer>,' for q in questions)
    reasoning_format = "\n".join(f'    "{q}": "<brief justification>",' for q in questions)
    location_format = "\n".join(
        f'    "{q}": {{"page": <integer>, "region": "<top-left|top-right|mid-left|mid-right|bottom-left|bottom-right>"}},'
        for q in questions
    )
```

And update the `_SYSTEM_PROMPT.format(...)` call (lines 76-80) to also pass `location_format=location_format`.

Finally, replace `_parse_response()` (lines 106-138) with:

```python
def _parse_response(raw: str, questions: list[str]) -> dict:
    """Extract JSON from model response, with fallback for extra prose."""
    blank = {q: -1 for q in questions}
    blank["reasoning"] = {q: "" for q in questions}
    blank["location"] = {}

    def _valid_location(entry: object) -> dict[str, int | str] | None:
        if not isinstance(entry, dict):
            return None
        page = entry.get("page")
        region = entry.get("region")
        if not isinstance(page, int) or page < 1:
            return None
        if region not in _VALID_REGIONS:
            return None
        return {"page": page, "region": region}

    def _try(text: str) -> dict | None:
        try:
            data = json.loads(text.strip())
            result = {}
            q_data = data.get("questions", data)
            for q in questions:
                val = q_data.get(q)
                if isinstance(val, (int, float)):
                    result[q] = max(0, int(val))
                else:
                    result[q] = -1
            result["reasoning"] = data.get("reasoning", {q: "" for q in questions})

            raw_locations = data.get("location", {})
            locations = {}
            if isinstance(raw_locations, dict):
                for q in questions:
                    valid = _valid_location(raw_locations.get(q))
                    if valid is not None:
                        locations[q] = valid
            result["location"] = locations
            return result
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    parsed = _try(raw)
    if parsed:
        return parsed

    # Try to find a JSON block in the response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        parsed = _try(match.group())
        if parsed:
            return parsed

    return blank
```

Also update the `grade()` docstring (lines 63-66) to mention `location`:

```python
    """
    Grade a single submission. Returns a dict:
      {"Q1": int, "Q2": int, ..., "reasoning": {"Q1": str, ...}, "location": {"Q1": {"page": int, "region": str}, ...}}
    Mark values default to -1 on parse failure. "location" only contains entries
    the model reported validly; questions with no/invalid location are absent.
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grader.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_grader/grader.py tests/test_grader.py
git commit -m "feat: add per-question location to grader schema"
```

---

### Task 2: `annotator.py` — cover page + on-page badges

**Files:**
- Create: `ai_grader/annotator.py`
- Test: `tests/test_annotator.py`

**Interfaces:**
- Consumes: `marks: dict` shaped exactly like `grade()`'s return value from Task 1 (`{q: int, ..., "reasoning": {q: str}, "location": {q: {"page": int, "region": str}}}`).
- Produces: `annotate(submission_path: str, student_name: str, student_id: str, questions: list[str], marks: dict, output_path: str) -> None`. Writes a new PDF to `output_path` (creating parent dirs as needed); never mutates `submission_path`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_annotator.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_annotator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_grader.annotator'`

- [ ] **Step 3: Write the implementation**

Create `ai_grader/annotator.py`:

```python
"""
annotator.py — Write a marked-up copy of a student's submission PDF.

Inserts a cover page (marks + reasoning) and best-effort on-page badges
near each question's reported location. Never mutates the source file.
"""

import os

import fitz

# (x0_frac, y0_frac, x1_frac, y1_frac) — badge rectangle as a fraction of page size
_REGIONS: dict[str, tuple[float, float, float, float]] = {
    "top-left": (0.05, 0.04, 0.35, 0.11),
    "top-right": (0.65, 0.04, 0.95, 0.11),
    "mid-left": (0.05, 0.46, 0.35, 0.53),
    "mid-right": (0.65, 0.46, 0.95, 0.53),
    "bottom-left": (0.05, 0.86, 0.35, 0.93),
    "bottom-right": (0.65, 0.86, 0.95, 0.93),
}

_BADGE_LINE_COLOR = (0.8, 0, 0)
_BADGE_FILL_COLOR = (1, 0.88, 0.88)
_BADGE_TEXT_COLOR = (0.6, 0, 0)


def annotate(
    submission_path: str,
    student_name: str,
    student_id: str,
    questions: list[str],
    marks: dict,
    output_path: str,
) -> None:
    """Write an annotated copy of submission_path to output_path."""
    doc = fitz.open(submission_path)
    locations = marks.get("location", {})

    for question in questions:
        location = locations.get(question)
        if not location:
            continue
        page_num = location.get("page")
        region = location.get("region")
        if region not in _REGIONS:
            continue
        if not isinstance(page_num, int) or not 1 <= page_num <= doc.page_count:
            continue

        page = doc[page_num - 1]
        x0f, y0f, x1f, y1f = _REGIONS[region]
        rect = fitz.Rect(
            x0f * page.rect.width, y0f * page.rect.height,
            x1f * page.rect.width, y1f * page.rect.height,
        )
        score = marks.get(question, -1)
        label = f"{question}: {score}" if score >= 0 else f"{question}: ?"
        page.draw_rect(rect, color=_BADGE_LINE_COLOR, fill=_BADGE_FILL_COLOR, width=1)
        page.insert_textbox(rect, label, color=_BADGE_TEXT_COLOR, fontsize=10, align=1)

    cover = doc.new_page(0, width=595, height=842)
    _draw_cover_page(cover, student_name, student_id, questions, marks)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    doc.close()


def _draw_cover_page(
    page: "fitz.Page",
    student_name: str,
    student_id: str,
    questions: list[str],
    marks: dict,
) -> None:
    reasoning = marks.get("reasoning", {})
    q_vals = [marks.get(q, -1) for q in questions]
    total = sum(q_vals) if all(v >= 0 for v in q_vals) else -1

    lines = [
        "AI Grader — Marking Summary",
        "",
        f"Student: {student_name} ({student_id})",
        "",
        "Marks:",
    ]
    for q in questions:
        lines.append(f"  {q}: {marks.get(q, -1)}")
    lines.append(f"  Total: {total if total >= 0 else 'FLAGGED — needs manual review'}")
    lines.append("")
    lines.append("Reasoning:")
    for q in questions:
        lines.append(f"  {q}: {reasoning.get(q, '')}")

    text = "\n".join(lines)
    rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_annotator.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_grader/annotator.py tests/test_annotator.py
git commit -m "feat: add annotator module for marked-up submission PDFs"
```

---

### Task 3: CLI wiring — `ai-grader mark` writes `annotated/`

**Files:**
- Modify: `ai_grader/cli.py:1-169`
- Test: `tests/test_cli_integration.py`

**Interfaces:**
- Consumes: `annotate()` from Task 2.

- [ ] **Step 1: Read the existing CLI integration test to match its mocking style**

Run: `uv run pytest tests/test_cli_integration.py -v --collect-only` and open the file to see how `grade`/`discover`/`load` are monkeypatched (same module-level function references imported into `cli.py`). Use the same monkeypatch targets (`ai_grader.cli.grade`, etc.) for the new `annotate` call — add `ai_grader.cli.annotate` to the list of monkeypatched symbols.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_cli_integration.py`:

```python
def test_mark_writes_annotated_pdf(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from ai_grader.cli import cli
    from ai_grader.submission_loader import Submission

    scheme_path = tmp_path / "scheme.md"
    scheme_path.write_text("# Scheme\nQ1: 1 mark", encoding="utf-8")

    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    (submissions_dir / "Alice_MATH2083_2026A_quiz_D240051A.pdf").write_bytes(b"%PDF-1.4\n")

    output_dir = tmp_path / "output"
    annotated_calls = []

    monkeypatch.setattr("ai_grader.cli.ollama.Client", lambda host: type(
        "C", (), {"list": lambda self: None}
    )())
    monkeypatch.setattr("ai_grader.cli.load_scheme", lambda path: "scheme text")
    monkeypatch.setattr(
        "ai_grader.cli.discover",
        lambda folder: [Submission(student_id="D240051A", name="Alice", path=str(submissions_dir / "Alice_MATH2083_2026A_quiz_D240051A.pdf"))],
    )
    monkeypatch.setattr("ai_grader.cli.load", lambda sub, dpi=150: sub)
    monkeypatch.setattr(
        "ai_grader.cli.grade",
        lambda *a, **k: {"Q1": 1, "reasoning": {"Q1": "ok"}, "location": {}},
    )

    def fake_annotate(submission_path, name, student_id, questions, marks, output_path):
        annotated_calls.append((student_id, output_path))
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr("ai_grader.cli.annotate", fake_annotate)

    result = CliRunner().invoke(
        cli,
        [
            "mark",
            "--scheme", str(scheme_path),
            "--submissions", str(submissions_dir),
            "--model", "fake-model",
            "--output", str(output_dir),
            "--questions", "Q1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(annotated_calls) == 1
    assert annotated_calls[0][0] == "D240051A"
    assert (output_dir / "annotated").is_dir()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_integration.py::test_mark_writes_annotated_pdf -v`
Expected: FAIL — `AttributeError: module 'ai_grader.cli' has no attribute 'annotate'`

- [ ] **Step 4: Implement the wiring**

In `ai_grader/cli.py`, add the import (after line 20 `from .grader import grade`):

```python
from .annotator import annotate
```

In the `mark()` command's grading loop (lines 130-147), replace the `try` block that calls `grade()` with:

```python
        try:
            marks = grade(sub, scheme_text, model, ollama_host, question_list)
            q_str = " ".join(f"{q}={marks.get(q, -1)}" for q in question_list)
            q_vals = [marks.get(q, -1) for q in question_list]
            total = sum(q_vals) if all(v >= 0 for v in q_vals) else "ERR"
            click.echo(f" {q_str} → {total}/{len(question_list)*5}  {mode_tag}")
            result = {
                "student_id": sub.student_id,
                "name": sub.name,
                "reasoning": marks.get("reasoning", {}),
            }
            for q in question_list:
                result[q] = marks.get(q, -1)
            results.append(result)

            annotated_name = _safe_filename(f"{sub.name}_{sub.student_id}") + ".pdf"
            annotated_path = os.path.join(output, "annotated", annotated_name)
            try:
                annotate(sub.path, sub.name, sub.student_id, question_list, marks, annotated_path)
            except Exception as e:
                click.echo(f"    (annotation skipped: {e})")
        except Exception as e:
            click.echo(f" FAILED (AI error: {e})  {mode_tag}")
            results.append(_error_result(sub, question_list, str(e)))
```

Add the helper function near `_error_result` (after line 169):

```python
def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name).strip("_")
```

Add `import re` to the top-level imports (after line 7 `import sys`):

```python
import re
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_integration.py::test_mark_writes_annotated_pdf -v`
Expected: PASS.

- [ ] **Step 6: Run the full CLI test file to check for regressions**

Run: `uv run pytest tests/test_cli_integration.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add ai_grader/cli.py tests/test_cli_integration.py
git commit -m "feat: write annotated PDFs from ai-grader mark CLI"
```

---

### Task 4: GUI — replace server-path submissions field with real file upload

**Files:**
- Modify: `ai_grader/gui.py:111-267` (remove `/api/browse-folder`, rewrite `/api/jobs`)
- Modify: `ai_grader/templates/index.html:587-601`, `1056-1075` (remove browse UI/JS), `1036-1043` (form submit unchanged — `FormData` already picks up file inputs automatically)
- Test: `tests/test_gui.py`

**Interfaces:**
- Produces: `/api/jobs` now expects one or more files under form field name `submissions` (multipart), not `submissions_path`. Saves them into `<job_root>/uploads/submissions/`. `_run_job` discovers submissions from that folder — its own signature is unchanged, only the folder it's pointed at changes.

- [ ] **Step 1: Update the existing GUI test to use file uploads**

In `tests/test_gui.py`, replace the request body in `test_job_stream_and_download_work_with_fake_dependencies` (lines 130-141):

```python
    response = client.post(
        "/api/jobs",
        data={
            "scheme": (io.BytesIO(b"# Scheme"), "scheme.md"),
            "submissions": (io.BytesIO(b"%PDF-1.4\n"), "Alice_MATH2083_2026A_quiz_D240051A.pdf"),
            "model": "fake-model",
            "questions": "Q1",
            "dpi": "150",
        },
        headers={"X-CSRF-Token": _csrf_token(client)},
        content_type="multipart/form-data",
    )
```

Also delete the now-unused `submissions_dir = tmp_path / "submissions"` / `submissions_dir.mkdir()` lines (125-126) — the uploaded file replaces the pre-existing folder, and `fake_discover` (line 94) ignores its `folder` argument anyway so it needs no change.

Replace `test_api_jobs_rejects_missing_csrf_token` (lines 220-232ish) similarly — swap its `"submissions_path": str(submissions_dir)` for a `"submissions": (io.BytesIO(b"%PDF-1.4\n"), "x.pdf")` entry, and drop that test's now-unused submissions dir creation too.

- [ ] **Step 2: Add a test for rejecting empty submissions and a test for multi-file save**

Add to `tests/test_gui.py`:

```python
def test_api_jobs_rejects_missing_submissions() -> None:
    app = create_app(default_questions=["Q1"])
    client = app.test_client()
    client.get("/")

    response = client.post(
        "/api/jobs",
        data={
            "scheme": (io.BytesIO(b"# Scheme"), "scheme.md"),
            "model": "fake-model",
            "questions": "Q1",
            "dpi": "150",
        },
        headers={"X-CSRF-Token": _csrf_token(client)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
```

- [ ] **Step 3: Run tests to verify failures**

Run: `uv run pytest tests/test_gui.py -v`
Expected: the modified tests FAIL (backend still expects `submissions_path`), the new test FAILS or errors.

- [ ] **Step 4: Implement the backend change**

In `ai_grader/gui.py`, delete the entire `/api/browse-folder` route (lines 111-126).

Replace the `create_job()` function body (lines 212-267) with:

```python
    @app.post("/api/jobs")
    def create_job() -> Response:
        scheme_file = request.files.get("scheme")
        submission_files = request.files.getlist("submissions")
        model = (request.form.get("model") or "").strip()
        questions = _normalize_questions(
            request.form.get("questions") or ",".join(app.config["DEFAULT_QUESTIONS"])
        )
        dpi_value = request.form.get("dpi") or str(app.config["DEFAULT_DPI"])

        if not scheme_file or not scheme_file.filename:
            return jsonify({"ok": False, "message": "Please choose a marking scheme file."}), 400
        submission_files = [f for f in submission_files if f and f.filename]
        if not submission_files:
            return jsonify({"ok": False, "message": "Please choose one or more submission files."}), 400
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

        api_key = (request.form.get("ollama_api_key") or "").strip() or None

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

        submissions_dir = uploads_dir / "submissions"
        submissions_dir.mkdir(parents=True, exist_ok=True)
        for submission_file in submission_files:
            saved_name = secure_filename(submission_file.filename)
            if not saved_name:
                continue
            submission_file.save(submissions_dir / saved_name)

        thread = app.config["THREAD_FACTORY"](
            target=_run_job,
            args=(app, job_id, str(scheme_path), str(submissions_dir), model, questions, dpi, str(output_dir), api_key),
            daemon=True,
        )
        thread.start()

        return jsonify({"ok": True, "job_id": job_id})
```

Remove the now-unused `import tkinter` (there wasn't a top-level one — it was a local import inside the deleted route, so nothing else to clean up there).

- [ ] **Step 5: Update the template — remove folder-path/browse UI**

In `ai_grader/templates/index.html`, replace the "Submissions folder" field block (lines 590-601):

```html
          <div class="field">
            <label for="submissions_path">Submissions folder</label>
            <div class="browse-row">
              <input
                id="submissions_path"
                name="submissions_path"
                type="text"
                placeholder="C:\Users\Teacher\Documents\Submissions"
                required
              >
              <button id="browse-button" class="browse-btn" type="button">Browse…</button>
            </div>
          </div>
```

with:

```html
          <div class="field">
            <label for="submissions">Student submissions</label>
            <input id="submissions" name="submissions" type="file" multiple required accept=".pdf,.docx,.txt,.md">
          </div>
```

Remove the `submissionsPath` and `browseButton` entries from the `elements` object (lines 688-690) — delete those two lines.

Remove the entire `elements.browseButton.addEventListener(...)` block (lines 1056 through its closing `});`, which calls `/api/browse-folder`) — search for it and delete the whole handler.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_gui.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add ai_grader/gui.py ai_grader/templates/index.html tests/test_gui.py
git commit -m "feat: replace server-path submissions field with real file upload"
```

---

### Task 5: GUI wiring — annotate submissions and offer a zip download

**Files:**
- Modify: `ai_grader/gui.py:353-469` (`_run_job`)
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `annotate()` from Task 2.
- Produces: when at least one submission is successfully annotated, `job.files` gains an `"annotated.zip"` entry, and the `"done"` SSE event's `files` list includes it — the existing generic frontend download-link rendering (`index.html:980-985`) picks it up with no further template change.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gui.py`, reusing the fake dependencies pattern from `test_job_stream_and_download_work_with_fake_dependencies`:

```python
def test_job_produces_annotated_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        def __init__(self, host: str, headers: dict | None = None) -> None:
            self.host = host

        def list(self) -> dict:
            return {"models": [{"model": "fake-model"}]}

    def fake_load_scheme(path: str) -> str:
        return "scheme"

    def fake_discover(folder: str) -> list[Submission]:
        submission_path = tmp_path / "alice.pdf"
        submission_path.write_bytes(b"%PDF-1.4\n")
        return [Submission(student_id="D240051A", name="Alice", path=str(submission_path))]

    def fake_load(submission: Submission, dpi: int = 150) -> Submission:
        submission.mode = "text"
        submission.text = "Q1: APPLE"
        return submission

    def fake_grade(*args, **kwargs) -> dict:
        return {"Q1": 1, "reasoning": {"Q1": "ok"}, "location": {}}

    def fake_write_results(results, output_dir, questions, formats) -> list[str]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        xlsx_path = output / "marks.xlsx"
        xlsx_path.write_text("placeholder", encoding="utf-8")
        return [str(xlsx_path)]

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

    client = app.test_client()
    client.get("/")

    response = client.post(
        "/api/jobs",
        data={
            "scheme": (io.BytesIO(b"# Scheme"), "scheme.md"),
            "submissions": (io.BytesIO(b"%PDF-1.4\n"), "Alice.pdf"),
            "model": "fake-model",
            "questions": "Q1",
            "dpi": "150",
        },
        headers={"X-CSRF-Token": _csrf_token(client)},
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    stream = client.get(f"/api/jobs/{payload['job_id']}/stream")
    stream_text = stream.get_data(as_text=True)
    assert '"name": "annotated.zip"' in stream_text

    download = client.get(f"/download/{payload['job_id']}/annotated.zip")
    assert download.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gui.py::test_job_produces_annotated_zip -v`
Expected: FAIL — no `annotated.zip` in the done event's files.

- [ ] **Step 3: Implement the wiring**

In `ai_grader/gui.py`, add the import (after line 33 `from .submission_loader import Submission, discover, load`):

```python
from .annotator import annotate
```

In `_run_job` (lines 353-469), inside the per-submission loop's `try` block (lines 403-419), add the annotate call right after `result` is built:

```python
            try:
                app.config["LOAD_SUBMISSION"](submission, dpi=dpi)
                marks = app.config["GRADE"](
                    submission,
                    scheme_text,
                    model,
                    app.config["DEFAULT_OLLAMA_HOST"],
                    questions,
                    api_key,
                )
                result = {
                    "student_id": submission.student_id,
                    "name": submission.name,
                    "reasoning": marks.get("reasoning", {}),
                }
                for question in questions:
                    result[question] = marks.get(question, -1)

                annotated_name = _safe_filename(f"{submission.name}_{submission.student_id}") + ".pdf"
                annotated_path = Path(output_dir) / "annotated" / annotated_name
                try:
                    annotate(submission.path, submission.name, submission.student_id, questions, marks, str(annotated_path))
                except Exception:
                    pass  # annotation is best-effort; grading result is unaffected
            except Exception as exc:
                result = _error_result(submission, questions, str(exc))
```

(This replaces the existing lines 403-421 — the only change is the new `annotated_name`/`annotated_path`/inner-`try` block inserted before the outer `except`.)

After the loop, replace lines 441-464 (the `written = ...` through the `_emit(job, {"type": "done", ...})` block) with:

```python
        written = app.config["WRITE_RESULTS"](
            results,
            output_dir,
            questions,
            app.config["OUTPUT_FORMATS"],
        )
        job.files = {Path(path).name: path for path in written}

        annotated_dir = Path(output_dir) / "annotated"
        if annotated_dir.is_dir() and any(annotated_dir.iterdir()):
            zip_base = str(Path(output_dir) / "annotated")
            zip_path = shutil.make_archive(zip_base, "zip", root_dir=str(annotated_dir))
            job.files[Path(zip_path).name] = zip_path

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
```

Add the same `_safe_filename` helper used in Task 3, near `_error_result` (after line 554):

```python
def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name).strip("_")
```

Add `import re` if not already present (it is not currently imported in `gui.py` — add it alongside the existing `import re` check; `gui.py` line 11 already has `import re` — reuse it, no new import needed).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gui.py -v`
Expected: all PASS, including `test_job_produces_annotated_zip`.

- [ ] **Step 5: Commit**

```bash
git add ai_grader/gui.py tests/test_gui.py
git commit -m "feat: write annotated PDFs and zip them for GUI download"
```

---

### Task 6: GUI — manual "clear now" cleanup action

**Files:**
- Modify: `ai_grader/gui.py:309-328` (add route)
- Modify: `ai_grader/templates/index.html` (add button + handler)
- Test: `tests/test_gui.py`

**Interfaces:**
- Produces: `POST /api/jobs/<job_id>/clear` → `{"ok": true}`, immediately runs the *existing* `_cleanup_job(app, job_id)` (no new deletion logic — this just triggers what the timer would do anyway, sooner).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gui.py`:

```python
def test_clear_job_endpoint_removes_job_immediately(tmp_path: Path) -> None:
    app = create_app(default_questions=["Q1"])
    client = app.test_client()
    client.get("/")

    from ai_grader.gui import JobState

    job_id = "test-job-clear"
    job_root = tmp_path / "job-root"
    job_root.mkdir()
    (job_root / "marker.txt").write_text("x", encoding="utf-8")
    job = JobState(job_root=str(job_root))
    with app.extensions["jobs_lock"]:
        app.extensions["jobs"][job_id] = job

    response = client.post(
        f"/api/jobs/{job_id}/clear",
        headers={"X-CSRF-Token": _csrf_token(client)},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert not job_root.exists()
    with app.extensions["jobs_lock"]:
        assert job_id not in app.extensions["jobs"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gui.py::test_clear_job_endpoint_removes_job_immediately -v`
Expected: FAIL — 404, no such route.

- [ ] **Step 3: Implement the route**

In `ai_grader/gui.py`, add a new route right after the `download` route (after line 327's `return response`, before `return app` on line 328):

```python
    @app.post("/api/jobs/<job_id>/clear")
    def clear_job(job_id: str) -> Response:
        with app.extensions["jobs_lock"]:
            job_exists = job_id in app.extensions["jobs"]
        if job_exists:
            _cleanup_job(app, job_id)
        return jsonify({"ok": True})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gui.py::test_clear_job_endpoint_removes_job_immediately -v`
Expected: PASS.

- [ ] **Step 5: Add the frontend button**

In `ai_grader/templates/index.html`, inside the "done" event handler (lines 971-989), after the download links loop (`for (const file of event.files) { ... }`, ends at line 985) and before `activeStream.close();` (line 986), add:

```javascript
          const clearButton = document.createElement("button");
          clearButton.type = "button";
          clearButton.className = "ghost-button";
          clearButton.textContent = "Clear submissions from server now";
          clearButton.addEventListener("click", async () => {
            if (!confirm("Have you downloaded everything you need? This clears the uploaded files from the server now.")) return;
            clearButton.disabled = true;
            clearButton.textContent = "Clearing…";
            try {
              await fetch(`/api/jobs/${jobId}/clear`, {
                method: "POST",
                headers: { "X-CSRF-Token": csrfToken },
              });
              clearButton.textContent = "Cleared.";
            } catch (error) {
              clearButton.textContent = "Clear failed — try again.";
              clearButton.disabled = false;
            }
          });
          elements.downloads.append(clearButton);
```

(This runs inside the same `onmessage` handler as the `"done"` branch, so `jobId` is in scope from `openStream(jobId, ...)`'s parameter — no new variable needed.)

- [ ] **Step 6: Run full test suite for regressions**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add ai_grader/gui.py ai_grader/templates/index.html tests/test_gui.py
git commit -m "feat: add manual clear-now cleanup action to GUI"
```

---

### Task 7: Verification pass + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (Architecture table + Key Behaviours section)

- [ ] **Step 1: Run the full verification checklist from CLAUDE.md**

```bash
python3 -m py_compile ai_grader/*.py
uv run pytest tests/ -q
```

Expected: no syntax errors, all tests green.

- [ ] **Step 2: Manual smoke test**

```bash
ollama serve &
uv run ai-grader gui --no-browser
```

Open the printed URL, upload a real scheme + a couple of test PDFs, run a grading job, confirm:
- `annotated.zip` appears in the download list
- unzip it and open one PDF — cover page is legible, badges appear near the right pages (or absent, never crashing)
- "Clear submissions from server now" button works and the job's temp folder is gone (check `ls $TMPDIR/ai-grader/` before/after, or on Linux `ls /tmp/ai-grader/`)

- [ ] **Step 3: Update `CLAUDE.md`**

In the `Architecture` table, add a row after `exporter.py`:

```markdown
| `annotator.py` | Writes a marked-up copy of each submission PDF: cover page (marks + reasoning) + best-effort on-page badges near each question's reported location |
```

In `Key Behaviours`, add:

```markdown
- **Annotated PDFs**: `<output>/annotated/<Name>_<StudentID>.pdf` per submission (cover page always present; on-page badges are best-effort and silently skipped when the model didn't report a valid location). GUI additionally zips these into `annotated.zip` for one-click download.
- **Submissions upload**: GUI now takes real file uploads (`<input type="file" multiple>`), not a server-side folder path — required for remote/Tailscale use where the browser and the ai-grader process are on different machines.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document annotator module and upload change in CLAUDE.md"
```

---

## Self-Review Notes

- **Spec coverage:** cover page (Task 2) ✓, on-page badges via `location` schema (Tasks 1-2) ✓, `annotated/` folder + zip delivery (Tasks 3, 5) ✓, manual clear-now button reusing existing cleanup (Task 6) ✓. The upload-path fix (Task 4) was a scope addition the user explicitly approved after the spec was written, since the spec's assumption (browser already uploads files) turned out to be false in the current codebase — documented here rather than silently folded in.
- **Type/name consistency checked:** `annotate(submission_path, student_name, student_id, questions, marks, output_path)` signature is identical across Task 2 (definition), Task 3 (CLI call), and Task 5 (GUI call). `_safe_filename` is duplicated in `cli.py` and `gui.py` rather than shared — each module is small and self-contained per existing project structure (no shared `utils.py` exists yet); flagging this as an acceptable duplication given both call sites are ~1 line each, not a candidate for premature abstraction.
