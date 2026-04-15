# Copilot Instructions for ai-grader

## Setup

```bash
pip install -r requirements.txt
pip install -e .
ollama pull gemma4:12b   # or any vision-capable model
ollama serve             # run in a separate terminal before grading
```

## Build and Test

There is no automated test suite. Validation is manual:

```bash
# Test the CLI end-to-end with sample data
ai-grader mark \
  --scheme examples/sample_scheme.md \
  --submissions ./examples/ \
  --model gemma4:12b \
  --questions "Q1,Q2,Q3,Q4"

# Verify output was written to ./output/
```

## Architecture

**Single CLI entry point** (`ai_grader/cli.py` → `ai-grader mark`) orchestrates a linear pipeline:

1. **`scheme_parser.py`** — Loads marking scheme from `.md`/`.txt` (raw read) or `.pdf`/`.docx`/`.pptx` (via MarkItDown) → returns plain text
2. **`submission_loader.py`** — Discovers files in submission folder, parses student ID/name from filename regex pattern, auto-detects grading mode:
   - PDF with <50 chars extracted text → **vision mode** (PyMuPDF renders pages as base64 PNG)
   - PDF with extractable text / `.docx` / `.txt` / `.md` → **text mode** (MarkItDown or plain read)
3. **`grader.py`** — Sends scheme + submission to Ollama; vision submissions attach images, text submissions embed text in prompt; parses strict JSON response with regex fallback; returns `{Q1: int, Q2: int, ..., reasoning: {Q1: str, ...}}`; failed parse returns `-1` for all marks
4. **`exporter.py`** — Writes `marks.xlsx` (Marks sheet + Reasoning sheet, red highlight on `-1`) and `marks.csv` to output dir

**Data flow**: CLI discovers files → loads each submission (auto mode detection) → grades against scheme → exports results

## Key Conventions

### Filename Parsing
Pattern: `Name_CourseCode_Year_AssessmentName_StudentID.pdf`  
Example: `John_Doe_MATH101_2026A_quiz_D240051A.pdf`

- Regex extracts student ID from final field and name from initial fields
- Underscores in names are converted to spaces
- If pattern doesn't match, full filename stem is used as name
- Double extensions (`.pdf.pdf`) are explicitly handled

### Error Handling
- Failed AI parses: `grader.py` returns `-1` for all marks, with error message in first question's reasoning
- Failed marks in results: marked red in Excel, listed as warnings in CLI output
- `total` column: set to `-1` if any question in the row is `-1` (avoids false partial totals)

### Vision vs Text Mode
- **Vision mode**: PyMuPDF renders pages at configurable DPI (default 150), encodes as base64 PNG, sent to Ollama with `image/png` media type
- **Text mode**: Content extracted via MarkItDown (handles `.docx`, `.pptx`, scanned PDFs with OCR) or raw read (`.txt`, `.md`), sent as text in prompt
- Mode detection in `submission_loader.py:load()` uses `_TEXT_THRESHOLD = 50` chars as the cutoff

### CLI and Ollama Integration
- `ollama.Client(host=...)` connects to local Ollama instance
- Default host: `http://localhost:11434` (overridable via `--ollama-host` or `OLLAMA_HOST` env var)
- CLI validates Ollama is reachable before starting pipeline
- Questions are normalized to uppercase (e.g., `q1` → `Q1`)
- Default questions: `Q1,Q2,Q3,Q4` (configurable via `--questions`)

### Output Structure
- **marks.xlsx**: Marks sheet (student_id, name, Q1, Q2, ... Qn, total) + Reasoning sheet
- **marks.csv**: Same data as Marks sheet for spreadsheet import
- Both formats written to output dir (default `./output`), configurable via `--output`
- Export format(s) configurable via `--format` (e.g., `excel,csv` or just `csv`)

## MCP Servers (Optional)

MCP (Model Context Protocol) servers are optional tools for development and testing. They are **not required for the main CLI** but can enhance your workflow with additional capabilities.

### Overview

Three MCP servers are available in `mcp_servers/`:

1. **Ollama MCP Server** — Interact with Ollama directly; test grading logic, experiment with models, and engineer prompts without running the full pipeline
2. **Playwright MCP Server** — Browser automation for testing web-based UIs (currently for future web dashboard features)

