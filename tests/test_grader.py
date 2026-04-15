from ai_grader.grader import _parse_response


def test_parse_response_accepts_valid_json() -> None:
    raw = """
    {
      "questions": {"Q1": 1, "Q2": 0},
      "reasoning": {"Q1": "exact match", "Q2": "missing answer"}
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2"])

    assert parsed == {
        "Q1": 1,
        "Q2": 0,
        "reasoning": {"Q1": "exact match", "Q2": "missing answer"},
    }


def test_parse_response_extracts_json_wrapped_in_extra_text() -> None:
    raw = 'Here is the result: {"questions": {"Q1": 1}, "reasoning": {"Q1": "ok"}}'

    parsed = _parse_response(raw, ["Q1"])

    assert parsed["Q1"] == 1
    assert parsed["reasoning"]["Q1"] == "ok"


def test_parse_response_returns_blank_scores_on_invalid_json() -> None:
    parsed = _parse_response("definitely not json", ["Q1", "Q2"])

    assert parsed == {
        "Q1": -1,
        "Q2": -1,
        "reasoning": {"Q1": "", "Q2": ""},
    }
