import sys
import types
from pathlib import Path

import pytest

from ai_grader.scheme_parser import load_scheme


def test_load_scheme_reads_markdown_directly(tmp_path: Path) -> None:
    scheme_path = tmp_path / "scheme.md"
    scheme_path.write_text("# Scheme\n\nQ1: 1 mark", encoding="utf-8")

    assert load_scheme(str(scheme_path)) == "# Scheme\n\nQ1: 1 mark"


def test_load_scheme_uses_markitdown_for_docx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeMarkItDown:
        def convert(self, path: str) -> types.SimpleNamespace:
            return types.SimpleNamespace(text_content=f"converted:{path}")

    monkeypatch.setitem(
        sys.modules,
        "markitdown",
        types.SimpleNamespace(MarkItDown=FakeMarkItDown),
    )

    scheme_path = tmp_path / "scheme.docx"
    converted = load_scheme(str(scheme_path))

    assert converted == f"converted:{scheme_path}"


def test_load_scheme_wraps_markitdown_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeMarkItDown:
        def convert(self, path: str) -> types.SimpleNamespace:
            raise ValueError("broken document")

    monkeypatch.setitem(
        sys.modules,
        "markitdown",
        types.SimpleNamespace(MarkItDown=FakeMarkItDown),
    )

    with pytest.raises(RuntimeError, match="Failed to parse marking scheme"):
        load_scheme(str(tmp_path / "bad_scheme.docx"))
