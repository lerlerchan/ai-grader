# Windows 11 Desktop GUI (Flask Local Web App) — Plan

## Context

The CLI is too technical for non-tech teachers.  
The goal is a **Taguette-style local web app**:

*   Teacher runs **one command** (or double‑clicks)
*   A **Flask server starts locally**
*   Browser opens automatically
*   Teacher uses a **clean web UI**
*   **Cross-platform** (browser-based, no native GUI)
*   Existing **CLI remains unchanged**

***

## Locked Design Decisions

*   **Framework**: Flask local server, browser as UI
*   **Layout**:
    *   Single main form
    *   3 primary fields
    *   1 large **Mark** button
    *   **Advanced** toggle for optional questions
*   **Scheme input**:
    *   `<input type="file">` upload
    *   Saved to a temporary directory
*   **Submissions input**:
    *   Folder path text input
    *   Teacher pastes path from Windows Explorer
*   **Model selection**:
    *   Dropdown populated live from `ollama.list()`
*   **Progress updates**:
    *   Server‑Sent Events (SSE)
    *   No WebSockets
*   **Results**:
    *   Summary table in browser
    *   Download links for `xlsx` and `csv`

***

## File Structure Changes

### New Files

```text
ai_grader/
├── gui.py
└── templates/
    └── index.html
```

| File                             | Purpose                                              |
| -------------------------------- | ---------------------------------------------------- |
| `ai_grader/gui.py`               | Flask app: routes, SSE grading stream, file handling |
| `ai_grader/templates/index.html` | Single‑page UI: form, progress, results              |

***

### Modified Files

| File               | Change                  |
| ------------------ | ----------------------- |
| `ai_grader/cli.py` | Add `gui` Click command |
| `pyproject.toml`   | Add `flask` dependency  |

***

## Implementation Steps

***

### 1. Add Flask Dependency

**`pyproject.toml`**

Append `flask` to the dependencies list.

***

### 2. Create `ai_grader/gui.py`

#### Flask Routes

| Method | Route              | Description                  |
| ------ | ------------------ | ---------------------------- |
| GET    | `/`                | Serve `index.html`           |
| GET    | `/api/models`      | Return list of Ollama models |
| POST   | `/api/mark`        | SSE grading stream           |
| GET    | `/download/<name>` | Serve result files           |

***

#### `/api/models`

*   Calls `ollama.Client().list()`
*   Returns:
    *   JSON list of model names
    *   `[]` on error

***

#### `/api/mark` — SSE Stream

**Request**

*   Multipart form:
    *   Marking scheme file
    *   Submissions folder path
    *   Model
    *   Settings (questions, etc.)

**Processing Flow**

1.  Save uploaded scheme to `tempfile.mkdtemp()`
2.  `load_scheme(tmp_scheme_path)` → `scheme_text`
3.  `discover(submissions_folder)` → submission list
4.  For each submission:
    *   `load(sub)`
    *   `grade(sub, ...)`
    *   Stream SSE progress event
5.  After completion:
    *   `write_results(...)` → `./output/`
    *   Stream final SSE event with download URLs

***

#### SSE Event Formats

```json
{
  "type": "progress",
  "student_id": "D240051A",
  "name": "John",
  "marks": {"Q1": 4, "Q2": 5},
  "total": 9,
  "mode": "text"
}
```

```json
{
  "type": "done",
  "files": ["output/marks.xlsx", "output/marks.csv"],
  "failed": 0
}
```

```json
{
  "type": "error",
  "message": "..."
}
```

***

#### Launch Helper

```python
def run(host, port, open_browser):
    if open_browser:
        threading.Timer(
            1.0,
            lambda: webbrowser.open(f"http://{host}:{port}")
        ).start()
    app.run(host=host, port=port)
```

***

### 3. Create `ai_grader/templates/index.html`

Single-page HTML (no frameworks, **vanilla JS only**).

***

#### UI Sections

##### Form (Initial View)

*   **Marking Scheme**
    *   File upload
*   **Submissions Folder**
    *   Text input (paste Windows path)
*   **Model**
    *   Dropdown populated from `/api/models`

```text
▼ Advanced
  Questions: [Q1, Q2, Q3, Q4]
```

*   **▶ Mark Submissions**
    *   Large green primary button

***

##### Progress View

*   Header: `Grading X of Y...`
*   Live-updating table:
    *   Student ID
    *   Name
    *   Question marks
    *   Total
    *   Mode tag
*   Failed rows highlighted in red

***

##### Results View

*   Summary:
    *   `X graded, Y failed`
*   Download links:
    *   `marks.xlsx`
    *   `marks.csv`
*   **Grade Another Batch**
    *   Resets UI state to form

***

#### JavaScript Logic

*   On page load:
    *   `fetch('/api/models')`
    *   Populate model dropdown
*   On form submit:
    *   Open `EventSource` to `/api/mark`
    *   Handle SSE messages:
        *   `progress`
        *   `done`
        *   `error`
*   No external JS libraries

***

### 4. Add `gui` Command to CLI

**`ai_grader/cli.py`**

```python
@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=5000, show_default=True)
@click.option("--no-browser", is_flag=True, help="Don't auto-open browser")
def gui(host, port, no_browser):
    """Launch the web UI (opens in your browser)."""
    from .gui import run
    click.echo(f"Starting AI Grader UI at http://{host}:{port}")
    run(host=host, port=port, open_browser=not no_browser)
```

*   Entry point unchanged:
    *   `ai-grader = "ai_grader.cli:main"`

***

## Reused Modules (No Changes)

*   `scheme_parser.py`
    *   `load_scheme(path)`
*   `submission_loader.py`
    *   `discover(folder)`
    *   `load(sub)`
*   `grader.py`
    *   `grade(sub, scheme_text, model, ollama_host, questions)`
*   `exporter.py`
    *   `write_results(results, output_dir, questions, formats)`

***

## Verification Checklist

```bash
# Install Flask
pip install flask

# Launch GUI
ai-grader gui
```

*   Browser opens at `http://localhost:5000`
*   Test flow:
    1.  Upload `.md` or `.pdf` marking scheme
    2.  Paste submission folder path
    3.  Select Ollama model
    4.  Click **Mark Submissions**
    5.  Observe live progress table
    6.  Download `marks.xlsx`
    7.  Verify output matches CLI results

```bash
# CLI remains functional
ai-grader mark \
  --scheme examples/sample_scheme.md \
  --submissions ./test/ \
  --model gemma4:12b
```

