"""
grader.py — Send a submission to Ollama and return per-question marks.

Supports both vision mode (images) and text mode.
"""

import json
import re

import ollama

from .submission_loader import Submission

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

_USER_PROMPT_VISION = (
    "Here is the student's submission (scanned pages). "
    "Mark each question and return the JSON."
)

_USER_PROMPT_TEXT = (
    "Here is the student's submission:\n\n{text}\n\n"
    "Mark each question and return the JSON."
)


def grade(
    submission: Submission,
    scheme_text: str,
    model: str,
    ollama_host: str = "http://localhost:11434",
    questions: list[str] | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Grade a single submission. Returns a dict:
      {"Q1": int, "Q2": int, ..., "reasoning": {"Q1": str, ...}, "location": {"Q1": {"page": int, "region": str}, ...}}
    Mark values default to -1 on parse failure. "location" only contains entries
    the model reported validly; questions with no/invalid location are absent.
    """
    if questions is None:
        questions = ["Q1", "Q2", "Q3", "Q4"]

    question_format = "\n".join(f'    "{q}": <integer>,' for q in questions)
    reasoning_format = "\n".join(f'    "{q}": "<brief justification>",' for q in questions)
    location_format = "\n".join(
        f'    "{q}": {{"page": <integer>, "region": "<top-left|top-right|mid-left|mid-right|bottom-left|bottom-right>"}},'
        for q in questions
    )

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    client = ollama.Client(host=ollama_host, headers=headers)
    system = _SYSTEM_PROMPT.format(
        scheme=scheme_text,
        question_format=question_format,
        reasoning_format=reasoning_format,
        location_format=location_format,
    )

    if submission.mode == "vision":
        message = {
            "role": "user",
            "content": _USER_PROMPT_VISION,
            "images": submission.images,
        }
    else:
        message = {
            "role": "user",
            "content": _USER_PROMPT_TEXT.format(text=submission.text),
        }

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            message,
        ],
    )

    raw = response["message"]["content"]
    return _parse_response(raw, questions)


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
