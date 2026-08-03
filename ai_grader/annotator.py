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
