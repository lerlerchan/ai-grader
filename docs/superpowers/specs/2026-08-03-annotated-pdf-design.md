# Annotated PDF Output — Design Spec

Date: 2026-08-03
Status: Approved

## Problem

Teacher runs ai-grader remotely (Linux host `k45vd`, accessed over Tailscale
from a Windows 11 client where submissions live in OneDrive). After grading,
`marks.xlsx`/`marks.csv` are downloaded back to the OneDrive folder, but the
teacher needs a marked-up copy of each student's original PDF — badges near
each answer plus a summary — to justify grades to management and students.
Today ai-grader produces no PDF output at all, only the spreadsheet.

Separately: k45vd accumulates uploaded submission PDFs across batches with no
cleanup path, so disk usage grows unbounded over time.

## Approach

Extend the existing grading pipeline (not a separate post-process pass) with
three additions:

1. **Grader schema extension** — the JSON the model already returns per
   question gains an optional `location` field: `{"page": int, "region": str}`
   where `region` is one of six values: `top-left`, `top-right`, `mid-left`,
   `mid-right`, `bottom-left`, `bottom-right`. The model already receives each
   page as an image in vision mode, so it can name where an answer roughly sits
   without new API calls. Pixel-perfect bounding boxes were explicitly rejected
   as unrealistic for handwritten/OCR content — this is a best-effort visual
   pointer, not a source of truth.

2. **`ai_grader/annotator.py`** — new module, one public function:
   `annotate(submission: Submission, marks: dict, output_path: str) -> None`.
   - Opens `submission.path` with PyMuPDF (already a dependency).
   - Inserts a new page 0 (cover page): student name, student ID, per-question
     marks table, total, and the full reasoning text already returned by the
     grader. This cover page is the authoritative record — full detail always
     lives here regardless of whether on-page badges succeeded.
   - For each question with a valid `location` (page in range, region
     recognized), draws a small badge (filled rect + text, e.g. `"Q3: 2/3"`)
     at the region's mapped page-relative coordinates (2×3 grid over page
     width/height fractions) on that question's source page.
   - Any question with missing/invalid location is silently skipped for the
     badge — its marks still appear on the cover page. Never raises for a
     single bad location; mirrors the existing `-1`-on-parse-failure pattern
     in `grader.py`.
   - Saves as a new PDF (original untouched) at `output_path`.

3. **Output layout** — for a batch export, alongside the existing
   `marks.xlsx`/`marks.csv`, a new `annotated/` subfolder is created in the
   same output directory containing one file per submission:
   `annotated/<StudentName>_<StudentID>.pdf` (reusing the existing filename
   parsing from `submission_loader.parse_filename`).

4. **GUI "Clear this batch" button** — appears only after export completes.
   Requires a confirm dialog. Deletes the batch's uploaded submission files
   (the raw PDFs copied into k45vd during upload) — never touches
   `marks.xlsx`, `marks.csv`, or the `annotated/` folder, since those are
   presumed already downloaded to OneDrive by the time cleanup runs. No
   automatic/timed deletion — deletion is always an explicit teacher action.

## Data flow

```
upload (browser → k45vd) → discover/load (submission_loader)
  → grade (grader.py, now returns marks + reasoning + location)
    → export (exporter.py, unchanged: marks.xlsx/csv)
    → annotate (annotator.py, new: annotated/<name>.pdf per submission)
  → teacher downloads marks.xlsx + annotated/ folder to OneDrive
  → teacher clicks "Clear this batch" → submissions deleted from k45vd
```

## Error handling

- Malformed/missing `location` for a question → skip that question's badge,
  cover page still shows correct marks. Batch-level grading is unaffected.
- `location.page` outside the submission's actual page range → same skip
  behavior.
- Annotator failure on a single submission (e.g. corrupted source PDF) should
  not abort the batch — log and continue to the next submission, same as
  existing per-submission error handling elsewhere in the pipeline.
- "Clear this batch" deletion requires explicit confirm; scoped to the
  batch's submission files only.

## Testing

- `tests/test_annotator.py`: build a throwaway 1-page PDF via PyMuPDF in the
  test itself, run `annotate()` with a mix of valid and invalid/missing
  locations, assert: cover page is present at index 0, badge count on
  original pages matches only the valid locations, and a malformed location
  does not raise.
- No integration test requiring live Ollama (per existing project convention
  in CLAUDE.md).

## Out of scope

- Pixel-precise bounding-box annotation.
- Auto-expiring/timed deletion of submissions.
- Any change to `exporter.py`'s existing Excel/CSV output format.
