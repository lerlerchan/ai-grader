# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip install -r requirements.txt
pip install -e .
ollama pull gemma4:12b   # or any vision-capable model
```

## Run

```bash
ai-grader mark \
  --scheme examples/sample_scheme.md \
  --submissions ./submissions/ \
  --model gemma4:12b \
  --questions "Q1,Q2,Q3,Q4"
```

Ollama must be running (`ollama serve`) before invoking the CLI. Override host via `OLLAMA_HOST` env var or `--ollama-host`.

## Architecture

Single CLI entry point (`ai_grader/cli.py` → `ai-grader mark`) orchestrates a linear pipeline:

1. **`scheme_parser.py`** — loads marking scheme (`.md`/`.txt` raw read; `.pdf`/`.docx`/`.pptx` via MarkItDown) → returns plain text
2. **`submission_loader.py`** — discovers files in submission folder, parses student ID/name from filename, then `load()` auto-detects mode:
   - PDF with <50 chars extracted text → **vision mode** (PyMuPDF renders pages as base64 PNG)
   - PDF with text / `.docx` / `.txt` / `.md` → **text mode** (MarkItDown or plain read)
3. **`grader.py`** — sends scheme + submission to Ollama; vision submissions attach images, text submissions embed text in prompt; parses strict JSON response with regex fallback; returns `{Q1: int, Q2: int, ..., reasoning: {Q1: str, ...}}`; failed parse returns `-1` for all marks
4. **`exporter.py`** — writes `marks.xlsx` (Marks sheet + Reasoning sheet, red highlight on `-1`) and `marks.csv` to output dir

## Key Behaviours

- **Filename convention**: `Name_CourseCode_Year_AssessmentName_StudentID.pdf` — regex extracts student ID and name; unmatched filenames use full stem
- **Failed marks**: any question scoring `-1` means AI parse failure; rows flagged red in Excel and listed as warnings in CLI output
- **Double extension**: `.pdf.pdf` filenames handled explicitly throughout the pipeline
- **`total` column**: set to `-1` if any question in the row is `-1` (avoids false partial totals)
