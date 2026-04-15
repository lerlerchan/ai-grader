"""
submission_loader.py — Discover and load student submissions.

Auto-detects grading mode per file:
  - PDF with little/no extractable text → vision mode (base64 images via PyMuPDF)
  - PDF with text / DOCX / TXT / MD    → text mode (MarkItDown extraction)
"""

import base64
import os
import re
from dataclasses import dataclass, field
from typing import Literal

# Minimum characters of extracted text to consider a PDF "typed" (not scanned/handwritten)
_TEXT_THRESHOLD = 50

# Filename pattern:  <Name>_MATH2083_2026A_quiz_D240051A.pdf
# Handles: double extension, missing underscore before ID
_FILENAME_RE = re.compile(
    r"^(.+?)_[A-Z0-9]+_\d{4}[A-Z]_[^_]+_?([A-Z]\d+[A-Z])(?:\.(?:pdf|docx|txt|md))+$",
    re.IGNORECASE,
)

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Submission:
    student_id: str
    name: str
    path: str
    mode: Literal["vision", "text"] = "vision"
    # Populated by load()
    images: list[str] = field(default_factory=list)   # base64 PNGs (vision mode)
    text: str = ""                                      # extracted text (text mode)


def parse_filename(filename: str) -> tuple[str, str]:
    """
    Extract (student_id, name) from filename.
    Falls back to (stem, stem) if the pattern doesn't match.
    """
    m = _FILENAME_RE.match(filename)
    if m:
        name_raw, student_id = m.group(1), m.group(2)
        name = re.sub(r"_+", " ", name_raw).strip()
        name = re.sub(r"\s+", " ", name)
        return student_id, name

    # Fallback: use full filename stem
    stem = os.path.splitext(filename)[0]
    # Strip double extension (e.g. .pdf.pdf)
    stem = re.sub(r"\.(pdf|docx|txt|md)$", "", stem, flags=re.IGNORECASE)
    return stem, stem


def discover(folder: str) -> list[Submission]:
    """Return a Submission object for every supported file in folder."""
    submissions = []
    for filename in sorted(os.listdir(folder)):
        ext = os.path.splitext(filename)[1].lower()
        # Handle double extensions like .pdf.pdf
        if filename.lower().endswith(".pdf.pdf"):
            ext = ".pdf"
        if ext not in SUPPORTED_EXTS:
            continue
        student_id, name = parse_filename(filename)
        submissions.append(Submission(
            student_id=student_id,
            name=name,
            path=os.path.join(folder, filename),
        ))
    return submissions


def load(submission: Submission, dpi: int = 150) -> Submission:
    """
    Populate submission.images (vision) or submission.text (text mode).
    Modifies and returns the submission in place.
    """
    ext = os.path.splitext(submission.path)[1].lower()
    if submission.path.lower().endswith(".pdf.pdf"):
        ext = ".pdf"

    if ext == ".pdf":
        _load_pdf(submission, dpi)
    else:
        _load_text(submission)

    return submission


# ── PDF loader ────────────────────────────────────────────────────────────────

def _load_pdf(submission: Submission, dpi: int) -> None:
    import fitz  # pymupdf

    doc = fitz.open(submission.path)

    # Try text extraction to decide mode
    all_text = "".join(page.get_text() for page in doc).strip()

    if len(all_text) >= _TEXT_THRESHOLD:
        submission.mode = "text"
        submission.text = all_text
    else:
        submission.mode = "vision"
        doc.close()
        doc = fitz.open(submission.path)
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            submission.images.append(
                base64.b64encode(pix.tobytes("png")).decode("utf-8")
            )

    doc.close()


# ── Text/document loader ──────────────────────────────────────────────────────

def _load_text(submission: Submission) -> None:
    ext = os.path.splitext(submission.path)[1].lower()
    submission.mode = "text"

    if ext in (".txt", ".md"):
        with open(submission.path, encoding="utf-8", errors="replace") as f:
            submission.text = f.read()
        return

    # DOCX / PPTX via MarkItDown
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(submission.path)
        submission.text = result.text_content
    except ImportError:
        raise RuntimeError(
            "markitdown is required to read .docx/.pptx files.\n"
            "Install it: pip install markitdown"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to read '{submission.path}': {e}") from e
