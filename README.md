# ai-grader

> Local AI grading assistant for teachers — runs 100% on your machine, no cloud, no data leaks.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Why ai-grader?

- **Privacy-first** — student data never leaves your machine
- **Any format** — PDF (handwritten or typed), Word, plain text
- **Any marking scheme** — paste it as Markdown, PDF, or Word doc
- **Any local model** — works with any Ollama vision model (Gemma, LLaMA, Qwen…)
- **Excel + CSV output** — open straight in Excel or Google Sheets

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download) running locally
- A vision-capable Ollama model (for handwritten PDFs)

---

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt
pip install -e .

# 2. Pull a model (vision-capable recommended)
ollama pull gemma4:12b

# 3. Mark
ai-grader mark \
  --scheme marking_scheme.md \
  --submissions ./submissions/ \
  --model gemma4:12b
```

Results are saved to `./output/marks.xlsx` and `./output/marks.csv`.

---

## Usage

```
ai-grader mark [OPTIONS]

Options:
  -s, --scheme PATH         Marking scheme file (.md, .txt, .pdf, .docx)  [required]
  -d, --submissions PATH    Folder of student submission files             [required]
  -m, --model TEXT          Ollama model name          [default: gemma4:12b]
  -o, --output PATH         Output directory           [default: ./output]
      --format TEXT         Export formats: excel, csv [default: excel,csv]
  -q, --questions TEXT      Question labels            [default: Q1,Q2,Q3,Q4]
      --ollama-host TEXT     Ollama API host            [default: http://localhost:11434]
      --dpi INTEGER         PDF render resolution      [default: 150]
```

### Example — custom questions

```bash
ai-grader mark \
  --scheme scheme.md \
  --submissions ./class_a/ \
  --questions "Q1,Q2,Q3" \
  --format csv
```

---

## How it works

1. **Scheme** — loads your marking scheme from any supported format
2. **Detect** — for each submission, detects automatically:
   - Handwritten/scanned PDF → **vision mode** (pages sent as images to the LLM)
   - Typed PDF / Word / text → **text mode** (text extracted, sent as prompt)
3. **Grade** — sends each submission to a locally-running Ollama model with the scheme as context
4. **Export** — writes Excel + CSV with student ID, name, per-question marks, total, and AI reasoning

---

## Supported formats

| File type | Mode |
|-----------|------|
| `.pdf` (handwritten / scanned) | Vision |
| `.pdf` (typed / digital) | Text |
| `.docx` | Text (via MarkItDown) |
| `.txt` / `.md` | Text |

---

## Filename convention (for automatic student ID extraction)

Name your submission files like:

```
StudentName_CourseCode_Year_AssessmentName_StudentID.pdf
```

Example:
```
John_Doe_MATH101_2026A_quiz_D240051A.pdf
```

If the filename doesn't match this pattern, the full filename is used as the student name.

---

## Output

### marks.xlsx
| student_id | name | Q1 | Q2 | Q3 | Q4 | total |
|---|---|---|---|---|---|---|
| D240051A | John Doe | 4 | 5 | 3 | 5 | 17 |

A second **Reasoning** sheet shows the AI's justification for each mark.

Rows with failed marks (`-1`) are highlighted red for manual review.

### marks.csv
Same data as the Marks sheet, plain CSV for Excel/Google Sheets import.

---

## Privacy

- No internet connection required after setup
- No telemetry, no data sent to any cloud service
- All grading happens on your machine via Ollama

---

## Contributing

Pull requests welcome. See [PRD.md](PRD.md) for the product vision and roadmap.

---

## License

MIT
