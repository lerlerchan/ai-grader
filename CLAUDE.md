# CLAUDE.md — ai-grader

Guidance for Claude Code when working in this repository.

---

## Quick Start

```bash
# Install (system Python is externally managed — always use uv)
uv tool install -e ".[test]"

# Or dev-install into a venv
uv venv && uv pip install -e ".[test]"

# Run Ollama first
ollama serve

# CLI
ai-grader mark \
  --scheme examples/sample_scheme.md \
  --submissions ./submissions/ \
  --model gemma4:12b \
  --questions "Q1,Q2,Q3,Q4"

# Web UI
ai-grader gui
```

Override Ollama host: `OLLAMA_HOST=http://remote:11434` or `--ollama-host`.

---

## Architecture

Single linear pipeline, all under `ai_grader/`:

| Module | Role |
|--------|------|
| `cli.py` | Click entry point — `ai-grader mark` and `ai-grader gui` |
| `scheme_parser.py` | Loads scheme: raw for `.md`/`.txt`; MarkItDown for `.pdf`/`.docx`/`.pptx` |
| `submission_loader.py` | Discovers files, parses `Name_Course_Year_Assessment_StudentID` filename, auto-detects vision vs text mode |
| `grader.py` | Sends scheme + submission to Ollama; returns `{Q1: int, ..., reasoning: {...}}`; failed parse → `-1` |
| `exporter.py` | Writes `marks.xlsx` (Marks + Reasoning sheets, red `-1` rows) and `marks.csv` |
| `gui.py` | Flask local web app with SSE live progress, file upload, folder browse |

**Vision mode**: PDF with <50 chars extracted text → PyMuPDF renders pages as base64 PNG → sent as images.
**Text mode**: PDF with text / `.docx` / `.txt` / `.md` → MarkItDown or plain read → embedded in prompt.

### Key invariants
- Score clamping: `max(0, val)` in `_parse_response` — never return negative marks
- Dynamic question labels: prompt JSON template built from actual `questions` list, not hardcoded Q1-Q4
- `total` = `-1` if any question is `-1` (avoids false partial totals)
- Double extension `.pdf.pdf` handled explicitly throughout

---

## Harness Engineering

This section defines how Claude Code should behave in this project.
Follow these conventions proactively — do not wait to be asked.

### Agents to invoke automatically

| Trigger | Agent |
|---------|-------|
| Any code written or modified | `code-reviewer` |
| Build/type error | `build-error-resolver` |
| Bug report or unexpected output | `bug-analyzer` |
| New module or structural change | `architect` |
| New feature with testable behaviour | `tdd-guide` |

### Hooks (project-level)

Create `.claude/settings.json` if it does not exist. Recommended project hooks:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "bash /home/lerler/github/ai-grader/.claude/hooks/guard-destructive.sh",
          "timeout": 5
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{
          "type": "command",
          "command": "bash /home/lerler/github/ai-grader/.claude/hooks/lint-on-save.sh",
          "timeout": 15
        }]
      }
    ]
  }
}
```

`guard-destructive.sh` — block `rm -rf`, `DROP TABLE`, `git reset --hard` without confirmation.
`lint-on-save.sh` — run `python3 -m py_compile` on the saved file; surface syntax errors immediately.

### Skills to activate

| User intent | Skill |
|-------------|-------|
| UI or frontend change | `frontend-design` |
| Commit + push | `git-push` |
| Code quality sweep | `code-review-excellence` |
| Bug investigation | `bug-detective` |

### Memory

Project memory lives at:
```
~/.claude/projects/-home-lerler-github-ai-grader/memory/
```

Update `MEMORY.md` after each session with:
- Version just released
- Any non-obvious constraint discovered (e.g. `uv` required, no `gh` CLI)
- Decisions made and why

Do **not** store in memory: file paths, code patterns, git history — read those live.

---

## Development Conventions

### Always use `uv`
System Python is externally managed (Debian). Never `pip install` bare.

```bash
uv pip install -e ".[test]"   # dev install
uv build                       # build wheel + sdist
uv run pytest                  # run tests
```

### GitHub API — no `gh` CLI
`gh` is not installed. Use `curl` + GitHub PAT for all GitHub API calls.
PAT stored at session time by user — not in `.env` or memory.

### Tests
```bash
uv run pytest tests/ -v
```

All new features need a test in `tests/`. Mocking `ollama.Client` is acceptable for unit tests.
Integration tests must not require a live Ollama instance.

### Verification checklist before commit
1. `python3 -m py_compile ai_grader/*.py` — no syntax errors
2. `uv run pytest tests/ -q` — all green
3. Version bumped in **both** `pyproject.toml` and `ai_grader/__init__.py`
4. `CLAUDE.md` updated if architecture changed

### Release process
```bash
uv build
# Then GitHub release via curl + PAT (no gh CLI)
curl -X POST https://api.github.com/repos/lerlerchan/ai-grader/releases \
  -H "Authorization: token $GITHUB_PAT" \
  -d '{"tag_name":"vX.Y.Z","name":"vX.Y.Z — ...","body":"..."}'
```

### Windows build
PyInstaller must run **on Windows** — cannot cross-compile from Linux.
Build scripts: `scripts/build-windows.bat`, `scripts/build-windows.ps1`.

---

## Key Behaviours

- **Filename convention**: `Name_CourseCode_Year_AssessmentName_StudentID.pdf`
  Regex extracts student ID and name; unmatched filenames use full stem.
- **Failed marks**: `-1` = AI parse failure. Flagged red in Excel, listed in CLI warnings.
- **Ollama API key**: optional `Authorization: Bearer` header — passed through GUI form → `grader.py`.
- **Theme**: GUI supports `brown` (dark) and `light` (cream) themes via CSS variables, persisted in `localStorage`.
- **Auto-detect questions**: `/api/detect-questions` endpoint — model reads scheme and returns comma-separated question labels.
