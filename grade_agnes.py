#!/usr/bin/env python3
"""
AI Grader with AGNES (OpenAI-compatible) instead of Ollama.

Uses the ai-grader pipeline components but calls AGNES via OpenAI client.
"""
import sys
sys.path.insert(0, "/home/lerler/github/ai-grader")

from ai_grader.scheme_parser import load_scheme
from ai_grader.submission_loader import discover, load, Submission
from ai_grader.exporter import write_results
import os
import json
import base64
from pathlib import Path
from openai import OpenAI

# AGNES config (from your Hermes .env)
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_MODEL = "agnes-2.5-flash"

# Auto-load AGNES key from ~/.hermes/.env if not in env
if not os.getenv("AGNES_AI_API_KEY"):
    try:
        with open(os.path.expanduser("~/.hermes/.env")) as f:
            for line in f:
                line = line.strip()
                if line.startswith("AGNES_AI_API_KEY="):
                    os.environ["AGNES_AI_API_KEY"] = line.split("=", 1)[1]
    except FileNotFoundError:
        pass

AGNES_KEY = os.getenv("AGNES_AI_API_KEY", "").strip()

if not AGNES_KEY:
    print("ERROR: AGNES_AI_API_KEY not set in environment")
    sys.exit(1)

client = OpenAI(base_url=AGNES_BASE_URL, api_key=AGNES_KEY)

_SYSTEM_PROMPT = """You are an experienced teacher marking a student quiz.

Below is the official marking scheme:

{scheme}

INSTRUCTIONS:
- Carefully examine the student's work (images or text provided).
- Award marks based on demonstrated understanding. Use partial credit generously
where the student shows partial knowledge or correct method with minor errors.
- The submission may be handwritten and OCR-extracted; spelling errors, merged
words, or garbled characters do NOT count against the student — focus on
mathematical/conceptual correctness and intent.
- All mark values must be non-negative integers within the range shown for each question.
- Return ONLY a valid JSON object — no explanation outside the JSON.

Required JSON format (use exactly these question keys):
{{
  "questions": {{
{question_format}
  }},
  "reasoning": {{
{reasoning_format}
  }}
}}

If a question is genuinely blank (no attempt at all), award 0."""

_USER_PROMPT_VISION = "Here is the student's submission (scanned pages). Mark each question and return the JSON."
_USER_PROMPT_TEXT = "Here is the student's submission:\n\n{text}\n\nMark each question and return the JSON."


def grade_agnes(
    submission: Submission,
    scheme_text: str,
    questions: list[str],
) -> dict:
    """Grade using AGNES (OpenAI-compatible)."""
    question_format = "\n".join(f'    "{q}": <integer>,' for q in questions)
    reasoning_format = "\n".join(f'    "{q}": "<brief justification>",' for q in questions)

    system = _SYSTEM_PROMPT.format(
        scheme=scheme_text,
        question_format=question_format,
        reasoning_format=reasoning_format,
    )

    if submission.mode == "vision":
        # AGNES expects images as base64 data URLs in content array
        content = [
            {"type": "text", "text": "Here is the student's submission (scanned pages). Mark each question and return the JSON."},
            *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}} for img in submission.images],
        ]
    else:
        content = [{"type": "text", "text": f"Here is the student's submission:\n\n{submission.text}\n\nMark each question and return the JSON."}]

    response = client.chat.completions.create(
        model=AGNES_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        temperature=0.1,
        max_tokens=4000,
        extra_body={"reasoning_effort": "none"},
    )

    raw = response.choices[0].message.content
    return _parse_response(raw, questions)


def _parse_response(raw: str, questions: list[str]) -> dict:
    blank = {q: -1 for q in questions}
    blank["reasoning"] = {q: "" for q in questions}

    def _try(text: str):
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
            return result
        except Exception:
            return None

    parsed = _try(raw)
    if parsed:
        return parsed

    # Try to find JSON block
    import re
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        parsed = _try(match.group())
        if parsed:
            return parsed

    return blank


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", required=True, help="Marking scheme file (.md, .txt, .pdf, .docx)")
    ap.add_argument("--submissions", required=True, help="Folder with student submission PDFs")
    ap.add_argument("--questions", required=True, help="Comma-separated question labels, e.g. Q1,Q2,Q3")
    ap.add_argument("--output", default="marks.xlsx", help="Output Excel file")
    args = ap.parse_args()

    questions = [q.strip() for q in args.questions.split(",")]

    # Load scheme
    print(f"Loading scheme: {args.scheme}")
    scheme_text = load_scheme(args.scheme)
    print(f"Scheme loaded: {len(scheme_text)} chars")

    # Load submissions
    print(f"Loading submissions from: {args.submissions}")
    subs = discover(args.submissions)
    print(f"Found {len(subs)} submissions")

    # Load each submission (parse PDF/text)
    submissions = []
    for i, sub in enumerate(subs, 1):
        print(f"  Parsing {sub.student_id} ({sub.mode})...", end=" ", flush=True)
        try:
            loaded = load(sub, dpi=75)
            submissions.append(loaded)
            print(f"OK ({loaded.mode})")
        except Exception as e:
            print(f"ERROR: {e}")
            # Create a dummy submission with error
            sub.text = f"ERROR loading: {e}"
            sub.mode = "text"
            submissions.append(sub)

    # Grade each
    results = []
    for i, sub in enumerate(submissions, 1):
        print(f"[{i}/{len(submissions)}] Grading {sub.student_id} ({sub.mode})...", end=" ", flush=True)
        try:
            result = grade_agnes(sub, scheme_text, questions)
            result["student_id"] = sub.student_id
            result["student_name"] = sub.name
            result["name"] = sub.name
            result["filename"] = os.path.basename(sub.path)
            results.append(result)
            marks = [result.get(q, -1) for q in questions]
            print(f"marks={marks}")
        except Exception as e:
            print(f"ERROR: {e}")
            blank = {q: -1 for q in questions}
            blank["reasoning"] = {q: f"ERROR: {e}" for q in questions}
            blank.update({"student_id": sub.student_id, "student_name": sub.name, "name": sub.name, "filename": os.path.basename(sub.path)})
            results.append(blank)

    # Export
    print(f"Exporting to {args.output}...")
    out_dir = os.path.dirname(args.output) or "."
    out_base = os.path.basename(args.output)
    # write_results expects (results, output_dir, questions, formats)
    # We'll just write excel to the desired path
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    _HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    _HEADER_FONT = Font(color="FFFFFF", bold=True)
    _FLAG_FILL = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Marks"
    headers = ["student_id", "name"] + questions + ["total"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    for r in results:
        q_vals = [r.get(q, -1) for q in questions]
        total = sum(q_vals) if all(v >= 0 for v in q_vals) else -1
        row = [r["student_id"], r["name"]] + q_vals + [total]
        ws.append(row)
        if total < 0:
            for cell in ws[ws.max_row]:
                cell.fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max(max_len + 2, 12)
    ws2 = wb.create_sheet("Reasoning")
    reason_headers = ["student_id", "name"] + [f"{q}_reason" for q in questions]
    ws2.append(reason_headers)
    for cell in ws2[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    for r in results:
        reasoning = r.get("reasoning", {})
        ws2.append([r["student_id"], r["name"]] + [reasoning.get(q, "") for q in questions])
    for col in ws2.columns:
        ws2.column_dimensions[col[0].column_letter].width = 40
    wb.save(args.output)
    print("Done.")


if __name__ == "__main__":
    main()