**When to use**: Test a new marking scheme against different models before deploying, debug AI prompt engineering, or experiment with model responses interactively.

### Ollama MCP Server

**Purpose**: Direct interaction with Ollama for testing, model management, and prompt engineering.

**Location**: `mcp_servers/ollama_server.py`

**Startup** (from repo root):
```bash
python -m mcp run mcp_servers/ollama_server.py
```

**Available tools**:
- `list_models` — List all available models in Ollama
- `generate_text` — Generate text with a specific model
- `chat` — Chat interface for multi-turn conversations
- `pull_model` — Download a model from Ollama registry
- `check_health` — Verify Ollama connection and server status

**Use case example**: Test a new marking scheme against different models (e.g., `gemma4`, `llama2`) before using it in production. Use the `chat` tool to interactively refine your scheme based on model responses.

### Playwright MCP Server

**Purpose**: Browser automation and web testing (prepared for future web-based grading dashboard).

**Location**: `mcp_servers/playwright/`

**Startup** (from `mcp_servers/playwright/` directory):
```bash
npm run build && npm start
```

**Available tools**:
- `navigate` — Go to a URL
- `click` — Click an element
- `fill_form` — Fill form fields
- `screenshot` — Capture page screenshot
- `get_text` — Extract text from page
- `evaluate` — Execute JavaScript in page context

**Use case example**: Test a web dashboard for grading management (future feature). Automate form submission, screenshot results, or validate UI state.

### Starting MCP Servers

**Helper script**:
- Unix/Linux/macOS: `mcp_servers/start-mcp-servers.sh`
- Windows: `mcp_servers/start-mcp-servers.ps1`

**Environment variables**:
- `OLLAMA_HOST` — Override default Ollama instance (default: `http://localhost:11434`)

**Troubleshooting**:
- **Ollama MCP**: Ensure `ollama serve` is running before starting the Ollama MCP server
- **Playwright MCP**: Requires Node.js 18 or later

### Usage in Claude

Once an MCP server is running, you can interact with it in Claude Copilot:

- **Test a marking scheme**: Use the Ollama MCP `chat` tool to submit your scheme and a sample submission, then refine based on AI feedback
- **Model comparison**: Use `generate_text` with different models to compare outputs before deciding which to deploy
- **Debug prompt engineering**: Iterate on your grading prompt in real time with the `chat` tool

These tools integrate seamlessly with the main grading pipeline but are independent of it.

## Module Imports

| Module | Purpose |
|--------|---------|
| `ollama` | Client for Ollama API (`Client(host=...)`, `client.generate()`, `client.list()`) |
| `pymupdf` | PDF parsing and rendering (`fitz.open()`) |
| `openpyxl` | Excel workbook creation and formatting |
| `click` | CLI command and option decorators |
| `markitdown` | Format conversion for `.docx`, `.pptx`, etc. |
| `dataclasses`, `typing` | Data structures for Submission and type hints |

## Submission Class

```python
@dataclass
class Submission:
    student_id: str
    name: str
    path: str
    mode: Literal["vision", "text"] = "vision"
    images: list[str] = field(default_factory=list)   # base64 PNGs (vision mode)
    text: str = ""                                      # extracted text (text mode)
```

Populated by `submission_loader.load(submission, dpi=150)` — populates either `images` (vision) or `text` (text mode).

## Grading Prompt Structure

- **System prompt** (`_SYSTEM_PROMPT` in `grader.py`): Instructs AI to act as a teacher, follow the marking scheme, return valid JSON with questions + reasoning
- **User prompt** (vision): "Here is the student's submission (scanned pages). Mark each question and return the JSON."
- **User prompt** (text): "Here is the student's submission: {extracted_text}. Mark each question and return the JSON."
- **Vision mode**: Message includes `image/png` base64 content blocks for each page
- **Expected JSON response**:
  ```json
  {
    "questions": {"Q1": 4, "Q2": 5, "Q3": 3, "Q4": 5},
    "reasoning": {"Q1": "...", "Q2": "...", ...}
  }
  ```

## Windows-Specific Notes

UTF-8 output is forced on Windows in `cli.py` to prevent encoding errors with special characters.
