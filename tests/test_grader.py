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
        "location": {},
    }


def test_parse_response_extracts_json_wrapped_in_extra_text() -> None:
    raw = 'Here is the result: {"questions": {"Q1": 1}, "reasoning": {"Q1": "ok"}}'

    parsed = _parse_response(raw, ["Q1"])

    assert parsed["Q1"] == 1
    assert parsed["reasoning"]["Q1"] == "ok"
    assert parsed["location"] == {}


def test_parse_response_returns_blank_scores_on_invalid_json() -> None:
    parsed = _parse_response("definitely not json", ["Q1", "Q2"])

    assert parsed == {
        "Q1": -1,
        "Q2": -1,
        "reasoning": {"Q1": "", "Q2": ""},
        "location": {},
    }


def test_parse_response_captures_valid_locations() -> None:
    raw = """
    {
      "questions": {"Q1": 2, "Q2": 1},
      "reasoning": {"Q1": "ok", "Q2": "partial"},
      "location": {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": 2, "region": "bottom-right"}
      }
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2"])

    assert parsed["location"] == {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": 2, "region": "bottom-right"},
    }


def test_parse_response_drops_invalid_locations() -> None:
    raw = """
    {
      "questions": {"Q1": 2, "Q2": 1, "Q3": 0},
      "reasoning": {"Q1": "ok", "Q2": "partial", "Q3": "blank"},
      "location": {
        "Q1": {"page": 1, "region": "top-left"},
        "Q2": {"page": "not-a-number", "region": "top-left"},
        "Q3": {"page": 1, "region": "center"}
      }
    }
    """

    parsed = _parse_response(raw, ["Q1", "Q2", "Q3"])

    assert parsed["location"] == {"Q1": {"page": 1, "region": "top-left"}}
