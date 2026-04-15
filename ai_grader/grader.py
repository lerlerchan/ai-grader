"""
grader.py — Send a submission to Ollama and return per-question marks.

Supports both vision mode (images) and text mode.
"""

import json
import re

import ollama

from .submission_loader import Submission

_SYSTEM_PROMPT = """\
You are an experienced teacher marking a student quiz.

Below is the official marking scheme:

{scheme}

INSTRUCTIONS:
- Carefully examine the student's work (images or text provided).
- Award marks strictly according to the marking scheme above.
- All mark values must be integers within the range shown for each question.
- Return ONLY a valid JSON object — no explanation outside the JSON.

Required JSON format:
{{
  "questions": {{
    "Q1": <integer>,
    "Q2": <integer>,
    "Q3": <integer>,
    "Q4": <integer>
  }},
  "reasoning": {{
    "Q1": "<brief justification>",
    "Q2": "<brief justification>",
    "Q3": "<brief justification>",
    "Q4": "<brief justification>"
  }}
}}

If the student's work for a question is blank or unreadable, award 0 for that question.
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
) -> dict:
    """
    Grade a single submission. Returns a dict:
      {"Q1": int, "Q2": int, ..., "reasoning": {"Q1": str, ...}}
    Mark values default to -1 on parse failure.
    """
    if questions is None:
        questions = ["Q1", "Q2", "Q3", "Q4"]

    client = ollama.Client(host=ollama_host)
    system = _SYSTEM_PROMPT.format(scheme=scheme_text)

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

    def _try(text: str) -> dict | None:
        try:
            data = json.loads(text.strip())
            result = {}
            q_data = data.get("questions", data)
            for q in questions:
                val = q_data.get(q, -1)
                result[q] = int(val) if isinstance(val, (int, float)) else -1
            result["reasoning"] = data.get("reasoning", {q: "" for q in questions})
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
